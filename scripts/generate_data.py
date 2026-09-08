"""
Dummy Dataset Generator for AI-Powered Automatic Block Planning System
Simulates data from: TMS, SMMS, TDMS, COA (corridor availability),
Train Timetable, and Goods Traffic Forecast.

Each dataset has 2000+ rows with realistic railway-style fields.
Run this once to produce CSVs in /data, which are then loaded into SQLite.
"""

import os
import random
from datetime import datetime, timedelta
import pandas as pd
from faker import Faker

fake = Faker("en_IN")
random.seed(42)
Faker.seed(42)

# ---------------------------------------------------------------------------
# Shared reference data (kept consistent across all datasets)
# ---------------------------------------------------------------------------

DIVISIONS = ["Secunderabad", "Vijayawada", "Guntakal", "Guntur", "Hyderabad"]

SECTIONS = [
    f"{div}-SEC-{i:02d}"
    for div in DIVISIONS
    for i in range(1, 9)
]  # 5 divisions x 8 sections = 40 sections

DEPARTMENTS = ["Engineering", "S&T", "TRD"]

SEVERITY_LEVELS = ["Critical", "High", "Medium", "Low"]
SEVERITY_WEIGHTS = [0.10, 0.25, 0.40, 0.25]  # most defects are medium/low

START_DATE = datetime(2026, 9, 1)
HORIZON_DAYS = 60  # 2 months of planning horizon


def random_datetime_within(days_back_max=90):
    """Random datetime up to `days_back_max` days before START_DATE (defect reported date)."""
    delta_days = random.randint(0, days_back_max)
    delta_seconds = random.randint(0, 86399)
    return START_DATE - timedelta(days=delta_days, seconds=delta_seconds)


def random_future_datetime_within(days_forward_max=HORIZON_DAYS):
    delta_days = random.randint(0, days_forward_max)
    delta_seconds = random.randint(0, 86399)
    return START_DATE + timedelta(days=delta_days, seconds=delta_seconds)


# ---------------------------------------------------------------------------
# 1. TMS - Track Management System (Engineering defects)
# ---------------------------------------------------------------------------

TMS_DEFECT_TYPES = [
    "Rail fracture", "Weld defect", "Ballast deficiency", "Track geometry deviation",
    "Rail wear beyond limit", "Fish plate loose", "Sleeper damage", "Rail corrugation",
    "Points & crossing wear", "Formation failure", "Vegetation encroachment",
    "Level crossing surface damage",
]


