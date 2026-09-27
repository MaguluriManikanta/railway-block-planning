"""
Controller Requests Workflow & Preprocessing Module (STEP 5)
Handles:
- Request data retrieval from SQLite repository (block_requests_v2 & defects)
- Separation of unprocessed requests into NEW REQUESTS and OVERDUE REQUESTS
- Dynamic calculation of overdue status and overdue durations (e.g. '16h 32m', '2h 35m', '1d 4h 12m')
- Department normalization (Engineering, OHE/Traction, S&T)
- Individual request cards with View Details
- Filtering & sorting inside the Requests modal
- Preserved floating chatbot & underlying map integrity
- Zero manual dependency or isolation inputs (enforced by design)
"""

import os
import re
import sqlite3
import textwrap
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st


def clean_html(html_str: str) -> str:
    """Removes leading indentation on all lines so markdown never renders HTML as code blocks."""
    if not html_str:
        return ""
    return re.sub(r'^[ \t]+', '', str(html_str), flags=re.MULTILINE)


DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")


def init_reported_defects_db(db_path: str = DB_PATH):
    """Ensures reported_defects table exists in SQLite database."""
    try:
        conn = sqlite3.connect(db_path, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reported_defects (
                defect_id TEXT PRIMARY KEY,
                reporter_type TEXT NOT NULL,
                reporter_name TEXT NOT NULL,
                contact_info TEXT NOT NULL,
                division TEXT NOT NULL,
                section TEXT NOT NULL,
                station TEXT NOT NULL,
                track_km_details TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                problem_brief TEXT NOT NULL,
                detailed_description TEXT NOT NULL,
                department TEXT NOT NULL,
                severity TEXT DEFAULT 'Not Yet Assessed',
                status TEXT DEFAULT 'New',
                department_analysis TEXT,
                recommended_action TEXT,
                assessed_by TEXT,
                assessed_at TEXT,
                block_request_id TEXT,
                reported_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


# Ensure initialized on module load
init_reported_defects_db()


# =============================================================================
# 1. PARSING & NORMALIZATION
# =============================================================================

def parse_deadline_datetime(deadline_raw, reported_time_raw=None, current_time=None) -> datetime:
    """
    Parses deadline string into a datetime object using standard Indian Railways formats.
    """
    if current_time is None:
        current_time = datetime.now()
        
    if not deadline_raw:
        # Default: 24h after reported_time or 24h from now
        if reported_time_raw:
            try:
                rep_dt = datetime.strptime(str(reported_time_raw).strip()[:19], "%Y-%m-%d %H:%M:%S")
                return rep_dt + timedelta(hours=24)
            except Exception:
                pass
        return current_time + timedelta(hours=24)

    deadline_str = str(deadline_raw).strip()

    # Format 1: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DD HH:MM"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(deadline_str[:19], fmt)
        except Exception:
            pass

    # Format 2: "YYYY-MM-DD" or "DD/MM/YYYY" -> set to 18:00:00 of that day
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            d = datetime.strptime(deadline_str[:10], fmt)
            return datetime(d.year, d.month, d.day, 18, 0, 0)
        except Exception:
            pass

    # Format 3: Relative expressions like "URGENT (< 4 Hours)"
    if "URGENT" in deadline_str.upper() or "< 4" in deadline_str:
        if reported_time_raw:
            try:
                rep_dt = datetime.strptime(str(reported_time_raw).strip()[:19], "%Y-%m-%d %H:%M:%S")
                return rep_dt + timedelta(hours=4)
            except Exception:
                pass
        return current_time - timedelta(hours=1) # Mark overdue if urgent in past

    return current_time + timedelta(hours=24)


def format_overdue_duration(overdue_seconds: float) -> str:
    """
    Formats overdue duration into readable railway notation:
    '2h 35m' or '1d 4h 12m' or '45m'.
    """
    if overdue_seconds < 0:
        return "0m"
    
    total_mins = int(overdue_seconds // 60)
    days = total_mins // (24 * 60)
    rem_mins = total_mins % (24 * 60)
    hours = rem_mins // 60
    mins = rem_mins % 60

    if days > 0:
        return f"{days}d {hours}h {mins}m"
    elif hours > 0:
        return f"{hours}h {mins}m"
    else:
        return f"{max(1, mins)}m"


def normalize_department_name(dept_raw: str) -> str:
    """Normalizes raw department string into standard UI format."""
    d_clean = str(dept_raw or "").strip().upper()
    if "ENG" in d_clean:
        return "Engineering"
    elif "TEND" in d_clean:
        return "Tenders"
    elif "OHE" in d_clean or "TRD" in d_clean or "TRAC" in d_clean:
        return "OHE/Traction"
    elif "S&T" in d_clean or "S_AND_T" in d_clean or "SIG" in d_clean or "TELE" in d_clean:
        return "S&T"
    else:
        return dept_raw or "Engineering"


def parse_request_record(raw_dict: dict, current_time: datetime = None) -> dict:
    """
    Parses and standardizes any raw request record into the unified Step 5 model.
    Calculates overdue status dynamically without altering stored timestamps.
    """
    if current_time is None:
        current_time = datetime.now()

    req_id = str(raw_dict.get("request_id") or raw_dict.get("defect_id") or "REQ-001")
    dept = normalize_department_name(raw_dict.get("department", "Engineering"))
    req_type = str(raw_dict.get("request_type") or raw_dict.get("defect_type") or "Track Maintenance")
    desc = str(raw_dict.get("reason") or raw_dict.get("task_description") or raw_dict.get("justification") or f"{req_type} corridor maintenance work")
    
    # Strip any internal [DEMO] tags for clean user display, while keeping source flag
    clean_desc = re.sub(r"^\[DEMO\]\s*", "", desc).strip()
    
    section = str(raw_dict.get("section") or raw_dict.get("section_id") or "Vijayawada–Kondapalli")
    line = str(raw_dict.get("line") or "DOWN Line")
    
    # Derive block name
    block_val = raw_dict.get("block") or raw_dict.get("block_id") or raw_dict.get("location")
    if not block_val or "KM" in str(block_val):
        block = f"BLK-{section[:3].upper()}-{int(float(raw_dict.get('from_km', 114.0))):03d}"
    else:
        block = str(block_val)

    from_km = float(raw_dict.get("from_km") or 114.0)
    to_km = float(raw_dict.get("to_km") or 118.0)
    if to_km < from_km:
        from_km, to_km = to_km, from_km

    # Duration in minutes
    dur_val = raw_dict.get("required_duration", raw_dict.get("duration", 60))
    if isinstance(dur_val, str):
        try:
            dur_mins = int(float(dur_val.split()[0]))
        except Exception:
            dur_mins = 60
    else:
        dur_mins = int(dur_val or 60)

    priority = str(raw_dict.get("priority") or raw_dict.get("severity") or "High").capitalize()
    
    # Urgency derivation
    urgency = "HIGH" if priority in ["Critical", "High"] or "EMERGENCY" in str(raw_dict.get("archetype", "")).upper() else ("MEDIUM" if priority == "Medium" else "LOW")

    reported_time_str = str(raw_dict.get("reported_time") or raw_dict.get("created_at") or raw_dict.get("reported_date") or current_time.strftime("%Y-%m-%d %H:%M:%S"))
    deadline_raw = raw_dict.get("deadline") or raw_dict.get("due_date")
    deadline_dt = parse_deadline_datetime(deadline_raw, reported_time_str, current_time)
    required_by_str = deadline_dt.strftime("%Y-%m-%d %H:%M")

    # Date requested
    req_date = str(raw_dict.get("preferred_start") or raw_dict.get("requested_date") or deadline_dt.strftime("%Y-%m-%d"))
    if len(req_date) > 10:
        req_date = req_date[:10]

    raw_status = str(raw_dict.get("status") or "NEW").upper()

    # A request is classified / terminal if explicitly marked as such
    is_terminal = raw_status in ["ALLOCATED", "ACTIVE", "COMPLETED", "CANCELLED", "CLASSIFIED", "REJECTED"]
    
    is_overdue = False
    overdue_seconds = 0
    if not is_terminal:
        if "OVERDUE" in raw_status or "OVERDUE" in req_id.upper():
            is_overdue = True
            overdue_seconds = max(3600, (current_time - deadline_dt).total_seconds()) if current_time > deadline_dt else 14 * 3600 + 32 * 60
        elif current_time > deadline_dt and raw_status not in ["NEW", "SUBMITTED"]:
            is_overdue = True
            overdue_seconds = (current_time - deadline_dt).total_seconds()

    overdue_str = format_overdue_duration(overdue_seconds) if is_overdue else ""

    source_flag = "DEMO" if raw_dict.get("source") == "DEMO" or "DEMO" in req_id.upper() else "DATABASE"

    if is_terminal:
        final_status = raw_status
    elif is_overdue:
        final_status = "OVERDUE"
    else:
        final_status = "NEW"

    return {
        "request_id": req_id,
        "department": dept,
        "request_type": req_type,
        "description": clean_desc,
        "section": section,
        "line": line,
        "block": block,
        "from_km": from_km,
        "to_km": to_km,
        "date": req_date,
        "duration": dur_mins,
        "priority": priority,
        "urgency": urgency,
        "submitted_at": reported_time_str,
        "required_by": required_by_str,
        "deadline_dt": deadline_dt,
        "status": final_status,
        "is_overdue": is_overdue,
        "is_terminal": is_terminal,
        "overdue_seconds": overdue_seconds,
        "overdue_duration": overdue_str,
        "source": source_flag,
        "is_demo": (source_flag == "DEMO")
    }


# =============================================================================
# 2. ISOLATED DEMO DATASET (Requirement 23)
# =============================================================================

def get_demo_requests_dataset() -> list:
    """
    Provides an isolated DEMO dataset clearly tagged with source = 'DEMO'.
    Used when operational database does not contain enough test requests.
    """
    now = datetime.now()
    return [
        {
            "request_id": "ENG-104",
            "department": "Engineering",
            "request_type": "Track Maintenance & Tamping",
            "reason": "CSM Track tamping and ballast compaction after sleeper replacement",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-BZA-KI-01",
            "from_km": 570.0,
            "to_km": 575.0,
            "required_duration": 30,
            "priority": "High",
            "reported_time": (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "deadline": (now + timedelta(hours=22)).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "NEW",
            "source": "DEMO"
        },
        {
            "request_id": "OHE-203",
            "department": "OHE/Traction",
            "request_type": "Catenary Wire Adjustment",
            "reason": "Contact wire height inspection and dropper replacement at curve section",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-BZA-KI-01",
            "from_km": 572.0,
            "to_km": 576.0,
            "required_duration": 45,
            "priority": "High",
            "reported_time": (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"),
            "deadline": (now + timedelta(hours=21)).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "NEW",
            "source": "DEMO"
        },
        {
            "request_id": "S&T-301",
            "department": "S&T",
            "request_type": "Point Machine Calibration",
            "reason": "Point machine motor calibration and track circuit bond resistance check",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-BZA-KI-01",
            "from_km": 571.0,
            "to_km": 574.0,
            "required_duration": 30,
            "priority": "Medium",
            "reported_time": (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "deadline": (now + timedelta(hours=23)).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "NEW",
            "source": "DEMO"
        },
        {
            "request_id": "ENG-087",
            "department": "Engineering",
            "request_type": "Track Inspection & De-stressing",
            "reason": "USFD identified micro-flaw requiring immediate rail joint clamping and de-stressing",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-BZA-KI-01",
            "from_km": 570.0,
            "to_km": 573.0,
            "required_duration": 45,
            "priority": "High",
            "reported_time": (now - timedelta(hours=40)).strftime("%Y-%m-%d %H:%M:%S"),
            "deadline": (now - timedelta(hours=16, minutes=32)).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "OVERDUE",
            "source": "DEMO"
        },
        {
            "request_id": "S&T-055",
            "department": "S&T",
            "request_type": "Axle Counter Maintenance",
            "reason": "Axle counter transducer sensor drift attention and head tuning",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-BZA-KI-01",
            "from_km": 572.0,
            "to_km": 575.0,
            "required_duration": 40,
            "priority": "High",
            "reported_time": (now - timedelta(hours=28)).strftime("%Y-%m-%d %H:%M:%S"),
            "deadline": (now - timedelta(hours=4, minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
            "status": "OVERDUE",
            "source": "DEMO"
        }
    ]


# =============================================================================
# 3. REQUEST RETRIEVAL & FILTERING ENGINE
# =============================================================================

def fetch_controller_requests(
    division_name: str = "",
    dept_filter: str = "ALL",
    category_filter: str = "ALL",
    sort_by: str = "DEFAULT"
) -> tuple:
    """
    Fetches, standardizes, classifies, filters, and sorts all department block requests.
    Returns (new_requests_list, overdue_requests_list, new_count, overdue_count).
    """
    raw_records = []
    now = datetime.now()
    classified_req_ids = set()

    # 1. Fetch from SQLite block_requests_v2 table
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            cur = conn.cursor()

            # Collect all previously classified or resolved request IDs from classification history
            try:
                cur.execute("SELECT request_ids FROM request_classification_history")
                for (r_ids_str,) in cur.fetchall():
                    if r_ids_str:
                        for token in str(r_ids_str).split(","):
                            clean_tok = token.strip()
                            if clean_tok:
                                classified_req_ids.add(clean_tok)
            except Exception:
                pass

            # Collect all requests explicitly marked as CLASSIFIED, ALLOCATED, COMPLETED, CANCELLED, REJECTED
            try:
                cur.execute("SELECT request_id FROM block_requests_v2 WHERE status IN ('CLASSIFIED', 'ALLOCATED', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'REJECTED')")
                for (r_id,) in cur.fetchall():
                    if r_id:
                        classified_req_ids.add(str(r_id).strip())
            except Exception:
                pass

            cur.execute("""
                SELECT request_id, source, department, request_type, asset_type, location,
                       from_km, to_km, section, line, direction, reported_time, required_duration,
                       minimum_duration, preferred_start, deadline, priority, reason, status, archetype
                FROM block_requests_v2
                WHERE status NOT IN ('CANCELLED', 'REJECTED')
                ORDER BY 
                    CASE WHEN status IN ('NEW', 'SUBMITTED', 'PENDING', 'Pending') THEN 0 ELSE 1 END,
                    reported_time DESC,
                    rowid DESC
            """)
            cols = [col[0] for col in cur.description]
            for row in cur.fetchall():
                row_dict = dict(zip(cols, row))
                raw_records.append(row_dict)

            conn.close()
    except Exception:
        pass

    # 2. Standalone fallback only if SQLite database file does not exist on disk
    if not os.path.exists(DB_PATH) and not raw_records:
        for d_rec in get_demo_requests_dataset():
            raw_records.append(d_rec)

    # 3. Parse and standardize all records
    parsed_records = [parse_request_record(r, current_time=now) for r in raw_records]

    # 4. Separate into NEW and OVERDUE pending groups
    new_requests = []
    overdue_requests = []
    for r in parsed_records:
        r_id = str(r["request_id"]).strip()
        r_st = str(r.get("status", "")).upper()

        # Skip terminal / classified requests - they are already processed and no longer pending
        if r_id in classified_req_ids or r_st in ["CLASSIFIED", "ALLOCATED", "ACTIVE", "COMPLETED", "CANCELLED", "REJECTED"] or r.get("is_terminal"):
            continue

        if r.get("is_overdue") or r_st == "OVERDUE":
            overdue_requests.append(r)
        else:
            new_requests.append(r)

    # Total counts before UI filters
    total_new_count = len(new_requests)
    total_overdue_count = len(overdue_requests)

    # 5. Apply Department Filter
    if dept_filter and dept_filter.upper() != "ALL":
        target_dept = normalize_department_name(dept_filter)
        new_requests = [r for r in new_requests if r["department"] == target_dept]
        overdue_requests = [r for r in overdue_requests if r["department"] == target_dept]

    # 6. Apply Category Filter
    if category_filter and category_filter.upper() == "NEW REQUESTS":
        overdue_requests = []
    elif category_filter and category_filter.upper() == "OVERDUE REQUESTS":
        new_requests = []

    # 7. Apply Sorting
    # NEW Requests sorting
    if sort_by == "PRIORITY":
        pri_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        new_requests.sort(key=lambda r: (pri_order.get(r["priority"], 4), r["submitted_at"]))
        overdue_requests.sort(key=lambda r: (pri_order.get(r["priority"], 4), -r["overdue_seconds"]))
    elif sort_by == "DATE":
        new_requests.sort(key=lambda r: (r["date"], r["submitted_at"]))
        overdue_requests.sort(key=lambda r: (r["date"], -r["overdue_seconds"]))
    elif sort_by == "URGENCY":
        urg_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        new_requests.sort(key=lambda r: (urg_order.get(r["urgency"], 4), r["submitted_at"]))
        overdue_requests.sort(key=lambda r: (urg_order.get(r["urgency"], 4), -r["overdue_seconds"]))
    else: # DEFAULT: NEW by newest submitted, OVERDUE by longest overdue
        new_requests.sort(key=lambda r: r["submitted_at"], reverse=True)
        overdue_requests.sort(key=lambda r: r["overdue_seconds"], reverse=True)

    return new_requests, overdue_requests, total_new_count, total_overdue_count


def get_pending_request_counts() -> dict:
    """
    Returns live summary counts of unprocessed requests for the Controller header badge.
    """
    new_reqs, overdue_reqs, n_count, o_count = fetch_controller_requests()
    return {
        "total": n_count + o_count,
        "new": n_count,
        "overdue": o_count
    }


# =============================================================================
# 4. CARD & DETAILS UI COMPONENTS
# =============================================================================

def render_request_card(req: dict, is_overdue: bool = False, card_idx: int = 0):
    """
    Renders an individual request card adhering to Step 5 specifications.
    Shows individual request attributes without grouping or manual dependency/isolation fields.
    """
    # Department accent colors
    dept = req["department"]
    if dept == "Engineering":
        dept_color = "#3b82f6"
        dept_bg = "rgba(59, 130, 246, 0.15)"
        dept_icon = "🛤️"
    elif dept == "OHE/Traction":
        dept_color = "#f97316"
        dept_bg = "rgba(249, 115, 22, 0.15)"
        dept_icon = "⚡"
    else: # S&T
        dept_color = "#22c55e"
        dept_bg = "rgba(34, 197, 94, 0.15)"
        dept_icon = "🚦"

    # Status & Border styling
    if is_overdue:
        card_border = "#ef4444"
        card_bg = "rgba(239, 68, 68, 0.05)"
        status_badge = f"""
        <span style="background: #ef4444; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-size: 10.5px; font-weight: 800; letter-spacing: 0.5px;">
            🔴 OVERDUE • {req['overdue_duration']}
        </span>
        """
    else:
        card_border = "#334155"
        card_bg = "#0f172a"
        status_badge = """
        <span style="background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid #10b981; padding: 2px 8px; border-radius: 4px; font-size: 10.5px; font-weight: 800;">
            🟢 NEW REQUEST
        </span>
        """

    # Priority styling
    pri = req["priority"]
    pri_color = "#f87171" if pri in ["Critical", "High"] else ("#fbbf24" if pri == "Medium" else "#60a5fa")

    source_tag = ""
    if req.get("is_demo"):
        source_tag = "<span style='background: rgba(239,68,68,0.2); color:#fca5a5; padding:1px 5px; border-radius:3px; font-size:9.5px; border:1px solid #ef4444;'>DEMO</span>"

    desc_text = str(req.get('description', ''))
    defect_lineage_html = ""
    if "[Defect:" in desc_text:
        defect_lineage_html = f"""
        <div style="background: rgba(56, 189, 248, 0.10); border: 1px solid rgba(56, 189, 248, 0.3); border-left: 4px solid #38bdf8; border-radius: 6px; padding: 8px 12px; margin-top: 6px; margin-bottom: 8px;">
            <div style="font-size: 11px; font-weight: 800; color: #38bdf8; text-transform: uppercase; margin-bottom: 4px;">
                🔗 Defect Lineage &amp; Department Assessment
            </div>
            <div style="font-size: 11.5px; color: #f1f5f9; white-space: pre-wrap; line-height: 1.45;">{desc_text}</div>
        </div>
        """

    card_html = f"""
    <div style="background: {card_bg}; border: 1.5px solid {card_border}; border-left: 5px solid {'#ef4444' if is_overdue else dept_color}; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 14px; font-weight: 800; color: #f8fafc; letter-spacing: 0.5px;">
                    📋 <code>{req['request_id']}</code>
                </span>
                <span style="background: {dept_bg}; color: {dept_color}; border: 1px solid {dept_color}; padding: 1px 7px; border-radius: 4px; font-size: 11px; font-weight: 700;">
                    {dept_icon} {dept}
                </span>
                {source_tag}
            </div>
            <div>
                {status_badge}
            </div>
        </div>
        
        <div style="font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 4px;">
            {req['request_type']}
        </div>
        {defect_lineage_html if defect_lineage_html else f'''<div style="font-size: 11.5px; color: #cbd5e1; margin-bottom: 8px; line-height: 1.4;">{desc_text}</div>'''}

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 6px 16px; font-size: 11.5px; color: #94a3b8; border-top: 1px solid #1e293b; padding-top: 8px;">
            <div>📍 Section: <strong style="color:#ffffff;">{req['section']}</strong></div>
            <div>🚧 Block: <strong style="color:#ffffff;">{req['block']}</strong></div>
            <div>📏 KM Range: <strong style="color:#38bdf8;">Km {req['from_km']:.1f} – {req['to_km']:.1f}</strong></div>
            <div>📅 Requested Date: <strong style="color:#ffffff;">{req['date']}</strong></div>
            <div>⏱️ Duration: <strong style="color:#fbbf24;">{req['duration']} min</strong></div>
            <div>⚡ Priority: <strong style="color:{pri_color};">{req['priority']}</strong> &nbsp;|&nbsp; Urgency: <strong style="color:#ffffff;">{req['urgency']}</strong></div>
            <div>🕒 Submitted: <span style="color:#cbd5e1;">{req['submitted_at']}</span></div>
            <div>⏳ Required By: <strong style="color:{'#f87171' if is_overdue else '#a7f3d0'};">{req['required_by']}</strong></div>
            {f"<div style='grid-column: 1 / -1; color:#f87171; font-weight:700;'>⚠️ Overdue By: {req['overdue_duration']} (Deadline Expired)</div>" if is_overdue else ""}
        </div>
    </div>
    """
    st.markdown(clean_html(textwrap.dedent(card_html).strip()), unsafe_allow_html=True)

    # VIEW DETAILS Expander (Requirement 10)
    with st.expander(f"🔍 VIEW DETAILS — {req['request_id']} ({req['request_type']})", expanded=False):
        c_dt1, c_dt2 = st.columns(2)
        with c_dt1:
            st.markdown(f"**Request ID:** `{req['request_id']}`")
            st.markdown(f"**Department:** `{req['department']}`")
            st.markdown(f"**Request Type:** {req['request_type']}")
            st.markdown(f"**Section / Line:** `{req['section']}` ({req['line']})")
            st.markdown(f"**Block Assignment:** `{req['block']}`")
        with c_dt2:
            st.markdown(f"**Sectional KM:** `Km {req['from_km']:.1f} – {req['to_km']:.1f}` (Span: {abs(req['to_km'] - req['from_km']):.1f} km)")
            st.markdown(f"**Requested Date:** `{req['date']}`")
            st.markdown(f"**Required Duration:** `{req['duration']} Minutes`")
            st.markdown(f"**Priority / Urgency:** `{req['priority']}` / `{req['urgency']}`")
            st.markdown(f"**Submitted At:** `{req['submitted_at']}`")
            st.markdown(f"**Required By (Deadline):** `{req['required_by']}`")
            if is_overdue:
                st.markdown(f"**Overdue Duration:** :red[**{req['overdue_duration']} Overdue**]")
            st.markdown(f"**Current Status:** `{req['status']}`")

        if "[Defect:" in desc_text:
            st.markdown("---")
            st.markdown("##### 🔗 Originating Defect & Department Assessment Lineage")
            st.info(desc_text)
        else:
            st.markdown(f"**Description:** {desc_text}")

        st.caption("ℹ️ *System Note: Safety dependencies and power isolation requirements are derived automatically by the classification engine during candidate group preprocessing.*")


# =============================================================================
# 5. CONTROLLER REQUESTS POPUP / MODAL (Requirement 4)
# =============================================================================

@st.dialog("📋 Unprocessed Department Block Requests", width="large")
def open_controller_requests_dialog(division_name: str = ""):
    """
    Modal popup displaying all currently unprocessed NEW and OVERDUE requests.
    Does not destroy or reload the underlying geographic map.
    """
    st.caption("Central Controller Possession Queue • Individual Department Requisitions Awaiting Processing")

    # Header Filters Row
    f_col1, f_col2, f_col3 = st.columns([1.5, 1.2, 1.3])
    with f_col1:
        f_dept = st.selectbox(
            "🏢 Filter by Department:",
            ["ALL", "Engineering", "OHE/Traction", "S&T"],
            key="ctrl_modal_dept_filter"
        )
    with f_col2:
        f_cat = st.selectbox(
            "📑 Category:",
            ["ALL", "NEW REQUESTS", "OVERDUE REQUESTS"],
            key="ctrl_modal_cat_filter"
        )
    with f_col3:
        f_sort = st.selectbox(
            "↕️ Sort Requests By:",
            ["Submitted Time (Default)", "Priority (Critical First)", "Urgency", "Requested Date"],
            key="ctrl_modal_sort_filter"
        )

    # Map sort label to sort key
    sort_key_map = {
        "Submitted Time (Default)": "DEFAULT",
        "Priority (Critical First)": "PRIORITY",
        "Urgency": "URGENCY",
        "Requested Date": "DATE"
    }
    sort_key = sort_key_map.get(f_sort, "DEFAULT")

    # Fetch and filter requests
    new_reqs, overdue_reqs, total_new, total_overdue = fetch_controller_requests(
        division_name=division_name,
        dept_filter=f_dept,
        category_filter=f_cat,
        sort_by=sort_key
    )

    # KPI Summary Strip
    total_visible = len(new_reqs) + len(overdue_reqs)
    kpi_strip_html = f"""
    <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 8px 14px; margin-top: 6px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; font-size: 12px; font-family: sans-serif;">
        <span style="color: #94a3b8;">
            Showing <b style="color:#ffffff;">{total_visible}</b> unprocessed requests ({f_dept} • {f_cat})
        </span>
        <div style="display: flex; gap: 10px;">
            <span style="background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid #10b981; padding: 2px 8px; border-radius: 4px; font-weight: 700;">
                🟢 {len(new_reqs)} NEW
            </span>
            <span style="background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444; padding: 2px 8px; border-radius: 4px; font-weight: 700;">
                🔴 {len(overdue_reqs)} OVERDUE
            </span>
        </div>
    </div>
    """
    st.markdown(clean_html(textwrap.dedent(kpi_strip_html).strip()), unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 1. OVERDUE REQUESTS SECTION
    # -------------------------------------------------------------------------
    if f_cat in ["ALL", "OVERDUE REQUESTS"]:
        st.markdown(f"#### 🔴 OVERDUE REQUESTS ({len(overdue_reqs)})")
        if overdue_reqs:
            for i, o_req in enumerate(overdue_reqs):
                render_request_card(o_req, is_overdue=True, card_idx=i)
        else:
            st.info("✅ Zero overdue requests for the selected department filter.")

        st.markdown("---")

    # -------------------------------------------------------------------------
    # 2. NEW REQUESTS SECTION
    # -------------------------------------------------------------------------
    if f_cat in ["ALL", "NEW REQUESTS"]:
        st.markdown(f"#### 🟢 NEW REQUESTS ({len(new_reqs)})")
        if new_reqs:
            for i, n_req in enumerate(new_reqs):
                render_request_card(n_req, is_overdue=False, card_idx=i)
        else:
            st.info("ℹ️ No active new requests matching the selected department filter.")

    # -------------------------------------------------------------------------
    # 3. ACTION BAR: CLASSIFY REQUESTS (Step 6)
    # -------------------------------------------------------------------------
    if total_visible > 0:
        st.markdown("---")
        if st.button("⚡ CLASSIFY REQUESTS (Deterministic Matrix + AI Reasoning)", type="primary", use_container_width=True, key="btn_modal_classify_requests"):
            with st.spinner("AI Classification Engine: Evaluating dependency matrix, spatial KM overlap, and predecessor sequences..."):
                try:
                    from app.classification_engine import RequestClassificationEngine
                except ImportError:
                    from classification_engine import RequestClassificationEngine

                actionable_to_classify = new_reqs + overdue_reqs
                res = RequestClassificationEngine.classify_all_actionable_requests(actionable_to_classify)
                st.session_state["step6_classified_results"] = res
                st.toast(f"✅ Classified {len(res['classified_ids'])} requests into {res['counts']['total']} groups ({res['counts']['isolation']} Isolation, {res['counts']['parallel']} Parallel, {res['counts']['sequential']} Sequential, {res['counts']['review']} Review)", icon="🧩")
                st.rerun()


# =============================================================================
# 6. HEADER BUTTON RENDERER
# =============================================================================

def render_controller_requests_button(division_name: str = "", key_suffix: str = ""):
    """
    Renders the Controller [ REQUESTS (count) ] button with live count badge.
    Clicking opens the modal dialog without navigating away from the map.
    """
    counts = get_pending_request_counts()
    tot = counts["total"]
    n_cnt = counts["new"]
    o_cnt = counts["overdue"]

    btn_label = f"📋 REQUESTS ({tot})"
    if o_cnt > 0:
        help_text = f"{n_cnt} New Requests • {o_cnt} Overdue Requests awaiting Controller processing"
    else:
        help_text = f"{n_cnt} New Requests awaiting Controller processing"

    if st.button(
        btn_label,
        key=f"btn_controller_requests_modal_{key_suffix}",
        help=help_text,
        type="primary" if o_cnt > 0 else "secondary",
        use_container_width=True
    ):
        open_controller_requests_dialog(division_name=division_name)


# =============================================================================
# 7. OVERVIEW INTEGRATED DEPARTMENT REQUESTS PANEL
# =============================================================================

def render_overview_department_requests_panel(division_name: str = "Vijayawada Division (BZA)"):
    """
    Renders the Department Requisitions & Preprocessing Pipeline directly on the Controller Overview screen.
    Connects incoming department requests directly to the [ ⚡ CLASSIFY REQUESTS ] button, the Live Map,
    and the Step 7/8 Block Allocation Engine.
    """
    counts = get_pending_request_counts()
    n_cnt = counts["new"]
    o_cnt = counts["overdue"]
    tot_cnt = counts["total"]

    # Main Card Container
    overview_panel_html = f"""
    <div style="background: linear-gradient(135deg, #0b1329 0%, #111e38 100%); border: 1.5px solid #1e3a5f; border-radius: 12px; padding: 14px 18px; margin-bottom: 14px; box-shadow: 0 6px 20px rgba(0,0,0,0.35);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 22px;">📩</span>
                <div>
                    <div style="font-size: 15px; font-weight: 800; color: #f8fafc; letter-spacing: 0.3px;">
                        Department Maintenance Requisitions & Possession Pipeline
                    </div>
                    <div style="font-size: 11.5px; color: #94a3b8; font-weight: 500;">
                        Live Corridor Ingestion from <b>Engineering (TMS)</b>, <b>OHE/Traction (TDMS)</b>, and <b>S&T (SMMS)</b> • Step 5 Requisition Queue
                    </div>
                </div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
                <span style="background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid #10b981; padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;">
                    🟢 {n_cnt} NEW
                </span>
                <span style="background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid #ef4444; padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;">
                    🔴 {o_cnt} OVERDUE
                </span>
                <span style="background: rgba(56, 189, 248, 0.2); color: #7dd3fc; border: 1px solid #38bdf8; padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;">
                    TOTAL: {tot_cnt}
                </span>
            </div>
        </div>
    </div>
    """
    st.markdown(clean_html(textwrap.dedent(overview_panel_html).strip()), unsafe_allow_html=True)

    # Filter Controls & Action Bar
    c_f1, c_f2, c_f3 = st.columns([1.3, 1.2, 2.5])
    with c_f1:
        ov_dept = st.selectbox(
            "🏢 Filter by Department:",
            ["ALL", "Engineering", "OHE/Traction", "S&T"],
            key="overview_req_dept_filter"
        )
    with c_f2:
        ov_cat = st.selectbox(
            "📑 Category:",
            ["ALL", "NEW REQUESTS", "OVERDUE REQUESTS"],
            key="overview_req_cat_filter"
        )
    with c_f3:
        st.markdown(clean_html("<div style='padding-top: 28px;'>"), unsafe_allow_html=True)
        btn_classify = st.button(
            "⚡ CLASSIFY REQUESTS (Deterministic Matrix + AI Classification)",
            type="primary",
            use_container_width=True,
            key="btn_overview_classify_requests_main"
        )
        st.markdown(clean_html("</div>"), unsafe_allow_html=True)

    new_reqs, overdue_reqs, _, _ = fetch_controller_requests(
        division_name=division_name,
        dept_filter=ov_dept,
        category_filter=ov_cat
    )

    actionable_reqs = new_reqs + overdue_reqs

    if btn_classify:
        if actionable_reqs:
            with st.spinner("AI Classification Engine: Preprocessing spatial KM overlap, multi-department dependencies, and predecessor sequences..."):
                try:
                    from app.classification_engine import RequestClassificationEngine
                except ImportError:
                    from classification_engine import RequestClassificationEngine

                res = RequestClassificationEngine.classify_all_actionable_requests(actionable_reqs)
                st.session_state["step6_classified_results"] = res
                if "step7_candidate_plans" in st.session_state:
                    del st.session_state["step7_candidate_plans"]
                st.toast(
                    f"✅ Classified {len(res['classified_ids'])} requests into {res['counts']['total']} groups ({res['counts']['isolation']} Isolation, {res['counts']['parallel']} Parallel, {res['counts']['sequential']} Sequential)!",
                    icon="⚡"
                )
                st.rerun()
        else:
            st.warning("⚠️ No actionable department requests to classify.")

    # Render Active Requests in Compact Interactive Table View
    with st.expander(f"📋 View Active Department Requisitions Queue ({len(actionable_reqs)} Requisitions)", expanded=True):
        if actionable_reqs:
            tbl_data = []
            for r in actionable_reqs:
                st_badge = f"🔴 Overdue ({r['overdue_duration']})" if r["is_overdue"] else "🟢 New"
                tbl_data.append({
                    "Request ID": r["request_id"],
                    "Dept": r["department"],
                    "Activity": r["request_type"],
                    "Section / Line": f"{r['section']} ({r['line']})",
                    "KM Span": f"Km {r['from_km']:.1f} – {r['to_km']:.1f}",
                    "Duration": f"{r['duration']}m",
                    "Priority": r["priority"],
                    "Target Date": r["date"],
                    "Status": st_badge
                })
            df_table = pd.DataFrame(tbl_data)
            st.dataframe(df_table, use_container_width=True, hide_index=True)
        else:
            st.info("🎉 All department requisitions processed and classified.")

