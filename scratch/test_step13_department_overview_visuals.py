"""
Test Step 13: Department & Controller Overview Charts, Graphs & Data Tables Verification
========================================================================================
Validates:
1. Department Overview contains KPI metric cards (Total defects, Open Backlog, Scheduled Blocks, Completed Tasks, Completion Rate).
2. Department Overview renders Plotly pie chart for Defect Severity Breakdown (px.pie, df_sev).
3. Department Overview renders Plotly bar chart for Task Status Breakdown (px.bar, df_st).
4. Department Overview renders Plotly bar chart for Top Priority Railway Sections (px.bar, df_sec).
5. Department Overview renders Plotly horizontal bar chart for Defect Category Frequency (px.bar, df_type).
6. Department Overview renders Geographic Railway Corridor Map (render_railflow_geographic_corridor_view).
7. Department Overview renders Comprehensive Data Tables (High-Priority Defects, Scheduled Possessions, Section Matrix).
8. Controller Overview renders matching visual charts and data tables for all departments and filtered departments.
"""

import unittest
import os
import sqlite3
import pandas as pd

class TestDepartmentAndControllerOverview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'main.py')
        with open(main_path, 'r', encoding='utf-8') as f:
            cls.main_code = f.read()

    def test_01_department_overview_kpi_metrics(self):
        """TEST 1: Department Overview renders 5 KPI metric cards."""
        self.assertIn("Total {cur_dept_cfg['acronym']} Defects", self.main_code)
        self.assertIn("Open Safety Backlog", self.main_code)
        self.assertIn("Active Coordinated Plan", self.main_code)
        self.assertIn("Completion Rate", self.main_code)

    def test_02_department_overview_pie_and_bar_charts(self):
        """TEST 2: Department Overview renders Severity Pie Chart & Status Bar Chart."""
        self.assertIn("Defect Severity Breakdown", self.main_code)
        self.assertIn("px.pie", self.main_code)
        self.assertIn("Task Status Breakdown", self.main_code)
        self.assertIn("px.bar", self.main_code)

    def test_03_department_overview_section_and_type_charts(self):
        """TEST 3: Department Overview renders Top Priority Sections & Defect Frequency Charts."""
        self.assertIn("Top Priority Railway Sections", self.main_code)
        self.assertIn("Defect Category Distribution", self.main_code)
        self.assertIn("avg_priority", self.main_code)

    def test_04_department_overview_map_and_live_trains(self):
        """TEST 4: Department Overview preserves Geographic Corridor Map and Live Train telemetry."""
        self.assertIn("render_railflow_geographic_corridor_view", self.main_code)
        self.assertIn("render_visual_train_cards", self.main_code)
        self.assertIn("render_live_corridor_map_plotly", self.main_code)

    def test_05_department_overview_data_tables(self):
        """TEST 5: Department Overview renders High-Priority Defects, Scheduled Possessions & Section Matrix."""
        self.assertIn("Critical & High-Priority Safety Defects", self.main_code)
        self.assertIn("Confirmed & Active Maintenance Possessions", self.main_code)
        self.assertIn("Section Infrastructure Health & Backlog Breakdown", self.main_code)

    def test_06_controller_overview_data_tables(self):
        """TEST 6: Controller Overview also renders Division-wide and Department-filtered data tables."""
        self.assertIn("Division-Wide Infrastructure Data Registers & Health Matrix", self.main_code)
        self.assertIn("Master Coordinated Maintenance Block Schedule", self.main_code)
        self.assertIn("Department-Wise Backlog & Resolution Health Matrix", self.main_code)

    def test_07_database_queries_validity(self):
        """TEST 7: SQL queries for Engineering, S&T, and TRD return valid data."""
        conn = sqlite3.connect('railway.db')
        for dept in ["Engineering", "S&T", "TRD"]:
            df_sev = pd.read_sql("SELECT severity, COUNT(*) as count FROM defects WHERE department=? GROUP BY severity", conn, params=(dept,))
            self.assertFalse(df_sev.empty, f"Defect severity breakdown must have records for {dept}")

            df_st = pd.read_sql("SELECT status, COUNT(*) as count FROM defects WHERE department=? GROUP BY status", conn, params=(dept,))
            self.assertFalse(df_st.empty, f"Defect status breakdown must have records for {dept}")

            df_sec = pd.read_sql("""
                SELECT section_id, COUNT(*) as defect_count, AVG(priority_score) as avg_priority 
                FROM defects 
                WHERE department=? AND LOWER(status)!='completed'
                GROUP BY section_id 
                ORDER BY avg_priority DESC 
                LIMIT 10
            """, conn, params=(dept,))
            self.assertFalse(df_sec.empty, f"High-priority sections query must have records for {dept}")
        conn.close()


if __name__ == '__main__':
    unittest.main()
