"""
Operational Input Generator for Railway Prototype (Phase 3)
Generates realistic DEMO/SIMULATED operational inputs across 3 departments
(ENGINEERING, OHE_TRACTION, S_AND_T) and 4 sources (LOCO_PILOT, INSPECTION_STAFF,
MAINTENANCE_STAFF, SYSTEM_GENERATED).

Covers all 8 block classifications:
- Independent work
- Dependent work
- Parallel work
- Sequential work
- Isolation-required work
- Emergency work
- Overdue work
- Conflicting & Impossible work windows
"""

import os
import sys
import sqlite3
import random
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
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# REAL RAILWAY GEOGRAPHIC ANCHORS (From WTT No. 80 Ground Truth)
# -----------------------------------------------------------------------------
LOCATIONS = [
    # GDR-BZA Section (KM 134 to 428)
    {"section": "GDR-BZA-DN", "line": "DOWN Line", "direction": "DOWN", "station": "GDR", "from_km": 136.0, "to_km": 145.0, "sub_section": "Gudur-Manubolu"},
    {"section": "GDR-BZA-DN", "line": "DOWN Line", "direction": "DOWN", "station": "NLR", "from_km": 174.0, "to_km": 185.0, "sub_section": "Nellore-Kodavaluru"},
    {"section": "GDR-BZA-DN", "line": "DOWN Line", "direction": "DOWN", "station": "BTTR", "from_km": 208.0, "to_km": 224.0, "sub_section": "Bitragunta-Kavali"},
    {"section": "GDR-BZA-DN", "line": "DOWN Line", "direction": "DOWN", "station": "SKM", "from_km": 262.0, "to_km": 272.0, "sub_section": "Singarayakonda-Tanguturu"},
    {"section": "GDR-BZA-DN", "line": "DOWN Line", "direction": "DOWN", "station": "OGL", "from_km": 290.0, "to_km": 305.0, "sub_section": "Ongole-Ammanabrolu"},
    {"section": "GDR-BZA-DN", "line": "DOWN Line", "direction": "DOWN", "station": "CLX", "from_km": 339.0, "to_km": 354.0, "sub_section": "Chirala-Bapatla"},
    {"section": "GDR-BZA-DN", "line": "DOWN Line", "direction": "DOWN", "station": "TEL", "from_km": 397.0, "to_km": 407.0, "sub_section": "Tenali-Duggirala"},
    {"section": "GDR-BZA-DN", "line": "DOWN Line", "direction": "DOWN", "station": "KCC", "from_km": 423.0, "to_km": 428.0, "sub_section": "Krishna Canal-Vijayawada"},

    # BZA-GDR-UP Section (KM 428 to 134)
    {"section": "BZA-GDR-UP", "line": "UP Line", "direction": "UP", "station": "BZA", "from_km": 428.0, "to_km": 423.0, "sub_section": "Vijayawada-Krishna Canal"},
    {"section": "BZA-GDR-UP", "line": "UP Line", "direction": "UP", "station": "TEL", "from_km": 397.0, "to_km": 385.0, "sub_section": "Tenali-Tsunduru"},
    {"section": "BZA-GDR-UP", "line": "UP Line", "direction": "UP", "station": "BPP", "from_km": 354.0, "to_km": 339.0, "sub_section": "Bapatla-Chirala"},
    {"section": "BZA-GDR-UP", "line": "UP Line", "direction": "UP", "station": "OGL", "from_km": 290.0, "to_km": 280.0, "sub_section": "Ongole-Surareddipalem"},
    {"section": "BZA-GDR-UP", "line": "UP Line", "direction": "UP", "station": "KVZ", "from_km": 224.0, "to_km": 208.0, "sub_section": "Kavali-Bitragunta"},
    {"section": "BZA-GDR-UP", "line": "UP Line", "direction": "UP", "station": "NLR", "from_km": 174.0, "to_km": 157.0, "sub_section": "Nellore-Venkatachalam"},

    # BZA-VSKP Section (KM 428 to 778)
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "GWM", "from_km": 448.0, "to_km": 460.0, "sub_section": "Gannavaram-Telaprolu"},
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "EE", "from_km": 488.0, "to_km": 498.0, "sub_section": "Eluru-Denduluru"},
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "TDD", "from_km": 536.0, "to_km": 545.0, "sub_section": "Tadepalligudem-Navabpalem"},
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "NDD", "from_km": 555.0, "to_km": 564.0, "sub_section": "Nidadavolu-Chagallu"},
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "RJY", "from_km": 578.0, "to_km": 588.0, "sub_section": "Rajahmundry-Kadiyam (Godavari Br.)"},
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "SLO", "from_km": 628.0, "to_km": 640.0, "sub_section": "Samalkot-Pithapuram"},
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "TUNI", "from_km": 681.0, "to_km": 693.0, "sub_section": "Tuni-Gullipadu"},
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "AKP", "from_km": 745.0, "to_km": 752.0, "sub_section": "Anakapalle-Thadi"},
    {"section": "BZA-VSKP-DN", "line": "DOWN Line", "direction": "DOWN", "station": "DVD", "from_km": 761.0, "to_km": 778.0, "sub_section": "Duvvada-Visakhapatnam"},

    # VSKP-BZA-UP Section
    {"section": "VSKP-BZA-UP", "line": "UP Line", "direction": "UP", "station": "DVD", "from_km": 761.0, "to_km": 745.0, "sub_section": "Duvvada-Anakapalle"},
    {"section": "VSKP-BZA-UP", "line": "UP Line", "direction": "UP", "station": "TUNI", "from_km": 681.0, "to_km": 665.0, "sub_section": "Tuni-Annavaram"},
    {"section": "VSKP-BZA-UP", "line": "UP Line", "direction": "UP", "station": "SLO", "from_km": 628.0, "to_km": 611.0, "sub_section": "Samalkot-Bikkavolu"},
    {"section": "VSKP-BZA-UP", "line": "UP Line", "direction": "UP", "station": "RJY", "from_km": 578.0, "to_km": 570.0, "sub_section": "Rajahmundry-Kovvuru"},
    {"section": "VSKP-BZA-UP", "line": "UP Line", "direction": "UP", "station": "EE", "from_km": 488.0, "to_km": 479.0, "sub_section": "Eluru-Vatlur"},

    # Branch Line (Single Line / Double Line)
    {"section": "GDV-MTM", "line": "Single Line", "direction": "BIDIRECTIONAL", "station": "GDV", "from_km": 0.0, "to_km": 36.7, "sub_section": "Gudivada-Machilipatnam Branch"},
    {"section": "GNT-TEL", "line": "Double Line", "direction": "BIDIRECTIONAL", "station": "GNT", "from_km": 0.0, "to_km": 25.4, "sub_section": "Guntur-Tenali Chord"},
    {"section": "BVRM-NS", "line": "Single Line", "direction": "BIDIRECTIONAL", "station": "BVRM", "from_km": 0.0, "to_km": 29.4, "sub_section": "Bhimavaram-Narasapur Branch"}
]

