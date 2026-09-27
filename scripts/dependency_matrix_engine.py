"""
Phase 4/5/7/8/10: Dependency Matrix & Controller Block Allocation Preprocessing Engine
Implements:
1. Configurable SQLite-backed Predefined Dependency Matrix (ENGINEERING, OHE/TRACTION, S&T)
2. Deterministic Spatial & Temporal Request Grouping (Same Block + Same Date + Overlapping KM)
3. Multi-Department Relationship Classifier (PARALLEL, SEQUENTIAL, ISOLATION, INDEPENDENT)
4. Full Audit & Diagnostic Explanations for Controller Decision Support
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, date

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "railway.db")


# -----------------------------------------------------------------------------
# 1. DATABASE INITIALIZATION: PREDEFINED DEPENDENCY MATRIX
# -----------------------------------------------------------------------------

DEFAULT_DEPENDENCY_RULES = [
    # Engineering & OHE/Traction (TRD)
    {
        "dept_a": "ENGINEERING",
        "activity_a": "Track renewal activity",
        "dept_b": "TRD",
        "activity_b": "Overhead equipment replacement",
        "relationship": "ISOLATION",
        "priority_level": "MANDATORY",
        "rule_description": "25kV OHE power isolation (PTW) is mandatory during heavy track renewal under catenary wires to protect ground personnel."
    },
    {
        "dept_a": "ENGINEERING",
        "activity_a": "Track tamping (CSM / BCM)",
        "dept_b": "TRD",
        "activity_b": "OHE Mast Alignment & Dropper Adjustment",
        "relationship": "SEQUENTIAL",
        "priority_level": "RECOMMENDED",
        "rule_description": "Track tamping & slewing must precede OHE dropper adjustment so catenary height aligns with final rail top level."
    },
    {
        "dept_a": "ENGINEERING",
        "activity_a": "Deep screening & ballast renewal",
        "dept_b": "TRD",
        "activity_b": "25kV Catenary Wire Stringing",
        "relationship": "PARALLEL",
        "priority_level": "COORDINATED",
        "rule_description": "Deep screening and wire stringing can proceed in parallel during unified corridor possession under joint safety supervisor."
    },

    # Engineering & S&T
    {
        "dept_a": "ENGINEERING",
        "activity_a": "Track renewal activity",
        "dept_b": "S&T",
        "activity_b": "Track circuit inspection & tuning",
        "relationship": "SEQUENTIAL",
        "priority_level": "MANDATORY",
        "rule_description": "P-Way track renewal must complete before S&T reconnects impedance bonds, track leads, and audio-frequency track circuits."
    },
    {
        "dept_a": "ENGINEERING",
        "activity_a": "Turnout sleeper replacement",
        "dept_b": "S&T",
        "activity_b": "Point machine maintenance",
        "relationship": "SEQUENTIAL",
        "priority_level": "MANDATORY",
        "rule_description": "Mechanical turnout sleeper replacement precedes electric point machine installation, stroke testing, and lock detection adjustment."
    },
    {
        "dept_a": "ENGINEERING",
        "activity_a": "Switch expansion joint replacement",
        "dept_b": "S&T",
        "activity_b": "Axle counter reset & testing",
        "relationship": "PARALLEL",
        "priority_level": "COORDINATED",
        "rule_description": "SEJ replacement and axle counter sensor recalibration can execute in parallel during the same track possession window."
    },

    # OHE/Traction (TRD) & S&T
    {
        "dept_a": "TRD",
        "activity_a": "Overhead equipment replacement",
        "dept_b": "S&T",
        "activity_b": "Signal aspect LED unit replacement",
        "relationship": "PARALLEL",
        "priority_level": "COORDINATED",
        "rule_description": "OHE maintenance and signal aspect replacement can be scheduled simultaneously as signal cables are shielded from catenary work."
    },
    {
        "dept_a": "TRD",
        "activity_a": "Traction Substation Transformer Overhaul",
        "dept_b": "S&T",
        "activity_b": "Electronic interlocking testing",
        "relationship": "ISOLATION",
        "priority_level": "MANDATORY",
        "rule_description": "Auxiliary traction power supply switchover requires interlocking safety interlocks and DG backup verification."
    },

    # Intra-Department Rules
    {
        "dept_a": "ENGINEERING",
        "activity_a": "Rail fracture emergency weld",
        "dept_b": "ENGINEERING",
        "activity_b": "Track tamping (CSM / BCM)",
        "relationship": "SEQUENTIAL",
        "priority_level": "MANDATORY",
        "rule_description": "Emergency rail weld and ultrasonic testing must be completed before heavy tamper passes over newly welded joint."
    },
    {
        "dept_a": "TRD",
        "activity_a": "Isolator switch maintenance",
        "dept_b": "TRD",
        "activity_b": "25kV Catenary Wire Stringing",
        "relationship": "ISOLATION",
        "priority_level": "MANDATORY",
        "rule_description": "Sectional isolator must be locked and earthed before catenary conductor wire tensioning commences."
    },
    {
        "dept_a": "S&T",
        "activity_a": "Point machine maintenance",
        "dept_b": "S&T",
        "activity_b": "Electronic interlocking testing",
        "relationship": "SEQUENTIAL",
        "priority_level": "MANDATORY",
        "rule_description": "Point machine obstruction testing must finish before end-to-end station electronic interlocking route validation."
    }
]


def init_dependency_matrix_table(db_path=DB_PATH):
    """Initializes the configurable dependency matrix table in SQLite."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_dependency_matrix (
                rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                dept_a TEXT NOT NULL,
                activity_a TEXT NOT NULL,
                dept_b TEXT NOT NULL,
                activity_b TEXT NOT NULL,
                relationship TEXT NOT NULL, -- PARALLEL, SEQUENTIAL, ISOLATION, INDEPENDENT
                priority_level TEXT DEFAULT 'MANDATORY', -- MANDATORY, RECOMMENDED, COORDINATED
                rule_description TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Check if table is empty, if so populate defaults
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) FROM system_dependency_matrix").fetchone()[0]
        if count == 0:
            for r in DEFAULT_DEPENDENCY_RULES:
                cur.execute("""
                    INSERT INTO system_dependency_matrix 
                    (dept_a, activity_a, dept_b, activity_b, relationship, priority_level, rule_description, is_active, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """, (
                    r["dept_a"], r["activity_a"], r["dept_b"], r["activity_b"],
                    r["relationship"], r["priority_level"], r["rule_description"],
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ))
            conn.commit()
    except Exception as e:
        print(f"Error initializing system_dependency_matrix: {e}")
    finally:
        conn.close()


