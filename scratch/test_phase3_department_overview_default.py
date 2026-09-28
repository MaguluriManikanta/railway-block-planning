import unittest
import pandas as pd
import sqlite3
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import get_db, get_cached_admin_overview_counts

class TestPhase3DepartmentOverviewDefault(unittest.TestCase):

    def test_01_department_counts_for_overview(self):
        for dept in ["Engineering", "S&T", "TRD"]:
            counts = get_cached_admin_overview_counts(dept)
            self.assertIsInstance(counts, dict)
            for key in ["total_def", "open_def", "sched_def", "comp_def", "sched_blocks", "crit_def"]:
                self.assertIn(key, counts)
                self.assertIsInstance(counts[key], int)

    def test_02_department_defect_tables_for_overview(self):
        conn = get_db()
        for dept in ["Engineering", "S&T", "TRD"]:
            df = pd.read_sql("""
                SELECT defect_id, section_id, defect_type, severity, priority_score, status
                FROM defects
                WHERE department = ?
                ORDER BY priority_score DESC LIMIT 10
            """, conn, params=(dept,))
            self.assertIsInstance(df, pd.DataFrame)
        conn.close()

if __name__ == "__main__":
    unittest.main()
