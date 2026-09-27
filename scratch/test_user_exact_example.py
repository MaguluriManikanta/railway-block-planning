"""
Test: User's Exact Example
Scenario:
- Initial Queue: New Requests = 0, Overdue Requests = 28.
- Action: Controller classifies the 28 requests.
- Expected Result:
  - New Requests = 0
  - Overdue Requests = 0
  - Total Pending = 0
  - Classification candidate groups saved and visible
  - Survives browser refresh (remains 0)
  - When 1 new request is submitted later -> New Requests = 1, Overdue = 0.
"""

import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath("."))
from app.controller_requests import fetch_controller_requests, DB_PATH
from app.classification_engine import RequestClassificationEngine


class TestUserExactExample(unittest.TestCase):

    def setUp(self):
        self.now = datetime.now()
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()

        ts = int(self.now.timestamp())
        self.od_ids = [f"USER-OD-{ts}-{i:02d}" for i in range(1, 29)] # Exactly 28 overdue requests
        self.all_ids = list(self.od_ids)

        # 1. Clean previous artifacts
        cur.executemany("DELETE FROM block_requests_v2 WHERE request_id = ?", [(i,) for i in self.all_ids])
        cur.executemany("DELETE FROM request_classification_history WHERE request_ids LIKE ?", [(f"%{i}%",) for i in self.all_ids])

        # 2. Insert exactly 28 overdue requests into block_requests_v2 (and 0 new requests)
        od_rows = []
        for i, od_id in enumerate(self.od_ids):
            dept = "Engineering" if i % 3 == 0 else ("Tenders" if i % 3 == 1 else "S&T")
            od_rows.append((
                od_id, "DATABASE", dept, "Corridor Overdue Maintenance", "Track Asset",
                "Section BZA-KI", 570.0 + (i % 6), 574.0 + (i % 6), "Vijayawada–Kondapalli", "DOWN Line", "DOWN",
                (self.now - timedelta(hours=36)).strftime("%Y-%m-%d %H:%M:%S"), 45, 30, "02:00",
                (self.now - timedelta(hours=14)).strftime("%Y-%m-%d %H:%M:%S"), "High",
                f"Overdue maintenance requisition #{i+1}", "OVERDUE", "CORRECTIVE_MAINTENANCE"
            ))
        cur.executemany("""
            INSERT INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, od_rows)

        conn.commit()
        conn.close()

    def tearDown(self):
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()
        for i in self.all_ids + [getattr(self, "later_req_id", "")]:
            if i:
                cur.execute("DELETE FROM block_requests_v2 WHERE request_id = ?", (i,))
                cur.execute("DELETE FROM request_classification_history WHERE request_ids LIKE ?", (f"%{i}%",))
        conn.commit()
        conn.close()

    def test_new_0_overdue_28_classification_lifecycle(self):
        # 1. INITIAL STATE: New = 0, Overdue = 28
        new_reqs, overdue_reqs, total_new, total_overdue = fetch_controller_requests()
        test_new = [r for r in new_reqs if r["request_id"] in self.all_ids]
        test_od = [r for r in overdue_reqs if r["request_id"] in self.all_ids]

        print(f"\n[TEST] Before Classify: New = {len(test_new)}, Overdue = {len(test_od)}, Total = {len(test_new) + len(test_od)}")
        self.assertEqual(len(test_new), 0, "Expected New Requests = 0")
        self.assertEqual(len(test_od), 28, "Expected Overdue Requests = 28")

        # 2. CLASSIFY REQUESTS
        actionable = test_new + test_od
        self.assertEqual(len(actionable), 28)
        res = RequestClassificationEngine.classify_all_actionable_requests(actionable)
        print(f"[TEST] Classified into {res['counts']['total']} groups: {res['counts']}")
        self.assertEqual(len(res["classified_ids"]), 28)

        # 3. AFTER CLASSIFICATION: New = 0, Overdue = 0, Total = 0
        new_after, overdue_after, total_new_after, total_overdue_after = fetch_controller_requests()
        test_new_after = [r for r in new_after if r["request_id"] in self.all_ids]
        test_od_after = [r for r in overdue_after if r["request_id"] in self.all_ids]

        print(f"[TEST] After Classify: New = {len(test_new_after)}, Overdue = {len(test_od_after)}, Total = {len(test_new_after) + len(test_od_after)}")
        self.assertEqual(len(test_new_after), 0, "After classification, New Requests must be 0")
        self.assertEqual(len(test_od_after), 0, "After classification, Overdue Requests must be 0 (classified requests are not pending)")
        self.assertEqual(len(test_new_after) + len(test_od_after), 0, "Total must decrease to 0")

        # 4. REFRESH / RELOAD: New = 0, Overdue = 0, Total = 0
        new_refreshed, overdue_refreshed, _, _ = fetch_controller_requests()
        test_new_refreshed = [r for r in new_refreshed if r["request_id"] in self.all_ids]
        test_od_refreshed = [r for r in overdue_refreshed if r["request_id"] in self.all_ids]

        print(f"[TEST] After Refresh: New = {len(test_new_refreshed)}, Overdue = {len(test_od_refreshed)}, Total = {len(test_new_refreshed) + len(test_od_refreshed)}")
        self.assertEqual(len(test_new_refreshed), 0, "On refresh, New Requests must remain 0")
        self.assertEqual(len(test_od_refreshed), 0, "On refresh, Overdue Requests must remain 0")
        self.assertEqual(len(test_new_refreshed) + len(test_od_refreshed), 0, "On refresh, Total must remain 0")

        # 5. LATER: Engineering submits 1 genuinely new request
        self.later_req_id = f"ENG-LATER-{int(self.now.timestamp())}"
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
            VALUES (?, 'PORTAL', 'Engineering', 'Track Renewal', 'P-Way Track', 'Section BZA-KI',
                    570.0, 574.0, 'Vijayawada–Kondapalli', 'DOWN Line', 'DOWN', ?, 45,
                    30, '02:00', ?, 'High', 'Track renewal requisition', 'SUBMITTED', 'PREVENTIVE')
        """, (
            self.later_req_id,
            self.now.strftime("%Y-%m-%d %H:%M:%S"),
            (self.now + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        # Check queue
        new_final, overdue_final, _, _ = fetch_controller_requests()
        later_reqs = [r for r in new_final if r["request_id"] == self.later_req_id]
        print(f"[TEST] After 1 New Submission: New = {len(later_reqs)}, Overdue = {len([r for r in overdue_final if r['request_id'] in self.all_ids])}")
        self.assertEqual(len(later_reqs), 1, "Expected New Requests = 1 after new submission")


if __name__ == "__main__":
    unittest.main(verbosity=2)
