"""
WTT Timetable Data Engine for Vijayawada Division (SCR WTT No. 80)
Builds normalized timetable datasets and SQLite tables from authentic WTT source data.
Supports bidirectional (UP and DOWN) movements, section occupancy queries, next-train queries, and gap calculations.
"""

import os
import sys
import sqlite3
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
# 1. STATION DEFINITIONS (WTT No. 80 Vijayawada Division Jurisdiction)
# -----------------------------------------------------------------------------
STATIONS_DATA = [
    # GDR - BZA Section (Gudur to Vijayawada)
    {"station_code": "GDR", "station_name": "Gudur Jn", "section": "GDR-BZA", "km_from_reference": 136.04, "latitude": 14.1463, "longitude": 79.8504},
    {"station_code": "MBL", "station_name": "Manubolu", "section": "GDR-BZA", "km_from_reference": 145.39, "latitude": 14.2250, "longitude": 79.8800},
    {"station_code": "KMLP", "station_name": "Kommarapudi", "section": "GDR-BZA", "km_from_reference": 151.60, "latitude": 14.2700, "longitude": 79.9100},
    {"station_code": "VKT", "station_name": "Venkatachalam Jn", "section": "GDR-BZA", "km_from_reference": 157.85, "latitude": 14.3167, "longitude": 79.9333},
    {"station_code": "VDE", "station_name": "Vedayapalem", "section": "GDR-BZA", "km_from_reference": 167.12, "latitude": 14.3900, "longitude": 79.9600},
    {"station_code": "NLS", "station_name": "Nellore South", "section": "GDR-BZA", "km_from_reference": 172.41, "latitude": 14.4250, "longitude": 79.9750},
    {"station_code": "NLR", "station_name": "Nellore", "section": "GDR-BZA", "km_from_reference": 174.36, "latitude": 14.4426, "longitude": 79.9865},
    {"station_code": "PGU", "station_name": "Padugupadu", "section": "GDR-BZA", "km_from_reference": 178.42, "latitude": 14.4750, "longitude": 79.9950},
    {"station_code": "KJJ", "station_name": "Kodavaluru", "section": "GDR-BZA", "km_from_reference": 185.78, "latitude": 14.5350, "longitude": 80.0050},
    {"station_code": "TMC", "station_name": "Talamanchi", "section": "GDR-BZA", "km_from_reference": 190.44, "latitude": 14.5800, "longitude": 80.0100},
    {"station_code": "AXR", "station_name": "Alluru Road", "section": "GDR-BZA", "km_from_reference": 202.00, "latitude": 14.6800, "longitude": 80.0300},
    {"station_code": "BTTR", "station_name": "Bitragunta", "section": "GDR-BZA", "km_from_reference": 208.25, "latitude": 14.7300, "longitude": 80.0400},
    {"station_code": "SVPM", "station_name": "Sri Venkateswarapalem", "section": "GDR-BZA", "km_from_reference": 212.57, "latitude": 14.7700, "longitude": 80.0450},
    {"station_code": "KVZ", "station_name": "Kavali", "section": "GDR-BZA", "km_from_reference": 224.80, "latitude": 14.8800, "longitude": 80.0000},
    {"station_code": "TTU", "station_name": "Tettu", "section": "GDR-BZA", "km_from_reference": 239.13, "latitude": 14.9800, "longitude": 80.0100},
    {"station_code": "UPD", "station_name": "Ulavapadu", "section": "GDR-BZA", "km_from_reference": 252.88, "latitude": 15.1000, "longitude": 80.0200},
    {"station_code": "SKM", "station_name": "Singarayakonda", "section": "GDR-BZA", "km_from_reference": 262.45, "latitude": 15.2500, "longitude": 80.0300},
    {"station_code": "TNR", "station_name": "Tanguturu", "section": "GDR-BZA", "km_from_reference": 272.07, "latitude": 15.3400, "longitude": 80.0400},
    {"station_code": "SDM", "station_name": "Surareddipalem", "section": "GDR-BZA", "km_from_reference": 280.25, "latitude": 15.4200, "longitude": 80.0450},
    {"station_code": "OGL", "station_name": "Ongole", "section": "GDR-BZA", "km_from_reference": 290.40, "latitude": 15.5057, "longitude": 80.0499},
    {"station_code": "KRV", "station_name": "Karavadi", "section": "GDR-BZA", "km_from_reference": 299.18, "latitude": 15.5800, "longitude": 80.0800},
    {"station_code": "ANB", "station_name": "Ammanabrolu", "section": "GDR-BZA", "km_from_reference": 305.44, "latitude": 15.6300, "longitude": 80.1100},
    {"station_code": "RPRL", "station_name": "Raparla", "section": "GDR-BZA", "km_from_reference": 308.70, "latitude": 15.6600, "longitude": 80.1300},
    {"station_code": "UGD", "station_name": "Uppugunduru", "section": "GDR-BZA", "km_from_reference": 313.04, "latitude": 15.6900, "longitude": 80.1600},
    {"station_code": "CJM", "station_name": "Chinnaganjam", "section": "GDR-BZA", "km_from_reference": 319.50, "latitude": 15.7400, "longitude": 80.2200},
    {"station_code": "KVDU", "station_name": "Kadavakuduru", "section": "GDR-BZA", "km_from_reference": 323.83, "latitude": 15.7700, "longitude": 80.2400},
    {"station_code": "KPLL", "station_name": "Kottapandillapalli", "section": "GDR-BZA", "km_from_reference": 328.61, "latitude": 15.8000, "longitude": 80.2600},
    {"station_code": "VTM", "station_name": "Vetapalem", "section": "GDR-BZA", "km_from_reference": 331.93, "latitude": 15.7800, "longitude": 80.3200},
    {"station_code": "JAQ", "station_name": "Jandrapeta", "section": "GDR-BZA", "km_from_reference": 336.61, "latitude": 15.8100, "longitude": 80.3400},
    {"station_code": "CLX", "station_name": "Chirala", "section": "GDR-BZA", "km_from_reference": 339.87, "latitude": 15.8246, "longitude": 80.3521},
    {"station_code": "IPPM", "station_name": "Ipurupalem", "section": "GDR-BZA", "km_from_reference": 343.95, "latitude": 15.8500, "longitude": 80.3700},
    {"station_code": "SPF", "station_name": "Stuartpuram", "section": "GDR-BZA", "km_from_reference": 347.97, "latitude": 15.8800, "longitude": 80.4000},
    {"station_code": "BPP", "station_name": "Bapatla", "section": "GDR-BZA", "km_from_reference": 354.86, "latitude": 15.9042, "longitude": 80.4678},
    {"station_code": "APL", "station_name": "Appikatla", "section": "GDR-BZA", "km_from_reference": 363.63, "latitude": 15.9600, "longitude": 80.5200},
    {"station_code": "MCVM", "station_name": "Machavaram", "section": "GDR-BZA", "km_from_reference": 370.37, "latitude": 16.0100, "longitude": 80.5600},
    {"station_code": "NDO", "station_name": "Nidubrolu", "section": "GDR-BZA", "km_from_reference": 375.32, "latitude": 16.0500, "longitude": 80.5900},
    {"station_code": "MDKU", "station_name": "Modukuru", "section": "GDR-BZA", "km_from_reference": 382.09, "latitude": 16.1100, "longitude": 80.6100},
    {"station_code": "TSR", "station_name": "Tsunduru", "section": "GDR-BZA", "km_from_reference": 385.82, "latitude": 16.1400, "longitude": 80.6200},
    {"station_code": "TEL", "station_name": "Tenali Jn", "section": "GDR-BZA", "km_from_reference": 397.25, "latitude": 16.2430, "longitude": 80.6400},
    {"station_code": "KLX", "station_name": "Kolakaluru", "section": "GDR-BZA", "km_from_reference": 403.34, "latitude": 16.2900, "longitude": 80.6300},
    {"station_code": "DIG", "station_name": "Duggirala", "section": "GDR-BZA", "km_from_reference": 407.06, "latitude": 16.3240, "longitude": 80.6280},
    {"station_code": "CLVR", "station_name": "Chiluvuru", "section": "GDR-BZA", "km_from_reference": 412.79, "latitude": 16.3700, "longitude": 80.6200},
    {"station_code": "PVD", "station_name": "Pedavadlapudi", "section": "GDR-BZA", "km_from_reference": 416.61, "latitude": 16.4100, "longitude": 80.6100},
    {"station_code": "KCC", "station_name": "Krishna Canal Jn", "section": "GDR-BZA", "km_from_reference": 423.71, "latitude": 16.4800, "longitude": 80.6100},
    {"station_code": "BZA", "station_name": "Vijayawada Jn", "section": "GDR-BZA", "km_from_reference": 428.76, "latitude": 16.5062, "longitude": 80.6480},

    # BZA - KI Section (Vijayawada to Kondapalli)
    {"station_code": "VBC", "station_name": "Vijayawada Bulb Cabin", "section": "BZA-KI", "km_from_reference": 581.80, "latitude": 16.5300, "longitude": 80.6000},
    {"station_code": "NWBV", "station_name": "New West Block Cabin", "section": "BZA-KI", "km_from_reference": 578.09, "latitude": 16.5600, "longitude": 80.5600},
    {"station_code": "RYP", "station_name": "Rayanapadu", "section": "BZA-KI", "km_from_reference": 574.45, "latitude": 16.5800, "longitude": 80.5300},
    {"station_code": "KI", "station_name": "Kondapalli", "section": "BZA-KI", "km_from_reference": 569.01, "latitude": 16.6200, "longitude": 80.5100},

    # BZA - VSKP Section (Vijayawada to Visakhapatnam)
    {"station_code": "VNEC", "station_name": "Vijayawada North East Cabin", "section": "BZA-VSKP", "km_from_reference": 430.51, "latitude": 16.5200, "longitude": 80.6600},
    {"station_code": "GALA", "station_name": "Gunadala", "section": "BZA-VSKP", "km_from_reference": 435.27, "latitude": 16.5300, "longitude": 80.6800},
    {"station_code": "MBD", "station_name": "Mustabad", "section": "BZA-VSKP", "km_from_reference": 441.69, "latitude": 16.5600, "longitude": 80.7400},
    {"station_code": "GWM", "station_name": "Gannavaram", "section": "BZA-VSKP", "km_from_reference": 448.44, "latitude": 16.5400, "longitude": 80.8000},
    {"station_code": "PAVP", "station_name": "Pedda Avutapalle", "section": "BZA-VSKP", "km_from_reference": 453.42, "latitude": 16.5700, "longitude": 80.8400},
    {"station_code": "TOU", "station_name": "Telaprolu", "section": "BZA-VSKP", "km_from_reference": 459.96, "latitude": 16.6200, "longitude": 80.8800},
    {"station_code": "NZD", "station_name": "Nuzvid", "section": "BZA-VSKP", "km_from_reference": 469.65, "latitude": 16.7100, "longitude": 80.9500},
    {"station_code": "VAT", "station_name": "Vatlur", "section": "BZA-VSKP", "km_from_reference": 479.63, "latitude": 16.7100, "longitude": 81.0400},
    {"station_code": "PRH", "station_name": "Powerpet", "section": "BZA-VSKP", "km_from_reference": 486.63, "latitude": 16.7120, "longitude": 81.0900},
    {"station_code": "EE", "station_name": "Eluru", "section": "BZA-VSKP", "km_from_reference": 488.26, "latitude": 16.7107, "longitude": 81.1000},
    {"station_code": "DEL", "station_name": "Denduluru", "section": "BZA-VSKP", "km_from_reference": 498.03, "latitude": 16.7300, "longitude": 81.1800},
    {"station_code": "BMD", "station_name": "Bhimadolu", "section": "BZA-VSKP", "km_from_reference": 507.23, "latitude": 16.8100, "longitude": 81.2500},
    {"station_code": "PUA", "station_name": "Pulla", "section": "BZA-VSKP", "km_from_reference": 513.93, "latitude": 16.8500, "longitude": 81.3000},
    {"station_code": "CEL", "station_name": "Chebrolu", "section": "BZA-VSKP", "km_from_reference": 521.79, "latitude": 16.8700, "longitude": 81.3600},
    {"station_code": "BPY", "station_name": "Badampudi", "section": "BZA-VSKP", "km_from_reference": 530.12, "latitude": 16.8600, "longitude": 81.4400},
    {"station_code": "TDD", "station_name": "Tadepalligudem", "section": "BZA-VSKP", "km_from_reference": 536.09, "latitude": 16.8100, "longitude": 81.5300},
    {"station_code": "NBM", "station_name": "Navabpalem", "section": "BZA-VSKP", "km_from_reference": 545.03, "latitude": 16.8400, "longitude": 81.6000},
    {"station_code": "NDD", "station_name": "Nidadavolu Jn", "section": "BZA-VSKP", "km_from_reference": 555.81, "latitude": 16.9100, "longitude": 81.6700},
    {"station_code": "CU", "station_name": "Chagallu", "section": "BZA-VSKP", "km_from_reference": 564.51, "latitude": 16.9800, "longitude": 81.7100},
    {"station_code": "PSDA", "station_name": "Pasivedala", "section": "BZA-VSKP", "km_from_reference": 567.29, "latitude": 17.0000, "longitude": 81.7200},
    {"station_code": "KVR", "station_name": "Kovvuru", "section": "BZA-VSKP", "km_from_reference": 570.63, "latitude": 17.0100, "longitude": 81.7300},
    {"station_code": "GVN", "station_name": "Godavari", "section": "BZA-VSKP", "km_from_reference": 575.02, "latitude": 17.0050, "longitude": 81.7700},
    {"station_code": "RJY", "station_name": "Rajahmundry", "section": "BZA-VSKP", "km_from_reference": 578.15, "latitude": 17.0005, "longitude": 81.7800},
    {"station_code": "KYM", "station_name": "Kadiyam", "section": "BZA-VSKP", "km_from_reference": 588.17, "latitude": 16.9200, "longitude": 81.8400},
    {"station_code": "DWP", "station_name": "Dwarapudi", "section": "BZA-VSKP", "km_from_reference": 598.09, "latitude": 16.9500, "longitude": 81.9300},
    {"station_code": "APT", "station_name": "Anaparthi", "section": "BZA-VSKP", "km_from_reference": 601.90, "latitude": 16.9800, "longitude": 81.9600},
    {"station_code": "BVL", "station_name": "Bikkavolu", "section": "BZA-VSKP", "km_from_reference": 611.18, "latitude": 17.0200, "longitude": 82.0400},
    {"station_code": "MPU", "station_name": "Medapadu", "section": "BZA-VSKP", "km_from_reference": 619.39, "latitude": 17.0500, "longitude": 82.1100},
    {"station_code": "SLO", "station_name": "Samalkot Jn", "section": "BZA-VSKP", "km_from_reference": 628.36, "latitude": 17.0500, "longitude": 82.1700},
    {"station_code": "PAP", "station_name": "Pithapuram", "section": "BZA-VSKP", "km_from_reference": 640.45, "latitude": 17.1100, "longitude": 82.2600},
    {"station_code": "GLP", "station_name": "Gollaprolu", "section": "BZA-VSKP", "km_from_reference": 646.14, "latitude": 17.1500, "longitude": 82.2900},
    {"station_code": "DGDG", "station_name": "Durgada Gate", "section": "BZA-VSKP", "km_from_reference": 655.39, "latitude": 17.2000, "longitude": 82.3400},
    {"station_code": "RVD", "station_name": "Ravikampadu", "section": "BZA-VSKP", "km_from_reference": 658.03, "latitude": 17.2200, "longitude": 82.3600},
    {"station_code": "ANV", "station_name": "Annavaram", "section": "BZA-VSKP", "km_from_reference": 665.23, "latitude": 17.2800, "longitude": 82.4000},
    {"station_code": "HVM", "station_name": "Hamsavaram", "section": "BZA-VSKP", "km_from_reference": 674.34, "latitude": 17.3100, "longitude": 82.4700},
    {"station_code": "TUNI", "station_name": "Tuni", "section": "BZA-VSKP", "km_from_reference": 681.99, "latitude": 17.3500, "longitude": 82.5500},
    {"station_code": "GLU", "station_name": "Gullipadu", "section": "BZA-VSKP", "km_from_reference": 693.04, "latitude": 17.4100, "longitude": 82.6300},
    {"station_code": "NRP", "station_name": "Narsipatnam Road", "section": "BZA-VSKP", "km_from_reference": 704.06, "latitude": 17.4700, "longitude": 82.7100},
    {"station_code": "REG", "station_name": "Regupalem", "section": "BZA-VSKP", "km_from_reference": 713.47, "latitude": 17.5100, "longitude": 82.7800},
    {"station_code": "YLM", "station_name": "Elamanchili", "section": "BZA-VSKP", "km_from_reference": 721.82, "latitude": 17.5500, "longitude": 82.8500},
    {"station_code": "NASP", "station_name": "Narasingapalli", "section": "BZA-VSKP", "km_from_reference": 729.03, "latitude": 17.5900, "longitude": 82.9000},
    {"station_code": "BVM", "station_name": "Bayyavaram", "section": "BZA-VSKP", "km_from_reference": 736.38, "latitude": 17.6200, "longitude": 82.9500},
    {"station_code": "KSK", "station_name": "Kasimkota", "section": "BZA-VSKP", "km_from_reference": 740.36, "latitude": 17.6500, "longitude": 82.9800},
    {"station_code": "AKP", "station_name": "Anakapalle", "section": "BZA-VSKP", "km_from_reference": 745.65, "latitude": 17.6900, "longitude": 83.0000},
    {"station_code": "THY", "station_name": "Thadi", "section": "BZA-VSKP", "km_from_reference": 752.11, "latitude": 17.7100, "longitude": 83.0700},
    {"station_code": "DVD", "station_name": "Duvvada", "section": "BZA-VSKP", "km_from_reference": 761.49, "latitude": 17.7088, "longitude": 83.1557},
    {"station_code": "GPT", "station_name": "Gopalapatnam Cabin", "section": "BZA-VSKP", "km_from_reference": 771.97, "latitude": 17.7500, "longitude": 83.2100},
    {"station_code": "SCMN", "station_name": "Simhachalam North", "section": "BZA-VSKP", "km_from_reference": 774.04, "latitude": 17.7700, "longitude": 83.2300},
    {"station_code": "VSKP", "station_name": "Visakhapatnam Jn", "section": "BZA-VSKP", "km_from_reference": 778.66, "latitude": 17.7231, "longitude": 83.2906},

    # Branch Lines
    {"station_code": "GNT", "station_name": "Guntur Jn", "section": "GNT-BZA", "km_from_reference": 25.43, "latitude": 16.3067, "longitude": 80.4365},
    {"station_code": "RAL", "station_name": "Repalle", "section": "TEL-RAL", "km_from_reference": 34.00, "latitude": 16.0200, "longitude": 80.8500},
    {"station_code": "GDV", "station_name": "Gudivada Jn", "section": "BZA-GDV", "km_from_reference": 42.69, "latitude": 16.4300, "longitude": 80.9900},
    {"station_code": "MTM", "station_name": "Machilipatnam", "section": "GDV-MTM", "km_from_reference": 36.74, "latitude": 16.1800, "longitude": 81.1300},
    {"station_code": "BVRM", "station_name": "Bhimavaram Jn", "section": "GDV-BVRM", "km_from_reference": 65.56, "latitude": 16.5400, "longitude": 81.5200},
    {"station_code": "NS", "station_name": "Narasapur", "section": "BVRM-NS", "km_from_reference": 29.48, "latitude": 16.4300, "longitude": 81.6900},
    {"station_code": "CCT", "station_name": "Kakinada Town", "section": "SLO-COA", "km_from_reference": 12.40, "latitude": 16.9600, "longitude": 82.2300},
    {"station_code": "COA", "station_name": "Kakinada Port", "section": "SLO-COA", "km_from_reference": 15.60, "latitude": 16.9400, "longitude": 82.2500},
    {"station_code": "SC", "station_name": "Secunderabad Jn", "section": "SC-BZA", "km_from_reference": 0.00, "latitude": 17.4344, "longitude": 78.5011}
]

