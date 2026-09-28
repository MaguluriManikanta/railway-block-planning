import unittest
import pandas as pd
import sqlite3
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import (
    get_full_schedule,
    generate_ai_block_plan_matrix_html,
    display_overall_statistics,
    get_db
)

class TestDepartmentMaintenanceSchedule(unittest.TestCase):
    def test_01_get_full_schedule_weekly(self):
        df_weekly = get_full_schedule(horizon="weekly")
        self.assertIsInstance(df_weekly, pd.DataFrame)

    def test_02_get_full_schedule_monthly(self):
        df_monthly = get_full_schedule(horizon="monthly")
        self.assertIsInstance(df_monthly, pd.DataFrame)

    def test_03_generate_matrix_html_for_each_department(self):
        df_weekly = get_full_schedule(horizon="weekly")
        for dept in ["Engineering", "S&T", "TRD"]:
            html = generate_ai_block_plan_matrix_html(df_weekly, current_dept=dept, color_mode="department")
            self.assertIsInstance(html, str)
            self.assertTrue(len(html) > 0)
            self.assertIn("matrixGridWrapper", html)

    def test_04_department_filtered_slices(self):
        df_weekly = get_full_schedule(horizon="weekly")
        if not df_weekly.empty:
            for dept in ["Engineering", "S&T", "TRD"]:
                dept_df = df_weekly[df_weekly["department"] == dept]
                self.assertIsInstance(dept_df, pd.DataFrame)

if __name__ == "__main__":
    unittest.main()
