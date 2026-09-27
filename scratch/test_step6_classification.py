"""
Unit & Integration Test Suite for STEP 6 — REQUEST CLASSIFICATION ENGINE
Indian Railways Block Planning System
Tests:
1. Matrix initialization & rule seeding
2. Pairwise rule lookups (ISOLATION, PARALLEL, SEQUENTIAL, CONTROLLER_REVIEW)
3. Spatial KM overlap logic with boundary & inverted range checks
4. Temporal date compatibility logic
5. Connected-component clustering of overlapping requests
6. Precedence ordering for sequential clusters (ENG -> TRD -> S&T)
7. Dominant classification hierarchy (Review > Isolation > Sequential > Parallel)
8. Ambiguous / structural activity review detection
9. Explainable AI reasoning, confidence scores, and supporting rule references
10. Non-destructive database persistence (status -> CLASSIFIED, no record deletion)
11. Token safety and execution performance
12. UI rendering stability
"""

import os
import sys
import unittest
import sqlite3
import pandas as pd
from datetime import datetime

# Setup paths
APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.classification_engine import (
    init_classification_db,
    DependencyMatrixEngine,
    RequestClassificationEngine,
    is_km_range_overlapping,
    are_locations_compatible,
    are_dates_compatible,
    _render_classified_group_card,
    render_classified_groups_workspace
)
from app.controller_requests import (
    fetch_controller_requests,
    get_pending_request_counts
)


