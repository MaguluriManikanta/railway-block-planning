"""
Automated Test Suite for STEP 5 — CONTROLLER REQUESTS POPUP & NEW/OVERDUE REQUESTS
Tests all 25 explicit test requirements from the Step 5 specification.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
        sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass

from app.controller_requests import (
    parse_request_record,
    parse_deadline_datetime,
    format_overdue_duration,
    normalize_department_name,
    fetch_controller_requests,
    get_pending_request_counts,
    get_demo_requests_dataset
)
from app.controller_map import ControllerMap, BaseRailwayLayer, AllocatedBlockLayer, LiveTrainLayer


class TestStep5ControllerRequests(unittest.TestCase):
    """25 Test Cases for Step 5 Controller Requests & New/Overdue Processing."""

    @classmethod
    def setUpClass(cls):
        cls.test_ids = ["STEP5-ENG-01", "STEP5-OHE-01", "STEP5-SNT-01", "STEP5-ENG-OD", "STEP5-SNT-OD"]
        now = datetime.now()
        conn = sqlite3.connect(os.path.join(PROJECT_ROOT, "railway.db"), timeout=10.0)
        cur = conn.cursor()
        test_rows = [
            ("STEP5-ENG-01", "TEST", "Engineering", "Track Tamping", "Track", "BZA-KI", 570.0, 575.0, "Vijayawada–Kondapalli", "DOWN Line", "DOWN", (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"), 30, 20, "02:00", (now + timedelta(hours=20)).strftime("%Y-%m-%d %H:%M:%S"), "High", "Test track tamping", "NEW", "PREVENTIVE"),
            ("STEP5-OHE-01", "TEST", "OHE/Traction", "Catenary Inspection", "OHE", "BZA-KI", 572.0, 576.0, "Vijayawada–Kondapalli", "DOWN Line", "DOWN", (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"), 45, 30, "02:00", (now + timedelta(hours=18)).strftime("%Y-%m-%d %H:%M:%S"), "High", "Test catenary inspection", "NEW", "PREVENTIVE"),
            ("STEP5-SNT-01", "TEST", "S&T", "Point Machine Calibration", "Signal", "BZA-KI", 571.0, 574.0, "Vijayawada–Kondapalli", "DOWN Line", "DOWN", (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"), 30, 20, "02:00", (now + timedelta(hours=22)).strftime("%Y-%m-%d %H:%M:%S"), "Medium", "Test point machine calibration", "NEW", "PREVENTIVE"),
            ("STEP5-ENG-OD", "TEST", "Engineering", "Track De-stressing", "Track", "BZA-KI", 570.0, 573.0, "Vijayawada–Kondapalli", "DOWN Line", "DOWN", (now - timedelta(hours=40)).strftime("%Y-%m-%d %H:%M:%S"), 45, 30, "02:00", (now - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S"), "High", "Test track de-stressing overdue", "OVERDUE", "CORRECTIVE"),
            ("STEP5-SNT-OD", "TEST", "S&T", "Axle Counter Maintenance", "Signal", "BZA-KI", 572.0, 575.0, "Vijayawada–Kondapalli", "DOWN Line", "DOWN", (now - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S"), 40, 25, "02:00", (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"), "High", "Test axle counter overdue", "OVERDUE", "CORRECTIVE")
        ]
        cur.executemany("""
            INSERT OR REPLACE INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, priority, reason, status, archetype)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, test_rows)
        cur.executemany("DELETE FROM request_classification_history WHERE request_ids LIKE ?", [(f"%{tid}%",) for tid in cls.test_ids])
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        conn = sqlite3.connect(os.path.join(PROJECT_ROOT, "railway.db"), timeout=10.0)
        cur = conn.cursor()
        cur.executemany("DELETE FROM block_requests_v2 WHERE request_id = ?", [(tid,) for tid in cls.test_ids])
        conn.commit()
        conn.close()

    def setUp(self):
        self.now = datetime.now()

    # --- TEST 1: Controller Requests Module Loads ---
    def test_01_controller_requests_module_loads(self):
        self.assertTrue(callable(fetch_controller_requests))
        self.assertTrue(callable(get_pending_request_counts))
        self.assertTrue(callable(parse_request_record))

    # --- TEST 2: REQUESTS Button & Counts ---
    def test_02_requests_badge_count_accurate(self):
        counts = get_pending_request_counts()
        self.assertIn("total", counts)
        self.assertIn("new", counts)
        self.assertIn("overdue", counts)
        self.assertEqual(counts["total"], counts["new"] + counts["overdue"])
        self.assertGreater(counts["total"], 0, "Should have pending requests (DB or demo)")

    # --- TEST 3: Fetching Requests Returns Valid Structure ---
    def test_03_fetch_controller_requests_structure(self):
        new_reqs, overdue_reqs, n_cnt, o_cnt = fetch_controller_requests()
        self.assertIsInstance(new_reqs, list)
        self.assertIsInstance(overdue_reqs, list)
        self.assertEqual(len(new_reqs), n_cnt)
        self.assertEqual(len(overdue_reqs), o_cnt)

    # --- TEST 4: NEW Requests Appear ---
    def test_04_new_requests_appear(self):
        new_reqs, _, _, _ = fetch_controller_requests(category_filter="NEW REQUESTS")
        self.assertGreater(len(new_reqs), 0, "Should have NEW requests")
        for nr in new_reqs:
            self.assertFalse(nr["is_overdue"], "NEW request must not be flagged as overdue")
            self.assertEqual(nr["status"], "NEW")

    # --- TEST 5: OVERDUE Requests Appear Separately ---
    def test_05_overdue_requests_appear_separately(self):
        _, overdue_reqs, _, _ = fetch_controller_requests(category_filter="OVERDUE REQUESTS")
        self.assertGreater(len(overdue_reqs), 0, "Should have OVERDUE requests")
        for orq in overdue_reqs:
            self.assertTrue(orq["is_overdue"], "OVERDUE request must be flagged as overdue")
            self.assertNotEqual(orq["overdue_duration"], "", "OVERDUE request must have overdue duration string")

    # --- TEST 6: Engineering Requests Supported ---
    def test_06_engineering_requests_appear(self):
        new_reqs, overdue_reqs, _, _ = fetch_controller_requests(dept_filter="Engineering")
        all_eng = new_reqs + overdue_reqs
        self.assertGreater(len(all_eng), 0, "Should have Engineering requests")
        for r in all_eng:
            self.assertEqual(r["department"], "Engineering")

    # --- TEST 7: OHE/Traction Requests Supported ---
    def test_07_ohe_traction_requests_appear(self):
        new_reqs, overdue_reqs, _, _ = fetch_controller_requests(dept_filter="OHE/Traction")
        all_ohe = new_reqs + overdue_reqs
        self.assertGreater(len(all_ohe), 0, "Should have OHE/Traction requests")
        for r in all_ohe:
            self.assertEqual(r["department"], "OHE/Traction")

    # --- TEST 8: S&T Requests Supported ---
    def test_08_snt_requests_appear(self):
        new_reqs, overdue_reqs, _, _ = fetch_controller_requests(dept_filter="S&T")
        all_snt = new_reqs + overdue_reqs
        self.assertGreater(len(all_snt), 0, "Should have S&T requests")
        for r in all_snt:
            self.assertEqual(r["department"], "S&T")

    # --- TEST 9: Request Details Model Fields ---
    def test_09_request_details_contains_all_fields(self):
        new_reqs, overdue_reqs, _, _ = fetch_controller_requests()
        sample = (new_reqs + overdue_reqs)[0]
        expected_fields = [
            "request_id", "department", "request_type", "description", "section",
            "block", "from_km", "to_km", "date", "duration", "priority", "urgency",
            "submitted_at", "required_by", "status", "is_overdue", "source"
        ]
        for f in expected_fields:
            self.assertIn(f, sample, f"Field '{f}' missing from parsed request model")

    # --- TEST 10: Request ID Preserved & Correct ---
    def test_10_request_id_preserved(self):
        demo_recs = get_demo_requests_dataset()
        for d in demo_recs:
            parsed = parse_request_record(d)
            self.assertEqual(parsed["request_id"], d["request_id"])

    # --- TEST 11: Section & KM Coordinates Correct ---
    def test_11_section_and_km_correct(self):
        raw = {
            "request_id": "REQ-TEST-KM",
            "department": "Engineering",
            "section": "Vijayawada–Kondapalli",
            "from_km": 570.0,
            "to_km": 575.0,
            "required_duration": 30
        }
        parsed = parse_request_record(raw)
        self.assertEqual(parsed["section"], "Vijayawada–Kondapalli")
        self.assertEqual(parsed["from_km"], 570.0)
        self.assertEqual(parsed["to_km"], 575.0)

    # --- TEST 12: Date & Time Calculation ---
    def test_12_date_and_time_calculation(self):
        dt_str = "2026-09-27 10:00:00"
        raw = {
            "request_id": "REQ-TIME-01",
            "department": "Engineering",
            "reported_time": dt_str,
            "deadline": "2026-09-28 18:00:00"
        }
        parsed = parse_request_record(raw, current_time=datetime(2026, 9, 27, 12, 0, 0))
        self.assertEqual(parsed["submitted_at"], dt_str)
        self.assertEqual(parsed["required_by"], "2026-09-28 18:00")
        self.assertFalse(parsed["is_overdue"])

    # --- TEST 13: Priority and Urgency Normalization ---
    def test_13_priority_and_urgency(self):
        raw_crit = {"request_id": "R1", "priority": "Critical"}
        parsed_crit = parse_request_record(raw_crit)
        self.assertEqual(parsed_crit["priority"], "Critical")
        self.assertEqual(parsed_crit["urgency"], "HIGH")

        raw_low = {"request_id": "R2", "priority": "Low"}
        parsed_low = parse_request_record(raw_low)
        self.assertEqual(parsed_low["priority"], "Low")
        self.assertEqual(parsed_low["urgency"], "LOW")

    # --- TEST 14: Overdue Duration Calculation & Formatting ---
    def test_14_overdue_duration_format(self):
        # 16 hours 32 minutes overdue
        sec_16h = 16 * 3600 + 32 * 60
        self.assertEqual(format_overdue_duration(sec_16h), "16h 32m")

        # 2 hours 35 minutes overdue
        sec_2h = 2 * 3600 + 35 * 60
        self.assertEqual(format_overdue_duration(sec_2h), "2h 35m")

        # 1 day 4 hours 12 minutes overdue
        sec_1d = 1 * 86400 + 4 * 3600 + 12 * 60
        self.assertEqual(format_overdue_duration(sec_1d), "1d 4h 12m")

        # 45 minutes overdue
        sec_45m = 45 * 60
        self.assertEqual(format_overdue_duration(sec_45m), "45m")

    # --- TEST 15: Request Count Accuracy ---
    def test_15_request_count_accuracy(self):
        new_reqs, overdue_reqs, n_cnt, o_cnt = fetch_controller_requests()
        self.assertEqual(len(new_reqs), n_cnt)
        self.assertEqual(len(overdue_reqs), o_cnt)
        counts = get_pending_request_counts()
        self.assertEqual(counts["new"], n_cnt)
        self.assertEqual(counts["overdue"], o_cnt)
        self.assertEqual(counts["total"], n_cnt + o_cnt)

    # --- TEST 16: Underlying Map Intact ---
    def test_16_underlying_map_intact(self):
        map_html = ControllerMap.generate_html(division_name="Vijayawada Division (BZA)")
        self.assertIn("leaflet", map_html.lower())
        self.assertIn("trainHudCard", map_html)

    # --- TEST 17: Allocated Blocks Layer Visible Underneath ---
    def test_17_allocated_blocks_visible_underneath(self):
        map_html = ControllerMap.generate_html(division_name="Vijayawada Division (BZA)")
        self.assertIn("Allocated Maintenance Blocks", map_html)

    # --- TEST 18: Live Trains Layer Visible Underneath ---
    def test_18_live_trains_visible_underneath(self):
        map_html = ControllerMap.generate_html(division_name="Vijayawada Division (BZA)")
        self.assertIn("Live Moving Trains", map_html)

    # --- TEST 19: Floating Chatbot Not inside Requests Popup ---
    def test_19_floating_chatbot_preserved(self):
        # Verify controller_requests does not contain chatbot rendering code
        import app.controller_requests as cr
        self.assertFalse(hasattr(cr, "render_chatbot_panel"))
        self.assertFalse(hasattr(cr, "open_chatbot_in_dialog"))

    # --- TEST 20: No Manual Dependency or Isolation Fields ---
    def test_20_no_manual_dependency_or_isolation_fields(self):
        demo_recs = get_demo_requests_dataset()
        for r in demo_recs:
            parsed = parse_request_record(r)
            # Ensure the request cards / details do not expose dependency or isolation for manual entry
            self.assertNotIn("manual_dependency", parsed)
            self.assertNotIn("manual_isolation", parsed)

    # --- TEST 21: No Requests Deleted When Processing ---
    def test_21_no_requests_deleted(self):
        db_path = os.path.join(PROJECT_ROOT, "railway.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM block_requests_v2")
            count_before = cur.fetchone()[0]
            conn.close()
            # Fetch requests multiple times
            fetch_controller_requests()
            get_pending_request_counts()
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM block_requests_v2")
            count_after = cur.fetchone()[0]
            conn.close()
            self.assertEqual(count_before, count_after, "Request counts in DB must never decrease")

    # --- TEST 22: Department Request Submission Schema Matches ---
    def test_22_department_request_submission_schema_matches(self):
        # Verify block_requests_v2 schema supports required fields
        db_path = os.path.join(PROJECT_ROOT, "railway.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(block_requests_v2)")
            col_names = [r[1] for r in cur.fetchall()]
            conn.close()
            for required_col in ["request_id", "department", "request_type", "section", "from_km", "to_km", "deadline", "status"]:
                self.assertIn(required_col, col_names, f"Column '{required_col}' must exist in block_requests_v2")

    # --- TEST 23: No Duplicate Database Created ---
    def test_23_no_duplicate_database(self):
        # Ensure only standard railway.db is used
        import app.controller_requests as cr
        self.assertTrue(cr.DB_PATH.endswith("railway.db"))

    # --- TEST 24: Sorting Logic Verified ---
    def test_24_sorting_logic_verified(self):
        # Priority sort
        new_pri, overdue_pri, _, _ = fetch_controller_requests(sort_by="PRIORITY")
        pri_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        if len(new_pri) >= 2:
            self.assertLessEqual(pri_order.get(new_pri[0]["priority"], 4), pri_order.get(new_pri[-1]["priority"], 4))

        # Default sort (overdue by longest overdue)
        _, overdue_def, _, _ = fetch_controller_requests(sort_by="DEFAULT")
        if len(overdue_def) >= 2:
            self.assertGreaterEqual(overdue_def[0]["overdue_seconds"], overdue_def[-1]["overdue_seconds"])

    # --- TEST 25: Terminal Statuses Excluded from Count ---
    def test_25_terminal_statuses_excluded_from_pending_count(self):
        now = datetime.now()
        terminal_statuses = ["CLASSIFIED", "ALLOCATED", "ACTIVE", "COMPLETED", "CANCELLED"]
        for st in terminal_statuses:
            raw = {
                "request_id": f"REQ-TERM-{st}",
                "department": "Engineering",
                "status": st,
                "deadline": (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
            }
            parsed = parse_request_record(raw, current_time=now)
            # Terminal requests must not be marked as actionable overdue in Step 5
            self.assertFalse(parsed["is_overdue"], f"Terminal status '{st}' must not be marked overdue")


if __name__ == "__main__":
    unittest.main()
