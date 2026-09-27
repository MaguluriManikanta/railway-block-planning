import sqlite3
import json
import re
import os
import sys
from datetime import datetime
import folium

# UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("."))

from app.controller_map import get_division_network_data, STATION_COORDINATES, DIVISION_GEOGRAPHIC_NETWORKS, DB_PATH

def get_section_geometry_refined(section_name: str, from_km: float, to_km: float, division_name: str = "Vijayawada Division (BZA)") -> list:
    net_data = get_division_network_data(division_name)
    best_coords = []
    f_km = float(from_km) if from_km is not None else 100.0
    t_km = float(to_km) if to_km is not None else (f_km + 5.0)
    if f_km > t_km:
        f_km, t_km = t_km, f_km

    # Normalize tokens cleanly
    sec_clean = re.sub(r"[^a-zA-Z0-9\s]+", " ", str(section_name)).upper()
    tokens = [t.strip() for t in sec_clean.split() if t.strip()]

    # 1. Score all lines in this division
    best_line = None
    best_score = -1
    best_matched_stations = []

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
            best_matched_stations = matched_in_line

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

print("Refined get_section_geometry test:")
print("Vijayawada–Kondapalli 100-105:", get_section_geometry_refined("Vijayawada–Kondapalli", 100, 105))
print("BZA-VSKP 570-575:", get_section_geometry_refined("BZA-VSKP", 570, 575))
print("Unknown Section 10-15:", get_section_geometry_refined("Unknown", 10, 15))
