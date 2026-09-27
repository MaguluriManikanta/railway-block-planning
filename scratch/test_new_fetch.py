import sqlite3
import json
import re
import os
import sys
from datetime import datetime

# UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("."))

from app.controller_map import get_division_network_data, get_section_geometry, STATION_COORDINATES, DB_PATH

def test_new_fetch_live_trains(division_name="Vijayawada Division (BZA)", train_filter="ALL", search_query=""):
    trains = {}
    now = datetime.now()
    net_data = get_division_network_data(division_name)

    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # 1. Check live_train_positions table
            has_pos = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='live_train_positions'").fetchone()
            if has_pos:
                rows = cur.execute("SELECT * FROM live_train_positions").fetchall()
                for r in rows:
                    rd = dict(r)
                    t_num = str(rd.get("train_number") or "12000")
                    t_lat = rd.get("latitude")
                    t_lon = rd.get("longitude")
                    cur_km = float(rd.get("current_km") or 100.0)
                    sec_ref = f"{rd.get('current_station', 'BZA')}-{rd.get('next_station', 'KI')}"
                    
                    if t_lat is None or t_lon is None or not (8.0 <= float(t_lat) <= 36.0 and 68.0 <= float(t_lon) <= 98.0):
                        geo = get_section_geometry(sec_ref, cur_km, cur_km + 1.0, division_name=division_name)
                        t_lat = geo[0][0]
                        t_lon = geo[0][1]
                    else:
                        t_lat = float(t_lat)
                        t_lon = float(t_lon)
                    
                    trains[t_num] = {
                        "train_number": t_num,
                        "train_name": f"Express {t_num}",
                        "latitude": t_lat,
                        "longitude": t_lon,
                        "current_km": cur_km,
                        "current_station": str(rd.get("current_station") or "En Route"),
                        "next_station": str(rd.get("next_station") or "Next Hub"),
                        "direction": str(rd.get("direction") or "UP"),
                        "speed": float(rd.get("speed") or 80.0),
                        "delay": float(rd.get("delay") or 0.0),
                        "mps": 110.0,
                        "status": str(rd.get("status") or "RUNNING").upper(),
                        "timestamp": str(rd.get("last_updated") or now.strftime("%Y-%m-%d %H:%M:%S")),
                        "data_source": str(rd.get("data_source") or "LIVE").upper(),
                        "is_stale": False,
                        "age_seconds": 15,
                        "source": "DATABASE_POS"
                    }

            # 2. Check live_train_status table
            has_stat = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='live_train_status'").fetchone()
            if has_stat:
                rows = cur.execute("SELECT * FROM live_train_status").fetchall()
                for r in rows:
                    rd = dict(r)
                    t_num = str(rd.get("train_id") or rd.get("train_number") or "12000")
                    t_name = str(rd.get("train_name") or f"Express {t_num}")
                    t_div = str(rd.get("division_id") or rd.get("division") or "Vijayawada Division (BZA)")
                    
                    sec_id = str(rd.get("section_id") or "Main Corridor")
                    cur_km = float(rd.get("current_km") or 100.0)
                    delay = float(rd.get("delay_minutes") or rd.get("delay") or 0.0)
                    speed = float(rd.get("current_speed_kmh") or rd.get("speed") or 80.0)
                    mps = float(rd.get("recommended_speed_kmh") or rd.get("max_permissible_speed") or 110.0)
                    status = str(rd.get("status") or "RUNNING").upper()
                    last_upd = str(rd.get("last_updated") or rd.get("last_update") or now.strftime("%Y-%m-%d %H:%M:%S"))
                    
                    if t_num in trains:
                        trains[t_num]["train_name"] = t_name
                        trains[t_num]["mps"] = mps
                        if "DATABASE" in trains[t_num]["source"]:
                            trains[t_num]["status"] = status
                    else:
                        geo = get_section_geometry(sec_id, cur_km, cur_km + 1.0, division_name=division_name)
                        t_lat = geo[0][0]
                        t_lon = geo[0][1]
                        trains[t_num] = {
                            "train_number": t_num,
                            "train_name": t_name,
                            "latitude": t_lat,
                            "longitude": t_lon,
                            "current_km": cur_km,
                            "current_station": sec_id.split("-")[0] if "-" in sec_id else "En Route",
                            "next_station": sec_id.split("-")[-1] if "-" in sec_id else "Next Hub",
                            "direction": "UP" if "UP" in sec_id or "NB" in sec_id else "DOWN",
                            "speed": speed,
                            "delay": delay,
                            "mps": mps,
                            "status": status,
                            "timestamp": last_upd,
                            "data_source": "LIVE",
                            "is_stale": False,
                            "age_seconds": 15,
                            "source": "DATABASE_STAT"
                        }
            conn.close()
    except Exception as e:
        print("DB Error:", e)

    # 3. Merge divisional defaults
    defaults = net_data.get("default_trains", [])
    for d_tr in defaults:
        num = d_tr.get("train_number")
        if num not in trains:
            tr_copy = dict(d_tr)
            tr_copy["age_seconds"] = 10
            tr_copy["is_stale"] = False
            tr_copy["source"] = "DIVISION_FEED"
            trains[num] = tr_copy
        else:
            if trains[num]["train_name"].startswith("Express "):
                trains[num]["train_name"] = d_tr.get("train_name", trains[num]["train_name"])

    res = list(trains.values())
    print(f"Fetched {len(res)} trains for {division_name}")
    for t in res[:8]:
        print(f"  Train {t['train_number']}: {t['train_name']} @ ({t['latitude']:.4f}, {t['longitude']:.4f}) | spd: {t['speed']} | status: {t['status']} | src: {t['source']}")
    return res

test_new_fetch_live_trains("Vijayawada Division (BZA)")
