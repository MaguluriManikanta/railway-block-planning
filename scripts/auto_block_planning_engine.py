"""
Phase 5: Automatic Block Planning Engine
Implements the full 16-Step Block Planning Algorithm, recommendation generator,
and Controller Decision Support Layer with persistent audit logging.
"""

import os
import sys
import sqlite3
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
        sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")


# -----------------------------------------------------------------------------
# 1. 16-STEP AUTOMATIC BLOCK PLANNING ENGINE
# -----------------------------------------------------------------------------
class AutomaticBlockPlanningEngine:
    """
    Executes the 16-step automatic block planning algorithm combining:
    - Working Time Table (WTT No. 80) schedules
    - Live / Simulated train vectors
    - Dynamic safety buffer calculations
    - Cross-departmental dependency & isolation checks
    - Resource & active block concurrency constraints
    """

    def __init__(self, db_path=DB_PATH, default_buffer_before=5, default_buffer_after=5):
        self.db_path = db_path
        self.buffer_before = default_buffer_before
        self.buffer_after = default_buffer_after

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30.0)

    @staticmethod
    def _time_to_minutes(t_str):
        if not t_str or ":" not in str(t_str):
            return None
        parts = str(t_str).strip().split(":")
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _minutes_to_time(mins):
        if mins is None:
            return "--:--"
        mins = mins % (24 * 60)
        return f"{int(mins // 60):02d}:{int(mins % 60):02d}"

    def plan_single_request(self, request: dict, active_scenario: str = "HIGH_TRAFFIC", active_blocks: list = None, busy_resources: list = None) -> dict:
        """
        Executes the 16-step algorithm for a single block request.
        """
        active_blocks = active_blocks or []
        busy_resources = busy_resources or []
        req_id = request.get("request_id", "REQ-UNKNOWN")
        
        # STEP 1: Identify affected section
        section = request.get("section", "GDR-BZA-DN")

        # STEP 2: Identify affected KM range
        from_km = float(request.get("from_km", 0.0))
        to_km = float(request.get("to_km", from_km + 5.0))
        min_km = min(from_km, to_km)
        max_km = max(from_km, to_km)

        # STEP 3: Identify affected line/track & direction
        line = request.get("line", "DOWN Line")
        direction = request.get("direction", "DOWN")
        dept = request.get("department", "ENGINEERING")
        res = request.get("required_resource", "Maintenance Crew")
        req_dur = int(request.get("required_duration", 60))
        min_dur = int(request.get("minimum_duration", req_dur))
        pref_start_str = str(request.get("preferred_start", "02:30"))
        pref_min = self._time_to_minutes(pref_start_str) or 150 # default 02:30
        dependency_info = str(request.get("dependency", "None"))
        isolation_req = bool(request.get("isolation_required", False))

        # STEP 4: Find all trains that will occupy or cross the affected area
        conn = self._get_conn()
        
        # Get scenario trains if active
        query_trains = """
            SELECT train_number FROM prototype_trains WHERE scenario = ?
        """
        scenario_trains = [r[0] for r in conn.execute(query_trains, (active_scenario,)).fetchall()]
        if not scenario_trains:
            scenario_trains = [r[0] for r in conn.execute("SELECT DISTINCT train_number FROM wtt_train_schedule").fetchall()]

        placeholders = ",".join(["?"] * len(scenario_trains))
        sched_query = f"""
            SELECT s.train_number, s.direction, s.station_code, s.station_name, s.station_km,
                   s.arrival_time, s.departure_time, s.pass_or_skip
            FROM wtt_train_schedule s
            WHERE s.train_number IN ({placeholders})
              AND (s.direction = ? OR ? = 'BIDIRECTIONAL')
            ORDER BY s.train_number, s.departure_time ASC
        """
        df_sched = pd.read_sql(sched_query, conn, params=(*scenario_trains, direction, direction))
        conn.close()

        # STEP 5: Calculate chronological train movements through the KM range
        train_movements = []
        for train_no, grp in df_sched.groupby("train_number"):
            # Check if train path intersects with KM range
            grp_km = grp["station_km"].dropna()
            if grp_km.empty:
                continue
            
            # Find closest station
            grp = grp.copy()
            grp["km_dist"] = grp["station_km"].apply(lambda k: 0 if min_km <= k <= max_km else min(abs(k - min_km), abs(k - max_km)))
            nearest = grp.sort_values("km_dist").iloc[0]
            
            arr_m = self._time_to_minutes(nearest["arrival_time"])
            dep_m = self._time_to_minutes(nearest["departure_time"])
            if dep_m is not None:
                train_movements.append({
                    "train_number": train_no,
                    "direction": nearest["direction"],
                    "station_code": nearest["station_code"],
                    "station_km": nearest["station_km"],
                    "entry_min": arr_m or dep_m,
                    "clear_min": dep_m,
                    "clear_time": nearest["departure_time"]
                })

        train_movements.sort(key=lambda x: x["entry_min"])

        # STEP 6: Find gaps between consecutive train movements
        candidate_gaps = []
        for i in range(len(train_movements) - 1):
            t_prev = train_movements[i]
            t_next = train_movements[i+1]

            # STEP 7: Calculate RAW_GAP = NEXT_TRAIN_ENTRY - PREVIOUS_TRAIN_CLEARANCE
            raw_gap = t_next["entry_min"] - t_prev["clear_min"]
            if raw_gap <= 0:
                raw_gap += 24 * 60 # overnight wrap

            # STEP 8: Calculate USABLE_GAP = RAW_GAP - SAFETY_BUFFER_BEFORE - SAFETY_BUFFER_AFTER
            usable_gap = raw_gap - self.buffer_before - self.buffer_after

            # STEP 9: Check USABLE_GAP >= REQUIRED_BLOCK_DURATION (or MINIMUM_DURATION)
            if usable_gap >= min_dur:
                safe_start_min = (t_prev["clear_min"] + self.buffer_before) % (24 * 60)
                safe_end_min = (safe_start_min + min(req_dur, usable_gap)) % (24 * 60)
                candidate_gaps.append({
                    "prev_train": t_prev["train_number"],
                    "prev_train_clear": t_prev["clear_time"],
                    "next_train": t_next["train_number"],
                    "next_train_entry": t_next["clear_time"],
                    "raw_gap": raw_gap,
                    "usable_gap": usable_gap,
                    "safe_start_min": safe_start_min,
                    "safe_end_min": safe_end_min,
                    "safe_start_str": self._minutes_to_time(safe_start_min),
                    "safe_end_str": self._minutes_to_time(safe_end_min),
                    "diff_from_pref": abs(safe_start_min - pref_min)
                })

        # STEP 10: Check dependency constraints
        dependency_status = "Satisfied"
        conflicts = []
        if dependency_info.lower() != "none" and "independent" not in dependency_info.lower():
            if "requires" in dependency_info.lower() and "completion" not in dependency_info.lower():
                dependency_status = "Unsatisfied"
                conflicts.append(f"DEPENDENCY CONFLICT ({dependency_info})")

        # STEP 11: Check isolation requirements
        isolation_status = "Granted / Ready" if not isolation_req else "Permit to Work Required (25kV OHE Disconnection)"

        # STEP 12: Check existing blocks
        existing_block_conflict = False
        for ab in active_blocks:
            if ab.get("section") == section and ab.get("line") == line:
                existing_block_conflict = True
                conflicts.append(f"OVERLAPPING BLOCK CONFLICT with {ab.get('block_id')}")

        # STEP 13: Check resource availability
        resource_status = "Available"
        if res in busy_resources:
            resource_status = "Resource Busy"
            conflicts.append(f"RESOURCE CONFLICT ({res} in use)")

        # STEP 14: Generate candidate windows
        candidate_gaps.sort(key=lambda x: x["diff_from_pref"])

        # STEP 15: Reject unsafe candidates
        safe_candidates = [g for g in candidate_gaps if g["usable_gap"] >= min_dur]

        # STEP 16: Generate recommended window
        if safe_candidates and not conflicts:
            best_win = safe_candidates[0]
            feasibility = "FEASIBLE"
            actual_grant_dur = min(req_dur, best_win["usable_gap"])
            grant_end_str = self._minutes_to_time(best_win["safe_start_min"] + actual_grant_dur)
            rec_start = best_win["safe_start_str"]
            rec_end = grant_end_str
            reason = (
                f"Feasible window verified: {rec_start}–{rec_end} ({actual_grant_dur}m granted within {best_win['raw_gap']}m gap). "
                f"Previous Train {best_win['prev_train']} clears at {best_win['prev_train_clear']} (+{self.buffer_before}m buffer). "
                f"Next Train {best_win['next_train']} enters at {best_win['next_train_entry']} (-{self.buffer_after}m buffer). "
                f"Safety buffers and operational dependencies fully satisfied."
            )
        else:
            feasibility = "REJECTED"
            rec_start = "None"
            rec_end = "None"
            best_win = candidate_gaps[0] if candidate_gaps else None
            primary_reason = conflicts[0] if conflicts else "No train-free interval of required duration available."
            reason = (
                f"NOT FEASIBLE: {primary_reason}. "
                f"Requested duration {req_dur}m (Min: {min_dur}m) exceeds available safe interval between scheduled trains on {section}."
            )

        return {
            "block_request_id": req_id,
            "department": dept,
            "request_type": request.get("request_type"),
            "section": section,
            "line": line,
            "recommended_start": rec_start,
            "recommended_end": rec_end,
            "previous_train": best_win["prev_train"] if best_win else "N/A",
            "previous_train_clear_time": best_win["prev_train_clear"] if best_win else "N/A",
            "next_train": best_win["next_train"] if best_win else "N/A",
            "next_train_entry_time": best_win["next_train_entry"] if best_win else "N/A",
            "raw_gap": best_win["raw_gap"] if best_win else 0,
            "safety_buffer": self.buffer_before + self.buffer_after,
            "usable_gap": best_win["usable_gap"] if best_win else 0,
            "required_duration": req_dur,
            "dependency_status": dependency_status,
            "isolation_status": isolation_status,
            "resource_status": resource_status,
            "conflicts": ", ".join(conflicts) if conflicts else "None",
            "feasibility": feasibility,
            "reason": reason
        }

    def plan_all_requests(self, active_scenario: str = "HIGH_TRAFFIC") -> pd.DataFrame:
        """Processes all block requests and returns a consolidated recommendation DataFrame."""
        df_reqs = pd.read_csv(os.path.join(DATA_DIR, "block_requests.csv"))
        recommendations = []
        for _, r in df_reqs.iterrows():
            rec = self.plan_single_request(r.to_dict(), active_scenario=active_scenario)
            recommendations.append(rec)
        return pd.DataFrame(recommendations)


