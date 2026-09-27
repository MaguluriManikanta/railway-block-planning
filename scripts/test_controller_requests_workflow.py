"""
Comprehensive Integration Test Suite for Controller Requests, Dependency Classification,
Multi-Alternative AI Decision Support, Controller Authorization, and Two-Layer Map Telemetry.
"""

import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta

# Ensure scripts directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from scripts.dependency_matrix_engine import (
    init_dependency_matrix_table,
    get_dependency_matrix_df,
    group_candidate_block_requests,
    find_relationship_between_activities
)
from scripts.ai_block_allocation_engine import (
    AIBlockAllocationEngine,
    record_controller_decision
)
from scripts.final_block_allocation_engine import (
    init_final_allocation_db,
    create_final_block_allocation,
    get_all_final_block_allocations,
    get_department_notifications,
    set_block_allocation_lifecycle_status
)


class TestControllerRequestsWorkflow(unittest.TestCase):
    def setUp(self):
        self.test_db = os.path.join(BASE_DIR, "test_controller_workflow.db")
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        init_dependency_matrix_table(self.test_db)
        init_final_allocation_db(self.test_db)
        
        conn = sqlite3.connect(self.test_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS block_requests_v2 (
                request_id TEXT PRIMARY KEY,
                department TEXT,
                request_type TEXT,
                section TEXT,
                line TEXT,
                from_km REAL,
                to_km REAL,
                required_duration INTEGER,
                minimum_duration INTEGER,
                preferred_start TEXT,
                deadline TEXT,
                dependency TEXT,
                isolation_required INTEGER,
                priority TEXT,
                reason TEXT,
                status TEXT,
                reported_time TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                defect_id TEXT,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_01_classification_into_all_three_categories(self):
        """Test deterministic grouping into ISOLATION, PARALLEL, and SEQUENTIAL groups."""
        matrix_df = get_dependency_matrix_df(self.test_db)

        # 1. Cluster A (Engineering + TRD Track Renewal under Catenary) -> ISOLATION
        reqs_iso = [
            {
                "request_id": "REQ-TEST-ENG-01",
                "department": "Engineering",
                "request_type": "Track renewal activity",
                "section": "BZA-RAY",
                "from_km": 114.0,
                "to_km": 118.0,
                "required_duration": 60,
                "deadline": "2026-09-30",
                "status": "SUBMITTED"
            },
            {
                "request_id": "REQ-TEST-TRD-01",
                "department": "OHE/Traction",
                "request_type": "Overhead equipment replacement",
                "section": "BZA-RAY",
                "from_km": 114.0,
                "to_km": 118.0,
                "required_duration": 60,
                "deadline": "2026-09-30",
                "status": "SUBMITTED"
            }
        ]
        groups_iso = group_candidate_block_requests(reqs_iso, matrix_df)
        self.assertEqual(len(groups_iso), 1)
        self.assertEqual(groups_iso[0]["overall_relationship"], "ISOLATION")

        # 2. Cluster B (Engineering Tamping + TRD Mast Alignment) -> SEQUENTIAL
        reqs_seq = [
            {
                "request_id": "REQ-TEST-ENG-02",
                "department": "Engineering",
                "request_type": "Track tamping (CSM / BCM)",
                "section": "RAY-KDM",
                "from_km": 120.0,
                "to_km": 125.0,
                "required_duration": 45,
                "deadline": "2026-09-30",
                "status": "SUBMITTED"
            },
            {
                "request_id": "REQ-TEST-TRD-02",
                "department": "TRD",
                "request_type": "OHE Mast Alignment & Dropper Adjustment",
                "section": "RAY-KDM",
                "from_km": 120.0,
                "to_km": 125.0,
                "required_duration": 45,
                "deadline": "2026-09-30",
                "status": "SUBMITTED"
            }
        ]
        groups_seq = group_candidate_block_requests(reqs_seq, matrix_df)
        self.assertEqual(len(groups_seq), 1)
        self.assertEqual(groups_seq[0]["overall_relationship"], "SEQUENTIAL")

        # 3. Cluster C (Engineering Deep Screening + TRD Wire Stringing) -> PARALLEL
        reqs_par = [
            {
                "request_id": "REQ-TEST-ENG-03",
                "department": "Engineering",
                "request_type": "Deep screening & ballast renewal",
                "section": "KDM-MDR",
                "from_km": 130.0,
                "to_km": 135.0,
                "required_duration": 60,
                "deadline": "2026-09-30",
                "status": "SUBMITTED"
            },
            {
                "request_id": "REQ-TEST-TRD-03",
                "department": "TRD",
                "request_type": "25kV Catenary Wire Stringing",
                "section": "KDM-MDR",
                "from_km": 130.0,
                "to_km": 135.0,
                "required_duration": 60,
                "deadline": "2026-09-30",
                "status": "SUBMITTED"
            }
        ]
        groups_par = group_candidate_block_requests(reqs_par, matrix_df)
        self.assertEqual(len(groups_par), 1)
        self.assertEqual(groups_par[0]["overall_relationship"], "PARALLEL")

    def test_02_ai_alternatives_and_multifactor_scoring(self):
        """Test generation of multiple feasible alternatives with multi-factor scoring breakdown."""
        matrix_df = get_dependency_matrix_df(self.test_db)
        reqs = [
            {"request_id": "REQ-01", "department": "Engineering", "request_type": "Track renewal activity", "section": "BZA-RAY", "from_km": 114.0, "to_km": 118.0, "required_duration": 60, "deadline": "2026-09-30", "status": "SUBMITTED"},
            {"request_id": "REQ-02", "department": "S&T", "request_type": "Track circuit inspection & tuning", "section": "BZA-RAY", "from_km": 115.0, "to_km": 117.0, "required_duration": 45, "deadline": "2026-09-30", "status": "SUBMITTED"}
        ]
        groups = group_candidate_block_requests(reqs, matrix_df)
        grp = groups[0]

        ai_engine = AIBlockAllocationEngine(db_path=self.test_db)
        ai_res = ai_engine.generate_block_allocation_alternatives(grp)

        self.assertIn("alternatives", ai_res)
        self.assertGreaterEqual(len(ai_res["alternatives"]), 2)
        self.assertIsNotNone(ai_res["ai_recommended_id"])

        for alt in ai_res["alternatives"]:
            self.assertIn("score_breakdown", alt)
            sb = alt["score_breakdown"]
            self.assertIn("Safety & Buffer (35%)", sb)
            self.assertIn("Gap Utilization (30%)", sb)
            self.assertIn("Corridor Efficiency (20%)", sb)
            self.assertIn("Headway Protection (15%)", sb)
            self.assertGreaterEqual(alt["score"], 0)
            self.assertLessEqual(alt["score"], 100)

    def test_03_controller_selection_and_final_allocation(self):
        """Test Controller confirmation creating final allocation and targeted notifications."""
        matrix_df = get_dependency_matrix_df(self.test_db)
        reqs = [
            {"request_id": "REQ-TEST-ENG-10", "department": "Engineering", "request_type": "Track renewal activity", "section": "BZA-RAY", "from_km": 114.0, "to_km": 118.0, "required_duration": 60, "deadline": "2026-09-30", "status": "SUBMITTED"},
            {"request_id": "REQ-TEST-TRD-10", "department": "OHE/Traction", "request_type": "Overhead equipment replacement", "section": "BZA-RAY", "from_km": 114.0, "to_km": 118.0, "required_duration": 60, "deadline": "2026-09-30", "status": "SUBMITTED"}
        ]
        groups = group_candidate_block_requests(reqs, matrix_df)
        grp = groups[0]

        ai_engine = AIBlockAllocationEngine(db_path=self.test_db)
        ai_res = ai_engine.generate_block_allocation_alternatives(grp)
        rec_alt = next(a for a in ai_res["alternatives"] if a["alt_id"] == ai_res["ai_recommended_id"])

        # Execute Controller Confirmation
        alloc_res = create_final_block_allocation(
            planning_group=grp,
            selected_alt=rec_alt,
            ai_recommendation_id=ai_res["ai_recommended_id"],
            controller_id="CONTROLLER-BZA-01",
            override_reason="AI Recommendation Adopted",
            db_path=self.test_db
        )

        self.assertTrue(alloc_res["success"])
        alloc_id = alloc_res["allocation_id"]

        # Verify final_block_allocations record
        all_allocs = get_all_final_block_allocations(self.test_db)
        self.assertEqual(len(all_allocs), 1)
        self.assertEqual(all_allocs[0]["allocation_id"], alloc_id)
        self.assertEqual(all_allocs[0]["status"], "ALLOCATED")

        # Verify targeted notifications for Engineering and OHE/Traction
        eng_notifs = get_department_notifications("Engineering", db_path=self.test_db)
        trd_notifs = get_department_notifications("OHE/Traction", db_path=self.test_db)
        st_notifs = get_department_notifications("S&T", db_path=self.test_db)

        self.assertGreaterEqual(len(eng_notifs), 1)
        self.assertGreaterEqual(len(trd_notifs), 1)
        self.assertEqual(len(st_notifs), 0)  # S&T was not in this group, zero leak!

    def test_04_conflict_monitoring_block_at_risk(self):
        """Test lifecycle status transition to AT_RISK when delay conflict occurs."""
        matrix_df = get_dependency_matrix_df(self.test_db)
        reqs = [
            {"request_id": "REQ-CONF-01", "department": "Engineering", "request_type": "Track renewal activity", "section": "BZA-RAY", "from_km": 114.0, "to_km": 118.0, "required_duration": 60, "deadline": "2026-09-30", "status": "SUBMITTED"}
        ]
        groups = group_candidate_block_requests(reqs, matrix_df)
        grp = groups[0]

        ai_engine = AIBlockAllocationEngine(db_path=self.test_db)
        ai_res = ai_engine.generate_block_allocation_alternatives(grp)
        alt0 = ai_res["alternatives"][0]

        alloc_res = create_final_block_allocation(
            planning_group=grp,
            selected_alt=alt0,
            ai_recommendation_id=ai_res["ai_recommended_id"],
            controller_id="CONTROLLER-BZA-01",
            db_path=self.test_db
        )
        alloc_id = alloc_res["allocation_id"]

        # Simulate Headway Infringement -> Flag AT_RISK
        res_risk = set_block_allocation_lifecycle_status(
            allocation_id=alloc_id,
            new_status="AT_RISK",
            controller_id="AUTOMATIC_CONFLICT_MONITOR",
            reason="Preceding train delay (+12m) infringes 5-min entry buffer into planned block window",
            db_path=self.test_db
        )
        self.assertTrue(res_risk["success"])

        # Check notification dispatched
        notifs = get_department_notifications("Engineering", db_path=self.test_db)
        risk_notifs = [n for n in notifs if n["notification_type"] == "BLOCK AT RISK"]
        self.assertEqual(len(risk_notifs), 1)


if __name__ == "__main__":
    unittest.main()