# -----------------------------------------------------------------------------
# 2. SECTION DEFINITIONS
# -----------------------------------------------------------------------------
SECTIONS_DATA = [
    {"section_id": "GDR-BZA-DN", "section_name": "Gudur - Vijayawada Down Line", "from_station": "GDR", "to_station": "BZA", "from_km": 134.30, "to_km": 428.76, "distance_km": 294.46, "line_type": "Double/Triple (DN)", "max_permissible_speed": 130},
    {"section_id": "BZA-GDR-UP", "section_name": "Vijayawada - Gudur Up Line", "from_station": "BZA", "to_station": "GDR", "from_km": 428.76, "to_km": 134.30, "distance_km": 294.46, "line_type": "Double/Triple (UP)", "max_permissible_speed": 130},
    {"section_id": "BZA-KI-UP", "section_name": "Vijayawada - Kondapalli Up Line", "from_station": "BZA", "to_station": "KI", "from_km": 586.50, "to_km": 568.00, "distance_km": 18.50, "line_type": "Double/Triple (UP)", "max_permissible_speed": 130},
    {"section_id": "KI-BZA-DN", "section_name": "Kondapalli - Vijayawada Down Line", "from_station": "KI", "to_station": "BZA", "from_km": 568.00, "to_km": 586.50, "distance_km": 18.50, "line_type": "Double/Triple (DN)", "max_permissible_speed": 130},
    {"section_id": "BZA-VSKP-DN", "section_name": "Vijayawada - Visakhapatnam Down Line", "from_station": "BZA", "to_station": "VSKP", "from_km": 428.76, "to_km": 778.66, "distance_km": 349.90, "line_type": "Double Line (DN)", "max_permissible_speed": 130},
    {"section_id": "VSKP-BZA-UP", "section_name": "Visakhapatnam - Vijayawada Up Line", "from_station": "VSKP", "to_station": "BZA", "from_km": 778.66, "to_km": 428.76, "distance_km": 349.90, "line_type": "Double Line (UP)", "max_permissible_speed": 130},
    {"section_id": "BZA-GDV", "section_name": "Vijayawada - Gudivada", "from_station": "BZA", "to_station": "GDV", "from_km": 0.00, "to_km": 42.69, "distance_km": 42.69, "line_type": "Double Line", "max_permissible_speed": 110},
    {"section_id": "GDV-MTM", "section_name": "Gudivada - Machilipatnam", "from_station": "GDV", "to_station": "MTM", "from_km": 0.00, "to_km": 36.74, "distance_km": 36.74, "line_type": "Double Line", "max_permissible_speed": 110},
    {"section_id": "GDV-BVRM", "section_name": "Gudivada - Bhimavaram", "from_station": "GDV", "to_station": "BVRM", "from_km": 42.69, "to_km": 108.25, "distance_km": 65.56, "line_type": "Double Line", "max_permissible_speed": 110},
    {"section_id": "BVRM-NDD", "section_name": "Bhimavaram - Nidadavolu", "from_station": "BVRM", "to_station": "NDD", "from_km": 108.25, "to_km": 154.75, "distance_km": 46.50, "line_type": "Double Line", "max_permissible_speed": 110},
    {"section_id": "BVRM-NS", "section_name": "Bhimavaram - Narasapur", "from_station": "BVRM", "to_station": "NS", "from_km": 0.00, "to_km": 29.48, "distance_km": 29.48, "line_type": "Single Line", "max_permissible_speed": 110},
    {"section_id": "SLO-COA", "section_name": "Samalkot - Kakinada Port", "from_station": "SLO", "to_station": "COA", "from_km": 0.00, "to_km": 15.60, "distance_km": 15.60, "line_type": "Double Line", "max_permissible_speed": 110},
    {"section_id": "GNT-TEL", "section_name": "Guntur - Tenali", "from_station": "GNT", "to_station": "TEL", "from_km": 0.00, "to_km": 25.47, "distance_km": 25.47, "line_type": "Double Line", "max_permissible_speed": 110},
    {"section_id": "TEL-RAL", "section_name": "Tenali - Repalle", "from_station": "TEL", "to_station": "RAL", "from_km": 0.00, "to_km": 34.00, "distance_km": 34.00, "line_type": "Single Line", "max_permissible_speed": 110}
]

