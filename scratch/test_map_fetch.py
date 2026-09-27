import sqlite3
import os
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.abspath("."))

from app.controller_map import fetch_allocated_blocks, fetch_live_trains, ControllerMap, get_section_geometry, DIVISION_GEOGRAPHIC_NETWORKS

print("=== DB Tables ===")
conn = sqlite3.connect("railway.db")
cur = conn.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

for t in ["live_train_status", "live_train_positions", "final_block_allocations", "slot_requests", "defects", "schedule"]:
    if t in tables:
        count = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        col_names = [d[0] for d in cur.execute(f"SELECT * FROM {t} LIMIT 1").description] if count > 0 else []
        print(f"Table {t}: {count} rows | cols: {col_names}")
conn.close()

print("\n=== Test all divisions in fetch_allocated_blocks & fetch_live_trains ===")
for div in DIVISION_GEOGRAPHIC_NETWORKS.keys():
    blocks = fetch_allocated_blocks(div, "ALL", "ALL")
    trains = fetch_live_trains(div, "ALL", "")
    print(f"\nDivision: {div}")
    print(f"  Allocated/Candidate Blocks: {len(blocks)}")
    for b in blocks:
        coords = b.get("line_coords")
        print(f"    Block: {b.get('block_id')} ({b.get('section')}) | status: {b.get('status')} | coords count: {len(coords) if coords else 0} | coords: {coords}")
    print(f"  Live Trains: {len(trains)}")
    for tr in trains:
        print(f"    Train: {tr.get('train_number')} {tr.get('train_name')} | pos: ({tr.get('latitude')}, {tr.get('longitude')}) | spd: {tr.get('speed')} | km: {tr.get('current_km')} | status: {tr.get('status')} | src: {tr.get('source')}")
