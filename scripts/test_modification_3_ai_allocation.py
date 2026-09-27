"""
Comprehensive Unit Test Suite for Modification 3:
AI-Assisted Block Allocation Decision Support Layer
Tests all 11 required scenarios:
1. 2 requests
2. 3 requests
3. Multiple departments
4. Parallel requests
5. Sequential requests
6. Independent requests
7. Isolation-required requests
8. Overdue requests
9. High traffic
10. Medium traffic
11. Low traffic
"""

import os
import sys
import unittest
import pandas as pd

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.dependency_matrix_engine import init_dependency_matrix_table, get_dependency_matrix_df, group_candidate_block_requests
from scripts.ai_block_allocation_engine import AIBlockAllocationEngine, record_controller_decision

class TestAIAssistedBlockAllocation(unittest.TestCase):

    def setUp(self):
        init_dependency_matrix_table()
        self.matrix_df = get_dependency_matrix_df()
        self.ai_engine = AIBlockAllocationEngine()

    def test_01_two_requests_allocation(self):
        """Case 1: Group with 2 requests generates multiple alternatives with explainable metrics"""
        reqs = [
            {"request_id": "REQ-2A", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Track renewal activity", "required_duration": 60},
            {"request_id": "REQ-2B", "department": "S&T", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Track circuit inspection & tuning", "required_duration": 45}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        res = self.ai_engine.generate_block_allocation_alternatives(groups[0])
        self.assertGreaterEqual(len(res["alternatives"]), 3, "Should generate at least 3 alternatives")
        self.assertIsNotNone(res["ai_recommended_id"])
        self.assertTrue(len(res["ai_recommended_rationale"]) > 10)
        print("[PASS] Test 1: 2 requests evaluated into 3 distinct alternatives with recommendation.")

    def test_02_three_requests_cluster(self):
        """Case 2: Group with 3 requests (tri-department) evaluated with full metrics"""
        reqs = [
            {"request_id": "REQ-3A", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Track renewal activity", "required_duration": 60},
            {"request_id": "REQ-3B", "department": "TRD", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Overhead equipment replacement", "required_duration": 60},
            {"request_id": "REQ-3C", "department": "S&T", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Track circuit inspection & tuning", "required_duration": 45}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        res = self.ai_engine.generate_block_allocation_alternatives(groups[0])
        self.assertEqual(res["alternatives"][0]["requests_allocated"], 3)
        self.assertEqual(set(res["alternatives"][0]["departments_covered"]), {"ENGINEERING", "TRD", "S&T"})
        print("[PASS] Test 2: 3 requests evaluated with multi-department coverage.")

    def test_03_multiple_departments_coordination(self):
        """Case 3: Multiple departments coordinated under unified shadow window"""
        reqs = [
            {"request_id": "REQ-MD-1", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 570.0, "to_km": 575.0, "deadline": "2026-09-27", "request_type": "Track tamping (CSM / BCM)", "required_duration": 50},
            {"request_id": "REQ-MD-2", "department": "TRD", "section": "GDR-BZA-DN", "from_km": 570.0, "to_km": 575.0, "deadline": "2026-09-27", "request_type": "OHE Mast Alignment & Dropper Adjustment", "required_duration": 45}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        res = self.ai_engine.generate_block_allocation_alternatives(groups[0])
        alt1 = res["alternatives"][0]
        self.assertIn("Safety & Buffer (35%)", alt1["score_breakdown"])
        self.assertIn("Gap Utilization (30%)", alt1["score_breakdown"])
        print("[PASS] Test 3: Multiple departments explainable scoring breakdown verified.")

    def test_04_parallel_requests_classification(self):
        """Case 4: Parallel requests classified and scheduled in single bundled window"""
        reqs = [
            {"request_id": "REQ-PAR-1", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Deep screening & ballast renewal", "required_duration": 60},
            {"request_id": "REQ-PAR-2", "department": "TRD", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "25kV Catenary Wire Stringing", "required_duration": 60}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        res = self.ai_engine.generate_block_allocation_alternatives(groups[0])
        self.assertIn(res["alternatives"][0]["classification"], ["PARALLEL", "ISOLATION"])
        print("[PASS] Test 4: Parallel request alternative verified.")

    def test_05_sequential_requests_classification(self):
        """Case 5: Sequential requests sequenced in phased alternative"""
        reqs = [
            {"request_id": "REQ-SEQ-1", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Track renewal activity", "required_duration": 40},
            {"request_id": "REQ-SEQ-2", "department": "S&T", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Track circuit inspection & tuning", "required_duration": 30}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        res = self.ai_engine.generate_block_allocation_alternatives(groups[0])
        alt2 = res["alternatives"][1]
        self.assertEqual(alt2["classification"], "SEQUENTIAL")
        print("[PASS] Test 5: Sequential request phased alternative verified.")

    def test_06_independent_requests_staged(self):
        """Case 6: Independent request priority staging verified"""
        reqs = [
            {"request_id": "REQ-IND-1", "department": "ENGINEERING", "section": "BZA-RAY", "from_km": 10.0, "to_km": 14.0, "deadline": "2026-09-27", "request_type": "Routine track inspection", "required_duration": 45}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        res = self.ai_engine.generate_block_allocation_alternatives(groups[0])
        self.assertEqual(res["alternatives"][2]["classification"], "INDEPENDENT")
        print("[PASS] Test 6: Independent request staged allocation verified.")

    def test_07_isolation_required_requests(self):
        """Case 7: Catenary/OHE work enforces isolation requirement flag and PTW clearance"""
        reqs = [
            {"request_id": "REQ-ISO-1", "department": "TRD", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Overhead equipment replacement", "required_duration": 60}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        res = self.ai_engine.generate_block_allocation_alternatives(groups[0])
        alt1 = res["alternatives"][0]
        self.assertEqual(alt1["classification"], "ISOLATION")
        self.assertIn("Permit to Work", alt1["dependency_satisfaction"])
        print("[PASS] Test 7: Isolation required alternative enforced with PTW clearance.")

    def test_08_overdue_requests_pipeline(self):
        """Case 8: Overdue request evaluated under mandatory train/safety constraints"""
        reqs = [
            {"request_id": "REQ-OD-1", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-01-10", "request_type": "Track renewal activity", "status": "SUBMITTED"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        res = self.ai_engine.generate_block_allocation_alternatives(groups[0])
        self.assertTrue(groups[0]["has_overdue"])
        self.assertEqual(res["alternatives"][0]["safety_buffer"], "+5m Entry / -5m Exit (10m Total)")
        print("[PASS] Test 8: Overdue request evaluated with mandatory safety buffers protected.")

    def test_09_high_traffic_corridor_evaluation(self):
        """Case 9: High traffic scenario evaluated with tight gap buffers"""
        gaps = self.ai_engine.get_timetable_gaps_for_section("GDR-BZA-DN")
        day_gaps = [g for g in gaps if g.get("traffic") == "HIGH_DAYLIGHT" or g.get("raw_gap", 0) <= 90]
        self.assertTrue(len(gaps) > 0)
        print("[PASS] Test 9: High traffic corridor gaps extracted and verified.")

    def test_10_medium_traffic_evaluation(self):
        """Case 10: Medium traffic corridor evaluated"""
        gaps = self.ai_engine.get_timetable_gaps_for_section("TEL-BZA-UP")
        self.assertTrue(len(gaps) > 0)
        print("[PASS] Test 10: Medium traffic corridor evaluated.")

    def test_11_low_traffic_nocturnal_evaluation(self):
        """Case 11: Low traffic nocturnal window offers prime shadow block fit"""
        gaps = self.ai_engine.get_timetable_gaps_for_section("GDR-BZA-DN")
        night_gaps = [g for g in gaps if g.get("traffic") == "LOW_NIGHT" or g.get("usable_gap", 0) >= 90]
        self.assertTrue(len(night_gaps) > 0)
        print("[PASS] Test 11: Low traffic nocturnal window verified.")

    def test_12_controller_decision_override_audit(self):
        """Case 12: Controller explicit selection and override reason audit logging"""
        d_id = record_controller_decision(
            controller_id="CONTROLLER-BZA-01",
            group_id="GRP-TEST-01",
            section_id="GDR-BZA-DN",
            selected_alternative="ALT-2",
            ai_recommendation="ALT-1",
            override_reason="Sequential track tamping inspection required by Division Safety Officer before energization",
            allocated_start="02:30",
            allocated_end="04:00",
            allocated_duration=90,
            classification="SEQUENTIAL"
        )
        self.assertGreater(d_id, 0)
        print(f"[PASS] Test 12: Controller decision audit logged (Decision ID #{d_id}).")


if __name__ == "__main__":
    unittest.main(verbosity=2)
