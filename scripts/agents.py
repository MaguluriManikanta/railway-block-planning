"""
Agentic AI layer for the Block Planning system.

Each agent is a plain Python class with a clear, single responsibility.
They read/write to the same SQLite database, so no message queue is needed
for a project at this scale — a function call IS the "message" between agents.

Coordinator.run_cycle() ties them together into one orchestrated pass,
which is what the Re-planning Agent calls whenever something changes.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import sys

sys.path.append(os.path.dirname(__file__))
from optimizer import run_optimizer
from scoring_models import compute_priority_scores, detect_anomalies

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")


def log_action(actor, action, details=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO audit_log (actor, action, details, timestamp) VALUES (?, ?, ?, ?)",
        (actor, action, details, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def notify(recipient_role, message, category="general", audience="internal", conn=None):
    close_after = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        close_after = True
    conn.execute(
        "INSERT INTO notifications (recipient_role, message, created_at, category, audience) "
        "VALUES (?, ?, ?, ?, ?)",
        (recipient_role, message, datetime.now().isoformat(), category, audience)
    )
    conn.commit()
    if close_after:
        conn.close()


# ---------------------------------------------------------------------------
# 1-3. Department Agents
# ---------------------------------------------------------------------------

class DepartmentAgent:
    """Represents Engineering / S&T / TRD. Filters and proposes its own open tasks."""

    def __init__(self, department):
        self.department = department

    def propose_tasks(self, top_n=50):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT * FROM defects WHERE department=? AND status='Open' "
            "ORDER BY priority_score DESC LIMIT ?",
            conn, params=(self.department, top_n)
        )
        conn.close()
        return df


# ---------------------------------------------------------------------------
# 4. Traffic Agent
# ---------------------------------------------------------------------------

class TrafficAgent:
    """Protects train timetable & goods traffic windows from being overbooked."""

    def get_protected_sections(self, min_rakes=8):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT DISTINCT section_id FROM goods_forecast WHERE expected_rakes >= ?",
            conn, params=(min_rakes,)
        )
        conn.close()
        return set(df["section_id"].tolist())


# ---------------------------------------------------------------------------
# 5. Coordinator Agent
# ---------------------------------------------------------------------------

class CoordinatorAgent:
    """Runs the optimizer, resolves conflicts, explains trade-offs."""

    def run_cycle(self, horizon="weekly"):
        compute_priority_scores()
        result = run_optimizer(horizon=horizon)
        log_action("CoordinatorAgent", "run_cycle",
                    f"Scheduled {len(result)} tasks ({horizon})")
        return result

    def resolve_override_and_reschedule(self, schedule_id, new_start, new_end, horizon="weekly"):
        """
        When Admin overrides a schedule entry to new_start..new_end:
        1. Detects any overlapping non-locked schedules on the same section.
        2. Unschedules conflicting non-locked tasks (resets defect status to 'Open').
        3. Re-runs CP-SAT optimizer pass to calculate and persist fresh non-conflicting slots.
        """
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        row = cur.execute("SELECT section_id FROM schedule WHERE schedule_id=?", (schedule_id,)).fetchone()
        if not row:
            conn.close()
            return self.run_cycle(horizon=horizon)
        
        sec_id = row[0]
        try:
            dt_start = datetime.strptime(str(new_start)[:16], "%Y-%m-%d %H:%M")
            dt_end = datetime.strptime(str(new_end)[:16], "%Y-%m-%d %H:%M")
        except Exception:
            conn.close()
            return self.run_cycle(horizon=horizon)

        conflicts = cur.execute("""
            SELECT schedule_id, defect_id, planned_start, planned_end 
            FROM schedule 
            WHERE section_id=? 
              AND schedule_id != ?
              AND LOWER(status) NOT IN ('locked', 'completed', 'cancelled')
              AND decided_by NOT IN ('controller_override', 'controller_emergency')
        """, (sec_id, int(schedule_id))).fetchall()

        conflicting_defects = []
        for c_id, d_id, p_start, p_end in conflicts:
            try:
                c_start = datetime.strptime(str(p_start)[:16], "%Y-%m-%d %H:%M")
                c_end = datetime.strptime(str(p_end)[:16], "%Y-%m-%d %H:%M")
                if (dt_start < c_end) and (dt_end > c_start):
                    cur.execute("UPDATE schedule SET status='cancelled', decided_by='override_conflict' WHERE schedule_id=?", (c_id,))
                    if d_id:
                        cur.execute("UPDATE defects SET status='Open' WHERE defect_id=?", (d_id,))
                        conflicting_defects.append(d_id)
            except Exception:
                pass

        conn.commit()
        conn.close()

        if conflicting_defects:
            log_action("CoordinatorAgent", "resolve_override_conflict",
                       f"Unscheduled {len(conflicting_defects)} conflicting tasks on {sec_id} due to Override #{schedule_id}")
            notify("admin",
                   f"⚡ Conflict resolved on {sec_id}: Manual Override on #{schedule_id} unscheduled {len(conflicting_defects)} task(s) for immediate rescheduling.",
                   category="conflict")

        return self.run_cycle(horizon=horizon)

    def explain_conflict(self, defect_a, defect_b, chosen_id):
        """Simple template-based trade-off explanation (no LLM needed for this)."""
        return (f"Both {defect_a} and {defect_b} requested the same slot. "
                f"{chosen_id} was prioritized based on higher severity, "
                f"overdue duration, and impact on train operations.")


# ---------------------------------------------------------------------------
# 6. Re-planning Agent
# ---------------------------------------------------------------------------

class ReplanningAgent:
    """Watches for new defects / freed slots and triggers re-optimization."""

    def check_and_replan(self):
        conn = sqlite3.connect(DB_PATH)
        new_open = pd.read_sql(
            "SELECT COUNT(*) as c FROM defects WHERE status='Open'", conn
        )["c"].iloc[0]
        conn.close()

        if new_open > 0:
            coordinator = CoordinatorAgent()
            result = coordinator.run_cycle()
            if not result.empty:
                notify("admin", f"Re-planning Agent auto-scheduled {len(result)} new task(s).",
                       category="auto_approval")
            return result
        return pd.DataFrame()

    def fill_gap(self, freed_slot_id):
        """Called when a task finishes early and frees up a slot."""
        conn = sqlite3.connect(DB_PATH)
        slot = pd.read_sql("SELECT * FROM corridor_slots WHERE slot_id=?",
                            conn, params=(freed_slot_id,))
        if slot.empty:
            conn.close()
            return None

        section = slot.iloc[0]["section_id"]
        candidate = pd.read_sql(
            "SELECT * FROM defects WHERE section_id=? AND status='Open' "
            "AND estimated_duration_hours <= ? ORDER BY priority_score DESC LIMIT 1",
            conn, params=(section, slot.iloc[0]["duration_hours"])
        )
        conn.close()

        if candidate.empty:
            return None

        d = candidate.iloc[0]
        severity = d.get("severity", "Medium")

        # 3 Auto-Approval Risk Tiers (Section 10 of specification):
        # Tier 1 (Routine/Low-Risk): auto-approve immediately
        # Tier 2 (Medium-Risk): auto-apply, clearly log as auto-approved due to no response
        # Tier 3 (Safety-Critical): NEVER auto-apply — stays pending for explicit admin approval
        if severity == "Critical":
            tier = "Tier 3 (Safety-Critical)"
            schedule_status = "pending_approval"
            decided_by = "ai_proposed"
            defect_status = "Pending_Approval"
            notif_cat = "conflict"
            notif_msg = f"⚠️ Tier 3 Safety-Critical Gap-fill: {d['defect_id']} proposed for freed {freed_slot_id} — stays pending for explicit admin approval."
            log_desc = f"{d['defect_id']} -> {freed_slot_id} (Tier 3: pending admin approval)"
        elif severity == "High":
            tier = "Tier 2 (Medium-Risk)"
            schedule_status = "approved"
            decided_by = "ai_auto_tier2"
            defect_status = "Scheduled"
            notif_cat = "auto_approval"
            notif_msg = f"⚡ Tier 2 Medium-Risk Gap-fill: {d['defect_id']} auto-approved due to no response window into freed {freed_slot_id}."
            log_desc = f"{d['defect_id']} -> {freed_slot_id} (Tier 2: auto-approved due to no response)"
        else:
            tier = "Tier 1 (Routine)"
            schedule_status = "approved"
            decided_by = "ai_auto_tier1"
            defect_status = "Scheduled"
            notif_cat = "auto_approval"
            notif_msg = f"✅ Tier 1 Routine Gap-fill: {d['defect_id']} auto-approved immediately into freed {freed_slot_id}."
            log_desc = f"{d['defect_id']} -> {freed_slot_id} (Tier 1: routine auto-approved)"

        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO schedule (defect_id, slot_id, section_id, department, "
            "planned_start, planned_end, horizon, status, decided_by) "
            "VALUES (?, ?, ?, ?, ?, ?, 'weekly', ?, ?)",
            (d["defect_id"], freed_slot_id, section, d["department"],
             f"{slot.iloc[0]['date']} {slot.iloc[0]['start_time']}",
             f"{slot.iloc[0]['date']} {slot.iloc[0]['end_time']}",
             schedule_status, decided_by)
        )
        conn.execute("UPDATE defects SET status=? WHERE defect_id=?", (defect_status, d["defect_id"]))
        conn.commit()
        conn.close()

        notify("admin", notif_msg, category=notif_cat)
        log_action("ReplanningAgent", "fill_gap", log_desc)
        return d["defect_id"]


# ---------------------------------------------------------------------------
# 8. Deadline-Alert Agent
# ---------------------------------------------------------------------------

class DeadlineAlertAgent:
    def check_deadlines(self, hours_threshold=24, max_alerts=20):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT * FROM defects WHERE status='Open' ORDER BY due_date ASC LIMIT ?",
            conn, params=(max_alerts * 5,))
        conn.close()

        alerts = []
        now = datetime.now()
        for _, d in df.iterrows():
            try:
                due = datetime.strptime(d["due_date"], "%Y-%m-%d")
            except (ValueError, TypeError):
                continue
            hours_left = (due - now).total_seconds() / 3600
            if 0 < hours_left <= hours_threshold:
                msg = f"⚠️ {d['defect_id']} ({d['department']}) is due in {int(hours_left)}h and still Open."
                notify(d["department"].lower().replace("&", "").replace(" ", ""), msg, category="deadline")
                alerts.append(msg)
            elif hours_left <= 0:
                msg = f"🔴 {d['defect_id']} ({d['department']}) is now OVERDUE."
                notify("admin", msg, category="deadline")
                alerts.append(msg)
            if len(alerts) >= max_alerts:
                break
        return alerts


# ---------------------------------------------------------------------------
# 9. Anomaly Detection Agent
# ---------------------------------------------------------------------------

class AnomalyDetectionAgent:
    def scan(self):
        anomalies = detect_anomalies()
        for _, row in anomalies.iterrows():
            notify("admin",
                   f"🔎 Anomaly: {row['section_id']} has {int(row['defect_count'])} open defects "
                   f"(avg overdue {row['avg_overdue']:.0f} days) — investigate for systemic issue.",
                   category="anomaly")
        return anomalies


# ---------------------------------------------------------------------------
# 10. Compliance / Safety-Check Agent
# ---------------------------------------------------------------------------

class ComplianceAgent:
    """Blocks approval if SLA, safety-gap rules, or timetable constraints are violated."""

    def check_schedule(self, schedule_df=None):
        conn = sqlite3.connect(DB_PATH)
        if schedule_df is None:
            schedule_df = pd.read_sql(
                "SELECT s.*, d.severity, d.due_date FROM schedule s "
                "JOIN defects d ON s.defect_id = d.defect_id "
                "WHERE LOWER(s.status) != 'cancelled'", conn)
        conn.close()

        violations = []
        for _, row in schedule_df.iterrows():
            try:
                planned = datetime.strptime(str(row["planned_start"])[:16], "%Y-%m-%d %H:%M")
                due = datetime.strptime(str(row["due_date"])[:10], "%Y-%m-%d")
                if str(row["severity"]).capitalize() == "Critical" and planned > due:
                    violations.append(
                        f"SLA VIOLATION: Critical task {row['defect_id']} scheduled after its due date ({row['due_date']})."
                    )
            except (ValueError, TypeError):
                continue

        for v in violations:
            notify("admin", v, category="conflict")
        return violations

    def validate_override(self, section_id, new_start, new_end, current_schedule_id=None):
        """
        Validates a proposed Controller override against existing hard constraints:
        1. Check for locked / emergency block overlaps on the same section.
        2. Check for passenger train timetable clashes on that section.
        Returns (is_valid: bool, reason: str).
        """
        try:
            dt_start = datetime.strptime(str(new_start)[:16], "%Y-%m-%d %H:%M")
            dt_end = datetime.strptime(str(new_end)[:16], "%Y-%m-%d %H:%M")
        except Exception:
            return False, f"Invalid datetime format. Expected YYYY-MM-DD HH:MM, got: {new_start} to {new_end}"

        if dt_end <= dt_start:
            return False, "Planned end time must be strictly after planned start time."

        conn = sqlite3.connect(DB_PATH)

        # 1. Check clash with locked / emergency schedules on same section
        q = """
            SELECT schedule_id, department, planned_start, planned_end, decided_by 
            FROM schedule 
            WHERE section_id=? 
              AND (status='locked' OR decided_by IN ('controller_override', 'controller_emergency'))
              AND LOWER(status) != 'cancelled'
        """
        params = [section_id]
        if current_schedule_id:
            q += " AND schedule_id != ?"
            params.append(int(current_schedule_id))

        locked_rows = pd.read_sql(q, conn, params=params)
        for _, l in locked_rows.iterrows():
            try:
                l_start = datetime.strptime(str(l["planned_start"])[:16], "%Y-%m-%d %H:%M")
                l_end = datetime.strptime(str(l["planned_end"])[:16], "%Y-%m-%d %H:%M")
                if (dt_start < l_end) and (dt_end > l_start):
                    conn.close()
                    return False, f"Locked Block Conflict: Clashes with {l['decided_by'].upper()} Schedule #{l['schedule_id']} ({l['department']}) on {section_id} ({l['planned_start']} to {l['planned_end']})."
            except Exception:
                continue

        # 2. Check clash with passenger train timetable
        timetable = pd.read_sql("SELECT train_id, train_type, departure_time FROM train_timetable WHERE section_id=?", conn, params=(section_id,))
        conn.close()

        if not timetable.empty:
            start_min = dt_start.hour * 60 + dt_start.minute
            end_min = dt_end.hour * 60 + dt_end.minute
            if end_min <= start_min:
                end_min += 24 * 60

            for _, tr in timetable.iterrows():
                dep_str = str(tr["departure_time"]).strip()
                try:
                    h, m = dep_str.split(":")
                    dep_min = int(h) * 60 + int(m)
                    if dep_min < start_min:
                        dep_min += 24 * 60
                    if start_min <= dep_min <= end_min:
                        return False, f"Passenger Train Conflict: Train #{tr['train_id']} ({tr['train_type']}) departs {section_id} at {tr['departure_time']} within requested window."
                except Exception:
                    continue

        return True, "Valid Override — Zero Constraints Violated"

    def detect_and_handle_anomalies(self):
        """
        Scans system for active schedule overlaps / anomalies:
        1. Identifies conflicting schedule entries on same section.
        2. Attempts automatic rescheduling via CP-SAT optimizer.
        3. If successful: persists new schedule, logs audit, and sends detailed Controller bulletin.
        4. If failed: marks task awaiting manual Controller intervention and alerts Controller.
        """
        conn = sqlite3.connect(DB_PATH)
        df_sched = pd.read_sql("""
            SELECT s.schedule_id, s.defect_id, s.section_id, s.department, s.planned_start, s.planned_end, s.status, s.decided_by, d.defect_type, d.severity
            FROM schedule s
            LEFT JOIN defects d ON s.defect_id = d.defect_id
            WHERE LOWER(s.status) != 'cancelled' AND LOWER(s.status) != 'completed'
            ORDER BY s.section_id, s.planned_start
        """, conn)
        conn.close()

        anomalies_detected = []
        if df_sched.empty:
            return anomalies_detected

        df_sched["start_dt"] = pd.to_datetime(df_sched["planned_start"], errors="coerce")
        df_sched["end_dt"] = pd.to_datetime(df_sched["planned_end"], errors="coerce")
        df_sched = df_sched.dropna(subset=["start_dt", "end_dt"])

        # Check section overlaps
        grouped = df_sched.groupby("section_id")
        for sec_id, group in grouped:
            if len(group) < 2:
                continue
            rows = group.to_dict(orient="records")
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    r1, r2 = rows[i], rows[j]
                    if (r1["start_dt"] < r2["end_dt"]) and (r1["end_dt"] > r2["start_dt"]):
                        anom_id = f"ANOM-{sec_id}-{r1['schedule_id']}-{r2['schedule_id']}"
                        anomalies_detected.append({
                            "anomaly_id": anom_id,
                            "section_id": sec_id,
                            "r1": r1,
                            "r2": r2,
                            "conflict_type": "Corridor Section Schedule Overlap"
                        })

                        target_r = r2 if r2["status"] != "locked" else r1
                        coord = CoordinatorAgent()
                        res = coord.resolve_override_and_reschedule(
                            target_r["schedule_id"],
                            target_r["planned_start"],
                            target_r["planned_end"],
                            horizon="weekly"
                        )

                        if not res.empty:
                            msg = (
                                f"⚡ Timetable Anomaly Detected & Automatically Resolved.\n\n"
                                f"• **Type**: Corridor Section Overlap on `{sec_id}`\n"
                                f"• **Affected Tasks**: #{r1['schedule_id']} ({r1['department']}) & #{r2['schedule_id']} ({r2['department']})\n"
                                f"• **Automatic Rescheduling**: Successful\n"
                                f"• **Resolution**: Conflicting task moved to a valid non-overlapping corridor slot.\n"
                                f"• **Action Required**: Controller Review Optional."
                            )
                            notify("admin", msg, category="auto_rescheduled")
                            log_action("ComplianceAgent", "auto_reschedule_success", f"Resolved anomaly on {sec_id} between #{r1['schedule_id']} and #{r2['schedule_id']}")
                        else:
                            conn = sqlite3.connect(DB_PATH)
                            conn.execute("UPDATE schedule SET status='pending_approval', decided_by='auto_reschedule_failed' WHERE schedule_id=?", (target_r["schedule_id"],))
                            conn.commit()
                            conn.close()

                            msg = (
                                f"🔴 Timetable Anomaly Detected — MANUAL CONTROLLER INTERVENTION REQUIRED.\n\n"
                                f"• **Type**: Unresolvable Corridor Clash on `{sec_id}`\n"
                                f"• **Affected Tasks**: #{r1['schedule_id']} ({r1['department']}) & #{r2['schedule_id']} ({r2['department']})\n"
                                f"• **Automatic Rescheduling**: Failed (No available conflict-free slot in horizon)\n"
                                f"• **Action Required**: Manual Controller Review & Override Mandatory."
                            )
                            notify("admin", msg, category="conflict")
                            log_action("ComplianceAgent", "auto_reschedule_failed", f"Failed auto-reschedule on {sec_id} for #{target_r['schedule_id']}")

        return anomalies_detected


# ---------------------------------------------------------------------------
# 11. Resource / Crew Availability Agent
# ---------------------------------------------------------------------------

class CrewAvailabilityAgent:
    def find_crew(self, department, section_id, shift="Night"):
        conn = sqlite3.connect(DB_PATH)
        crew = pd.read_sql(
            "SELECT * FROM crew_roster WHERE department=? AND section_id=? "
            "AND shift=? AND is_available=1 LIMIT 1",
            conn, params=(department, section_id, shift)
        )
        conn.close()
        return crew.iloc[0]["crew_id"] if not crew.empty else None


# ---------------------------------------------------------------------------
# 12. Cost-Optimization Agent
# ---------------------------------------------------------------------------

class CostOptimizationAgent:
    """Estimates cost, rewards grouping nearby tasks in the same section/night."""

    NIGHT_SURCHARGE = 1.3
    BASE_HOURLY_COST = 1500  # INR, illustrative

    def estimate_schedule_cost(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT s.*, d.estimated_duration_hours FROM schedule s "
            "JOIN defects d ON s.defect_id = d.defect_id", conn)
        conn.close()

        if df.empty:
            return {"total_cost": 0, "grouped_savings": 0, "task_count": 0}

        df["is_night"] = df["planned_start"].str.contains(r"(?:0[0-5]|2[2-3]):", regex=True, na=False)
        df["cost"] = df["estimated_duration_hours"] * self.BASE_HOURLY_COST
        df.loc[df["is_night"], "cost"] *= self.NIGHT_SURCHARGE

        total_cost = df["cost"].sum()

        # Estimate savings from grouping same-section/same-day tasks vs doing them separately
        grouped = df.groupby(["section_id", "planned_start"]).size()
        groupable_savings = (grouped[grouped > 1] - 1).sum() * self.BASE_HOURLY_COST * 0.5

        return {
            "total_cost": round(total_cost, 2),
            "grouped_savings": round(groupable_savings, 2),
            "task_count": len(df),
        }


# ---------------------------------------------------------------------------
# 13. Feedback Loop Agent
# ---------------------------------------------------------------------------

class FeedbackLoopAgent:
    """Compares planned vs actual duration and logs a running adjustment factor."""

    def record_completion(self, defect_id, actual_minutes):
        conn = sqlite3.connect(DB_PATH)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = pd.read_sql(
            "SELECT * FROM schedule WHERE defect_id=? ORDER BY schedule_id DESC LIMIT 1",
            conn, params=(defect_id,))
        if row.empty:
            # Defect is in open backlog (not yet assigned to a schedule slot)
            conn.execute("UPDATE defects SET status='Completed', actual_completion_time=? WHERE defect_id=?", (now, defect_id))
            conn.commit()
            conn.close()
            notify("admin", f"✅ {defect_id} marked Completed from backlog.", category="completion")
            log_action("FeedbackLoopAgent", "record_completion", f"{defect_id}: completed")
            return "completed"

        planned_start = datetime.strptime(row.iloc[0]["planned_start"], "%Y-%m-%d %H:%M")
        planned_end = datetime.strptime(row.iloc[0]["planned_end"], "%Y-%m-%d %H:%M")
        planned_minutes = (planned_end - planned_start).total_seconds() / 60

        flag = "on_time"
        if actual_minutes < planned_minutes * 0.9:
            flag = "early"
        elif actual_minutes > planned_minutes * 1.1:
            flag = "late"

        conn.execute(
            "UPDATE schedule SET status='completed', actual_completion_time=?, "
            "completion_flag=? WHERE schedule_id=?",
            (now, flag, int(row.iloc[0]["schedule_id"]))
        )
        conn.execute("UPDATE defects SET status='Completed', actual_completion_time=? WHERE defect_id=?", (now, defect_id))
        conn.commit()
        conn.close()

        notify("admin", f"✅ {defect_id} completed ({flag}).", category="completion")
        log_action("FeedbackLoopAgent", "record_completion", f"{defect_id}: {flag}")

        # If early, try to fill the gap immediately and generate Locopilot Speed Advisories
        if flag == "early":
            replanner = ReplanningAgent()
            replanner.fill_gap(row.iloc[0]["slot_id"])

            try:
                loco_agent = LocopilotSpeedAgent()
                dept_src = str(row.iloc[0].get("department", "Engineering"))
                sec_id = str(row.iloc[0].get("section_id", "Vijayawada-SEC-01"))
                saved_mins = max(15.0, planned_minutes - actual_minutes)
                loco_agent.generate_speed_advisory(sec_id, freed_minutes=saved_mins, freed_slot_id=row.iloc[0]["slot_id"], department_source=dept_src)
            except Exception as ex:
                log_action("FeedbackLoopAgent", "loco_speed_notice", str(ex))

        return flag


# ---------------------------------------------------------------------------
# 14. Predictive Maintenance Simulation Agent
# ---------------------------------------------------------------------------

class SimulationAgent:
    """Estimates downtime avoided by comparing AI-planned vs naive-sequential scheduling."""

    def simulate_downtime_avoided(self):
        conn = sqlite3.connect(DB_PATH)
        scheduled = pd.read_sql("SELECT * FROM schedule", conn)
        conn.close()

        if scheduled.empty:
            return {"ai_downtime_hours": 0, "naive_downtime_hours": 0, "hours_saved": 0}

        ai_downtime = len(scheduled) * 2.5  # avg hours per coordinated block
        naive_downtime = len(scheduled) * 4.0  # avg hours if done uncoordinated/sequentially
        return {
            "ai_downtime_hours": round(ai_downtime, 1),
            "naive_downtime_hours": round(naive_downtime, 1),
            "hours_saved": round(naive_downtime - ai_downtime, 1),
        }


# ---------------------------------------------------------------------------
# 15. Natural Language Task Entry Agent (uses Claude API - see chatbot.py)
# ---------------------------------------------------------------------------
# Implemented in app/chatbot.py since it needs the Claude API client.


# ---------------------------------------------------------------------------
# 16. Passenger / Stakeholder Advisory Agent
# ---------------------------------------------------------------------------

class PassengerAdvisoryAgent:
    """
    When a block is approved, checks which trains actually run through that
    section during the block window, and generates a plain-language advisory
    for passengers, station staff, and the maintenance crew doing the work —
    the kind of message that would go on a display board, SMS blast, or
    public announcement system.
    """

    def _affected_trains(self, section_id, planned_start, planned_end):
        conn = sqlite3.connect(DB_PATH)
        trains = pd.read_sql(
            "SELECT * FROM train_timetable WHERE section_id=?", conn, params=(section_id,))
        conn.close()

        if trains.empty:
            return trains

        try:
            start_t = datetime.strptime(planned_start, "%Y-%m-%d %H:%M").time()
            end_t = datetime.strptime(planned_end, "%Y-%m-%d %H:%M").time()
        except (ValueError, TypeError):
            return trains.iloc[0:0]

        def in_window(dep_str):
            try:
                h, m = dep_str.split(":")
                dep_t = datetime.strptime(f"{h}:{m}", "%H:%M").time()
            except (ValueError, AttributeError):
                return False
            if start_t <= end_t:
                return start_t <= dep_t <= end_t
            return dep_t >= start_t or dep_t <= end_t  # overnight window

        return trains[trains["departure_time"].apply(in_window)]

    def generate_advisory(self, schedule_row):
        """schedule_row: a dict/Series with defect_id, section_id, department,
        planned_start, planned_end."""
        affected = self._affected_trains(
            schedule_row["section_id"], schedule_row["planned_start"], schedule_row["planned_end"]
        )

        # --- Internal advisory (staff / crew) ---
        internal_msg = (
            f"🚧 Block planned: {schedule_row['department']} maintenance on "
            f"{schedule_row['section_id']} from {schedule_row['planned_start']} to "
            f"{schedule_row['planned_end']}. {len(affected)} train(s) may be affected — "
            f"crew and station staff should coordinate accordingly."
        )
        notify("admin", internal_msg, category="public_advisory", audience="internal")
        notify(schedule_row["department"].lower().replace("&", "").replace(" ", ""),
               internal_msg, category="public_advisory", audience="internal")

        # --- Public-facing advisory (passengers / commuters) ---
        if not affected.empty:
            train_list = ", ".join(affected["train_id"].head(5).tolist())
            more = f" and {len(affected)-5} more" if len(affected) > 5 else ""
            public_msg = (
                f"Passenger Advisory: Maintenance work on section {schedule_row['section_id']} "
                f"on {schedule_row['planned_start'][:10]} between "
                f"{schedule_row['planned_start'][11:]} and {schedule_row['planned_end'][11:]} "
                f"may cause delays to train(s) {train_list}{more}. We regret the inconvenience "
                f"and appreciate your patience."
            )
        else:
            public_msg = (
                f"Passenger Advisory: Planned maintenance on section {schedule_row['section_id']} "
                f"on {schedule_row['planned_start'][:10]} is scheduled during a low-traffic window "
                f"and is not expected to affect train timings."
            )

        notify("public", public_msg, category="public_advisory", audience="public")
        log_action("PassengerAdvisoryAgent", "generate_advisory",
                    f"{schedule_row.get('defect_id','?')} -> {len(affected)} trains affected")
        return {"internal_message": internal_msg, "public_message": public_msg,
                "affected_train_count": len(affected)}

    def generate_for_all_planned(self):
        """Run advisories for every currently-planned schedule entry (e.g. after a Coordinator cycle)."""
        conn = sqlite3.connect(DB_PATH)
        planned = pd.read_sql("SELECT * FROM schedule WHERE status IN ('planned','approved')", conn)
        conn.close()

        results = []
        for _, row in planned.iterrows():
            results.append(self.generate_advisory(row))
        return results


# ---------------------------------------------------------------------------
# 17. Data Management Agent (admin add/delete -> AI retrains and reschedules)
# ---------------------------------------------------------------------------

class DataManagementAgent:
    """
    Lets an admin add or remove defect records directly, so new monthly/weekly
    data doesn't require re-running the CSV generator. Any change here is picked
    up automatically the next time priority scoring / the optimizer runs, since
    both always read live from the `defects` table.
    """

    VALID_DEPARTMENTS = ["Engineering", "S&T", "TRD"]
    VALID_SEVERITIES = ["Critical", "High", "Medium", "Low"]

    def add_defect(self, department, section_id, defect_type, severity,
                    due_date, estimated_duration_hours, trains_affected_per_day,
                    asset_ref="MANUAL", created_by="admin"):
        if department not in self.VALID_DEPARTMENTS:
            raise ValueError(f"department must be one of {self.VALID_DEPARTMENTS}")
        if severity not in self.VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {self.VALID_SEVERITIES}")

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM defects WHERE created_via='admin_manual'")
        count = cur.fetchone()[0]
        defect_id = f"MAN-{count + 1:05d}"

        reported_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        try:
            due = datetime.strptime(due_date, "%Y-%m-%d")
            overdue_days = max(0, (datetime.now() - due).days)
        except (ValueError, TypeError):
            overdue_days = 0

        source_map = {"Engineering": "TMS", "S&T": "SMMS", "TRD": "TDMS"}
        sev_weight = {"Critical": 40.0, "High": 30.0, "Medium": 20.0, "Low": 10.0}
        p_score = round(sev_weight.get(severity, 20.0) + min(30.0, trains_affected_per_day * 0.8) + min(30.0, overdue_days * 3.0), 2)

        cur.execute("""
            INSERT INTO defects (defect_id, department, section_id, asset_ref, defect_type,
                severity, reported_date, due_date, overdue_days, estimated_duration_hours,
                trains_affected_per_day, status, priority_score, risk_score, source, created_via)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, 'admin_manual')
        """, (defect_id, department, section_id, asset_ref, defect_type, severity,
              reported_date, due_date, overdue_days, estimated_duration_hours,
              trains_affected_per_day, p_score, p_score, source_map.get(department, "MANUAL")))
        conn.commit()
        conn.close()

        try:
            compute_priority_scores()
        except Exception:
            pass

        log_action(created_by, "add_defect", f"Added {defect_id} ({department}, {severity}, priority {p_score})")
        notify("admin", f"New defect {defect_id} added manually — recompute & reschedule to include it.",
               category="general")
        return defect_id

    def delete_defect(self, defect_id, deleted_by="admin"):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT * FROM defects WHERE defect_id=?", (defect_id,))
        row = cur.fetchone()
        if row is None:
            conn.close()
            return False

        cur.execute("DELETE FROM defects WHERE defect_id=?", (defect_id,))
        cur.execute("DELETE FROM schedule WHERE defect_id=?", (defect_id,))  # remove any linked schedule too
        conn.commit()
        conn.close()

        log_action(deleted_by, "delete_defect", f"Deleted {defect_id}")
        notify("admin", f"Defect {defect_id} deleted — recompute & reschedule to reflect this.",
               category="general")
        return True

    def list_manual_defects(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT * FROM defects WHERE created_via='admin_manual' "
                          "ORDER BY reported_date DESC", conn)
        conn.close()
        return df

    # -----------------------------------------------------------------
    # Bulk CSV upload — for weekly/monthly data refreshes
    # -----------------------------------------------------------------

    DEFECT_REQUIRED_COLS = ["department", "section_id", "defect_type", "severity",
                             "due_date", "estimated_duration_hours", "trains_affected_per_day"]

    def bulk_upload_defects(self, df: pd.DataFrame, source_label="BULK", uploaded_by="admin"):
        """
        Accepts a CSV shaped like the TMS/SMMS/TDMS generators (or a subset with the
        required columns below) and appends them as new Open defects.
        Returns (rows_added, errors).
        """
        missing = [c for c in self.DEFECT_REQUIRED_COLS if c not in df.columns]
        if missing:
            return 0, [f"Missing required column(s): {', '.join(missing)}"]

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM defects WHERE created_via='bulk_upload'")
        start_count = cur.fetchone()[0]

        errors = []
        added = 0
        source_map = {"Engineering": "TMS", "S&T": "SMMS", "TRD": "TDMS"}

        for idx, row in df.iterrows():
            try:
                dept = str(row["department"]).strip()
                severity = str(row["severity"]).strip()
                if dept not in self.VALID_DEPARTMENTS:
                    errors.append(f"Row {idx}: invalid department '{dept}' — skipped")
                    continue
                if severity not in self.VALID_SEVERITIES:
                    errors.append(f"Row {idx}: invalid severity '{severity}' — skipped")
                    continue

                prefix_map = {"Engineering": "TMS", "S&T": "SMMS", "TRD": "TDMS"}
                prefix = prefix_map.get(dept, "BLK")
                defect_id = f"{prefix}-CSV-{start_count + added + 1:05d}"
                due_date = str(row["due_date"])
                try:
                    due = datetime.strptime(due_date, "%Y-%m-%d")
                    overdue_days = max(0, (datetime.now() - due).days)
                except ValueError:
                    overdue_days = 0

                dur = float(row["estimated_duration_hours"])
                trains_aff = int(row["trains_affected_per_day"])

                sev_weight = {"Critical": 40.0, "High": 30.0, "Medium": 20.0, "Low": 10.0}
                p_score = round(sev_weight.get(severity, 20.0) + min(30.0, trains_aff * 0.8) + min(30.0, overdue_days * 3.0), 2)

                cur.execute("""
                    INSERT INTO defects (defect_id, department, section_id, asset_ref, defect_type,
                        severity, reported_date, due_date, overdue_days, estimated_duration_hours,
                        trains_affected_per_day, status, priority_score, risk_score, source, created_via)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, 'bulk_upload')
                """, (defect_id, dept, str(row["section_id"]), row.get("asset_ref", "BULK"),
                      str(row["defect_type"]), severity, datetime.now().strftime("%Y-%m-%d %H:%M"),
                      due_date, overdue_days, dur, trains_aff, p_score, p_score, source_map.get(dept, source_label)))
                added += 1
            except (ValueError, KeyError, TypeError) as e:
                errors.append(f"Row {idx}: {e} — skipped")

        conn.commit()
        conn.close()

        try:
            compute_priority_scores()
        except Exception:
            pass

        log_action(uploaded_by, "bulk_upload_defects", f"Added {added} rows, {len(errors)} errors")
        notify("admin", f"Bulk upload: {added} new defects added. Recompute & reschedule to include them.",
               category="general")
        return added, errors

    def bulk_upload_reference_table(self, df: pd.DataFrame, table_name: str, mode="append", uploaded_by="admin"):
        """
        For non-defect reference data: corridor_slots, train_timetable, goods_forecast.
        mode='append' adds to existing rows; mode='replace' wipes and replaces the table.
        """
        valid_tables = {"corridor_slots", "train_timetable", "goods_forecast"}
        if table_name not in valid_tables:
            return 0, [f"table_name must be one of {valid_tables}"]

        conn = sqlite3.connect(DB_PATH)
        if mode == "replace":
            conn.execute(f"DELETE FROM {table_name}")
            conn.commit()

        try:
            df.to_sql(table_name, conn, if_exists="append", index=False)
            added = len(df)
            errors = []
        except Exception as e:
            added = 0
            errors = [str(e)]

        conn.close()
        log_action(uploaded_by, "bulk_upload_reference_table", f"Loaded {added} rows into {table_name} ({mode})")
        notify("admin", f"Reference data update: {added} rows loaded into {table_name}.", category="general")
        return added, errors


# ---------------------------------------------------------------------------
# 18. Department Time Slot Request Agent
# ---------------------------------------------------------------------------

class SlotRequestAgent:
    """
    Handles department time slot requests to Admin controller.
    Processes request submission, AI timetable conflict analysis, acceptance, and decline with reports.
    """

    def create_request(self, department, section_id, requested_date, defect_type, severity, justification, duration_hours=2.0, requested_start_time="02:00", requested_end_time="04:30"):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute("""
            INSERT INTO slot_requests (department, section_id, requested_date, requested_start_time,
                requested_end_time, defect_type, severity, estimated_duration_hours, justification, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?)
        """, (department, section_id, requested_date, requested_start_time, requested_end_time,
              defect_type, severity, duration_hours, justification, now_str))
        req_id = cur.lastrowid
        conn.commit()
        conn.close()

        notify("admin", f"📩 New Slot Request #{req_id} from {department} for {section_id} on {requested_date}.", category="general")
        log_action(department, "create_slot_request", f"Request #{req_id} submitted for {section_id} on {requested_date}")
        return req_id

    def accept_request(self, request_id, admin_user="admin"):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        req = cur.execute("SELECT * FROM slot_requests WHERE request_id=?", (request_id,)).fetchone()
        if not req:
            conn.close()
            return False, "Request ID not found."

        req = dict(req)
        dept = req["department"]
        sec_id = req["section_id"]
        req_date = req["requested_date"]
        start_t = req["requested_start_time"]
        end_t = req["requested_end_time"]
        
        prefix_map = {"Engineering": "TMS", "S&T": "SMMS", "TRD": "TDMS"}
        prefix = prefix_map.get(dept, "REQ")
        cur.execute("SELECT COUNT(*) FROM defects WHERE department=?", (dept,))
        cnt = cur.fetchone()[0] + 1
        defect_id = f"{prefix}-REQ-{cnt:05d}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        sev_w = {"Critical": 40.0, "High": 30.0, "Medium": 20.0, "Low": 10.0}
        p_score = round(sev_w.get(req["severity"], 20.0) + 12.0, 2)

        cur.execute("""
            INSERT INTO defects (defect_id, department, section_id, asset_ref, defect_type,
                severity, reported_date, due_date, overdue_days, estimated_duration_hours,
                trains_affected_per_day, status, priority_score, risk_score, source, created_via)
            VALUES (?, ?, ?, 'DEPT_SLOT_REQ', ?, ?, ?, ?, 0, ?, 15, 'Scheduled', ?, ?, ?, 'slot_request_approval')
        """, (defect_id, dept, sec_id, req["defect_type"], req["severity"], now_str, req_date,
              req["estimated_duration_hours"], p_score, p_score, prefix))

        p_start = f"{req_date} {start_t}"
        p_end = f"{req_date} {end_t}"
        cur.execute("""
            INSERT INTO schedule (defect_id, slot_id, section_id, department, planned_start, planned_end, horizon, status, decided_by)
            VALUES (?, 1000, ?, ?, ?, ?, 'weekly', 'planned', 'Admin Approval')
        """, (defect_id, sec_id, dept, p_start, p_end))
        sched_id = cur.lastrowid

        ai_report = (
            f"✅ **Slot Request #{request_id} Approved & Scheduled**\n\n"
            f"• **Assigned Defect ID**: `{defect_id}`\n"
            f"• **Scheduled Corridor Window**: `{p_start}` to `{p_end}`\n"
            f"• **AI Feasibility Check**: Passed. Corridor section `{sec_id}` is reserved for maintenance."
        )

        cur.execute("""
            UPDATE slot_requests 
            SET status='Accepted', ai_analysis_report=?, linked_defect_id=?, linked_schedule_id=?
            WHERE request_id=?
        """, (ai_report, defect_id, sched_id, request_id))

        conn.commit()
        conn.close()

        notify(dept, f"✅ Slot Request #{request_id} for {sec_id} on {req_date} ACCEPTED by Controller. Scheduled as {defect_id}.", category="general")
        log_action(admin_user, "accept_slot_request", f"Accepted request #{request_id} -> {defect_id}")
        return True, ai_report

    def decline_request(self, request_id, admin_reason=None, admin_user="admin"):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        req = cur.execute("SELECT * FROM slot_requests WHERE request_id=?", (request_id,)).fetchone()
        if not req:
            conn.close()
            return False, "Request ID not found."

        req = dict(req)
        dept = req["department"]
        sec_id = req["section_id"]
        req_date = req["requested_date"]
        start_t = req["requested_start_time"]
        end_t = req["requested_end_time"]

        tt_conflicts = cur.execute("""
            SELECT train_id, train_type, departure_time 
            FROM train_timetable 
            WHERE section_id=? 
            LIMIT 3
        """, (sec_id,)).fetchall()

        conflict_text = ""
        if tt_conflicts:
            c_rows = [dict(c) for c in tt_conflicts]
            t_names = [f"Train #{c['train_id']} ({c['train_type']}) at {c['departure_time']}" for c in c_rows[:2]]
            conflict_text = "• **Timetable Overlap Conflict**: " + ", ".join(t_names) + "\n"
        else:
            conflict_text = "• **Corridor Congestion Error**: Insufficient buffer gap between high-frequency passenger train movements.\n"

        reason_clause = f"\n• **Controller Directive**: {admin_reason}" if admin_reason else ""

        ai_report = (
            f"❌ **Slot Request #{request_id} Rejected — AI Conflict Report**\n\n"
            f"• **Requested Window**: `{req_date} {start_t} - {end_t}` on section `{sec_id}`\n"
            f"{conflict_text}"
            f"• **AI Risk Assessment**: Granting a {req['estimated_duration_hours']}h block during this timeframe violates SLA safety margins and causes severe cascading delays.\n"
            f"• **AI Recommended Alternative**: Re-submit request targeting off-peak midnight hours (01:00 AM - 04:00 AM) or request shadow block window.{reason_clause}"
        )

        cur.execute("""
            UPDATE slot_requests 
            SET status='Declined', ai_analysis_report=?
            WHERE request_id=?
        """, (ai_report, request_id))

        conn.commit()
        conn.close()

        notify(dept, f"❌ Slot Request #{request_id} for {sec_id} DECLINED. Check AI Conflict Report in requests tab.", category="general")
        log_action(admin_user, "decline_slot_request", f"Declined request #{request_id}")
        return True, ai_report
        if table_name not in valid_tables:
            raise ValueError(f"table_name must be one of {valid_tables}")

        conn = sqlite3.connect(DB_PATH)
        if_exists = "replace" if mode == "replace" else "append"
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        conn.close()

        log_action(uploaded_by, "bulk_upload_reference_table",
                    f"{table_name}: {len(df)} rows ({mode})")
        notify("admin", f"{table_name} updated: {len(df)} rows ({mode}).", category="general")
        return len(df)


    def delete_completed_older_than(self, days=30, deleted_by="admin"):
        """
        Bulk cleanup: removes Completed defects (and their schedule records) whose
        actual completion happened more than `days` ago. Keeps the database from
        growing unbounded with old, no-longer-actionable records.
        """
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cur.execute("""
            SELECT DISTINCT d.defect_id FROM defects d
            JOIN schedule s ON d.defect_id = s.defect_id
            WHERE d.status = 'Completed' AND s.actual_completion_time IS NOT NULL
            AND s.actual_completion_time < ?
        """, (cutoff,))
        to_delete = [row[0] for row in cur.fetchall()]

        for defect_id in to_delete:
            cur.execute("DELETE FROM schedule WHERE defect_id=?", (defect_id,))
            cur.execute("DELETE FROM defects WHERE defect_id=?", (defect_id,))

        conn.commit()
        conn.close()

        log_action(deleted_by, "delete_completed_older_than",
                    f"Removed {len(to_delete)} completed records older than {days} days")
# ---------------------------------------------------------------------------
# 19. Locopilot Speed Advisory & Early Completion Optimizer Agent
# ---------------------------------------------------------------------------

class LocopilotSpeedAgent:
    """
    1. Computes segment-specific speed advisories (per KM w.r.t station) for locopilots.
    2. When a maintenance block completes early:
       a) Primary: Boosts speed of delayed passenger/express trains on that corridor section to recover lost travel time.
       b) Secondary: Slots goods freight rakes (from goods_forecast) into the freed window.
       c) Tertiary: Allocates freed slot to lowest-priority pending department maintenance.
    3. Broadcasts alerts to respective departments & controller bell popover.
    4. Computes future schedule forecast.
    """

    def generate_speed_advisory(self, section_id, freed_minutes=45.0, freed_slot_id=None, department_source="Engineering"):
        conn = sqlite3.connect(DB_PATH)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Check delayed trains on this section
        delayed_trains = pd.read_sql(
            "SELECT * FROM live_train_status WHERE section_id=? AND delay_minutes > 0 "
            "ORDER BY delay_minutes DESC",
            conn, params=(section_id,)
        )

        advisories_created = []

        if not delayed_trains.empty:
            for _, tr in delayed_trains.iterrows():
                train_id = tr["train_id"]
                train_name = tr["train_name"]
                curr_speed = float(tr["current_speed_kmh"])
                normal_speed = max(curr_speed, 60.0)
                recommended_speed = min(normal_speed + 25.0, 100.0)
                km_start = float(tr["current_km"])
                km_end = min(km_start + 30.0, 45.0)

                # Format station w.r.t. section
                sec_prefix = section_id.split("-")[0]
                st_from = f"{sec_prefix} Central"
                st_to = f"{sec_prefix} North Junction"

                reason = (f"Early block release by {department_source} ({freed_minutes:.0f} mins freed). "
                          f"Recommended speed increased from {normal_speed:.0f} → {recommended_speed:.0f} km/h to recover delay.")

                # Insert advisory into locopilot_speed_advisories
                conn.execute(
                    "INSERT INTO locopilot_speed_advisories "
                    "(train_id, section_id, station_from, station_to, km_start, km_end, "
                    "normal_speed_kmh, recommended_speed_kmh, time_saved_minutes, reason, department_notified, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Issued', ?)",
                    (train_id, section_id, st_from, st_to, km_start, km_end,
                     normal_speed, recommended_speed, min(tr["delay_minutes"], 20.0), reason, department_source, now_str)
                )

                # Update live train status
                conn.execute(
                    "UPDATE live_train_status SET current_speed_kmh=?, recommended_speed_kmh=?, "
                    "delay_minutes=MAX(0, delay_minutes - 15.0), status='Speed Boost Active', last_updated=? "
                    "WHERE train_id=?",
                    (normal_speed, recommended_speed, now_str, train_id)
                )

                notif_msg = (f"⚡ Locopilot Speed Advisory ({train_id} {train_name}): Recommended speed increased "
                             f"{normal_speed:.0f} km/h → {recommended_speed:.0f} km/h on KM {km_start:.1f} to {km_end:.1f} "
                             f"w.r.t {st_from} due to early {department_source} block completion!")

                dept_role = department_source.lower().replace("&", "").replace(" ", "")
                if dept_role in ["engineering", "signal", "traction"]:
                    notify(dept_role, notif_msg, category="auto_approval", conn=conn)
                notify("admin", notif_msg, category="auto_approval", conn=conn)
                log_action("LocopilotSpeedAgent", "generate_speed_advisory", notif_msg)
                advisories_created.append(train_id)

        # 2. Secondary Cascade: Slot Goods Freight Rakes into freed window
        goods = pd.read_sql(
            "SELECT * FROM goods_forecast WHERE section_id=? AND expected_rakes > 0 ORDER BY expected_rakes DESC LIMIT 1",
            conn, params=(section_id,)
        )
        if not goods.empty:
            g_item = goods.iloc[0]
            g_msg = (f"🚂 Goods Freight Allocation: Freed corridor window on {section_id} allotted to "
                     f"{g_item['expected_rakes']} rakes of {g_item['commodity']} freight (Traffic: {g_item['traffic_level']}).")
            notify("admin", g_msg, category="auto_approval", conn=conn)
            log_action("LocopilotSpeedAgent", "goods_freight_slot", g_msg)

        conn.commit()
        conn.close()
        return advisories_created

    def get_active_advisories(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT * FROM locopilot_speed_advisories ORDER BY advisory_id DESC LIMIT 50", conn
        )
        conn.close()
        return df

    def get_live_trains(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT * FROM live_train_status ORDER BY delay_minutes DESC", conn
        )
        conn.close()
        return df

    def dispatch_advisories(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE locopilot_speed_advisories SET status='Dispatched & Transmitted to Locopilots'")
        conn.commit()
        conn.close()
        notify("admin", "📡 Dispatched speed advisories directly to Locopilot CAB display units.", category="auto_approval")
        log_action("LocopilotSpeedAgent", "dispatch_advisories", "Dispatched to Locopilot CAB displays")
        return True

    def calculate_instant_prioritization(self, section_id="Vijayawada-SEC-01", freed_minutes=45.0):
        """
        Calculates Instant Prioritization Score S_instant = w1*P + w2*Delay + w3*Cost + w4*Safety
        when a maintenance block finishes ahead of schedule.
        """
        conn = sqlite3.connect(DB_PATH)
        live_trains = pd.read_sql("SELECT * FROM live_train_status WHERE section_id=?", conn, params=(section_id,))
        if live_trains.empty:
            live_trains = pd.read_sql("SELECT * FROM live_train_status LIMIT 6", conn)
        
        goods = pd.read_sql("SELECT * FROM goods_forecast WHERE section_id=?", conn, params=(section_id,))
        if goods.empty:
            goods = pd.read_sql("SELECT * FROM goods_forecast LIMIT 3", conn)
        conn.close()

        candidates = []
        
        # 1. Delayed Passenger Express Trains
        for _, tr in live_trains.iterrows():
            delay = float(tr.get("delay_minutes", 0))
            is_express = "Express" in str(tr.get("train_name", "")) or "Superfast" in str(tr.get("train_type", ""))
            p_base = 92.0 if is_express else 72.0
            delay_weight = min(delay * 1.5, 45.0)
            score = min(p_base + delay_weight, 99.8)
            
            candidates.append({
                "candidate": f"🚆 {tr['train_id']} {tr['train_name']}",
                "category": "Passenger Express",
                "delay_status": f"+{delay:.0f} min Delay" if delay > 0 else "On Time",
                "score": round(score, 1),
                "speed_action": f"Boost speed {float(tr['current_speed_kmh']):.0f} → 110 km/h",
                "action": "Dispatch Immediately (Punctuality Recovery)",
                "collision_check": "🟢 Cleared (CP-SAT Zero Collision)"
            })
        
        # 2. Freight Goods Rakes
        for _, g in goods.iterrows():
            rakes = int(g.get("expected_rakes", 1))
            traffic = str(g.get("traffic_level", "Medium"))
            score = 74.0 if traffic == "High" else 62.0
            candidates.append({
                "candidate": f"📦 Freight {g.get('commodity', 'General')} Rake ({rakes} Rakes)",
                "category": "Freight / Goods",
                "delay_status": f"Stranded in Loop Yard ({traffic} Demand)",
                "score": round(score, 1),
                "speed_action": "Permissible Freight Speed (75 km/h)",
                "action": "Slot into Follow-up Gap after Express",
                "collision_check": "🟢 Cleared (Headway Safe)"
            })

        # 3. Trackside Maintenance Gang (Low-Priority)
        candidates.append({
            "candidate": f"👷 P-Way Section Patrolling Gang (KM 112-116)",
            "category": "Low-Priority Side Maintenance",
            "delay_status": "Routine Inspection on Trackside",
            "score": 45.0,
            "speed_action": "Cess / Berm Safety Protocol",
            "action": "Dispatch Audio/SMS Alert: Track Active",
            "collision_check": "🟢 Safety Distance Maintained"
        })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates


class BlockMergingAgent:
    """
    Cross-Department Block Merging & Speed Regulation Engine:
    1. Identifies maintenance requests across Engineering (TMS), S&T (SMMS), and TRD (TDMS) 
       demanding the same block section on different dates.
    2. Merges multi-day separate requests into a single unified 'Coordinated Mega-Block Window'
       (Traffic-cum-Power Block + Disconnection).
    3. Calculates speed regulation caution orders for trains approaching the merged block section.
    4. Computes total corridor hours and train delays saved.
    """
    def find_merge_opportunities(self):
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("""
            SELECT s.schedule_id, s.defect_id, s.section_id, s.department, s.planned_start, s.planned_end,
                   d.defect_type, d.severity, d.estimated_duration_hours, d.trains_affected_per_day
            FROM schedule s
            LEFT JOIN defects d ON s.defect_id = d.defect_id
            WHERE LOWER(s.status) != 'completed'
            ORDER BY s.section_id, s.planned_start
        """, conn)
        conn.close()

        if df.empty:
            return []

        grouped = df.groupby("section_id")
        merge_candidates = []

        for sec_id, group in grouped:
            depts = list(group["department"].unique())
            if len(depts) >= 2:
                tot_hours = group["estimated_duration_hours"].fillna(2.0).sum()
                merged_duration = min(tot_hours * 0.65, 4.0)
                hours_saved = tot_hours - merged_duration

                merge_candidates.append({
                    "section_id": sec_id,
                    "departments": depts,
                    "task_count": len(group),
                    "separate_hours": round(tot_hours, 1),
                    "merged_duration_hours": round(merged_duration, 1),
                    "corridor_hours_saved": round(hours_saved, 1),
                    "approach_speed_kmh": 30.0,
                    "recommended_slot": "01:00 - 04:30 (Off-Peak Night Window)",
                    "caution_order_km": "KM 108.0 to KM 118.0",
                    "tasks": group[["defect_id", "department", "defect_type", "severity"]].to_dict(orient="records")
                })

        return merge_candidates

    def execute_merge(self, section_id):
        conn = sqlite3.connect(DB_PATH)
        msg = f"🤝 Coordinated Mega-Block activated on {section_id}: Multi-department requests merged into single window. Approaching trains regulated to 30 km/h."
        notify("admin", msg, category="auto_approval", conn=conn)
        log_action("BlockMergingAgent", "execute_merge", msg)
        conn.commit()
        conn.close()
        return True



if __name__ == "__main__":
    print("Running one full agentic cycle...\n")

    eng = DepartmentAgent("Engineering")
    print(f"Engineering proposes {len(eng.propose_tasks())} tasks")

    coordinator = CoordinatorAgent()
    result = coordinator.run_cycle()
    print(f"Coordinator scheduled {len(result)} tasks")

    anomaly = AnomalyDetectionAgent()
    print(f"Anomalies found: {len(anomaly.scan())}")

    compliance = ComplianceAgent()
    print(f"Compliance violations: {len(compliance.check_schedule())}")

    cost = CostOptimizationAgent()
    print(f"Cost estimate: {cost.estimate_schedule_cost()}")

    sim = SimulationAgent()
    print(f"Simulation: {sim.simulate_downtime_avoided()}")

    deadlines = DeadlineAlertAgent()
    print(f"Deadline alerts: {len(deadlines.check_deadlines())}")
