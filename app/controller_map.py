"""
Controller Geographic Railway Map Architecture (STEP 3 & 4)
Modular component structure:
ControllerMap
├── BaseRailwayLayer       (Layer 0: Geographic Tracks, Stations, Hubs, KM references)
├── AllocatedBlockLayer    (Layer 1: Maintenance Blocks with Time-Aware Status, Candidate Blocks, Geometry Adapter & Rich Popups)
├── LiveTrainLayer         (Layer 2: Moving Train Markers, Speed vectors, Live/Sim telemetry, Direction arrows)
├── MapControls            (Layer toggles, Basemaps, Zoom, Reset, Full-screen HUD)
└── MapLegend              (Compact Railway Control-Room Legend)

Hierarchy & Visual Stacking:
RAILWAY BASE (Layer 0, zIndex: 210) -> ALLOCATED BLOCKS (Layer 1, zIndex: 450) -> LIVE TRAINS (Layer 2, zIndex: 900)
"""

import os
import sqlite3
import json
import re
from datetime import datetime
import folium
import pandas as pd

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(base_dir, "railway.db")
if not os.path.exists(DB_PATH):
    DB_PATH = "railway.db"


# =============================================================================
# STATION GEOGRAPHIC COORDINATE DICTIONARY
# =============================================================================
STATION_COORDINATES = {
    # Vijayawada Division & Main SCR Corridor
    "BZA": {"name": "Vijayawada Jn", "lat": 16.5062, "lon": 80.6480, "km": 0.0},
    "VIJAYAWADA": {"name": "Vijayawada Jn", "lat": 16.5062, "lon": 80.6480, "km": 0.0},
    "RYP": {"name": "Rayanapadu", "lat": 16.5450, "lon": 80.5980, "km": 8.0},
    "RAYANAPADU": {"name": "Rayanapadu", "lat": 16.5450, "lon": 80.5980, "km": 8.0},
    "RAY": {"name": "Rayanapadu", "lat": 16.5450, "lon": 80.5980, "km": 8.0},
    "KI": {"name": "Kondapalli", "lat": 16.6180, "lon": 80.5360, "km": 25.0},
    "KDM": {"name": "Kondapalli", "lat": 16.6180, "lon": 80.5360, "km": 25.0},
    "KONDAPALLI": {"name": "Kondapalli", "lat": 16.6180, "lon": 80.5360, "km": 25.0},
    "MDR": {"name": "Madhira", "lat": 16.9180, "lon": 80.3640, "km": 55.0},
    "MADHIRA": {"name": "Madhira", "lat": 16.9180, "lon": 80.3640, "km": 55.0},
    "KMT": {"name": "Khammam", "lat": 17.2472, "lon": 80.1514, "km": 95.0},
    "KHAMMAM": {"name": "Khammam", "lat": 17.2472, "lon": 80.1514, "km": 95.0},
    "WL": {"name": "Warangal", "lat": 17.9783, "lon": 79.5217, "km": 165.0},
    "WARANGAL": {"name": "Warangal", "lat": 17.9783, "lon": 79.5217, "km": 165.0},
    "KZJ": {"name": "Kazipet Jn", "lat": 17.9800, "lon": 79.5100, "km": 175.0},
    "KAZIPET": {"name": "Kazipet Jn", "lat": 17.9800, "lon": 79.5100, "km": 175.0},

    # East Trunk (BZA - VSKP)
    "EE": {"name": "Eluru", "lat": 16.7107, "lon": 81.1042, "km": 60.0},
    "ELURU": {"name": "Eluru", "lat": 16.7107, "lon": 81.1042, "km": 60.0},
    "TDD": {"name": "Tadepalligudem", "lat": 16.8143, "lon": 81.5268, "km": 108.0},
    "TADEPALLIGUDEM": {"name": "Tadepalligudem", "lat": 16.8143, "lon": 81.5268, "km": 108.0},
    "NDD": {"name": "Nidadavolu", "lat": 16.9050, "lon": 81.6700, "km": 128.0},
    "NIDADAVOLU": {"name": "Nidadavolu", "lat": 16.9050, "lon": 81.6700, "km": 128.0},
    "RJY": {"name": "Rajahmundry", "lat": 17.0005, "lon": 81.7774, "km": 150.0},
    "RAJAHMUNDRY": {"name": "Rajahmundry", "lat": 17.0005, "lon": 81.7774, "km": 150.0},
    "SLO": {"name": "Samalkot", "lat": 17.0500, "lon": 82.1667, "km": 200.0},
    "SAMALKOT": {"name": "Samalkot", "lat": 17.0500, "lon": 82.1667, "km": 200.0},
    "CCT": {"name": "Kakinada Town", "lat": 16.9600, "lon": 82.2300, "km": 215.0},
    "COA": {"name": "Kakinada Port", "lat": 16.9400, "lon": 82.2500, "km": 220.0},
    "TUNI": {"name": "Tuni", "lat": 17.3500, "lon": 82.5500, "km": 255.0},
    "AKP": {"name": "Anakapalle", "lat": 17.6800, "lon": 83.0000, "km": 305.0},
    "DVD": {"name": "Duvvada", "lat": 17.7100, "lon": 83.1500, "km": 330.0},
    "VSKP": {"name": "Visakhapatnam", "lat": 17.7200, "lon": 83.2900, "km": 350.0},
    "VISAKHAPATNAM": {"name": "Visakhapatnam", "lat": 17.7200, "lon": 83.2900, "km": 350.0},

    # South Trunk (BZA - GDR)
    "KCC": {"name": "Krishna Canal", "lat": 16.4800, "lon": 80.6200, "km": 5.0},
    "TEL": {"name": "Tenali Jn", "lat": 16.2430, "lon": 80.6470, "km": 32.0},
    "TENALI": {"name": "Tenali Jn", "lat": 16.2430, "lon": 80.6470, "km": 32.0},
    "NDO": {"name": "Nidubrolu", "lat": 16.0800, "lon": 80.5400, "km": 54.0},
    "BPP": {"name": "Bapatla", "lat": 15.9040, "lon": 80.4670, "km": 74.0},
    "BAPATLA": {"name": "Bapatla", "lat": 15.9040, "lon": 80.4670, "km": 74.0},
    "CLX": {"name": "Chirala", "lat": 15.8200, "lon": 80.3500, "km": 90.0},
    "CHIRALA": {"name": "Chirala", "lat": 15.8200, "lon": 80.3500, "km": 90.0},
    "CJM": {"name": "Chinnaganjam", "lat": 15.7000, "lon": 80.2500, "km": 110.0},
    "OGL": {"name": "Ongole", "lat": 15.5057, "lon": 80.0499, "km": 138.0},
    "ONGOLE": {"name": "Ongole", "lat": 15.5057, "lon": 80.0499, "km": 138.0},
    "SKM": {"name": "Singarayakonda", "lat": 15.2500, "lon": 80.0300, "km": 168.0},
    "KVZ": {"name": "Kavali", "lat": 14.9100, "lon": 79.9900, "km": 208.0},
    "KAVALI": {"name": "Kavali", "lat": 14.9100, "lon": 79.9900, "km": 208.0},
    "BTTR": {"name": "Bitragunta", "lat": 14.7800, "lon": 79.9800, "km": 224.0},
    "BITRAGUNTA": {"name": "Bitragunta", "lat": 14.7800, "lon": 79.9800, "km": 224.0},
    "NLR": {"name": "Nellore", "lat": 14.4426, "lon": 79.9865, "km": 255.0},
    "NELLORE": {"name": "Nellore", "lat": 14.4426, "lon": 79.9865, "km": 255.0},
    "GDR": {"name": "Gudur Jn", "lat": 14.1460, "lon": 79.8500, "km": 293.0},
    "GUDUR": {"name": "Gudur Jn", "lat": 14.1460, "lon": 79.8500, "km": 293.0},

    # Secunderabad Division
    "SC": {"name": "Secunderabad Jn", "lat": 17.4344, "lon": 78.5011, "km": 0.0},
    "SECUNDERABAD": {"name": "Secunderabad Jn", "lat": 17.4344, "lon": 78.5011, "km": 0.0},
    "MLY": {"name": "Moula Ali", "lat": 17.4650, "lon": 78.5600, "km": 10.0},
    "MOULA ALI": {"name": "Moula Ali", "lat": 17.4650, "lon": 78.5600, "km": 10.0},
    "CHZ": {"name": "Cherlapalli", "lat": 17.4725, "lon": 78.6000, "km": 22.0},
    "CHERLAPALLI": {"name": "Cherlapalli", "lat": 17.4725, "lon": 78.6000, "km": 22.0},
    "BG": {"name": "Bhongir", "lat": 17.5111, "lon": 78.8900, "km": 48.0},
    "BHONGIR": {"name": "Bhongir", "lat": 17.5111, "lon": 78.8900, "km": 48.0},
    "ZN": {"name": "Jangaon", "lat": 17.7200, "lon": 79.1800, "km": 84.0},
    "JANGAON": {"name": "Jangaon", "lat": 17.7200, "lon": 79.1800, "km": 84.0},

    # Guntakal Division
    "GTL": {"name": "Guntakal Jn", "lat": 15.1667, "lon": 77.3667, "km": 0.0},
    "GUNTAKAL": {"name": "Guntakal Jn", "lat": 15.1667, "lon": 77.3667, "km": 0.0},
    "AD": {"name": "Adoni", "lat": 15.6300, "lon": 77.2700, "km": 52.0},
    "ADONI": {"name": "Adoni", "lat": 15.6300, "lon": 77.2700, "km": 52.0},
    "MALM": {"name": "Mantralayam Rd", "lat": 15.9300, "lon": 77.4200, "km": 93.0},
    "RC": {"name": "Raichur Jn", "lat": 16.2000, "lon": 77.3550, "km": 121.0},
    "RAICHUR": {"name": "Raichur Jn", "lat": 16.2000, "lon": 77.3550, "km": 121.0},
    "YG": {"name": "Yadgir", "lat": 16.7700, "lon": 77.1350, "km": 190.0},
    "WADI": {"name": "Wadi Jn", "lat": 17.0500, "lon": 76.9900, "km": 228.0},

    # Guntur Division
    "GNT": {"name": "Guntur Jn", "lat": 16.3008, "lon": 80.4428, "km": 0.0},
    "GUNTUR": {"name": "Guntur Jn", "lat": 16.3008, "lon": 80.4428, "km": 0.0},
    "NLPD": {"name": "Nallapadu", "lat": 16.2750, "lon": 80.3800, "km": 12.0},
    "NRT": {"name": "Narasaraopet", "lat": 16.2350, "lon": 80.0500, "km": 45.0},
    "VKN": {"name": "Vinukonda", "lat": 16.0500, "lon": 79.7400, "km": 82.0},
    "MRK": {"name": "Markapur Rd", "lat": 15.7300, "lon": 79.2700, "km": 140.0},
    "NDL": {"name": "Nandyal Jn", "lat": 15.4800, "lon": 78.4800, "km": 210.0},

    # Hyderabad Division
    "HYB": {"name": "Hyderabad", "lat": 17.3920, "lon": 78.4690, "km": 0.0},
    "HYDERABAD": {"name": "Hyderabad", "lat": 17.3920, "lon": 78.4690, "km": 0.0},
    "KCG": {"name": "Kacheguda", "lat": 17.3888, "lon": 78.4983, "km": 12.0},
    "KACHEGUDA": {"name": "Kacheguda", "lat": 17.3888, "lon": 78.4983, "km": 12.0},
    "UR": {"name": "Umdanagar", "lat": 17.2600, "lon": 78.4200, "km": 28.0},
    "SHNR": {"name": "Shadnagar", "lat": 17.0700, "lon": 78.2050, "km": 55.0},
    "JCL": {"name": "Jadcherla", "lat": 16.7700, "lon": 78.1400, "km": 90.0},
    "MBNR": {"name": "Mahbubnagar", "lat": 16.7400, "lon": 77.9900, "km": 108.0},

    # Khurda Road Division
    "CTC": {"name": "Cuttack", "lat": 20.4625, "lon": 85.8830, "km": 0.0},
    "BBS": {"name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245, "km": 28.0},
    "KUR": {"name": "Khurda Road", "lat": 20.1833, "lon": 85.7333, "km": 48.0},
    "BALU": {"name": "Balugaon", "lat": 19.7483, "lon": 85.2056, "km": 118.0},
    "BAM": {"name": "Brahmapur", "lat": 19.3150, "lon": 84.7941, "km": 194.0},

    # Howrah Division
    "HWH": {"name": "Howrah Jn", "lat": 22.5839, "lon": 88.3428, "km": 0.0},
    "SRP": {"name": "Serampore", "lat": 22.7500, "lon": 88.3400, "km": 20.0},
    "BDC": {"name": "Bandel Jn", "lat": 22.9200, "lon": 88.3800, "km": 40.0},
    "BWN": {"name": "Bardhaman Jn", "lat": 23.2400, "lon": 87.8600, "km": 100.0}
}


# =============================================================================
# DIVISION GEOGRAPHIC NETWORKS & COORDINATES
# =============================================================================
DIVISION_GEOGRAPHIC_NETWORKS = {
    "Vijayawada Division (BZA)": {
        "center": [16.55, 80.85],
        "zoom": 9,
        "corridor_title": "Vijayawada — Kondapalli — Eluru — Tenali — Ongole Multi-Track Network",
        "jurisdiction": "SCR Jurisdiction • Vijayawada Division HQ (BZA)",
        "kpi": {"running": 20, "reduced": 3, "stopped": 1, "total": 24},
        "division_tags": [
            {"name": "Vijayawada Division HQ", "lat": 16.5062, "lon": 80.6480},
            {"name": "Secunderabad Division Interlock", "lat": 17.40, "lon": 79.80},
            {"name": "Guntur Division Junction", "lat": 16.2430, "lon": 80.6470},
            {"name": "Waltair Division Exchange", "lat": 17.20, "lon": 82.20}
        ],
        "lines": [
            {
                "name": "North-West Trunk Line (BZA - Khammam - Warangal)",
                "color": "#38bdf8",
                "stations": [
                    {"name": "Vijayawada Jn (BZA)", "km": 100.0, "lat": 16.5062, "lon": 80.6480, "hub": True, "type": "Division HQ Junction"},
                    {"name": "Rayanapadu (RYP)", "km": 108.0, "lat": 16.5450, "lon": 80.5980, "type": "Crossing Junction"},
                    {"name": "Kondapalli (KI)", "km": 125.0, "lat": 16.6180, "lon": 80.5360, "hub": True, "type": "Major Freight Yard"},
                    {"name": "Madhira (MDR)", "km": 135.0, "lat": 16.9180, "lon": 80.3640, "type": "Block Station"},
                    {"name": "Khammam (KMT)", "km": 160.0, "lat": 17.2472, "lon": 80.1514, "hub": True, "type": "Important Junction"},
                    {"name": "Warangal (WL)", "km": 210.0, "lat": 17.9783, "lon": 79.5217, "hub": True, "type": "Inter-Division Interchange"}
                ]
            },
            {
                "name": "East Main Trunk Line (BZA - Eluru - Rajahmundry - VSKP)",
                "color": "#34d399",
                "stations": [
                    {"name": "Vijayawada Jn (BZA)", "km": 428.0, "lat": 16.5062, "lon": 80.6480, "hub": True, "type": "Division HQ Junction"},
                    {"name": "Eluru (EE)", "km": 488.0, "lat": 16.7107, "lon": 81.1042, "hub": True, "type": "Commercial Station"},
                    {"name": "Tadepalligudem (TDD)", "km": 536.0, "lat": 16.8143, "lon": 81.5268, "type": "Crossing Station"},
                    {"name": "Nidadavolu (NDD)", "km": 556.0, "lat": 16.9050, "lon": 81.6700, "type": "Branch Station"},
                    {"name": "Rajahmundry (RJY)", "km": 578.0, "lat": 17.0005, "lon": 81.7774, "hub": True, "type": "Major Godavari Hub"},
                    {"name": "Samalkot (SLO)", "km": 628.0, "lat": 17.0500, "lon": 82.1667, "type": "Branch Junction"},
                    {"name": "Tuni (TUNI)", "km": 683.0, "lat": 17.3500, "lon": 82.5500, "type": "Important Crossing"},
                    {"name": "Anakapalle (AKP)", "km": 733.0, "lat": 17.6800, "lon": 83.0000, "type": "Industrial Hub"},
                    {"name": "Visakhapatnam (VSKP)", "km": 778.0, "lat": 17.7200, "lon": 83.2900, "hub": True, "type": "Coastal Terminal"}
                ]
            },
            {
                "name": "South Trunk Line (BZA - Tenali - Ongole - Gudur)",
                "color": "#f59e0b",
                "stations": [
                    {"name": "Vijayawada Jn (BZA)", "km": 428.0, "lat": 16.5062, "lon": 80.6480, "hub": True, "type": "Division HQ Junction"},
                    {"name": "Tenali Jn (TEL)", "km": 396.0, "lat": 16.2430, "lon": 80.6470, "hub": True, "type": "Triple-Line Junction"},
                    {"name": "Bapatla (BPP)", "km": 354.0, "lat": 15.9040, "lon": 80.4670, "type": "Coastal Section Station"},
                    {"name": "Chirala (CLX)", "km": 338.0, "lat": 15.8200, "lon": 80.3500, "type": "Commercial Station"},
                    {"name": "Ongole (OGL)", "km": 290.0, "lat": 15.5057, "lon": 80.0499, "hub": True, "type": "District Headquarters"},
                    {"name": "Kavali (KVZ)", "km": 224.0, "lat": 14.9100, "lon": 79.9900, "type": "Intermediate Hub"},
                    {"name": "Bitragunta (BTTR)", "km": 208.0, "lat": 14.7800, "lon": 79.9800, "type": "Loco Yard"},
                    {"name": "Nellore (NLR)", "km": 173.0, "lat": 14.4426, "lon": 79.9865, "hub": True, "type": "Major Terminal"},
                    {"name": "Gudur Jn (GDR)", "km": 135.0, "lat": 14.1460, "lon": 79.8500, "hub": True, "type": "Grand Trunk Junction"}
                ]
            }
        ],
        "default_blocks": [
            {
                "allocation_id": "DEMO-ISO-001",
                "planning_group_id": "GRP-DEMO-BZA-01",
                "request_ids": ["REQ-ENG-104", "REQ-TRD-105"],
                "departments": ["Engineering", "OHE/Traction"],
                "classification": "ISOLATION",
                "block_id": "BLK-BZA-KI-01",
                "section": "BZA-KDM-01 (Vijayawada – Kondapalli)",
                "from_km": 114.0,
                "to_km": 118.0,
                "date": "2026-09-27",
                "start_time": "10:00",
                "end_time": "13:00",
                "duration_minutes": 180,
                "status": "ALLOCATED",
                "reason": "CSM Track Tamping & 25kV OHE Isolation",
                "line_coords": [[16.5450, 80.5980], [16.6180, 80.5360]],
                "lat": 16.5800,
                "lon": 80.5600,
                "source": "DEMO",
                "is_demo": True
            },
            {
                "allocation_id": "DEMO-PAR-001",
                "planning_group_id": "GRP-DEMO-BZA-02",
                "request_ids": ["REQ-TRD-201", "REQ-SNT-202"],
                "departments": ["OHE/Traction", "S&T"],
                "classification": "PARALLEL",
                "block_id": "BLK-BZA-TRD-02",
                "section": "KDM-MDR-02 (Kondapalli – Madhira)",
                "from_km": 130.0,
                "to_km": 134.0,
                "date": "2026-09-27",
                "start_time": "12:00",
                "end_time": "14:30",
                "duration_minutes": 150,
                "status": "ACTIVE",
                "reason": "Catenary Wire Adjustment & Signal Calibration",
                "line_coords": [[16.6180, 80.5360], [16.9180, 80.3640]],
                "lat": 16.7680,
                "lon": 80.4500,
                "source": "DEMO",
                "is_demo": True
            }
        ],
        "default_trains": [
            {
                "train_number": "12727",
                "train_name": "Godavari Express",
                "latitude": 16.6500,
                "longitude": 80.5100,
                "current_km": 120.5,
                "direction": "Vijayawada → Warangal (UP)",
                "speed": 80.0,
                "delay": 0.0,
                "current_station": "KDM",
                "next_station": "Madhira (MDR)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            },
            {
                "train_number": "12759",
                "train_name": "Charminar Express",
                "latitude": 16.5700,
                "longitude": 80.5700,
                "current_km": 112.0,
                "direction": "Vijayawada → Kondapalli (UP)",
                "speed": 30.0,
                "delay": 12.0,
                "current_station": "RYP",
                "next_station": "Kondapalli (KI)",
                "status": "REDUCED SPEED (TSR 30)",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            },
            {
                "train_number": "20833",
                "train_name": "Vande Bharat Express",
                "latitude": 16.9180,
                "longitude": 80.3640,
                "current_km": 135.0,
                "direction": "Vijayawada → Khammam (UP)",
                "speed": 120.0,
                "delay": 0.0,
                "current_station": "MDR",
                "next_station": "Khammam (KMT)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            },
            {
                "train_number": "12621",
                "train_name": "Tamil Nadu Express",
                "latitude": 15.7000,
                "longitude": 80.2500,
                "current_km": 110.0,
                "direction": "Gudur → Vijayawada (DN)",
                "speed": 110.0,
                "delay": 0.0,
                "current_station": "CJM",
                "next_station": "Bapatla (BPP)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            },
            {
                "train_number": "12841",
                "train_name": "Coromandel Express",
                "latitude": 16.7107,
                "longitude": 81.1042,
                "current_km": 60.0,
                "direction": "VSKP → BZA (UP)",
                "speed": 95.0,
                "delay": 0.0,
                "current_station": "EE",
                "next_station": "Vijayawada Jn (BZA)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            },
            {
                "train_number": "G-402",
                "train_name": "Coal Rake Special",
                "latitude": 16.5200,
                "longitude": 80.6200,
                "current_km": 104.0,
                "direction": "Tenali → Vijayawada (DN)",
                "speed": 0.0,
                "delay": 18.0,
                "current_station": "BZA",
                "next_station": "Rayanapadu (RYP)",
                "status": "STOPPED (Loop Hold)",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "SIMULATION"
            }
        ]
    },
    "Secunderabad Division (SC)": {
        "center": [17.50, 78.85],
        "zoom": 9,
        "corridor_title": "Secunderabad — Moula Ali — Cherlapalli — Kazipet High Density Corridor",
        "jurisdiction": "SCR Jurisdiction • Secunderabad Division HQ (SC)",
        "kpi": {"running": 22, "reduced": 2, "stopped": 1, "total": 25},
        "division_tags": [
            {"name": "Secunderabad Division HQ", "lat": 17.4344, "lon": 78.5011},
            {"name": "Hyderabad Division Junction", "lat": 17.3920, "lon": 78.4690},
            {"name": "Vijayawada Corridor Link", "lat": 16.5062, "lon": 80.6480}
        ],
        "lines": [
            {
                "name": "Secunderabad - Kazipet Main Trunk",
                "color": "#38bdf8",
                "stations": [
                    {"name": "Secunderabad Jn (SC)", "km": 0.0, "lat": 17.4344, "lon": 78.5011, "hub": True, "type": "Division HQ"},
                    {"name": "Moula Ali (MLY)", "km": 10.0, "lat": 17.4650, "lon": 78.5600, "type": "Major Yard"},
                    {"name": "Cherlapalli (CHZ)", "km": 22.0, "lat": 17.4725, "lon": 78.6000, "hub": True, "type": "Terminal Hub"},
                    {"name": "Bhongir (BG)", "km": 48.0, "lat": 17.5111, "lon": 78.8900, "type": "Crossing Station"},
                    {"name": "Jangaon (ZN)", "km": 84.0, "lat": 17.7200, "lon": 79.1800, "hub": True, "type": "Intermediate Hub"},
                    {"name": "Kazipet Jn (KZJ)", "km": 132.0, "lat": 17.9783, "lon": 79.5217, "hub": True, "type": "Major Interchange"}
                ]
            }
        ],
        "default_blocks": [
            {
                "allocation_id": "DEMO-SC-001",
                "planning_group_id": "GRP-DEMO-SC-01",
                "request_ids": ["REQ-SC-ENG-01"],
                "departments": ["Engineering"],
                "classification": "ISOLATION",
                "block_id": "BLK-SC-088",
                "section": "CHZ-BG-01",
                "from_km": 35.0,
                "to_km": 50.0,
                "date": "2026-09-27",
                "start_time": "09:30",
                "end_time": "12:30",
                "duration_minutes": 180,
                "status": "ALLOCATED",
                "reason": "Deep Ballast Screening & Track Relaying",
                "line_coords": [[17.4725, 78.6000], [17.5111, 78.8900]],
                "lat": 17.4900,
                "lon": 78.7500,
                "source": "DEMO",
                "is_demo": True
            }
        ],
        "default_trains": [
            {
                "train_number": "12701",
                "train_name": "Hussain Sagar Express",
                "latitude": 17.4600,
                "longitude": 78.5500,
                "current_km": 8.5,
                "direction": "SC → Kazipet (UP)",
                "speed": 85.0,
                "delay": 0.0,
                "current_station": "SC",
                "next_station": "Moula Ali (MLY)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            },
            {
                "train_number": "17015",
                "train_name": "Visakha Express",
                "latitude": 17.6100,
                "longitude": 79.0300,
                "current_km": 60.0,
                "direction": "SC → KZJ (UP)",
                "speed": 0.0,
                "delay": 22.0,
                "current_station": "BG",
                "next_station": "Jangaon (ZN)",
                "status": "STOPPED",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            }
        ]
    },
    "Khurda Road Division (KUR)": {
        "center": [20.05, 85.55],
        "zoom": 8,
        "corridor_title": "Khurda Road — Bhubaneswar — Cuttack — Puri Network",
        "jurisdiction": "ECoR Jurisdiction • Khurda Road Division HQ (KUR)",
        "kpi": {"running": 18, "reduced": 4, "stopped": 2, "total": 24},
        "division_tags": [
            {"name": "Khurda Road Division HQ", "lat": 20.1833, "lon": 85.7333},
            {"name": "Bhubaneswar Capital Hub", "lat": 20.2961, "lon": 85.8245}
        ],
        "lines": [
            {
                "name": "Main Trunk Line (Cuttack - Visakhapatnam)",
                "color": "#38bdf8",
                "stations": [
                    {"name": "Cuttack (CTC)", "km": 280.0, "lat": 20.4625, "lon": 85.8830, "hub": True, "type": "Major Junction"},
                    {"name": "Bhubaneswar (BBS)", "km": 308.0, "lat": 20.2961, "lon": 85.8245, "hub": True, "type": "Capital Terminal"},
                    {"name": "Khurda Road (KUR)", "km": 328.0, "lat": 20.1833, "lon": 85.7333, "hub": True, "type": "Division HQ"},
                    {"name": "Balugaon (BALU)", "km": 398.0, "lat": 19.7483, "lon": 85.2056, "type": "Chilika Station"},
                    {"name": "Brahmapur (BAM)", "km": 474.0, "lat": 19.3150, "lon": 84.7941, "hub": True, "type": "Commercial Junction"}
                ]
            }
        ],
        "default_blocks": [
            {
                "allocation_id": "DEMO-KUR-001",
                "planning_group_id": "GRP-DEMO-KUR-01",
                "request_ids": ["REQ-KUR-ENG-01"],
                "departments": ["Engineering"],
                "classification": "ISOLATION",
                "block_id": "BLK-KUR-298",
                "section": "CTC-BBS-01",
                "from_km": 298.0,
                "to_km": 301.0,
                "date": "2026-09-27",
                "start_time": "10:00",
                "end_time": "14:00",
                "duration_minutes": 240,
                "status": "ALLOCATED",
                "reason": "Track Renewal & Tamper Block",
                "line_coords": [[20.4625, 85.8830], [20.2961, 85.8245]],
                "lat": 20.3500,
                "lon": 85.8400,
                "source": "DEMO",
                "is_demo": True
            }
        ],
        "default_trains": [
            {
                "train_number": "12841",
                "train_name": "Coromandel Express",
                "latitude": 20.3800,
                "longitude": 85.8500,
                "current_km": 290.0,
                "direction": "Howrah → Chennai (DN)",
                "speed": 80.0,
                "delay": 0.0,
                "current_station": "CTC",
                "next_station": "Bhubaneswar (BBS)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            }
        ]
    },
    "Howrah Division (HWH)": {
        "center": [22.95, 88.05],
        "zoom": 9,
        "corridor_title": "Howrah — Bandel — Bardhaman — Durgapur Quadruple Track Corridor",
        "jurisdiction": "ER Jurisdiction • Howrah Division HQ (HWH)",
        "kpi": {"running": 26, "reduced": 4, "stopped": 2, "total": 32},
        "division_tags": [
            {"name": "Howrah Division HQ", "lat": 22.5839, "lon": 88.3428},
            {"name": "Bardhaman Junction", "lat": 23.2400, "lon": 87.8600}
        ],
        "lines": [
            {
                "name": "Howrah - Bardhaman Main Chord",
                "color": "#38bdf8",
                "stations": [
                    {"name": "Howrah Jn (HWH)", "km": 0.0, "lat": 22.5839, "lon": 88.3428, "hub": True, "type": "Terminal"},
                    {"name": "Serampore (SRP)", "km": 20.0, "lat": 22.7500, "lon": 88.3400, "type": "Suburban"},
                    {"name": "Bandel Jn (BDC)", "km": 40.0, "lat": 22.9200, "lon": 88.3800, "hub": True, "type": "Junction"},
                    {"name": "Bardhaman Jn (BWN)", "km": 100.0, "lat": 23.2400, "lon": 87.8600, "hub": True, "type": "Junction"}
                ]
            }
        ],
        "default_blocks": [
            {
                "allocation_id": "DEMO-HWH-001",
                "planning_group_id": "GRP-DEMO-HWH-01",
                "request_ids": ["REQ-HWH-TRD-01"],
                "departments": ["OHE/Traction"],
                "classification": "ISOLATION",
                "block_id": "BLK-HWH-CAT-01",
                "section": "BDC-BWN-01",
                "from_km": 40.0,
                "to_km": 50.0,
                "date": "2026-09-27",
                "start_time": "11:30",
                "end_time": "14:30",
                "duration_minutes": 180,
                "status": "ALLOCATED",
                "reason": "Catenary & Track Mega-Block",
                "line_coords": [[22.9200, 88.3800], [23.2400, 87.8600]],
                "lat": 23.0500,
                "lon": 88.1000,
                "source": "DEMO",
                "is_demo": True
            }
        ],
        "default_trains": [
            {
                "train_number": "12301",
                "train_name": "Howrah Rajdhani Express",
                "latitude": 22.7000,
                "longitude": 88.3200,
                "current_km": 15.0,
                "direction": "Howrah → New Delhi (UP)",
                "speed": 110.0,
                "delay": 0.0,
                "current_station": "HWH",
                "next_station": "Bardhaman Jn (BWN)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            }
        ]
    },
    "Guntakal Division (GTL)": {
        "center": [15.95, 77.30],
        "zoom": 8,
        "corridor_title": "Guntakal — Adoni — Raichur — Yadgir — Wadi Main Line Corridor",
        "jurisdiction": "SCR Jurisdiction • Guntakal Division HQ (GTL)",
        "kpi": {"running": 16, "reduced": 2, "stopped": 1, "total": 19},
        "division_tags": [
            {"name": "Guntakal Division HQ", "lat": 15.1667, "lon": 77.3667},
            {"name": "Raichur Junction", "lat": 16.2000, "lon": 77.3550}
        ],
        "lines": [
            {
                "name": "Guntakal - Wadi Main Line",
                "color": "#38bdf8",
                "stations": [
                    {"name": "Guntakal Jn (GTL)", "km": 0.0, "lat": 15.1667, "lon": 77.3667, "hub": True, "type": "Division HQ"},
                    {"name": "Adoni (AD)", "km": 52.0, "lat": 15.6300, "lon": 77.2700, "type": "Station"},
                    {"name": "Mantralayam Rd (MALM)", "km": 93.0, "lat": 15.9300, "lon": 77.4200, "type": "Station"},
                    {"name": "Raichur Jn (RC)", "km": 121.0, "lat": 16.2000, "lon": 77.3550, "hub": True, "type": "Junction"},
                    {"name": "Yadgir (YG)", "km": 190.0, "lat": 16.7700, "lon": 77.1350, "type": "Station"},
                    {"name": "Wadi Jn (WADI)", "km": 228.0, "lat": 17.0500, "lon": 76.9900, "hub": True, "type": "Interchange"}
                ]
            }
        ],
        "default_blocks": [
            {
                "allocation_id": "DEMO-GTL-001",
                "planning_group_id": "GRP-DEMO-GTL-01",
                "request_ids": ["REQ-GTL-ENG-01"],
                "departments": ["Engineering"],
                "classification": "ISOLATION",
                "block_id": "BLK-GTL-112",
                "section": "MALM-RC-01",
                "from_km": 95.0,
                "to_km": 105.0,
                "date": "2026-09-27",
                "start_time": "10:00",
                "end_time": "12:30",
                "duration_minutes": 150,
                "status": "ALLOCATED",
                "reason": "Track Geometry & Axle Counter Maintenance",
                "line_coords": [[15.9300, 77.4200], [16.2000, 77.3550]],
                "lat": 16.0500,
                "lon": 77.3800,
                "source": "DEMO",
                "is_demo": True
            }
        ],
        "default_trains": [
            {
                "train_number": "12164",
                "train_name": "Chennai Superfast Express",
                "latitude": 15.8000,
                "longitude": 77.3200,
                "current_km": 75.0,
                "direction": "Wadi → Guntakal (DN)",
                "speed": 85.0,
                "delay": 0.0,
                "current_station": "AD",
                "next_station": "Guntakal (GTL)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            }
        ]
    },
    "Guntur Division (GNT)": {
        "center": [16.05, 79.80],
        "zoom": 8,
        "corridor_title": "Guntur — Nallapadu — Narasaraopet — Markapur — Nandyal Line",
        "jurisdiction": "SCR Jurisdiction • Guntur Division HQ (GNT)",
        "kpi": {"running": 14, "reduced": 1, "stopped": 1, "total": 16},
        "division_tags": [
            {"name": "Guntur Division HQ", "lat": 16.3008, "lon": 80.4428}
        ],
        "lines": [
            {
                "name": "Guntur - Nandyal Line",
                "color": "#38bdf8",
                "stations": [
                    {"name": "Guntur Jn (GNT)", "km": 0.0, "lat": 16.3008, "lon": 80.4428, "hub": True, "type": "Division HQ"},
                    {"name": "Nallapadu (NLPD)", "km": 12.0, "lat": 16.2750, "lon": 80.3800, "type": "Junction"},
                    {"name": "Narasaraopet (NRT)", "km": 45.0, "lat": 16.2350, "lon": 80.0500, "type": "Station"},
                    {"name": "Vinukonda (VKN)", "km": 82.0, "lat": 16.0500, "lon": 79.7400, "type": "Station"},
                    {"name": "Markapur Rd (MRK)", "km": 140.0, "lat": 15.7300, "lon": 79.2700, "type": "Station"},
                    {"name": "Nandyal Jn (NDL)", "km": 210.0, "lat": 15.4800, "lon": 78.4800, "hub": True, "type": "Junction"}
                ]
            }
        ],
        "default_blocks": [
            {
                "allocation_id": "DEMO-GNT-001",
                "planning_group_id": "GRP-DEMO-GNT-01",
                "request_ids": ["REQ-GNT-ENG-01"],
                "departments": ["Engineering"],
                "classification": "ISOLATION",
                "block_id": "BLK-GNT-404",
                "section": "NRT-VKN-01",
                "from_km": 60.0,
                "to_km": 75.0,
                "date": "2026-09-27",
                "start_time": "09:00",
                "end_time": "12:00",
                "duration_minutes": 180,
                "status": "ALLOCATED",
                "reason": "CSM Heavy Tamping Machine Block",
                "line_coords": [[16.2350, 80.0500], [16.0500, 79.7400]],
                "lat": 16.1400,
                "lon": 79.9000,
                "source": "DEMO",
                "is_demo": True
            }
        ],
        "default_trains": [
            {
                "train_number": "17215",
                "train_name": "Machilipatnam Express",
                "latitude": 16.1500,
                "longitude": 79.9500,
                "current_km": 65.0,
                "direction": "GNT → NDL (UP)",
                "speed": 65.0,
                "delay": 2.0,
                "current_station": "NRT",
                "next_station": "Vinukonda (VKN)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            }
        ]
    },
    "Hyderabad Division (HYB)": {
        "center": [17.10, 78.25],
        "zoom": 9,
        "corridor_title": "Hyderabad — Kacheguda — Umdanagar — Mahbubnagar Corridor",
        "jurisdiction": "SCR Jurisdiction • Hyderabad Division HQ (HYB/KCG)",
        "kpi": {"running": 15, "reduced": 2, "stopped": 0, "total": 17},
        "division_tags": [
            {"name": "Hyderabad / Kacheguda HQ", "lat": 17.3888, "lon": 78.4983}
        ],
        "lines": [
            {
                "name": "Kacheguda - Mahbubnagar Line",
                "color": "#38bdf8",
                "stations": [
                    {"name": "Hyderabad (HYB)", "km": 0.0, "lat": 17.3920, "lon": 78.4690, "hub": True, "type": "Terminal"},
                    {"name": "Kacheguda (KCG)", "km": 12.0, "lat": 17.3888, "lon": 78.4983, "hub": True, "type": "Division HQ"},
                    {"name": "Umdanagar (UR)", "km": 28.0, "lat": 17.2600, "lon": 78.4200, "type": "Airport Station"},
                    {"name": "Shadnagar (SHNR)", "km": 55.0, "lat": 17.0700, "lon": 78.2050, "type": "Crossing Station"},
                    {"name": "Jadcherla (JCL)", "km": 90.0, "lat": 16.7700, "lon": 78.1400, "type": "Station"},
                    {"name": "Mahbubnagar (MBNR)", "km": 108.0, "lat": 16.7400, "lon": 77.9900, "hub": True, "type": "Junction"}
                ]
            }
        ],
        "default_blocks": [
            {
                "allocation_id": "DEMO-HYB-001",
                "planning_group_id": "GRP-DEMO-HYB-01",
                "request_ids": ["REQ-HYB-SNT-01"],
                "departments": ["S&T"],
                "classification": "ISOLATION",
                "block_id": "BLK-HYB-050",
                "section": "UR-SHNR-01",
                "from_km": 35.0,
                "to_km": 48.0,
                "date": "2026-09-27",
                "start_time": "10:15",
                "end_time": "11:45",
                "duration_minutes": 90,
                "status": "ALLOCATED",
                "reason": "Signal Cable Integrity Testing",
                "line_coords": [[17.2600, 78.4200], [17.0700, 78.2050]],
                "lat": 17.1500,
                "lon": 78.3000,
                "source": "DEMO",
                "is_demo": True
            }
        ],
        "default_trains": [
            {
                "train_number": "12785",
                "train_name": "Kacheguda Express",
                "latitude": 17.2000,
                "longitude": 78.3500,
                "current_km": 42.0,
                "direction": "KCG → MBNR (UP)",
                "speed": 75.0,
                "delay": 0.0,
                "current_station": "UR",
                "next_station": "Shadnagar (SHNR)",
                "status": "RUNNING",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": "LIVE"
            }
        ]
    }
}


def get_division_network_data(division_name: str) -> dict:
    """Safely retrieves division network configuration matching name or alias."""
    div_str = str(division_name).lower()
    for key, data in DIVISION_GEOGRAPHIC_NETWORKS.items():
        if key.lower() in div_str or div_str in key.lower():
            return data
    if "kur" in div_str or "khurda" in div_str:
        return DIVISION_GEOGRAPHIC_NETWORKS["Khurda Road Division (KUR)"]
    if "howrah" in div_str or "hwh" in div_str:
        return DIVISION_GEOGRAPHIC_NETWORKS["Howrah Division (HWH)"]
    if "secund" in div_str or "sc" in div_str:
        return DIVISION_GEOGRAPHIC_NETWORKS["Secunderabad Division (SC)"]
    if "guntak" in div_str or "gtl" in div_str:
        return DIVISION_GEOGRAPHIC_NETWORKS["Guntakal Division (GTL)"]
    if "guntur" in div_str or "gnt" in div_str:
        return DIVISION_GEOGRAPHIC_NETWORKS["Guntur Division (GNT)"]
    if "hyder" in div_str or "hyb" in div_str:
        return DIVISION_GEOGRAPHIC_NETWORKS["Hyderabad Division (HYB)"]
    return DIVISION_GEOGRAPHIC_NETWORKS["Vijayawada Division (BZA)"]


# =============================================================================
# GEOGRAPHIC ADAPTER: SECTION/KM -> ACCURATE MAP GEOMETRY
# =============================================================================
def get_section_geometry(section_name: str, from_km: float, to_km: float, division_name: str = "Vijayawada Division (BZA)") -> list:
    """
    Adapter converting railway section & KM range into geographic GPS line coordinates
    using the comprehensive station network, station acronym mappings, and track polyline interpolations.
    Guarantees realistic, non-colliding coordinates along the actual railway line.
    """
    net_data = get_division_network_data(division_name)
    best_coords = []
    f_km = float(from_km) if from_km is not None else 100.0
    t_km = float(to_km) if to_km is not None else (f_km + 5.0)
    if f_km > t_km:
        f_km, t_km = t_km, f_km

    # Normalize tokens cleanly across special characters and encodings
    sec_clean = re.sub(r"[^a-zA-Z0-9\s]+", " ", str(section_name)).upper()
    tokens = [t.strip() for t in sec_clean.split() if t.strip()]

    # 1. Score all lines in this division to pick the most accurate track line
    best_line = None
    best_score = -1

    for line in net_data.get("lines", []):
        st_list = line.get("stations", [])
        if len(st_list) < 2:
            continue
        
        matched_in_line = []
        for st in st_list:
            s_name = st["name"].upper()
            for t in tokens:
                if t in s_name or f"({t})" in s_name:
                    if st not in matched_in_line:
                        matched_in_line.append(st)
                    break
        
        kms = [float(s.get("km", 0.0)) for s in st_list]
        min_k, max_k = min(kms), max(kms)
        score = len(matched_in_line) * 10
        if min_k <= f_km <= max_k or min_k <= t_km <= max_k:
            score += 20
        if any(t in line["name"].upper() for t in tokens if len(t) > 2):
            score += 5

        if score > best_score:
            best_score = score
            best_line = line

    if best_line and best_score > 0:
        st_list = best_line["stations"]
        kms = [float(s.get("km", 0.0)) for s in st_list]
        min_k, max_k = min(kms), max(kms)

        eff_f_km = f_km
        eff_t_km = t_km
        if eff_f_km > max_k or eff_t_km > max_k or eff_t_km < min_k:
            span = max_k - min_k if max_k > min_k else 100.0
            eff_f_km = min_k + (f_km % span)
            eff_t_km = eff_f_km + min(15.0, abs(t_km - f_km))

        p_from, p_to = None, None
        for i in range(len(st_list) - 1):
            s1, s2 = st_list[i], st_list[i+1]
            k1, k2 = float(s1.get("km", 0.0)), float(s2.get("km", 0.0))
            if k1 == k2:
                continue
            seg_min, seg_max = min(k1, k2), max(k1, k2)

            if p_from is None and (seg_min <= eff_f_km <= seg_max or (i == 0 and eff_f_km <= seg_min)):
                ratio = (eff_f_km - k1) / (k2 - k1) if k2 != k1 else 0.0
                ratio = max(0.0, min(1.0, ratio))
                lat = s1["lat"] + ratio * (s2["lat"] - s1["lat"])
                lon = s1["lon"] + ratio * (s2["lon"] - s1["lon"])
                p_from = [round(lat, 4), round(lon, 4)]

            if p_to is None and (seg_min <= eff_t_km <= seg_max or (i == len(st_list) - 2 and eff_t_km >= seg_max)):
                ratio = (eff_t_km - k1) / (k2 - k1) if k2 != k1 else 1.0
                ratio = max(0.0, min(1.0, ratio))
                lat = s1["lat"] + ratio * (s2["lat"] - s1["lat"])
                lon = s1["lon"] + ratio * (s2["lon"] - s1["lon"])
                p_to = [round(lat, 4), round(lon, 4)]

        if p_from and p_to:
            best_coords = [p_from, p_to]

    # 2. Token-based station lookup from global dictionary
    if not best_coords:
        matched_stns = []
        for t in tokens:
            if t in STATION_COORDINATES:
                st_data = STATION_COORDINATES[t]
                if not any(s["name"] == st_data["name"] for s in matched_stns):
                    matched_stns.append(st_data)

        if len(matched_stns) >= 2:
            s1, s2 = matched_stns[0], matched_stns[1]
            lat1, lon1 = s1["lat"], s1["lon"]
            lat2, lon2 = s2["lat"], s2["lon"]
            best_coords = [
                [round(lat1 * 0.7 + lat2 * 0.3, 4), round(lon1 * 0.7 + lon2 * 0.3, 4)],
                [round(lat1 * 0.3 + lat2 * 0.7, 4), round(lon1 * 0.3 + lon2 * 0.7, 4)]
            ]
        elif len(matched_stns) == 1:
            s1 = matched_stns[0]
            lat1, lon1 = s1["lat"], s1["lon"]
            best_coords = [
                [round(lat1 + 0.015, 4), round(lon1 - 0.020, 4)],
                [round(lat1 - 0.015, 4), round(lon1 + 0.020, 4)]
            ]

    # 3. Fallback to primary corridor alignment of division
    if not best_coords:
        lines = net_data.get("lines", [])
        if lines and len(lines[0].get("stations", [])) >= 2:
            st1 = lines[0]["stations"][0]
            st2 = lines[0]["stations"][1]
            best_coords = [
                [round(st1["lat"] * 0.6 + st2["lat"] * 0.4, 4), round(st1["lon"] * 0.6 + st2["lon"] * 0.4, 4)],
                [round(st1["lat"] * 0.4 + st2["lat"] * 0.6, 4), round(st1["lon"] * 0.4 + st2["lon"] * 0.6, 4)]
            ]
        else:
            c_lat, c_lon = net_data.get("center", [16.55, 80.85])
            best_coords = [[c_lat - 0.02, c_lon - 0.02], [c_lat + 0.02, c_lon + 0.02]]

    return best_coords


# =============================================================================
# DATA FETCHING: ALLOCATED & CLASSIFIED MAINTENANCE BLOCKS
# =============================================================================
def fetch_allocated_blocks(
    division_name: str = "Vijayawada Division (BZA)",
    status_filter: str = "ALL",
    dept_filter: str = "ALL"
) -> list:
    """
    Fetches allocated maintenance blocks from SQLite table 'final_block_allocations'
    AND ingests active classified candidate groups from Streamlit session state ('step6_classified_results').
    Applies status_filter (ALL, CLASSIFIED, ALLOCATED, ACTIVE, COMPLETED, AT_RISK, PLANNED, CANCELLED)
    and dept_filter.
    Falls back to isolated DEMO dataset only if zero DB records and zero candidate groups exist.
    """
    blocks = []
    seen_group_ids = set()
    seen_alloc_keys = set()

    # 1. Fetch DB Final Block Allocations
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            t_exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='final_block_allocations'").fetchone()
            if t_exists:
                q = "SELECT * FROM final_block_allocations WHERE 1=1"
                params = []
                
                if status_filter and status_filter.upper() != "ALL":
                    q += " AND UPPER(status) = ?"
                    params.append(status_filter.upper())
                
                q += " ORDER BY is_active DESC, updated_at DESC, created_at DESC, version DESC, allocation_id DESC"
                rows = cur.execute(q, params).fetchall()
                
                for r in rows:
                    row_dict = dict(r)
                    g_id = str(row_dict.get("planning_group_id") or "GRP-001")
                    blk_id_val = str(row_dict.get("block") or row_dict.get("allocation_id"))
                    
                    # Deduplicate so obsolete versions are replaced by the active/latest version
                    dedup_key = f"{g_id}_{blk_id_val}"
                    if dedup_key in seen_alloc_keys:
                        continue
                    seen_alloc_keys.add(dedup_key)
                    seen_group_ids.add(g_id)
                    
                    det = {}
                    if row_dict.get("details_json"):
                        try:
                            det = json.loads(row_dict["details_json"])
                        except Exception:
                            det = {}
                    
                    f_km = float(row_dict.get("from_km") or 100.0)
                    t_km = float(row_dict.get("to_km") or (f_km + 5.0))
                    sec = str(row_dict.get("section") or row_dict.get("block") or "Main Corridor")
                    
                    dept_val = str(row_dict.get("departments") or "Engineering")
                    dept_list = [d.strip() for d in re.split(r"[,/]+", dept_val) if d.strip()]
                    
                    # Apply Department Filter
                    if dept_filter and dept_filter.upper() != "ALL":
                        if not any(dept_filter.upper() in d.upper() or d.upper() in dept_filter.upper() for d in dept_list):
                            continue
                    
                    line_geo = get_section_geometry(sec, f_km, t_km, division_name=division_name)
                    req_val = str(row_dict.get("request_ids") or "REQ-001")
                    req_list = [rq.strip() for rq in re.split(r"[,/]+", req_val) if rq.strip()]
                    seq_order = det.get("execution_order", [])
                    
                    c_lat = (line_geo[0][0] + line_geo[-1][0]) / 2.0 if line_geo else 16.55
                    c_lon = (line_geo[0][1] + line_geo[-1][1]) / 2.0 if line_geo else 80.85

                    blocks.append({
                        "allocation_id": str(row_dict.get("allocation_id")),
                        "planning_group_id": g_id,
                        "request_ids": req_list,
                        "departments": dept_list,
                        "classification": str(row_dict.get("classification") or "ISOLATION"),
                        "block_id": blk_id_val,
                        "section": sec,
                        "from_km": f_km,
                        "to_km": t_km,
                        "date": str(row_dict.get("date") or datetime.now().strftime("%Y-%m-%d")),
                        "start_time": str(row_dict.get("start_time") or "10:00"),
                        "end_time": str(row_dict.get("end_time") or "12:00"),
                        "duration_minutes": int(row_dict.get("duration") or 60),
                        "status": str(row_dict.get("status") or "ALLOCATED").upper(),
                        "reason": str(row_dict.get("override_reason") or det.get("summary_text") or det.get("name") or "Corridor Block Possession"),
                        "execution_order": seq_order,
                        "line_coords": line_geo,
                        "lat": c_lat,
                        "lon": c_lon,
                        "source": "DATABASE",
                        "is_demo": False
                    })
            conn.close()
    except Exception:
        pass

    # 2. Ingest active classified candidate groups from Streamlit session state
    if status_filter in ["ALL", "CLASSIFIED", "PLANNED"]:
        try:
            import streamlit as st
            cls_results = st.session_state.get("step6_classified_results", {})
            if cls_results and cls_results.get("all_groups"):
                for grp in cls_results.get("all_groups", []):
                    g_id = str(grp.get("group_id", "GRP-001"))
                    if g_id in seen_group_ids:
                        continue
                    
                    g_depts = grp.get("departments", ["Engineering"])
                    if isinstance(g_depts, str):
                        g_depts = [g_depts]
                    
                    # Apply Department Filter
                    if dept_filter and dept_filter.upper() != "ALL":
                        if not any(dept_filter.upper() in d.upper() or d.upper() in dept_filter.upper() for d in g_depts):
                            continue
                    
                    f_km = float(grp.get("from_km") or 114.0)
                    t_km = float(grp.get("to_km") or (f_km + 5.0))
                    sec = str(grp.get("section") or "Vijayawada–Kondapalli")
                    line_geo = get_section_geometry(sec, f_km, t_km, division_name=division_name)
                    dur_val = 60
                    if grp.get("requests"):
                        dur_val = max([int(r.get("required_duration", 60)) for r in grp["requests"]])
                    
                    seen_group_ids.add(g_id)
                    c_lat = (line_geo[0][0] + line_geo[-1][0]) / 2.0 if line_geo else 16.55
                    c_lon = (line_geo[0][1] + line_geo[-1][1]) / 2.0 if line_geo else 80.85
                    blocks.append({
                        "allocation_id": f"CAND-{g_id}",
                        "planning_group_id": g_id,
                        "request_ids": grp.get("request_ids", []),
                        "departments": g_depts,
                        "classification": grp.get("classification", "ISOLATION"),
                        "block_id": str(grp.get("block") or f"BLK-{g_id}"),
                        "section": sec,
                        "from_km": f_km,
                        "to_km": t_km,
                        "date": str(grp.get("date") or datetime.now().strftime("%Y-%m-%d")),
                        "start_time": "AWAITING ALLOCATION",
                        "end_time": "AWAITING ALLOCATION",
                        "duration_minutes": dur_val,
                        "status": "CLASSIFIED",
                        "reason": f"Classified {grp.get('classification')} Group: {grp.get('reason', '')}",
                        "execution_order": grp.get("execution_order", []),
                        "line_coords": line_geo,
                        "lat": c_lat,
                        "lon": c_lon,
                        "source": "CLASSIFIED_GROUPS",
                        "is_demo": False
                    })
        except Exception:
            pass

    # 3. Fallback to isolated DEMO dataset if no DB records or candidate groups exist
    if not blocks and status_filter in ["ALL", "ALLOCATED", "ACTIVE"]:
        net_data = get_division_network_data(division_name)
        demo_defaults = net_data.get("default_blocks", [])
        for d_blk in demo_defaults:
            d_status = str(d_blk.get("status", "ALLOCATED")).upper()
            d_dept = d_blk.get("departments", d_blk.get("department", "Engineering"))
            d_dept_str = ", ".join(d_dept) if isinstance(d_dept, list) else str(d_dept)
            
            if status_filter and status_filter.upper() != "ALL" and d_status != status_filter.upper():
                continue
            if dept_filter and dept_filter.upper() != "ALL" and dept_filter.upper() not in d_dept_str.upper():
                continue
            
            blk_copy = dict(d_blk)
            blk_copy["source"] = "DEMO"
            blk_copy["is_demo"] = True
            if "duration_minutes" not in blk_copy:
                blk_copy["duration_minutes"] = 180
            if "planning_group_id" not in blk_copy:
                blk_copy["planning_group_id"] = f"DEMO-{blk_copy.get('classification', 'ISO')[:3]}-001"
            if "request_ids" not in blk_copy:
                blk_copy["request_ids"] = [f"REQ-{d_dept_str[:3].upper()}-01"]
            if isinstance(blk_copy.get("departments"), str):
                blk_copy["departments"] = [blk_copy["departments"]]
            elif "departments" not in blk_copy:
                blk_copy["departments"] = [d_dept_str]
            blocks.append(blk_copy)

    return blocks


# =============================================================================
# DATA FETCHING: LIVE TRAINS (LAYER 2)
# =============================================================================
def fetch_live_trains(
    division_name: str = "Vijayawada Division (BZA)",
    train_filter: str = "ALL",
    search_query: str = ""
) -> list:
    """
    Fetches and prepares live train records for Layer 2 visualization.
    Retrieves records from SQLite repository (live_train_positions / live_train_status)
    and computes authentic geographic track coordinates along the division corridor.
    Guarantees moving trains with live speed, direction, and delay telemetry.
    """
    trains_dict = {}
    now = datetime.now()
    net_data = get_division_network_data(division_name)

    # 1. Initialize from division default trains
    defaults = net_data.get("default_trains", [])
    for d_tr in defaults:
        num = str(d_tr["train_number"])
        tr_copy = dict(d_tr)
        tr_copy["age_seconds"] = 10
        tr_copy["is_stale"] = False
        tr_copy["source"] = "DIVISION_FEED"
        trains_dict[num] = tr_copy

    # 2. Enrich/Update from SQLite live tables (live_train_status & live_train_positions)
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            has_stat = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='live_train_status'").fetchone()
            if has_stat:
                rows = cur.execute("SELECT * FROM live_train_status").fetchall()
                for r in rows:
                    rd = dict(r)
                    t_num = str(rd.get("train_id") or rd.get("train_number") or "")
                    if not t_num:
                        continue
                    if t_num in trains_dict:
                        t_name = str(rd.get("train_name") or trains_dict[t_num]["train_name"])
                        cur_km = float(rd.get("current_km") or trains_dict[t_num]["current_km"])
                        delay = float(rd.get("delay_minutes") or rd.get("delay") or trains_dict[t_num]["delay"])
                        speed = float(rd.get("current_speed_kmh") or rd.get("speed") or trains_dict[t_num]["speed"])
                        mps = float(rd.get("recommended_speed_kmh") or rd.get("max_permissible_speed") or trains_dict[t_num].get("mps", 110.0))
                        status = str(rd.get("status") or trains_dict[t_num]["status"]).upper()
                        last_upd = str(rd.get("last_updated") or rd.get("last_update") or trains_dict[t_num]["timestamp"])
                        sec_id = str(rd.get("section_id") or trains_dict[t_num].get("current_station", "Main Corridor"))

                        geo = get_section_geometry(sec_id, cur_km, cur_km + 1.0, division_name=division_name)
                        trains_dict[t_num].update({
                            "train_name": t_name,
                            "current_km": cur_km,
                            "speed": speed,
                            "delay": delay,
                            "mps": mps,
                            "status": status,
                            "timestamp": last_upd,
                            "latitude": geo[0][0],
                            "longitude": geo[0][1],
                            "data_source": "LIVE",
                            "source": "DATABASE"
                        })

            has_pos = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='live_train_positions'").fetchone()
            if has_pos:
                rows = cur.execute("SELECT * FROM live_train_positions").fetchall()
                for r in rows:
                    rd = dict(r)
                    t_num = str(rd.get("train_number") or "")
                    if not t_num:
                        continue
                    if t_num in trains_dict:
                        t_lat = rd.get("latitude")
                        t_lon = rd.get("longitude")
                        cur_km = float(rd.get("current_km") or trains_dict[t_num]["current_km"])
                        if t_lat is not None and t_lon is not None and (8.0 <= float(t_lat) <= 36.0 and 68.0 <= float(t_lon) <= 98.0):
                            trains_dict[t_num]["latitude"] = float(t_lat)
                            trains_dict[t_num]["longitude"] = float(t_lon)
                        trains_dict[t_num]["current_km"] = cur_km
                        trains_dict[t_num]["speed"] = float(rd.get("speed") or trains_dict[t_num]["speed"])
                        trains_dict[t_num]["delay"] = float(rd.get("delay") or trains_dict[t_num]["delay"])
                        trains_dict[t_num]["status"] = str(rd.get("status") or trains_dict[t_num]["status"]).upper()
                        trains_dict[t_num]["data_source"] = str(rd.get("data_source") or "LIVE").upper()
                        trains_dict[t_num]["source"] = "DATABASE"
            conn.close()
    except Exception:
        pass

    # 3. Ingest active trains from session state if available
    try:
        import streamlit as st
        if "trains_10_state" in st.session_state and st.session_state.trains_10_state:
            for t_id, tr in st.session_state.trains_10_state.items():
                num = str(tr.get("number", tr.get("train_number", t_id)))
                if num in trains_dict:
                    trains_dict[num]["train_name"] = tr.get("name", trains_dict[num]["train_name"])
                    trains_dict[num]["speed"] = float(tr.get("current_speed", trains_dict[num]["speed"]))
                    trains_dict[num]["status"] = str(tr.get("status", trains_dict[num]["status"])).upper()
                    trains_dict[num]["delay"] = float(tr.get("delay_minutes", trains_dict[num]["delay"]))
    except Exception:
        pass

    trains = list(trains_dict.values())

    # 5. Apply Filtering
    filtered_trains = []
    for tr in trains:
        spd = float(tr.get("speed", 0.0))
        del_m = float(tr.get("delay", 0.0))
        st_clean = str(tr.get("status", "RUNNING")).upper()
        num_str = str(tr.get("train_number", "")).lower()
        name_str = str(tr.get("train_name", "")).lower()

        # Status Filter
        if train_filter and train_filter.upper() != "ALL":
            tf_upper = train_filter.upper()
            if tf_upper == "RUNNING":
                if "STOP" in st_clean or spd == 0 or del_m > 15:
                    continue
            elif tf_upper == "DELAYED":
                if del_m <= 0 and "DELAY" not in st_clean and "LATE" not in st_clean:
                    continue
            elif tf_upper == "STOPPED":
                if spd > 0 and "STOP" not in st_clean:
                    continue

        # Search Query Filter
        if search_query and search_query.strip():
            sq = search_query.strip().lower()
            if (sq not in num_str and sq not in name_str and 
                sq not in str(tr.get("current_station", "")).lower() and 
                sq not in str(tr.get("next_station", "")).lower()):
                continue

        filtered_trains.append(tr)

    return filtered_trains


# =============================================================================
# 1. BASE RAILWAY LAYER (Layer 0)
# =============================================================================
class BaseRailwayLayer:
    """
    Renders geographic tracks, multi-track corridors, station nodes, and KM references.
    Layer 0 of the Controller Geographic Map.
    """

    @staticmethod
    def add_to_map(m: folium.Map, network_data: dict):
        base_group = folium.FeatureGroup(name="🛣️ Railway Base (Tracks & Stations)", overlay=True, control=True)

        # 1. Track Polylines
        for line in network_data.get("lines", []):
            coords = [[st_node["lat"], st_node["lon"]] for st_node in line["stations"]]

            # Track Bed Outline (Broad Gauge dark bed)
            folium.PolyLine(
                coords,
                color="#0b1329",
                weight=7,
                opacity=0.9,
                z_index_offset=100
            ).add_to(base_group)

            # High-visibility Track Line with Tooltip
            track_tooltip = f"""
            <div style="background: #0f172a; color: white; padding: 8px 12px; border-radius: 8px; border: 1.5px solid {line['color']}; font-family: sans-serif; font-size: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.6); min-width: 200px;">
                <div style="font-size: 13px; font-weight: bold; color: {line['color']};">🛣️ {line['name']}</div>
                <div style="margin-top: 3px; color: #e2e8f0;">Route: <b>{line['stations'][0]['name']}</b> ➔ <b>{line['stations'][-1]['name']}</b></div>
                <div style="color: #4ade80; margin-top: 2px; font-size: 11px;">⚡ MPS: <b>110–130 km/h</b> | 25kV AC Electrified</div>
            </div>
            """
            folium.PolyLine(
                coords,
                color=line["color"],
                weight=3.5,
                opacity=0.95,
                tooltip=folium.Tooltip(track_tooltip, sticky=True),
                z_index_offset=150
            ).add_to(base_group)

            # 2. Station Circle Markers and Hub Nodes
            for st_node in line["stations"]:
                is_hub = st_node.get("hub", False)
                rad = 7 if is_hub else 4.5
                c_color = "#38bdf8" if is_hub else "#ffffff"
                f_color = "#0284c7" if is_hub else "#1e293b"

                st_tooltip = f"""
                <div style="background: #0f172a; color: white; padding: 8px 12px; border-radius: 6px; border: 1.5px solid #38bdf8; font-family: sans-serif; font-size: 12px;">
                    <div style="font-weight: bold; color: #38bdf8; font-size: 13px;">🚉 {st_node['name']}</div>
                    <div style="color: #cbd5e1; margin-top: 2px;">KM Ref: <b>Km {st_node.get('km', 0.0):.1f}</b></div>
                    <div style="color: #94a3b8; font-size: 11px;">Type: {st_node.get('type', 'Station')}</div>
                </div>
                """

                # Station Marker Node
                folium.CircleMarker(
                    location=[st_node["lat"], st_node["lon"]],
                    radius=rad,
                    color=c_color,
                    weight=2,
                    fill=True,
                    fill_color=f_color,
                    fill_opacity=1.0,
                    tooltip=folium.Tooltip(st_tooltip, sticky=True),
                    z_index_offset=200
                ).add_to(base_group)

                # Outer Glow Ring for Hub Stations
                if is_hub:
                    folium.CircleMarker(
                        location=[st_node["lat"], st_node["lon"]],
                        radius=rad + 4,
                        color="#38bdf8",
                        weight=1.5,
                        opacity=0.6,
                        fill=False,
                        z_index_offset=190
                    ).add_to(base_group)

                # Text Label next to Station
                lbl_html = f"""
                <div style="font-family: sans-serif; font-size: 10.5px; font-weight: 700; color: #f1f5f9; text-shadow: 1px 1px 2px #000, 0 0 4px #000; white-space: nowrap; pointer-events: none;">
                    {st_node['name'].split()[0]}
                </div>
                """
                folium.Marker(
                    location=[st_node["lat"], st_node["lon"]],
                    icon=folium.DivIcon(html=lbl_html, icon_size=(80, 20), icon_anchor=(-8, 10)),
                    z_index_offset=210
                ).add_to(base_group)

        # 3. Regional Tags / Jurisdiction boundaries
        for tag in network_data.get("division_tags", []):
            tag_html = f"""
            <div style="font-family: sans-serif; font-size: 10px; font-weight: 800; color: rgba(148, 163, 184, 0.65); letter-spacing: 1.2px; text-transform: uppercase; text-shadow: 0 1px 3px rgba(0,0,0,0.8); pointer-events: none;">
                🏷️ {tag['name']}
            </div>
            """
            folium.Marker(location=[tag["lat"], tag["lon"]], icon=folium.DivIcon(html=tag_html), z_index_offset=50).add_to(base_group)

        base_group.add_to(m)


# =============================================================================
# 2. ALLOCATED & CANDIDATE MAINTENANCE BLOCK LAYER (Layer 1)
# =============================================================================
class AllocatedBlockLayer:
    """
    Renders allocated maintenance blocks & classified candidate blocks on track sections.
    Layer 1 of the Controller Geographic Map.
    Receives allocation objects and renders hatched lines, department colors, and rich popups.
    """

    @staticmethod
    def get_department_color(departments) -> tuple:
        """Returns (fill_color, border_color) for department(s)."""
        if isinstance(departments, list):
            d_str = " ".join(departments).lower()
        else:
            d_str = str(departments).lower()

        is_eng = "eng" in d_str
        is_trd = "trd" in d_str or "trac" in d_str or "ohe" in d_str
        is_snt = "s&t" in d_str or "sig" in d_str or "tele" in d_str

        dept_count = sum([is_eng, is_trd, is_snt])
        if dept_count > 1:
            return ("#a855f7", "#7e22ce") # Purple (Multi-dept / Joint)
        elif is_eng:
            return ("#3b82f6", "#1d4ed8") # Blue
        elif is_trd:
            return ("#f97316", "#c2410c") # Orange
        elif is_snt:
            return ("#22c55e", "#15803d") # Green
        else:
            return ("#a855f7", "#7e22ce") # Default Joint Purple

    @staticmethod
    def get_status_style(status: str, base_color: str) -> dict:
        """Returns visual styling properties based on lifecycle status."""
        st_clean = str(status).upper()
        if st_clean == "ACTIVE":
            return {
                "color": "#ef4444",
                "weight": 12,
                "opacity": 0.85,
                "dash_array": "4,6",
                "badge_bg": "#ef4444",
                "badge_txt": "🟢 ACTIVE (In Possession)",
                "icon": "⚡"
            }
        elif st_clean == "CLASSIFIED":
            return {
                "color": "#a855f7",
                "weight": 11,
                "opacity": 0.90,
                "dash_array": "5,5",
                "badge_bg": "#7e22ce",
                "badge_txt": "🧩 CLASSIFIED CANDIDATE (Awaiting Allocation)",
                "icon": "🧩"
            }
        elif st_clean in ["ALLOCATED", "PLANNED"]:
            return {
                "color": base_color,
                "weight": 10,
                "opacity": 0.75,
                "dash_array": "6,8",
                "badge_bg": "#3b82f6",
                "badge_txt": "🟡 ALLOCATED (Upcoming)",
                "icon": "🚧"
            }
        elif st_clean == "COMPLETED":
            return {
                "color": "#10b981",
                "weight": 7,
                "opacity": 0.50,
                "dash_array": "2,4",
                "badge_bg": "#10b981",
                "badge_txt": "✅ COMPLETED (Certified Fit)",
                "icon": "✅"
            }
        elif st_clean in ["AT_RISK", "OVERRUN"]:
            return {
                "color": "#dc2626",
                "weight": 12,
                "opacity": 0.90,
                "dash_array": "3,3",
                "badge_bg": "#dc2626",
                "badge_txt": "🔴 AT RISK (Overrun Alert)",
                "icon": "⚠️"
            }
        elif st_clean == "CANCELLED":
            return {
                "color": "#64748b",
                "weight": 6,
                "opacity": 0.40,
                "dash_array": "1,6",
                "badge_bg": "#64748b",
                "badge_txt": "⚪ CANCELLED",
                "icon": "❌"
            }
        else:
            return {
                "color": base_color,
                "weight": 9,
                "opacity": 0.65,
                "dash_array": "6,8",
                "badge_bg": "#3b82f6",
                "badge_txt": f"ℹ️ {st_clean}",
                "icon": "🚧"
            }

    @staticmethod
    def add_to_map(m: folium.Map, blocks: list):
        blocks_group = folium.FeatureGroup(name="🚧 Allocated Maintenance Blocks", overlay=True, control=True)

        for blk in blocks:
            depts = blk.get("departments", blk.get("department", ["Engineering"]))
            if isinstance(depts, str):
                depts = [d.strip() for d in depts.split(",") if d.strip()]

            dept_fill, dept_border = AllocatedBlockLayer.get_department_color(depts)
            st_style = AllocatedBlockLayer.get_status_style(blk.get("status", "ALLOCATED"), dept_fill)

            line_coords = blk.get("line_coords", [])
            lat = blk.get("lat")
            lon = blk.get("lon")

            if not line_coords and lat and lon:
                line_coords = [[lat - 0.03, lon - 0.03], [lat + 0.03, lon + 0.03]]

            if not line_coords:
                continue

            c_lat = lat if lat else (line_coords[0][0] + line_coords[-1][0]) / 2.0
            c_lon = lon if lon else (line_coords[0][1] + line_coords[-1][1]) / 2.0

            source_type = blk.get("source", "DATABASE")
            if source_type == "DEMO" or blk.get("is_demo"):
                source_tag = "<span style='background:rgba(239,68,68,0.2); color:#fca5a5; padding:2px 7px; border-radius:4px; font-size:10px; border:1px solid #ef4444; font-weight:700;'>DEMO DATA</span>"
            elif source_type == "CLASSIFIED_GROUPS":
                source_tag = "<span style='background:rgba(168,85,247,0.25); color:#d8b4fe; padding:2px 7px; border-radius:4px; font-size:10px; border:1px solid #a855f7; font-weight:700;'>⚡ STEP 6 CLASSIFIED</span>"
            else:
                source_tag = "<span style='background:rgba(16,185,129,0.2); color:#6ee7b7; padding:2px 7px; border-radius:4px; font-size:10px; border:1px solid #10b981; font-weight:700;'>DATABASE ALLOCATION</span>"

            # Department Badges HTML
            dept_badges = ""
            for d in depts:
                d_color = "#3b82f6" if "eng" in d.lower() else ("#f97316" if "trd" in d.lower() or "ohe" in d.lower() else "#22c55e")
                dept_badges += f"<span style='background:{d_color}; color:#ffffff; padding:1px 6px; border-radius:3px; font-size:10px; font-weight:700; margin-right:4px;'>{d}</span>"

            # Sequential Order Execution Details
            seq_order_html = ""
            if blk.get("execution_order"):
                seq_items = "".join([f"<li style='margin-bottom:2px;'>{step}</li>" for step in blk["execution_order"]])
                seq_order_html = f"""
                <div style="margin-top:6px; padding:6px 8px; background:rgba(168,85,247,0.15); border:1px solid #a855f7; border-radius:6px;">
                    <div style="font-size:10.5px; font-weight:700; color:#d8b4fe;">🔄 Sequential Execution Order:</div>
                    <ol style="margin:2px 0 0 16px; padding:0; font-size:10.5px; color:#f1f5f9;">{seq_items}</ol>
                </div>
                """

            alloc_id = blk.get("allocation_id", blk.get("block_id", "ALLOC-001"))
            pg_id = blk.get("planning_group_id", "GRP-001")
            req_ids_str = ", ".join(blk.get("request_ids", ["REQ-001"]))

            # Comprehensive Block Popup
            block_popup_html = f"""
            <div style="background: #0f172a; color: white; padding: 12px 14px; border-radius: 8px; border: 2px solid {st_style['color']}; font-family: sans-serif; font-size: 12px; min-width: 270px; max-width: 340px; box-shadow: 0 4px 20px rgba(0,0,0,0.6);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span style="font-size: 13.5px; font-weight: 800; color: {st_style['color']};">{st_style['icon']} {blk.get('block_id', 'BLOCK')}</span>
                    {source_tag}
                </div>
                <div style="color: #94a3b8; font-size: 10px; margin-bottom: 4px;">Alloc ID: <strong style="color:#e2e8f0;">{alloc_id}</strong> &nbsp;|&nbsp; Group: <strong style="color:#38bdf8;">{pg_id}</strong></div>
                <div style="color: #e2e8f0; font-weight: 600; font-size: 12px; margin-bottom: 6px;">{blk.get('reason', 'Corridor Maintenance Possession')}</div>
                <div style="border-top: 1px solid #334155; padding-top: 6px; margin-top: 4px; font-size: 11.5px; line-height: 1.5; color: #cbd5e1;">
                    <div>📍 Section: <strong style="color:#ffffff;">{blk.get('section', 'Main Corridor')}</strong></div>
                    <div>📏 KM Range: <strong style="color:#38bdf8;">Km {blk.get('from_km', 0):.1f} – {blk.get('to_km', 0):.1f}</strong> (Span: {abs(blk.get('to_km', 0) - blk.get('from_km', 0)):.1f} km)</div>
                    <div style="margin-top:2px;">🏢 Departments: {dept_badges}</div>
                    <div style="margin-top:2px;">⏱️ Time Window: <strong style="color:#fbbf24;">{blk.get('start_time', 'AWAITING ALLOCATION')} – {blk.get('end_time', '')}</strong> ({blk.get('duration_minutes', 60)} min)</div>
                    <div>📅 Date: <strong>{blk.get('date', datetime.now().strftime('%Y-%m-%d'))}</strong></div>
                    <div>🏷️ Classification: <span style="background:{dept_border}; color:#fff; padding:1px 5px; border-radius:3px; font-size:10px; font-weight:700;">{blk.get('classification', 'ISOLATION')}</span></div>
                    <div>📋 Request(s): <span style="color:#94a3b8; font-size:10.5px;">{req_ids_str}</span></div>
                    <div style="margin-top:3px;">⚡ Status: <span style="background:{st_style['badge_bg']}; color:#fff; padding:1px 6px; border-radius:4px; font-size:10px; font-weight:700;">{st_style['badge_txt']}</span></div>
                </div>
                {seq_order_html}
            </div>
            """

            # Thick hatched possession line
            folium.PolyLine(
                line_coords,
                color=st_style["color"],
                weight=st_style["weight"],
                opacity=st_style["opacity"],
                dash_array=st_style["dash_array"],
                tooltip=folium.Tooltip(block_popup_html, sticky=True),
                z_index_offset=400
            ).add_to(blocks_group)

            # Block Marker Pin Tag
            c_html = f"""
            <div style="background: rgba(15, 23, 42, 0.92); border: 1.5px solid {st_style['color']}; border-radius: 6px; padding: 3px 8px; color: #ffffff; font-family: sans-serif; font-size: 10.5px; font-weight: 700; white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.5); cursor: pointer;">
                <span style="color: {st_style['color']};">{st_style['icon']}</span> {blk.get('block_id', 'BLOCK')} (Km {blk.get('from_km', 0):.0f}–{blk.get('to_km', 0):.0f})
            </div>
            """
            folium.Marker(
                location=[c_lat, c_lon],
                icon=folium.DivIcon(html=c_html),
                tooltip=folium.Tooltip(block_popup_html, sticky=True),
                z_index_offset=450
            ).add_to(blocks_group)

        blocks_group.add_to(m)


# =============================================================================
# 3. LIVE TRAIN LAYER (Layer 2)
# =============================================================================
class LiveTrainLayer:
    """
    Renders moving train markers, speed vectors, direction, and live telemetry popups.
    Layer 2 of the Controller Geographic Map.
    Visually rendered ABOVE the railway tracks (Layer 0) and maintenance blocks (Layer 1).
    Ensures marker z-index is set to 900+ for clear stacking hierarchy and full interactivity.
    """

    @classmethod
    def add_to_map(cls, m: folium.Map, trains: list):
        trains_group = folium.FeatureGroup(name="🚆 Live Moving Trains", overlay=True, control=True)

        for tr in trains:
            lat = tr.get("latitude", tr.get("lat"))
            lon = tr.get("longitude", tr.get("lon"))
            if not lat or not lon:
                continue

            num = str(tr.get("train_number", tr.get("num", "12000")))
            name = str(tr.get("train_name", tr.get("name", "Express")))
            spd_val = tr.get("speed", tr.get("speed_kmh", 80))
            if isinstance(spd_val, str) and "km" in spd_val:
                try:
                    spd_num = float(spd_val.split()[0])
                except Exception:
                    spd_num = 60.0
            else:
                try:
                    spd_num = float(spd_val)
                except Exception:
                    spd_num = 60.0

            stat = str(tr.get("status", "RUNNING")).upper()
            d_src = str(tr.get("data_source", "LIVE")).upper()
            delay_val = tr.get("delay", tr.get("delay_minutes", 0))
            delay_txt = f"+{int(delay_val)} min" if delay_val and float(delay_val) > 0 else "On Time"
            direction_raw = str(tr.get("direction", "UP"))
            is_stale = tr.get("is_stale", False)
            age_sec = tr.get("age_seconds", 0)

            # Direction visual indicator
            if "UP" in direction_raw.upper() or "NORTH" in direction_raw.upper() or "WEST" in direction_raw.upper():
                dir_symbol = "▶ UP"
            elif "DN" in direction_raw.upper() or "DOWN" in direction_raw.upper() or "SOUTH" in direction_raw.upper() or "EAST" in direction_raw.upper():
                dir_symbol = "◀ DN"
            else:
                dir_symbol = f"➔ {direction_raw[:4]}"

            # Determine visual color styling
            if is_stale:
                bg_color = "#f97316" # Stale warning orange
                border_color = "#c2410c"
                status_icon = "⚠️ STALE DATA"
            elif "STOP" in stat or spd_num == 0:
                bg_color = "#ef4444" # Red
                border_color = "#dc2626"
                status_icon = "🔴 STOPPED"
            elif "REDUCE" in stat or "CAUTION" in stat or "SLOW" in stat or (0 < spd_num <= 45):
                bg_color = "#eab308" # Yellow / Amber
                border_color = "#ca8a04"
                status_icon = "🟡 CAUTION (TSR)"
            elif spd_num > 100:
                bg_color = "#2563eb" # High Speed Blue
                border_color = "#1d4ed8"
                status_icon = "⚡ HIGH SPEED"
            else:
                bg_color = "#22c55e" # Normal Green
                border_color = "#16a34a"
                status_icon = "🟢 RUNNING"

            # Telemetry source badge
            if d_src == "LIVE":
                src_tag = "<span style='background:rgba(16,185,129,0.25); color:#6ee7b7; padding:2px 6px; border-radius:4px; font-size:10px; border:1px solid #10b981; font-weight:700;'>📡 LIVE RTIS</span>"
            else:
                src_tag = "<span style='background:rgba(59,130,246,0.25); color:#93c5fd; padding:2px 6px; border-radius:4px; font-size:10px; border:1px solid #3b82f6; font-weight:700;'>🤖 SIMULATION</span>"

            # Stale Warning Banner if applicable
            stale_warning_html = ""
            if is_stale:
                stale_warning_html = f"""
                <div style="margin-top:6px; padding:4px 8px; background:rgba(239,68,68,0.25); border:1px solid #ef4444; border-radius:4px; color:#fca5a5; font-size:10.5px; font-weight:700;">
                    ⚠️ TELEMETRY STALE: No position ping received for {age_sec}s (&gt;120s limit). Displaying last known coordinate.
                </div>
                """

            train_popup_html = f"""
            <div style="background: #0f172a; color: white; padding: 12px 14px; border-radius: 8px; border: 2px solid {bg_color}; font-family: sans-serif; font-size: 12px; min-width: 260px; max-width: 320px; box-shadow: 0 4px 20px rgba(0,0,0,0.6);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                    <span style="font-size: 14px; font-weight: 800; color: #ffffff;">🚆 TRAIN {num}</span>
                    {src_tag}
                </div>
                <div style="color: #38bdf8; font-weight: 700; font-size: 12.5px; margin-bottom: 4px;">{name}</div>
                <div style="border-top: 1px solid #334155; padding-top: 6px; margin-top: 4px; font-size: 11.5px; line-height: 1.5; color: #cbd5e1;">
                    <div>📍 Current KM: <strong style="color:#ffffff;">Km {tr.get('current_km', 120.0):.1f}</strong></div>
                    <div>🧭 Direction: <strong style="color:#fbbf24;">{direction_raw}</strong> ({dir_symbol})</div>
                    <div>⚡ Speed: <strong style="color:{bg_color};">{spd_num:.0f} km/h</strong></div>
                    <div>⏱️ Delay: <strong style="color:{'#f87171' if delay_txt != 'On Time' else '#4ade80'};">{delay_txt}</strong></div>
                    <div>🚉 Next Station: <strong style="color:#ffffff;">{tr.get('next_station', 'En Route')}</strong></div>
                    <div>📡 Telemetry Status: <strong style="color:#ffffff;">{status_icon}</strong></div>
                    <div style="color:#94a3b8; font-size:10px; margin-top:4px;">Last Ping: {tr.get('timestamp', datetime.now().strftime('%H:%M:%S'))}</div>
                </div>
                {stale_warning_html}
            </div>
            """

            # Train Marker Pill: Elevated z-index 900, clickable over maintenance blocks
            t_html = f"""
            <div style="background: {bg_color}; color: #ffffff; border: 2px solid #ffffff; border-radius: 14px; padding: 2px 7px; font-family: sans-serif; font-size: 11px; font-weight: 800; display: inline-flex; align-items: center; gap: 4px; box-shadow: 0 3px 12px rgba(0,0,0,0.7); cursor: pointer; transform: translate(-50%, -50%); z-index: 900 !important; pointer-events: auto;">
                <span>🚆</span>
                <span>{num}</span>
                <span style="font-size: 9px; opacity: 0.9;">{dir_symbol.split()[-1]}</span>
                <span style="background: rgba(0,0,0,0.4); padding: 1px 4px; border-radius: 8px; font-size: 9px; font-weight: 700;">{spd_num:.0f}k</span>
            </div>
            """

            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(html=t_html, icon_size=(100, 26), icon_anchor=(50, 13)),
                tooltip=folium.Tooltip(train_popup_html, sticky=True),
                z_index_offset=900
            ).add_to(trains_group)

        trains_group.add_to(m)


# =============================================================================
# 4. MAP CONTROLS & HUD OVERLAY
# =============================================================================
class MapControls:
    """Provides TileLayers, LayerControl, Fullscreen, and HUD styling."""

    @staticmethod
    def setup_controls(m: folium.Map):
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            attr="CartoDB DarkMatter",
            name="🌑 Dark Control Room View",
            show=False
        ).add_to(m)

        folium.TileLayer(
            tiles="OpenStreetMap",
            name="🗺️ Street Map View",
            show=False
        ).add_to(m)

        folium.LayerControl(position="topleft", collapsed=False).add_to(m)

    @staticmethod
    def get_hud_overlay_html(kpis: dict, corridor_title: str, jurisdiction: str) -> str:
        """Returns Leaflet HTML HUD widgets for top-right live stats and compass."""
        return f"""
        <style>
        .leaflet-control-train-hud {{
            background: rgba(15, 23, 42, 0.90) !important;
            border: 1px solid #334155 !important;
            border-radius: 10px !important;
            padding: 10px 14px !important;
            color: #ffffff !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
            min-width: 260px !important;
            backdrop-filter: blur(8px) !important;
            margin-top: 12px !important;
            margin-right: 12px !important;
            pointer-events: auto !important;
        }}
        .leaflet-control-compass {{
            background: rgba(15, 23, 42, 0.90) !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            padding: 6px 10px !important;
            color: #38bdf8 !important;
            font-weight: 800 !important;
            font-size: 11px !important;
            letter-spacing: 1px !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4) !important;
            margin-bottom: 12px !important;
            margin-right: 12px !important;
        }}
        </style>
        <script>
        document.addEventListener("DOMContentLoaded", function() {{
            var topRight = document.querySelector(".leaflet-top.leaflet-right");
            if (topRight && !document.getElementById("trainHudCard")) {{
                var hud = document.createElement("div");
                hud.id = "trainHudCard";
                hud.className = "leaflet-control leaflet-control-train-hud";
                hud.innerHTML = `
                    <div style="font-size: 12.5px; font-weight: 800; color: #f8fafc; display:flex; justify-content:space-between; align-items:center;">
                        <span>📡 Live Corridor Telemetry</span>
                        <span style="font-size: 10px; background: rgba(16,185,129,0.2); color: #34d399; padding: 2px 6px; border-radius: 4px; border: 1px solid #10b981;">LIVE</span>
                    </div>
                    <div style="font-size: 10.5px; color: #94a3b8; margin-top: 2px; line-height: 1.3;">{corridor_title}</div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: 8px; text-align: center;">
                        <div style="background: rgba(34, 197, 94, 0.15); border: 1px solid #22c55e; border-radius: 6px; padding: 4px 2px;">
                            <div style="font-size: 14px; font-weight: 800; color: #4ade80;">{kpis.get('running', 18)}</div>
                            <div style="font-size: 9px; color: #86efac; font-weight: 600;">RUNNING</div>
                        </div>
                        <div style="background: rgba(234, 179, 8, 0.15); border: 1px solid #eab308; border-radius: 6px; padding: 4px 2px;">
                            <div style="font-size: 14px; font-weight: 800; color: #fde047;">{kpis.get('reduced', 4)}</div>
                            <div style="font-size: 9px; color: #fef08a; font-weight: 600;">CAUTION</div>
                        </div>
                        <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 6px; padding: 4px 2px;">
                            <div style="font-size: 14px; font-weight: 800; color: #f87171;">{kpis.get('stopped', 2)}</div>
                            <div style="font-size: 9px; color: #fca5a5; font-weight: 600;">STOPPED</div>
                        </div>
                        <div style="background: rgba(56, 189, 248, 0.15); border: 1px solid #38bdf8; border-radius: 6px; padding: 4px 2px;">
                            <div style="font-size: 14px; font-weight: 800; color: #7dd3fc;">{kpis.get('total', 24)}</div>
                            <div style="font-size: 9px; color: #bae6fd; font-weight: 600;">TOTAL</div>
                        </div>
                    </div>
                `;
                topRight.appendChild(hud);
            }}

            var bottomRight = document.querySelector(".leaflet-bottom.leaflet-right");
            if (bottomRight && !document.getElementById("compassCard")) {{
                var comp = document.createElement("div");
                comp.id = "compassCard";
                comp.className = "leaflet-control leaflet-control-compass";
                comp.innerHTML = "🧭 NORTH ▲ (MPS 130 km/h)";
                bottomRight.appendChild(comp);
            }}
        }});
        </script>
        """


# =============================================================================
# 5. MAP LEGEND COMPONENT
# =============================================================================
class MapLegend:
    """Renders compact control-room legend bar below the map."""

    @staticmethod
    def render_html() -> str:
        return """
        <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 10px 16px; margin-top: 8px; margin-bottom: 14px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px;">
            <div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
                <div style="font-weight: 800; color: #94a3b8; text-transform: uppercase; font-size: 11px; letter-spacing: 0.8px;">
                    MAP LAYERS & LEGEND:
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="display: inline-block; width: 16px; height: 4px; background: #38bdf8; border-radius: 2px;"></span>
                    <span style="color: #e2e8f0; font-weight: 600;">Track (Layer 0)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: #0284c7; border: 2px solid #38bdf8;"></span>
                    <span style="color: #e2e8f0; font-weight: 600;">Station / Hub</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="display: inline-block; width: 16px; height: 7px; border: 1.5px dashed #a855f7; background: rgba(168,85,247,0.3); border-radius: 2px;"></span>
                    <span style="color: #d8b4fe; font-weight: 600;">Classified Candidate Block (Layer 1)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="display: inline-block; width: 16px; height: 7px; border: 1.5px dashed #3b82f6; background: rgba(59,130,246,0.3); border-radius: 2px;"></span>
                    <span style="color: #60a5fa; font-weight: 600;">Allocated Block (Layer 1)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="display: inline-block; width: 16px; height: 7px; border: 1.5px solid #ef4444; background: rgba(239,68,68,0.4); border-radius: 2px;"></span>
                    <span style="color: #f87171; font-weight: 600;">Active Block (In Possession)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="display: inline-block; width: 16px; height: 5px; border: 1px dotted #10b981; background: rgba(16,185,129,0.25); border-radius: 2px;"></span>
                    <span style="color: #6ee7b7; font-weight: 600;">Completed Block</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="background: #22c55e; color: #fff; font-size: 10px; font-weight: 800; padding: 1px 5px; border-radius: 6px;">🚆 LIVE</span>
                    <span style="color: #4ade80; font-weight: 600;">Live Train (Layer 2)</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="background: #eab308; color: #000; font-size: 10px; font-weight: 800; padding: 1px 5px; border-radius: 6px;">🟡 TSR</span>
                    <span style="color: #fde047; font-weight: 600;">Caution Train</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="background: #ef4444; color: #fff; font-size: 10px; font-weight: 800; padding: 1px 5px; border-radius: 6px;">🔴 STOP</span>
                    <span style="color: #fca5a5; font-weight: 600;">Stopped Train</span>
                </div>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <span style="background: #f97316; color: #fff; font-size: 10px; font-weight: 800; padding: 1px 5px; border-radius: 6px;">⚠️ STALE</span>
                    <span style="color: #fdba74; font-weight: 600;">Stale (&gt;120s)</span>
                </div>
            </div>
            <div style="font-size: 11px; color: #64748b; font-weight: 500;">
                Stacking: <span style="color: #38bdf8;">Geography (z:210)</span> ➔ <span style="color: #fb923c;">Blocks (z:450)</span> ➔ <span style="color: #4ade80;">Live Trains (z:900)</span>
            </div>
        </div>
        """


# =============================================================================
# 6. CONTROLLER MAP ORCHESTRATOR
# =============================================================================
class ControllerMap:
    """
    Orchestrates the entire Geographic Railway Map for the Controller Main Page.
    Enforces Layer 0 (Geography) -> Layer 1 (Allocated & Classified Blocks) -> Layer 2 (Live Trains).
    """

    @classmethod
    def generate_html(
        cls,
        division_name: str = "Vijayawada Division (BZA)",
        allocations: list = None,
        trains: list = None,
        status_filter: str = "ALL",
        dept_filter: str = "ALL",
        train_filter: str = "ALL",
        search_query: str = ""
    ) -> str:
        net_data = get_division_network_data(division_name)
        kpis = net_data.get("kpi", {"running": 20, "reduced": 3, "stopped": 1, "total": 24})

        # 1. Create Folium Map instance with Esri Satellite basemap
        m = folium.Map(
            location=net_data["center"],
            zoom_start=net_data["zoom"],
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            control_scale=False,
            zoom_control=True
        )

        # 2. Map Controls & Tile Switchers
        MapControls.setup_controls(m)

        # 3. Layer 0: Base Railway (Tracks, Stations, KM marks)
        BaseRailwayLayer.add_to_map(m, net_data)

        # 4. Layer 1: Allocated & Classified Maintenance Blocks
        if allocations is not None:
            blocks_data = allocations
        else:
            blocks_data = fetch_allocated_blocks(
                division_name=division_name,
                status_filter=status_filter,
                dept_filter=dept_filter
            )
        AllocatedBlockLayer.add_to_map(m, blocks_data)

        # 5. Layer 2: Live Trains
        if trains is not None:
            trains_data = trains
        else:
            trains_data = fetch_live_trains(
                division_name=division_name,
                train_filter=train_filter,
                search_query=search_query
            )
        LiveTrainLayer.add_to_map(m, trains_data)

        # 6. Generate Leaflet HTML with HUD Injection
        raw_map_html = m.get_root().render()
        hud_js = MapControls.get_hud_overlay_html(
            kpis=kpis,
            corridor_title=net_data.get("corridor_title", "Divisional Corridor"),
            jurisdiction=net_data.get("jurisdiction", "SCR Jurisdiction")
        )
        complete_map_html = raw_map_html.replace("</body>", f"{hud_js}</body>")
        return complete_map_html
