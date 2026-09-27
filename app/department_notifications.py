import re
"""
Department Notification & Live Allocation Synchronization Engine (Step 9)
Indian Railways Automatic Block Planning System

Handles:
1. ALLOCATION_CONFIRMED application event generation post-Controller confirmation.
2. Direct identification of affected departments from request records.
3. Department-specific targeted notification formatting (ISOLATION, PARALLEL, SEQUENTIAL).
4. Full delivery state tracking (PENDING, SENT, DELIVERED, READ, ACKNOWLEDGED, FAILED).
5. Duplicate notification prevention (allocation_id + request_id + department).
6. Failed notification handling & Controller retry mechanisms without allocation rollback.
7. Department acknowledgement workflow & audit trail logging.
8. Single source-of-truth query helpers for Controller, Department Dashboards, and Map synchronization.
"""

import os
import sys
import sqlite3
import json
import textwrap
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


def clean_html(html_str: str) -> str:
    """Removes leading indentation on all lines so markdown never renders HTML as code blocks."""
    if not html_str:
        return ""
    return re.sub(r'^[ \t]+', '', str(html_str), flags=re.MULTILINE)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "railway.db")


# =============================================================================
# 1. DATABASE SCHEMA INITIALIZATION & MIGRATIONS
# =============================================================================

def init_notifications_db(db_path: str = DB_PATH):
    """
    Ensures department_notifications_v4 table and required columns exist.
    Non-destructive schema initialization and column migrations.
    """
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        
        # Ensure base table exists
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
        
        # Ensure audit trail table exists
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

        # Add optional columns if not present
        existing_cols = [c[1] for c in conn.execute("PRAGMA table_info(department_notifications_v4)").fetchall()]
        
        if "delivery_status" not in existing_cols:
            conn.execute("ALTER TABLE department_notifications_v4 ADD COLUMN delivery_status TEXT DEFAULT 'DELIVERED'")
        if "created_at" not in existing_cols:
            conn.execute("ALTER TABLE department_notifications_v4 ADD COLUMN created_at TEXT")
        if "sent_at" not in existing_cols:
            conn.execute("ALTER TABLE department_notifications_v4 ADD COLUMN sent_at TEXT")
        if "read_at" not in existing_cols:
            conn.execute("ALTER TABLE department_notifications_v4 ADD COLUMN read_at TEXT")
        if "acknowledged_at" not in existing_cols:
            conn.execute("ALTER TABLE department_notifications_v4 ADD COLUMN acknowledged_at TEXT")
        if "acknowledged_by" not in existing_cols:
            conn.execute("ALTER TABLE department_notifications_v4 ADD COLUMN acknowledged_by TEXT")

        conn.commit()
    except Exception as e:
        print(f"Error in init_notifications_db: {e}")
    finally:
        conn.close()


# =============================================================================
# 2. HELPER UTILITIES: DEPARTMENT STANDARDIZATION & AUDIT LOGGING
# =============================================================================

def format_standard_department_name(dept_str: str) -> str:
    """
    Standardizes department names across Engineering, OHE/Traction, and S&T.
    Avoids hardcoding discrepancies.
    """
    if not dept_str:
        return "Engineering"
    s = str(dept_str).strip().upper()
    if any(k in s for k in ["ENG", "P-WAY", "TRACK", "CIVIL"]):
        return "Engineering"
    if any(k in s for k in ["OHE", "TRD", "TRACTION", "ELECTRICAL", "POWER"]):
        return "OHE/Traction"
    if any(k in s for k in ["S&T", "SNT", "SIGNAL", "TELECOM", "INTERLOCK"]):
        return "S&T"
    return str(dept_str).strip()


def record_notification_audit_event(
    event_type: str,
    actor: str,
    allocation_id: Optional[str] = None,
    planning_group_id: Optional[str] = None,
    request_id: Optional[str] = None,
    details: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    db_path: str = DB_PATH
) -> int:
    """Records an immutable lifecycle event in block_allocation_audit_trail."""
    init_notifications_db(db_path)
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO block_allocation_audit_trail
            (allocation_id, planning_group_id, request_id, event_type, actor, timestamp, details, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            allocation_id, planning_group_id, request_id, event_type,
            actor, now_ts, details, json.dumps(metadata or {}, default=str)
        ))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        print(f"Error recording notification audit event: {e}")
        return 0
    finally:
        conn.close()


# =============================================================================
# 3. DEPARTMENT NOTIFICATION ENGINE
# =============================================================================

