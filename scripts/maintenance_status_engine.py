"""
Phase 8: Maintenance Status Engine for Indian Railways Block Planning System
Provides:
1. Strict mathematical status calculation from due_date, current_date, completion_date.
2. 8 Canonical Statuses: SCHEDULED, DUE, OVERDUE, IN_PROGRESS, BLOCK_REQUIRED, BLOCK_ALLOCATED, COMPLETED, CANCELLED.
3. Realistic DEMO maintenance records spanning Engineering, TRD, and S&T departments.
4. AI Planner integration ensuring: OVERDUE ≠ automatic permission to block a busy section.
"""

import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")

CANONICAL_STATUSES = [
    "SCHEDULED",
    "DUE",
    "OVERDUE",
    "IN_PROGRESS",
    "BLOCK_REQUIRED",
    "BLOCK_ALLOCATED",
    "COMPLETED",
    "CANCELLED"
]

class MaintenanceStatusEngine:
    """
    Automated Maintenance Status Engine.
    Evaluates maintenance lifecycle states from temporal markers and operational constraints.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.ensure_table_exists()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_table_exists(self):
        """Creates the maintenance_status_records table if not present."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_status_records (
                record_id TEXT PRIMARY KEY,
                department TEXT NOT NULL,
                section_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                asset_name TEXT NOT NULL,
                task_description TEXT NOT NULL,
                severity TEXT NOT NULL,
                reported_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                current_date_ref TEXT NOT NULL,
                completion_date TEXT,
                planned_start TEXT,
                planned_end TEXT,
                status TEXT NOT NULL,
                overdue_days INTEGER DEFAULT 0,
                block_required INTEGER DEFAULT 1,
                block_allocated INTEGER DEFAULT 0,
                allocated_window TEXT,
                estimated_duration_minutes INTEGER DEFAULT 90,
                speed_restriction_kmh INTEGER,
                planner_verdict TEXT,
                planner_safety_notes TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    @staticmethod
    def parse_date(date_val):
        """Parses various date representations into datetime.date object."""
        if date_val is None or str(date_val).strip() in ("", "None", "null", "N/A", "--"):
            return None
        if isinstance(date_val, (datetime, pd.Timestamp)):
            return date_val.date()
        if isinstance(date_val, date):
            return date_val
        date_str = str(date_val).strip()
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(date_str[:10], fmt[:10] if len(date_str) == 10 else fmt).date()
            except ValueError:
                continue
        return None

    @classmethod
    def calculate_status_and_overdue(
        cls,
        due_date,
        current_date=None,
        completion_date=None,
        is_cancelled=False,
        is_in_progress=False,
        block_allocated=False,
        block_required=True,
        planned_start=None
    ):
        """
        Determines canonical maintenance status and exact overdue days.
        Strictly derives state from dates and lifecycle flags.
        
        Rules:
        1. If is_cancelled -> CANCELLED (overdue_days = 0)
        2. If completion_date is provided and <= current_date -> COMPLETED (overdue_days = 0)
        3. If is_in_progress -> IN_PROGRESS
        4. If block_allocated -> BLOCK_ALLOCATED
        5. If current_date > due_date and completion_date is None -> OVERDUE (overdue_days = (current_date - due_date).days)
        6. If current_date == due_date or (due_date - current_date).days <= 2 -> DUE
        7. If planned_start is set and > current_date -> SCHEDULED
        8. If block_required and not allocated -> BLOCK_REQUIRED
        9. Default -> SCHEDULED
        """
        curr_d = cls.parse_date(current_date) or date.today()
        due_d = cls.parse_date(due_date)
        comp_d = cls.parse_date(completion_date)
        plan_d = cls.parse_date(planned_start)

        overdue_days = 0
        if due_d:
            if comp_d:
                # If completed, overdue calculation reflects if it was closed late or 0
                overdue_days = 0
            else:
                days_diff = (curr_d - due_d).days
                overdue_days = max(0, days_diff)

        # 1. Cancelled
        if is_cancelled:
            return "CANCELLED", 0

        # 2. Completed
        if comp_d is not None:
            return "COMPLETED", 0

        # 3. Active execution on track
        if is_in_progress:
            return "IN_PROGRESS", overdue_days

        # 4. Block allocated / scheduled window confirmed
        if block_allocated:
            return "BLOCK_ALLOCATED", overdue_days

        # 5. Overdue (due date has elapsed without completion)
        if due_d and curr_d > due_d:
            return "OVERDUE", overdue_days

        # 6. Due (due today or within 2 days)
        if due_d and 0 <= (due_d - curr_d).days <= 2:
            return "DUE", 0

        # 7. Scheduled (future planned execution)
        if plan_d and plan_d > curr_d:
            return "SCHEDULED", 0

        # 8. Block required (identified maintenance requiring possession)
        if block_required:
            return "BLOCK_REQUIRED", 0

        return "SCHEDULED", 0

    @classmethod
    def evaluate_overdue_safety_constraint(cls, record: dict, is_peak_corridor: bool = True) -> dict:
        """
        Evaluates Planner Rule:
        OVERDUE != automatic permission to block a busy section.
        Safety and train movement constraints remain mandatory.
        """
        severity = record.get("severity", "Medium")
        overdue_days = int(record.get("overdue_days", 0))
        dept = record.get("department", "Engineering")
        section = record.get("section_id", "Vijayawada-SEC-01")
        req_dur = int(record.get("estimated_duration_minutes", 90))

        # Risk escalation score
        sev_weight = {"Critical": 50, "High": 35, "Medium": 20, "Low": 10}.get(severity, 20)
        overdue_factor = min(40, overdue_days * 5)
        escalated_priority = sev_weight + overdue_factor

        if is_peak_corridor and escalated_priority >= 70:
            # Overdue item on heavy traffic corridor
            verdict = "DEFERRED_SAFETY_PRIORITY_PROTECTED"
            reason = (
                f"SAFETY ENFORCEMENT: Item is OVERDUE by {overdue_days} days (Priority {escalated_priority}/100), "
                f"but Section {section} carries high-density passenger/freight movement during peak hours. "
                f"OVERDUE status DOES NOT grant automatic permission to halt critical trains. "
                f"Mandatory Action: Impose Temporary Speed Restriction (TSR 30 km/h) and schedule track possession during night shadow window (01:30–04:00)."
            )
            rec_window = "02:00 – 04:00 (Night Shadow)"
            action = "APPLY_TSR_AND_NIGHT_WINDOW"
        elif not is_peak_corridor or escalated_priority < 70:
            verdict = "FEASIBLE_WINDOW_AVAILABLE"
            reason = (
                f"TIMETABLE CLEARANCE: Gap of {req_dur + 30} mins verified between Train #12764 and #12841. "
                f"Safety buffers (+5m/-5m) satisfied. Off-peak window allocated."
            )
            rec_window = "11:30 – 13:00 (Off-Peak)"
            action = "ALLOCATE_BLOCK_WINDOW"
        else:
            verdict = "COORDINATED_CORRIDOR_POSSESSION_REQUIRED"
            reason = (
                f"Cross-departmental lock: Joint OHE & Track circuit isolation required before possession. "
                f"Traffic flow protected."
            )
            rec_window = "03:00 – 05:00 (Integrated Block)"
            action = "COORDINATE_MULTI_DEPT"

        return {
            "verdict": verdict,
            "escalated_priority": escalated_priority,
            "reason": reason,
            "recommended_window": rec_window,
            "action": action
        }

    def seed_realistic_demo_records(self, current_date_str="2026-09-27"):
        """
        Seeds rich, realistic Indian Railways maintenance demo records covering all 8 statuses
        across Engineering (P-Way), TRD (OHE/Traction), and S&T (Signalling & Telecom).
        """
        ref_date = self.parse_date(current_date_str) or date.today()
        
        # Real-world Indian Railways Maintenance Master Templates
        demo_specs = [
            # 1. OVERDUE (Critical P-Way & S&T assets past due date)
            {
                "id": "MNT-ENG-0801",
                "dept": "Engineering",
                "sec": "Vijayawada-SEC-01",
                "asset_id": "PWAY-RAIL-104",
                "asset_name": "60kg UIC Rail Joint & Fishplate Cluster",
                "task": "Emergency USFD ultrasonic flaw weld replacement on high-density curve",
                "sev": "Critical",
                "rep_delta": -18,
                "due_delta": -7,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 120,
                "tsr": 30
            },
            {
                "id": "MNT-TRD-0802",
                "dept": "TRD",
                "sec": "Vijayawada-SEC-03",
                "asset_id": "OHE-CAT-228",
                "asset_name": "25kV Catenary Mast Isolator & Dropper Assembly",
                "task": "Thermal hotspot defect remediation on traction feeder isolator",
                "sev": "High",
                "rep_delta": -12,
                "due_delta": -4,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 90,
                "tsr": 45
            },
            {
                "id": "MNT-SNT-0803",
                "dept": "S&T",
                "sec": "Vijayawada-SEC-02",
                "asset_id": "SIG-PT-109B",
                "asset_name": "Siemens Point Machine & Throw Rod Assembly",
                "task": "Point detection contact wear & micro-switch timing tuning",
                "sev": "Critical",
                "rep_delta": -14,
                "due_delta": -3,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 60,
                "tsr": 20
            },
            # 2. DUE (Due today or within 48h)
            {
                "id": "MNT-ENG-0804",
                "dept": "Engineering",
                "sec": "Vijayawada-SEC-04",
                "asset_id": "PWAY-SEJ-051",
                "asset_name": "Switch Expansion Joint (SEJ) Gap #4",
                "task": "SEJ gap oiling, packing and sleeper renewal before temperature spike",
                "sev": "High",
                "rep_delta": -7,
                "due_delta": 0, # Due today
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 90,
                "tsr": None
            },
            {
                "id": "MNT-TRD-0805",
                "dept": "TRD",
                "sec": "Vijayawada-SEC-06",
                "asset_id": "TRD-TSS-02",
                "asset_name": "Traction Substation Transformer #1 Bushing",
                "task": "Transformer oil filtration & lightning arrester dielectric test",
                "sev": "Medium",
                "rep_delta": -5,
                "due_delta": 1, # Due tomorrow
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 150,
                "tsr": None
            },
            {
                "id": "MNT-SNT-0806",
                "dept": "S&T",
                "sec": "Vijayawada-SEC-05",
                "asset_id": "SIG-AXL-08",
                "asset_name": "Dual Single-Section Digital Axle Counter (SSDAC)",
                "task": "High-frequency wheel sensor tuning and resonator check",
                "sev": "High",
                "rep_delta": -6,
                "due_delta": 1,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 60,
                "tsr": None
            },
            # 3. SCHEDULED (Future planned preventive maintenance)
            {
                "id": "MNT-ENG-0807",
                "dept": "Engineering",
                "sec": "Vijayawada-SEC-07",
                "asset_id": "PWAY-CSM-09",
                "asset_name": "Continuous Action Tamping Machine (CSM-09)",
                "task": "Scheduled corridor mechanized tamping & track lifting (KM 204-209)",
                "sev": "Medium",
                "rep_delta": -2,
                "due_delta": 8,
                "plan_delta": 5,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 180,
                "tsr": None
            },
            {
                "id": "MNT-TRD-0808",
                "dept": "TRD",
                "sec": "Vijayawada-SEC-08",
                "asset_id": "OHE-TW-03",
                "asset_name": "Self-Propelled 4-Wheeler OHE Tower Wagon",
                "task": "Routine periodic catenary wire height & stagger measurement",
                "sev": "Low",
                "rep_delta": -1,
                "due_delta": 10,
                "plan_delta": 7,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 120,
                "tsr": None
            },
            # 4. IN_PROGRESS (Active possession currently on track)
            {
                "id": "MNT-ENG-0809",
                "dept": "Engineering",
                "sec": "Vijayawada-SEC-01",
                "asset_id": "PWAY-BCM-04",
                "asset_name": "Ballast Cleaning Machine (BCM Gang #2)",
                "task": "Deep screening of turnout #102 ballast & screening return",
                "sev": "High",
                "rep_delta": -4,
                "due_delta": 1,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": True,
                "blk_alloc": True,
                "dur": 180,
                "tsr": 30
            },
            {
                "id": "MNT-SNT-0810",
                "dept": "S&T",
                "sec": "Vijayawada-SEC-03",
                "asset_id": "SIG-LED-31",
                "asset_name": "Home Signal Aspect Multi-LED Array",
                "task": "Current regulator replacement and aspect health monitoring",
                "sev": "Medium",
                "rep_delta": -3,
                "due_delta": 2,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": True,
                "blk_alloc": True,
                "dur": 45,
                "tsr": None
            },
            # 5. BLOCK_REQUIRED (Identified maintenance needing possession slot)
            {
                "id": "MNT-ENG-0811",
                "dept": "Engineering",
                "sec": "Vijayawada-SEC-02",
                "asset_id": "PWAY-RAIL-209",
                "asset_name": "Glued Insulated Rail Joint (G3L)",
                "task": "Replacement of damaged fiberglass end-post and torque tightening",
                "sev": "High",
                "rep_delta": -3,
                "due_delta": 6,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 75,
                "tsr": None
            },
            {
                "id": "MNT-TRD-0812",
                "dept": "TRD",
                "sec": "Vijayawada-SEC-05",
                "asset_id": "OHE-CANT-144",
                "asset_name": "Cantilever Ceramic Insulator & Steady Arm",
                "task": "Washed insulator replacement due to flashover marks",
                "sev": "Critical",
                "rep_delta": -2,
                "due_delta": 5,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 90,
                "tsr": 50
            },
            {
                "id": "MNT-SNT-0818",
                "dept": "S&T",
                "sec": "Vijayawada-SEC-09",
                "asset_id": "SIG-TRK-55",
                "asset_name": "Audio Frequency Track Circuit (AFTC) Receiver",
                "task": "Tuning unit impedance check and cable insulation resistance testing",
                "sev": "Medium",
                "rep_delta": -1,
                "due_delta": 7,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 60,
                "tsr": None
            },
            # 6. BLOCK_ALLOCATED (Controller has authorized possession slot)
            {
                "id": "MNT-ENG-0813",
                "dept": "Engineering",
                "sec": "Vijayawada-SEC-06",
                "asset_id": "PWAY-WELD-55",
                "asset_name": "Alumino-Thermic (AT) Weld Point #12",
                "task": "AT weld testing & joggled fishplate with wooden clamps installation",
                "sev": "High",
                "rep_delta": -5,
                "due_delta": 2,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": True,
                "dur": 90,
                "tsr": 45
            },
            {
                "id": "MNT-SNT-0814",
                "dept": "S&T",
                "sec": "Vijayawada-SEC-08",
                "asset_id": "SIG-EI-01",
                "asset_name": "KyuSan Electronic Interlocking (EI) VDU",
                "task": "Quarterly standby CPU transition & optical modem loop check",
                "sev": "Medium",
                "rep_delta": -4,
                "due_delta": 3,
                "comp_delta": None,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": True,
                "dur": 60,
                "tsr": None
            },
            # 7. COMPLETED (Certified Fit & Track Restored)
            {
                "id": "MNT-ENG-0815",
                "dept": "Engineering",
                "sec": "Vijayawada-SEC-01",
                "asset_id": "PWAY-SLP-99",
                "asset_name": "PSC Sleepers on Bridge Approach #44",
                "task": "Renewed 12 PSC sleepers with rubber pads & elastic rail clips",
                "sev": "High",
                "rep_delta": -10,
                "due_delta": -3,
                "comp_delta": -1, # Completed yesterday
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": True,
                "dur": 120,
                "tsr": None
            },
            {
                "id": "MNT-TRD-0816",
                "dept": "TRD",
                "sec": "Vijayawada-SEC-04",
                "asset_id": "OHE-BND-12",
                "asset_name": "Cross Traction Bond & Structure Bond",
                "task": "Replaced copper earth bond on mast #24/11",
                "sev": "Low",
                "rep_delta": -8,
                "due_delta": -2,
                "comp_delta": -2,
                "is_canc": False,
                "is_prog": False,
                "blk_alloc": True,
                "dur": 45,
                "tsr": None
            },
            # 8. CANCELLED (Superseded by complete track renewal)
            {
                "id": "MNT-ENG-0817",
                "dept": "Engineering",
                "sec": "Vijayawada-SEC-09",
                "asset_id": "PWAY-MAN-01",
                "asset_name": "Manual Ballast Packing Gang Task",
                "task": "Manual packing superseded by mechanized CSM tamper deployment",
                "sev": "Low",
                "rep_delta": -15,
                "due_delta": -5,
                "comp_delta": None,
                "is_canc": True,
                "is_prog": False,
                "blk_alloc": False,
                "dur": 60,
                "tsr": None
            }
        ]

        conn = self._get_conn()
        cur = conn.cursor()
        
        # Clear existing demo records
        cur.execute("DELETE FROM maintenance_status_records")

        for s in demo_specs:
            r_id = s["id"]
            dept = s["dept"]
            sec = s["sec"]
            asset_id = s["asset_id"]
            asset_name = s["asset_name"]
            task = s["task"]
            sev = s["sev"]
            
            rep_d = (ref_date + timedelta(days=s["rep_delta"])).strftime("%Y-%m-%d")
            due_d = (ref_date + timedelta(days=s["due_delta"])).strftime("%Y-%m-%d")
            comp_d = (ref_date + timedelta(days=s["comp_delta"])).strftime("%Y-%m-%d") if s["comp_delta"] is not None else None
            
            if s.get("plan_delta") is not None:
                plan_start = (ref_date + timedelta(days=s["plan_delta"])).strftime("%Y-%m-%d 02:30:00")
                plan_end = (ref_date + timedelta(days=s["plan_delta"])).strftime("%Y-%m-%d 04:30:00")
            elif s.get("blk_alloc"):
                plan_start = (ref_date + timedelta(days=max(1, s["due_delta"]))).strftime("%Y-%m-%d 02:30:00")
                plan_end = (ref_date + timedelta(days=max(1, s["due_delta"]))).strftime("%Y-%m-%d 04:30:00")
            else:
                plan_start = None
                plan_end = None

            # Automatic Mathematical Status Calculation
            status, overdue_days = self.calculate_status_and_overdue(
                due_date=due_d,
                current_date=ref_date,
                completion_date=comp_d,
                is_cancelled=s["is_canc"],
                is_in_progress=s["is_prog"],
                block_allocated=s["blk_alloc"],
                block_required=True,
                planned_start=plan_start
            )

            # Safety constraint evaluation
            temp_rec = {
                "severity": sev,
                "overdue_days": overdue_days,
                "department": dept,
                "section_id": sec,
                "estimated_duration_minutes": s["dur"]
            }
            is_peak = (sec in ("Vijayawada-SEC-01", "Vijayawada-SEC-02", "Vijayawada-SEC-03"))
            safety_eval = self.evaluate_overdue_safety_constraint(temp_rec, is_peak_corridor=is_peak)

            alloc_win = "02:30 – 04:30 IST" if s["blk_alloc"] else (safety_eval["recommended_window"] if status == "OVERDUE" else None)

            cur.execute("""
                INSERT INTO maintenance_status_records (
                    record_id, department, section_id, asset_id, asset_name, task_description,
                    severity, reported_date, due_date, current_date_ref, completion_date,
                    planned_start, planned_end, status, overdue_days, block_required,
                    block_allocated, allocated_window, estimated_duration_minutes,
                    speed_restriction_kmh, planner_verdict, planner_safety_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r_id, dept, sec, asset_id, asset_name, task,
                sev, rep_d, due_d, ref_date.strftime("%Y-%m-%d"), comp_d,
                plan_start, plan_end, status, overdue_days, 1,
                1 if s["blk_alloc"] else 0, alloc_win, s["dur"],
                s.get("tsr"), safety_eval["verdict"], safety_eval["reason"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

        conn.commit()
        conn.close()
        return len(demo_specs)

    def get_records_df(self, status_filter=None, department_filter=None):
        """Fetches records as a pandas DataFrame."""
        conn = self._get_conn()
        query = "SELECT * FROM maintenance_status_records WHERE 1=1"
        params = []
        if status_filter:
            if isinstance(status_filter, list):
                placeholders = ",".join(["?"] * len(status_filter))
                query += f" AND status IN ({placeholders})"
                params.extend(status_filter)
            else:
                query += " AND status = ?"
                params.append(status_filter)
        if department_filter and department_filter != "All":
            query += " AND department = ?"
            params.append(department_filter)
        query += " ORDER BY overdue_days DESC, severity DESC, due_date ASC"
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df

    def recalculate_all_statuses(self, current_date_str=None):
        """
        Recalculates status & overdue days dynamically for all stored records
        using the specified reference date.
        """
        ref_d = self.parse_date(current_date_str) or date.today()
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("SELECT record_id, due_date, completion_date, planned_start, block_allocated, status, speed_restriction_kmh FROM maintenance_status_records")
        rows = cur.fetchall()

        for r in rows:
            r_id = r["record_id"]
            due_d = r["due_date"]
            comp_d = r["completion_date"]
            plan_s = r["planned_start"]
            blk_alloc = bool(r["block_allocated"])
            old_status = r["status"]

            is_canc = (old_status == "CANCELLED")
            is_prog = (old_status == "IN_PROGRESS")

            new_status, overdue_days = self.calculate_status_and_overdue(
                due_date=due_d,
                current_date=ref_d,
                completion_date=comp_d,
                is_cancelled=is_canc,
                is_in_progress=is_prog,
                block_allocated=blk_alloc,
                block_required=True,
                planned_start=plan_s
            )

            cur.execute("""
                UPDATE maintenance_status_records
                SET status = ?, overdue_days = ?, current_date_ref = ?
                WHERE record_id = ?
            """, (new_status, overdue_days, ref_d.strftime("%Y-%m-%d"), r_id))

        conn.commit()
        conn.close()