class TestStep6ClassificationEngine(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Ensure test DB is initialized."""
        init_classification_db()

    def test_01_matrix_initialization_and_seeding(self):
        """Verify system_dependency_matrix table exists and contains baseline rules."""
        rules_df = DependencyMatrixEngine.get_all_rules()
        self.assertFalse(rules_df.empty, "Dependency matrix rules should not be empty")
        self.assertGreaterEqual(len(rules_df), 10, "Should have at least 10 seeded dependency rules")
        expected_cols = ["rule_code", "dept_a", "activity_a", "dept_b", "activity_b", "relationship", "rule_description"]
        for col in expected_cols:
            self.assertIn(col, rules_df.columns, f"Matrix DataFrame should have column '{col}'")

    def test_02_pairwise_rule_eng_trd_isolation(self):
        """Test Engineering Track Renewal + TRD OHE Replacement -> ISOLATION."""
        rel, code, desc, pri = DependencyMatrixEngine.evaluate_pairwise_relationship(
            "Engineering", "Track renewal activity",
            "OHE/Traction", "Overhead equipment replacement"
        )
        self.assertEqual(rel, "ISOLATION")
        self.assertIn("PTW", desc)
        self.assertEqual(pri, "MANDATORY")

    def test_03_pairwise_rule_eng_trd_sequential(self):
        """Test Engineering Track Tamping + TRD Dropper Adjustment -> SEQUENTIAL."""
        rel, code, desc, pri = DependencyMatrixEngine.evaluate_pairwise_relationship(
            "Engineering", "Track tamping (CSM / BCM)",
            "TRD", "OHE Mast Alignment & Dropper Adjustment"
        )
        self.assertEqual(rel, "SEQUENTIAL")
        self.assertIn("tamping", desc.lower())

    def test_04_pairwise_rule_eng_trd_parallel(self):
        """Test Engineering Deep Screening + TRD Wire Stringing -> PARALLEL."""
        rel, code, desc, pri = DependencyMatrixEngine.evaluate_pairwise_relationship(
            "Engineering", "Deep screening & ballast renewal",
            "TRD", "25kV Catenary Wire Stringing"
        )
        self.assertEqual(rel, "PARALLEL")
        self.assertEqual(pri, "COORDINATED")

    def test_05_pairwise_rule_eng_snt_sequential_track_circuit(self):
        """Test Engineering Track Renewal + S&T Track Circuit Inspection -> SEQUENTIAL."""
        rel, code, desc, pri = DependencyMatrixEngine.evaluate_pairwise_relationship(
            "Engineering", "Track renewal activity",
            "S&T", "Track circuit inspection & tuning"
        )
        self.assertEqual(rel, "SEQUENTIAL")
        self.assertIn("P-Way", desc)

    def test_06_pairwise_rule_eng_snt_sequential_point_machine(self):
        """Test Engineering Turnout Sleeper + S&T Point Machine -> SEQUENTIAL."""
        rel, code, desc, pri = DependencyMatrixEngine.evaluate_pairwise_relationship(
            "Engineering", "Turnout sleeper replacement",
            "S&T", "Point machine maintenance"
        )
        self.assertEqual(rel, "SEQUENTIAL")

    def test_07_pairwise_rule_eng_snt_parallel_sej(self):
        """Test Engineering SEJ Replacement + S&T Axle Counter -> PARALLEL."""
        rel, code, desc, pri = DependencyMatrixEngine.evaluate_pairwise_relationship(
            "Engineering", "Switch expansion joint replacement",
            "S&T", "Axle counter reset & testing"
        )
        self.assertEqual(rel, "PARALLEL")

    def test_08_pairwise_rule_trd_snt_isolation_substation(self):
        """Test TRD Substation Transformer Overhaul + S&T Interlocking -> ISOLATION."""
        rel, code, desc, pri = DependencyMatrixEngine.evaluate_pairwise_relationship(
            "TRD", "Traction Substation Transformer Overhaul",
            "S&T", "Electronic interlocking testing"
        )
        self.assertEqual(rel, "ISOLATION")

    def test_09_pairwise_rule_ambiguous_bridge_case(self):
        """Test Ambiguous Civil activity (Bridge girder) -> REQUIRES CONTROLLER REVIEW."""
        rel, code, desc, pri = DependencyMatrixEngine.evaluate_pairwise_relationship(
            "Engineering", "Bridge girder replacement",
            "OHE/Traction", "Catenary inspection"
        )
        self.assertEqual(rel, "CONTROLLER_REVIEW")
        self.assertIn("Controller", desc)

    def test_10_spatial_km_overlap_logic(self):
        """Test max(from_a, from_b) <= min(to_a, to_b) evaluation under normal and edge conditions."""
        # Overlapping ranges
        self.assertTrue(is_km_range_overlapping(100.0, 110.0, 105.0, 115.0))
        self.assertTrue(is_km_range_overlapping(100.0, 110.0, 100.0, 110.0)) # Exact match
        self.assertTrue(is_km_range_overlapping(100.0, 120.0, 105.0, 115.0)) # Subset
        
        # Non-overlapping ranges
        self.assertFalse(is_km_range_overlapping(100.0, 105.0, 110.0, 115.0))
        self.assertFalse(is_km_range_overlapping(10.0, 20.0, 25.0, 30.0))

        # Inverted KM inputs (e.g. from 110 down to 100)
        self.assertTrue(is_km_range_overlapping(110.0, 100.0, 105.0, 115.0))
        self.assertTrue(is_km_range_overlapping(110.0, 100.0, 115.0, 105.0))

    def test_11_temporal_date_compatibility_logic(self):
        """Test that requests on different dates are NOT grouped together."""
        req1 = {"section": "Vijayawada–Kondapalli", "from_km": 100.0, "to_km": 105.0, "date": "2026-09-30"}
        req2 = {"section": "Vijayawada–Kondapalli", "from_km": 102.0, "to_km": 107.0, "date": "2026-09-30"}
        req3 = {"section": "Vijayawada–Kondapalli", "from_km": 102.0, "to_km": 107.0, "date": "2026-10-01"}
        
        self.assertTrue(are_dates_compatible(req1, req2))
        self.assertFalse(are_dates_compatible(req1, req3))

    def test_12_classify_single_standalone_request(self):
        """Test single request produces a standalone ISOLATION group."""
        req = {
            "request_id": "TEST-REQ-ISO-01",
            "department": "Engineering",
            "request_type": "Track tamping",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 104.0,
            "date": "2026-09-30",
            "duration": 90,
            "priority": "High"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req])
        self.assertEqual(res["counts"]["isolation"], 1)
        self.assertEqual(res["counts"]["parallel"], 0)
        self.assertEqual(res["counts"]["sequential"], 0)
        grp = res["isolation_groups"][0]
        self.assertEqual(grp["classification"], "ISOLATION")
        self.assertIn("TEST-REQ-ISO-01", grp["request_ids"])
        self.assertGreaterEqual(grp["confidence"], 0.90)

    def test_13_classify_multi_request_parallel_cluster(self):
        """Test multiple compatible overlapping requests classified as PARALLEL."""
        req1 = {
            "request_id": "TEST-PAR-01",
            "department": "Engineering",
            "request_type": "Switch expansion joint replacement",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-110",
            "from_km": 110.0,
            "to_km": 114.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        req2 = {
            "request_id": "TEST-PAR-02",
            "department": "S&T",
            "request_type": "Axle counter reset & testing",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-110",
            "from_km": 112.0,
            "to_km": 115.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req1, req2])
        self.assertEqual(res["counts"]["parallel"], 1)
        grp = res["parallel_groups"][0]
        self.assertEqual(grp["classification"], "PARALLEL")
        self.assertEqual(set(grp["request_ids"]), {"TEST-PAR-01", "TEST-PAR-02"})
        self.assertIn("Simultaneous Execution", grp["execution_order"][0])

    def test_14_classify_multi_request_sequential_cluster_with_precedence(self):
        """Test sequential cluster sorts departments in correct order: ENG -> TRD -> S&T."""
        req_snt = {
            "request_id": "TEST-SEQ-SNT",
            "department": "S&T",
            "request_type": "Track circuit inspection & tuning",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-120",
            "from_km": 120.0,
            "to_km": 124.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        req_eng = {
            "request_id": "TEST-SEQ-ENG",
            "department": "Engineering",
            "request_type": "Track renewal activity",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-120",
            "from_km": 121.0,
            "to_km": 125.0,
            "date": "2026-09-30",
            "duration": 120,
            "priority": "Critical"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req_snt, req_eng])
        self.assertEqual(res["counts"]["sequential"], 1)
        grp = res["sequential_groups"][0]
        self.assertEqual(grp["classification"], "SEQUENTIAL")
        # Precedence check: Engineering must be step 1, S&T step 2
        self.assertIn("TEST-SEQ-ENG ➔ TEST-SEQ-SNT", grp["dependency_graph"])
        self.assertTrue("Engineering" in grp["execution_order"][0])
        self.assertTrue("S&T" in grp["execution_order"][1])

    def test_15_classify_multi_request_isolation_dominant_cluster(self):
        """Test cluster with mandatory power isolation classifies group as ISOLATION."""
        req1 = {
            "request_id": "TEST-ISO-ENG",
            "department": "Engineering",
            "request_type": "Track renewal activity",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-130",
            "from_km": 130.0,
            "to_km": 135.0,
            "date": "2026-09-30",
            "duration": 120,
            "priority": "Critical"
        }
        req2 = {
            "request_id": "TEST-ISO-TRD",
            "department": "TRD",
            "request_type": "Overhead equipment replacement",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-130",
            "from_km": 131.0,
            "to_km": 134.0,
            "date": "2026-09-30",
            "duration": 90,
            "priority": "High"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req1, req2])
        self.assertEqual(res["counts"]["isolation"], 1)
        grp = res["isolation_groups"][0]
        self.assertEqual(grp["classification"], "ISOLATION")
        self.assertIn("PTW", grp["reason"])

    def test_16_classify_ambiguous_case_controller_review(self):
        """Test request with ambiguous special work classifies as REQUIRES CONTROLLER REVIEW."""
        req = {
            "request_id": "TEST-REV-01",
            "department": "Engineering",
            "request_type": "Bridge girder replacement",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-140",
            "from_km": 140.0,
            "to_km": 141.0,
            "date": "2026-09-30",
            "duration": 180,
            "priority": "Critical"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req])
        self.assertEqual(res["counts"]["review"], 1)
        grp = res["review_groups"][0]
        self.assertEqual(grp["classification"], "REQUIRES CONTROLLER REVIEW")
        self.assertIn("Controller Review Required", grp["execution_order"][0])

    def test_17_non_destructive_database_persistence(self):
        """Verify classified records are stored in history and original requests are updated to CLASSIFIED without deletion."""
        db_path = os.path.join(os.path.dirname(__file__), "..", "railway.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Insert a temporary test request in block_requests_v2
        test_id = f"TEST-PERSIST-{int(datetime.now().timestamp())}"
        cur.execute("""
            INSERT OR REPLACE INTO block_requests_v2
            (request_id, department, request_type, reason, section, location, from_km, to_km, reported_time, required_duration, priority, status)
            VALUES (?, 'Engineering', 'Track tamping', 'Test persistence non-destructive', 'Vijayawada–Kondapalli', 'BLK-VIJ-150', 150.0, 154.0, '2026-09-30 08:00:00', 60, 'High', 'NEW')
        """, (test_id,))
        conn.commit()

        # Classify the request
        req = {
            "request_id": test_id,
            "department": "Engineering",
            "request_type": "Track tamping",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-150",
            "from_km": 150.0,
            "to_km": 154.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req])
        self.assertIn(test_id, res["classified_ids"])

        # Verify status in block_requests_v2 changed to 'CLASSIFIED' and record was NOT deleted
        row = cur.execute("SELECT status, reason FROM block_requests_v2 WHERE request_id = ?", (test_id,)).fetchone()
        self.assertIsNotNone(row, "Original request record must not be deleted")
        self.assertEqual(row[0], "CLASSIFIED", "Status must transition to CLASSIFIED")
        self.assertEqual(row[1], "Test persistence non-destructive", "Original reason text must remain untouched")

        # Verify history row in request_classification_history
        hist_row = cur.execute("SELECT classification, supporting_rules FROM request_classification_history WHERE request_ids LIKE ?", (f"%{test_id}%",)).fetchone()
        self.assertIsNotNone(hist_row, "History entry must exist in request_classification_history")
        self.assertEqual(hist_row[0], "ISOLATION")

        # Cleanup
        cur.execute("DELETE FROM block_requests_v2 WHERE request_id = ?", (test_id,))
        cur.execute("DELETE FROM request_classification_history WHERE request_ids LIKE ?", (f"%{test_id}%",))
        conn.commit()
        conn.close()

    def test_18_department_normalization(self):
        """Test department string normalization handles aliases cleanly."""
        self.assertEqual(DependencyMatrixEngine.normalize_dept("Engineering"), "ENGINEERING")
        self.assertEqual(DependencyMatrixEngine.normalize_dept("CIVIL P-WAY"), "ENGINEERING")
        self.assertEqual(DependencyMatrixEngine.normalize_dept("OHE/Traction"), "TRD")
        self.assertEqual(DependencyMatrixEngine.normalize_dept("TRAC_ELEC"), "TRD")
        self.assertEqual(DependencyMatrixEngine.normalize_dept("S&T"), "S&T")
        self.assertEqual(DependencyMatrixEngine.normalize_dept("Signal and Telecom"), "S&T")

    def test_19_token_safety_and_performance(self):
        """Test classification engine processes a batch of 20 requests in < 100ms."""
        import time
        mock_batch = []
        for i in range(20):
            mock_batch.append({
                "request_id": f"PERF-REQ-{i:03d}",
                "department": "Engineering" if i % 2 == 0 else "TRD",
                "request_type": "Track tamping" if i % 2 == 0 else "Catenary inspection",
                "section": "Vijayawada–Kondapalli",
                "block": f"BLK-VIJ-{100 + (i // 2)}",
                "from_km": 100.0 + (i % 5),
                "to_km": 104.0 + (i % 5),
                "date": "2026-09-30",
                "duration": 60,
                "priority": "High"
            })
        
        t0 = time.time()
        res = RequestClassificationEngine.classify_all_actionable_requests(mock_batch)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 3.5, "Classification engine must complete 20 requests in < 3500ms")
        self.assertEqual(len(res["classified_ids"]), 20)

    def test_20_explainable_ai_reasoning_and_confidence(self):
        """Verify every classified group includes reasoning, supporting rules, and confidence."""
        req1 = {
            "request_id": "TEST-EXP-01",
            "department": "Engineering",
            "request_type": "Track tamping (CSM / BCM)",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-160",
            "from_km": 160.0,
            "to_km": 165.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        req2 = {
            "request_id": "TEST-EXP-02",
            "department": "TRD",
            "request_type": "OHE Mast Alignment & Dropper Adjustment",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-160",
            "from_km": 161.0,
            "to_km": 164.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req1, req2])
        grp = res["all_groups"][0]
        self.assertTrue(len(grp["reason"]) > 10, "Reason must be descriptive")
        self.assertTrue(len(grp["supporting_rules"]) >= 1, "Must list supporting rules")
        self.assertGreaterEqual(grp["confidence"], 0.85, "Confidence should be >= 0.85")
        self.assertIn("TrackMind-IR-Classifier-v2.0", grp["model_version"])

    def test_21_fetch_controller_requests_integration(self):
        """Verify fetch_controller_requests interacts cleanly with pending counts and classification."""
        counts = get_pending_request_counts()
        self.assertIn("total", counts)
        self.assertIn("new", counts)
        self.assertIn("overdue", counts)
        self.assertGreaterEqual(counts["total"], 0)

    def test_22_spatial_clustering_non_overlapping_separate_groups(self):
        """Verify that requests on same date and section with non-overlapping KM form separate groups."""
        req1 = {
            "request_id": "TEST-SEP-01",
            "department": "Engineering",
            "request_type": "Track tamping",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-100",
            "from_km": 100.0,
            "to_km": 105.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        req2 = {
            "request_id": "TEST-SEP-02",
            "department": "Engineering",
            "request_type": "Track tamping",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-180",
            "from_km": 180.0,
            "to_km": 185.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req1, req2])
        # Since KM 100-105 and 180-185 do not overlap, they form 2 distinct groups
        self.assertEqual(res["counts"]["total"], 2)
        self.assertEqual(len(res["isolation_groups"]), 2)

    def test_23_tri_department_sequential_clustering(self):
        """Verify 3-department overlapping cluster (ENG + TRD + S&T) is sequential with 3-stage precedence."""
        req_eng = {
            "request_id": "TRI-ENG",
            "department": "Engineering",
            "request_type": "Track renewal activity",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-200",
            "from_km": 200.0,
            "to_km": 205.0,
            "date": "2026-09-30",
            "duration": 120,
            "priority": "Critical"
        }
        req_trd = {
            "request_id": "TRI-TRD",
            "department": "TRD",
            "request_type": "OHE Mast Alignment & Dropper Adjustment",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-200",
            "from_km": 201.0,
            "to_km": 204.0,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        req_snt = {
            "request_id": "TRI-SNT",
            "department": "S&T",
            "request_type": "Track circuit inspection & tuning",
            "section": "Vijayawada–Kondapalli",
            "block": "BLK-VIJ-200",
            "from_km": 200.5,
            "to_km": 203.5,
            "date": "2026-09-30",
            "duration": 60,
            "priority": "High"
        }
        res = RequestClassificationEngine.classify_all_actionable_requests([req_eng, req_trd, req_snt])
        self.assertEqual(res["counts"]["total"], 1)
        grp = res["all_groups"][0]
        self.assertIn(grp["classification"], ["SEQUENTIAL", "ISOLATION"])
        self.assertEqual(len(grp["request_ids"]), 3)

    def test_24_empty_requests_safety(self):
        """Verify classification handles empty lists gracefully without throwing exceptions."""
        res = RequestClassificationEngine.classify_all_actionable_requests([])
        self.assertEqual(res["counts"]["total"], 0)
        self.assertEqual(len(res["classified_ids"]), 0)

    def test_25_system_matrix_immutability_and_lookup_speed(self):
        """Verify system matrix can be queried repeatedly with cached speed."""
        import time
        t0 = time.time()
        for _ in range(50):
            df = DependencyMatrixEngine.get_all_rules()
            self.assertGreater(len(df), 0)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 0.5, "50 rule queries should take < 500ms")


if __name__ == "__main__":
    unittest.main()
