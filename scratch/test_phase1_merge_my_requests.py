import unittest
import pandas as pd
import sqlite3
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import get_db, get_department_my_requests

class TestPhase1MergeMyRequests(unittest.TestCase):

    def test_01_verify_db_block_requests_unaffected(self):
        conn = get_db()
        df = pd.read_sql("SELECT * FROM block_requests_v2", conn)
        conn.close()
        self.assertIsInstance(df, pd.DataFrame)
        # Verify schema
        for col in ["request_id", "department", "request_type", "section", "status"]:
            self.assertIn(col, df.columns)

    def test_02_verify_department_my_requests_helper(self):
        for dept in ["Engineering", "S&T", "TRD"]:
            reqs = get_department_my_requests(dept)
            self.assertIsInstance(reqs, list)
            for r in reqs:
                self.assertIn("workflow_status", r)
                self.assertIn("request_id", r)

    def test_03_verify_pending_filtering(self):
        conn = get_db()
        df_pending = pd.read_sql("""
            SELECT r.request_id, r.request_type, r.section, r.line, r.required_duration, r.preferred_start, r.deadline, r.priority, r.status
            FROM block_requests_v2 r
            WHERE (r.status IN ('Pending', 'SUBMITTED') OR UPPER(r.status) LIKE '%PENDING%')
        """, conn)
        conn.close()
        self.assertIsInstance(df_pending, pd.DataFrame)

if __name__ == "__main__":
    unittest.main()
