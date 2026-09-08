"""
Block Scheduling Optimizer using Google OR-Tools CP-SAT.

Problem: assign maintenance tasks (defects) to available corridor time slots
such that:
  HARD constraints:
    - each slot can hold at most one task (no department clashes)
    - a task can only go in a slot on the same section
    - a task's estimated duration must fit within the slot's duration
  OBJECTIVE:
    - maximize total priority score of tasks that get scheduled
"""

import sqlite3
import pandas as pd
from ortools.sat.python import cp_model
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")


def _time_to_minutes(t_str):
    """Convert 'HH:MM' string to minutes since midnight. Returns None if unparseable."""
    try:
        h, m = t_str.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def filter_slots_against_timetable(slots: pd.DataFrame, timetable: pd.DataFrame) -> pd.DataFrame:
    """
    HARD CONSTRAINT: remove any corridor slot whose time window overlaps a
    scheduled train's departure time on the same section. This is what makes
    the train timetable an explicit, enforced rule rather than an assumption
    baked into how slots happened to be generated.
    """
    if timetable.empty:
        return slots

    # Pre-group train departure times (in minutes) by section for fast lookup
    tt = timetable.copy()
    tt["dep_minutes"] = tt["departure_time"].apply(_time_to_minutes)
    tt = tt.dropna(subset=["dep_minutes"])
    dep_by_section = tt.groupby("section_id")["dep_minutes"].apply(list).to_dict()

    def slot_is_clear(row):
        # Night blocks are pre-cleared low-traffic corridor windows already granted
        # by Control Office specifically to avoid train movement — only Day/Traffic
        # blocks need an explicit per-train check against the timetable.
        if row.get("slot_type") == "Night block":
            return True

        deps = dep_by_section.get(row["section_id"], [])
        if not deps:
            return True
        start = _time_to_minutes(row["start_time"])
        end = _time_to_minutes(row["end_time"])
        if start is None or end is None:
            return True
        # Handle overnight slots that wrap past midnight (e.g. 23:00 - 02:00)
        if end <= start:
            end += 24 * 60
        for dep in deps:
            dep_adj = dep if dep >= start else dep + 24 * 60
            if start <= dep_adj <= end:
                return False  # a train departs during this slot -> block it
        return True

    before = len(slots)
    clear_mask = slots.apply(slot_is_clear, axis=1)
    filtered = slots[clear_mask].copy()
    excluded = before - len(filtered)
    print(f"Timetable constraint: excluded {excluded} of {before} slots "
          f"that overlapped a scheduled train departure.")
    return filtered


def filter_slots_against_locked_schedules(slots: pd.DataFrame, conn: sqlite3.Connection) -> pd.DataFrame:
    """
    HARD CONSTRAINT: remove any corridor slot that overlaps an existing
    locked or controller-overridden schedule block on the same section.
    """
    locked = pd.read_sql(
        "SELECT section_id, planned_start, planned_end FROM schedule WHERE status = 'locked' OR decided_by IN ('controller_override', 'controller_emergency')",
        conn
    )
    if locked.empty or slots.empty:
        return slots

    locked["start_dt"] = pd.to_datetime(locked["planned_start"], errors="coerce")
    locked["end_dt"] = pd.to_datetime(locked["planned_end"], errors="coerce")
    locked = locked.dropna(subset=["start_dt", "end_dt"])

    def slot_is_unlocked(row):
        sec = row["section_id"]
        try:
            s_start = pd.to_datetime(f"{row['date']} {row['start_time']}")
            s_end = pd.to_datetime(f"{row['date']} {row['end_time']}")
        except Exception:
            return True

        sec_locked = locked[locked["section_id"] == sec]
        for _, l in sec_locked.iterrows():
            if (s_start < l["end_dt"]) and (s_end > l["start_dt"]):
                return False
        return True

    before = len(slots)
    filtered = slots[slots.apply(slot_is_unlocked, axis=1)].copy()
    excluded = before - len(filtered)
    print(f"Locked schedule constraint: excluded {excluded} of {before} slots overlapping controller overrides.")
    return filtered