def generate_tms(n=2200):
    rows = []
    for i in range(n):
        reported = random_datetime_within(120)
        severity = random.choices(SEVERITY_LEVELS, SEVERITY_WEIGHTS)[0]
        # SLA-style due days by severity
        due_days = {"Critical": 2, "High": 7, "Medium": 21, "Low": 45}[severity]
        due_date = reported + timedelta(days=due_days)
        overdue_days = max(0, (START_DATE - due_date).days)
        est_duration_hours = round(random.uniform(1, 8), 1) if severity != "Critical" else round(random.uniform(2, 10), 1)

        rows.append({
            "defect_id": f"TMS-{i+1:05d}",
            "department": "Engineering",
            "section_id": random.choice(SECTIONS),
            "chainage_km": round(random.uniform(0, 120), 2),
            "defect_type": random.choice(TMS_DEFECT_TYPES),
            "severity": severity,
            "reported_date": reported.strftime("%Y-%m-%d %H:%M"),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "overdue_days": overdue_days,
            "estimated_duration_hours": est_duration_hours,
            "trains_affected_per_day": random.randint(2, 45),
            "status": random.choices(["Open", "Scheduled", "Completed"], [0.55, 0.25, 0.20])[0],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 2. SMMS - Signalling Maintenance & Management System (S&T defects)
# ---------------------------------------------------------------------------

SMMS_DEFECT_TYPES = [
    "Signal lamp failure", "Point machine malfunction", "Axle counter fault",
    "Track circuit failure", "Interlocking software fault", "Cable fault",
    "Level crossing gate interlock fault", "Block instrument fault",
    "Relay degradation", "Data logger fault", "Block proving failure",
]


def generate_smms(n=2100):
    rows = []
    for i in range(n):
        reported = random_datetime_within(120)
        severity = random.choices(SEVERITY_LEVELS, SEVERITY_WEIGHTS)[0]
        due_days = {"Critical": 1, "High": 5, "Medium": 15, "Low": 30}[severity]
        due_date = reported + timedelta(days=due_days)
        overdue_days = max(0, (START_DATE - due_date).days)
        est_duration_hours = round(random.uniform(0.5, 6), 1)

        rows.append({
            "defect_id": f"SMMS-{i+1:05d}",
            "department": "S&T",
            "section_id": random.choice(SECTIONS),
            "equipment_id": f"EQ-{random.randint(1000,9999)}",
            "defect_type": random.choice(SMMS_DEFECT_TYPES),
            "severity": severity,
            "reported_date": reported.strftime("%Y-%m-%d %H:%M"),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "overdue_days": overdue_days,
            "estimated_duration_hours": est_duration_hours,
            "trains_affected_per_day": random.randint(2, 50),
            "status": random.choices(["Open", "Scheduled", "Completed"], [0.55, 0.25, 0.20])[0],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. TDMS - Traction Distribution Management System (TRD defects)
# ---------------------------------------------------------------------------

TDMS_DEFECT_TYPES = [
    "OHE wire wear", "Insulator flashover", "Feeder fault", "Circuit breaker trip",
    "Traction transformer fault", "Earthing fault", "Dropper damage",
    "Registration arm misalignment", "Section insulator damage", "SCADA communication fault",
]


def generate_tdms(n=2000):
    rows = []
    for i in range(n):
        reported = random_datetime_within(120)
        severity = random.choices(SEVERITY_LEVELS, SEVERITY_WEIGHTS)[0]
        due_days = {"Critical": 1, "High": 6, "Medium": 18, "Low": 35}[severity]
        due_date = reported + timedelta(days=due_days)
        overdue_days = max(0, (START_DATE - due_date).days)
        est_duration_hours = round(random.uniform(1, 7), 1)

        rows.append({
            "defect_id": f"TDMS-{i+1:05d}",
            "department": "TRD",
            "section_id": random.choice(SECTIONS),
            "feeder_id": f"FDR-{random.randint(100,999)}",
            "defect_type": random.choice(TDMS_DEFECT_TYPES),
            "severity": severity,
            "reported_date": reported.strftime("%Y-%m-%d %H:%M"),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "overdue_days": overdue_days,
            "estimated_duration_hours": est_duration_hours,
            "trains_affected_per_day": random.randint(2, 40),
            "status": random.choices(["Open", "Scheduled", "Completed"], [0.55, 0.25, 0.20])[0],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 4. COA - Control Office Application (corridor block availability)
# ---------------------------------------------------------------------------

def generate_corridor_availability(n=2400):
    rows = []
    for i in range(n):
        section = random.choice(SECTIONS)
        day_offset = random.randint(0, HORIZON_DAYS)
        slot_date = START_DATE + timedelta(days=day_offset)
        start_hour = random.choice([0, 1, 2, 3, 4, 5, 13, 14, 22, 23])  # typical low-traffic windows
        duration = random.choice([1, 2, 3, 4])
        end_hour = (start_hour + duration) % 24

        rows.append({
            "slot_id": f"SLOT-{i+1:05d}",
            "section_id": section,
            "date": slot_date.strftime("%Y-%m-%d"),
            "start_time": f"{start_hour:02d}:00",
            "end_time": f"{end_hour:02d}:00",
            "duration_hours": duration,
            "slot_type": random.choices(["Night block", "Day block", "Traffic block"], [0.55, 0.15, 0.30])[0],
            "is_available": random.choices([True, False], [0.8, 0.2])[0],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. Train Timetable
# ---------------------------------------------------------------------------

TRAIN_TYPES = ["Express", "Passenger", "Superfast", "MEMU", "Suburban"]


def generate_timetable(n=2000):
    rows = []
    for i in range(n):
        section = random.choice(SECTIONS)
        dep_hour = random.randint(0, 23)
        dep_min = random.choice([0, 15, 30, 45])
        train_type = random.choices(TRAIN_TYPES, [0.25, 0.30, 0.20, 0.15, 0.10])[0]

        rows.append({
            "train_id": f"TRN-{random.randint(10000,99999)}",
            "train_type": train_type,
            "section_id": section,
            "departure_time": f"{dep_hour:02d}:{dep_min:02d}",
            "frequency": random.choices(["Daily", "Tri-weekly", "Weekly"], [0.7, 0.2, 0.1])[0],
            "priority_class": random.choices(["High", "Medium", "Low"], [0.3, 0.5, 0.2])[0],
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 6. Goods Traffic Forecast
# ---------------------------------------------------------------------------

def generate_goods_forecast(n=2000):
    rows = []
    for i in range(n):
        section = random.choice(SECTIONS)
        day_offset = random.randint(0, HORIZON_DAYS)
        forecast_date = START_DATE + timedelta(days=day_offset)
        expected_rakes = random.randint(1, 12)

        rows.append({
            "forecast_id": f"GDS-{i+1:05d}",
            "section_id": section,
            "date": forecast_date.strftime("%Y-%m-%d"),
            "expected_rakes": expected_rakes,
            "commodity": random.choice(["Coal", "Cement", "Container", "Foodgrain", "Iron ore", "POL"]),
            "traffic_level": "High" if expected_rakes >= 8 else ("Medium" if expected_rakes >= 4 else "Low"),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Run all generators and save
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    datasets = {
        "tms_defects": generate_tms(),
        "smms_defects": generate_smms(),
        "tdms_defects": generate_tdms(),
        "corridor_availability": generate_corridor_availability(),
        "train_timetable": generate_timetable(),
        "goods_forecast": generate_goods_forecast(),
    }

    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    for name, df in datasets.items():
        path = os.path.join(data_dir, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"{name}: {len(df)} rows -> {path}")

    print("\nAll dummy datasets generated successfully.")