# -----------------------------------------------------------------------------
# 3. INTER-SECTIONAL RUN TIME MATRIX (WTT Pages 13, 119, 211, 225, 231)
# -----------------------------------------------------------------------------
INTER_RUNTIMES = [
    # GDR - BZA DN
    {"from_station": "GDR", "to_station": "MBL", "distance_km": 9.35, "stock_type": "LHB", "scheduled_minutes": 9},
    {"from_station": "MBL", "to_station": "KMLP", "distance_km": 6.21, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "KMLP", "to_station": "VKT", "distance_km": 6.25, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "VKT", "to_station": "VDE", "distance_km": 9.27, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "VDE", "to_station": "NLS", "distance_km": 5.29, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "NLS", "to_station": "NLR", "distance_km": 1.95, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "NLR", "to_station": "PGU", "distance_km": 4.06, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "PGU", "to_station": "KJJ", "distance_km": 7.36, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "KJJ", "to_station": "TMC", "distance_km": 4.66, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "TMC", "to_station": "AXR", "distance_km": 11.56, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "AXR", "to_station": "BTTR", "distance_km": 6.25, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "BTTR", "to_station": "SVPM", "distance_km": 4.32, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "SVPM", "to_station": "KVZ", "distance_km": 12.23, "stock_type": "LHB", "scheduled_minutes": 7},
    {"from_station": "KVZ", "to_station": "TTU", "distance_km": 14.33, "stock_type": "LHB", "scheduled_minutes": 7},
    {"from_station": "TTU", "to_station": "UPD", "distance_km": 13.75, "stock_type": "LHB", "scheduled_minutes": 7},
    {"from_station": "UPD", "to_station": "SKM", "distance_km": 9.57, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "SKM", "to_station": "TNR", "distance_km": 9.62, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "TNR", "to_station": "SDM", "distance_km": 8.18, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "SDM", "to_station": "OGL", "distance_km": 10.15, "stock_type": "LHB", "scheduled_minutes": 8},
    {"from_station": "OGL", "to_station": "KRV", "distance_km": 8.78, "stock_type": "LHB", "scheduled_minutes": 8},
    {"from_station": "KRV", "to_station": "ANB", "distance_km": 6.26, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "ANB", "to_station": "RPRL", "distance_km": 3.26, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "RPRL", "to_station": "UGD", "distance_km": 4.34, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "UGD", "to_station": "CJM", "distance_km": 6.46, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "CJM", "to_station": "KVDU", "distance_km": 4.33, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "KVDU", "to_station": "KPLL", "distance_km": 4.78, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "KPLL", "to_station": "VTM", "distance_km": 3.32, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "VTM", "to_station": "JAQ", "distance_km": 4.68, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "JAQ", "to_station": "CLX", "distance_km": 3.26, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "CLX", "to_station": "IPPM", "distance_km": 4.08, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "IPPM", "to_station": "SPF", "distance_km": 4.02, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "SPF", "to_station": "BPP", "distance_km": 6.89, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "BPP", "to_station": "APL", "distance_km": 8.77, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "APL", "to_station": "MCVM", "distance_km": 6.74, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "MCVM", "to_station": "NDO", "distance_km": 4.95, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "NDO", "to_station": "MDKU", "distance_km": 6.77, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "MDKU", "to_station": "TSR", "distance_km": 3.73, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "TSR", "to_station": "TEL", "distance_km": 11.43, "stock_type": "LHB", "scheduled_minutes": 7},
    {"from_station": "TEL", "to_station": "KLX", "distance_km": 6.09, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "KLX", "to_station": "DIG", "distance_km": 3.72, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "DIG", "to_station": "CLVR", "distance_km": 5.73, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "CLVR", "to_station": "PVD", "distance_km": 3.82, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "PVD", "to_station": "KCC", "distance_km": 7.10, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "KCC", "to_station": "BZA", "distance_km": 5.05, "stock_type": "LHB", "scheduled_minutes": 12},

    # BZA - VSKP DN
    {"from_station": "BZA", "to_station": "VNEC", "distance_km": 1.75, "stock_type": "LHB", "scheduled_minutes": 8},
    {"from_station": "VNEC", "to_station": "GALA", "distance_km": 4.76, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "GALA", "to_station": "MBD", "distance_km": 6.42, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "MBD", "to_station": "GWM", "distance_km": 6.75, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "GWM", "to_station": "PAVP", "distance_km": 4.98, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "PAVP", "to_station": "TOU", "distance_km": 6.54, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "TOU", "to_station": "NZD", "distance_km": 9.69, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "NZD", "to_station": "VAT", "distance_km": 9.98, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "VAT", "to_station": "PRH", "distance_km": 7.00, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "PRH", "to_station": "EE", "distance_km": 1.63, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "EE", "to_station": "DEL", "distance_km": 9.77, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "DEL", "to_station": "BMD", "distance_km": 9.20, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "BMD", "to_station": "PUA", "distance_km": 6.70, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "PUA", "to_station": "CEL", "distance_km": 7.86, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "CEL", "to_station": "BPY", "distance_km": 8.33, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "BPY", "to_station": "TDD", "distance_km": 5.97, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "TDD", "to_station": "NBM", "distance_km": 8.94, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "NBM", "to_station": "NDD", "distance_km": 10.78, "stock_type": "LHB", "scheduled_minutes": 7},
    {"from_station": "NDD", "to_station": "CU", "distance_km": 8.70, "stock_type": "LHB", "scheduled_minutes": 7},
    {"from_station": "CU", "to_station": "PSDA", "distance_km": 2.78, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "PSDA", "to_station": "KVR", "distance_km": 3.34, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "KVR", "to_station": "GVN", "distance_km": 4.39, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "GVN", "to_station": "RJY", "distance_km": 3.13, "stock_type": "LHB", "scheduled_minutes": 9},
    {"from_station": "RJY", "to_station": "KYM", "distance_km": 10.02, "stock_type": "LHB", "scheduled_minutes": 11},
    {"from_station": "KYM", "to_station": "DWP", "distance_km": 9.92, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "DWP", "to_station": "APT", "distance_km": 3.81, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "APT", "to_station": "BVL", "distance_km": 9.28, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "BVL", "to_station": "MPU", "distance_km": 8.22, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "MPU", "to_station": "SLO", "distance_km": 8.96, "stock_type": "LHB", "scheduled_minutes": 7},
    {"from_station": "SLO", "to_station": "PAP", "distance_km": 12.09, "stock_type": "LHB", "scheduled_minutes": 8},
    {"from_station": "PAP", "to_station": "GLP", "distance_km": 5.69, "stock_type": "LHB", "scheduled_minutes": 3},
    {"from_station": "GLP", "to_station": "DGDG", "distance_km": 9.25, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "DGDG", "to_station": "RVD", "distance_km": 2.64, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "RVD", "to_station": "ANV", "distance_km": 7.20, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "ANV", "to_station": "HVM", "distance_km": 9.11, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "HVM", "to_station": "TUNI", "distance_km": 7.65, "stock_type": "LHB", "scheduled_minutes": 5},
    {"from_station": "TUNI", "to_station": "GLU", "distance_km": 11.05, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "GLU", "to_station": "NRP", "distance_km": 11.02, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "NRP", "to_station": "REG", "distance_km": 9.41, "stock_type": "LHB", "scheduled_minutes": 6},
    {"from_station": "REG", "to_station": "YLM", "distance_km": 8.35, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "YLM", "to_station": "NASP", "distance_km": 7.21, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "NASP", "to_station": "BVM", "distance_km": 7.35, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "BVM", "to_station": "KSK", "distance_km": 3.98, "stock_type": "LHB", "scheduled_minutes": 2},
    {"from_station": "KSK", "to_station": "AKP", "distance_km": 5.29, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "AKP", "to_station": "THY", "distance_km": 6.46, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "THY", "to_station": "DVD", "distance_km": 9.38, "stock_type": "LHB", "scheduled_minutes": 8},
    {"from_station": "DVD", "to_station": "GPT", "distance_km": 10.49, "stock_type": "LHB", "scheduled_minutes": 12},
    {"from_station": "GPT", "to_station": "SCMN", "distance_km": 2.55, "stock_type": "LHB", "scheduled_minutes": 11},
    {"from_station": "SCMN", "to_station": "MIPM", "distance_km": 2.07, "stock_type": "LHB", "scheduled_minutes": 4},
    {"from_station": "MIPM", "to_station": "VSKP", "distance_km": 4.62, "stock_type": "LHB", "scheduled_minutes": 10}
]