def get_dependency_matrix_df(db_path=DB_PATH) -> pd.DataFrame:
    """Retrieves all active dependency matrix rules."""
    init_dependency_matrix_table(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        df = pd.read_sql("SELECT * FROM system_dependency_matrix WHERE is_active=1 ORDER BY rule_id ASC", conn)
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 2. DETERMINISTIC CANDIDATE GROUPING ENGINE (SAME BLOCK + DATE + OVERLAPPING KM)
# -----------------------------------------------------------------------------

def is_km_overlapping(from_a, to_a, from_b, to_b) -> bool:
    """
    Determines if two KM ranges overlap.
    Overlapping condition: max(from_a, from_b) <= min(to_a, to_b)
    """
    try:
        min_a, max_a = min(float(from_a), float(to_a)), max(float(from_a), float(to_a))
        min_b, max_b = min(float(from_b), float(to_b)), max(float(from_b), float(to_b))
        return max(min_a, min_b) <= min(max_a, max_b)
    except (ValueError, TypeError):
        return False


def normalize_dept_name(d_str: str) -> str:
    """Standardizes department names for matrix matching."""
    s = str(d_str).strip().upper()
    if "ENG" in s or "P-WAY" in s or "TRACK" in s:
        return "ENGINEERING"
    if "TRD" in s or "OHE" in s or "TRACTION" in s:
        return "TRD"
    if "S&T" in s or "SIGNAL" in s or "SMMS" in s:
        return "S&T"
    return s


def find_relationship_between_activities(dept_a, act_a, dept_b, act_b, matrix_df: pd.DataFrame = None):
    """
    Determines relationship (PARALLEL, SEQUENTIAL, ISOLATION, INDEPENDENT)
    between two requests using the database matrix.
    """
    if matrix_df is None or matrix_df.empty:
        matrix_df = get_dependency_matrix_df()

    norm_a = normalize_dept_name(dept_a)
    norm_b = normalize_dept_name(dept_b)
    act_a_l = str(act_a).strip().lower()
    act_b_l = str(act_b).strip().lower()

    if not matrix_df.empty:
        for _, r in matrix_df.iterrows():
            m_dept_a = normalize_dept_name(r["dept_a"])
            m_dept_b = normalize_dept_name(r["dept_b"])
            m_act_a = str(r["activity_a"]).strip().lower()
            m_act_b = str(r["activity_b"]).strip().lower()

            # Forward check: (A, B)
            if norm_a == m_dept_a and norm_b == m_dept_b:
                if (m_act_a == "*" or m_act_a in act_a_l or act_a_l in m_act_a) and \
                   (m_act_b == "*" or m_act_b in act_b_l or act_b_l in m_act_b):
                    return r["relationship"], r["rule_description"], r.get("priority_level", "MANDATORY")

            # Reverse check: (B, A)
            if norm_a == m_dept_b and norm_b == m_dept_a:
                if (m_act_b == "*" or m_act_b in act_a_l or act_a_l in m_act_b) and \
                   (m_act_a == "*" or m_act_a in act_b_l or act_b_l in m_act_a):
                    return r["relationship"], r["rule_description"], r.get("priority_level", "MANDATORY")

    # High-level fallbacks if exact activity row not present
    if norm_a == "TRD" or norm_b == "TRD":
        if "catenary" in act_a_l or "catenary" in act_b_l or "ohe" in act_a_l or "ohe" in act_b_l:
            return "ISOLATION", "OHE 25kV power isolation is active on corridor segment.", "MANDATORY"
        return "PARALLEL", "OHE inspection and P-Way/S&T works compatible under joint corridor possession.", "COORDINATED"

    if (norm_a == "ENGINEERING" and norm_b == "S&T") or (norm_a == "S&T" and norm_b == "ENGINEERING"):
        return "SEQUENTIAL", "Track renewal must finish before signal circuit reconnection and sensor testing.", "MANDATORY"

    if norm_a == norm_b:
        return "PARALLEL", f"Coordinated intra-department {norm_a} block window on same track segment.", "COORDINATED"

    return "INDEPENDENT", "No operational interlock conflict detected between activities.", "STANDARD"


def group_candidate_block_requests(requests: list, matrix_df: pd.DataFrame = None) -> list:
    """
    Groups requests according to PRIMARY constraints:
    1. SAME BLOCK / SECTION
    2. SAME DATE
    3. OVERLAPPING SECTIONAL KM

    Supports both NEW (`SUBMITTED`/`Pending`) and `OVERDUE` requests.
    """
    if not requests:
        return []

    if matrix_df is None or matrix_df.empty:
        matrix_df = get_dependency_matrix_df()

    # Normalize requests into uniform dicts
    cleaned_reqs = []
    for r in requests:
        req_id = r.get("request_id") or r.get("defect_id") or "REQ-UNK"
        dept = normalize_dept_name(r.get("department", "ENGINEERING"))
        sec = str(r.get("section") or r.get("section_id") or "GDR-BZA-DN").strip()
        
        # Date parsing (deadline or requested_date or reported_time)
        raw_date = str(r.get("deadline") or r.get("requested_date") or r.get("due_date") or r.get("reported_time") or datetime.now().strftime("%Y-%m-%d"))[:10]
        try:
            req_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        except Exception:
            req_date = datetime.now().strftime("%Y-%m-%d")

        from_km = float(r.get("from_km") or 114.0)
        to_km = float(r.get("to_km") or from_km + 4.0)
        req_type = str(r.get("request_type") or r.get("defect_type") or "Maintenance Work")
        pri = str(r.get("priority") or r.get("severity") or "Medium")
        dur = int(r.get("required_duration") or int(float(r.get("estimated_duration_hours", 1.0)) * 60) or 60)
        status = str(r.get("status", "SUBMITTED")).strip()
        
        # Check overdue status
        is_overdue = False
        overdue_days = 0
        try:
            dt_obj = datetime.strptime(req_date, "%Y-%m-%d").date()
            if dt_obj < date.today() and status.lower() != "completed":
                is_overdue = True
                overdue_days = (date.today() - dt_obj).days
        except Exception:
            pass

        cleaned_reqs.append({
            "request_id": req_id,
            "department": dept,
            "raw_dept": r.get("department", dept),
            "section": sec,
            "date": req_date,
            "from_km": min(from_km, to_km),
            "to_km": max(from_km, to_km),
            "request_type": req_type,
            "priority": pri,
            "duration": dur,
            "preferred_start": r.get("preferred_start", "02:30"),
            "line": r.get("line", "DOWN Line"),
            "status": status,
            "is_overdue": is_overdue,
            "overdue_days": overdue_days,
            "raw_data": r
        })

    # Group by (Section, Date)
    buckets = {}
    for r in cleaned_reqs:
        key = (r["section"], r["date"])
        buckets.setdefault(key, []).append(r)

    candidate_groups = []
    grp_counter = 1

    for (sec, req_date), bucket_reqs in buckets.items():
        n = len(bucket_reqs)
        if n == 1:
            # Single request in this section & date
            r0 = bucket_reqs[0]
            grp_id = f"GRP-{req_date.replace('-', '')}-{sec}-{grp_counter:02d}"
            grp_counter += 1
            candidate_groups.append({
                "group_id": grp_id,
                "date": req_date,
                "section": sec,
                "block": sec,
                "from_km": r0["from_km"],
                "to_km": r0["to_km"],
                "combined_km_range": f"KM {r0['from_km']:.1f} – {r0['to_km']:.1f}",
                "num_requests": 1,
                "departments": [r0["department"]],
                "request_ids": [r0["request_id"]],
                "requests": [r0],
                "relationships": [],
                "overall_relationship": "INDEPENDENT",
                "traffic_condition": "Medium Density Corridor (WTT Gap Available)",
                "status": "Ready for Controller Allocation",
                "has_overdue": r0["is_overdue"],
                "max_overdue_days": r0["overdue_days"]
            })
            continue

        # Multiple requests in same section & date: Build overlap clusters using Disjoint Set / BFS
        adj = {i: [] for i in range(n)}
        for i in range(n):
            for j in range(i + 1, n):
                if is_km_overlapping(bucket_reqs[i]["from_km"], bucket_reqs[i]["to_km"],
                                      bucket_reqs[j]["from_km"], bucket_reqs[j]["to_km"]):
                    adj[i].append(j)
                    adj[j].append(i)

        visited = [False] * n
        for i in range(n):
            if not visited[i]:
                # Collect connected component
                comp_indices = []
                queue = [i]
                visited[i] = True
                while queue:
                    curr = queue.pop(0)
                    comp_indices.append(curr)
                    for neighbor in adj[curr]:
                        if not visited[neighbor]:
                            visited[neighbor] = True
                            queue.append(neighbor)

                comp_reqs = [bucket_reqs[idx] for idx in comp_indices]
                min_k = min(r["from_km"] for r in comp_reqs)
                max_k = max(r["to_km"] for r in comp_reqs)
                depts = list(dict.fromkeys(r["department"] for r in comp_reqs))
                req_ids = [r["request_id"] for r in comp_reqs]
                has_od = any(r["is_overdue"] for r in comp_reqs)
                max_od = max((r["overdue_days"] for r in comp_reqs), default=0)

                # Pairwise relationships
                relationships = []
                rel_types = set()
                for p1 in range(len(comp_reqs)):
                    for p2 in range(p1 + 1, len(comp_reqs)):
                        ra = comp_reqs[p1]
                        rb = comp_reqs[p2]
                        rel, reason, pri_lvl = find_relationship_between_activities(
                            ra["department"], ra["request_type"],
                            rb["department"], rb["request_type"],
                            matrix_df
                        )
                        rel_types.add(rel)
                        relationships.append({
                            "req_a": ra["request_id"],
                            "dept_a": ra["department"],
                            "type_a": ra["request_type"],
                            "req_b": rb["request_id"],
                            "dept_b": rb["department"],
                            "type_b": rb["request_type"],
                            "relationship": rel,
                            "priority_level": pri_lvl,
                            "reason": reason
                        })

                # Derive overall dominant relationship
                if "ISOLATION" in rel_types:
                    overall_rel = "ISOLATION"
                elif "SEQUENTIAL" in rel_types:
                    overall_rel = "SEQUENTIAL"
                elif "PARALLEL" in rel_types:
                    overall_rel = "PARALLEL"
                else:
                    overall_rel = "INDEPENDENT" if len(comp_reqs) == 1 else "PARALLEL"

                grp_id = f"GRP-{req_date.replace('-', '')}-{sec}-{grp_counter:02d}"
                grp_counter += 1

                candidate_groups.append({
                    "group_id": grp_id,
                    "date": req_date,
                    "section": sec,
                    "block": sec,
                    "from_km": min_k,
                    "to_km": max_k,
                    "combined_km_range": f"KM {min_k:.1f} – {max_k:.1f}",
                    "num_requests": len(comp_reqs),
                    "departments": depts,
                    "request_ids": req_ids,
                    "requests": comp_reqs,
                    "relationships": relationships,
                    "overall_relationship": overall_rel,
                    "traffic_condition": "High Density Corridor (Shadow Block Merge Recommended)",
                    "status": "Candidate Group Formed (Preprocessed)",
                    "has_overdue": has_od,
                    "max_overdue_days": max_od
                })

    return candidate_groups