def run_optimizer(horizon="weekly", horizon_days=7, max_tasks=400, max_slots=400):
    conn = sqlite3.connect(DB_PATH)

    defects = pd.read_sql(
        "SELECT * FROM defects WHERE status = 'Open' ORDER BY priority_score DESC LIMIT ?",
        conn, params=(max_tasks,)
    )
    slots = pd.read_sql(
        "SELECT * FROM corridor_slots WHERE is_available = 1 LIMIT ?",
        conn, params=(max_slots,)
    )
    timetable = pd.read_sql("SELECT * FROM train_timetable", conn)

    if horizon == "monthly":
        horizon_days = 30 if horizon_days == 7 else horizon_days
        max_tasks = 1000 if max_tasks == 400 else max_tasks
        max_slots = 1000 if max_slots == 400 else max_slots

    slots = slots[pd.to_datetime(slots["date"]) <= pd.to_datetime(slots["date"]).min() + pd.Timedelta(days=horizon_days)]

    # Enforce the train timetable and locked overrides as hard constraints
    slots = filter_slots_against_timetable(slots, timetable)
    slots = filter_slots_against_locked_schedules(slots, conn)

    if defects.empty or slots.empty:
        print("No defects or slots available to schedule.")
        conn.close()
        return pd.DataFrame()

    defects["priority_score"] = pd.to_numeric(defects["priority_score"], errors="coerce").fillna(5.0)
    defects["estimated_duration_hours"] = pd.to_numeric(defects["estimated_duration_hours"], errors="coerce").fillna(2.0)
    slots["duration_hours"] = pd.to_numeric(slots["duration_hours"], errors="coerce").fillna(2.0)

    model = cp_model.CpModel()

    # Decision variables: assign[i][j] = 1 if defect i is assigned to slot j
    assign = {}
    valid_pairs = []
    for i, d in defects.iterrows():
        for j, s in slots.iterrows():
            # Hard constraint: same section, and task must fit in slot duration
            if d["section_id"] == s["section_id"] and d["estimated_duration_hours"] <= s["duration_hours"]:
                assign[(i, j)] = model.NewBoolVar(f"assign_{i}_{j}")
                valid_pairs.append((i, j))

    if not valid_pairs:
        print("No valid (defect, slot) pairs found — check section matching.")
        return pd.DataFrame()

    # Constraint: each defect assigned to at most 1 slot
    for i in defects.index:
        related = [assign[(i, j)] for (ii, j) in valid_pairs if ii == i]
        if related:
            model.Add(sum(related) <= 1)

    # Constraint: each slot used by at most 1 defect (no department clashes)
    for j in slots.index:
        related = [assign[(i, j)] for (i, jj) in valid_pairs if jj == j]
        if related:
            model.Add(sum(related) <= 1)

    # Objective: maximize total priority score of scheduled tasks
    objective_terms = []
    for (i, j) in valid_pairs:
        score = int(defects.loc[i, "priority_score"] * 100)  # scale for integer solver
        objective_terms.append(score * assign[(i, j)])
    model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    results = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (i, j) in valid_pairs:
            if solver.Value(assign[(i, j)]) == 1:
                d = defects.loc[i]
                s = slots.loc[j]
                results.append({
                    "defect_id": d["defect_id"],
                    "slot_id": s["slot_id"],
                    "section_id": d["section_id"],
                    "department": d["department"],
                    "planned_start": f"{s['date']} {s['start_time']}",
                    "planned_end": f"{s['date']} {s['end_time']}",
                    "horizon": horizon,
                    "status": "planned",
                    "decided_by": "optimizer",
                })

    result_df = pd.DataFrame(results)
    print(f"Optimizer status: {solver.StatusName(status)}")
    print(f"Scheduled {len(result_df)} of {len(defects)} candidate tasks "
          f"into {len(slots)} available slots ({horizon} horizon).")

    if not result_df.empty:
        result_df.to_sql("schedule", conn, if_exists="append", index=False)

        # mark scheduled defects and used slots
        cur = conn.cursor()
        for _, row in result_df.iterrows():
            cur.execute("UPDATE defects SET status='Scheduled' WHERE defect_id=?", (row["defect_id"],))
            cur.execute("UPDATE corridor_slots SET is_available=0 WHERE slot_id=?", (row["slot_id"],))
        conn.commit()

    conn.close()
    return result_df


if __name__ == "__main__":
    weekly = run_optimizer(horizon="weekly", horizon_days=7)
    print(weekly.head(10))
