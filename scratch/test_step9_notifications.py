"""
Automated Test Suite for STEP 9 — Department Notification & Live Allocation Synchronization
Tests:
1. Successful Controller allocation generates ALLOCATION_CONFIRMED event.
2. Correct department is identified directly from request records.
3. Only affected departments receive notification.
4. Isolation notification works (single department only).
5. Parallel notification works (both/all participating departments notified with joint block info).
6. Sequential notification works (all affected departments notified).
7. Execution order is displayed correctly with phased steps and time windows.
8. Department notification contains correct block information (Section, Block, KM, Date, Times).
9. Notification count updates dynamically.
10. Unread/read state transitions work.
11. Duplicate notification is prevented.
12. Failed notification can be retried without duplicate allocation.
13. Request status changes to ALLOCATED in block_requests_v2.
14. Allocation appears on Controller map Layer 1.
15. Allocation appears on relevant department view / Approved Blocks.
16. Live train layer remains active and uninterrupted.
17. Existing allocations remain unchanged.
18. All pages reference the exact same allocation ID.
19. Authorization filtering prevents cross-department leaks.
20. Floating chatbot remains functional.
21. No notification occurs before Controller confirmation.
22. No request is deleted (non-destructive persistence).
23. Explicit acknowledgement sets status to ACKNOWLEDGED with audit trail.
24. Audit trail records ALLOCATION_CONFIRMED and DEPARTMENT_NOTIFIED events.
"""