# -----------------------------------------------------------------------------
# 2. CONTROLLER DECISION & AUDIT LAYER
# -----------------------------------------------------------------------------
class ControllerDecisionEngine:
    """
    Manages Controller decisions: APPROVE, MODIFY, REJECT, OVERRIDE
    and ensures strict persistence in block_decision_history with mandatory audit trails.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS block_decision_history (
            decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            recommendation TEXT,
            controller_decision TEXT NOT NULL, -- APPROVE / MODIFY / REJECT / OVERRIDE
            selected_start TEXT,
            selected_end TEXT,
            override_reason TEXT,
            timestamp TEXT NOT NULL,
            controller_id TEXT NOT NULL
        )
        """)
        conn.commit()
        conn.close()

    def record_decision(self, request_id: str, recommendation: str, decision: str, selected_start: str = None, selected_end: str = None, override_reason: str = None, controller_id: str = "CONTROLLER-BZA-01") -> dict:
        """
        Records a controller decision with validation.
        """
        decision_upper = decision.strip().upper()
        if decision_upper not in ["APPROVE", "MODIFY", "REJECT", "OVERRIDE"]:
            raise ValueError(f"Invalid decision '{decision}'. Must be one of APPROVE, MODIFY, REJECT, OVERRIDE")

        if decision_upper in ["MODIFY", "OVERRIDE"] and not override_reason:
            raise ValueError("Mandatory override_reason is required when modifying or overriding recommendation.")

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO block_decision_history 
            (request_id, recommendation, controller_decision, selected_start, selected_end, override_reason, timestamp, controller_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (request_id, recommendation, decision_upper, selected_start, selected_end, override_reason or "Approved as recommended", ts, controller_id))
        
        # Also sync status in block_requests_v2 table
        status_map = {
            "APPROVE": "Approved / Scheduled",
            "MODIFY": "Modified & Approved",
            "REJECT": "Rejected by Controller",
            "OVERRIDE": "Controller Override Active"
        }
        cur.execute("UPDATE block_requests_v2 SET status = ? WHERE request_id = ?", (status_map[decision_upper], request_id))
        conn.commit()
        conn.close()

        print(f"✅ Recorded Controller Decision [{decision_upper}] for {request_id} by {controller_id} at {ts}.")
        return {
            "request_id": request_id,
            "decision": decision_upper,
            "controller_id": controller_id,
            "timestamp": ts,
            "status": "RECORDED"
        }

    def get_decision_history(self) -> pd.DataFrame:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        df = pd.read_sql("SELECT * FROM block_decision_history ORDER BY decision_id DESC", conn)
        conn.close()
        return df


