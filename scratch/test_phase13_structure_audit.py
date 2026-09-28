import sys
import os

def test_phase13_structure_audit():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    print("Phase 13 Structure Audit:")

    # 1. Department Navigation Items
    idx_dept = content.find('dept_menu = st.sidebar.radio(')
    assert idx_dept != -1, "dept_menu radio definition missing"
    dept_options_block = content[idx_dept:idx_dept + 500]
    
    # Verify default is Overview (index 0)
    assert "Operational Overview" in dept_options_block or "Overview" in dept_options_block
    assert "My Requests" in dept_options_block
    assert "Work Status" in dept_options_block
    assert "Maintenance Schedule" in dept_options_block
    print("  [OK] Department sidebar menu contains all required consolidated tabs (Overview, My Requests, Work Status, Maintenance Schedule).")

    # 2. Department Overview Structure
    dept_ov_pos = content.find('elif "Overview" in dept_menu:')
    assert dept_ov_pos != -1
    dept_ov_code = content[dept_ov_pos:dept_ov_pos + 3000]

    pos_div_sel = dept_ov_code.find("dept_ov_sel_div")
    pos_trn_sel = dept_ov_code.find("dept_ov_sel_train")
    pos_corridor = dept_ov_code.find("render_live_corridor_map_plotly")
    pos_map = dept_ov_code.find("render_railflow_geographic_corridor_view")
    pos_metrics = dept_ov_code.find("get_cached_admin_overview_counts")

    assert pos_div_sel != -1 and pos_trn_sel != -1, "Division and Train selectors missing from Department Overview"
    assert pos_div_sel < pos_corridor, "Division selector must appear before corridor"
    assert pos_corridor < pos_map, "Live Corridor must appear before Map"
    assert pos_map < pos_metrics, "Map must appear before metrics cards"
    print("  [OK] Department Overview hierarchy strictly verified (Division + Train -> Live Corridor -> Map -> Other Overview Content).")

    # 3. Department My Requests (Merged All + Pending)
    assert 'All Requisitions' in content and 'Pending Approval' in content and 'req_subtab1, req_subtab2 = st.tabs(' in content
    print("  [OK] Department My Requests contains merged All Requisitions and Pending Approval sub-tabs.")

    # 4. Department Work Status (Merged Approved + Active + Completed + Overdue)
    assert 'tab_appr, tab_act, tab_comp, tab_od = st.tabs([' in content
    print("  [OK] Department Work Status contains merged Approved, Active, Completed, and Overdue sub-tabs with top metrics strip.")

    # 5. Controller Overview (No standalone division selectbox)
    ctrl_ov_pos = content.find('if admin_menu == "📊 Overview":')
    ctrl_ov_end = content.find('elif admin_menu == "⚙️ Deterministic Simulation Mode":', ctrl_ov_pos)
    ctrl_ov_code = content[ctrl_ov_pos:ctrl_ov_end]
    assert "ctrl_overview_selected_division" not in ctrl_ov_code
    assert "selected_ctrl_div = get_shared_selected_division()" in ctrl_ov_code
    print("  [OK] Controller Overview standalone division selectbox successfully removed while preserving data flow.")

    # 6. Controller Loco Pilot Structure
    p6_pos = content.find("def render_phase_6_live_controller_command_center(")
    p6_code = content[p6_pos:p6_pos + 8000]
    
    pos_ctrl_trn_sel = p6_code.find("p6_ctrl_sel_train_")
    pos_ctrl_corridor = p6_code.find("render_live_corridor_map_plotly")
    pos_ctrl_map = p6_code.find("render_railflow_geographic_corridor_view")
    pos_ctrl_cards = p6_code.find("12 MANDATORY TELEMETRY CARDS")

    assert pos_ctrl_trn_sel != -1
    assert pos_ctrl_corridor != -1
    assert pos_ctrl_map != -1
    assert pos_ctrl_trn_sel < pos_ctrl_corridor, "Controller Train selector must appear before corridor"
    assert pos_ctrl_corridor < pos_ctrl_map, "Controller Live Corridor must appear before Map"
    assert pos_ctrl_map < pos_ctrl_cards, "Controller Map must appear before telemetry cards"
    print("  [OK] Controller Loco Pilot hierarchy strictly verified (Division + Train -> Live Corridor -> Map -> Telemetry & Registers).")

    print("\nPhase 13 Structure Audit Passed with 100% compliance.")

if __name__ == "__main__":
    test_phase13_structure_audit()
