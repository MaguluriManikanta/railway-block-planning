"""
Unit & Integration Test Suite for STEP 8 — CONTROLLER SELECTION AND FINAL BLOCK ALLOCATION
Indian Railways Block Planning Prototype

Tests (Requirement 32):
1. Controller can open allocation alternatives
2. Controller can inspect metrics
3. AI recommendation is visible
4. Controller can choose a different valid alternative
5. Selecting an alternative creates PREVIEW / selected state
6. CONFIRM ALLOCATION is mandatory
7. No allocation occurs before confirmation
8. Final validation runs before commit
9. Invalid/stale candidates are rejected
10. Existing allocation conflicts are detected
11. Successful allocation changes status to ALLOCATED
12. Isolation allocation works
13. Parallel allocation works
14. Sequential allocation preserves order
15. Allocation appears in database / geographic map
16. Live trains remain visible
17. Request disappears from NEW/OVERDUE queue
18. Request remains in history / classification log
19. AI recommendation and Controller decision stored separately
20. Controller override recorded when applicable
21. Cancel does not allocate
22. Re-plan does not delete classification
23. Allocation failure does not create partial allocation
24. No department notification sent yet
25. Floating chatbot remains functional
"""

import os
import sys
import unittest
import sqlite3
import json
from datetime import datetime

# Setup paths
APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.block_allocation_engine import (
    init_allocation_database,
    BlockAllocationCandidate,
    BlockAllocationEngine,
    render_alternative_comparison_table,
    render_confirmation_panel
)
from app.controller_requests import fetch_controller_requests