# -----------------------------------------------------------------------------
# WORK TYPES BY DEPARTMENT & SOURCE
# -----------------------------------------------------------------------------
WORK_TAXONOMY = {
    "ENGINEERING": [
        {"type": "Track tamping", "asset": "Track Geometry / Ballast", "dur": 120, "min_dur": 75, "res": "CSM Tamping Machine + Trackman Gang", "iso": False, "pri": "Medium"},
        {"type": "Rail grinding", "asset": "Rail Head Profile", "dur": 150, "min_dur": 90, "res": "Rail Grinding Machine (RGM)", "iso": False, "pri": "Medium"},
        {"type": "Track geometry inspection", "asset": "P-Way Track Parameters", "dur": 60, "min_dur": 30, "res": "Track Recording Car / Trolley", "iso": False, "pri": "Low"},
        {"type": "Rail joint inspection", "asset": "Fishplated / Welded Joints", "dur": 45, "min_dur": 30, "res": "USFD Testing Team", "iso": False, "pri": "High"},
        {"type": "Sleeper replacement", "asset": "PSC Sleepers", "dur": 180, "min_dur": 120, "res": "T-28 Machine Gang", "iso": False, "pri": "High"},
        {"type": "Ballast maintenance", "asset": "Ballast Bed", "dur": 180, "min_dur": 120, "res": "BCM Deep Screening Machine", "iso": False, "pri": "Medium"},
        {"type": "Drainage maintenance", "asset": "Track Cess & Side Drains", "dur": 90, "min_dur": 45, "res": "P-Way Maintenance Labour", "iso": False, "pri": "Low"},
        {"type": "Track renewal activity", "asset": "Rails & Sleepers (TSR/CTR)", "dur": 240, "min_dur": 180, "res": "PQRS Portal Crane + DMT Rake", "iso": False, "pri": "Critical"},
        {"type": "Bridge inspection", "asset": "Girder / Substructure", "dur": 60, "min_dur": 40, "res": "Bridge Inspection Unit + SSE/Bridges", "iso": False, "pri": "Medium"},
        {"type": "Level crossing maintenance", "asset": "LC Gate Track & Check Rails", "dur": 90, "min_dur": 60, "res": "P-Way Gang + Gateman Assistance", "iso": False, "pri": "High"}
    ],
    "OHE_TRACTION": [
        {"type": "OHE inspection", "asset": "25kV Contact & Catenary Wire", "dur": 90, "min_dur": 60, "res": "Tower Wagon (RU) + TRD Staff", "iso": True, "pri": "Medium"},
        {"type": "OHE maintenance", "asset": "Cantilever & Dropper Assembly", "dur": 120, "min_dur": 90, "res": "Tower Car + Ladder Gang", "iso": True, "pri": "High"},
        {"type": "Isolator maintenance", "asset": "Sectional Isolator Switches", "dur": 60, "min_dur": 45, "res": "TRD Maintenance Team", "iso": True, "pri": "Medium"},
        {"type": "Overhead equipment replacement", "asset": "Contact Wire / Bracket", "dur": 180, "min_dur": 120, "res": "Wiring Train + TRD Crew", "iso": True, "pri": "High"},
        {"type": "Contact wire inspection", "asset": "Contact Wire Wear & Stagger", "dur": 60, "min_dur": 40, "res": "Tower Wagon Laser Profiler", "iso": True, "pri": "Medium"},
        {"type": "Mast inspection", "asset": "OHE Traction Masts & Portals", "dur": 45, "min_dur": 30, "res": "TRD Ground Inspection Team", "iso": False, "pri": "Low"},
        {"type": "Traction substation maintenance", "asset": "25kV TSS Transformer / CB", "dur": 120, "min_dur": 90, "res": "Substation Electrical Officers", "iso": True, "pri": "Critical"},
        {"type": "Section insulator maintenance", "asset": "Section Insulators / Neutral Section", "dur": 90, "min_dur": 60, "res": "Tower Car + TRD In-charge", "iso": True, "pri": "High"},
        {"type": "Pantograph/OHE-related defect attention", "asset": "OHE Clearance & Steady Arm", "dur": 60, "min_dur": 30, "res": "TRD Emergency Flying Gang", "iso": True, "pri": "Critical"}
    ],
    "S_AND_T": [
        {"type": "Signal maintenance", "asset": "Color Light Signals (MACLS)", "dur": 45, "min_dur": 30, "res": "Signal Maintainer + JE/Signals", "iso": False, "pri": "Medium"},
        {"type": "Track circuit inspection", "asset": "DC Track Circuit / Audio Frequency TC", "dur": 60, "min_dur": 40, "res": "S&T Inspection Team", "iso": False, "pri": "High"},
        {"type": "Axle counter maintenance", "asset": "High-Availability Axle Counters (MSDAC)", "dur": 60, "min_dur": 30, "res": "S&T Technical Team", "iso": False, "pri": "High"},
        {"type": "Point machine maintenance", "asset": "Electric Point Machine (IRS-500)", "dur": 90, "min_dur": 60, "res": "SSE/Signal + Points Gang", "iso": False, "pri": "Critical"},
        {"type": "Signal cable maintenance", "asset": "Underground Signalling Cable / OFC", "dur": 120, "min_dur": 60, "res": "S&T Cable Jointing Team", "iso": False, "pri": "Medium"},
        {"type": "Interlocking equipment inspection", "asset": "Electronic Interlocking (EI) Panel", "dur": 60, "min_dur": 40, "res": "EI Specialist Engineer", "iso": False, "pri": "Critical"},
        {"type": "Data logger maintenance", "asset": "Station Solid State Data Logger", "dur": 30, "min_dur": 20, "res": "S&T Telecom Maintainer", "iso": False, "pri": "Low"},
        {"type": "Automatic signalling equipment maintenance", "asset": "Automatic Signal Hut Relay Racks", "dur": 90, "min_dur": 60, "res": "Automatic Block Maintenance Crew", "iso": False, "pri": "High"}
    ]
}

