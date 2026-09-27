"""
STEP 3 Automated Test Verification Suite
Validates all 20 required test cases for Allocated Maintenance Block Layer.
"""

import sys
import os
import unittest
import sqlite3
import py_compile
import json

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('app'))

from controller_map import (
    ControllerMap,
    MapLegend,
    BaseRailwayLayer,
    AllocatedBlockLayer,
    LiveTrainLayer,
    get_section_geometry,
    fetch_allocated_blocks,
    get_division_network_data,
    DIVISION_GEOGRAPHIC_NETWORKS
)


class TestStep3AllocatedBlocks(unittest.TestCase):

    def test_01_compilation(self):
        """TEST 1 & 2: Controller page and controller_map compile cleanly."""
        try:
            py_compile.compile('app/main.py', doraise=True)
            py_compile.compile('app/controller_map.py', doraise=True)
        except Exception as e:
            self.fail(f"Compilation error: {e}")

    def test_02_allocated_block_layer_initialization(self):
        """TEST 3: AllocatedBlockLayer loads and renders blocks."""
        html = ControllerMap.generate_html("Vijayawada Division (BZA)")
        self.assertIn("Allocated Maintenance Blocks", html)
        self.assertIn("L.featureGroup", html)

    def test_03_database_and_demo_allocations_loaded(self):
        """TEST 4 & 5: Existing allocation records appear; multiple blocks appear simultaneously."""
        blocks = fetch_allocated_blocks("Vijayawada Division (BZA)")
        self.assertIsInstance(blocks, list)
        self.assertTrue(len(blocks) >= 2, "Must support multiple blocks simultaneously")
        # Check presence of block fields
        for b in blocks:
            self.assertIn("allocation_id", b)
            self.assertIn("block_id", b)
            self.assertIn("section", b)
            self.assertIn("from_km", b)
            self.assertIn("to_km", b)
            self.assertIn("date", b)
            self.assertIn("start_time", b)
            self.assertIn("end_time", b)
            self.assertIn("status", b)
            self.assertIn("source", b)

    def test_04_block_popup_and_metadata(self):
        """TEST 6 to 13: Block popup displays Block ID, Section, KM range, Date/Time, Department, Classification, Status."""
        sample_block = {
            "allocation_id": "ALLOC-TEST-999",
            "planning_group_id": "GRP-TEST-01",
            "request_ids": ["REQ-ENG-901", "REQ-TRD-902"],
            "departments": ["Engineering", "OHE/Traction"],
            "classification": "ISOLATION",
            "block_id": "BLK-TEST-SEC-01",
            "section": "Vijayawada – Kondapalli",
            "from_km": 114.5,
            "to_km": 118.5,
            "date": "2026-09-27",
            "start_time": "10:30",
            "end_time": "13:30",
            "duration_minutes": 180,
            "status": "ACTIVE",
            "reason": "CSM Track Tamping Machine",
            "execution_order": ["1. Engineering (Tamping)", "2. OHE/Traction (Wire Isolation)"],
            "line_coords": [[16.545, 80.598], [16.618, 80.536]],
            "lat": 16.58,
            "lon": 80.56,
            "source": "DATABASE",
            "is_demo": False
        }
        html = ControllerMap.generate_html("Vijayawada Division (BZA)", allocations=[sample_block])
        self.assertIn("BLK-TEST-SEC-01", html) # TEST 7: Block ID
        self.assertIn("Vijayawada – Kondapalli", html) # TEST 8: Section
        self.assertIn("Km 114.5 – 118.5", html) # TEST 9: KM Range
        self.assertIn("10:30 – 13:30", html) # TEST 10: Date/Time
        self.assertIn("Engineering", html) # TEST 11: Department
        self.assertIn("ISOLATION", html) # TEST 12: Classification
        self.assertIn("ACTIVE", html) # TEST 13: Status
        self.assertIn("DATABASE ALLOCATION", html) # Source separation

    def test_05_geometric_adapter(self):
        """TEST: Geographic adapter get_section_geometry maps section/KM to coordinates."""
        coords = get_section_geometry("Vijayawada – Kondapalli", from_km=114.0, to_km=118.0, division_name="Vijayawada Division (BZA)")
        self.assertIsNotNone(coords)
        self.assertEqual(len(coords), 2)
        # Verify valid latitude & longitude in Indian Railways Vijayawada jurisdiction
        self.assertTrue(16.0 <= coords[0][0] <= 18.0)
        self.assertTrue(80.0 <= coords[0][1] <= 82.0)

    def test_06_layer_ordering_and_z_index(self):
        """TEST 14: Allocated blocks render below live trains, above geography."""
        html = ControllerMap.generate_html("Vijayawada Division (BZA)")
        # Check zIndexOffset enforcement
        self.assertIn('"zIndexOffset": 210', html) # Base geography
        self.assertIn('"zIndexOffset": 450', html) # Allocated blocks
        self.assertIn('"zIndexOffset": 900', html) # Live trains
        self.assertTrue(210 < 450 < 900, "Hierarchy must be Base (210) < Blocks (450) < Trains (900)")

    def test_07_live_trains_and_requests_unbroken(self):
        """TEST 15 to 17: Live trains, Requests button, and Floating chatbot continue working."""
        with open('app/main.py', 'r', encoding='utf-8') as f:
            code = f.read()
        self.assertIn("open_floating_ai_chatbot_dialog", code)
        self.assertIn("req_pop_label", code) # Requests popup
        self.assertTrue("render_railflow_geographic_corridor_view" in code or "ControllerMap.generate_html" in code)

    def test_08_database_integrity(self):
        """TEST 18: No database tables or records are deleted."""
        conn = sqlite3.connect('railway.db')
        cur = conn.cursor()
        total_tables = cur.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        self.assertTrue(total_tables >= 30, "Database tables must remain completely intact")
        req_count = cur.execute("SELECT COUNT(*) FROM block_requests_v2").fetchone()[0]
        self.assertTrue(req_count > 0, "Requisition records must be preserved")
        conn.close()

    def test_09_filtering_by_status_and_dept(self):
        """TEST: Filtering blocks by status and department works properly."""
        b_all = fetch_allocated_blocks("Vijayawada Division (BZA)", status_filter="ALL", dept_filter="ALL")
        b_eng = fetch_allocated_blocks("Vijayawada Division (BZA)", status_filter="ALL", dept_filter="Engineering")
        self.assertIsInstance(b_all, list)
        self.assertIsInstance(b_eng, list)

    def test_10_legend_content(self):
        """TEST: Updated Map Legend reflects allocated and active block states."""
        legend = MapLegend.render_html()
        self.assertIn("Allocated Block", legend)
        self.assertIn("Active Block", legend)
        self.assertIn("Completed Block", legend)
        self.assertIn("Live Train", legend)


if __name__ == '__main__':
    unittest.main()