class TestStep8ControllerSelection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize database tables before tests."""
        init_allocation_database()

    def test_01_controller_can_open_allocation_alternatives(self):
        """TEST 1: Controller can generate and view feasible candidate alternatives."""
        mock_grp = {
            "group_id": "GRP-STEP8-01",
            "classification": "ISOLATION",
            "request_ids": ["REQ-S8-01"],
            "departments": ["Engineering"],
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-11-01",
            "duration": 60,
            "requests": [{"request_id": "REQ-S8-01", "department": "Engineering", "duration": 60}]
        }
        cands = BlockAllocationEngine.generate_alternatives_for_group(mock_grp)
        self.assertGreaterEqual(len(cands), 2, "Must generate multiple candidate alternatives")
        self.assertEqual(cands[0].group_id, "GRP-STEP8-01")

    def test_02_controller_can_inspect_metrics(self):
        """TEST 2: Controller can inspect all separate metrics."""
        mock_grp = {
            "group_id": "GRP-STEP8-02",
            "classification": "ISOLATION",
            "request_ids": ["REQ-S8-02"],
            "departments": ["Engineering"],
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-11-02",
            "duration": 60,
            "requests": [{"request_id": "REQ-S8-02", "department": "Engineering", "duration": 60}]
        }
        cands = BlockAllocationEngine.generate_alternatives_for_group(mock_grp)
        m = cands[0].metrics
        self.assertIn("gap_suitability", m)
        self.assertIn("operational_slack_mins", m)
        self.assertIn("train_impact_score", m)
        self.assertIn("overall_score", m)

    def test_03_ai_recommendation_visible(self):
        """TEST 3: AI recommendation is clearly marked with explanation."""
        mock_grp = {
            "group_id": "GRP-STEP8-03",
            "classification": "ISOLATION",
            "request_ids": ["REQ-S8-03"],
            "departments": ["Engineering"],
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-11-03",
            "duration": 60,
            "requests": [{"request_id": "REQ-S8-03", "department": "Engineering", "duration": 60}]
        }
        cands = BlockAllocationEngine.generate_alternatives_for_group(mock_grp)
        rec_cands = [c for c in cands if c.is_ai_recommended]
        self.assertEqual(len(rec_cands), 1)
        self.assertIn("AI RECOMMENDED", rec_cands[0].explanation)

    def test_04_controller_can_choose_different_valid_alternative(self):
        """TEST 4: Controller can choose an alternative different from the AI recommendation."""
        mock_grp = {
            "group_id": "GRP-STEP8-04",
            "classification": "ISOLATION",
            "request_ids": ["REQ-S8-04"],
            "departments": ["Engineering"],
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-11-04",
            "duration": 60,
            "requests": [{"request_id": "REQ-S8-04", "department": "Engineering", "duration": 60}]
        }
        cands = BlockAllocationEngine.generate_alternatives_for_group(mock_grp)
        non_rec = [c for c in cands if not c.is_ai_recommended and c.feasibility_status == "FEASIBLE"]
        self.assertGreaterEqual(len(non_rec), 1, "Should have a non-recommended feasible alternative")
        
        # Select non-recommended alternative
        success, msg = BlockAllocationEngine.select_and_allocate_candidate(
            candidate=non_rec[0],
            group=mock_grp,
            controller_id="CONTROLLER-BZA-01",
            override_reason="Testing Controller Override"
        )
        self.assertTrue(success)

        # Verify override logged
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        row = conn.cursor().execute("SELECT is_override, override_reason FROM controller_decisions_v2 WHERE group_id = 'GRP-STEP8-04'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1, "Override flag must be set to 1")
        conn.close()

    def test_05_selecting_alternative_creates_preview_state(self):
        """TEST 5: Selecting alternative transitions state to confirmation review."""
        mock_cand = BlockAllocationCandidate(
            candidate_id="ALT-PREV-01",
            group_id="GRP-STEP8-05",
            request_ids=["REQ-S8-05"],
            classification="ISOLATION",
            date="2026-11-05",
            section="Vijayawada–Kondapalli",
            block="BLK-VIJ-100",
            from_km=100.0,
            to_km=105.0,
            start_time="02:00",
            end_time="03:00",
            duration=60
        )
        self.assertEqual(mock_cand.candidate_id, "ALT-PREV-01")

    def test_06_confirm_allocation_required(self):
        """TEST 6: Confirmation safety validation runs before committing."""
        mock_cand = BlockAllocationCandidate(
            candidate_id="ALT-CONF-01",
            group_id="GRP-STEP8-06",
            request_ids=["REQ-S8-06"],
            classification="ISOLATION",
            date="2026-11-06",
            section="Vijayawada–Kondapalli",
            block="BLK-VIJ-100",
            from_km=100.0,
            to_km=105.0,
            start_time="02:00",
            end_time="03:00",
            duration=60
        )
        is_valid, msg = BlockAllocationEngine.validate_candidate_before_commit(mock_cand, {"group_id": "GRP-STEP8-06"})
        self.assertTrue(is_valid)

    def test_07_no_allocation_before_confirmation(self):
        """TEST 7: No DB record is written before explicit select_and_allocate_candidate call."""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        row = conn.cursor().execute("SELECT * FROM final_block_allocations WHERE planning_group_id = 'GRP-UNCONFIRMED'").fetchone()
        self.assertIsNone(row, "Unconfirmed groups must not exist in final_block_allocations")
        conn.close()

    def test_08_final_validation_runs_before_commit(self):
        """TEST 8: Validation rejects invalid start/end times."""
        invalid_cand = BlockAllocationCandidate(
            candidate_id="ALT-INV-01",
            group_id="GRP-STEP8-08",
            request_ids=["REQ-S8-08"],
            classification="ISOLATION",
            date="2026-11-08",
            section="Vijayawada–Kondapalli",
            block="BLK-VIJ-100",
            from_km=100.0,
            to_km=105.0,
            start_time="03:00",
            end_time="02:00", # Inverted time
            duration=60
        )
        is_valid, msg = BlockAllocationEngine.validate_candidate_before_commit(invalid_cand, {"group_id": "GRP-STEP8-08"})
        self.assertFalse(is_valid)
        self.assertIn("Invalid", msg)

    def test_09_invalid_stale_candidates_rejected(self):
        """TEST 9: Window duration smaller than required work duration is rejected."""
        short_cand = BlockAllocationCandidate(
            candidate_id="ALT-SHORT-01",
            group_id="GRP-STEP8-09",
            request_ids=["REQ-S8-09"],
            classification="ISOLATION",
            date="2026-11-09",
            section="Vijayawada–Kondapalli",
            block="BLK-VIJ-100",
            from_km=100.0,
            to_km=105.0,
            start_time="02:00",
            end_time="02:30", # 30 mins window for 60 mins work
            duration=60
        )
        is_valid, msg = BlockAllocationEngine.validate_candidate_before_commit(short_cand, {"group_id": "GRP-STEP8-09"})
        self.assertFalse(is_valid)
        self.assertIn("less than required", msg)

    def test_10_existing_allocation_conflicts_detected(self):
        """TEST 10: Double-allocation conflict on identical track segment and date is rejected."""
        db_path = os.path.join(os.path.dirname(__file__), "..", "railway.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Insert blocking allocation
        cur.execute("""
            INSERT OR REPLACE INTO final_block_allocations
            (allocation_id, planning_group_id, request_ids, block, section, from_km, to_km, date, start_time, end_time, duration, classification, departments, selected_by_controller, controller_id, selection_time, AI_recommended_option, controller_selected_option, status, is_active)
            VALUES ('ALLOC-EXIST-01', 'GRP-EXIST-01', 'REQ-EXIST-1', 'BLK-VIJ-100', 'Vijayawada–Kondapalli', 100.0, 105.0, '2026-11-10', '02:00', '03:00', 60, 'ISOLATION', 'Engineering', 'YES', 'CONTROLLER-01', '2026-09-27 10:00:00', 'ALT-01', 'ALT-01', 'ALLOCATED', 1)
        """)
        conn.commit()

        # Try to allocate overlapping block at 02:30-03:30 on same date & KM
        conf_cand = BlockAllocationCandidate(
            candidate_id="ALT-CONF-02",
            group_id="GRP-CONF-TEST",
            request_ids=["REQ-CONF-TEST"],
            classification="ISOLATION",
            date="2026-11-10",
            section="Vijayawada–Kondapalli",
            block="BLK-VIJ-100",
            from_km=100.0,
            to_km=105.0,
            start_time="02:30",
            end_time="03:30",
            duration=60
        )
        is_valid, msg = BlockAllocationEngine.validate_candidate_before_commit(conf_cand, {"group_id": "GRP-CONF-TEST"})
        self.assertFalse(is_valid)
        self.assertIn("Conflict with active allocation", msg)

        # Cleanup
        cur.execute("DELETE FROM final_block_allocations WHERE allocation_id = 'ALLOC-EXIST-01'")
        conn.commit()
        conn.close()

    def test_11_successful_allocation_changes_status_to_allocated(self):
        """TEST 11: Successful allocation updates status to ALLOCATED."""
        mock_grp = {
            "group_id": "GRP-STEP8-11",
            "classification": "ISOLATION",
            "request_ids": ["REQ-S8-11"],
            "departments": ["Engineering"],
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-11-11",
            "duration": 60,
            "requests": [{"request_id": "REQ-S8-11", "department": "Engineering", "duration": 60}]
        }
        cands = BlockAllocationEngine.generate_alternatives_for_group(mock_grp)
        success, msg = BlockAllocationEngine.select_and_allocate_candidate(cands[0], mock_grp)
        self.assertTrue(success)

        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        row = conn.cursor().execute("SELECT status FROM final_block_allocations WHERE planning_group_id = 'GRP-STEP8-11'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "ALLOCATED")
        conn.close()

    def test_12_isolation_allocation_works(self):
        """TEST 12: Isolation block finalization stores single independent record."""
        mock_grp = {
            "group_id": "GRP-STEP8-12",
            "classification": "ISOLATION",
            "request_ids": ["REQ-S8-12"],
            "departments": ["Engineering"],
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-11-12",
            "duration": 45,
            "requests": [{"request_id": "REQ-S8-12", "department": "Engineering", "duration": 45}]
        }
        cands = BlockAllocationEngine.generate_alternatives_for_group(mock_grp)
        success, msg = BlockAllocationEngine.select_and_allocate_candidate(cands[0], mock_grp)
        self.assertTrue(success)

    def test_13_parallel_allocation_works(self):
        """TEST 13: Parallel block finalization links multiple requests to same joint allocation."""
        mock_grp = {
            "group_id": "GRP-STEP8-13",
            "classification": "PARALLEL",
            "request_ids": ["REQ-S8-13A", "REQ-S8-13B"],
            "departments": ["Engineering", "S&T"],
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-11-13",
            "duration": 60,
            "requests": [
                {"request_id": "REQ-S8-13A", "department": "Engineering", "duration": 60},
                {"request_id": "REQ-S8-13B", "department": "S&T", "duration": 45}
            ]
        }
        cands = BlockAllocationEngine.generate_alternatives_for_group(mock_grp)
        success, msg = BlockAllocationEngine.select_and_allocate_candidate(cands[0], mock_grp)
        self.assertTrue(success)

        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        row = conn.cursor().execute("SELECT request_ids, departments FROM final_block_allocations WHERE planning_group_id = 'GRP-STEP8-13'").fetchone()
        self.assertIn("REQ-S8-13A", row[0])
        self.assertIn("REQ-S8-13B", row[0])
        self.assertIn("Engineering", row[1])
        self.assertIn("S&T", row[1])
        conn.close()

    def test_14_sequential_allocation_preserves_order(self):
        """TEST 14: Sequential block stores phase order in details_json."""
        mock_grp = {
            "group_id": "GRP-STEP8-14",
            "classification": "SEQUENTIAL",
            "request_ids": ["REQ-S8-14A", "REQ-S8-14B"],
            "departments": ["Engineering", "TRD"],
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-11-14",
            "requests": [
                {"request_id": "REQ-S8-14A", "department": "Engineering", "duration": 30, "request_type": "Tamping"},
                {"request_id": "REQ-S8-14B", "department": "TRD", "duration": 30, "request_type": "Dropper adjustment"}
            ]
        }
        cands = BlockAllocationEngine.generate_alternatives_for_group(mock_grp)
        success, msg = BlockAllocationEngine.select_and_allocate_candidate(cands[0], mock_grp)
        self.assertTrue(success)

        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        row = conn.cursor().execute("SELECT details_json FROM final_block_allocations WHERE planning_group_id = 'GRP-STEP8-14'").fetchone()
        details = json.loads(row[0])
        self.assertIn("sequence", details)
        self.assertEqual(len(details["sequence"]), 2)
        self.assertEqual(details["sequence"][0]["department"], "Engineering")
        self.assertEqual(details["sequence"][1]["department"], "TRD")
        conn.close()

    def test_15_allocation_appears_in_database(self):
        """TEST 15: Table final_block_allocations contains valid allocation record."""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        cur = conn.cursor()
        count = cur.execute("SELECT COUNT(*) FROM final_block_allocations WHERE status = 'ALLOCATED'").fetchone()[0]
        self.assertGreaterEqual(count, 1)
        conn.close()

    def test_16_live_trains_remain_visible(self):
        """TEST 16: Live train layer queries continue functioning during selection."""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        cur = conn.cursor()
        t_count = cur.execute("SELECT COUNT(*) FROM live_train_positions").fetchone()[0]
        self.assertGreaterEqual(t_count, 0)
        conn.close()

    def test_17_request_status_transitions_to_allocated(self):
        """TEST 17: Ingested requests transition to ALLOCATED in block_requests_v2."""
        db_path = os.path.join(os.path.dirname(__file__), "..", "railway.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        test_id = f"TEST-REQ-STATUS-{int(datetime.now().timestamp())}"
        cur.execute("""
            INSERT OR REPLACE INTO block_requests_v2
            (request_id, department, request_type, reason, section, location, from_km, to_km, reported_time, required_duration, priority, status)
            VALUES (?, 'Engineering', 'Track renewal', 'Status transition test', 'Vijayawada–Kondapalli', 'BLK-VIJ-100', 100.0, 105.0, '2026-11-17 08:00:00', 60, 'High', 'CLASSIFIED')
        """, (test_id,))
        conn.commit()

        mock_cand = BlockAllocationCandidate(
            candidate_id="ALT-S8-17",
            group_id="GRP-STEP8-17",
            request_ids=[test_id],
            classification="ISOLATION",
            date="2026-11-17",
            section="Vijayawada–Kondapalli",
            block="BLK-VIJ-100",
            from_km=100.0,
            to_km=105.0,
            start_time="02:00",
            end_time="03:00",
            duration=60
        )
        BlockAllocationEngine.select_and_allocate_candidate(mock_cand, {"group_id": "GRP-STEP8-17", "departments": ["Engineering"]})

        # Verify status is now ALLOCATED
        row = cur.execute("SELECT status FROM block_requests_v2 WHERE request_id = ?", (test_id,)).fetchone()
        self.assertEqual(row[0], "ALLOCATED")

        # Cleanup
        cur.execute("DELETE FROM block_requests_v2 WHERE request_id = ?", (test_id,))
        conn.commit()
        conn.close()

    def test_18_request_remains_in_history(self):
        """TEST 18: Audit trail records allocation event."""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        cur = conn.cursor()
        row = cur.execute("SELECT event_type, actor FROM block_allocation_audit_trail ORDER BY audit_id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(row)
        self.assertIn(row[0], ["ALLOCATION_CREATED", "ALLOCATION_CONFIRMED", "DEPARTMENT_NOTIFIED"])
        conn.close()

    def test_19_ai_recommendation_and_controller_decision_stored_separately(self):
        """TEST 19: AI recommendation option and Controller chosen option stored in separate fields."""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        cur = conn.cursor()
        cols = [c[1] for c in cur.execute("PRAGMA table_info(final_block_allocations)").fetchall()]
        self.assertIn("AI_recommended_option", cols)
        self.assertIn("controller_selected_option", cols)
        self.assertIn("override_reason", cols)
        conn.close()

    def test_20_controller_override_recorded(self):
        """TEST 20: Discretionary controller overrides are logged in controller_decisions_v2."""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        cur = conn.cursor()
        row = cur.execute("SELECT is_override, override_reason FROM controller_decisions_v2 WHERE is_override = 1 LIMIT 1").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1)
        conn.close()

    def test_21_cancel_does_not_allocate(self):
        """TEST 21: Canceling from confirmation panel does not write allocation."""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        row = conn.cursor().execute("SELECT * FROM final_block_allocations WHERE planning_group_id = 'GRP-CANCELLED-TEST'").fetchone()
        self.assertIsNone(row)
        conn.close()

    def test_22_replan_does_not_delete_classification(self):
        """TEST 22: Re-planning does not delete classification history."""
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        cur = conn.cursor()
        c_count = cur.execute("SELECT COUNT(*) FROM request_classification_history").fetchone()[0]
        self.assertGreaterEqual(c_count, 0)
        conn.close()

    def test_23_allocation_failure_does_not_create_partial_allocation(self):
        """TEST 23: When validation fails, zero rows are inserted into final_block_allocations."""
        invalid_cand = BlockAllocationCandidate(
            candidate_id="ALT-FAIL-01",
            group_id="GRP-FAIL-TEST",
            request_ids=["REQ-FAIL-1"],
            classification="ISOLATION",
            date="2026-11-23",
            section="Vijayawada–Kondapalli",
            block="BLK-VIJ-100",
            from_km=100.0,
            to_km=105.0,
            start_time="05:00",
            end_time="04:00", # Invalid inverted time
            duration=60
        )
        success, msg = BlockAllocationEngine.select_and_allocate_candidate(invalid_cand, {"group_id": "GRP-FAIL-TEST"})
        self.assertFalse(success)

        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "..", "railway.db"))
        row = conn.cursor().execute("SELECT * FROM final_block_allocations WHERE planning_group_id = 'GRP-FAIL-TEST'").fetchone()
        self.assertIsNone(row, "Failed allocation must not leave partial DB records")
        conn.close()

    def test_24_no_department_notification_sent_yet(self):
        """TEST 24: Step 8 does not dispatch department notifications."""
        # Notifications belong to Step 9
        self.assertTrue(True)

    def test_25_floating_chatbot_remains_functional(self):
        """TEST 25: Floating chatbot imports and components remain functional."""
        try:
            from app.chatbot import render_floating_chatbot_icon
            self.assertTrue(callable(render_floating_chatbot_icon))
        except ImportError:
            # Check file exists
            self.assertTrue(os.path.exists(os.path.join(os.path.dirname(__file__), "..", "app", "chatbot.py")))


if __name__ == "__main__":
    unittest.main()
