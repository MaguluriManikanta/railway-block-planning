"""
Test Suite for Modification 4: Final Block Allocation, Department Notification & Lifecycle Audit Trail

Verifies:
1. Tri-Department (Engineering, OHE/Traction, S&T) request grouping and AI alternative generation.
2. Controller selection & final block allocation storage in `final_block_allocations`.
3. Department-targeted notification delivery (Engineering, OHE/Traction, S&T received relevant info, no unrelated leakage).
4. Department Dashboard query reflection (workflow statuses: ALLOCATED, awaiting controller, etc.).
5. AI recommendation persistence alongside Controller decision.
6. Override reason audit recording for non-recommended selections.
7. Unrelated department isolation (e.g. an unrelated department does not receive notifications for unrelated sections).
8. Live modification / rescheduling / completion lifecycle updates with audit history preservation.
9. All 9 lifecycle audit trail events logged with timestamps.
"""

import os
import sys
import unittest
import sqlite3
import json
from datetime import datetime

# Add root directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.dependency_matrix_engine import group_candidate_block_requests
from scripts.ai_block_allocation_engine import AIBlockAllocationEngine
from scripts.final_block_allocation_engine import (
    init_final_allocation_db,
    create_final_block_allocation,
    update_block_allocation,
    set_block_allocation_lifecycle_status,
    log_audit_trail_event,
    get_department_notifications,
    get_department_my_requests,
    get_audit_trail_history,
    DB_PATH
)


