"""
FastAPI High-Performance Backend Application — Indian Railways Automatic Block Planning
Serves REST APIs, WebSockets, and AI Agent Execution for React Frontend (Vercel/Render Deployment).
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
import sys
import json
import asyncio

# Add scripts directory to path
SYS_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
if SYS_SCRIPTS_DIR not in sys.path:
    sys.path.append(SYS_SCRIPTS_DIR)

from agents import (
    CoordinatorAgent,
    ComplianceAgent,
    log_action,
    notify,
    get_agent_db
)
from scoring_models import compute_priority_scores, detect_anomalies

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")

app = FastAPI(
    title="Indian Railways AI Block Planning API",
    description="Zero-Lag FastAPI REST Backend & WebSockets for Railway Maintenance Planning System",
    version="2.0.0"
)

# Enable CORS for Vercel Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    return conn


def ensure_schema():
    try:
        conn = get_db_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        notif_cols = [col[1] for col in conn.execute("PRAGMA table_info(notifications)").fetchall()]
        if notif_cols and "is_read" not in notif_cols:
            conn.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0")
            conn.commit()
        conn.close()
    except Exception:
        pass

ensure_schema()

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class OverrideRequest(BaseModel):
    schedule_id: int
    section_id: str
    department: str
    new_start: str
    new_end: str
    is_locked: bool = False
    is_emerg_force: bool = False
    override_reason: Optional[str] = "Controller Optimization"
    horizon: Optional[str] = "weekly"

class EmergencyBlockRequest(BaseModel):
    department: str
    section_id: str
    defect_type: str
    severity: str = "Critical"
    duration_hours: float = 2.0
    reason: str = "G&SR Rule 4.09 Emergency Protection"

class MarkReadRequest(BaseModel):
    notif_id: Optional[int] = None  # None means mark all as read
    mark_all: bool = False

class SystemSettingRequest(BaseModel):
    key: str
    value: str

class ChatbotRequest(BaseModel):
    query: str
    department: Optional[str] = "All"
    user_lang: Optional[str] = "en"

# ---------------------------------------------------------------------------
# Health & Dashboard KPIs
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health_check():
    return {"status": "online", "system": "Indian Railways Automatic Block Planning API", "version": "2.0.0"}

@app.get("/api/kpi")
def get_kpi_metrics(department: str = "All"):
    conn = get_db_conn()
    cur = conn.cursor()
    
    tot_d = cur.execute("SELECT COUNT(*) FROM defects").fetchone()[0]
    open_d = cur.execute("SELECT COUNT(*) FROM defects WHERE status='Open'").fetchone()[0]
    crit_d = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(severity)='critical' AND status!='Completed'").fetchone()[0]
    high_d = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(severity)='high' AND status!='Completed'").fetchone()[0]
    sched_count = cur.execute("SELECT COUNT(*) FROM schedule WHERE LOWER(status)!='cancelled'").fetchone()[0]
    locked_count = cur.execute("SELECT COUNT(*) FROM schedule WHERE status='locked' OR decided_by IN ('controller_override', 'controller_emergency', 'emergency_force_override')").fetchone()[0]
    
    conn.close()

    total_tasks = max(1, tot_d)
    health_score = max(35.0, round(100.0 - ((crit_d * 2.5 + open_d * 0.4) / total_tasks * 100.0), 1))

    return {
        "total_defects": tot_d,
        "open_defects": open_d,
        "critical_defects": crit_d,
        "high_defects": high_d,
        "scheduled_blocks": sched_count,
        "locked_overrides": locked_count,
        "health_score": health_score,
        "active_trains_count": 10,
        "on_time_pct": 90.0,
        "capacity_utilization_pct": 62.5
    }

# ---------------------------------------------------------------------------
# Schedule & Corridor Matrix APIs
# ---------------------------------------------------------------------------

@app.get("/api/schedules")
def get_schedules(horizon: Optional[str] = None, department: Optional[str] = None, include_completed: bool = False):
    conn = get_db_conn()
    q = """
        SELECT s.schedule_id, s.defect_id, s.slot_id, s.section_id, 
               COALESCE(s.department, d.department) as department,
               s.planned_start, s.planned_end, s.horizon, s.status, s.decided_by,
               d.defect_type, d.severity, d.priority_score, d.trains_affected_per_day, d.due_date,
               d.estimated_duration_hours,
               cs.duration_hours as slot_duration_hours, cs.slot_type
        FROM schedule s
        LEFT JOIN defects d ON s.defect_id = d.defect_id
        LEFT JOIN corridor_slots cs ON s.slot_id = cs.slot_id
        WHERE LOWER(s.status) != 'cancelled'
    """
    params = []
    
    if not include_completed:
        q += " AND LOWER(s.status) != 'completed'"
        
    if department and department != "All":
        q += " AND (s.department = ? OR d.department = ?)"
        params.extend([department, department])

    if horizon:
        q += " AND (s.horizon = ? OR s.horizon = 'emergency' OR s.decided_by IN ('controller_override', 'controller_emergency', 'emergency_force_override', 'admin'))"
        params.append(horizon)

    q += " ORDER BY s.planned_start ASC"
    df = pd.read_sql(q, conn, params=params if params else None)
    conn.close()

    records = df.to_dict(orient="records")
    return {"status": "success", "count": len(records), "data": records}

@app.post("/api/schedules/override")
def apply_controller_override(req: OverrideRequest):
    comp = ComplianceAgent()
    is_valid, reason = comp.validate_override(req.section_id, req.new_start, req.new_end, current_schedule_id=req.schedule_id)
    
    if not is_valid and not req.is_emerg_force:
        return {
            "success": False,
            "reason": f"Controller Override Rejected — {reason}",
            "is_emergency_option_available": True
        }

    conn = get_db_conn()
    new_status = "locked" if req.is_locked else "planned"
    decided_val = "emergency_force_override" if req.is_emerg_force else "controller_override"
    conn.execute(
        "UPDATE schedule SET planned_start=?, planned_end=?, status=?, decided_by=? WHERE schedule_id=?",
        (req.new_start, req.new_end, new_status, decided_val, req.schedule_id)
    )
    conn.commit()
    conn.close()

    coord = CoordinatorAgent()
    res = coord.resolve_override_and_reschedule(req.schedule_id, req.new_start, req.new_end, horizon=req.horizon)

    log_action("Controller", "manual_override", f"Schedule #{req.schedule_id} updated: {req.new_start} to {req.new_end} ({req.override_reason}) [Emergency Force: {req.is_emerg_force}]")
    notify("admin", f"Manual Override: Schedule #{req.schedule_id} ({req.department}) timing modified by Central Control.", category="controller_override")

    message = f"⚡ EMERGENCY FORCE OVERRIDE GRANTED! Schedule #{req.schedule_id} updated ({req.new_start} to {req.new_end}). TSR 30 km/h active." if req.is_emerg_force else f"✅ Schedule #{req.schedule_id} successfully updated to {req.new_start} - {req.new_end} & timetable re-optimized!"

    return {
        "success": True,
        "message": message,
        "schedule_id": req.schedule_id,
        "rescheduled_tasks_count": len(res) if not res.empty else 0
    }

@app.post("/api/schedules/cancel")
def cancel_schedule_block(schedule_id: int, reason: Optional[str] = "Controller Postponed"):
    conn = get_db_conn()
    row = conn.execute("SELECT defect_id, slot_id, horizon FROM schedule WHERE schedule_id=?", (schedule_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Schedule ID not found")
    
    defect_id, slot_id, horizon = row["defect_id"], row["slot_id"], row["horizon"]
    conn.execute("UPDATE schedule SET status='cancelled', decided_by='controller_cancelled' WHERE schedule_id=?", (schedule_id,))
    if defect_id:
        conn.execute("UPDATE defects SET status='Open' WHERE defect_id=?", (defect_id,))
    if slot_id:
        conn.execute("UPDATE corridor_slots SET is_available=1 WHERE slot_id=?", (slot_id,))
    conn.commit()
    conn.close()

    coord = CoordinatorAgent()
    coord.run_cycle(horizon=horizon if horizon else "weekly")
    log_action("Controller", "cancel_block", f"Schedule #{schedule_id} cancelled: {reason}")

    return {"success": True, "message": f"⚠️ Schedule #{schedule_id} cancelled. Corridor slot released and weekly schedule re-optimized."}

@app.post("/api/schedules/emergency")
def grant_emergency_block(req: EmergencyBlockRequest):
    now_dt = datetime.now()
    end_dt = now_dt + pd.Timedelta(hours=req.duration_hours)
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")
    end_str = end_dt.strftime("%Y-%m-%d %H:%M")
    em_defect_id = f"EMERG-{now_dt.strftime('%m%d%H%M')}"

    conn = get_db_conn()
    conn.execute("""
        INSERT INTO defects (defect_id, section_id, department, defect_type, severity, priority_score, status, estimated_duration_hours, overdue_days, trains_affected_per_day)
        VALUES (?, ?, ?, ?, ?, 99.9, 'Emergency Active', ?, 0, 15)
    """, (em_defect_id, req.section_id, req.department, req.defect_type, req.severity, req.duration_hours))

    conn.execute("""
        INSERT INTO schedule (defect_id, slot_id, section_id, department, planned_start, planned_end, horizon, status, decided_by)
        VALUES (?, 'SLOT-EMERGENCY', ?, ?, ?, ?, 'emergency', 'locked', 'controller_emergency')
    """, (em_defect_id, req.section_id, req.department, now_str, end_str))

    try:
        conn.execute("""
            INSERT INTO locopilot_speed_advisories (train_id, section_id, station_from, station_to, km_start, km_end, normal_speed_kmh, recommended_speed_kmh, time_saved_minutes, reason, department_notified, status, created_at)
            VALUES ('ALL-TRAINS', ?, 'BZA', 'KI', 114.0, 118.0, 110.0, 30.0, 0.0, ?, ?, 'Dispatched to Locopilots', ?)
        """, (req.section_id, f"EMERGENCY BLOCK ({req.department}): {req.defect_type}", req.department, now_dt.strftime("%Y-%m-%d %H:%M:%S")))
    except Exception:
        pass

    conn.commit()
    conn.close()

    log_action("Controller", "emergency_block", f"Imposed emergency block on {req.section_id} ({req.department}) for {req.duration_hours} hrs")
    notify("admin", f"🚨 EMERGENCY BLOCK IMPOSED on {req.section_id} ({req.department}) until {end_str}. Caution order 30 km/h dispatched.", category="emergency")

    return {
        "success": True,
        "message": f"⚡ 🚨 EMERGENCY BLOCK GRANTED on {req.section_id} until {end_str}! Caution orders (TSR 30 km/h) transmitted to Locopilots.",
        "defect_id": em_defect_id
    }

# ---------------------------------------------------------------------------
# Live Train Telemetry APIs
# ---------------------------------------------------------------------------

@app.get("/api/trains/live")
def get_live_trains():
    conn = get_db_conn()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "live_train_status" in tables:
        df = pd.read_sql("SELECT * FROM live_train_status ORDER BY delay_minutes DESC LIMIT 10", conn)
        conn.close()
        return {"status": "success", "data": df.to_dict(orient="records")}
    conn.close()
    return {"status": "success", "data": []}

@app.post("/api/trains/advance")
def advance_train_telemetry(step_km: float = 3.0):
    conn = get_db_conn()
    df = pd.read_sql("SELECT * FROM live_train_status", conn)
    updated_records = []
    
    for _, tr in df.iterrows():
        new_km = tr["current_km"] + step_km
        if new_km > 280:
            new_km = 10
        delay = tr["delay_minutes"]
        if delay > 0:
            delay = max(0, delay - 1)
        
        speed = tr["speed_kmh"]
        status = tr["status"]
        if 112 <= new_km <= 120:
            speed = 30
            status = "Regulated (30 km/h TSR Caution)"
        else:
            speed = 110
            status = "Cruising (On Time)" if delay == 0 else f"Running (+{delay}m Delay)"

        conn.execute("""
            UPDATE live_train_status SET current_km=?, speed_kmh=?, delay_minutes=?, status=?, updated_at=? WHERE train_id=?
        """, (new_km, speed, delay, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tr["train_id"]))
        
        tr_dict = dict(tr)
        tr_dict.update({"current_km": new_km, "speed_kmh": speed, "delay_minutes": delay, "status": status})
        updated_records.append(tr_dict)
        
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Advanced telemetry step by {step_km} KM", "trains": updated_records}

# ---------------------------------------------------------------------------
# Notifications & System Settings APIs
# ---------------------------------------------------------------------------

@app.get("/api/notifications")
def get_notifications(role: str = "admin"):
    conn = get_db_conn()
    cur = conn.cursor()
    notif_query = "SELECT notif_id, recipient_role, category, audience, message, created_at, COALESCE(is_read, 0) as is_read FROM notifications ORDER BY notif_id DESC LIMIT 25"
    cur.execute(notif_query)
    notif_rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    unread_count = sum(1 for n in notif_rows if n["is_read"] == 0)
    return {"unread_count": unread_count, "data": notif_rows}

@app.post("/api/notifications/read")
def mark_notification_read(req: MarkReadRequest):
    conn = get_db_conn()
    if req.mark_all:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE is_read = 0 OR is_read IS NULL")
    elif req.notif_id is not None:
        conn.execute("UPDATE notifications SET is_read = 1 WHERE notif_id = ?", (req.notif_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/settings/{key}")
def get_setting(key: str):
    conn = get_db_conn()
    row = conn.execute("SELECT value FROM system_settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return {"key": key, "value": row[0] if row else "0"}

@app.post("/api/settings")
def set_setting(req: SystemSettingRequest):
    conn = get_db_conn()
    conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (req.key, req.value))
    conn.commit()
    conn.close()
    return {"success": True, "key": req.key, "value": req.value}

# ---------------------------------------------------------------------------
# Server Launch Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
