import sys
import os

def test_phase8_overview_div_selector():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find Controller Overview block
    ov_pos = content.find('if admin_menu == "📊 Overview":')
    assert ov_pos != -1, "Controller Overview block not found"
    
    # Block up to next menu item
    next_pos = content.find('elif admin_menu == "⚙️ Deterministic Simulation Mode":', ov_pos)
    ov_block = content[ov_pos:next_pos]
    
    # 1. Verify unnecessary selectbox is removed
    assert "ctrl_overview_selected_division" not in ov_block, "Unnecessary division selectbox still exists in Controller Overview"
    assert 'st.selectbox(\n                    "🚉 Division:",' not in ov_block, "st.selectbox for Division still present in Controller Overview"
    
    # 2. Verify selected_ctrl_div is still assigned
    assert "selected_ctrl_div = get_shared_selected_division()" in ov_block, "get_shared_selected_division() not used in Controller Overview"
    
    # 3. Verify division selector in Department Overview is intact
    dept_ov_pos = content.find('elif "Overview" in dept_menu:')
    assert "dept_ov_sel_div" in content[dept_ov_pos:dept_ov_pos+2000], "Department division selector must remain intact"
    
    print("Phase 8 Test Passed: Unnecessary division selector removed from Controller Overview while retaining shared data flow.")

if __name__ == "__main__":
    test_phase8_overview_div_selector()
