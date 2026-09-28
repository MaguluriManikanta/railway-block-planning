import sys
import os

def test_phase10_loco_pilot_tab_order():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    p6_def_pos = content.find("def render_phase_6_live_controller_command_center(")
    assert p6_def_pos != -1, "render_phase_6_live_controller_command_center not found"
    
    p6_def_end = content.find("def render_phase_7_department_portal(", p6_def_pos)
    p6_code = content[p6_def_pos:p6_def_end]
    
    # Strip docstring
    doc_end = p6_code.find('"""', 10)
    if doc_end != -1:
        doc_end_2 = p6_code.find('"""', doc_end + 3)
        if doc_end_2 != -1:
            p6_code = p6_code[doc_end_2 + 3:]
    
    pos_live_corridor = p6_code.find("render_live_corridor_map_plotly")
    pos_geo_map = p6_code.find("render_railflow_geographic_corridor_view")
    pos_telemetry_cards = p6_code.find("12 MANDATORY TELEMETRY CARDS")
    pos_timeline = p6_code.find("Live Block Timeline (Horizontal Operational Time-Gap)")
    
    assert pos_live_corridor != -1, "Live Corridor call not found"
    assert pos_geo_map != -1, "Geographic Map call not found"
    assert pos_telemetry_cards != -1, "Telemetry cards not found"
    assert pos_timeline != -1, "Timeline not found"
    
    assert pos_live_corridor < pos_geo_map, f"Live Corridor ({pos_live_corridor}) must appear before Map ({pos_geo_map})"
    assert pos_geo_map < pos_telemetry_cards, f"Map ({pos_geo_map}) must appear before Telemetry Cards ({pos_telemetry_cards})"
    assert pos_telemetry_cards < pos_timeline, f"Telemetry Cards ({pos_telemetry_cards}) must appear before Timeline ({pos_timeline})"
    
    print("Phase 10 Test Passed: Controller Loco Pilot / Live Trains order verified (1. Live Control & Linear Corridor Tracking -> 2. Geographic Map -> 3. Other existing relevant content).")

if __name__ == "__main__":
    test_phase10_loco_pilot_tab_order()
