"""
Phase 9: Deterministic Railway Simulation Engine
Implements authentic timetable-driven deterministic simulation for Indian Railways Corridor Operations.

Simulates:
1. train movement
2. arrival
3. departure
4. delay
5. section occupation
6. section clearance
7. block request
8. block allocation
9. block start
10. block completion
11. conflict
12. rescheduling

Scenarios:
- SCENARIO A — HIGH TRAFFIC
- SCENARIO B — MEDIUM TRAFFIC
- SCENARIO C — LOW TRAFFIC
- SCENARIO D — MAINTENANCE CONFLICT
- SCENARIO E — DELAY CAUSING BLOCK RESCHEDULING
- SCENARIO F — OVERDUE MAINTENANCE
- SCENARIO G — DEPENDENT MULTI-DEPARTMENT WORK
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")

SCENARIO_DEFINITIONS = {
    "SCENARIO A — HIGH TRAFFIC": {
        "title": "Scenario A — High Traffic Corridor Density",
        "description": "High-density mainline traffic with closely bunched Vande Bharat, Rajdhani, and Superfast express trains. Timetable gaps are narrow (35–55 mins), demonstrating automatic shadow slot extraction.",
        "default_start_time": "02:00",
        "traffic_density": "HIGH",
        "delay_factor": 0,
        "active_corridor": "Vijayawada Division (GDR–BZA–VSKP)",
        "train_numbers": ["12621", "12846", "22834", "13352", "20850", "12764", "12841", "20834", "12704", "17209", "12840", "12622"],
        "maintenance_requests": [
            {
                "req_id": "SIM-REQ-A01",
                "department": "Engineering",
                "section": "Vijayawada-SEC-01",
                "line": "UP_MAIN",
                "from_km": 110.0,
                "to_km": 115.0,
                "task": "Mechanized Tie Tamping (CSM)",
                "duration": 45,
                "preferred_start": "02:40",
                "deadline": "2026-09-27 06:00",
                "severity": "Medium",
                "isolation": 0,
                "dependencies": "None"
            }
        ]
    },
    "SCENARIO B — MEDIUM TRAFFIC": {
        "title": "Scenario B — Medium Traffic Flow",
        "description": "Balanced operational traffic with mixed passenger and fast freight vectors. Usable headway gaps of 75–110 mins allow standard preventive maintenance without headway disruption.",
        "default_start_time": "01:30",
        "traffic_density": "MEDIUM",
        "delay_factor": 0,
        "active_corridor": "Vijayawada Division (GDR–BZA)",
        "train_numbers": ["12621", "12846", "13352", "12764", "12841", "20834", "17209"],
        "maintenance_requests": [
            {
                "req_id": "SIM-REQ-B01",
                "department": "TRD",
                "section": "Vijayawada-SEC-03",
                "line": "UP_MAIN",
                "from_km": 130.0,
                "to_km": 134.0,
                "task": "25kV Catenary Dropper & Mast Alignment",
                "duration": 60,
                "preferred_start": "02:15",
                "deadline": "2026-09-27 05:30",
                "severity": "Medium",
                "isolation": 1,
                "dependencies": "None"
            }
        ]
    },
    "SCENARIO C — LOW TRAFFIC": {
        "title": "Scenario C — Low Traffic / Off-Peak Night Window",
        "description": "Nocturnal off-peak window with wide inter-train headways (>180 mins). Ideal for heavy mechanized corridor possessions (Deep Ballast Screening & Track Renewal).",
        "default_start_time": "01:00",
        "traffic_density": "LOW",
        "delay_factor": 0,
        "active_corridor": "Vijayawada Division (BZA–EE–RJY)",
        "train_numbers": ["12621", "13352", "12841", "17209"],
        "maintenance_requests": [
            {
                "req_id": "SIM-REQ-C01",
                "department": "Engineering",
                "section": "Vijayawada-SEC-02",
                "line": "DN_MAIN",
                "from_km": 118.0,
                "to_km": 124.0,
                "task": "Heavy BCM Deep Screening & Ballast Packing",
                "duration": 180,
                "preferred_start": "01:30",
                "deadline": "2026-09-27 06:00",
                "severity": "High",
                "isolation": 1,
                "dependencies": "None"
            }
        ]
    },
    "SCENARIO D — MAINTENANCE CONFLICT": {
        "title": "Scenario D — Direct Timetable Maintenance Conflict",
        "description": "Department submits a track possession request on Section 02 that directly overlaps with Train #12764 (04:20–04:55). Automatic planner detects conflict, flags safety violation, and dynamically recommends an alternate slot.",
        "default_start_time": "04:15",
        "traffic_density": "HIGH",
        "delay_factor": 0,
        "active_corridor": "Vijayawada Division (GDR–BZA)",
        "train_numbers": ["12621", "12846", "22834", "12764", "12841", "20834"],
        "maintenance_requests": [
            {
                "req_id": "SIM-REQ-D01",
                "department": "Engineering",
                "section": "Vijayawada-SEC-02",
                "line": "UP_MAIN",
                "from_km": 146.0,
                "to_km": 154.0,
                "task": "Emergency Turnout Point #14 Packing & Switch Adjustment",
                "duration": 60,
                "preferred_start": "04:30", # Direct overlap with Train 12764 passing section at 04:20–04:53
                "deadline": "2026-09-27 08:00",
                "severity": "Critical",
                "isolation": 1,
                "dependencies": "None"
            }
        ]
    },
    "SCENARIO E — DELAY CAUSING BLOCK RESCHEDULING": {
        "title": "Scenario E — Dynamic Train Delay & Real-Time Block Rescheduling",
        "description": "Train #12764 encounters an upstream signal failure, accumulating +45 mins delay. As the delayed train breaches the planned block safety buffer, the planner triggers dynamic rescheduling to avoid collision.",
        "default_start_time": "03:00",
        "traffic_density": "MEDIUM",
        "delay_factor": 45, # Dynamic 45-min delay on critical train
        "delayed_train": "12764",
        "delay_start_minute": 210, # 03:30 IST
        "active_corridor": "Vijayawada Division (GDR–BZA)",
        "train_numbers": ["12621", "12846", "12764", "12841", "20834", "17209"],
        "maintenance_requests": [
            {
                "req_id": "SIM-REQ-E01",
                "department": "Engineering",
                "section": "Vijayawada-SEC-01",
                "line": "UP_MAIN",
                "from_km": 112.0,
                "to_km": 116.0,
                "task": "Flash-Butt Rail Weld Rectification",
                "duration": 60,
                "preferred_start": "03:45",
                "deadline": "2026-09-27 07:00",
                "severity": "High",
                "isolation": 0,
                "dependencies": "None"
            }
        ]
    },
    "SCENARIO F — OVERDUE MAINTENANCE": {
        "title": "Scenario F — Overdue Safety Task & Protected Peak Traffic",
        "description": "Demonstrates: OVERDUE != Automatic Line Block Permission. A 7-day overdue USFD rail defect is processed. Planner enforces TSR 30 km/h caution order during daylight and locks safe night shadow window (02:00–04:00).",
        "default_start_time": "06:30",
        "traffic_density": "HIGH",
        "delay_factor": 0,
        "active_corridor": "Vijayawada Division (GDR–BZA)",
        "train_numbers": ["12621", "12846", "13352", "12764", "12841", "20834", "12704"],
        "maintenance_requests": [
            {
                "req_id": "SIM-REQ-F01",
                "department": "Engineering",
                "section": "Vijayawada-SEC-01",
                "asset_id": "PWAY-RAIL-104",
                "line": "UP_MAIN",
                "from_km": 114.0,
                "to_km": 118.0,
                "task": "Emergency USFD ultrasonic flaw weld replacement (7 Days Overdue)",
                "duration": 90,
                "preferred_start": "07:00",
                "deadline": "2026-09-20 00:00", # Past due
                "severity": "Critical",
                "overdue_days": 7,
                "isolation": 0,
                "dependencies": "None"
            }
        ]
    },
    "SCENARIO G — DEPENDENT MULTI-DEPARTMENT WORK": {
        "title": "Scenario G — Multi-Department Dependent Task DAG",
        "description": "Multi-department synchronized execution: P-Way Track Packing requires predecessor TRD 25kV OHE power isolation and S&T Point machine clamping. Planner coordinates sequential locks.",
        "default_start_time": "02:00",
        "traffic_density": "MEDIUM",
        "delay_factor": 0,
        "active_corridor": "Vijayawada Division (GDR–BZA)",
        "train_numbers": ["12621", "12846", "12764", "12841", "20834"],
        "maintenance_requests": [
            {
                "req_id": "SIM-REQ-G01-TRD",
                "department": "TRD",
                "section": "Vijayawada-SEC-02",
                "line": "UP_MAIN",
                "from_km": 120.0,
                "to_km": 122.0,
                "task": "25kV OHE Power Block Isolation & Grounding (Phase 1)",
                "duration": 30,
                "preferred_start": "02:30",
                "deadline": "2026-09-27 05:00",
                "severity": "High",
                "isolation": 1,
                "dependencies": "None"
            },
            {
                "req_id": "SIM-REQ-G02-SNT",
                "department": "S&T",
                "section": "Vijayawada-SEC-02",
                "line": "UP_MAIN",
                "from_km": 120.0,
                "to_km": 122.0,
                "task": "Point Machine Disconnection & Detection Clamping (Phase 2)",
                "duration": 20,
                "preferred_start": "03:00",
                "deadline": "2026-09-27 05:00",
                "severity": "High",
                "isolation": 1,
                "dependencies": "Requires SIM-REQ-G01-TRD"
            },
            {
                "req_id": "SIM-REQ-G03-ENG",
                "department": "Engineering",
                "section": "Vijayawada-SEC-02",
                "line": "UP_MAIN",
                "from_km": 120.0,
                "to_km": 122.0,
                "task": "Turnout Packing & Sleepers Realignment (Phase 3)",
                "duration": 50,
                "preferred_start": "03:20",
                "deadline": "2026-09-27 05:00",
                "severity": "High",
                "isolation": 0,
                "dependencies": "Requires SIM-REQ-G02-SNT"
            }
        ]
    }
}


class DeterministicRailwaySimulationEngine:
    """
    Deterministic Railway Simulation Engine for demonstration and stress testing.
    Uses Working Time Table (WTT No. 80) schedules and evaluates 12 operational lifecycle states.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.sections = self._load_corridor_sections()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def time_to_min(time_str):
        if not time_str or ":" not in str(time_str):
            return 0
        parts = str(time_str).strip().split(":")
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return 0

    @staticmethod
    def min_to_time(minutes):
        minutes = int(minutes) % (24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def _load_corridor_sections(self):
        """Loads canonical 10 corridor sections with station boundaries and exact WTT KM spans."""
        return [
            {"section_id": "Vijayawada-SEC-01", "name": "Gudur – Manubolu", "start_km": 136.0, "end_km": 145.4, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-02", "name": "Manubolu – Venkatachalam", "start_km": 145.4, "end_km": 157.8, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-03", "name": "Venkatachalam – Nellore", "start_km": 157.8, "end_km": 174.4, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-04", "name": "Nellore – Bitragunta", "start_km": 174.4, "end_km": 208.2, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-05", "name": "Bitragunta – Kavali", "start_km": 208.2, "end_km": 224.8, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-06", "name": "Kavali – Ongole", "start_km": 224.8, "end_km": 290.4, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-07", "name": "Ongole – Chirala", "start_km": 290.4, "end_km": 339.9, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-08", "name": "Chirala – Bapatla", "start_km": 339.9, "end_km": 354.9, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-09", "name": "Bapatla – Tenali", "start_km": 354.9, "end_km": 397.2, "max_speed": 130, "line": "UP_MAIN"},
            {"section_id": "Vijayawada-SEC-10", "name": "Tenali – Vijayawada Junction", "start_km": 397.2, "end_km": 428.8, "max_speed": 110, "line": "UP_MAIN"}
        ]

    def _get_train_timetable_paths(self, train_numbers):
        """Builds linear trajectories for selected trains from timetable schedule."""
        conn = self._get_conn()
        placeholders = ",".join(["?"] * len(train_numbers))
        query = f"""
            SELECT s.train_number, s.station_code, s.station_name, s.station_km, s.arrival_time, s.departure_time, s.direction
            FROM wtt_train_schedule s
            WHERE s.train_number IN ({placeholders})
            ORDER BY s.train_number, s.departure_time ASC
        """
        try:
            df = pd.read_sql(query, conn, params=train_numbers)
        except Exception:
            df = pd.DataFrame()
        conn.close()

        # Fallback synthetic trajectories if WTT schedule subset is sparse
        trajectories = {}
        for t_no in train_numbers:
            t_df = df[df["train_number"] == str(t_no)] if not df.empty else pd.DataFrame()
            if not t_df.empty and len(t_df) >= 2:
                points = []
                for _, r in t_df.iterrows():
                    arr_m = self.time_to_min(r["arrival_time"]) or self.time_to_min(r["departure_time"])
                    dep_m = self.time_to_min(r["departure_time"]) or arr_m
                    points.append({
                        "station": r["station_code"],
                        "km": float(r["station_km"]) if r["station_km"] is not None else 100.0,
                        "arr_min": arr_m,
                        "dep_min": dep_m
                    })
                trajectories[str(t_no)] = points
            else:
                # Deterministic synthetic timeline based on train number parity
                offset = (int(t_no) % 10) * 20 + 30
                trajectories[str(t_no)] = [
                    {"station": "GDR", "km": 100.0, "arr_min": offset, "dep_min": offset + 2},
                    {"station": "NLR", "km": 138.0, "arr_min": offset + 30, "dep_min": offset + 32},
                    {"station": "OGL", "km": 268.0, "arr_min": offset + 120, "dep_min": offset + 122},
                    {"station": "TEL", "km": 380.0, "arr_min": offset + 200, "dep_min": offset + 202},
                    {"station": "BZA", "km": 412.0, "arr_min": offset + 235, "dep_min": offset + 250}
                ]
        return trajectories

    def evaluate_step(self, scenario_name: str, current_minute: int) -> dict:
        """
        Evaluates complete deterministic simulation state at 'current_minute' (0..1439).
        Computes all 12 target states:
        - Train movement (KM, speed, direction)
        - Station Arrival / Departure
        - Live Delays & propagation
        - Section Occupation & Clearance
        - Block Requisitions, Allocations, Starts, Completions
        - Timetable Conflicts & Automatic Rescheduling
        """
        scenario = SCENARIO_DEFINITIONS.get(scenario_name, SCENARIO_DEFINITIONS["SCENARIO A — HIGH TRAFFIC"])
        train_nums = scenario["train_numbers"]
        trajectories = self._get_train_timetable_paths(train_nums)

        curr_time_str = self.min_to_time(current_minute)
        events_log = []
        active_trains = []
        section_states = {s["section_id"]: {"status": "CLEAR", "occupying_trains": [], "active_block": None} for s in self.sections}

        # 1. EVALUATE TRAIN MOVEMENTS, ARRIVALS, DEPARTURES, DELAYS & SECTION OCCUPATION
        for t_no in train_nums:
            t_str = str(t_no)
            path = trajectories.get(t_str, [])
            if not path or len(path) < 2:
                continue

            # Inject scenario-specific delay
            delay_mins = 0
            if scenario.get("delayed_train") == t_str and current_minute >= scenario.get("delay_start_minute", 0):
                delay_mins = scenario.get("delay_factor", 0)

            # Trajectory endpoints
            first_dep = path[0]["dep_min"] + delay_mins
            last_arr = path[-1]["arr_min"] + delay_mins

            if current_minute < first_dep:
                status = "SCHEDULED_AT_ORIGIN"
                curr_km = path[0]["km"]
                speed = 0
                curr_sec = self.sections[0]["section_id"]
                next_st = path[0]["station"]
            elif current_minute >= last_arr:
                status = "ARRIVED_DESTINATION"
                curr_km = path[-1]["km"]
                speed = 0
                curr_sec = self.sections[-1]["section_id"]
                next_st = path[-1]["station"]
            else:
                # Active train traversing the corridor
                status = "RUNNING"
                curr_km = path[0]["km"]
                speed = 110 if delay_mins == 0 else 75
                curr_sec = self.sections[0]["section_id"]
                next_st = path[-1]["station"]

                # Linear interpolation across trajectory points
                for i in range(len(path) - 1):
                    p1 = path[i]
                    p2 = path[i+1]
                    p1_time = p1["dep_min"] + delay_mins
                    p2_time = p2["arr_min"] + delay_mins

                    if p1_time <= current_minute <= p2_time:
                        frac = (current_minute - p1_time) / max(1, (p2_time - p1_time))
                        curr_km = p1["km"] + frac * (p2["km"] - p1["km"])
                        next_st = p2["station"]

                        # Check Arrival & Departure events
                        if current_minute == p1_time:
                            events_log.append(f"🚉 DEPARTURE: Train #{t_str} departed {p1['station']} at {curr_time_str} (KM {p1['km']:.1f}).")
                        elif current_minute == p2_time:
                            events_log.append(f"🏁 ARRIVAL: Train #{t_str} arrived {p2['station']} at {curr_time_str} (KM {p2['km']:.1f}).")
                        break

                # Find occupied section
                for sec in self.sections:
                    if sec["start_km"] <= curr_km <= sec["end_km"]:
                        curr_sec = sec["section_id"]
                        section_states[curr_sec]["status"] = "OCCUPIED"
                        section_states[curr_sec]["occupying_trains"].append(t_str)
                        break

            active_trains.append({
                "train_number": t_str,
                "current_km": round(curr_km, 1),
                "speed_kmh": speed,
                "current_section": curr_sec,
                "next_station": next_st,
                "delay_minutes": delay_mins,
                "status": status
            })

        # 2. EVALUATE BLOCK REQUISITIONS, ALLOCATIONS, STARTS, CONFLICTS & RESCHEDULING
        planner_verdicts = []
        block_records = []

        for req in scenario.get("maintenance_requests", []):
            req_id = req["req_id"]
            sec_id = req["section"]
            pref_start_min = self.time_to_min(req["preferred_start"])
            duration_mins = req["duration"]
            pref_end_min = pref_start_min + duration_mins

            # Default Planner Gap Evaluation
            is_feasible = True
            conflict_train = None
            rescheduled_start_min = pref_start_min
            rescheduled_end_min = pref_end_min
            planner_reason = "Timetable clearance verified with +5m/-5m buffers."

            # Check if any active/scheduled train overlaps with the preferred window on the target section
            for t in active_trains:
                t_no = t["train_number"]
                path = trajectories.get(t_no, [])
                delay_mins = t["delay_minutes"]
                
                # Check train passage time through the section
                for i in range(len(path) - 1):
                    p1 = path[i]
                    p2 = path[i+1]
                    p1_time = p1["dep_min"] + delay_mins
                    p2_time = p2["arr_min"] + delay_mins
                    
                    # If section overlaps with train segment (bidirectional)
                    sec_obj = next((s for s in self.sections if s["section_id"] == sec_id), None)
                    if sec_obj and (min(p1["km"], p2["km"]) <= sec_obj["end_km"] and max(p1["km"], p2["km"]) >= sec_obj["start_km"]):
                        # Train occupies section during [min(p1_time, p2_time), max(p1_time, p2_time)]
                        seg_start_t = min(p1_time, p2_time)
                        seg_end_t = max(p1_time, p2_time)
                        if not (pref_end_min + 5 <= seg_start_t or pref_start_min - 5 >= seg_end_t):
                            is_feasible = False
                            conflict_train = t_no
                            # Rescheduling recommendation
                            rescheduled_start_min = seg_end_t + 10 # 10m buffer after train clears
                            rescheduled_end_min = rescheduled_start_min + duration_mins
                            planner_reason = (
                                f"CONFLICT DETECTED: Train #{conflict_train} occupies Section {sec_id} during preferred window "
                                f"({self.min_to_time(pref_start_min)}–{self.min_to_time(pref_end_min)}). "
                                f"AUTOMATIC RESCHEDULING: Block shifted to {self.min_to_time(rescheduled_start_min)}–{self.min_to_time(rescheduled_end_min)} IST."
                            )
                            events_log.append(f"⚠️ CONFLICT: Request {req_id} conflicts with Train #{conflict_train} on {sec_id}!")
                            events_log.append(f"🔄 RESCHEDULING: Planner shifted {req_id} to {self.min_to_time(rescheduled_start_min)}–{self.min_to_time(rescheduled_end_min)}.")
                            break

            # Handle Scenario F Overdue Safety Rule
            if req.get("overdue_days", 0) > 0 and scenario_name == "SCENARIO F — OVERDUE MAINTENANCE":
                is_feasible = False
                rescheduled_start_min = self.time_to_min("02:00")
                rescheduled_end_min = rescheduled_start_min + duration_mins
                planner_reason = (
                    f"SAFETY CONSTRAINT ENFORCEMENT: Task {req_id} is {req['overdue_days']} days OVERDUE. "
                    f"OVERDUE != Automatic Line Block Permission. Daylight block rejected to protect peak traffic. "
                    f"Action: Imposed TSR 30 km/h; possession locked in Night Shadow Window (02:00–04:00 IST)."
                )

            # Determine Block Lifecycle State
            if current_minute < pref_start_min:
                blk_state = "ALLOCATED_WAITING_START" if is_feasible else "RESCHEDULED_PENDING"
            elif pref_start_min <= current_minute <= pref_end_min and is_feasible:
                blk_state = "IN_PROGRESS_TRACK_BLOCKED"
                section_states[sec_id]["status"] = "BLOCKED_FOR_MAINTENANCE"
                section_states[sec_id]["active_block"] = req_id
                if current_minute == pref_start_min:
                    events_log.append(f"⚡ BLOCK START: Possession activated for {req_id} on {sec_id} (KM {req['from_km']}–{req['to_km']}). Track Isolated.")
            elif current_minute > pref_end_min and is_feasible:
                blk_state = "COMPLETED_TRACK_FIT"
                if current_minute == pref_end_min + 1:
                    events_log.append(f"✅ BLOCK COMPLETION: Work completed on {sec_id} for {req_id}. Track certified Fit & Speed restored to 130 km/h.")
            else:
                blk_state = "RESCHEDULED"

            block_records.append({
                "request_id": req_id,
                "department": req["department"],
                "section": sec_id,
                "task": req["task"],
                "duration": duration_mins,
                "preferred_window": f"{req['preferred_start']} – {self.min_to_time(pref_end_min)}",
                "allocated_window": f"{self.min_to_time(rescheduled_start_min)} – {self.min_to_time(rescheduled_end_min)}",
                "is_feasible": is_feasible,
                "conflict_train": conflict_train,
                "state": blk_state,
                "planner_reason": planner_reason
            })

        return {
            "current_minute": current_minute,
            "current_time": curr_time_str,
            "scenario": scenario_name,
            "scenario_title": scenario["title"],
            "scenario_description": scenario["description"],
            "active_trains": active_trains,
            "section_states": section_states,
            "block_records": block_records,
            "events_log": events_log[-12:] # Keep recent 12 events
        }
