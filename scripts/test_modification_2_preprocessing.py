"""
Comprehensive Test Suite for Modification 2:
Controller Block Allocation Preprocessing & Dependency Matrix Engine
Tests all 8 required scenarios and validates grouping + relationship detection.
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
from scripts.dependency_matrix_engine import (
    init_dependency_matrix_table,
    get_dependency_matrix_df,
    is_km_overlapping,
    find_relationship_between_activities,
    group_candidate_block_requests
)

class TestControllerAllocationPreprocessing(unittest.TestCase):

    def setUp(self):
        init_dependency_matrix_table()
        self.matrix_df = get_dependency_matrix_df()

    def test_01_same_block_same_km_same_date(self):
        """Case 1: Same block + same KM + same date -> Grouped into 1 Candidate Group"""
        reqs = [
            {"request_id": "REQ-01-A", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 570.0, "to_km": 575.0, "deadline": "2026-09-27", "request_type": "Track renewal activity"},
            {"request_id": "REQ-01-B", "department": "S&T", "section": "GDR-BZA-DN", "from_km": 570.0, "to_km": 575.0, "deadline": "2026-09-27", "request_type": "Track circuit inspection & tuning"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        self.assertEqual(len(groups), 1, "Should form exactly 1 candidate group")
        self.assertEqual(groups[0]["num_requests"], 2)
        self.assertEqual(set(groups[0]["request_ids"]), {"REQ-01-A", "REQ-01-B"})
        self.assertEqual(groups[0]["combined_km_range"], "KM 570.0 – 575.0")
        print("[PASS] Test 1: Same block + same KM + same date correctly grouped.")

    def test_02_same_block_overlapping_km_same_date(self):
        """Case 2: Same block + overlapping KM (570-575 and 573-578) + same date -> Grouped with combined KM 570-578"""
        reqs = [
            {"request_id": "REQ-02-A", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 570.0, "to_km": 575.0, "deadline": "2026-09-27", "request_type": "Track renewal activity"},
            {"request_id": "REQ-02-B", "department": "TRD", "section": "GDR-BZA-DN", "from_km": 573.0, "to_km": 578.0, "deadline": "2026-09-27", "request_type": "Overhead equipment replacement"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["num_requests"], 2)
        self.assertEqual(groups[0]["combined_km_range"], "KM 570.0 – 578.0")
        self.assertEqual(groups[0]["overall_relationship"], "ISOLATION")
        print("[PASS] Test 2: Same block + overlapping KM + same date correctly grouped (Span 570–578).")

    def test_03_same_block_different_date(self):
        """Case 3: Same block + different date -> Must form 2 separate groups"""
        reqs = [
            {"request_id": "REQ-03-A", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 570.0, "to_km": 575.0, "deadline": "2026-09-27", "request_type": "Track renewal activity"},
            {"request_id": "REQ-03-B", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 570.0, "to_km": 575.0, "deadline": "2026-09-28", "request_type": "Track renewal activity"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        self.assertEqual(len(groups), 2, "Different dates must produce separate groups")
        print("[PASS] Test 3: Same block + different date separated into 2 distinct groups.")

    def test_04_different_block_same_date(self):
        """Case 4: Different block + same date -> Must form 2 separate groups"""
        reqs = [
            {"request_id": "REQ-04-A", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Track renewal activity"},
            {"request_id": "REQ-04-B", "department": "TRD", "section": "TEL-BZA-UP", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-09-27", "request_type": "Overhead equipment replacement"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        self.assertEqual(len(groups), 2, "Different blocks/sections must produce separate groups")
        print("[PASS] Test 4: Different block + same date separated into 2 distinct groups.")

    def test_05_same_date_non_overlapping_km(self):
        """Case 5: Same date + same section + non-overlapping KM -> Must form 2 separate groups"""
        reqs = [
            {"request_id": "REQ-05-A", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 100.0, "to_km": 105.0, "deadline": "2026-09-27", "request_type": "Track renewal activity"},
            {"request_id": "REQ-05-B", "department": "S&T", "section": "GDR-BZA-DN", "from_km": 200.0, "to_km": 205.0, "deadline": "2026-09-27", "request_type": "Point machine maintenance"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        self.assertEqual(len(groups), 2, "Non-overlapping KM ranges must produce separate groups")
        print("[PASS] Test 5: Same date + non-overlapping KM separated into 2 distinct groups.")

    def test_06_multiple_departments_in_one_group(self):
        """Case 6: Multiple departments in one group (Engineering + TRD + S&T on KM 570-575)"""
        reqs = [
            {"request_id": "REQ-06-ENG", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 570.0, "to_km": 575.0, "deadline": "2026-09-27", "request_type": "Track renewal activity"},
            {"request_id": "REQ-06-TRD", "department": "TRD", "section": "GDR-BZA-DN", "from_km": 572.0, "to_km": 574.0, "deadline": "2026-09-27", "request_type": "Overhead equipment replacement"},
            {"request_id": "REQ-06-ST", "department": "S&T", "section": "GDR-BZA-DN", "from_km": 571.0, "to_km": 575.0, "deadline": "2026-09-27", "request_type": "Track circuit inspection & tuning"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["num_requests"], 3)
        self.assertEqual(set(groups[0]["departments"]), {"ENGINEERING", "TRD", "S&T"})
        self.assertEqual(len(groups[0]["relationships"]), 3, "3 pairwise relationships (ENG-TRD, ENG-ST, TRD-ST)")
        print("[PASS] Test 6: Tri-department cluster (ENG + TRD + S&T) correctly unified with full relationship graph.")

    def test_07_overdue_request_inclusion(self):
        """Case 7: Overdue request enters same allocation pipeline with visible overdue indicator"""
        reqs = [
            {"request_id": "REQ-07-OVERDUE", "department": "ENGINEERING", "section": "GDR-BZA-DN", "from_km": 114.0, "to_km": 118.0, "deadline": "2026-01-15", "request_type": "Track renewal activity", "status": "SUBMITTED"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0]["has_overdue"])
        self.assertGreater(groups[0]["max_overdue_days"], 0)
        print("[PASS] Test 7: Overdue request seamlessly processed with active overdue indicator.")

    def test_08_independent_request(self):
        """Case 8: Independent single request evaluated cleanly without false dependencies"""
        reqs = [
            {"request_id": "REQ-08-IND", "department": "ENGINEERING", "section": "BZA-RAY", "from_km": 10.0, "to_km": 14.0, "deadline": "2026-09-30", "request_type": "Track inspection", "status": "SUBMITTED"}
        ]
        groups = group_candidate_block_requests(reqs, self.matrix_df)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["overall_relationship"], "INDEPENDENT")
        print("[PASS] Test 8: Independent request isolated with zero false dependencies.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
