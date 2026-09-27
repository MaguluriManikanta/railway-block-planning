import sys
sys.path.insert(0, '.')
from app.controller_map import ControllerMap, fetch_allocated_blocks, fetch_live_trains, get_division_network_data
from app.main import render_live_corridor_map_plotly, get_active_trains_df

# 1. Test ControllerMap
print("=== 1. ControllerMap (Leaflet) ===")
net_data = get_division_network_data("Vijayawada Division (BZA)")
print(f"Stations count: {len(net_data.get('stations', []))}")
print(f"Tracks count: {len(net_data.get('tracks', []))}")

blocks = fetch_allocated_blocks("Vijayawada Division (BZA)", status_filter="ALL", dept_filter="ALL")
print(f"Allocated / Candidate blocks count: {len(blocks)}")
for b in blocks:
    print(f"  - Block {b.get('id')}: status={b.get('status')}, geom_len={len(b.get('geometry', []))}, sec={b.get('section')}")

trains = fetch_live_trains("Vijayawada Division (BZA)", train_filter="ALL", search_query="")
print(f"Live trains count: {len(trains)}")
for t in trains[:3]:
    print(f"  - Train {t.get('train_id')} ({t.get('train_number')}): pos=({t.get('lat')}, {t.get('lon')}), status={t.get('status')}")

html = ControllerMap.generate_html("Vijayawada Division (BZA)")
print(f"Generated Leaflet HTML length: {len(html)}")
print(f"Contains 'L.tileLayer': {'L.tileLayer' in html or 'tileLayer' in html}")
print(f"Contains 'L.polyline' or track lines: {'polyline' in html.lower()}")
print(f"Contains train markers: {'🚆' in html or 'marker' in html.lower()}")

# 2. Test Plotly Map
print("\n=== 2. Plotly Live Corridor Map ===")
df_trains = get_active_trains_df("Vijayawada Division (BZA)")
print(f"Active trains DF shape: {df_trains.shape}")
fig = render_live_corridor_map_plotly(df_trains, division="Vijayawada Division (BZA)")
print(f"Plotly traces count: {len(fig.data)}")
for i, tr in enumerate(fig.data):
    print(f"  Trace {i}: name='{tr.name}', mode='{tr.mode}', x_len={len(tr.x) if hasattr(tr, 'x') and tr.x is not None else 0}")