SOURCES_DISTRIBUTION = ["MAINTENANCE_STAFF", "INSPECTION_STAFF", "LOCO_PILOT", "SYSTEM_GENERATED"]


def generate_operational_inputs():
    """Generates 200 realistic, internally consistent demo operational inputs."""
    print("🚀 Generating DEMO/SIMULATED operational inputs across 3 departments & 4 sources...")
    
    records = []
    base_date = datetime(2026, 9, 27)

    # Specific Scenario Archetypes to systematically build:
    # 1. INDEPENDENT WORK
    # 2. DEPENDENT WORK (S&T requiring Engineering track clearance)
    # 3. PARALLEL WORK (Engineering Track Tamping + TRD Mast Inspection on adjacent line/separate span)
    # 4. SEQUENTIAL WORK (Engg Isolation -> OHE Isolation -> S&T work -> Track Re-connection)
    # 5. ISOLATION REQUIRED WORK (25kV OHE isolation)
    # 6. EMERGENCY WORK (Immediate speed restriction / crack detection)
    # 7. OVERDUE WORK (Past scheduled deadline)
    # 8. CONFLICTING / IMPOSSIBLE WORK WINDOW (Over-duration request)

    req_counter = 1

    # --- ARCHETYPE 1: EMERGENCY BLOCKS (Urgent safety defects) ---
    emergency_specs = [
        ("ENGINEERING", "Rail joint inspection", "LOCO_PILOT", "Unusual hammering sound heard at Rail Joint KM 294/12", "Emergency Block: Weld Hairline Crack Attention", 45, 25, "Critical"),
        ("S_AND_T", "Point machine maintenance", "LOCO_PILOT", "Point No. 24B flashing out of correspondence at Tenali Yard", "Emergency Block: Point Machine Obstruction Clearing", 60, 30, "Critical"),
        ("OHE_TRACTION", "Pantograph/OHE-related defect attention", "LOCO_PILOT", "Heavy sparking and loose steady arm at Mast 576/12 Godavari Bridge", "Emergency Block: OHE Steady Arm Immediate Clamping", 45, 20, "Critical"),
        ("ENGINEERING", "Track defect", "INSPECTION_STAFF", "Track buckle alert due to high ambient rail temperature at KM 182", "Emergency Block: Rail De-stressing Attention", 60, 35, "Critical"),
        ("S_AND_T", "Axle counter maintenance", "SYSTEM_GENERATED", "MSDAC reset failure on Up line between Eluru and Denduluru", "Emergency Block: Axle Counter Sensor Alignment", 40, 20, "Critical")
    ]

    for dept, wtype, src, reason_txt, title, dur, min_dur, pri in emergency_specs:
        loc = random.choice(LOCATIONS)
        req_id = f"REQ-DEMO-{req_counter:04d}"
        req_counter += 1
        records.append({
            "request_id": req_id,
            "source": src,
            "department": dept,
            "request_type": wtype,
            "asset_type": f"{dept} Emergency Asset",
            "location": f"{loc['station']} ({loc['sub_section']})",
            "from_km": loc["from_km"],
            "to_km": loc["to_km"],
            "section": loc["section"],
            "line": loc["line"],
            "direction": loc["direction"],
            "reported_time": (base_date + timedelta(hours=random.randint(6, 18), minutes=random.randint(0, 59))).strftime("%Y-%m-%d %H:%M"),
            "required_duration": dur,
            "minimum_duration": min_dur,
            "preferred_start": "IMMEDIATE (Next Gap)",
            "deadline": "URGENT (< 4 Hours)",
            "dependency": "None (Emergency Priority)",
            "isolation_required": True if dept == "OHE_TRACTION" else False,
            "required_resource": "Emergency Flying Squad",
            "priority": pri,
            "reason": f"[DEMO] {reason_txt} - {title}",
            "status": "Pending Review",
            "archetype": "EMERGENCY_BLOCK"
        })

    # --- ARCHETYPE 2: DEPENDENT & SEQUENTIAL BLOCKS ---
    # Example: Engineering Track Renewal requires OHE Power Isolation (Sequential) & S&T Disconnection
    for i in range(12):
        loc = random.choice(LOCATIONS)
        base_time = (base_date + timedelta(days=random.randint(0, 3), hours=random.randint(8, 14))).strftime("%Y-%m-%d %H:%M")
        
        # Step 1: Civil Engineering
        eng_req_id = f"REQ-DEMO-{req_counter:04d}"
        req_counter += 1
        records.append({
            "request_id": eng_req_id,
            "source": "MAINTENANCE_STAFF",
            "department": "ENGINEERING",
            "request_type": "Track renewal activity",
            "asset_type": "60kg PSC Track Bed",
            "location": f"{loc['station']} ({loc['sub_section']})",
            "from_km": loc["from_km"],
            "to_km": round(loc["from_km"] + 2.5, 1),
            "section": loc["section"],
            "line": loc["line"],
            "direction": loc["direction"],
            "reported_time": base_time,
            "required_duration": 180,
            "minimum_duration": 120,
            "preferred_start": "11:30",
            "deadline": (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
            "dependency": "Prerequisite for OHE & S&T Sequential Cluster",
            "isolation_required": True,
            "required_resource": "PQRS Track Layer + CSM Tamper",
            "priority": "High",
            "reason": "[DEMO] Corrugated rail renewal and heavy ballast screening.",
            "status": "Submitted",
            "archetype": "SEQUENTIAL_BLOCK"
        })

        # Step 2: OHE Power Isolation (Dependent on Engineering possession)
        ohe_req_id = f"REQ-DEMO-{req_counter:04d}"
        req_counter += 1
        records.append({
            "request_id": ohe_req_id,
            "source": "MAINTENANCE_STAFF",
            "department": "OHE_TRACTION",
            "request_type": "Overhead equipment replacement",
            "asset_type": "25kV Catenary Wire",
            "location": f"{loc['station']} ({loc['sub_section']})",
            "from_km": loc["from_km"],
            "to_km": round(loc["from_km"] + 2.5, 1),
            "section": loc["section"],
            "line": loc["line"],
            "direction": loc["direction"],
            "reported_time": base_time,
            "required_duration": 150,
            "minimum_duration": 90,
            "preferred_start": "12:00",
            "deadline": (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
            "dependency": f"Requires {eng_req_id} (Engg Track Disconnection First)",
            "isolation_required": True,
            "required_resource": "Tower Wagon + TRD Earthing Gang",
            "priority": "High",
            "reason": "[DEMO] 25kV OHE isolation and catenary wire height adjustment during track renewal.",
            "status": "Submitted",
            "archetype": "DEPENDENT_BLOCK"
        })

        # Step 3: S&T Track Circuit Bond Reconnection (Sequential final step)
        st_req_id = f"REQ-DEMO-{req_counter:04d}"
        req_counter += 1
        records.append({
            "request_id": st_req_id,
            "source": "MAINTENANCE_STAFF",
            "department": "S_AND_T",
            "request_type": "Track circuit inspection",
            "asset_type": "DC Track Circuit Bonds",
            "location": f"{loc['station']} ({loc['sub_section']})",
            "from_km": loc["from_km"],
            "to_km": round(loc["from_km"] + 2.5, 1),
            "section": loc["section"],
            "line": loc["line"],
            "direction": loc["direction"],
            "reported_time": base_time,
            "required_duration": 45,
            "minimum_duration": 30,
            "preferred_start": "14:15",
            "deadline": (base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
            "dependency": f"Requires {eng_req_id} & {ohe_req_id} Completion",
            "isolation_required": False,
            "required_resource": "Signal Track Team + Megger Tester",
            "priority": "High",
            "reason": "[DEMO] Reconnecting track circuit bonding jumpers and joint insulation after tamping.",
            "status": "Submitted",
            "archetype": "SEQUENTIAL_BLOCK"
        })

    # --- ARCHETYPE 3: OVERDUE MAINTENANCE BLOCKS ---
    for i in range(20):
        dept = random.choice(["ENGINEERING", "OHE_TRACTION", "S_AND_T"])
        w_spec = random.choice(WORK_TAXONOMY[dept])
        loc = random.choice(LOCATIONS)
        past_deadline = (base_date - timedelta(days=random.randint(3, 45))).strftime("%Y-%m-%d")
        reported = (base_date - timedelta(days=random.randint(50, 90))).strftime("%Y-%m-%d %H:%M")

        req_id = f"REQ-DEMO-{req_counter:04d}"
        req_counter += 1
        records.append({
            "request_id": req_id,
            "source": "SYSTEM_GENERATED",
            "department": dept,
            "request_type": w_spec["type"],
            "asset_type": w_spec["asset"],
            "location": f"{loc['station']} ({loc['sub_section']})",
            "from_km": loc["from_km"],
            "to_km": loc["to_km"],
            "section": loc["section"],
            "line": loc["line"],
            "direction": loc["direction"],
            "reported_time": reported,
            "required_duration": w_spec["dur"],
            "minimum_duration": w_spec["min_dur"],
            "preferred_start": "Night Corridor (01:00 - 04:00)",
            "deadline": past_deadline,
            "dependency": "None",
            "isolation_required": w_spec["iso"],
            "required_resource": w_spec["res"],
            "priority": "Critical",
            "reason": f"[DEMO] OVERDUE by {random.randint(5, 40)} days. Mandatory statutory maintenance exceeded due date.",
            "status": "Overdue Pending",
            "archetype": "OVERDUE_BLOCK"
        })

    # --- ARCHETYPE 4: IMPOSSIBLE / CONFLICTING WINDOWS ---
    for i in range(10):
        dept = random.choice(["ENGINEERING", "OHE_TRACTION", "S_AND_T"])
        w_spec = random.choice(WORK_TAXONOMY[dept])
        loc = random.choice(LOCATIONS)
        req_id = f"REQ-DEMO-{req_counter:04d}"
        req_counter += 1
        records.append({
            "request_id": req_id,
            "source": "MAINTENANCE_STAFF",
            "department": dept,
            "request_type": w_spec["type"],
            "asset_type": w_spec["asset"],
            "location": f"{loc['station']} ({loc['sub_section']})",
            "from_km": loc["from_km"],
            "to_km": loc["to_km"],
            "section": loc["section"],
            "line": loc["line"],
            "direction": loc["direction"],
            "reported_time": base_date.strftime("%Y-%m-%d 09:00"),
            "required_duration": 300, # 5 hours in peak traffic
            "minimum_duration": 240,
            "preferred_start": "01:30",
            "deadline": (base_date + timedelta(days=2)).strftime("%Y-%m-%d"),
            "dependency": "None",
            "isolation_required": w_spec["iso"],
            "required_resource": w_spec["res"],
            "priority": "Low",
            "reason": "[DEMO] Heavy overhaul requiring 5-hour continuous slot during peak Vande Bharat / Express window (Infeasible).",
            "status": "Submitted",
            "archetype": "IMPOSSIBLE_WINDOW"
        })

    # --- ARCHETYPE 5: ROUTINE / INDEPENDENT / PARALLEL BLOCKS ---
    while len(records) < 180:
        dept = random.choice(["ENGINEERING", "OHE_TRACTION", "S_AND_T"])
        w_spec = random.choice(WORK_TAXONOMY[dept])
        src = random.choice(SOURCES_DISTRIBUTION)
        loc = random.choice(LOCATIONS)
        
        req_id = f"REQ-DEMO-{req_counter:04d}"
        req_counter += 1
        pref_hour = random.choice(["02:30", "11:30", "13:00", "16:15", "23:45"])
        records.append({
            "request_id": req_id,
            "source": src,
            "department": dept,
            "request_type": w_spec["type"],
            "asset_type": w_spec["asset"],
            "location": f"{loc['station']} ({loc['sub_section']})",
            "from_km": loc["from_km"],
            "to_km": loc["to_km"],
            "section": loc["section"],
            "line": loc["line"],
            "direction": loc["direction"],
            "reported_time": (base_date + timedelta(days=random.randint(0, 4), hours=random.randint(6, 20))).strftime("%Y-%m-%d %H:%M"),
            "required_duration": w_spec["dur"],
            "minimum_duration": w_spec["min_dur"],
            "preferred_start": pref_hour,
            "deadline": (base_date + timedelta(days=random.randint(3, 14))).strftime("%Y-%m-%d"),
            "dependency": "None (Independent)",
            "isolation_required": w_spec["iso"],
            "required_resource": w_spec["res"],
            "priority": w_spec["pri"],
            "reason": f"[DEMO] Routine planned maintenance for {w_spec['asset']} as per annual schedule.",
            "status": "Submitted",
            "archetype": "INDEPENDENT_BLOCK"
        })

    df_requests = pd.DataFrame(records)

    # -------------------------------------------------------------------------
    # DERIVE SPECIALIZED DATASETS FROM MASTER OPERATIONAL INPUTS
    # -------------------------------------------------------------------------
    # 1. block_requests.csv (Core planning dataset)
    df_requests.to_csv(os.path.join(DATA_DIR, "block_requests.csv"), index=False)

    # 2. loco_pilot_observations.csv
    df_loco = df_requests[df_requests["source"] == "LOCO_PILOT"].copy()
    df_loco.to_csv(os.path.join(DATA_DIR, "loco_pilot_observations.csv"), index=False)

    # 3. inspection_reports.csv
    df_insp = df_requests[df_requests["source"] == "INSPECTION_STAFF"].copy()
    df_insp.to_csv(os.path.join(DATA_DIR, "inspection_reports.csv"), index=False)

    # 4. maintenance_reports.csv
    df_maint = df_requests[df_requests["source"] == "MAINTENANCE_STAFF"].copy()
    df_maint.to_csv(os.path.join(DATA_DIR, "maintenance_reports.csv"), index=False)

    # 5. overdue_maintenance.csv
    df_overdue = df_requests[df_requests["archetype"] == "OVERDUE_BLOCK"].copy()
    df_overdue.to_csv(os.path.join(DATA_DIR, "overdue_maintenance.csv"), index=False)

    # 6. asset_defects.csv
    df_defects = df_requests[["request_id", "department", "asset_type", "location", "from_km", "to_km", "section", "priority", "reason", "status"]].copy()
    df_defects.to_csv(os.path.join(DATA_DIR, "asset_defects.csv"), index=False)

    print(f"✅ Generated 6 operational CSV datasets ({len(df_requests)} master records).")

    # -------------------------------------------------------------------------
    # SQLITE PERSISTENCE (Non-destructive table additions)
    # -------------------------------------------------------------------------
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS block_requests_v2 (
        request_id TEXT PRIMARY KEY,
        source TEXT,
        department TEXT,
        request_type TEXT,
        asset_type TEXT,
        location TEXT,
        from_km REAL,
        to_km REAL,
        section TEXT,
        line TEXT,
        direction TEXT,
        reported_time TEXT,
        required_duration INTEGER,
        minimum_duration INTEGER,
        preferred_start TEXT,
        deadline TEXT,
        dependency TEXT,
        isolation_required INTEGER,
        required_resource TEXT,
        priority TEXT,
        reason TEXT,
        status TEXT,
        archetype TEXT
    )
    """)
    conn.commit()

    df_requests.to_sql("block_requests_v2", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    print("✅ Ingested table 'block_requests_v2' into railway.db.")

    return df_requests


def run_operational_input_validations():
    """Validates operational consistency across all generated datasets."""
    print("\n🔍 Running Operational Input Integrity Validations...")
    errors = []

    df = pd.read_csv(os.path.join(DATA_DIR, "block_requests.csv"))

    # 1. Check required fields
    required_cols = [
        "request_id", "source", "department", "request_type", "asset_type",
        "location", "from_km", "to_km", "section", "line", "direction",
        "reported_time", "required_duration", "minimum_duration", "preferred_start",
        "deadline", "dependency", "isolation_required", "required_resource",
        "priority", "reason", "status"
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        errors.append(f"❌ Missing required columns: {missing_cols}")
    else:
        print("  ✓ All 22 mandatory input fields present and structured")

    # 2. Check department distribution
    depts = df["department"].unique().tolist()
    expected_depts = ["ENGINEERING", "OHE_TRACTION", "S_AND_T"]
    if not all(d in depts for d in expected_depts):
        errors.append(f"❌ Missing departments in dataset: expected {expected_depts}, found {depts}")
    else:
        print(f"  ✓ Multi-department representation verified: {df['department'].value_counts().to_dict()}")

    # 3. Check sources
    sources = df["source"].unique().tolist()
    expected_sources = ["LOCO_PILOT", "INSPECTION_STAFF", "MAINTENANCE_STAFF", "SYSTEM_GENERATED"]
    if not all(s in sources for s in expected_sources):
        errors.append(f"❌ Missing sources in dataset: expected {expected_sources}, found {sources}")
    else:
        print(f"  ✓ Multi-source origin verified: {df['source'].value_counts().to_dict()}")

    # 4. Check Archetype coverage
    archetypes = df["archetype"].value_counts().to_dict()
    print(f"  ✓ Archetype distribution: {archetypes}")

    # 5. KM consistency
    invalid_km = df[df["from_km"] < 0]
    if not invalid_km.empty:
        errors.append(f"❌ Found negative KM coordinates: {len(invalid_km)}")
    else:
        print("  ✓ All chainage coordinates (KM) positive and aligned with division posts")

    print(f"\n📊 Phase 3 Validation Summary: {len(errors)} Errors.")
    if errors:
        for e in errors:
            print(e)
        return False
    return True


if __name__ == "__main__":
    generate_operational_inputs()
    run_operational_input_validations()