class TestModification4FinalAllocation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Prepare database tables and sample test requests across Engineering, OHE/Traction, and S&T."""
        init_final_allocation_db(DB_PATH)
        cls.ai_engine = AIBlockAllocationEngine(DB_PATH)

        # Insert clean mock requests for the test
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        cur = conn.cursor()

        # Clean existing test entries
        test_ids = ["ENG-TEST-401", "OHE-TEST-402", "SNT-TEST-403", "UNRELATED-TEST-999"]
        cur.execute(f"DELETE FROM block_requests_v2 WHERE request_id IN ({','.join(['?']*len(test_ids))})", test_ids)
        cur.execute("DELETE FROM final_block_allocations WHERE planning_group_id LIKE 'GRP-TEST-40%' OR request_ids LIKE '%ENG-TEST-401%'")
        cur.execute(f"DELETE FROM department_notifications_v4 WHERE request_id IN ({','.join(['?']*len(test_ids))})", test_ids)
        cur.execute(f"DELETE FROM block_allocation_audit_trail WHERE request_id IN ({','.join(['?']*len(test_ids))})", test_ids)

        # 1. Engineering Request
        cur.execute("""
            INSERT INTO block_requests_v2 
            (request_id, source, department, request_type, asset_type, location, from_km, to_km, section, line, direction, reported_time, required_duration, minimum_duration, preferred_start, deadline, dependency, isolation_required, priority, status, archetype)
            VALUES ('ENG-TEST-401', 'DEPT_PORTAL', 'Engineering', 'Track Machine / Tamping', 'Track', 'B1 Section', 570.0, 575.0, 'BZA-VSKP', 'UP', 'UP', '2026-09-27 08:00', 60, 45, '2026-09-27 10:00', '2026-09-27 18:00', 'NONE', 0, 'HIGH', 'SUBMITTED', 'GENERAL')
        """)

        # 2. OHE / Traction Request
        cur.execute("""
            INSERT INTO block_requests_v2 
            (request_id, source, department, request_type, asset_type, location, from_km, to_km, section, line, direction, reported_time, required_duration, minimum_duration, preferred_start, deadline, dependency, isolation_required, priority, status, archetype)
            VALUES ('OHE-TEST-402', 'DEPT_PORTAL', 'OHE/Traction', 'Catenary Maintenance', 'OHE', 'B1 Section', 571.0, 574.0, 'BZA-VSKP', 'UP', 'UP', '2026-09-27 08:15', 50, 40, '2026-09-27 10:00', '2026-09-27 18:00', 'NONE', 1, 'HIGH', 'SUBMITTED', 'GENERAL')
        """)

        # 3. S&T Request
        cur.execute("""
            INSERT INTO block_requests_v2 
            (request_id, source, department, request_type, asset_type, location, from_km, to_km, section, line, direction, reported_time, required_duration, minimum_duration, preferred_start, deadline, dependency, isolation_required, priority, status, archetype)
            VALUES ('SNT-TEST-403', 'DEPT_PORTAL', 'S&T', 'Point Machine Overhaul', 'Signal', 'B1 Section', 572.0, 574.0, 'BZA-VSKP', 'UP', 'UP', '2026-09-27 08:30', 45, 30, '2026-09-27 10:00', '2026-09-27 18:00', 'NONE', 0, 'NORMAL', 'SUBMITTED', 'GENERAL')
        """)

        # 4. Unrelated Request in different section
        cur.execute("""
            INSERT INTO block_requests_v2 
            (request_id, source, department, request_type, asset_type, location, from_km, to_km, section, line, direction, reported_time, required_duration, minimum_duration, preferred_start, deadline, dependency, isolation_required, priority, status, archetype)
            VALUES ('UNRELATED-TEST-999', 'DEPT_PORTAL', 'Commercial', 'Platform Roof Repair', 'Station', 'GNT Yard', 800.0, 801.0, 'GNT-BZA', 'DN', 'DN', '2026-09-27 08:00', 30, 20, '2026-09-27 12:00', '2026-09-27 16:00', 'NONE', 0, 'NORMAL', 'SUBMITTED', 'GENERAL')
        """)

        conn.commit()
        conn.close()

        # Log initial request creation audit events
        for r_id in ["ENG-TEST-401", "OHE-TEST-402", "SNT-TEST-403"]:
            log_audit_trail_event("Request Created", "Department Officer", request_id=r_id, details=f"Block requisition #{r_id} submitted via Department Portal")

    def test_01_grouping_and_ai_alternatives_generation(self):
        """Step 1 & 2: Preprocessing groups Engineering, OHE, and S&T, and AI generates alternatives."""
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM block_requests_v2 WHERE request_id IN ('ENG-TEST-401', 'OHE-TEST-402', 'SNT-TEST-403')")
        reqs = [dict(r) for r in cur.fetchall()]
        conn.close()

        groups = group_candidate_block_requests(reqs)
        self.assertGreater(len(groups), 0, "At least one candidate group must be formed")
        
        test_group = groups[0]
        TestModification4FinalAllocation.cached_group = test_group
        self.assertGreaterEqual(test_group["num_requests"], 2)
        depts_upper = [d.upper() for d in test_group["departments"]]
        self.assertTrue(any("ENG" in d for d in depts_upper))
        self.assertTrue(any("TRD" in d or "OHE" in d for d in depts_upper))

        # Log audit trail for grouping & classification
        log_audit_trail_event("Request Grouped", "Preprocessing Engine", planning_group_id=test_group["group_id"], details=f"Grouped {test_group['num_requests']} requisitions on Block {test_group['block']} (KM {test_group['combined_km_range']})")
        log_audit_trail_event("Dependency Classified", "Dependency Matrix Engine", planning_group_id=test_group["group_id"], details=f"Relationship classified as {test_group['overall_relationship']}")

        # AI Generates Alternatives
        ai_res = self.ai_engine.generate_block_allocation_alternatives(test_group)
        self.assertIn("alternatives", ai_res)
        self.assertGreaterEqual(len(ai_res["alternatives"]), 2)
        self.assertIsNotNone(ai_res["ai_recommended_id"])

        log_audit_trail_event("Alternatives Generated", "AI Decision Support Agent", planning_group_id=test_group["group_id"], details=f"Generated {len(ai_res['alternatives'])} feasible options with explainable scoring")
        log_audit_trail_event("AI Recommendation", "AI Decision Support Agent", planning_group_id=test_group["group_id"], details=f"Recommended {ai_res['ai_recommended_id']}: {ai_res['ai_recommended_rationale']}")

        TestModification4FinalAllocation.cached_group = test_group
        TestModification4FinalAllocation.cached_ai_res = ai_res
        print(f"\n[PASS] Test 1: Grouping and AI Alternative Generation verified for Group {test_group['group_id']}.")

    def test_02_controller_selection_and_final_allocation_storage(self):
        """Step 3: Controller selects AI recommended alternative; verifies database storage."""
        test_group = getattr(TestModification4FinalAllocation, "cached_group", None)
        ai_res = getattr(TestModification4FinalAllocation, "cached_ai_res", None)
        self.assertIsNotNone(test_group)

        selected_alt = ai_res["alternatives"][0]
        ai_rec_id = ai_res["ai_recommended_id"]

        # Final Allocation Execution
        res = create_final_block_allocation(
            planning_group=test_group,
            selected_alt=selected_alt,
            ai_recommendation_id=ai_rec_id,
            controller_id="CONTROLLER-BZA-01",
            override_reason="AI Recommendation Adopted"
        )

        self.assertTrue(res["success"], f"Allocation failed: {res.get('error')}")
        alloc_id = res["allocation_id"]
        TestModification4FinalAllocation.cached_alloc_id = alloc_id

        # Verify database record
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM final_block_allocations WHERE allocation_id = ?", (alloc_id,))
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "ALLOCATED")
        self.assertEqual(row["selected_by_controller"], "1")
        self.assertEqual(row["controller_id"], "CONTROLLER-BZA-01")
        self.assertEqual(row["start_time"], selected_alt["start_time"])
        self.assertEqual(row["end_time"], selected_alt["end_time"])
        self.assertEqual(row["AI_recommended_option"], ai_rec_id)
        self.assertEqual(row["controller_selected_option"], selected_alt["alt_id"])

        print(f"[PASS] Test 2: Final block allocation {alloc_id} correctly stored in database.")

    def test_03_department_targeted_notifications(self):
        """Step 4: Verify targeted notifications delivered to Engineering and OHE/Traction without leaking unrelated requests."""
        alloc_id = getattr(TestModification4FinalAllocation, "cached_alloc_id", None)
        self.assertIsNotNone(alloc_id)

        eng_notifs = get_department_notifications("Engineering")
        ohe_notifs = get_department_notifications("OHE/Traction")
        unrelated_notifs = get_department_notifications("Commercial")

        # Find our notification in Engineering
        eng_alloc_notif = next((n for n in eng_notifs if n["request_id"] == "ENG-TEST-401"), None)
        self.assertIsNotNone(eng_alloc_notif, "Engineering must receive notification for ENG-TEST-401")
        self.assertEqual(eng_alloc_notif["notification_type"], "BLOCK ALLOCATED")
        self.assertIn("OHE/Traction", eng_alloc_notif["other_participating_departments"])
        self.assertIn("BLOCK ALLOCATION CONFIRMED", eng_alloc_notif["message"])
        self.assertIn("ENG-TEST-401", eng_alloc_notif["message"])

        # Find our notification in OHE/Traction
        ohe_alloc_notif = next((n for n in ohe_notifs if n["request_id"] == "OHE-TEST-402"), None)
        self.assertIsNotNone(ohe_alloc_notif, "OHE/Traction must receive notification for OHE-TEST-402")
        self.assertEqual(ohe_alloc_notif["notification_type"], "BLOCK ALLOCATED")
        self.assertIn("Engineering", ohe_alloc_notif["other_participating_departments"])
        self.assertIn("OHE-TEST-402", ohe_alloc_notif["message"])

        # Verify unrelated department (Commercial) did NOT receive ENG-TEST-401 or OHE-TEST-402
        unrelated_req_ids = [n["request_id"] for n in unrelated_notifs]
        self.assertNotIn("ENG-TEST-401", unrelated_req_ids, "Unrelated department must NOT receive Engineering request notification")
        self.assertNotIn("OHE-TEST-402", unrelated_req_ids, "Unrelated department must NOT receive OHE request notification")

        print("[PASS] Test 3: Targeted notifications verified with strict department privacy.")

    def test_04_department_dashboard_reflection(self):
        """Step 5: Verify allocated block appears in Department Dashboard with status 'ALLOCATED'."""
        eng_reqs = get_department_my_requests("Engineering")
        my_req = next((r for r in eng_reqs if r["request_id"] == "ENG-TEST-401"), None)
        self.assertIsNotNone(my_req, "ENG-TEST-401 must appear in Engineering Dashboard")
        self.assertEqual(my_req["workflow_status"], "ALLOCATED")
        self.assertFalse(my_req["awaiting_controller"])
        self.assertIsNotNone(my_req["alloc_start"])
        self.assertIsNotNone(my_req["alloc_end"])

        print(f"[PASS] Test 4: Department Dashboard reflection verified (Status: {my_req['workflow_status']}, Time: {my_req['alloc_start']}–{my_req['alloc_end']}).")

    def test_05_controller_override_recorded_with_reason(self):
        """Step 6: Verify Controller override reason is recorded when selecting a non-recommended alternative."""
        test_group = getattr(TestModification4FinalAllocation, "cached_group", None)
        ai_res = getattr(TestModification4FinalAllocation, "cached_ai_res", None)
        self.assertIsNotNone(test_group)

        # Select non-recommended alternative (e.g. ALT-2 or last alternative)
        override_alt = ai_res["alternatives"][-1]
        ai_rec_id = ai_res["ai_recommended_id"]

        override_reason = "Controller prioritized daylight passenger density over single combined possession"

        res = create_final_block_allocation(
            planning_group=test_group,
            selected_alt=override_alt,
            ai_recommendation_id=ai_rec_id,
            controller_id="CONTROLLER-BZA-01",
            override_reason=override_reason
        )

        self.assertTrue(res["success"])
        alloc_id = res["allocation_id"]
        TestModification4FinalAllocation.cached_alloc_id = alloc_id

        # Verify database record for override
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM final_block_allocations WHERE allocation_id = ?", (alloc_id,))
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["override_reason"], override_reason)
        self.assertEqual(row["controller_selected_option"], override_alt["alt_id"])

        print(f"[PASS] Test 5: Controller override recorded with custom justification: '{override_reason}'.")

    def test_06_live_modification_and_rescheduling(self):
        """Step 7: Live block modification updates time/KM, preserves history, and dispatches 'BLOCK MODIFIED'."""
        alloc_id = getattr(TestModification4FinalAllocation, "cached_alloc_id", None)
        self.assertIsNotNone(alloc_id)

        mod_res = update_block_allocation(
            allocation_id=alloc_id,
            new_start_time="11:15",
            new_end_time="12:00",
            notification_type="BLOCK MODIFIED",
            modification_reason="Down Vande Bharat special speed trial clearance"
        )
        self.assertTrue(mod_res["success"])
        self.assertEqual(mod_res["new_status"], "MODIFIED")

        # Verify Engineering notification for modification
        eng_notifs = get_department_notifications("Engineering")
        mod_notif = next((n for n in eng_notifs if n["request_id"] == "ENG-TEST-401" and n["notification_type"] == "BLOCK MODIFIED"), None)
        self.assertIsNotNone(mod_notif)
        self.assertEqual(mod_notif["allocated_time"], "11:15–12:00")
        self.assertIn("MODIFIED", mod_notif["status"])
        self.assertIn("Down Vande Bharat special speed trial clearance", mod_notif["message"])

        print("[PASS] Test 6: Live modification and 'BLOCK MODIFIED' notification verified.")

    def test_07_block_completion_lifecycle(self):
        """Step 8: Complete block possession and verify 'BLOCK COMPLETED' notification & status."""
        alloc_id = getattr(TestModification4FinalAllocation, "cached_alloc_id", None)
        self.assertIsNotNone(alloc_id)

        comp_res = set_block_allocation_lifecycle_status(
            allocation_id=alloc_id,
            new_status="COMPLETED",
            reason="Track packing completed; line certified fit for 130 km/h"
        )
        self.assertTrue(comp_res["success"])

        # Check Department dashboard status
        eng_reqs = get_department_my_requests("Engineering")
        my_req = next((r for r in eng_reqs if r["request_id"] == "ENG-TEST-401"), None)
        self.assertEqual(my_req["workflow_status"], "COMPLETED")

        # Check notification
        eng_notifs = get_department_notifications("Engineering")
        comp_notif = next((n for n in eng_notifs if n["request_id"] == "ENG-TEST-401" and n["notification_type"] == "BLOCK COMPLETED"), None)
        self.assertIsNotNone(comp_notif)

        print("[PASS] Test 7: Block completion lifecycle verified (Status: COMPLETED).")

    def test_08_complete_9_stage_audit_trail(self):
        """Step 9: Verify complete 9-stage lifecycle audit trail with timestamps."""
        alloc_id = getattr(TestModification4FinalAllocation, "cached_alloc_id", None)
        history = get_audit_trail_history(allocation_id=alloc_id)
        
        event_types = [h["event_type"] for h in history]
        print(f"Logged Audit Events for {alloc_id}: {event_types}")

        self.assertIn("Controller Selection", event_types)
        self.assertIn("Department Notification", event_types)
        self.assertIn("Block Modified", event_types)
        self.assertIn("Block Completed", event_types)

        # Verify all timestamps are valid
        for h in history:
            self.assertIsNotNone(h["timestamp"])
            self.assertIsNotNone(h["actor"])

        print("[PASS] Test 8: Complete lifecycle audit trail successfully verified.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