class DepartmentNotificationEngine:
    """
    Core engine managing event generation, affected department extraction,
    targeted notification dispatch, duplicate protection, and delivery tracking.
    """

    @staticmethod
    def create_allocation_confirmed_event(
        allocation_record: Dict[str, Any],
        group: Dict[str, Any],
        candidate: Any,
        controller_id: str = "CONTROLLER-BZA-01"
    ) -> Dict[str, Any]:
        """
        Creates the canonical ALLOCATION_CONFIRMED application event payload
        only after Controller confirmation and DB commit (Requirement 3).
        """
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alloc_id = allocation_record.get("allocation_id", "")
        req_ids = group.get("request_ids", [])
        if isinstance(candidate, dict):
            start_t = candidate.get("start_time", "")
            end_t = candidate.get("end_time", "")
            dur_m = candidate.get("duration", 60)
            c_type = candidate.get("classification", group.get("classification", "ISOLATION"))
        else:
            start_t = getattr(candidate, "start_time", "")
            end_t = getattr(candidate, "end_time", "")
            dur_m = getattr(candidate, "duration", 60)
            c_type = getattr(candidate, "classification", group.get("classification", "ISOLATION"))

        depts = [format_standard_department_name(d) for d in group.get("departments", [])]
        if not depts:
            depts = ["Engineering"]

        return {
            "event_type": "ALLOCATION_CONFIRMED",
            "allocation_id": alloc_id,
            "planning_group_id": group.get("group_id", ""),
            "request_ids": req_ids,
            "departments": list(dict.fromkeys(depts)),
            "classification": c_type,
            "section": group.get("section", ""),
            "block": group.get("block", group.get("section", "")),
            "from_km": float(group.get("from_km", 0.0)),
            "to_km": float(group.get("to_km", 0.0)),
            "date": str(group.get("date", "")),
            "start_time": start_t,
            "end_time": end_t,
            "duration_minutes": dur_m,
            "controller_id": controller_id,
            "timestamp": now_ts,
            "status": "ALLOCATED"
        }

    @staticmethod
    def identify_affected_departments(
        request_ids: List[str],
        db_path: str = DB_PATH
    ) -> List[Dict[str, Any]]:
        """
        Determines affected departments directly from the database request records (Requirement 4).
        Returns a list of dicts: [{"request_id": ..., "department": ..., "details": ...}].
        """
        init_notifications_db(db_path)
        affected = []
        if not request_ids:
            return affected

        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            placeholders = ",".join(["?"] * len(request_ids))
            cur.execute(f"""
                SELECT request_id, department, request_type, section, line, from_km, to_km, required_duration
                FROM block_requests_v2
                WHERE request_id IN ({placeholders})
            """, request_ids)
            rows = cur.fetchall()

            found_ids = set()
            for r in rows:
                r_dict = dict(r)
                found_ids.add(r_dict["request_id"])
                std_dept = format_standard_department_name(r_dict.get("department", "Engineering"))
                r_dict["standard_department"] = std_dept
                affected.append(r_dict)

            # Fallback for requests not yet in block_requests_v2
            for req_id in request_ids:
                if req_id not in found_ids:
                    # Infer standard department from ID prefix if present
                    std_dept = "Engineering"
                    if "TRD" in req_id or "OHE" in req_id:
                        std_dept = "OHE/Traction"
                    elif "SNT" in req_id or "S&T" in req_id or "SIG" in req_id:
                        std_dept = "S&T"
                    affected.append({
                        "request_id": req_id,
                        "department": std_dept,
                        "standard_department": std_dept,
                        "request_type": "Track Corridor Maintenance",
                        "section": "Corridor Section",
                        "line": "UP/DN Line",
                        "from_km": 0.0,
                        "to_km": 5.0,
                        "required_duration": 60
                    })
        except Exception as e:
            print(f"Error identifying affected departments: {e}")
        finally:
            conn.close()

        return affected

    @staticmethod
    def format_notification_message(
        dept_info: Dict[str, Any],
        group: Dict[str, Any],
        candidate: Any,
        all_affected_depts: List[str],
        controller_id: str,
        alloc_id: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Formats structured notification text and details payload based on classification:
        - ISOLATION: Single-department isolated possession.
        - PARALLEL: Joint block with co-located peer departments and shared requests.
        - SEQUENTIAL: Full execution order with individual phase timing.
        """
        if isinstance(candidate, dict):
            cand_dict = candidate
        else:
            cand_dict = candidate.to_dict() if hasattr(candidate, "to_dict") else dict(candidate.__dict__)

        my_dept = dept_info.get("standard_department", "Engineering")
        my_req_id = dept_info.get("request_id", "REQ-001")
        c_type = cand_dict.get("classification", group.get("classification", "ISOLATION"))
        block_val = group.get("block", group.get("section", "B-01"))
        sec_val = group.get("section", "Main Line")
        f_km = float(dept_info.get("from_km") or group.get("from_km", 0.0))
        t_km = float(dept_info.get("to_km") or group.get("to_km", 0.0))
        date_str = str(group.get("date", datetime.now().strftime("%d/%m/%Y")))
        start_t = cand_dict.get("start_time", "10:00")
        end_t = cand_dict.get("end_time", "11:00")
        dur_m = int(cand_dict.get("duration", 60))
        sequence_list = cand_dict.get("sequence", [])

        other_depts = [d for d in all_affected_depts if d != my_dept]
        other_depts_str = ", ".join(other_depts) if other_depts else "None (Single Department Isolation)"

        msg_lines = [
            "==========================================",
            "🔔 ALLOCATION CONFIRMED",
            "==========================================",
            f"Request: {my_req_id}",
            f"Department: {my_dept}",
            f"Classification: {c_type}",
            f"Date: {date_str}",
            f"Time: {start_t} – {end_t} IST ({dur_m} Mins)",
            f"Section: {sec_val}",
            f"Block: {block_val}",
            f"KM: {f_km:.1f} – {t_km:.1f}",
            f"Allocation ID: {alloc_id}",
            f"Status: ALLOCATED",
            f"Controller Confirmed: {datetime.now().strftime('%H:%M IST')} ({controller_id})"
        ]

        if c_type == "PARALLEL":
            msg_lines.append(f"Joint Department(s): {other_depts_str}")
            msg_lines.append("Shared Operation: Co-ordinated simultaneous possession window.")
        elif c_type == "SEQUENTIAL":
            msg_lines.append("Execution Order & Timeline:")
            if sequence_list:
                for step in sequence_list:
                    s_no = step.get("step", 1)
                    s_dept = step.get("department", "Engineering")
                    s_act = step.get("activity", "Maintenance")
                    s_st = step.get("start_time", "")
                    s_et = step.get("end_time", "")
                    is_me = (format_standard_department_name(s_dept) == my_dept)
                    pointer = " ◄ [YOUR PHASE]" if is_me else ""
                    msg_lines.append(f"  Step {s_no}: {s_st}–{s_et} | {s_dept} ({s_act}){pointer}")
            else:
                msg_lines.append(f"  Phase: Designated sequence for {my_dept} within {start_t}–{end_t}")
        else:
            msg_lines.append("Isolation: Dedicated exclusive track possession (No conflicting departments).")

        msg_lines.append("==========================================")
        formatted_msg = "\n".join(msg_lines)

        details_payload = {
            "allocation_id": alloc_id,
            "request_id": my_req_id,
            "department": my_dept,
            "classification": c_type,
            "section": sec_val,
            "block": block_val,
            "from_km": f_km,
            "to_km": t_km,
            "date": date_str,
            "start_time": start_t,
            "end_time": end_t,
            "duration_minutes": dur_m,
            "other_participating_departments": other_depts,
            "sequence_plan": sequence_list,
            "controller_id": controller_id,
            "status": "ALLOCATED"
        }

        return formatted_msg, details_payload

    @staticmethod
    def dispatch_allocation_notifications(
        allocation_id: str,
        group: Dict[str, Any],
        candidate: Any,
        controller_id: str = "CONTROLLER-BZA-01",
        simulate_failure: bool = False,
        db_path: str = DB_PATH
    ) -> Dict[str, Any]:
        """
        Dispatches targeted notifications to affected departments upon Controller confirmation (Requirement 3-8).
        Guarantees:
        1. Only affected departments receive notifications.
        2. Duplicate notification protection.
        3. Delivery status tracking (DELIVERED / FAILED).
        4. If failure occurs, allocation remains ALLOCATED, notification becomes FAILED.
        """
        init_notifications_db(db_path)
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        req_ids = group.get("request_ids", [])
        
        # 1. Identify affected requests and departments
        affected_reqs = DepartmentNotificationEngine.identify_affected_departments(req_ids, db_path)
        all_affected_depts = list(dict.fromkeys([r["standard_department"] for r in affected_reqs]))

        # 2. Build canonical ALLOCATION_CONFIRMED event
        confirmed_event = DepartmentNotificationEngine.create_allocation_confirmed_event(
            {"allocation_id": allocation_id}, group, candidate, controller_id
        )

        # 3. Log ALLOCATION_CONFIRMED event to audit trail
        record_notification_audit_event(
            event_type="ALLOCATION_CONFIRMED",
            actor=controller_id,
            allocation_id=allocation_id,
            planning_group_id=group.get("group_id", ""),
            request_id=", ".join(req_ids),
            details=f"Controller confirmed allocation '{allocation_id}' for {group.get('classification', 'ISOLATION')} group.",
            metadata=confirmed_event,
            db_path=db_path
        )

        dispatched = []
        failed = []
        duplicates_skipped = []

        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            cur = conn.cursor()

            for req_info in affected_reqs:
                my_dept = req_info["standard_department"]
                my_req_id = req_info["request_id"]

                # Check Duplicate Notification Protection (Requirement 19)
                cur.execute("""
                    SELECT notif_id, delivery_status FROM department_notifications_v4
                    WHERE allocation_id = ? AND request_id = ? AND department = ?
                """, (allocation_id, my_req_id, my_dept))
                existing_notif = cur.fetchone()

                if existing_notif and existing_notif[1] in ["SENT", "DELIVERED", "READ", "ACKNOWLEDGED"]:
                    duplicates_skipped.append({
                        "notif_id": existing_notif[0],
                        "request_id": my_req_id,
                        "department": my_dept,
                        "reason": "Existing valid notification already dispatched"
                    })
                    continue

                # Format targeted notification message
                msg_text, details_dict = DepartmentNotificationEngine.format_notification_message(
                    dept_info=req_info,
                    group=group,
                    candidate=candidate,
                    all_affected_depts=all_affected_depts,
                    controller_id=controller_id,
                    alloc_id=allocation_id
                )

                # Determine delivery state
                if simulate_failure:
                    delivery_st = "FAILED"
                else:
                    delivery_st = "DELIVERED"

                block_val = group.get("block", group.get("section", "B-01"))
                sec_val = group.get("section", "Main Line")
                f_km = float(req_info.get("from_km") or group.get("from_km", 0.0))
                t_km = float(req_info.get("to_km") or group.get("to_km", 0.0))
                date_str = str(group.get("date", datetime.now().strftime("%d/%m/%Y")))
                if isinstance(candidate, dict):
                    start_t = candidate.get("start_time", "10:00")
                    end_t = candidate.get("end_time", "11:00")
                    c_type = candidate.get("classification", "ISOLATION")
                else:
                    start_t = getattr(candidate, "start_time", "10:00")
                    end_t = getattr(candidate, "end_time", "11:00")
                    c_type = getattr(candidate, "classification", "ISOLATION")

                other_depts_str = ", ".join([d for d in all_affected_depts if d != my_dept]) or "None"

                if existing_notif:
                    # Update existing failed notification
                    cur.execute("""
                        UPDATE department_notifications_v4
                        SET notification_type = 'BLOCK ALLOCATED',
                            status = 'ALLOCATED BY CONTROLLER',
                            delivery_status = ?,
                            message = ?,
                            details_json = ?,
                            timestamp = ?,
                            sent_at = ?
                        WHERE notif_id = ?
                    """, (
                        delivery_st, msg_text, json.dumps(details_dict, default=str),
                        now_ts, now_ts, existing_notif[0]
                    ))
                    notif_id = existing_notif[0]
                else:
                    # Insert new notification
                    cur.execute("""
                        INSERT INTO department_notifications_v4
                        (department, request_id, allocation_id, notification_type, block, section,
                         from_km, to_km, date, allocated_time, planning_type, other_participating_departments,
                         status, delivery_status, message, details_json, timestamp, created_at, sent_at, is_read)
                        VALUES (?, ?, ?, 'BLOCK ALLOCATED', ?, ?, ?, ?, ?, ?, ?, ?, 'ALLOCATED BY CONTROLLER', ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        my_dept, my_req_id, allocation_id, block_val, sec_val,
                        f_km, t_km, date_str, f"{start_t}–{end_t}", c_type, other_depts_str,
                        delivery_st, msg_text, json.dumps(details_dict, default=str), now_ts, now_ts, now_ts
                    ))
                    notif_id = cur.lastrowid

                # Audit Log
                audit_event = "DEPARTMENT_NOTIFIED" if delivery_st == "DELIVERED" else "NOTIFICATION_FAILED"
                cur.execute("""
                    INSERT INTO block_allocation_audit_trail
                    (allocation_id, planning_group_id, request_id, event_type, actor, timestamp, details, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    allocation_id, group.get("group_id", ""), my_req_id, audit_event,
                    "System (Dispatcher)", now_ts,
                    f"Notification {delivery_st} for {my_dept} on Request {my_req_id} (Allocation: {allocation_id}).",
                    json.dumps({"notif_id": notif_id, "department": my_dept, "delivery_status": delivery_st})
                ))

                result_entry = {
                    "notif_id": notif_id,
                    "department": my_dept,
                    "request_id": my_req_id,
                    "delivery_status": delivery_st,
                    "message": msg_text
                }

                if delivery_st == "DELIVERED":
                    dispatched.append(result_entry)
                else:
                    failed.append(result_entry)

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error dispatching notifications: {e}")
            return {
                "success": False,
                "error": str(e),
                "event": confirmed_event,
                "dispatched": dispatched,
                "failed": failed
            }
        finally:
            conn.close()

        return {
            "success": len(failed) == 0,
            "allocation_id": allocation_id,
            "event": confirmed_event,
            "dispatched": dispatched,
            "failed": failed,
            "duplicates_skipped": duplicates_skipped,
            "total_affected": len(affected_reqs)
        }

    @staticmethod
    def retry_failed_notification(
        notif_id: int,
        actor: str = "CONTROLLER-BZA-01",
        db_path: str = DB_PATH
    ) -> Tuple[bool, str]:
        """
        Retries delivering a previously failed notification without modifying or duplicating allocation (Requirement 18).
        """
        init_notifications_db(db_path)
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            cur = conn.cursor()
            cur.execute("SELECT notif_id, department, request_id, allocation_id FROM department_notifications_v4 WHERE notif_id = ?", (notif_id,))
            row = cur.fetchone()
            if not row:
                return False, f"Notification #{notif_id} not found."

            n_id, dept, req_id, alloc_id = row
            cur.execute("""
                UPDATE department_notifications_v4
                SET delivery_status = 'DELIVERED',
                    timestamp = ?,
                    sent_at = ?
                WHERE notif_id = ?
            """, (now_ts, now_ts, n_id))

            # Log audit trail event
            cur.execute("""
                INSERT INTO block_allocation_audit_trail
                (allocation_id, request_id, event_type, actor, timestamp, details, metadata_json)
                VALUES (?, ?, 'NOTIFICATION_RETRIED', ?, ?, ?, ?)
            """, (
                alloc_id, req_id, actor, now_ts,
                f"Notification #{n_id} retried successfully by {actor} for {dept}.",
                json.dumps({"notif_id": n_id, "department": dept, "delivery_status": "DELIVERED"})
            ))

            conn.commit()
            return True, f"Notification #{n_id} for {dept} ({req_id}) successfully delivered."
        except Exception as e:
            conn.rollback()
            return False, f"Retry failed: {e}"
        finally:
            conn.close()

    @staticmethod
    def mark_notification_as_read(
        notif_id: int,
        reader_user: str = "dept_user",
        db_path: str = DB_PATH
    ) -> bool:
        """
        Marks notification as READ upon opening without prematurely acknowledging it (Requirement 11, 12).
        """
        init_notifications_db(db_path)
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            cur = conn.cursor()
            cur.execute("SELECT allocation_id, request_id, department, delivery_status FROM department_notifications_v4 WHERE notif_id = ?", (notif_id,))
            row = cur.fetchone()
            if not row:
                return False

            alloc_id, req_id, dept, cur_del_st = row
            new_del_st = "READ" if cur_del_st in ["DELIVERED", "SENT"] else cur_del_st

            cur.execute("""
                UPDATE department_notifications_v4
                SET is_read = 1,
                    read_at = ?,
                    delivery_status = ?
                WHERE notif_id = ?
            """, (now_ts, new_del_st, notif_id))

            # Audit Trail
            cur.execute("""
                INSERT INTO block_allocation_audit_trail
                (allocation_id, request_id, event_type, actor, timestamp, details, metadata_json)
                VALUES (?, ?, 'NOTIFICATION_READ', ?, ?, ?, ?)
            """, (
                alloc_id, req_id, reader_user, now_ts,
                f"Notification #{notif_id} opened and marked READ by {reader_user}.",
                json.dumps({"notif_id": notif_id, "department": dept})
            ))

            conn.commit()
            return True
        except Exception as e:
            print(f"Error marking notification read: {e}")
            return False
        finally:
            conn.close()

    @staticmethod
    def acknowledge_notification(
        notif_id: int,
        acknowledged_by: str = "SSE_PWAY",
        remarks: str = "Block window noted and gangs mobilized",
        db_path: str = DB_PATH
    ) -> Tuple[bool, str]:
        """
        Explicitly acknowledges the block allocation by department staff (Requirement 12).
        """
        init_notifications_db(db_path)
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            cur = conn.cursor()
            cur.execute("SELECT allocation_id, request_id, department FROM department_notifications_v4 WHERE notif_id = ?", (notif_id,))
            row = cur.fetchone()
            if not row:
                return False, f"Notification #{notif_id} not found."

            alloc_id, req_id, dept = row
            cur.execute("""
                UPDATE department_notifications_v4
                SET status = 'ACKNOWLEDGED',
                    delivery_status = 'ACKNOWLEDGED',
                    is_read = 1,
                    acknowledged_at = ?,
                    acknowledged_by = ?
                WHERE notif_id = ?
            """, (now_ts, acknowledged_by, notif_id))

            # Record in Audit Trail
            cur.execute("""
                INSERT INTO block_allocation_audit_trail
                (allocation_id, request_id, event_type, actor, timestamp, details, metadata_json)
                VALUES (?, ?, 'NOTIFICATION_ACKNOWLEDGED', ?, ?, ?, ?)
            """, (
                alloc_id, req_id, acknowledged_by, now_ts,
                f"Notification #{notif_id} explicitly ACKNOWLEDGED by {acknowledged_by} ({dept}). Remarks: {remarks}",
                json.dumps({"notif_id": notif_id, "department": dept, "remarks": remarks})
            ))

            conn.commit()
            return True, f"Allocation for Request {req_id} successfully ACKNOWLEDGED by {acknowledged_by}."
        except Exception as e:
            conn.rollback()
            return False, f"Acknowledgement error: {e}"
        finally:
            conn.close()

    @staticmethod
    def get_department_notifications(
        department: str,
        unread_only: bool = False,
        limit: int = 50,
        db_path: str = DB_PATH
    ) -> List[Dict[str, Any]]:
        """
        Retrieves targeted notifications for a specific department (Requirement 10, 32).
        Enforces strict department authorization filtering.
        """
        init_notifications_db(db_path)
        std_dept = format_standard_department_name(department)
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            q = "SELECT * FROM department_notifications_v4 WHERE 1=1"
            params = []

            if std_dept.upper() != "ALL":
                q += " AND (UPPER(department) = ? OR UPPER(department) LIKE ?)"
                params.append(std_dept.upper())
                params.append(f"%{std_dept.upper()}%")

            if unread_only:
                q += " AND is_read = 0"

            q += f" ORDER BY notif_id DESC LIMIT {int(limit)}"
            rows = cur.execute(q, params).fetchall()

            results = []
            for r in rows:
                r_dict = dict(r)
                det = {}
                if r_dict.get("details_json"):
                    try:
                        det = json.loads(r_dict["details_json"])
                    except Exception:
                        det = {}
                r_dict["parsed_details"] = det
                results.append(r_dict)
            return results
        except Exception as e:
            print(f"Error fetching department notifications: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def get_unread_notification_count(
        department: str,
        db_path: str = DB_PATH
    ) -> int:
        """Returns integer count of unread notifications for a department."""
        init_notifications_db(db_path)
        std_dept = format_standard_department_name(department)
        conn = sqlite3.connect(db_path, timeout=30.0)
        try:
            cur = conn.cursor()
            if std_dept.upper() == "ALL":
                cnt = cur.execute("SELECT COUNT(*) FROM department_notifications_v4 WHERE is_read = 0").fetchone()[0]
            else:
                cnt = cur.execute("""
                    SELECT COUNT(*) FROM department_notifications_v4 
                    WHERE is_read = 0 AND (UPPER(department) = ? OR UPPER(department) LIKE ?)
                """, (std_dept.upper(), f"%{std_dept.upper()}%")).fetchone()[0]
            return int(cnt or 0)
        except Exception:
            return 0
        finally:
            conn.close()

    @staticmethod
    def get_controller_allocation_notifications_summary(
        allocation_id: str,
        db_path: str = DB_PATH
    ) -> List[Dict[str, Any]]:
        """
        Provides Controller with real-time notification dispatch status for an allocation (Requirement 16, 26).
        """
        init_notifications_db(db_path)
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            rows = cur.execute("""
                SELECT notif_id, department, request_id, allocation_id, delivery_status, status, is_read, sent_at, acknowledged_at, acknowledged_by
                FROM department_notifications_v4
                WHERE allocation_id = ?
                ORDER BY notif_id ASC
            """, (allocation_id,)).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"Error getting controller allocation summary: {e}")
            return []
        finally:
            conn.close()


def get_department_notifications(
    department: str,
    unread_only: bool = False,
    limit: int = 50,
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """Module-level convenience wrapper for DepartmentNotificationEngine.get_department_notifications."""
    return DepartmentNotificationEngine.get_department_notifications(
        department=department,
        unread_only=unread_only,
        limit=limit,
        db_path=db_path
    )


def get_unread_notification_count(
    department: str,
    db_path: str = DB_PATH
) -> int:
    """Module-level convenience wrapper for DepartmentNotificationEngine.get_unread_notification_count."""
    return DepartmentNotificationEngine.get_unread_notification_count(
        department=department,
        db_path=db_path
    )


# =============================================================================
# 4. STREAMLIT UI RENDERERS (DEPARTMENT PORTAL & CONTROLLER NOTIFICATIONS)
# =============================================================================

def render_department_notifications_panel(department: str, user: str = "dept_user"):
    """
    Renders the dedicated Notification Area in the Department Portal (Requirement 10-13, 27, 28).
    Displays unread badge, targeted block allocation cards, joint/sequential views, and explicit acknowledgement.
    """
    import streamlit as st

    std_dept = format_standard_department_name(department)
    unread_cnt = DepartmentNotificationEngine.get_unread_notification_count(std_dept)
    notifs = DepartmentNotificationEngine.get_department_notifications(std_dept, unread_only=False, limit=20)

    badge_html = f"<span style='background:#ef4444; color:#fff; padding:2px 8px; border-radius:12px; font-size:12px; font-weight:800; margin-left:8px;'>{unread_cnt} NEW</span>" if unread_cnt > 0 else "<span style='background:#334155; color:#94a3b8; padding:2px 8px; border-radius:12px; font-size:12px; margin-left:8px;'>0 NEW</span>"

    st.markdown(clean_html(f"#### 🔔 NOTIFICATIONS {badge_html}"), unsafe_allow_html=True)
    st.caption(f"Official Indian Railways Block Allocation Advisories for **{std_dept}**.")

    if not notifs:
        st.info("ℹ️ No block allocation notifications recorded for this department yet.")
        return

    for notif in notifs:
        notif_id = notif["notif_id"]
        req_id = notif["request_id"]
        alloc_id = notif["allocation_id"]
        n_type = notif.get("notification_type", "BLOCK ALLOCATED")
        p_type = notif.get("planning_type", "ISOLATION")
        block_val = notif.get("block", "B-01")
        sec_val = notif.get("section", "Main Section")
        f_km = float(notif.get("from_km", 0.0))
        t_km = float(notif.get("to_km", 0.0))
        date_val = notif.get("date", "")
        alloc_time = notif.get("allocated_time", "")
        deliv_st = notif.get("delivery_status", "DELIVERED")
        is_ack = (notif.get("status") == "ACKNOWLEDGED" or deliv_st == "ACKNOWLEDGED")
        is_read = bool(notif.get("is_read", 0))
        other_depts = notif.get("other_participating_departments", "None")

        # Color coding
        card_border = "#10b981" if is_ack else ("#3b82f6" if is_read else "#f59e0b")
        status_badge_bg = "#065f46" if is_ack else ("#1e3a8a" if is_read else "#78350f")
        status_text = "✅ ACKNOWLEDGED" if is_ack else ("📖 READ" if is_read else "🟡 UNREAD")

        notif_card_html = f"""
        <div style="background:#0f172a; border: 1.5px solid {card_border}; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.4);">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1e293b; padding-bottom:6px; margin-bottom:8px;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-weight:800; font-size:14px; color:#f8fafc;">📢 {n_type}: <code style="color:#38bdf8;">{req_id}</code></span>
                    <span style="background:{'#1e3a8a' if p_type=='ISOLATION' else ('#064e3b' if p_type=='PARALLEL' else '#581c87')}; color:#fff; padding:1px 6px; border-radius:4px; font-size:11px; font-weight:700;">{p_type}</span>
                </div>
                <div>
                    <span style="background:{status_badge_bg}; color:#fff; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:700;">{status_text}</span>
                    <span style="font-size:11px; color:#94a3b8; margin-left:6px;">🕒 {notif.get('timestamp', '')}</span>
                </div>
            </div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; font-size:12px; color:#cbd5e1;">
                <div>🧱 <b>Block:</b> <code>{block_val}</code></div>
                <div>📍 <b>Section:</b> {sec_val}</div>
                <div>📏 <b>KM Span:</b> Km {f_km:.1f} – {t_km:.1f}</div>
                <div>📅 <b>Date:</b> {date_val}</div>
                <div>🕒 <b>Possession Time:</b> <strong style="color:#4ade80;">{alloc_time} IST</strong></div>
                <div>🆔 <b>Allocation:</b> <code>{alloc_id}</code></div>
            </div>
        </div>
        """
        st.markdown(clean_html(textwrap.dedent(notif_card_html).strip()), unsafe_allow_html=True)

        # Interactive Expander for View Allocation & Acknowledgement
        with st.expander(f"🔍 [VIEW ALLOCATION] Full Details for {req_id} ({alloc_id})", expanded=False):
            # Auto mark read when opened
            if not is_read:
                DepartmentNotificationEngine.mark_notification_as_read(notif_id, reader_user=user)

            parsed_det = notif.get("parsed_details", {})
            seq_plan = parsed_det.get("sequence_plan", [])

            # Classification Specific Visuals (Requirement 27, 28)
            if p_type == "PARALLEL":
                par_banner_html = f"""
                <div style="background:#064e3b; border-left:4px solid #10b981; padding:8px 12px; border-radius:4px; margin-bottom:10px; font-size:12px; color:#ecfdf5;">
                    <b>🤝 JOINT BLOCK COORDINATION:</b> This block is co-ordinated simultaneously with: <b>{other_depts}</b>.<br/>
                    All participating departments share the single continuous possession window ({alloc_time} IST).
                </div>
                """
                st.markdown(clean_html(textwrap.dedent(par_banner_html).strip()), unsafe_allow_html=True)
            elif p_type == "SEQUENTIAL":
                seq_banner_html = """
                <div style="background:#581c87; border-left:4px solid #c084fc; padding:8px 12px; border-radius:4px; margin-bottom:10px; font-size:12px; color:#faf5ff;">
                    <b>⏱️ SEQUENTIAL EXECUTION ORDER:</b> Multi-department predecessor hand-off plan.
                </div>
                """
                st.markdown(clean_html(textwrap.dedent(seq_banner_html).strip()), unsafe_allow_html=True)
                if seq_plan:
                    st.markdown("**Phased Timeline:**")
                    for step in seq_plan:
                        s_dept = step.get("department", "Engineering")
                        is_current = (format_standard_department_name(s_dept) == std_dept)
                        p_color = "#34d399" if is_current else "#94a3b8"
                        p_badge = " ◄ [YOUR DEPARTMENT'S PHASE]" if is_current else ""
                        st.markdown(f"- **Step {step.get('step', 1)}:** `{step.get('start_time')}–{step.get('end_time')}` ({step.get('duration', 30)}m) — **{s_dept}** ({step.get('activity', 'Work')}) <span style='color:{p_color}; font-weight:700;'>{p_badge}</span>", unsafe_allow_html=True)

            # Allocation Specifications
            c_det1, c_det2 = st.columns(2)
            with c_det1:
                st.write(f"• **Your Request ID:** `{req_id}`")
                st.write(f"• **Your Department:** `{std_dept}`")
                st.write(f"• **Allocated Block Assignment:** `{block_val}`")
                st.write(f"• **Section & Track Span:** `{sec_val}` (Km {f_km:.1f}–{t_km:.1f})")
            with c_det2:
                st.write(f"• **Date:** `{date_val}`")
                st.write(f"• **Authorized Window:** `{alloc_time} IST`")
                st.write(f"• **Classification:** `{p_type}`")
                st.write(f"• **Master Allocation Record:** `{alloc_id}`")

            # Acknowledgement Action
            if not is_ack:
                ack_remarks = st.text_input(
                    "Acknowledgement Remarks:",
                    value=f"Possession window {alloc_time} noted. Maintenance gang & machinery mobilization scheduled.",
                    key=f"txt_ack_rem_{notif_id}"
                )
                if st.button("✅ ACKNOWLEDGE ALLOCATION (Confirm Readiness)", key=f"btn_ack_notif_{notif_id}", type="primary"):
                    succ, ack_msg = DepartmentNotificationEngine.acknowledge_notification(
                        notif_id=notif_id,
                        acknowledged_by=user,
                        remarks=ack_remarks
                    )
                    if succ:
                        st.toast(ack_msg, icon="✅")
                        st.rerun()
                    else:
                        st.error(f"❌ {ack_msg}")
            else:
                st.success(f"✅ Allocation explicitly acknowledged by **{notif.get('acknowledged_by', user)}** at `{notif.get('acknowledged_at', '')}`.")


def render_controller_notifications_summary():
    """
    Renders the Controller's live synchronized notification status monitor (Requirement 16, 18, 26).
    Displays department notification delivery states (NOTIFIED ✓, ACKNOWLEDGED ✓, or FAILED with [RETRY]).
    """
    import streamlit as st

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        allocs = cur.execute("""
            SELECT allocation_id, planning_group_id, request_ids, block, section, date, start_time, end_time, duration, classification, departments, status, created_at
            FROM final_block_allocations
            WHERE is_active = 1
            ORDER BY created_at DESC
            LIMIT 6
        """).fetchall()
    except Exception:
        allocs = []
    finally:
        conn.close()

    if not allocs:
        return

    st.markdown("#### 📡 Controller Real-Time Allocation & Department Notification Synchronization (Step 9)")
    st.caption("Live Dispatch Monitor • Department Notifications Delivery Tracking • Single Shared Allocation Record")

    for alloc in allocs:
        alloc_id = alloc["allocation_id"]
        grp_id = alloc["planning_group_id"]
        req_ids_str = alloc["request_ids"]
        block_val = alloc["block"]
        sec_val = alloc["section"]
        date_val = alloc["date"]
        start_t = alloc["start_time"]
        end_t = alloc["end_time"]
        c_type = alloc["classification"]
        alloc_st = alloc["status"]

        # Fetch notifications attached to this allocation
        notif_list = DepartmentNotificationEngine.get_controller_allocation_notifications_summary(alloc_id)

        # Build notification badges
        notif_badges = []
        has_failed = False
        failed_notifs = []

        for n in notif_list:
            d_dept = n["department"]
            d_req = n["request_id"]
            d_st = n.get("delivery_status", "DELIVERED")
            is_ack = (n.get("status") == "ACKNOWLEDGED" or d_st == "ACKNOWLEDGED")
            is_read = bool(n.get("is_read", 0))

            if d_st == "FAILED":
                has_failed = True
                failed_notifs.append(n)
                notif_badges.append(f"<span style='background:#7f1d1d; color:#fca5a5; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:700;'>❌ {d_req} ({d_dept}): FAILED</span>")
            elif is_ack:
                notif_badges.append(f"<span style='background:#065f46; color:#a7f3d0; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:700;'>✅ {d_req} ({d_dept}): ACKNOWLEDGED ✓</span>")
            elif is_read:
                notif_badges.append(f"<span style='background:#1e3a8a; color:#93c5fd; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:700;'>📖 {d_req} ({d_dept}): READ ✓</span>")
            else:
                notif_badges.append(f"<span style='background:#065f46; color:#a7f3d0; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:700;'>🔔 {d_req} ({d_dept}): NOTIFIED ✓</span>")

        badges_html = " &nbsp; ".join(notif_badges) if notif_badges else "<span style='color:#94a3b8; font-size:11px;'>No notifications dispatched</span>"

        summary_card_html = f"""
        <div style="background:#090d16; border: 1.5px solid #1e293b; border-radius:8px; padding:10px 14px; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <div>
                    <strong style="color:#f8fafc; font-size:13px;">🆔 <code>{alloc_id}</code></strong> &nbsp;|&nbsp;
                    <span style="color:#38bdf8; font-weight:700; font-size:12px;">{sec_val} ({block_val})</span> &nbsp;|&nbsp;
                    <span style="color:#4ade80; font-weight:700; font-size:12px;">🕒 {start_t}–{end_t} IST ({date_val})</span>
                </div>
                <div>
                    <span style="background:#1e293b; color:#cbd5e1; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:700;">{c_type}</span>
                    <span style="background:#065f46; color:#a7f3d0; padding:2px 6px; border-radius:4px; font-size:11px; font-weight:700; margin-left:4px;">{alloc_st}</span>
                </div>
            </div>
            <div style="font-size:12px; color:#cbd5e1; margin-top:4px;">
                📋 <b>Requests:</b> <code>{req_ids_str}</code> &nbsp;|&nbsp; <b>Dispatch Status:</b> {badges_html}
            </div>
        </div>
        """
        st.markdown(clean_html(textwrap.dedent(summary_card_html).strip()), unsafe_allow_html=True)

        # Render Retry Button if any notification failed (Requirement 18)
        if has_failed and failed_notifs:
            for fn in failed_notifs:
                f_nid = fn["notif_id"]
                f_dept = fn["department"]
                f_req = fn["request_id"]
                st.error(f"⚠️ **Notification Delivery Failed for {f_dept} ({f_req}).** Block remains ALLOCATED.")
                if st.button(f"🔄 RETRY NOTIFICATION FOR {f_dept} ({f_req})", key=f"btn_retry_notif_{f_nid}", type="primary"):
                    succ, r_msg = DepartmentNotificationEngine.retry_failed_notification(f_nid, actor="CONTROLLER-BZA-01")
                    if succ:
                        st.toast(r_msg, icon="✅")
                        st.rerun()
                    else:
                        st.error(r_msg)

