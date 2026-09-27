"""
Acceptance Test for Section 18: Exact Department Request Flow & State Lifecycle
Simulates:
1. Initial State: 24 existing overdue/processed requests + 3 genuinely newly submitted department requests (Engineering, Tenders, S&T) = 27 total.
2. Verify Controller Sees: New Requests = 3, Total Requests = 27.
3. Execute Classification on all 27 requests.
4. Verify Post-Classification: New Requests = 0. Classified candidate groups formed.
5. Verify Refresh/Reload: New Requests = 0.
6. Verify Department Submission: Engineering submits 1 new request -> New Requests = 1, Total = 28 (or previously classified + new).
"""

import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath("."))
from app.controller_requests import fetch_controller_requests, DB_PATH
from app.classification_engine import RequestClassificationEngine


class TestDepartmentRequestLifecycleExact(unittest.TestCase):

    def setUp(self):
        self.now = datetime.now()
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()

        # Generate unique IDs for this test run
        ts = int(self.now.timestamp())
        self.od_ids = [f"OD-REQ-{ts}-{i:02d}" for i in range(1, 25)] # 24 overdue requests
        self.new_ids = [
            f"ENG-NEW-{ts}-01",
            f"TEND-NEW-{ts}-02",
            f"SNT-NEW-{ts}-03"
        ] # 3 genuinely new department requests
        self.all_ids = self.od_ids + self.new_ids

        # 1. Clean any previous test artifacts
        cur.executemany("DELETE FROM block_requests_v2 WHERE request_id = ?", [(i,) for i in self.all_ids])
        cur.executemany("DELETE FROM request_classification_history WHERE request_ids LIKE ?", [(f"%{i}%",) for i in self.all_ids])

        # 2. Insert 24 overdue requests
        od_rows = []
        for i, od_id in enumerate(self.od_ids):
            dept = "Engineering" if i % 3 == 0 else ("Tenders" if i % 3 == 1 else "S&T")
            od_rows.append((
                od_id, "DATABASE", dept, "Overdue Track Maintenance", "Track Equipment",
                "Section BZA-KI", 570.0 + (i % 5), 573.0 + (i % 5), "Vijayawada–Kondapalli", "DOWN Line", "DOWN",
                (self.now - timedelta(hours=36)).strftime("%Y-%m-%d %H:%M:%S"), 45, 30, "02:00",
                (self.now - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S"), "High",
                f"Existing overdue defect repair #{i+1}", "OVERDUE", "CORRECTIVE_MAINTENANCE"
            ))
        cur.executemany("""
            INSERT INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, od_rows)

        # 3. Insert 3 genuinely new department requests
        new_rows = [
            (self.new_ids[0], "PORTAL", "Engineering", "Track Tamping", "P-Way Track", "Section BZA-KI", 571.0, 575.0, "Vijayawada–Kondapalli", "DOWN Line", "DOWN", self.now.strftime("%Y-%m-%d %H:%M:%S"), 30, 20, "02:00", (self.now + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S"), "High", "Track tamping post sleeper replacement", "NEW", "PREVENTIVE"),
            (self.new_ids[1], "PORTAL", "Tenders", "Catenary Inspection", "OHE Catenary", "Section BZA-KI", 572.0, 576.0, "Vijayawada–Kondapalli", "DOWN Line", "DOWN", self.now.strftime("%Y-%m-%d %H:%M:%S"), 45, 30, "02:00", (self.now + timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S"), "High", "OHE catenary wire adjustment", "NEW", "PREVENTIVE"),
            (self.new_ids[2], "PORTAL", "S&T", "Point Machine Calibration", "Signal Equipment", "Section BZA-KI", 571.0, 574.0, "Vijayawada–Kondapalli", "DOWN Line", "DOWN", self.now.strftime("%Y-%m-%d %H:%M:%S"), 30, 20, "02:00", (self.now + timedelta(hours=22)).strftime("%Y-%m-%d %H:%M:%S"), "Medium", "Point machine tuning", "NEW", "PREVENTIVE")
        ]
        cur.executemany("""
            INSERT INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, new_rows)

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

    def test_full_request_lifecycle_and_persistence(self):
        # -------------------------------------------------------------
        # STEP 1: Initial State Check
        # -------------------------------------------------------------
        new_reqs, overdue_reqs, total_new, total_overdue = fetch_controller_requests()
        test_new_found = [r for r in new_reqs if r["request_id"] in self.new_ids]
        test_od_found = [r for r in overdue_reqs if r["request_id"] in self.od_ids]

        self.assertEqual(len(test_new_found), 3, f"Expected exactly 3 new department requests, found {len(test_new_found)}")
        self.assertEqual(len(test_od_found), 24, f"Expected 24 overdue requests, found {len(test_od_found)}")

        # Verify individual departments
        eng_new = [r for r in test_new_found if r["department"] == "Engineering"]
        tend_new = [r for r in test_new_found if r["department"] == "Tenders"]
        snt_new = [r for r in test_new_found if r["department"] == "S&T"]
        self.assertEqual(len(eng_new), 1, "Engineering must have 1 new request")
        self.assertEqual(len(tend_new), 1, "Tenders must have 1 new request")
        self.assertEqual(len(snt_new), 1, "S&T must have 1 new request")

        # -------------------------------------------------------------
        # STEP 2: Execute AI Classification on all 27 requests
        # -------------------------------------------------------------
        actionable_set = test_new_found + test_od_found
        self.assertEqual(len(actionable_set), 27, "Total actionable requests to classify must be 27")

        res = RequestClassificationEngine.classify_all_actionable_requests(actionable_set)
        self.assertEqual(len(res["classified_ids"]), 27, "All 27 requests must be classified")

        for rid in self.new_ids:
            self.assertIn(rid, res["classified_ids"], f"New request {rid} must be in classified_ids")

        # -------------------------------------------------------------
        # STEP 3: Verify State After Classification (New Requests = 0, Overdue = 0, Total = 0)
        # -------------------------------------------------------------
        new_after, overdue_after, total_new_after, total_overdue_after = fetch_controller_requests()
        test_new_after = [r for r in new_after if r["request_id"] in self.all_ids]
        test_od_after = [r for r in overdue_after if r["request_id"] in self.all_ids]

        self.assertEqual(len(test_new_after), 0, f"After classification, New Requests for test must be 0, found {len(test_new_after)}")
        self.assertEqual(len(test_od_after), 0, f"After classification, Overdue Requests for test must be 0, found {len(test_od_after)}")
        self.assertEqual(len(test_new_after) + len(test_od_after), 0, "Total must decrease to 0 after all 27 requests are classified")

        # -------------------------------------------------------------
        # STEP 4: Simulate Page Refresh / Reload (New = 0, Overdue = 0, Total = 0)
        # -------------------------------------------------------------
        new_refreshed, overdue_refreshed, _, _ = fetch_controller_requests()
        test_new_refreshed = [r for r in new_refreshed if r["request_id"] in self.all_ids]
        test_od_refreshed = [r for r in overdue_refreshed if r["request_id"] in self.all_ids]
        self.assertEqual(len(test_new_refreshed), 0, "On refresh, classified requests must NOT return to New Requests")
        self.assertEqual(len(test_od_refreshed), 0, "On refresh, Overdue count must remain 0")
        self.assertEqual(len(test_new_refreshed) + len(test_od_refreshed), 0, "On refresh, Total must remain 0")

        # -------------------------------------------------------------
        # STEP 5: Later, Engineering Actually Submits 1 Genuinely New Request
        # -------------------------------------------------------------
        self.later_req_id = f"ENG-LATER-{int(self.now.timestamp())}"
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
            VALUES (?, 'PORTAL', 'Engineering', 'USFD Rail Flaw Testing', 'P-Way Track', 'Section BZA-KI',
                    570.0, 573.0, 'Vijayawada–Kondapalli', 'DOWN Line', 'DOWN', ?, 40,
                    25, '03:00', ?, 'High', 'Urgent USFD rail flaw testing', 'SUBMITTED', 'PREVENTIVE')
        """, (
            self.later_req_id,
            self.now.strftime("%Y-%m-%d %H:%M:%S"),
            (self.now + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        # Check fetch results
        new_final, _, _, _ = fetch_controller_requests()
        later_found = [r for r in new_final if r["request_id"] == self.later_req_id]
        self.assertEqual(len(later_found), 1, "The genuinely newly submitted Engineering request must appear in New Requests")
        self.assertEqual(later_found[0]["department"], "Engineering")
        self.assertEqual(later_found[0]["status"], "NEW")

    def test_partial_classification_decreases_total_and_new_submission_increases_total(self):
        # 1. Start: 3 New + 24 Overdue = 27 Total
        new_reqs, overdue_reqs, _, _ = fetch_controller_requests()
        test_new = [r for r in new_reqs if r["request_id"] in self.new_ids]
        test_od = [r for r in overdue_reqs if r["request_id"] in self.od_ids]
        self.assertEqual(len(test_new), 3)
        self.assertEqual(len(test_od), 24)

        # 2. Classify ONLY the 3 New requests
        res = RequestClassificationEngine.classify_all_actionable_requests(test_new)
        self.assertEqual(len(res["classified_ids"]), 3)

        # 3. Verify: New drops to 0, Overdue stays 24, Total decreases from 27 to 24
        new_after, overdue_after, _, _ = fetch_controller_requests()
        test_new_after = [r for r in new_after if r["request_id"] in self.all_ids]
        test_od_after = [r for r in overdue_after if r["request_id"] in self.all_ids]
        self.assertEqual(len(test_new_after), 0, "New must decrease to 0")
        self.assertEqual(len(test_od_after), 24, "Overdue must remain 24")
        self.assertEqual(len(test_new_after) + len(test_od_after), 24, "Total must decrease from 27 to 24")

        # 4. Classify remaining 24 Overdue requests
        res2 = RequestClassificationEngine.classify_all_actionable_requests(test_od_after)
        self.assertEqual(len(res2["classified_ids"]), 24)

        # 5. Verify: Overdue drops to 0, Total decreases to 0
        new_after2, overdue_after2, _, _ = fetch_controller_requests()
        test_new_after2 = [r for r in new_after2 if r["request_id"] in self.all_ids]
        test_od_after2 = [r for r in overdue_after2 if r["request_id"] in self.all_ids]
        self.assertEqual(len(test_new_after2), 0)
        self.assertEqual(len(test_od_after2), 0, "Overdue must decrease to 0")
        self.assertEqual(len(test_new_after2) + len(test_od_after2), 0, "Total must decrease to 0")

        # 6. Submit 1 new request -> Total increases to 1
        self.later_req_id = f"ENG-LATER-PARTIAL-{int(self.now.timestamp())}"
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
            VALUES (?, 'PORTAL', 'Engineering', 'Track Renewal', 'P-Way Track', 'Section BZA-KI',
                    570.0, 574.0, 'Vijayawada–Kondapalli', 'DOWN Line', 'DOWN', ?, 45,
                    30, '02:00', ?, 'High', 'Track renewal', 'SUBMITTED', 'PREVENTIVE')
        """, (
            self.later_req_id,
            self.now.strftime("%Y-%m-%d %H:%M:%S"),
            (self.now + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        new_final, overdue_final, _, _ = fetch_controller_requests()
        test_new_final = [r for r in new_final if r["request_id"] == self.later_req_id]
        test_od_final = [r for r in overdue_final if r["request_id"] in self.all_ids]
        self.assertEqual(len(test_new_final), 1, "New must increase to 1")
        self.assertEqual(len(test_od_final), 0, "Overdue must stay 0")
        self.assertEqual(len(test_new_final) + len(test_od_final), 1, "Total must increase from 0 to 1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
