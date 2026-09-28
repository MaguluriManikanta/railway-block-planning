import sys
import os
import ast

def test_phase4_overview_structure():
    with open("app/main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the Operational Overview section in render_phase_7_department_portal
    overview_pos = content.find('elif "Overview" in dept_menu:')
    assert overview_pos != -1, "Operational Overview block not found"
    
    # Check ordering of elements after Overview declaration
    overview_content = content[overview_pos:overview_pos + 4000]
    
    pos_live_control = overview_content.find("render_live_corridor_map_plotly")
    pos_geo_map = overview_content.find("render_railflow_geographic_corridor_view")
    pos_metrics = overview_content.find("get_cached_admin_overview_counts")
    pos_kpi = overview_content.find("render_operational_kpi_bar")
    pos_analytics = overview_content.find("Analytics & Visual Distributions")
    
    assert pos_live_control != -1, "Live Control not found in Overview"
    assert pos_geo_map != -1, "Geographic Map not found in Overview"
    assert pos_metrics != -1, "Metrics cards not found in Overview"
    assert pos_kpi != -1, "KPI bar not found in Overview"
    assert pos_analytics != -1, "Analytics charts not found in Overview"
    
    assert pos_live_control < pos_geo_map, f"Live Control ({pos_live_control}) should come before Geographic Map ({pos_geo_map})"
    assert pos_geo_map < pos_metrics, f"Geographic Map ({pos_geo_map}) should come before Metrics cards ({pos_metrics})"
    assert pos_metrics < pos_kpi, f"Metrics ({pos_metrics}) should come before KPI ({pos_kpi})"
    assert pos_kpi < pos_analytics, f"KPI ({pos_kpi}) should come before Analytics ({pos_analytics})"

    print("Phase 4 Test Passed: Live Control & Corridor Tracking appears first, Geographic Map appears second, followed by metrics, KPI bar, analytics, and data tables.")

if __name__ == "__main__":
    test_phase4_overview_structure()
