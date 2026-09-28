import sys
import os

def test_phase11_controller_division_train():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Check Division selector in Controller Loco Pilot
    loco_pos = content.find('if admin_menu == "🚆 Locopilot Speed & Live Trains":')
    assert loco_pos != -1, "Locopilot Speed & Live Trains section not found"
    
    loco_div_block = content[loco_pos:loco_pos + 2500]
    assert "live_track_selected_division" in loco_div_block, "Division selector live_track_selected_division not found"
    assert "render_phase_6_live_controller_command_center(division=selected_division)" in loco_div_block, "selected_division not passed to command center"

    # 2. Check Train selector in command center
    p6_pos = content.find("def render_phase_6_live_controller_command_center(")
    p6_block = content[p6_pos:p6_pos + 8000]
    
    assert "get_division_train_options(division)" in p6_block, "get_division_train_options not called in controller command center"
    assert "p6_ctrl_sel_train_" in p6_block, "Train selector key per division missing"
    
    # 3. Check selected_train passed to Plotly and Folium maps
    assert "render_live_corridor_map_plotly(df_active_trains, division=division, selected_train=sel_train_opt)" in p6_block, "selected_train not passed to Plotly map in controller"
    assert "render_railflow_geographic_corridor_view(division=division, df_trains=df_active_trains, show_timeline=True, selected_train=sel_train_opt)" in p6_block, "selected_train not passed to Folium map in controller"

    print("Phase 11 Test Passed: Controller Loco Pilot / Live Trains fully supports Division + Train selection and live Map updates.")

if __name__ == "__main__":
    test_phase11_controller_division_train()
