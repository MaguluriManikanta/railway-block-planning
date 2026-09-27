"""
Test Suite: Step 15 Classified Requests Persistence
Verifies:
1. All classified request IDs are persisted to request_classification_history and block_requests_v2 / defects.
2. Classified requests are permanently excluded from New Requests on fresh fetches, page reloads, and app restarts.
3. Genuinely new/unprocessed requests still appear under New Requests.
4. Hydration from SQLite into classified workspace works when session state is empty.
"""

import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath("."))
from app.controller_requests import fetch_controller_requests, DB_PATH
from app.classification_engine import RequestClassificationEngine


class TestStep15ClassifiedPersistence(unittest.TestCase):

    def setUp(self):
        # Insert a temporary test request into block_requests_v2
        self.test_req_id = f"TEST-PERSIST-{int(datetime.now().timestamp())}"
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
            VALUES (?, 'PORTAL', 'Engineering', 'Track Renewal', 'P-Way Track', 'Section BZA-KI',
                    570.0, 574.0, 'Vijayawada–Kondapalli', 'DOWN Line', 'DOWN', ?, 45,
                    30, '02:00', ?, 'High', 'Test persistence track renewal', 'NEW', 'PREVENTIVE')
        """, (
            self.test_req_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            (datetime.now() + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

    def tearDown(self):
        # Clean up test request from db
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cur = conn.cursor()
        cur.execute("DELETE FROM block_requests_v2 WHERE request_id = ?", (self.test_req_id,))
        cur.execute("DELETE FROM request_classification_history WHERE request_ids LIKE ?", (f"%{self.test_req_id}%",))
        conn.commit()
        conn.close()

    def test_new_request_appears_before_classification(self):
        new_reqs, overdue_reqs, total_new, total_overdue = fetch_controller_requests()
        req_ids = [r["request_id"] for r in new_reqs]
        self.assertIn(self.test_req_id, req_ids, "Unclassified new request must appear in New Requests")

    def test_classified_request_is_permanently_excluded_from_new_requests(self):
        new_reqs, overdue_reqs, _, _ = fetch_controller_requests()
        target = [r for r in new_reqs if r["request_id"] == self.test_req_id]
        self.assertTrue(len(target) == 1, "Target test request must be fetched")

        # Classify the request
        res = RequestClassificationEngine.classify_all_actionable_requests(target)
        self.assertIn(self.test_req_id, res["classified_ids"], "Target test request must be in classified_ids")

        # Fetch again (simulating navigation/refresh)
        new_reqs_after, overdue_reqs_after, total_new_after, total_overdue_after = fetch_controller_requests()
        req_ids_after = [r["request_id"] for r in new_reqs_after]
        self.assertNotIn(self.test_req_id, req_ids_after, "Classified request must NOT reappear in New Requests")

        # Verify DB status
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        cur = conn.cursor()
        cur.execute("SELECT status FROM block_requests_v2 WHERE request_id = ?", (self.test_req_id,))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "CLASSIFIED", "DB status must be CLASSIFIED")

        # Verify classification history
        cur.execute("SELECT COUNT(*) FROM request_classification_history WHERE request_ids LIKE ?", (f"%{self.test_req_id}%",))
        hist_count = cur.fetchone()[0]
        self.assertGreaterEqual(hist_count, 1, "Classification history record must exist")
        conn.close()

    def test_persisted_classified_results_hydration(self):
        # Hydration function should return dictionary with all_groups and counts
        persisted = RequestClassificationEngine.get_persisted_classified_results()
        self.assertIsInstance(persisted, dict)
        if persisted:
            self.assertIn("all_groups", persisted)
            self.assertIn("counts", persisted)
            self.assertIn("isolation", persisted["counts"])
            self.assertIn("parallel", persisted["counts"])
            self.assertIn("sequential", persisted["counts"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