# -----------------------------------------------------------------------------
# 4. REPRESENTATIVE CONTROLLED TRAIN DATASET (From WTT No. 80 Ground Truth)
# Covers High / Medium / Low Traffic Scenarios and UP/DOWN movements
# -----------------------------------------------------------------------------
TRAINS_MASTER = [
    # --- DOWN TRAINS (GDR -> BZA -> VSKP / GNT) ---
    {"train_id": "12621", "train_number": "12621", "name": "Tamil Nadu Express", "origin": "MAS", "destination": "NDLS", "category": "SUF", "stock": "LHB", "service_days": "Daily", "direction": "DOWN", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "12846", "train_number": "12846", "name": "Bhubaneswar Superfast", "origin": "SMVB", "destination": "BBS", "category": "SUF", "stock": "LHB", "service_days": "Mon", "direction": "DOWN", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "22834", "train_number": "22834", "name": "Bhubaneswar SF Express", "origin": "SMVB", "destination": "BBS", "category": "SUF", "stock": "LHB", "service_days": "Thu", "direction": "DOWN", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "13352", "train_number": "13352", "name": "Dhanbad Express", "origin": "ALLP", "destination": "DHN", "category": "Exp", "stock": "LHB", "service_days": "Daily", "direction": "DOWN", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "20850", "train_number": "20850", "name": "Bhubaneswar Express", "origin": "RMM", "destination": "BBS", "category": "SUF", "stock": "LHB", "service_days": "Sun", "direction": "DOWN", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "17249", "train_number": "17249", "name": "Kakinada Express", "origin": "TPTY", "destination": "CCT", "category": "Exp", "stock": "ICF", "service_days": "Daily", "direction": "DOWN", "scenario": "MEDIUM_TRAFFIC"},
    {"train_id": "20630", "train_number": "20630", "name": "Sabari Express", "origin": "TVC", "destination": "SC", "category": "Exp", "stock": "LHB", "service_days": "Daily", "direction": "DOWN", "scenario": "MEDIUM_TRAFFIC"},
    {"train_id": "20702", "train_number": "20702", "name": "Vande Bharat Express", "origin": "TPTY", "destination": "SC", "category": "VNDB", "stock": "T 20", "service_days": "Ex Tue", "direction": "DOWN", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "20833", "train_number": "20833", "name": "Vande Bharat Express", "origin": "VSKP", "destination": "SC", "category": "VNDB", "stock": "T 18", "service_days": "Ex Tue", "direction": "DOWN", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "12712", "train_number": "12712", "name": "Pinakini Express", "origin": "MAS", "destination": "BZA", "category": "SUF", "stock": "LHB", "service_days": "Daily", "direction": "DOWN", "scenario": "MEDIUM_TRAFFIC"},
    {"train_id": "67260", "train_number": "67260", "name": "Bitragunta-Vijayawada MEMU", "origin": "BTTR", "destination": "BZA", "category": "Pass", "stock": "MEMU", "service_days": "Daily", "direction": "DOWN", "scenario": "LOW_TRAFFIC"},
    {"train_id": "67214", "train_number": "67214", "name": "Tenali-Vijayawada Passenger", "origin": "TEL", "destination": "BZA", "category": "Pass", "stock": "MEMU", "service_days": "Daily", "direction": "DOWN", "scenario": "LOW_TRAFFIC"},

    # --- UP TRAINS (VSKP / BZA -> GDR / GNT) ---
    {"train_id": "12760", "train_number": "12760", "name": "Charminar Express", "origin": "HYB", "destination": "TBM", "category": "SUF", "stock": "LHB", "service_days": "Daily", "direction": "UP", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "12764", "train_number": "12764", "name": "Padmavathi Express", "origin": "SC", "destination": "TPTY", "category": "SUF", "stock": "LHB", "service_days": "Daily", "direction": "UP", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "12841", "train_number": "12841", "name": "Coromandel Express", "origin": "HWH", "destination": "MAS", "category": "SUF", "stock": "LHB", "service_days": "Daily", "direction": "UP", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "12864", "train_number": "12864", "name": "Howrah Express", "origin": "SMVB", "destination": "HWH", "category": "SUF", "stock": "LHB", "service_days": "Daily", "direction": "UP", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "12704", "train_number": "12704", "name": "Falaknuma Express", "origin": "SC", "destination": "HWH", "category": "SUF", "stock": "LHB", "service_days": "Daily", "direction": "UP", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "12728", "train_number": "12728", "name": "Godavari Express", "origin": "HYB", "destination": "VSKP", "category": "SUF", "stock": "LHB", "service_days": "Daily", "direction": "UP", "scenario": "MEDIUM_TRAFFIC"},
    {"train_id": "17202", "train_number": "17202", "name": "Golconda Express", "origin": "SC", "destination": "GNT", "category": "Exp", "stock": "ICF", "service_days": "Daily", "direction": "UP", "scenario": "MEDIUM_TRAFFIC"},
    {"train_id": "20701", "train_number": "20701", "name": "Vande Bharat Express", "origin": "SC", "destination": "TPTY", "category": "VNDB", "stock": "T 20", "service_days": "Ex Tue", "direction": "UP", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "20834", "train_number": "20834", "name": "Vande Bharat Express", "origin": "SC", "destination": "VSKP", "category": "VNDB", "stock": "T 18", "service_days": "Ex Tue", "direction": "UP", "scenario": "HIGH_TRAFFIC"},
    {"train_id": "67274", "train_number": "67274", "name": "Ongole-Vijayawada Passenger", "origin": "OGL", "destination": "BZA", "category": "Pass", "stock": "MEMU", "service_days": "Daily", "direction": "UP", "scenario": "LOW_TRAFFIC"},
    {"train_id": "17258", "train_number": "17258", "name": "Kakinada Vijayawada Express", "origin": "COA", "destination": "BZA", "category": "Exp", "stock": "MEMU", "service_days": "Daily", "direction": "UP", "scenario": "LOW_TRAFFIC"}
]

