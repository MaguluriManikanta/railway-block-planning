import sys, os
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from app.controller_map import get_section_geometry, fetch_allocated_blocks, fetch_live_trains, DIVISION_GEOGRAPHIC_NETWORKS

print("=== Testing get_section_geometry ===")
sections_to_test = [
    ("Vijayawada–Kondapalli", 114.0, 118.0),
    ("BZA-GDR-UP", 224.0, 208.0),
    ("GDR-BZA-DN", 397.0, 407.0),
    ("BZA-VSKP-DN", 488.0, 490.5),
    ("Vijayawada-SEC-01", 100.0, 110.0),
    ("BZA-KI-01", 110.0, 120.0),
    ("TEL-BZA-UP", 10.0, 25.0),
    ("KDM-MDR", 125.0, 135.0),
    ("BZA-RAY", 100.0, 108.0),
]

for sec, f_km, t_km in sections_to_test:
    coords = get_section_geometry(sec, f_km, t_km, division_name="Vijayawada Division (BZA)")
    print(f"Section '{sec}' (KM {f_km}->{t_km}): coords = {coords}")

print("\n=== Testing fetch_allocated_blocks ===")
blocks = fetch_allocated_blocks(division_name="Vijayawada Division (BZA)", status_filter="ALL", dept_filter="ALL")
print(f"Total blocks returned: {len(blocks)}")
for b in blocks[:5]:
    print(f"Block: {b.get('block_id')} | Status: {b.get('status')} | Source: {b.get('source')} | Coords: {b.get('line_coords')}")

print("\n=== Testing fetch_live_trains ===")
trains = fetch_live_trains(division_name="Vijayawada Division (BZA)", train_filter="ALL")
print(f"Total trains returned: {len(trains)}")
for tr in trains[:5]:
    print(f"Train: {tr.get('train_number')} | Lat/Lon: ({tr.get('latitude')}, {tr.get('longitude')}) | KM: {tr.get('current_km')} | Status: {tr.get('status')} | Source: {tr.get('source')}")