import os
import sys
import unittest
import sqlite3
import json
import tempfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(BASE_DIR, "app")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
for p in [APP_DIR, SCRIPTS_DIR, BASE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from app.department_notifications import (
    DepartmentNotificationEngine,
    format_standard_department_name,
    record_notification_audit_event,
    init_notifications_db
)
from app.block_allocation_engine import (
    BlockAllocationEngine,
    BlockAllocationCandidate,
    init_allocation_database
)
from app.controller_map import fetch_allocated_blocks


class TestStep9DepartmentNotifications(unittest.TestCase):

    def setUp(self):
        """Create a dedicated isolated SQLite database for each test run."""
        self.temp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db_file.name
        self.temp_db_file.close()

        # Initialize schema
        init_notifications_db(self.db_path)
        init_allocation_database(self.db_path)

        # Seed sample requests in block_requests_v2
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS block_requests_v2 (
                request_id TEXT PRIMARY KEY,
                source TEXT,
                department TEXT,
                request_type TEXT,
                asset_type TEXT,
                location TEXT,
                from_km REAL,
                to_km REAL,
                section TEXT,
                line TEXT,
                direction TEXT,
                reported_time TEXT,
                required_duration INTEGER,
                minimum_duration INTEGER,
                preferred_start TEXT,
                deadline TEXT,
                dependency TEXT,
                isolation_required INTEGER,
                required_resource TEXT,
                priority TEXT,
                reason TEXT,
                status TEXT,
                archetype TEXT
            )
        """)

        # Insert test requests
        test_requests = [
            ("ENG-104", "ENG", "Engineering", "Deep Track Screening", "BCM-01", "KM 570-575", 570.0, 575.0, "BZA-VSKP", "UP", "UP", "2026-09-27 08:00:00", 60, 45, "10:00", "2026-09-28", "None", 1, "Crew", "High", "Track ballast renewal", "NEW", "PREVENTIVE"),
            ("SNT-301", "SNT", "S&T", "Track Circuit Replacement", "TC-Rig", "KM 570-575", 570.0, 575.0, "BZA-VSKP", "UP", "UP", "2026-09-27 08:00:00", 45, 30, "10:00", "2026-09-28", "Engineering", 1, "Crew", "High", "Joint bond renewal", "NEW", "PREVENTIVE"),
            ("TRD-202", "TRD", "OHE/Traction", "OHE Catenary Wire Adjustment", "Tower-Wagon", "KM 570-575", 570.0, 575.0, "BZA-VSKP", "UP", "UP", "2026-09-27 08:00:00", 45, 30, "10:30", "2026-09-28", "Power Block", 1, "Crew", "High", "Dropper replacement", "NEW", "PREVENTIVE"),
            ("ENG-999", "ENG", "Engineering", "Isolated Emergency Rail Weld", "Welding-Kit", "KM 410-412", 410.0, 412.0, "BZA-GDR", "DN", "DN", "2026-09-27 08:00:00", 90, 60, "02:00", "2026-09-28", "None", 1, "Crew", "Critical", "Fracture repair", "NEW", "EMERGENCY")
        ]
        for r in test_requests:
            cur.execute("""
                INSERT INTO block_requests_v2
                (request_id, source, department, request_type, asset_type, location, from_km, to_km, section, line, direction, reported_time, required_duration, minimum_duration, preferred_start, deadline, dependency, isolation_required, required_resource, priority, reason, status, archetype)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, r)

        conn.commit()
        conn.close()

    def tearDown(self):
        """Clean up the temporary SQLite database file."""
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception:
                pass

    # -------------------------------------------------------------------------
    # TEST 1: ALLOCATION_CONFIRMED Event Generation
    # -------------------------------------------------------------------------
    def test_01_allocation_confirmed_event_generation(self):
        """Test that Controller confirmation produces a canonical ALLOCATION_CONFIRMED event."""
        group = {
            "group_id": "GRP-TEST-01",
            "request_ids": ["ENG-104", "SNT-301"],
            "departments": ["Engineering", "S&T"],
            "classification": "PARALLEL",
            "section": "BZA-VSKP",
            "block": "B-04",
            "from_km": 570.0,
            "to_km": 575.0,
            "date": "2026-09-27"
        }
        cand = BlockAllocationCandidate(
            candidate_id="ALT-PAR-01",
            group_id="GRP-TEST-01",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:30",
            end_time="11:30",
            duration=60,
            classification="PARALLEL",
            feasibility_status="FEASIBLE",
            request_ids=["ENG-104", "SNT-301"]
        )
        event = DepartmentNotificationEngine.create_allocation_confirmed_event(
            {"allocation_id": "ALLOC-20260927-T01"}, group, cand, "CONTROLLER-BZA-01"
        )
        self.assertEqual(event["event_type"], "ALLOCATION_CONFIRMED")
        self.assertEqual(event["allocation_id"], "ALLOC-20260927-T01")
        self.assertEqual(event["status"], "ALLOCATED")
        self.assertIn("Engineering", event["departments"])
        self.assertIn("S&T", event["departments"])

    # -------------------------------------------------------------------------
    # TEST 2: Affected Department Identification from Database
    # -------------------------------------------------------------------------
    def test_02_identify_affected_departments(self):
        """Test affected departments are correctly extracted from database request records."""
        affected = DepartmentNotificationEngine.identify_affected_departments(["ENG-104", "SNT-301"], db_path=self.db_path)
        self.assertEqual(len(affected), 2)
        depts = [r["standard_department"] for r in affected]
        self.assertIn("Engineering", depts)
        self.assertIn("S&T", depts)

    # -------------------------------------------------------------------------
    # TEST 3 & 4: Isolation Notification (Single Department Only)
    # -------------------------------------------------------------------------
    def test_03_isolation_notification(self):
        """Test ISOLATION group notifies strictly the single requesting department."""
        group = {
            "group_id": "GRP-ISO-01",
            "request_ids": ["ENG-999"],
            "departments": ["Engineering"],
            "classification": "ISOLATION",
            "section": "BZA-GDR",
            "block": "B-01",
            "from_km": 410.0,
            "to_km": 412.0,
            "date": "2026-09-27"
        }
        cand = BlockAllocationCandidate(
            candidate_id="ALT-ISO-01",
            group_id="GRP-ISO-01",
            date="2026-09-27",
            section="BZA-GDR",
            block="B-01",
            from_km=410.0,
            to_km=412.0,
            start_time="02:00",
            end_time="03:30",
            duration=90,
            classification="ISOLATION",
            feasibility_status="FEASIBLE",
            request_ids=["ENG-999"]
        )
        res = DepartmentNotificationEngine.dispatch_allocation_notifications(
            allocation_id="ALLOC-ISO-001",
            group=group,
            candidate=cand,
            db_path=self.db_path
        )
        self.assertTrue(res["success"])
        self.assertEqual(len(res["dispatched"]), 1)
        self.assertEqual(res["dispatched"][0]["department"], "Engineering")

        # Verify OHE and S&T receive NO notifications
        eng_notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        ohe_notifs = DepartmentNotificationEngine.get_department_notifications("OHE/Traction", db_path=self.db_path)
        st_notifs = DepartmentNotificationEngine.get_department_notifications("S&T", db_path=self.db_path)

        self.assertEqual(len(eng_notifs), 1)
        self.assertEqual(len(ohe_notifs), 0)
        self.assertEqual(len(st_notifs), 0)

    # -------------------------------------------------------------------------
    # TEST 5: Parallel Notification (Joint Block with Peers)
    # -------------------------------------------------------------------------
    def test_05_parallel_notification_joint_block(self):
        """Test PARALLEL group notifies all participating departments with joint block reference."""
        group = {
            "group_id": "GRP-PAR-01",
            "request_ids": ["ENG-104", "SNT-301"],
            "departments": ["Engineering", "S&T"],
            "classification": "PARALLEL",
            "section": "BZA-VSKP",
            "block": "B-04",
            "from_km": 570.0,
            "to_km": 575.0,
            "date": "2026-09-27"
        }
        cand = BlockAllocationCandidate(
            candidate_id="ALT-PAR-01",
            group_id="GRP-PAR-01",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:30",
            end_time="11:30",
            duration=60,
            classification="PARALLEL",
            feasibility_status="FEASIBLE",
            request_ids=["ENG-104", "SNT-301"]
        )
        res = DepartmentNotificationEngine.dispatch_allocation_notifications(
            allocation_id="ALLOC-PAR-001",
            group=group,
            candidate=cand,
            db_path=self.db_path
        )
        self.assertTrue(res["success"])
        self.assertEqual(len(res["dispatched"]), 2)

        eng_notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        st_notifs = DepartmentNotificationEngine.get_department_notifications("S&T", db_path=self.db_path)

        self.assertEqual(len(eng_notifs), 1)
        self.assertEqual(len(st_notifs), 1)

        # Check joint peer mention
        self.assertIn("S&T", eng_notifs[0]["message"])
        self.assertIn("Engineering", st_notifs[0]["message"])
        self.assertEqual(eng_notifs[0]["allocation_id"], "ALLOC-PAR-001")
        self.assertEqual(st_notifs[0]["allocation_id"], "ALLOC-PAR-001")

    # -------------------------------------------------------------------------
    # TEST 6 & 7: Sequential Notification with Execution Order
    # -------------------------------------------------------------------------
    def test_06_sequential_notification_execution_order(self):
        """Test SEQUENTIAL group notifies all departments with structured execution sequence."""
        group = {
            "group_id": "GRP-SEQ-01",
            "request_ids": ["ENG-104", "TRD-202", "SNT-301"],
            "departments": ["Engineering", "OHE/Traction", "S&T"],
            "classification": "SEQUENTIAL",
            "section": "BZA-VSKP",
            "block": "B-04",
            "from_km": 570.0,
            "to_km": 575.0,
            "date": "2026-09-27"
        }
        sequence_steps = [
            {"step": 1, "department": "Engineering", "activity": "Deep Screening", "start_time": "10:00", "end_time": "11:00", "duration": 60},
            {"step": 2, "department": "OHE/Traction", "activity": "Catenary Adjustment", "start_time": "11:00", "end_time": "11:45", "duration": 45},
            {"step": 3, "department": "S&T", "activity": "Track Circuit Bonding", "start_time": "11:45", "end_time": "12:30", "duration": 45}
        ]
        cand = BlockAllocationCandidate(
            candidate_id="ALT-SEQ-01",
            group_id="GRP-SEQ-01",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:00",
            end_time="12:30",
            duration=150,
            classification="SEQUENTIAL",
            feasibility_status="FEASIBLE",
            request_ids=["ENG-104", "TRD-202", "SNT-301"],
            sequence=sequence_steps
        )
        res = DepartmentNotificationEngine.dispatch_allocation_notifications(
            allocation_id="ALLOC-SEQ-001",
            group=group,
            candidate=cand,
            db_path=self.db_path
        )
        self.assertTrue(res["success"])
        self.assertEqual(len(res["dispatched"]), 3)

        # Verify each department received the sequence breakdown with phase pointer
        eng_notif = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)[0]
        trd_notif = DepartmentNotificationEngine.get_department_notifications("OHE/Traction", db_path=self.db_path)[0]
        st_notif = DepartmentNotificationEngine.get_department_notifications("S&T", db_path=self.db_path)[0]

        self.assertIn("Execution Order", eng_notif["message"])
        self.assertIn("Step 1: 10:00–11:00", eng_notif["message"])
        self.assertIn("YOUR PHASE", eng_notif["message"])
        self.assertIn("Step 2: 11:00–11:45", trd_notif["message"])
        self.assertIn("Step 3: 11:45–12:30", st_notif["message"])

    # -------------------------------------------------------------------------
    # TEST 8: Notification Content Completeness
    # -------------------------------------------------------------------------
    def test_08_notification_content_completeness(self):
        """Test department notification contains all mandatory fields."""
        group = {
            "group_id": "GRP-ISO-02",
            "request_ids": ["ENG-999"],
            "departments": ["Engineering"],
            "classification": "ISOLATION",
            "section": "BZA-GDR",
            "block": "B-01",
            "from_km": 410.0,
            "to_km": 412.0,
            "date": "2026-09-27"
        }
        cand = BlockAllocationCandidate(
            candidate_id="ALT-ISO-02",
            group_id="GRP-ISO-02",
            date="2026-09-27",
            section="BZA-GDR",
            block="B-01",
            from_km=410.0,
            to_km=412.0,
            start_time="02:00",
            end_time="03:30",
            duration=90,
            classification="ISOLATION",
            feasibility_status="FEASIBLE",
            request_ids=["ENG-999"]
        )
        DepartmentNotificationEngine.dispatch_allocation_notifications(
            allocation_id="ALLOC-ISO-002",
            group=group,
            candidate=cand,
            db_path=self.db_path
        )
        notif = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)[0]
        self.assertEqual(notif["request_id"], "ENG-999")
        self.assertEqual(notif["department"], "Engineering")
        self.assertEqual(notif["block"], "B-01")
        self.assertEqual(notif["section"], "BZA-GDR")
        self.assertEqual(notif["from_km"], 410.0)
        self.assertEqual(notif["to_km"], 412.0)
        self.assertEqual(notif["date"], "2026-09-27")
        self.assertEqual(notif["allocated_time"], "02:00–03:30")
        self.assertEqual(notif["planning_type"], "ISOLATION")
        self.assertEqual(notif["status"], "ALLOCATED BY CONTROLLER")

    # -------------------------------------------------------------------------
    # TEST 9 & 10: Unread Count and Read Transition
    # -------------------------------------------------------------------------
    def test_09_10_unread_count_and_read_transition(self):
        """Test unread count updates dynamically and transitions to READ upon viewing."""
        group = {"group_id": "GRP-T9", "request_ids": ["ENG-104"], "departments": ["Engineering"], "classification": "ISOLATION", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand = BlockAllocationCandidate(
            candidate_id="ALT-T9",
            group_id="GRP-T9",
            request_ids=["ENG-104"],
            classification="ISOLATION",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:00",
            end_time="11:00",
            duration=60,
            feasibility_status="FEASIBLE"
        )
        
        DepartmentNotificationEngine.dispatch_allocation_notifications("ALLOC-T9", group, cand, db_path=self.db_path)
        
        # Unread count should be 1
        cnt = DepartmentNotificationEngine.get_unread_notification_count("Engineering", db_path=self.db_path)
        self.assertEqual(cnt, 1)

        notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        nid = notifs[0]["notif_id"]

        # Mark read
        DepartmentNotificationEngine.mark_notification_as_read(nid, reader_user="sse_eng", db_path=self.db_path)
        
        # Unread count should now be 0
        cnt_after = DepartmentNotificationEngine.get_unread_notification_count("Engineering", db_path=self.db_path)
        self.assertEqual(cnt_after, 0)

        # Status should be READ
        updated_notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        self.assertEqual(updated_notifs[0]["is_read"], 1)
        self.assertEqual(updated_notifs[0]["delivery_status"], "READ")

    # -------------------------------------------------------------------------
    # TEST 11: Duplicate Notification Prevention
    # -------------------------------------------------------------------------
    def test_11_duplicate_notification_prevention(self):
        """Test system prevents generating duplicate notifications for the same allocation & request."""
        group = {"group_id": "GRP-T11", "request_ids": ["ENG-104"], "departments": ["Engineering"], "classification": "ISOLATION", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand = BlockAllocationCandidate(
            candidate_id="ALT-T11",
            group_id="GRP-T11",
            request_ids=["ENG-104"],
            classification="ISOLATION",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:00",
            end_time="11:00",
            duration=60,
            feasibility_status="FEASIBLE"
        )
        
        # First dispatch
        res1 = DepartmentNotificationEngine.dispatch_allocation_notifications("ALLOC-T11", group, cand, db_path=self.db_path)
        self.assertEqual(len(res1["dispatched"]), 1)

        # Second dispatch (same allocation and request)
        res2 = DepartmentNotificationEngine.dispatch_allocation_notifications("ALLOC-T11", group, cand, db_path=self.db_path)
        self.assertEqual(len(res2["dispatched"]), 0)
        self.assertEqual(len(res2["duplicates_skipped"]), 1)

        # Total notification count in DB must remain 1
        all_notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        self.assertEqual(len(all_notifs), 1)

    # -------------------------------------------------------------------------
    # TEST 12: Failed Delivery Handling & Controller Retry
    # -------------------------------------------------------------------------
    def test_12_failed_delivery_and_controller_retry(self):
        """Test simulated notification failure sets status to FAILED without rolling back allocation, and allows retry."""
        group = {"group_id": "GRP-T12", "request_ids": ["ENG-104"], "departments": ["Engineering"], "classification": "ISOLATION", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand = BlockAllocationCandidate(
            candidate_id="ALT-T12",
            group_id="GRP-T12",
            request_ids=["ENG-104"],
            classification="ISOLATION",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:00",
            end_time="11:00",
            duration=60,
            feasibility_status="FEASIBLE"
        )
        
        # Commit candidate with simulate_failure=True
        res = DepartmentNotificationEngine.dispatch_allocation_notifications(
            "ALLOC-T12", group, cand, simulate_failure=True, db_path=self.db_path
        )
        self.assertFalse(res["success"])
        self.assertEqual(len(res["failed"]), 1)

        # Check delivery status in DB
        notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0]["delivery_status"], "FAILED")

        # Controller retries notification
        nid = notifs[0]["notif_id"]
        succ_retry, r_msg = DepartmentNotificationEngine.retry_failed_notification(nid, db_path=self.db_path)
        self.assertTrue(succ_retry)

        # Check delivery status after retry
        notifs_after = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        self.assertEqual(notifs_after[0]["delivery_status"], "DELIVERED")

    # -------------------------------------------------------------------------
    # TEST 13: End-to-End Controller Selection & Allocation Commit with Notification
    # -------------------------------------------------------------------------
    def test_13_end_to_end_controller_selection_commits_and_notifies(self):
        """Test select_and_allocate_candidate updates request status to ALLOCATED and dispatches notifications."""
        group = {
            "group_id": "GRP-E2E-01",
            "request_ids": ["ENG-104", "SNT-301"],
            "departments": ["Engineering", "S&T"],
            "classification": "PARALLEL",
            "section": "BZA-VSKP",
            "block": "B-04",
            "from_km": 570.0,
            "to_km": 575.0,
            "date": "2026-09-27"
        }
        cand = BlockAllocationCandidate(
            candidate_id="ALT-E2E-01",
            group_id="GRP-E2E-01",
            request_ids=["ENG-104", "SNT-301"],
            classification="PARALLEL",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:30",
            end_time="11:30",
            duration=60,
            feasibility_status="FEASIBLE",
            is_ai_recommended=True
        )
        
        success, msg = BlockAllocationEngine.select_and_allocate_candidate(
            candidate=cand,
            group=group,
            controller_id="CONTROLLER-BZA-01",
            db_path=self.db_path
        )
        self.assertTrue(success)
        self.assertIn("Notified", msg)

        # Verify request status in block_requests_v2
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        r1_st = cur.execute("SELECT status FROM block_requests_v2 WHERE request_id = 'ENG-104'").fetchone()[0]
        r2_st = cur.execute("SELECT status FROM block_requests_v2 WHERE request_id = 'SNT-301'").fetchone()[0]
        conn.close()

        self.assertEqual(r1_st, "ALLOCATED")
        self.assertEqual(r2_st, "ALLOCATED")

        # Verify notifications dispatched
        eng_notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        st_notifs = DepartmentNotificationEngine.get_department_notifications("S&T", db_path=self.db_path)
        self.assertEqual(len(eng_notifs), 1)
        self.assertEqual(len(st_notifs), 1)

    # -------------------------------------------------------------------------
    # TEST 14 & 15: Map and Department Synchronization (Single Record)
    # -------------------------------------------------------------------------
    def test_14_15_map_and_department_sync_single_record(self):
        """Test controller map and department views read the exact same allocation record."""
        group = {"group_id": "GRP-SYNC-01", "request_ids": ["ENG-104"], "departments": ["Engineering"], "classification": "ISOLATION", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand = BlockAllocationCandidate(
            candidate_id="ALT-SYNC-01",
            group_id="GRP-SYNC-01",
            request_ids=["ENG-104"],
            classification="ISOLATION",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:00",
            end_time="11:00",
            duration=60,
            feasibility_status="FEASIBLE"
        )
        
        BlockAllocationEngine.select_and_allocate_candidate(cand, group, db_path=self.db_path)

        conn = sqlite3.connect(self.db_path)
        alloc_row = conn.execute("SELECT allocation_id, planning_group_id, status FROM final_block_allocations WHERE planning_group_id = 'GRP-SYNC-01'").fetchone()
        conn.close()

        self.assertIsNotNone(alloc_row)
        alloc_id = alloc_row[0]

        # Check notification references same allocation_id
        notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        self.assertEqual(notifs[0]["allocation_id"], alloc_id)

    # -------------------------------------------------------------------------
    # TEST 16: Live Train Layer Remains Active
    # -------------------------------------------------------------------------
    def test_16_live_train_layer_remains_active(self):
        """Test live train positions continue to be fetched without interference."""
        from app.controller_map import fetch_live_trains
        trains = fetch_live_trains(division_name="Vijayawada Division (BZA)")
        self.assertGreater(len(trains), 0)
        self.assertIn("train_number", trains[0])

    # -------------------------------------------------------------------------
    # TEST 17: Existing Allocations Remain Unchanged
    # -------------------------------------------------------------------------
    def test_17_existing_allocations_remain_unchanged(self):
        """Test allocating a new block does not overwrite or corrupt existing historical allocations."""
        group1 = {"group_id": "GRP-HIST-01", "request_ids": ["ENG-104"], "departments": ["Engineering"], "classification": "ISOLATION", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand1 = BlockAllocationCandidate("ALT-H1", "GRP-HIST-01", ["ENG-104"], "ISOLATION", "2026-09-27", "BZA-VSKP", "B-04", 570.0, 575.0, "08:00", "09:00", 60, feasibility_status="FEASIBLE")
        BlockAllocationEngine.select_and_allocate_candidate(cand1, group1, db_path=self.db_path)

        group2 = {"group_id": "GRP-HIST-02", "request_ids": ["TRD-202"], "departments": ["OHE/Traction"], "classification": "ISOLATION", "section": "BZA-GDR", "from_km": 400.0, "to_km": 405.0, "date": "2026-09-27"}
        cand2 = BlockAllocationCandidate("ALT-H2", "GRP-HIST-02", ["TRD-202"], "ISOLATION", "2026-09-27", "BZA-GDR", "B-02", 400.0, 405.0, "13:00", "14:00", 60, feasibility_status="FEASIBLE")
        BlockAllocationEngine.select_and_allocate_candidate(cand2, group2, db_path=self.db_path)

        conn = sqlite3.connect(self.db_path)
        allocs = conn.execute("SELECT planning_group_id FROM final_block_allocations ORDER BY created_at ASC").fetchall()
        conn.close()

        group_ids = [a[0] for a in allocs]
        self.assertIn("GRP-HIST-01", group_ids)
        self.assertIn("GRP-HIST-02", group_ids)

    # -------------------------------------------------------------------------
    # TEST 18: Single Allocation Record Referenced by All
    # -------------------------------------------------------------------------
    def test_18_all_pages_reference_same_allocation_id(self):
        """Test single source of truth: Controller, Engineering, and S&T all share exact same allocation ID."""
        group = {"group_id": "GRP-SHR-01", "request_ids": ["ENG-104", "SNT-301"], "departments": ["Engineering", "S&T"], "classification": "PARALLEL", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand = BlockAllocationCandidate("ALT-SHR-01", "GRP-SHR-01", ["ENG-104", "SNT-301"], "PARALLEL", "2026-09-27", "BZA-VSKP", "B-04", 570.0, 575.0, "10:30", "11:30", 60, feasibility_status="FEASIBLE")
        
        BlockAllocationEngine.select_and_allocate_candidate(cand, group, db_path=self.db_path)

        conn = sqlite3.connect(self.db_path)
        alloc_id = conn.execute("SELECT allocation_id FROM final_block_allocations WHERE planning_group_id = 'GRP-SHR-01'").fetchone()[0]
        conn.close()

        eng_notif = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)[0]
        st_notif = DepartmentNotificationEngine.get_department_notifications("S&T", db_path=self.db_path)[0]

        self.assertEqual(eng_notif["allocation_id"], alloc_id)
        self.assertEqual(st_notif["allocation_id"], alloc_id)

    # -------------------------------------------------------------------------
    # TEST 19: Authorization Filtering (No Cross-Department Leaks)
    # -------------------------------------------------------------------------
    def test_19_authorization_filtering(self):
        """Test department users only query notifications relevant to their department."""
        group = {"group_id": "GRP-AUTH-01", "request_ids": ["TRD-202"], "departments": ["OHE/Traction"], "classification": "ISOLATION", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand = BlockAllocationCandidate("ALT-AUTH-01", "GRP-AUTH-01", ["TRD-202"], "ISOLATION", "2026-09-27", "BZA-VSKP", "B-04", 570.0, 575.0, "10:30", "11:30", 60, feasibility_status="FEASIBLE")
        
        BlockAllocationEngine.select_and_allocate_candidate(cand, group, db_path=self.db_path)

        trd_notifs = DepartmentNotificationEngine.get_department_notifications("OHE/Traction", db_path=self.db_path)
        eng_notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)

        self.assertEqual(len(trd_notifs), 1)
        self.assertEqual(len(eng_notifs), 0)

    # -------------------------------------------------------------------------
    # TEST 20: Floating Chatbot Remains Functional
    # -------------------------------------------------------------------------
    def test_20_floating_chatbot_remains_functional(self):
        """Test floating chatbot module is importable and functional."""
        from app.chatbot import ask_explainer
        resp = ask_explainer("What is an isolation block?", department="Engineering")
        self.assertIsNotNone(resp)
        self.assertTrue(len(resp) > 0)

    # -------------------------------------------------------------------------
    # TEST 21: No Notification Before Controller Confirmation
    # -------------------------------------------------------------------------
    def test_21_no_notification_before_controller_confirmation(self):
        """Test candidate generation alone does NOT create any department notifications."""
        # Initial count
        cnt = DepartmentNotificationEngine.get_unread_notification_count("Engineering", db_path=self.db_path)
        self.assertEqual(cnt, 0)

        # AI recommends candidate (Step 7), but Controller has not clicked confirm
        cand = BlockAllocationCandidate("ALT-REC-01", "GRP-NO-CONF", ["ENG-104"], "ISOLATION", "2026-09-27", "BZA-VSKP", "B-04", 570.0, 575.0, "10:00", "11:00", 60, feasibility_status="FEASIBLE", is_ai_recommended=True)
        self.assertTrue(cand.is_ai_recommended)

        # Confirm no notification was inserted
        cnt_after = DepartmentNotificationEngine.get_unread_notification_count("Engineering", db_path=self.db_path)
        self.assertEqual(cnt_after, 0)

    # -------------------------------------------------------------------------
    # TEST 22: Non-Destructive Integrity (No Request Deleted)
    # -------------------------------------------------------------------------
    def test_22_non_destructive_request_retention(self):
        """Test original requests are never deleted upon allocation."""
        conn = sqlite3.connect(self.db_path)
        initial_count = conn.execute("SELECT COUNT(*) FROM block_requests_v2").fetchone()[0]
        conn.close()

        group = {"group_id": "GRP-ND-01", "request_ids": ["ENG-104"], "departments": ["Engineering"], "classification": "ISOLATION", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand = BlockAllocationCandidate("ALT-ND-01", "GRP-ND-01", ["ENG-104"], "ISOLATION", "2026-09-27", "BZA-VSKP", "B-04", 570.0, 575.0, "10:00", "11:00", 60, feasibility_status="FEASIBLE")
        
        BlockAllocationEngine.select_and_allocate_candidate(cand, group, db_path=self.db_path)

        conn = sqlite3.connect(self.db_path)
        after_count = conn.execute("SELECT COUNT(*) FROM block_requests_v2").fetchone()[0]
        conn.close()

        self.assertEqual(initial_count, after_count)

    # -------------------------------------------------------------------------
    # TEST 23: Explicit Acknowledgement and Audit Trail
    # -------------------------------------------------------------------------
    def test_23_explicit_acknowledgement_and_audit_trail(self):
        """Test department acknowledgement updates status to ACKNOWLEDGED and logs audit event."""
        group = {"group_id": "GRP-ACK-01", "request_ids": ["ENG-104"], "departments": ["Engineering"], "classification": "ISOLATION", "section": "BZA-VSKP", "from_km": 570.0, "to_km": 575.0, "date": "2026-09-27"}
        cand = BlockAllocationCandidate(
            candidate_id="ALT-ACK-01",
            group_id="GRP-ACK-01",
            request_ids=["ENG-104"],
            classification="ISOLATION",
            date="2026-09-27",
            section="BZA-VSKP",
            block="B-04",
            from_km=570.0,
            to_km=575.0,
            start_time="10:00",
            end_time="11:00",
            duration=60,
            feasibility_status="FEASIBLE"
        )
        
        BlockAllocationEngine.select_and_allocate_candidate(cand, group, db_path=self.db_path)
        notifs = DepartmentNotificationEngine.get_department_notifications("Engineering", db_path=self.db_path)
        nid = notifs[0]["notif_id"]

        succ_ack, msg_ack = DepartmentNotificationEngine.acknowledge_notification(
            notif_id=nid,
            acknowledged_by="SSE_PWAY_BZA",
            remarks="Track gang ready for possession",
            db_path=self.db_path
        )
        self.assertTrue(succ_ack)

        # Verify status in DB
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        n_st = cur.execute("SELECT status, delivery_status, acknowledged_by FROM department_notifications_v4 WHERE notif_id = ?", (nid,)).fetchone()
        
        # Check audit trail event
        audit_events = cur.execute("SELECT event_type, actor FROM block_allocation_audit_trail WHERE request_id = 'ENG-104'").fetchall()
        conn.close()

        self.assertEqual(n_st[0], "ACKNOWLEDGED")
        self.assertEqual(n_st[1], "ACKNOWLEDGED")
        self.assertEqual(n_st[2], "SSE_PWAY_BZA")

        event_names = [e[0] for e in audit_events]
        self.assertIn("ALLOCATION_CONFIRMED", event_names)
        self.assertIn("DEPARTMENT_NOTIFIED", event_names)
        self.assertIn("NOTIFICATION_ACKNOWLEDGED", event_names)


if __name__ == "__main__":
    unittest.main()
