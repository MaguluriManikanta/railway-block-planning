import sys
import os
import ast

def test_phase6_department_map_division_train():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the Overview block in Department Portal
    ov_pos = content.find('elif "Overview" in dept_menu:')
    assert ov_pos != -1, "Department Overview block not found"
    
    ov_block = content[ov_pos:ov_pos + 2500]
    
    # 1. Check division selectbox
    assert "dept_ov_sel_div" in ov_block, "Division selector dept_ov_sel_div not found in Overview"
    
    # 2. Check train selectbox
    assert "dept_ov_sel_train" in ov_block, "Train selector dept_ov_sel_train not found in Overview"
    assert "get_division_train_options" in ov_block, "get_division_train_options call not found in Overview"
    
    # 3. Check selected_train passed to Plotly corridor map
    assert "render_live_corridor_map_plotly" in ov_block, "Plotly map call missing"
    assert "selected_train=dept_ov_sel_train" in ov_block, "selected_train not passed to Plotly map"
    
    # 4. Check selected_train passed to Folium geographic corridor map
    assert "render_railflow_geographic_corridor_view" in ov_block, "Folium map call missing"
    
    # Check that render_railflow_geographic_corridor_view call in ov_block has selected_train=dept_ov_sel_train
    call_geo_idx = ov_block.find("render_railflow_geographic_corridor_view")
    call_geo_block = ov_block[call_geo_idx:call_geo_idx + 400]
    assert "selected_train=dept_ov_sel_train" in call_geo_block, "selected_train not passed to Geographic map"
    
    print("Phase 6 Test Passed: Department Map supports Step 1 Division + Step 2 Train Selection with live synchronization to Corridor and Maps.")

if __name__ == "__main__":
    test_phase6_department_map_division_train()
