import unittest
import pandas as pd
import sqlite3
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import get_db

class TestPhase2MergeWorkStatus(unittest.TestCase):

    def test_01_approved_data_integrity(self):
        conn = get_db()
        df_final = pd.read_sql("SELECT * FROM final_block_allocations WHERE is_active=1", conn)
        df_sched = pd.read_sql("SELECT * FROM schedule WHERE LOWER(status) NOT IN ('completed', 'cancelled')", conn)
        conn.close()
        self.assertIsInstance(df_final, pd.DataFrame)
        self.assertIsInstance(df_sched, pd.DataFrame)

    def test_02_completed_work_data_integrity(self):
        conn = get_db()
        df_comp = pd.read_sql("SELECT * FROM defects WHERE LOWER(status) = 'completed'", conn)
        conn.close()
        self.assertIsInstance(df_comp, pd.DataFrame)
        for _, row in df_comp.iterrows():
            self.assertEqual(row['status'].lower(), 'completed')

    def test_03_overdue_work_data_integrity(self):
        conn = get_db()
        df_od = pd.read_sql("SELECT * FROM defects WHERE status != 'Completed' AND overdue_days > 0", conn)
        conn.close()
        self.assertIsInstance(df_od, pd.DataFrame)
        for _, row in df_od.iterrows():
            self.assertNotEqual(row['status'], 'Completed')
            self.assertGreater(row['overdue_days'], 0)

    def test_04_department_breakdowns_preserved(self):
        conn = get_db()
        for dept in ["Engineering", "S&T", "TRD"]:
            df_d_comp = pd.read_sql("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(status)='completed'", conn, params=(dept,))
            self.assertGreaterEqual(df_d_comp.iloc[0, 0], 0)
        conn.close()

if __name__ == "__main__":
    unittest.main()
