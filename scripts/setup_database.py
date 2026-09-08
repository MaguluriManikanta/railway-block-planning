"""
Database setup for the AI-Powered Automatic Block Planning system.
Creates all tables in SQLite and loads the generated CSV datasets.

Run this once (or whenever you want to reset the database):
    python scripts/setup_database.py
"""

import sqlite3
import pandas as pd
import bcrypt
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "railway.db")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def get_connection():
    return sqlite3.connect(DB_PATH)


def create_tables(conn):
    cur = conn.cursor()

    # Unified defects/tasks table (merges TMS + SMMS + TDMS)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS defects (
        defect_id TEXT PRIMARY KEY,
        department TEXT NOT NULL,          -- Engineering / S&T / TRD
        section_id TEXT NOT NULL,
        asset_ref TEXT,                    -- chainage_km / equipment_id / feeder_id
        defect_type TEXT,
        severity TEXT,                     -- Critical / High / Medium / Low
        reported_date TEXT,
        due_date TEXT,
        overdue_days INTEGER,
        estimated_duration_hours REAL,
        trains_affected_per_day INTEGER,
        status TEXT,                       -- Open / Scheduled / Completed
        actual_completion_time TEXT,
        priority_score REAL,
        risk_score REAL,
        source TEXT,                       -- TMS / SMMS / TDMS
        created_via TEXT DEFAULT 'system'  -- 'system' or 'nl_agent' (natural language entry)
    )
    """)

    # Corridor / block availability (from COA)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS corridor_slots (
        slot_id TEXT PRIMARY KEY,
        section_id TEXT NOT NULL,
        date TEXT,
        start_time TEXT,
        end_time TEXT,
        duration_hours REAL,
        slot_type TEXT,
        is_available INTEGER
    )
    """)

    # Train timetable
    cur.execute("""
    CREATE TABLE IF NOT EXISTS train_timetable (
        train_id TEXT,
        train_type TEXT,
        section_id TEXT,
        departure_time TEXT,
        frequency TEXT,
        priority_class TEXT
    )
    """)

    # Goods forecast
    cur.execute("""
    CREATE TABLE IF NOT EXISTS goods_forecast (
        forecast_id TEXT PRIMARY KEY,
        section_id TEXT,
        date TEXT,
        expected_rakes INTEGER,
        commodity TEXT,
        traffic_level TEXT
    )
    """)

    # Final schedule (output of the optimizer)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS schedule (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        defect_id TEXT,
        slot_id TEXT,
        section_id TEXT,
        department TEXT,
        planned_start TEXT,
        planned_end TEXT,
        horizon TEXT,               -- weekly / monthly
        status TEXT DEFAULT 'planned',   -- planned / approved / completed / cancelled
        decided_by TEXT DEFAULT 'optimizer',  -- optimizer / admin / ai_auto
        actual_completion_time TEXT,
        completion_flag TEXT,       -- early / on_time / late
        crew_id TEXT,
        FOREIGN KEY (defect_id) REFERENCES defects(defect_id)
    )
    """)

    # Users (role-based login)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,          -- engineering / signal / traction / admin
        full_name TEXT
    )
    """)

    # Notifications
    cur.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        notif_id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_role TEXT,
        message TEXT,
        created_at TEXT,
        is_read INTEGER DEFAULT 0,
        category TEXT,   -- completion / deadline / auto_approval / conflict / anomaly / public_advisory
        audience TEXT DEFAULT 'internal'   -- internal (staff/admin) or public (passengers/commuters)
    )
    """)

    # Audit log (every decision, human or agent)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT,          -- username or agent name
        action TEXT,
        details TEXT,
        timestamp TEXT
    )
    """)

    # Crew roster (for Resource/Crew Availability Agent)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS crew_roster (
        crew_id TEXT PRIMARY KEY,
        department TEXT,
        section_id TEXT,
        shift TEXT,          -- Night / Day
        is_available INTEGER
    )
    """)

    # Reports (metadata of generated PDF reports)
    # Locopilot speed advisories (generated when blocks complete early or corridor opens)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS locopilot_speed_advisories (
        advisory_id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_id TEXT NOT NULL,
        section_id TEXT NOT NULL,
        station_from TEXT,
        station_to TEXT,
        km_start REAL,
        km_end REAL,
        normal_speed_kmh REAL,
        recommended_speed_kmh REAL,
        time_saved_minutes REAL,
        reason TEXT,
        department_notified TEXT,
        status TEXT DEFAULT 'Issued',
        created_at TEXT
    )
    """)

    # Live train movement and speed tracking table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS live_train_status (
        train_id TEXT PRIMARY KEY,
        train_name TEXT,
        train_type TEXT,
        section_id TEXT NOT NULL,
        current_km REAL,
        delay_minutes REAL,
        current_speed_kmh REAL,
        recommended_speed_kmh REAL,
        status TEXT DEFAULT 'Running',
        last_updated TEXT
    )
    """)

    # Auto-migration for actual_completion_time column if missing
    defects_cols = [col[1] for col in cur.execute("PRAGMA table_info(defects)").fetchall()]
    if "actual_completion_time" not in defects_cols:
        cur.execute("ALTER TABLE defects ADD COLUMN actual_completion_time TEXT")

    conn.commit()


def load_defects(conn):
    """Merge TMS/SMMS/TDMS into the unified defects table."""
    tms = pd.read_csv(f"{DATA_DIR}/tms_defects.csv")
    smms = pd.read_csv(f"{DATA_DIR}/smms_defects.csv")
    tdms = pd.read_csv(f"{DATA_DIR}/tdms_defects.csv")

    tms = tms.rename(columns={"chainage_km": "asset_ref"})
    tms["source"] = "TMS"

    smms = smms.rename(columns={"equipment_id": "asset_ref"})
    smms["source"] = "SMMS"

    tdms = tdms.rename(columns={"feeder_id": "asset_ref"})
    tdms["source"] = "TDMS"

    cols = ["defect_id", "department", "section_id", "asset_ref", "defect_type",
            "severity", "reported_date", "due_date", "overdue_days",
            "estimated_duration_hours", "trains_affected_per_day", "status", "source"]

    merged = pd.concat([tms[cols], smms[cols], tdms[cols]], ignore_index=True)
    merged["priority_score"] = None
    merged["risk_score"] = None
    merged["created_via"] = "system"

    merged.to_sql("defects", conn, if_exists="replace", index=False)
    print(f"Loaded {len(merged)} defects into unified table.")


def load_other_tables(conn):
    pd.read_csv(f"{DATA_DIR}/corridor_availability.csv").to_sql(
        "corridor_slots", conn, if_exists="replace", index=False)
    pd.read_csv(f"{DATA_DIR}/train_timetable.csv").to_sql(
        "train_timetable", conn, if_exists="replace", index=False)
    pd.read_csv(f"{DATA_DIR}/goods_forecast.csv").to_sql(
        "goods_forecast", conn, if_exists="replace", index=False)
    print("Loaded corridor, timetable, and goods forecast tables.")


def create_default_users(conn):
    """Create one login per department + one admin. Change passwords after first login."""
    users = [
        ("engineer1", "engineer123", "engineering", "Engineering User"),
        ("signal1", "signal123", "signal", "S&T User"),
        ("traction1", "traction123", "traction", "TRD User"),
        ("admin1", "admin123", "admin", "Controller / Admin"),
    ]
    cur = conn.cursor()
    for username, pwd, role, name in users:
        hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
        cur.execute(
            "INSERT OR REPLACE INTO users (username, password_hash, role, full_name) VALUES (?, ?, ?, ?)",
            (username, hashed, role, name)
        )
    conn.commit()
    print("Default users created:")
    for u in users:
        print(f"   username={u[0]}  password={u[1]}  role={u[2]}")


def create_dummy_crew(conn):
    import random
    sections = pd.read_sql("SELECT DISTINCT section_id FROM defects", conn)["section_id"].tolist()
    rows = []
    for i, sec in enumerate(sections):
        for dept in ["Engineering", "S&T", "TRD"]:
            for shift in ["Night", "Day"]:
                rows.append({
                    "crew_id": f"CREW-{dept[:3].upper()}-{i}-{shift[0]}",
                    "department": dept,
                    "section_id": sec,
                    "shift": shift,
                    "is_available": random.choice([1, 1, 1, 0])  # mostly available
                })
    pd.DataFrame(rows).to_sql("crew_roster", conn, if_exists="replace", index=False)
    print(f"Created {len(rows)} crew roster entries.")


def create_dummy_live_trains(conn):
    trains = [
        {"train_id": "12727", "train_name": "Godavari Express", "train_type": "Superfast Express", "section_id": "Vijayawada-SEC-01", "current_km": 14.5, "delay_minutes": 25.0, "current_speed_kmh": 60.0, "recommended_speed_kmh": 90.0, "status": "Delayed - Speed Recovery Recommended", "last_updated": "2026-09-06 22:30:00"},
        {"train_id": "12707", "train_name": "AP Sampark Kranti", "train_type": "Superfast Express", "section_id": "Secunderabad-SEC-01", "current_km": 28.0, "delay_minutes": 15.0, "current_speed_kmh": 65.0, "recommended_speed_kmh": 85.0, "status": "Delayed - Corridor Opening Boost", "last_updated": "2026-09-06 22:35:00"},
        {"train_id": "12805", "train_name": "Jan Shatabdi Express", "train_type": "Express", "section_id": "Guntur-SEC-03", "current_km": 8.2, "delay_minutes": 0.0, "current_speed_kmh": 80.0, "recommended_speed_kmh": 80.0, "status": "On Time", "last_updated": "2026-09-06 22:40:00"},
        {"train_id": "GDS-9901", "train_name": "Coal Rake Special (Goods)", "train_type": "Freight Goods Rake", "section_id": "Hyderabad-SEC-04", "current_km": 33.0, "delay_minutes": 40.0, "current_speed_kmh": 45.0, "recommended_speed_kmh": 65.0, "status": "Freight Slotting Active", "last_updated": "2026-09-06 22:42:00"},
        {"train_id": "17225", "train_name": "Amaravati Express", "train_type": "Express", "section_id": "Vijayawada-SEC-02", "current_km": 19.4, "delay_minutes": 18.0, "current_speed_kmh": 55.0, "recommended_speed_kmh": 85.0, "status": "Delayed - Speed Recovery Recommended", "last_updated": "2026-09-06 22:43:00"}
    ]
    pd.DataFrame(trains).to_sql("live_train_status", conn, if_exists="replace", index=False)
    print(f"Loaded {len(trains)} live train tracking entries.")


if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    load_defects(conn)
    load_other_tables(conn)
    create_default_users(conn)
    create_dummy_crew(conn)
    create_dummy_live_trains(conn)
    conn.close()
    print(f"\nDatabase ready at: {DB_PATH}")