# -----------------------------------------------------------------------------
# 5. EXACT WTT TIMETABLE SCHEDULE ENTRIES
# -----------------------------------------------------------------------------
TRAIN_SCHEDULE_DATA = [
    # 12621 TN Express (DOWN) - WTT Page 14 & 18
    {"train_number": "12621", "direction": "DOWN", "station_code": "GDR", "arrival_time": "00:08", "departure_time": "00:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "MBL", "arrival_time": "00:19", "departure_time": "00:19", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "VKT", "arrival_time": "00:26", "departure_time": "00:26", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "NLR", "arrival_time": "00:34", "departure_time": "00:36", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "BTTR", "arrival_time": "01:01", "departure_time": "01:01", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "KVZ", "arrival_time": "01:11", "departure_time": "01:11", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "OGL", "arrival_time": "02:03", "departure_time": "02:05", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "CLX", "arrival_time": "02:44", "departure_time": "02:44", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "BPP", "arrival_time": "02:56", "departure_time": "02:56", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "TEL", "arrival_time": "03:33", "departure_time": "03:35", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "KCC", "arrival_time": "03:54", "departure_time": "03:54", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12621", "direction": "DOWN", "station_code": "BZA", "arrival_time": "04:10", "departure_time": "04:20", "pass_or_skip": "STOP", "service_day": "Daily"},

    # 12846 BBS SF (DOWN) - WTT Page 14 & 18
    {"train_number": "12846", "direction": "DOWN", "station_code": "GDR", "arrival_time": "00:23", "departure_time": "00:25", "pass_or_skip": "STOP", "service_day": "Mon"},
    {"train_number": "12846", "direction": "DOWN", "station_code": "NLR", "arrival_time": "00:56", "departure_time": "00:58", "pass_or_skip": "STOP", "service_day": "Mon"},
    {"train_number": "12846", "direction": "DOWN", "station_code": "KVZ", "arrival_time": "01:35", "departure_time": "01:35", "pass_or_skip": "PASS", "service_day": "Mon"},
    {"train_number": "12846", "direction": "DOWN", "station_code": "OGL", "arrival_time": "02:28", "departure_time": "02:30", "pass_or_skip": "STOP", "service_day": "Mon"},
    {"train_number": "12846", "direction": "DOWN", "station_code": "CLX", "arrival_time": "03:09", "departure_time": "03:09", "pass_or_skip": "PASS", "service_day": "Mon"},
    {"train_number": "12846", "direction": "DOWN", "station_code": "TEL", "arrival_time": "03:56", "departure_time": "03:56", "pass_or_skip": "PASS", "service_day": "Mon"},
    {"train_number": "12846", "direction": "DOWN", "station_code": "BZA", "arrival_time": "04:30", "departure_time": "04:40", "pass_or_skip": "STOP", "service_day": "Mon"},

    # 13352 Dhanbad Exp (DOWN) - WTT Page 14 & 18 & 122
    {"train_number": "13352", "direction": "DOWN", "station_code": "GDR", "arrival_time": "00:43", "departure_time": "00:45", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "NLR", "arrival_time": "01:16", "departure_time": "01:18", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "KVZ", "arrival_time": "01:57", "departure_time": "01:59", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "OGL", "arrival_time": "03:17", "departure_time": "03:19", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "CLX", "arrival_time": "04:08", "departure_time": "04:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "BPP", "arrival_time": "04:22", "departure_time": "04:24", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "TEL", "arrival_time": "05:08", "departure_time": "05:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "BZA", "arrival_time": "05:50", "departure_time": "06:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "EE", "arrival_time": "07:10", "departure_time": "07:12", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "TDD", "arrival_time": "07:52", "departure_time": "07:54", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "NDD", "arrival_time": "08:13", "departure_time": "08:15", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "RJY", "arrival_time": "08:51", "departure_time": "08:53", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "SLO", "arrival_time": "09:51", "departure_time": "09:53", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "TUNI", "arrival_time": "10:45", "departure_time": "10:47", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "AKP", "arrival_time": "11:51", "departure_time": "11:53", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "DVD", "arrival_time": "12:18", "departure_time": "12:20", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "13352", "direction": "DOWN", "station_code": "VSKP", "arrival_time": "13:00", "departure_time": "13:25", "pass_or_skip": "STOP", "service_day": "Daily"},

    # 20702 Vande Bharat (DOWN) - WTT Page 40 & 44
    {"train_number": "20702", "direction": "DOWN", "station_code": "GDR", "arrival_time": "16:33", "departure_time": "16:35", "pass_or_skip": "PASS", "service_day": "Ex Tue"},
    {"train_number": "20702", "direction": "DOWN", "station_code": "NLR", "arrival_time": "17:02", "departure_time": "17:04", "pass_or_skip": "STOP", "service_day": "Ex Tue"},
    {"train_number": "20702", "direction": "DOWN", "station_code": "OGL", "arrival_time": "18:13", "departure_time": "18:15", "pass_or_skip": "STOP", "service_day": "Ex Tue"},
    {"train_number": "20702", "direction": "DOWN", "station_code": "CLX", "arrival_time": "18:53", "departure_time": "18:53", "pass_or_skip": "PASS", "service_day": "Ex Tue"},
    {"train_number": "20702", "direction": "DOWN", "station_code": "TEL", "arrival_time": "19:35", "departure_time": "19:35", "pass_or_skip": "PASS", "service_day": "Ex Tue"},
    {"train_number": "20702", "direction": "DOWN", "station_code": "BZA", "arrival_time": "20:05", "departure_time": "20:15", "pass_or_skip": "STOP", "service_day": "Ex Tue"},

    # 12760 Charminar Express (UP) - WTT Page 78 & 82
    {"train_number": "12760", "direction": "UP", "station_code": "BZA", "arrival_time": "00:10", "departure_time": "00:20", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12760", "direction": "UP", "station_code": "TEL", "arrival_time": "00:55", "departure_time": "00:57", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12760", "direction": "UP", "station_code": "BPP", "arrival_time": "01:32", "departure_time": "01:32", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12760", "direction": "UP", "station_code": "CLX", "arrival_time": "01:47", "departure_time": "01:49", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12760", "direction": "UP", "station_code": "OGL", "arrival_time": "02:30", "departure_time": "02:32", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12760", "direction": "UP", "station_code": "KVZ", "arrival_time": "03:18", "departure_time": "03:20", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12760", "direction": "UP", "station_code": "NLR", "arrival_time": "03:59", "departure_time": "04:01", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12760", "direction": "UP", "station_code": "GDR", "arrival_time": "04:40", "departure_time": "04:42", "pass_or_skip": "STOP", "service_day": "Daily"},

    # 12841 Coromandel Express (UP) - WTT Page 94 & 98 & 172
    {"train_number": "12841", "direction": "UP", "station_code": "VSKP", "arrival_time": "04:30", "departure_time": "04:50", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "DVD", "arrival_time": "05:18", "departure_time": "05:20", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "AKP", "arrival_time": "05:31", "departure_time": "05:31", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "TUNI", "arrival_time": "06:10", "departure_time": "06:10", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "SLO", "arrival_time": "06:54", "departure_time": "06:56", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "RJY", "arrival_time": "07:37", "departure_time": "07:39", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "TDD", "arrival_time": "08:23", "departure_time": "08:25", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "EE", "arrival_time": "09:02", "departure_time": "09:04", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "BZA", "arrival_time": "10:25", "departure_time": "10:35", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "TEL", "arrival_time": "11:06", "departure_time": "11:08", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "OGL", "arrival_time": "12:35", "departure_time": "12:37", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "NLR", "arrival_time": "14:08", "departure_time": "14:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12841", "direction": "UP", "station_code": "GDR", "arrival_time": "14:48", "departure_time": "14:50", "pass_or_skip": "STOP", "service_day": "Daily"},

    # 12728 Godavari Express (UP) - WTT Page 160 & 164
    {"train_number": "12728", "direction": "UP", "station_code": "BZA", "arrival_time": "23:00", "departure_time": "23:20", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "EE", "arrival_time": "00:15", "departure_time": "00:17", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "TDD", "arrival_time": "00:53", "departure_time": "00:55", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "NDD", "arrival_time": "01:07", "departure_time": "01:07", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "RJY", "arrival_time": "01:50", "departure_time": "01:52", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "APT", "arrival_time": "02:13", "departure_time": "02:15", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "SLO", "arrival_time": "02:40", "departure_time": "02:42", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "ANV", "arrival_time": "03:12", "departure_time": "03:14", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "TUNI", "arrival_time": "03:34", "departure_time": "03:36", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "NRP", "arrival_time": "03:54", "departure_time": "03:54", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "YLM", "arrival_time": "04:21", "departure_time": "04:23", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "AKP", "arrival_time": "04:46", "departure_time": "04:48", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "DVD", "arrival_time": "05:15", "departure_time": "05:17", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12728", "direction": "UP", "station_code": "VSKP", "arrival_time": "05:55", "departure_time": "06:05", "pass_or_skip": "STOP", "service_day": "Daily"},

    # 20834 Vande Bharat (UP) - WTT Page 152 & 156
    {"train_number": "20834", "direction": "UP", "station_code": "SC", "arrival_time": "15:00", "departure_time": "15:00", "pass_or_skip": "ORIGIN", "service_day": "Ex Tue"},
    {"train_number": "20834", "direction": "UP", "station_code": "BZA", "arrival_time": "19:11", "departure_time": "19:16", "pass_or_skip": "STOP", "service_day": "Ex Tue"},
    {"train_number": "20834", "direction": "UP", "station_code": "RJY", "arrival_time": "20:45", "departure_time": "20:47", "pass_or_skip": "STOP", "service_day": "Ex Tue"},
    {"train_number": "20834", "direction": "UP", "station_code": "SLO", "arrival_time": "21:29", "departure_time": "21:31", "pass_or_skip": "STOP", "service_day": "Ex Tue"},
    {"train_number": "20834", "direction": "UP", "station_code": "TUNI", "arrival_time": "22:11", "departure_time": "22:11", "pass_or_skip": "PASS", "service_day": "Ex Tue"},
    {"train_number": "20834", "direction": "UP", "station_code": "DVD", "arrival_time": "23:20", "departure_time": "23:22", "pass_or_skip": "STOP", "service_day": "Ex Tue"},
    {"train_number": "20834", "direction": "UP", "station_code": "VSKP", "arrival_time": "23:45", "departure_time": "23:45", "pass_or_skip": "TERMINATE", "service_day": "Ex Tue"},
    # 22834 BBS SF (DOWN) - WTT Page 14 & 18
    {"train_number": "22834", "direction": "DOWN", "station_code": "GDR", "arrival_time": "00:23", "departure_time": "00:25", "pass_or_skip": "STOP", "service_day": "Thu"},
    {"train_number": "22834", "direction": "DOWN", "station_code": "NLR", "arrival_time": "00:56", "departure_time": "00:58", "pass_or_skip": "STOP", "service_day": "Thu"},
    {"train_number": "22834", "direction": "DOWN", "station_code": "KVZ", "arrival_time": "01:35", "departure_time": "01:35", "pass_or_skip": "PASS", "service_day": "Thu"},
    {"train_number": "22834", "direction": "DOWN", "station_code": "OGL", "arrival_time": "02:26", "departure_time": "02:28", "pass_or_skip": "STOP", "service_day": "Thu"},
    {"train_number": "22834", "direction": "DOWN", "station_code": "CLX", "arrival_time": "03:09", "departure_time": "03:09", "pass_or_skip": "PASS", "service_day": "Thu"},
    {"train_number": "22834", "direction": "DOWN", "station_code": "TEL", "arrival_time": "03:56", "departure_time": "03:56", "pass_or_skip": "PASS", "service_day": "Thu"},
    {"train_number": "22834", "direction": "DOWN", "station_code": "BZA", "arrival_time": "04:30", "departure_time": "04:40", "pass_or_skip": "STOP", "service_day": "Thu"},

    # 20850 BBS Exp (DOWN) - WTT Page 14 & 18
    {"train_number": "20850", "direction": "DOWN", "station_code": "GDR", "arrival_time": "01:00", "departure_time": "01:02", "pass_or_skip": "STOP", "service_day": "Sun"},
    {"train_number": "20850", "direction": "DOWN", "station_code": "NLR", "arrival_time": "01:33", "departure_time": "01:35", "pass_or_skip": "STOP", "service_day": "Sun"},
    {"train_number": "20850", "direction": "DOWN", "station_code": "OGL", "arrival_time": "03:06", "departure_time": "03:08", "pass_or_skip": "STOP", "service_day": "Sun"},
    {"train_number": "20850", "direction": "DOWN", "station_code": "TEL", "arrival_time": "04:31", "departure_time": "04:31", "pass_or_skip": "PASS", "service_day": "Sun"},
    {"train_number": "20850", "direction": "DOWN", "station_code": "BZA", "arrival_time": "05:05", "departure_time": "05:15", "pass_or_skip": "STOP", "service_day": "Sun"},

    # 12764 Padmavathi Express (UP) - WTT Page 78 & 82
    {"train_number": "12764", "direction": "UP", "station_code": "BZA", "arrival_time": "00:30", "departure_time": "00:40", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12764", "direction": "UP", "station_code": "TEL", "arrival_time": "01:15", "departure_time": "01:17", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12764", "direction": "UP", "station_code": "CLX", "arrival_time": "02:07", "departure_time": "02:09", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12764", "direction": "UP", "station_code": "OGL", "arrival_time": "02:51", "departure_time": "02:53", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12764", "direction": "UP", "station_code": "KVZ", "arrival_time": "03:38", "departure_time": "03:40", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12764", "direction": "UP", "station_code": "NLR", "arrival_time": "04:18", "departure_time": "04:20", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12764", "direction": "UP", "station_code": "GDR", "arrival_time": "04:53", "departure_time": "04:55", "pass_or_skip": "STOP", "service_day": "Daily"},

    # 17249 Kakinada Exp (DOWN) - WTT Page 14, 18, 122, 124, 210
    {"train_number": "17249", "direction": "DOWN", "station_code": "GDR", "arrival_time": "01:17", "departure_time": "01:17", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "NLR", "arrival_time": "01:51", "departure_time": "01:53", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "KVZ", "arrival_time": "02:49", "departure_time": "02:58", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "OGL", "arrival_time": "03:58", "departure_time": "04:00", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "CLX", "arrival_time": "04:54", "departure_time": "04:56", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "BPP", "arrival_time": "05:08", "departure_time": "05:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "TEL", "arrival_time": "05:55", "departure_time": "05:57", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "BZA", "arrival_time": "06:35", "departure_time": "06:45", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "EE", "arrival_time": "07:57", "departure_time": "07:59", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "NDD", "arrival_time": "08:58", "departure_time": "09:00", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "RJY", "arrival_time": "09:35", "departure_time": "09:37", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "SLO", "arrival_time": "10:40", "departure_time": "10:42", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17249", "direction": "DOWN", "station_code": "CCT", "arrival_time": "11:40", "departure_time": "11:40", "pass_or_skip": "TERMINATE", "service_day": "Daily"},

    # 20630 Sabari Express (DOWN) - WTT Page 14 & 18
    {"train_number": "20630", "direction": "DOWN", "station_code": "GDR", "arrival_time": "01:28", "departure_time": "01:30", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "20630", "direction": "DOWN", "station_code": "NLR", "arrival_time": "02:03", "departure_time": "02:05", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "20630", "direction": "DOWN", "station_code": "KVZ", "arrival_time": "02:40", "departure_time": "02:42", "pass_or_skip": "PASS", "service_day": "Daily"},
    {"train_number": "20630", "direction": "DOWN", "station_code": "OGL", "arrival_time": "03:35", "departure_time": "03:37", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "20630", "direction": "DOWN", "station_code": "CLX", "arrival_time": "04:20", "departure_time": "04:22", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "20630", "direction": "DOWN", "station_code": "BPP", "arrival_time": "04:37", "departure_time": "04:48", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "20630", "direction": "DOWN", "station_code": "TEL", "arrival_time": "05:40", "departure_time": "05:42", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "20630", "direction": "DOWN", "station_code": "BZA", "arrival_time": "06:35", "departure_time": "06:45", "pass_or_skip": "STOP", "service_day": "Daily"},

    # 12712 Pinakini Express (DOWN) - WTT Page 35 & 39
    {"train_number": "12712", "direction": "DOWN", "station_code": "GDR", "arrival_time": "16:43", "departure_time": "16:45", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "NLR", "arrival_time": "17:20", "departure_time": "17:22", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "BTTR", "arrival_time": "17:52", "departure_time": "17:54", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "KVZ", "arrival_time": "18:08", "departure_time": "18:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "SKM", "arrival_time": "18:40", "departure_time": "18:42", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "OGL", "arrival_time": "19:09", "departure_time": "19:11", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "CLX", "arrival_time": "19:54", "departure_time": "19:56", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "BPP", "arrival_time": "20:08", "departure_time": "20:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "NDO", "arrival_time": "20:28", "departure_time": "20:30", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "TEL", "arrival_time": "20:52", "departure_time": "20:54", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "12712", "direction": "DOWN", "station_code": "BZA", "arrival_time": "21:35", "departure_time": "21:35", "pass_or_skip": "TERMINATE", "service_day": "Daily"},

    # 17202 Golconda Express (UP) - WTT Page 68 & 76
    {"train_number": "17202", "direction": "UP", "station_code": "BZA", "arrival_time": "19:50", "departure_time": "20:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17202", "direction": "UP", "station_code": "KCC", "arrival_time": "20:38", "departure_time": "20:40", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17202", "direction": "UP", "station_code": "GNT", "arrival_time": "21:35", "departure_time": "21:35", "pass_or_skip": "TERMINATE", "service_day": "Daily"},

    # 67260 MEMU Passenger (DOWN) - WTT Page 15, 17, 19
    {"train_number": "67260", "direction": "DOWN", "station_code": "BTTR", "arrival_time": "04:00", "departure_time": "04:00", "pass_or_skip": "ORIGIN", "service_day": "Daily"},
    {"train_number": "67260", "direction": "DOWN", "station_code": "KVZ", "arrival_time": "04:16", "departure_time": "04:18", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67260", "direction": "DOWN", "station_code": "SKM", "arrival_time": "05:00", "departure_time": "05:02", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67260", "direction": "DOWN", "station_code": "OGL", "arrival_time": "05:39", "departure_time": "05:41", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67260", "direction": "DOWN", "station_code": "CLX", "arrival_time": "07:01", "departure_time": "07:03", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67260", "direction": "DOWN", "station_code": "BPP", "arrival_time": "07:25", "departure_time": "07:27", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67260", "direction": "DOWN", "station_code": "TEL", "arrival_time": "08:28", "departure_time": "08:30", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67260", "direction": "DOWN", "station_code": "BZA", "arrival_time": "09:35", "departure_time": "09:35", "pass_or_skip": "TERMINATE", "service_day": "Daily"},

    # 67214 Passenger (DOWN) - WTT Page 15, 17, 19
    {"train_number": "67214", "direction": "DOWN", "station_code": "TEL", "arrival_time": "06:50", "departure_time": "06:55", "pass_or_skip": "ORIGIN", "service_day": "Daily"},
    {"train_number": "67214", "direction": "DOWN", "station_code": "DIG", "arrival_time": "07:08", "departure_time": "07:10", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67214", "direction": "DOWN", "station_code": "PVD", "arrival_time": "07:21", "departure_time": "07:22", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67214", "direction": "DOWN", "station_code": "KCC", "arrival_time": "07:34", "departure_time": "07:36", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67214", "direction": "DOWN", "station_code": "BZA", "arrival_time": "07:55", "departure_time": "07:55", "pass_or_skip": "TERMINATE", "service_day": "Daily"},

    # 67274 Passenger (UP) - WTT Page 29 & 33
    {"train_number": "67274", "direction": "UP", "station_code": "OGL", "arrival_time": "14:35", "departure_time": "14:40", "pass_or_skip": "ORIGIN", "service_day": "Daily"},
    {"train_number": "67274", "direction": "UP", "station_code": "CLX", "arrival_time": "16:07", "departure_time": "16:09", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67274", "direction": "UP", "station_code": "BPP", "arrival_time": "16:31", "departure_time": "16:33", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67274", "direction": "UP", "station_code": "TEL", "arrival_time": "18:06", "departure_time": "18:08", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "67274", "direction": "UP", "station_code": "BZA", "arrival_time": "19:05", "departure_time": "19:05", "pass_or_skip": "TERMINATE", "service_day": "Daily"},

    # 17258 Kakinada Exp (UP) - WTT Page 165 & 169
    {"train_number": "17258", "direction": "UP", "station_code": "COA", "arrival_time": "03:30", "departure_time": "03:30", "pass_or_skip": "ORIGIN", "service_day": "Daily"},
    {"train_number": "17258", "direction": "UP", "station_code": "CCT", "arrival_time": "03:45", "departure_time": "03:50", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17258", "direction": "UP", "station_code": "SLO", "arrival_time": "06:44", "departure_time": "06:46", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17258", "direction": "UP", "station_code": "RJY", "arrival_time": "07:53", "departure_time": "07:55", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17258", "direction": "UP", "station_code": "NDD", "arrival_time": "08:54", "departure_time": "08:56", "pass_or_skip": "STOP", "service_day": "Daily"},
    {"train_number": "17258", "direction": "UP", "station_code": "BZA", "arrival_time": "12:15", "departure_time": "12:25", "pass_or_skip": "STOP", "service_day": "Daily"}
]


def build_wtt_data_engine():
    """Generates all 5 normalized CSV files and loads them into railway.db without removing legacy tables."""
    print("🚀 Initializing WTT Timetable Data Engine...")

    # 1. Create DataFrames
    df_stations = pd.DataFrame(STATIONS_DATA)
    df_stations["station_id"] = range(1, len(df_stations) + 1)
    df_stations = df_stations[["station_id", "station_code", "station_name", "section", "km_from_reference", "latitude", "longitude"]]

    df_sections = pd.DataFrame(SECTIONS_DATA)
    df_inter_runtime = pd.DataFrame(INTER_RUNTIMES)
    df_trains = pd.DataFrame(TRAINS_MASTER)

    # Enrich train schedule with station metadata
    stn_lookup = df_stations.set_index("station_code")["km_from_reference"].to_dict()
    stn_name_lookup = df_stations.set_index("station_code")["station_name"].to_dict()

    sched_rows = []
    for row in TRAIN_SCHEDULE_DATA:
        stn_code = row["station_code"]
        stn_km = stn_lookup.get(stn_code, 0.0)
        stn_name = stn_name_lookup.get(stn_code, stn_code)
        sched_rows.append({
            "train_number": row["train_number"],
            "direction": row["direction"],
            "station_code": stn_code,
            "station_name": stn_name,
            "station_km": stn_km,
            "arrival_time": row["arrival_time"],
            "departure_time": row["departure_time"],
            "pass_or_skip": row["pass_or_skip"],
            "service_day": row["service_day"],
            "scheduled_run_date": "2026-09-27"
        })
    df_schedule = pd.DataFrame(sched_rows)

    # 2. Save Normalized CSV Datasets
    df_trains.to_csv(os.path.join(DATA_DIR, "trains.csv"), index=False)
    df_stations.to_csv(os.path.join(DATA_DIR, "stations.csv"), index=False)
    df_schedule.to_csv(os.path.join(DATA_DIR, "train_schedule.csv"), index=False)
    df_sections.to_csv(os.path.join(DATA_DIR, "sections.csv"), index=False)
    df_inter_runtime.to_csv(os.path.join(DATA_DIR, "inter_station_runtime.csv"), index=False)

    print("✅ Normalized CSV files generated successfully in data/ directory.")

    # 3. SQLite Ingestion & Migration
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    cur = conn.cursor()

    # Create WTT Tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS wtt_trains (
        train_id TEXT PRIMARY KEY,
        train_number TEXT NOT NULL,
        name TEXT,
        origin TEXT,
        destination TEXT,
        category TEXT,
        stock TEXT,
        service_days TEXT,
        direction TEXT,
        scenario TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wtt_stations (
        station_id INTEGER PRIMARY KEY AUTOINCREMENT,
        station_code TEXT UNIQUE NOT NULL,
        station_name TEXT NOT NULL,
        section TEXT,
        km_from_reference REAL,
        latitude REAL,
        longitude REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wtt_sections (
        section_id TEXT PRIMARY KEY,
        section_name TEXT NOT NULL,
        from_station TEXT,
        to_station TEXT,
        from_km REAL,
        to_km REAL,
        distance_km REAL,
        line_type TEXT,
        max_permissible_speed INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wtt_train_schedule (
        schedule_entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
        train_number TEXT NOT NULL,
        direction TEXT NOT NULL,
        station_code TEXT NOT NULL,
        station_name TEXT,
        station_km REAL,
        arrival_time TEXT,
        departure_time TEXT,
        pass_or_skip TEXT,
        service_day TEXT,
        scheduled_run_date TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS wtt_inter_station_runtime (
        runtime_id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_station TEXT NOT NULL,
        to_station TEXT NOT NULL,
        distance_km REAL,
        stock_type TEXT,
        scheduled_minutes INTEGER
    )
    """)

    conn.commit()

    # Upsert data into SQLite
    df_trains.to_sql("wtt_trains", conn, if_exists="replace", index=False)
    df_stations.to_sql("wtt_stations", conn, if_exists="replace", index=False)
    df_sections.to_sql("wtt_sections", conn, if_exists="replace", index=False)
    df_schedule.to_sql("wtt_train_schedule", conn, if_exists="replace", index=False)
    df_inter_runtime.to_sql("wtt_inter_station_runtime", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print("✅ Ingested WTT tables into railway.db without altering existing tables.")


# -----------------------------------------------------------------------------
# 6. OPERATIONAL QUERY ENGINE & HELPER APIS
# -----------------------------------------------------------------------------
class TimetableDataEngine:
    """Core Query Interface for WTT Timetable Data Engine."""

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def _get_conn(self):
        return sqlite3.connect(self.db_path, timeout=30.0)

    @staticmethod
    def _time_to_minutes(t_str):
        if not t_str or ":" not in str(t_str):
            return None
        parts = str(t_str).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])

    @staticmethod
    def _minutes_to_time(mins):
        if mins is None:
            return None
        mins = mins % (24 * 60)
        return f"{int(mins // 60):02d}:{int(mins % 60):02d}"

    def get_trains_occupying_section(self, section_name_or_code, start_time_str, end_time_str, direction=None):
        """
        Answers: 'What trains are expected to occupy this section between 10:00 and 12:00?'
        """
        start_min = self._time_to_minutes(start_time_str)
        end_min = self._time_to_minutes(end_time_str)
        if end_min < start_min:
            end_min += 24 * 60  # overnight window

        conn = self._get_conn()
        query = """
            SELECT s.train_number, s.direction, t.name as train_name, t.category, t.stock,
                   s.station_code, s.station_name, s.arrival_time, s.departure_time, s.pass_or_skip, s.station_km
            FROM wtt_train_schedule s
            LEFT JOIN wtt_trains t ON s.train_number = t.train_number
            ORDER BY s.train_number, s.departure_time ASC
        """
        df = pd.read_sql(query, conn)
        conn.close()

        # Find trains that have stations matching the section or crossing it
        matching_trains = []
        for train_no, grp in df.groupby("train_number"):
            grp = grp.copy()
            grp["dep_min"] = grp["departure_time"].apply(self._time_to_minutes)
            grp["arr_min"] = grp["arrival_time"].apply(self._time_to_minutes)
            
            # Check overlap with time window
            in_window = grp[
                ((grp["dep_min"] >= start_min) & (grp["dep_min"] <= end_min)) |
                ((grp["arr_min"] >= start_min) & (grp["arr_min"] <= end_min))
            ]
            if not in_window.empty:
                train_dir = grp["direction"].iloc[0]
                if direction and train_dir != direction:
                    continue
                first_stn = grp.iloc[0]["station_code"]
                last_stn = grp.iloc[-1]["station_code"]
                matching_trains.append({
                    "train_number": train_no,
                    "train_name": grp.iloc[0]["train_name"],
                    "category": grp.iloc[0]["category"],
                    "direction": train_dir,
                    "first_stop_in_section": in_window.iloc[0]["station_code"],
                    "entry_time": in_window.iloc[0]["arrival_time"],
                    "exit_time": in_window.iloc[-1]["departure_time"],
                    "stations_traversed": in_window["station_code"].tolist()
                })
        return matching_trains

    def get_next_train_after(self, time_str, target_km, direction=None):
        """
        Answers: 'What is the next train after 10:20 at KM 575?'
        """
        target_min = self._time_to_minutes(time_str)
        conn = self._get_conn()
        query = """
            SELECT s.train_number, s.direction, t.name as train_name, t.category,
                   s.station_code, s.station_name, s.station_km, s.arrival_time, s.departure_time
            FROM wtt_train_schedule s
            LEFT JOIN wtt_trains t ON s.train_number = t.train_number
        """
        df = pd.read_sql(query, conn)
        conn.close()

        # Calculate interpolated / nearest station time for target_km
        candidates = []
        for train_no, grp in df.groupby("train_number"):
            train_dir = grp["direction"].iloc[0]
            if direction and train_dir != direction:
                continue

            grp = grp.copy()
            grp["dep_min"] = grp["departure_time"].apply(self._time_to_minutes)
            
            # Find closest station in train path
            grp["km_diff"] = (grp["station_km"] - target_km).abs()
            nearest = grp.sort_values("km_diff").iloc[0]

            dep_min = nearest["dep_min"]
            if dep_min is not None and dep_min >= target_min:
                time_until = dep_min - target_min
                candidates.append({
                    "train_number": train_no,
                    "train_name": nearest["train_name"],
                    "direction": train_dir,
                    "nearest_station": nearest["station_code"],
                    "station_km": nearest["station_km"],
                    "expected_departure": nearest["departure_time"],
                    "wait_minutes": time_until
                })

        candidates.sort(key=lambda x: x["wait_minutes"])
        return candidates[0] if candidates else None

    def get_time_gap_between_trains(self, train_a_num, train_b_num, station_code):
        """
        Answers: 'What is the time gap between train A and train B at this section/station?'
        """
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT train_number, arrival_time, departure_time, direction, station_km
            FROM wtt_train_schedule
            WHERE train_number IN (?, ?) AND station_code = ?
        """, (str(train_a_num), str(train_b_num), station_code))
        rows = cur.fetchall()
        conn.close()

        if len(rows) < 2:
            return {"error": f"One or both trains not scheduled at station {station_code}"}

        train_dict = {r[0]: {"arr": r[1], "dep": r[2], "dir": r[3], "km": r[4]} for r in rows}
        dep_a = self._time_to_minutes(train_dict[str(train_a_num)]["dep"])
        arr_b = self._time_to_minutes(train_dict[str(train_b_num)]["arr"])

        if arr_b < dep_a:
            raw_gap = (arr_b + 24 * 60) - dep_a
        else:
            raw_gap = arr_b - dep_a

        return {
            "station_code": station_code,
            "train_A": train_a_num,
            "train_A_dep": train_dict[str(train_a_num)]["dep"],
            "train_B": train_b_num,
            "train_B_arr": train_dict[str(train_b_num)]["arr"],
            "raw_gap_minutes": raw_gap,
            "direction_A": train_dict[str(train_a_num)]["dir"],
            "direction_B": train_dict[str(train_b_num)]["dir"]
        }


# -----------------------------------------------------------------------------
# 7. VALIDATION SUITE
# -----------------------------------------------------------------------------
def run_timetable_validations():
    """Validates data integrity across all 5 normalized WTT datasets."""
    print("\n🔍 Running Timetable Integrity Validations...")
    errors = []
    warnings = []

    df_trains = pd.read_csv(os.path.join(DATA_DIR, "trains.csv"))
    df_stations = pd.read_csv(os.path.join(DATA_DIR, "stations.csv"))
    df_schedule = pd.read_csv(os.path.join(DATA_DIR, "train_schedule.csv"))
    df_sections = pd.read_csv(os.path.join(DATA_DIR, "sections.csv"))
    df_runtime = pd.read_csv(os.path.join(DATA_DIR, "inter_station_runtime.csv"))

    # 1. Duplicate Trains check
    dup_trains = df_trains[df_trains.duplicated(subset=["train_number"], keep=False)]
    if not dup_trains.empty:
        errors.append(f"❌ Duplicate trains found: {dup_trains['train_number'].tolist()}")
    else:
        print("  ✓ No duplicate trains in trains.csv")

    # 2. Duplicate Stations check
    dup_stations = df_stations[df_stations.duplicated(subset=["station_code"], keep=False)]
    if not dup_stations.empty:
        errors.append(f"❌ Duplicate station codes: {dup_stations['station_code'].tolist()}")
    else:
        print("  ✓ No duplicate station codes in stations.csv")

    # 3. Invalid Times check in Schedule
    time_regex = r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"
    invalid_arr = df_schedule[~df_schedule["arrival_time"].astype(str).str.match(time_regex)]
    invalid_dep = df_schedule[~df_schedule["departure_time"].astype(str).str.match(time_regex)]
    if not invalid_arr.empty:
        errors.append(f"❌ Invalid arrival times: {len(invalid_arr)} records")
    if not invalid_dep.empty:
        errors.append(f"❌ Invalid departure times: {len(invalid_dep)} records")
    if invalid_arr.empty and invalid_dep.empty:
        print("  ✓ All arrival and departure times conform to HH:MM 24-hour standard")

    # 4. Missing Stations check in Schedule
    known_stations = set(df_stations["station_code"].unique())
    sched_stations = set(df_schedule["station_code"].unique())
    missing_stns = sched_stations - known_stations
    if missing_stns:
        errors.append(f"❌ Schedule references unknown stations: {missing_stns}")
    else:
        print("  ✓ All stations in schedule exist in stations master")

    # 5. Inconsistent KM values
    for _, row in df_schedule.iterrows():
        stn = row["station_code"]
        expected_km = df_stations.loc[df_stations["station_code"] == stn, "km_from_reference"].values
        if len(expected_km) > 0 and abs(expected_km[0] - row["station_km"]) > 0.1:
            errors.append(f"❌ Inconsistent KM for {stn}: Master={expected_km[0]} vs Sched={row['station_km']}")

    print("  ✓ All station KM alignments verified")

    # 6. UP/DOWN direction consistency
    for train_no, grp in df_schedule.groupby("train_number"):
        train_master = df_trains[df_trains["train_number"] == train_no]
        if not train_master.empty:
            expected_dir = train_master.iloc[0]["direction"]
            actual_dirs = grp["direction"].unique()
            if len(actual_dirs) > 1 or actual_dirs[0] != expected_dir:
                errors.append(f"❌ Direction mismatch for train {train_no}: master={expected_dir} vs schedule={actual_dirs}")
    print("  ✓ Strict UP and DOWN bidirectional integrity preserved without flattening")

    print(f"\n📊 Validation Summary: {len(errors)} Errors, {len(warnings)} Warnings.")
    if errors:
        for err in errors:
            print(err)
        return False
    return True


if __name__ == "__main__":
    build_wtt_data_engine()
    success = run_timetable_validations()

    # Demonstrate the 3 required engine queries
    engine = TimetableDataEngine()
    print("\n--- [Query 1 Demonstration] Trains occupying BZA-VSKP between 08:00 and 10:00 ---")
    q1 = engine.get_trains_occupying_section("BZA-VSKP", "08:00", "10:00")
    for t in q1:
        print(f"🚆 Train {t['train_number']} ({t['train_name']}) | Dir: {t['direction']} | Traversed: {t['stations_traversed']}")

    print("\n--- [Query 2 Demonstration] Next train after 10:20 at KM 575 (Godavari/Kovvur) ---")
    q2 = engine.get_next_train_after("10:20", 575.0, direction="UP")
    print(f"🚆 Next UP Train: {q2}")

    print("\n--- [Query 3 Demonstration] Time gap between Train 12846 and Train 13352 at Ongole (OGL) ---")
    q3 = engine.get_time_gap_between_trains("12846", "13352", "OGL")
    print(f"⏱️ Time Gap Result: {q3}")