# -----------------------------------------------------------------------------
# 3. TEST PIPELINE & BATCH EVALUATION
# -----------------------------------------------------------------------------
def run_phase_5_tests():
    print("🚀 Running Automatic Block Planning Engine (Phase 5)...")
    engine = AutomaticBlockPlanningEngine()
    df_recs = engine.plan_all_requests(active_scenario="HIGH_TRAFFIC")

    # Save to CSV and SQLite
    out_csv = os.path.join(DATA_DIR, "automatic_block_recommendations.csv")
    df_recs.to_csv(out_csv, index=False)
    print(f"✅ Generated {out_csv} with {len(df_recs)} structured recommendations.")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    df_recs.to_sql("automatic_block_recommendations", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    print("✅ Ingested table 'automatic_block_recommendations' into railway.db.")

    # Test Controller Decision Support Layer
    controller = ControllerDecisionEngine()
    print("\n🔹 Testing Controller Decision Support Actions...")
    
    # 1. Approve
    sample_rec = df_recs.iloc[0]
    controller.record_decision(
        request_id=sample_rec["block_request_id"],
        recommendation=sample_rec["reason"],
        decision="APPROVE",
        selected_start=sample_rec["recommended_start"],
        selected_end=sample_rec["recommended_end"],
        controller_id="CONTROLLER-BZA-01"
    )

    # 2. Override with reason
    sample_rec_rej = df_recs[df_recs["feasibility"] == "REJECTED"].iloc[0]
    controller.record_decision(
        request_id=sample_rec_rej["block_request_id"],
        recommendation=sample_rec_rej["reason"],
        decision="OVERRIDE",
        selected_start="02:00",
        selected_end="03:00",
        override_reason="Emergency critical weld repair prioritized by Sr. DOM authority; freight regulation authorized.",
        controller_id="SR-DOM-BZA"
    )

    history = controller.get_decision_history()
    print(f"✅ Controller Decision History Logged: {len(history)} decisions recorded.")

    print("\n================================================================================")
    print("📋 PHASE 5 AUTOMATIC BLOCK PLANNING ENGINE VERIFICATION")
    print("================================================================================")
    print(f"• Total Evaluated Requests  : {len(df_recs)}")
    print(f"• Feasible Recommendations  : {len(df_recs[df_recs['feasibility'] == 'FEASIBLE'])}")
    print(f"• Infeasible Rejections     : {len(df_recs[df_recs['feasibility'] == 'REJECTED'])}")
    print("\n🔹 SAMPLE RECOMMENDATION OBJECT:")
    print(json.dumps(df_recs.iloc[0].to_dict(), indent=2))
    print("================================================================================\n")


if __name__ == "__main__":
    run_phase_5_tests()
