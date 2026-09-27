"""
Phase 5/10 - Modification 4: Final Block Allocation, Department Notification & Audit Trail Engine

Handles:
1. Final Block Allocation creation and persistence with full metadata.
2. Department-specific targeted notification dispatch (preventing unrelated leaks).
3. Notification types: BLOCK ALLOCATED, BLOCK MODIFIED, BLOCK CANCELLED, BLOCK RESCHEDULED, BLOCK AT RISK, BLOCK COMPLETED.
4. Comprehensive 9-stage Audit Trail logging with timestamps.
5. Live block updates / modifications / cancellations with historical versioning.
6. Department status pipeline mapping (SUBMITTED, UNDER PLANNING, ALTERNATIVES AVAILABLE, ALLOCATED, etc.).
"""

import os
import sys
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "railway.db")


# -----------------------------------------------------------------------------
# 1. DATABASE SCHEMA INITIALIZATION
# -----------------------------------------------------------------------------

def init_final_allocation_db(db_path: str = DB_PATH):
    """Initializes tables for Final Block Allocations, Department Notifications, and Audit Trail."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")

        # Table 1: Final Block Allocations
        conn.execute("""
            CREATE TABLE IF NOT EXISTS final_block_allocations (
                allocation_id TEXT PRIMARY KEY,
                planning_group_id TEXT NOT NULL,
                request_ids TEXT NOT NULL,
                block TEXT NOT NULL,
                section TEXT NOT NULL,
                from_km REAL NOT NULL,
                to_km REAL NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                duration INTEGER NOT NULL,
                classification TEXT NOT NULL,
                departments TEXT NOT NULL,
                selected_by_controller TEXT NOT NULL,
                controller_id TEXT NOT NULL,
                selection_time TEXT NOT NULL,
                AI_recommended_option TEXT NOT NULL,
                controller_selected_option TEXT NOT NULL,
                override_reason TEXT,
                status TEXT NOT NULL DEFAULT 'ALLOCATED',
                version INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                details_json TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table 2: Department Notifications
        conn.execute("""
            CREATE TABLE IF NOT EXISTS department_notifications_v4 (
                notif_id INTEGER PRIMARY KEY AUTOINCREMENT,
                department TEXT NOT NULL,
                request_id TEXT NOT NULL,
                allocation_id TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                block TEXT NOT NULL,
                section TEXT NOT NULL,
                from_km REAL NOT NULL,
                to_km REAL NOT NULL,
                date TEXT NOT NULL,
                allocated_time TEXT NOT NULL,
                planning_type TEXT NOT NULL,
                other_participating_departments TEXT,
                status TEXT NOT NULL,
                message TEXT,
                details_json TEXT,
                timestamp TEXT NOT NULL,
                is_read INTEGER DEFAULT 0
            )
        """)

        # Table 3: Lifecycle Audit Trail
        conn.execute("""
            CREATE TABLE IF NOT EXISTS block_allocation_audit_trail (
                audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                allocation_id TEXT,
                planning_group_id TEXT,
                request_id TEXT,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                details TEXT,
                metadata_json TEXT
            )
        """)

        conn.commit()
    except Exception as e:
        print(f"Error initializing final_allocation_db: {e}")
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 2. AUDIT TRAIL LOGGER
# -----------------------------------------------------------------------------

def _record_audit_event_cursor(
    cur: sqlite3.Cursor,
    event_type: str,
    actor: str,
    allocation_id: Optional[str] = None,
    planning_group_id: Optional[str] = None,
    request_id: Optional[str] = None,
    details: str = "",
    metadata: Optional[Dict[str, Any]] = None
):
    """Internal helper to write audit event using an existing open transaction cursor."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT INTO block_allocation_audit_trail
        (allocation_id, planning_group_id, request_id, event_type, actor, timestamp, details, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        allocation_id, planning_group_id, request_id, event_type,
        actor, now_str, details, json.dumps(metadata or {})
    ))


def log_audit_trail_event(
    event_type: str,
    actor: str,
    allocation_id: Optional[str] = None,
    planning_group_id: Optional[str] = None,
    request_id: Optional[str] = None,
    details: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH
) -> int:
    """
    Standalone public logger for official lifecycle events in the block allocation audit trail.
    Supported event types:
    - Request Created
    - Request Grouped
    - Dependency Classified
    - Alternatives Generated
    - AI Recommendation
    - Controller Selection
    - Department Notification
    - Block Started
    - Block Completed
    - Block Modified
    - Block Rescheduled
    - Block Cancelled
    """
    init_final_allocation_db(db_path)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO block_allocation_audit_trail
            (allocation_id, planning_group_id, request_id, event_type, actor, timestamp, details, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            allocation_id, planning_group_id, request_id, event_type,
            actor, now_str, details, json.dumps(metadata or {})
        ))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        print(f"Error logging audit trail event: {e}")
        return 0
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 3. FINAL BLOCK ALLOCATION & TARGETED NOTIFICATION CREATION
# -----------------------------------------------------------------------------

def format_standard_dept_name(d_str: str) -> str:
    """Standardizes department name casing and abbreviations for display and notifications."""
    s = str(d_str).strip().upper()
    if "ENG" in s or "P-WAY" in s or "TRACK" in s:
        return "Engineering"
    if "TRD" in s or "OHE" in s or "TRACTION" in s:
        return "OHE/Traction"
    if "S&T" in s or "SIGNAL" in s:
        return "S&T"
    return str(d_str).strip()


def create_final_block_allocation(
    planning_group: Dict[str, Any],
    selected_alt: Dict[str, Any],
    ai_recommendation_id: str,
    controller_id: str = "CONTROLLER-BZA-01",
    override_reason: Optional[str] = None,
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Creates a definitive Final Block Allocation record, records audit trail,
    updates request statuses, and dispatches department-specific notifications.
    """
    init_final_allocation_db(db_path)
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_date_str = datetime.now().strftime("%Y%m%d")

    grp_id = planning_group.get("group_id", "GRP-001")
    reqs = planning_group.get("requests", [])
    req_ids = [r["request_id"] for r in reqs]
    req_ids_str = ", ".join(req_ids)

    depts = []
    for r in reqs:
        d_name = format_standard_dept_name(r.get("department", "Engineering"))
        if d_name not in depts:
            depts.append(d_name)
    depts_str = ", ".join(depts)

    block_val = planning_group.get("block", "B1")
    section_val = planning_group.get("section", "BZA-VSKP")
    from_km = float(planning_group.get("min_km", planning_group.get("from_km", 570.0)))
    to_km = float(planning_group.get("max_km", planning_group.get("to_km", 575.0)))
    date_val = str(planning_group.get("date", datetime.now().strftime("%d/%m/%Y")))
    
    start_time = selected_alt.get("start_time", "10:20")
    end_time = selected_alt.get("end_time", "10:50")
    duration = int(selected_alt.get("duration_minutes", 30))
    classification = selected_alt.get("classification", planning_group.get("overall_relationship", "PARALLEL"))

    selected_option_id = selected_alt.get("alt_id", "ALT-1")
    is_override = (selected_option_id != ai_recommendation_id)
    final_override_reason = override_reason if is_override else "AI Recommendation Adopted"

    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cur = conn.cursor()

        # Check if allocation already exists; if so, supersede old one
        cur.execute("SELECT allocation_id, version FROM final_block_allocations WHERE planning_group_id = ? AND is_active = 1", (grp_id,))
        existing = cur.fetchone()
        version_num = 1
        if existing:
            version_num = existing[1] + 1
            cur.execute("UPDATE final_block_allocations SET is_active = 0 WHERE allocation_id = ?", (existing[0],))

        alloc_id = f"ALLOC-{now_date_str}-{grp_id.replace('GRP-', '')}-V{version_num}"

        # 1. Insert Final Block Allocation
        cur.execute("""
            INSERT INTO final_block_allocations
            (allocation_id, planning_group_id, request_ids, block, section, from_km, to_km, date,
             start_time, end_time, duration, classification, departments, selected_by_controller,
             controller_id, selection_time, AI_recommended_option, controller_selected_option,
             override_reason, status, version, is_active, details_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ALLOCATED', ?, 1, ?, ?, ?)
        """, (
            alloc_id, grp_id, req_ids_str, block_val, section_val, from_km, to_km, date_val,
            start_time, end_time, duration, classification, depts_str,
            "1", controller_id, now_ts, ai_recommendation_id, selected_option_id,
            final_override_reason, version_num, json.dumps(selected_alt), now_ts, now_ts
        ))

        # 2. Update block_requests_v2 status to 'ALLOCATED'
        for r in reqs:
            cur.execute("UPDATE block_requests_v2 SET status = 'ALLOCATED' WHERE request_id = ?", (r["request_id"],))

        # 3. Synchronize schedule table
        for r in reqs:
            try:
                p_start = f"{date_val} {start_time}:00"
                p_end = f"{date_val} {end_time}:00"
                cur.execute("""
                    INSERT OR REPLACE INTO schedule 
                    (defect_id, slot_id, section_id, department, planned_start, planned_end, duration_minutes, horizon, status, decided_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'rolling_7d', 'ALLOCATED', ?)
                """, (r["request_id"], f"SLOT-{alloc_id}", section_val, r["department"], p_start, p_end, duration, f"Controller ({controller_id})"))
            except Exception as e_sched:
                pass

        # 4. Audit Trail: Log Controller Selection
        _record_audit_event_cursor(
            cur=cur,
            event_type="Controller Selection",
            actor=controller_id,
            allocation_id=alloc_id,
            planning_group_id=grp_id,
            details=f"Controller selected {selected_option_id} ({start_time}–{end_time}) [Classification: {classification}]. Override: {'Yes - ' + final_override_reason if is_override else 'No'}",
            metadata={"selected_alt": selected_alt, "ai_recommendation": ai_recommendation_id, "is_override": is_override}
        )

        # 5. Targeted Department Notifications (Isolated per affected department)
        notifications_created = []
        for r in reqs:
            my_dept = format_standard_dept_name(r["department"])
            my_req_id = r["request_id"]
            
            # Identify other participating departments strictly for this group
            other_depts = [d for d in depts if d != my_dept]
            other_depts_str = ", ".join(other_depts) if other_depts else "None (Single Department)"

            req_from_km = r.get("from_km", from_km)
            req_to_km = r.get("to_km", to_km)

            notif_msg = (
                f"BLOCK ALLOCATION CONFIRMED\n"
                f"Request: {my_req_id}\n"
                f"Block: {block_val}\n"
                f"Section: KM {req_from_km}–{req_to_km} ({section_val})\n"
                f"Date: {date_val}\n"
                f"Allocated Time: {start_time}–{end_time}\n"
                f"Planning Type: {classification}\n"
                f"Other participating departments: {other_depts_str}\n"
                f"Status: ALLOCATED BY CONTROLLER"
            )

            cur.execute("""
                INSERT INTO department_notifications_v4
                (department, request_id, allocation_id, notification_type, block, section, from_km, to_km,
                 date, allocated_time, planning_type, other_participating_departments, status, message, details_json, timestamp, is_read)
                VALUES (?, ?, ?, 'BLOCK ALLOCATED', ?, ?, ?, ?, ?, ?, ?, ?, 'ALLOCATED BY CONTROLLER', ?, ?, ?, 0)
            """, (
                my_dept, my_req_id, alloc_id, block_val, section_val, req_from_km, req_to_km,
                date_val, f"{start_time}–{end_time}", classification, other_depts_str,
                notif_msg, json.dumps({"request": r, "allocation": selected_alt}), now_ts
            ))
            notif_id = cur.lastrowid

            # Also record audit trail event for Department Notification
            _record_audit_event_cursor(
                cur=cur,
                event_type="Department Notification",
                actor="System (Dispatcher)",
                allocation_id=alloc_id,
                planning_group_id=grp_id,
                request_id=my_req_id,
                details=f"Dispatched 'BLOCK ALLOCATED' notification to {my_dept} for Request #{my_req_id}",
                metadata={"notification_id": notif_id, "department": my_dept, "participating_peers": other_depts}
            )

            notifications_created.append({
                "notif_id": notif_id,
                "department": my_dept,
                "request_id": my_req_id,
                "message": notif_msg
            })

        conn.commit()

        return {
            "success": True,
            "allocation_id": alloc_id,
            "planning_group_id": grp_id,
            "status": "ALLOCATED",
            "start_time": start_time,
            "end_time": end_time,
            "classification": classification,
            "notifications_dispatched": len(notifications_created),
            "notifications": notifications_created
        }

    except Exception as e:
        conn.rollback()
        print(f"Error creating final block allocation: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 4. LIVE BLOCK MODIFICATION & RESCHEDULING (AUDIT PRESERVED)
# -----------------------------------------------------------------------------

def update_block_allocation(
    allocation_id: str,
    new_start_time: Optional[str] = None,
    new_end_time: Optional[str] = None,
    new_date: Optional[str] = None,
    new_block: Optional[str] = None,
    new_from_km: Optional[float] = None,
    new_to_km: Optional[float] = None,
    new_classification: Optional[str] = None,
    notification_type: str = "BLOCK MODIFIED",
    controller_id: str = "CONTROLLER-BZA-01",
    modification_reason: str = "Controller adjusted window for timetable headway protection",
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """
    Modifies an active block allocation.
    Retains previous record in history/audit trail, updates final allocation,
    and dispatches 'BLOCK MODIFIED' or 'BLOCK RESCHEDULED' notifications.
    """
    init_final_allocation_db(db_path)
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM final_block_allocations WHERE allocation_id = ?", (allocation_id,))
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": f"Allocation {allocation_id} not found."}

        grp_id = row[1]
        req_ids_str = row[2]
        old_block = row[3]
        section = row[4]
        old_from_km = row[5]
        old_to_km = row[6]
        old_date = row[7]
        old_start = row[8]
        old_end = row[9]
        old_classification = row[11]
        departments_str = row[12]

        final_block = new_block or old_block
        final_from_km = new_from_km if new_from_km is not None else old_from_km
        final_to_km = new_to_km if new_to_km is not None else old_to_km
        final_date = new_date or old_date
        final_start = new_start_time or old_start
        final_end = new_end_time or old_end
        final_class = new_classification or old_classification

        new_status = "RESCHEDULED" if notification_type == "BLOCK RESCHEDULED" else "MODIFIED"

        # Update allocation record
        cur.execute("""
            UPDATE final_block_allocations
            SET block = ?, from_km = ?, to_km = ?, date = ?, start_time = ?, end_time = ?,
                classification = ?, status = ?, version = version + 1, updated_at = ?
            WHERE allocation_id = ?
        """, (final_block, final_from_km, final_to_km, final_date, final_start, final_end, final_class, new_status, now_ts, allocation_id))

        # Update block_requests_v2
        req_list = [r.strip() for r in req_ids_str.split(",") if r.strip()]
        for req_id in req_list:
            cur.execute("UPDATE block_requests_v2 SET status = ? WHERE request_id = ?", (new_status, req_id))

        # Log Audit Trail
        _record_audit_event_cursor(
            cur=cur,
            event_type=f"Block {new_status.title()}",
            actor=controller_id,
            allocation_id=allocation_id,
            planning_group_id=grp_id,
            details=f"Allocation {allocation_id} updated: Time={final_start}–{final_end}, Date={final_date}, Block={final_block}, KM={final_from_km}–{final_to_km}, Class={final_class}. Reason: {modification_reason}",
            metadata={"previous": {"start": old_start, "end": old_end, "date": old_date, "block": old_block}, "updated": {"start": final_start, "end": final_end, "date": final_date, "block": final_block}}
        )

        # Dispatch Targeted Notifications
        depts = [format_standard_dept_name(d) for d in departments_str.split(",") if d.strip()]
        for req_id in req_list:
            cur.execute("SELECT department FROM block_requests_v2 WHERE request_id = ?", (req_id,))
            dept_row = cur.fetchone()
            my_dept = format_standard_dept_name(dept_row[0] if dept_row else "Engineering")
            other_depts = [d for d in depts if d != my_dept]
            other_depts_str = ", ".join(other_depts) if other_depts else "None (Single Department)"

            notif_msg = (
                f"{notification_type.upper()}\n"
                f"Request: {req_id}\n"
                f"Block: {final_block}\n"
                f"Section: KM {final_from_km}–{final_to_km} ({section})\n"
                f"Date: {final_date}\n"
                f"Allocated Time: {final_start}–{final_end}\n"
                f"Planning Type: {final_class}\n"
                f"Other participating departments: {other_depts_str}\n"
                f"Status: {notification_type.upper()} BY CONTROLLER ({modification_reason})"
            )

            cur.execute("""
                INSERT INTO department_notifications_v4
                (department, request_id, allocation_id, notification_type, block, section, from_km, to_km,
                 date, allocated_time, planning_type, other_participating_departments, status, message, details_json, timestamp, is_read)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                my_dept, req_id, allocation_id, notification_type, final_block, section, final_from_km, final_to_km,
                final_date, f"{final_start}–{final_end}", final_class, other_depts_str,
                f"{notification_type.upper()} BY CONTROLLER", notif_msg,
                json.dumps({"reason": modification_reason}), now_ts
            ))

        conn.commit()
        return {"success": True, "allocation_id": allocation_id, "new_status": new_status}

    except Exception as e:
        conn.rollback()
        print(f"Error updating block allocation: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 5. BLOCK CANCELLATION & COMPLETION LIFECYCLE
# -----------------------------------------------------------------------------

def set_block_allocation_lifecycle_status(
    allocation_id: str,
    new_status: str, # "CANCELLED" or "COMPLETED" or "STARTED"
    controller_id: str = "CONTROLLER-BZA-01",
    reason: str = "Possession completed safely and certified fit",
    db_path: str = DB_PATH
) -> Dict[str, Any]:
    """Updates lifecycle state of allocation, logs audit trail, and notifies departments."""
    init_final_allocation_db(db_path)
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    st_clean = new_status.upper().replace('_', ' ')
    notif_type = f"BLOCK {st_clean}" if not st_clean.startswith("BLOCK") else st_clean

    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM final_block_allocations WHERE allocation_id = ?", (allocation_id,))
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": f"Allocation {allocation_id} not found."}

        grp_id = row[1]
        req_ids_str = row[2]
        block_val = row[3]
        section_val = row[4]
        from_km = row[5]
        to_km = row[6]
        date_val = row[7]
        start_time = row[8]
        end_time = row[9]
        classification = row[11]
        departments_str = row[12]

        cur.execute("""
            UPDATE final_block_allocations 
            SET status = ?, updated_at = ?
            WHERE allocation_id = ?
        """, (new_status.upper(), now_ts, allocation_id))

        req_list = [r.strip() for r in req_ids_str.split(",") if r.strip()]
        for req_id in req_list:
            cur.execute("UPDATE block_requests_v2 SET status = ? WHERE request_id = ?", (new_status.upper(), req_id))
            cur.execute("UPDATE schedule SET status = ? WHERE defect_id = ?", (new_status.upper(), req_id))

        # Audit event
        event_name = "Block Completed" if new_status.upper() == "COMPLETED" else ("Block Started" if new_status.upper() == "STARTED" else "Block Cancelled")
        _record_audit_event_cursor(
            cur=cur,
            event_type=event_name,
            actor=controller_id,
            allocation_id=allocation_id,
            planning_group_id=grp_id,
            details=f"Allocation {allocation_id} marked as {new_status.upper()}. Reason: {reason}",
            metadata={"status": new_status, "reason": reason}
        )

        # Notify departments
        depts = [format_standard_dept_name(d) for d in departments_str.split(",") if d.strip()]
        for req_id in req_list:
            cur.execute("SELECT department FROM block_requests_v2 WHERE request_id = ?", (req_id,))
            dept_row = cur.fetchone()
            my_dept = format_standard_dept_name(dept_row[0] if dept_row else "Engineering")
            other_depts = [d for d in depts if d != my_dept]
            other_depts_str = ", ".join(other_depts) if other_depts else "None (Single Department)"

            notif_msg = (
                f"{notif_type}\n"
                f"Request: {req_id}\n"
                f"Block: {block_val}\n"
                f"Section: KM {from_km}–{to_km} ({section_val})\n"
                f"Date: {date_val}\n"
                f"Allocated Time: {start_time}–{end_time}\n"
                f"Planning Type: {classification}\n"
                f"Other participating departments: {other_depts_str}\n"
                f"Status: {new_status.upper()} BY CONTROLLER ({reason})"
            )

            cur.execute("""
                INSERT INTO department_notifications_v4
                (department, request_id, allocation_id, notification_type, block, section, from_km, to_km,
                 date, allocated_time, planning_type, other_participating_departments, status, message, details_json, timestamp, is_read)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                my_dept, req_id, allocation_id, notif_type, block_val, section_val, from_km, to_km,
                date_val, f"{start_time}–{end_time}", classification, other_depts_str,
                f"{new_status.upper()} BY CONTROLLER", notif_msg, json.dumps({"reason": reason}), now_ts
            ))

        conn.commit()
        return {"success": True, "allocation_id": allocation_id, "status": new_status.upper()}

    except Exception as e:
        conn.rollback()
        print(f"Error setting block status: {e}")
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# 6. DEPARTMENT QUERIES & STATUS MAPPING
# -----------------------------------------------------------------------------

def get_all_final_block_allocations(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves all active final block allocations."""
    init_final_allocation_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM final_block_allocations WHERE is_active = 1 ORDER BY allocation_id DESC")
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"Error fetching allocations: {e}")
        return []
    finally:
        conn.close()


def get_department_notifications(department: str, unread_only: bool = False, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Fetches targeted notifications exclusively for a specific department."""
    init_final_allocation_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        dept_clean = department.strip()
        sql = """
            SELECT notif_id, department, request_id, allocation_id, notification_type,
                   block, section, from_km, to_km, date, allocated_time, planning_type,
                   other_participating_departments, status, message, timestamp, is_read
            FROM department_notifications_v4
            WHERE LOWER(department) = LOWER(?) OR LOWER(department) LIKE LOWER(?)
        """
        params = [dept_clean, f"%{dept_clean}%"]
        if unread_only:
            sql += " AND is_read = 0"
        sql += " ORDER BY notif_id DESC"
        
        cur.execute(sql, params)
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error fetching department notifications: {e}")
        return []
    finally:
        conn.close()


def get_department_my_requests(department: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Fetches all requests for a department mapped with their official workflow statuses:
    SUBMITTED, UNDER PLANNING, ALTERNATIVES AVAILABLE, ALLOCATED, MODIFIED, RESCHEDULED, CANCELLED, COMPLETED.
    """
    init_final_allocation_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        dept_clean = department.strip()
        sql = """
            SELECT r.request_id, r.department, r.request_type, r.section, r.line, r.from_km, r.to_km,
                   r.required_duration, r.preferred_start, r.deadline, r.priority, r.status,
                   fa.allocation_id, fa.start_time as alloc_start, fa.end_time as alloc_end,
                   fa.date as alloc_date, fa.classification as alloc_class, fa.status as alloc_status,
                   fa.AI_recommended_option, fa.controller_selected_option, fa.override_reason
            FROM block_requests_v2 r
            LEFT JOIN final_block_allocations fa ON fa.request_ids LIKE ('%' || r.request_id || '%') AND fa.is_active = 1
            WHERE LOWER(r.department) = LOWER(?) OR LOWER(r.department) LIKE LOWER(?)
            ORDER BY r.request_id DESC
        """
        cur.execute(sql, [dept_clean, f"%{dept_clean}%"])
        rows = cur.fetchall()
        
        results = []
        for r in rows:
            d = dict(r)
            raw_status = (d.get("status") or "").upper().strip()
            alloc_status = (d.get("alloc_status") or "").upper().strip()

            # Map to standard Modification 4 statuses
            if alloc_status in ["ALLOCATED", "MODIFIED", "RESCHEDULED", "CANCELLED", "COMPLETED"]:
                wf_status = alloc_status
            elif raw_status in ["COMPLETED"]:
                wf_status = "COMPLETED"
            elif raw_status in ["CANCELLED", "DECLINED / HOLD"]:
                wf_status = "CANCELLED"
            elif raw_status in ["APPROVED / SCHEDULED", "APPROVED", "ALLOCATED"]:
                wf_status = "ALLOCATED"
            elif raw_status in ["UNDER PLANNING"]:
                wf_status = "UNDER PLANNING"
            elif raw_status in ["ALTERNATIVES AVAILABLE"]:
                wf_status = "ALTERNATIVES AVAILABLE"
            else:
                wf_status = "SUBMITTED"

            d["workflow_status"] = wf_status
            d["awaiting_controller"] = (wf_status in ["SUBMITTED", "UNDER PLANNING", "ALTERNATIVES AVAILABLE"])
            results.append(d)
        return results
    except Exception as e:
        print(f"Error fetching department requests: {e}")
        return []
    finally:
        conn.close()


def get_audit_trail_history(allocation_id: Optional[str] = None, request_id: Optional[str] = None, limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves chronological audit trail records."""
    init_final_allocation_db(db_path)
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        if allocation_id:
            cur.execute("""
                SELECT * FROM block_allocation_audit_trail
                WHERE allocation_id = ?
                ORDER BY audit_id ASC
            """, (allocation_id,))
        elif request_id:
            cur.execute("""
                SELECT * FROM block_allocation_audit_trail
                WHERE request_id = ? OR allocation_id IN (
                    SELECT allocation_id FROM final_block_allocations WHERE request_ids LIKE ('%' || ? || '%')
                )
                ORDER BY audit_id ASC
            """, (request_id, request_id))
        else:
            cur.execute("""
                SELECT * FROM block_allocation_audit_trail
                ORDER BY audit_id DESC LIMIT ?
            """, (limit,))
        return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"Error retrieving audit trail: {e}")
        return []
    finally:
        conn.close()
