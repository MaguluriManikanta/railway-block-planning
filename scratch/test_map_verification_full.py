import sys, os
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from app.controller_map import (
    get_section_geometry,
    fetch_allocated_blocks,
    fetch_live_trains,
    ControllerMap,
    DIVISION_GEOGRAPHIC_NETWORKS
)

print("=" * 60)
print("1. VERIFYING get_section_geometry FOR ALL SECTION CODES")
print("=" * 60)
test_sections = [
    ("Vijayawada–Kondapalli", 114.0, 118.0, "Vijayawada Division (BZA)"),
    ("BZA-GDR-UP", 224.0, 208.0, "Vijayawada Division (BZA)"),
    ("GDR-BZA-DN", 397.0, 407.0, "Vijayawada Division (BZA)"),
    ("BZA-VSKP-DN", 488.0, 490.5, "Vijayawada Division (BZA)"),
    ("BZA-KI-01", 110.0, 120.0, "Vijayawada Division (BZA)"),
    ("KDM-MDR", 130.0, 134.0, "Vijayawada Division (BZA)"),
    ("CHZ-BG-01", 35.0, 50.0, "Secunderabad Division (SC)"),
    ("CTC-BBS-01", 298.0, 301.0, "Khurda Road Division (KUR)"),
    ("BDC-BWN-01", 40.0, 50.0, "Howrah Division (HWH)"),
    ("MALM-RC-01", 95.0, 105.0, "Guntakal Division (GTL)"),
    ("NRT-VKN-01", 60.0, 75.0, "Guntur Division (GNT)"),
    ("UR-SHNR-01", 35.0, 48.0, "Hyderabad Division (HYB)")
]

all_geo_passed = True
for sec, f_km, t_km, div in test_sections:
    coords = get_section_geometry(sec, f_km, t_km, div)
    assert len(coords) >= 2, f"Failed geometry for {sec}"
    assert len(coords[0]) == 2 and len(coords[1]) == 2, f"Invalid coord format for {sec}"
    for pt in coords:
        assert 10.0 <= pt[0] <= 32.0, f"Lat {pt[0]} out of range for {sec}"
        assert 70.0 <= pt[1] <= 92.0, f"Lon {pt[1]} out of range for {sec}"
    print(f"  [PASS] {sec:25s} [{div[:12]}]: KM {f_km:.0f}->{t_km:.0f} => {coords[0]} to {coords[1]}")

print("\n" + "=" * 60)
print("2. VERIFYING fetch_allocated_blocks (DATABASE + CANDIDATE INGESTION)")
print("=" * 60)
# Test default DB blocks
db_blocks = fetch_allocated_blocks(division_name="Vijayawada Division (BZA)", status_filter="ALL", dept_filter="ALL")
print(f"  [PASS] Default blocks count: {len(db_blocks)}")
for b in db_blocks[:3]:
    print(f"    - {b['block_id']}: status={b['status']}, source={b['source']}, coords={b['line_coords']}")

# Test mock Streamlit session state with classified candidate groups
import streamlit as st
st.session_state["step6_classified_results"] = {
    "all_groups": [
        {
            "group_id": "GRP-TEST-CLS-01",
            "request_ids": ["REQ-TEST-101", "REQ-TEST-102"],
            "departments": ["Engineering", "OHE/Traction"],
            "classification": "PARALLEL",
            "section": "Vijayawada–Kondapalli",
            "from_km": 114.0,
            "to_km": 118.0,
            "date": "2026-09-27",
            "reason": "CSM Tamping & OHE Joint Isolation",
            "execution_order": ["1. Parallel Track & OHE possession"]
        },
        {
            "group_id": "GRP-TEST-CLS-02",
            "request_ids": ["REQ-TEST-201"],
            "departments": ["S&T"],
            "classification": "ISOLATION",
            "section": "BZA-VSKP-DN",
            "from_km": 488.0,
            "to_km": 490.5,
            "date": "2026-09-27",
            "reason": "Axle Counter Calibration",
            "execution_order": ["1. S&T Track Circuit Testing"]
        }
    ]
}

blocks_with_cand = fetch_allocated_blocks(division_name="Vijayawada Division (BZA)", status_filter="ALL", dept_filter="ALL")
cand_blocks = [b for b in blocks_with_cand if b["status"] == "CLASSIFIED"]
print(f"  [PASS] Blocks with candidate groups count: {len(blocks_with_cand)} (Classified candidates: {len(cand_blocks)})")
assert len(cand_blocks) == 2, "Candidate blocks should be exactly 2"
for cb in cand_blocks:
    print(f"    - Candidate: {cb['block_id']}, group={cb['planning_group_id']}, status={cb['status']}, coords={cb['line_coords']}")

# Test status filtering
classified_only = fetch_allocated_blocks(division_name="Vijayawada Division (BZA)", status_filter="CLASSIFIED", dept_filter="ALL")
print(f"  [PASS] Filtered 'CLASSIFIED' count: {len(classified_only)}")
assert all(b["status"] == "CLASSIFIED" for b in classified_only)

print("\n" + "=" * 60)
print("3. VERIFYING fetch_live_trains (LAYER 2)")
print("=" * 60)
trains_bza = fetch_live_trains(division_name="Vijayawada Division (BZA)", train_filter="ALL")
print(f"  [PASS] BZA Live Trains count: {len(trains_bza)}")
assert len(trains_bza) >= 3, "Should have at least 3 live trains for BZA"
for tr in trains_bza:
    print(f"    - Train {tr['train_number']}: {tr['train_name']} at ({tr['latitude']}, {tr['longitude']}), KM={tr['current_km']}, speed={tr['speed']} km/h, status={tr['status']}")
    assert 10.0 <= tr['latitude'] <= 32.0 and 70.0 <= tr['longitude'] <= 92.0

trains_sc = fetch_live_trains(division_name="Secunderabad Division (SC)", train_filter="ALL")
print(f"  [PASS] SC Live Trains count: {len(trains_sc)}")
assert len(trains_sc) >= 2, "Should have at least 2 live trains for SC"
for tr in trains_sc:
    print(f"    - Train {tr['train_number']}: {tr['train_name']} at ({tr['latitude']}, {tr['longitude']}), status={tr['status']}")

print("\n" + "=" * 60)
print("4. VERIFYING ControllerMap.generate_html()")
print("=" * 60)
map_html = ControllerMap.generate_html(division_name="Vijayawada Division (BZA)")
assert "leaflet" in map_html.lower() or "folium" in map_html.lower()
assert "trainHudCard" in map_html
assert "compassCard" in map_html
assert len(map_html) > 5000, "Map HTML should be substantial"
print(f"  [PASS] Map HTML generated successfully ({len(map_html)} bytes)")

print("\n" + "=" * 60)
print("ALL MAP & LIVE TRAIN TESTS PASSED ACCURATELY!")
print("=" * 60)
