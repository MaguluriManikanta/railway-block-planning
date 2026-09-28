import sys
import os

def test_phase12_unified_map_subsystem():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Verify single definition of geographic map
    geo_defs = content.count("def render_railflow_geographic_corridor_view(")
    assert geo_defs == 1, f"Expected exactly 1 definition of render_railflow_geographic_corridor_view, found {geo_defs}"

    # 2. Verify single definition of linear corridor map
    corridor_defs = content.count("def render_live_corridor_map_plotly(")
    assert corridor_defs == 1, f"Expected exactly 1 definition of render_live_corridor_map_plotly, found {corridor_defs}"

    # 3. Verify single definition of train options helper
    train_opt_defs = content.count("def get_division_train_options(")
    assert train_opt_defs == 1, f"Expected exactly 1 definition of get_division_train_options, found {train_opt_defs}"

    # 4. Verify that Department and Controller both invoke the unified functions
    dept_pos = content.find('elif "Overview" in dept_menu:')
    ctrl_pos = content.find("def render_phase_6_live_controller_command_center(")

    dept_block = content[dept_pos:dept_pos + 3000]
    ctrl_block = content[ctrl_pos:ctrl_pos + 8000]

    for block_name, block in [("Department Overview", dept_block), ("Controller Command Center", ctrl_block)]:
        assert "get_division_train_options(" in block, f"{block_name} does not use unified get_division_train_options"
        assert "get_active_trains_df(" in block, f"{block_name} does not use unified get_active_trains_df"
        assert "render_live_corridor_map_plotly(" in block, f"{block_name} does not use unified render_live_corridor_map_plotly"
        assert "render_railflow_geographic_corridor_view(" in block, f"{block_name} does not use unified render_railflow_geographic_corridor_view"

    print("Phase 12 Test Passed: Department and Controller share 100% unified Map and Corridor subsystem.")

if __name__ == "__main__":
    test_phase12_unified_map_subsystem()
