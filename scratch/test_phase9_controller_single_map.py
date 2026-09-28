import sys
import os

def test_phase9_controller_single_map():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the entire Controller Loco Pilot section
    loco_pos = content.find('if admin_menu == "🚆 Locopilot Speed & Live Trains":')
    assert loco_pos != -1, "Locopilot Speed & Live Trains section not found"
    
    # End of this section (where 'else:' for other menus begins)
    loco_end = content.find('if admin_menu == "📊 Overview":', loco_pos)
    assert loco_end != -1, "Next menu section not found"
    
    loco_section = content[loco_pos:loco_end]
    
    # Count direct render_railflow_geographic_corridor_view calls within the section (excluding render_phase_6 which is defined elsewhere)
    direct_calls = loco_section.count("render_railflow_geographic_corridor_view(")
    assert direct_calls == 0, f"Expected 0 direct calls in loco section (it uses render_phase_6), found {direct_calls}"
    
    # Check that render_phase_6_live_controller_command_center is called exactly once
    p6_calls = loco_section.count("render_phase_6_live_controller_command_center(")
    assert p6_calls == 1, f"Expected 1 call to render_phase_6_live_controller_command_center, found {p6_calls}"
    
    # Inside render_phase_6_live_controller_command_center definition, check single map call
    p6_def_pos = content.find("def render_phase_6_live_controller_command_center(")
    p6_def_end = content.find("def render_phase_7_department_portal(", p6_def_pos)
    p6_def = content[p6_def_pos:p6_def_end]
    
    geo_calls_in_p6 = p6_def.count("render_railflow_geographic_corridor_view(")
    assert geo_calls_in_p6 == 1, f"Expected exactly 1 map call in render_phase_6, found {geo_calls_in_p6}"
    
    print("Phase 9 Test Passed: Exactly ONE Map exists in Controller Loco Pilot / Live Trains tab.")

if __name__ == "__main__":
    test_phase9_controller_single_map()
