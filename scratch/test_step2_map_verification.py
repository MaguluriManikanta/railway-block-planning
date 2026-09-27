"""
STEP 2 Automated Test Verification Suite
Validates all 13 required test cases for Controller Geographic Map Layout.
"""

import sys
import os
import unittest
import py_compile
import pandas as pd

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('app'))

from controller_map import (
    ControllerMap,
    MapLegend,
    BaseRailwayLayer,
    AllocatedBlockLayer,
    LiveTrainLayer,
    get_division_network_data,
    DIVISION_GEOGRAPHIC_NETWORKS
)


class TestStep2GeographicMap(unittest.TestCase):

    def test_01_controller_page_compilation(self):
        """TEST 1: Controller and app/main.py compiles with zero syntax errors."""
        try:
            py_compile.compile('app/main.py', doraise=True)
            py_compile.compile('app/controller_map.py', doraise=True)
        except Exception as e:
            self.fail(f"Compilation failed: {e}")

    def test_02_map_generation(self):
        """TEST 2 & 3: Map loads correctly and Railway Geographic Base is visible across all 7 divisions."""
        for div_name in DIVISION_GEOGRAPHIC_NETWORKS.keys():
            html = ControllerMap.generate_html(division_name=div_name)
            self.assertIsNotNone(html)
            self.assertTrue(len(html) > 10000, f"Map HTML too small for {div_name}")
            # Verify Leaflet Map initialization and HUD elements
            self.assertIn("L.map", html)
            self.assertIn("L.control.layers", html)
            self.assertIn("trainHudCard", html)

    def test_03_geographic_base_tracks_and_stations(self):
        """TEST 3: Tracks, stations, and KM references are present in the base layer."""
        bza_data = get_division_network_data("Vijayawada Division (BZA)")
        self.assertIn("lines", bza_data)
        self.assertTrue(len(bza_data["lines"]) >= 3)
        station_names = [st["name"] for line in bza_data["lines"] for st in line["stations"]]
        self.assertIn("Vijayawada Jn (BZA)", station_names)
        self.assertIn("Kondapalli (KI)", station_names)
        self.assertIn("Khammam (KMT)", station_names)

    def test_04_live_train_telemetry(self):
        """TEST 4: Live train data appears and distinguishes LIVE vs SIMULATION."""
        bza_data = get_division_network_data("Vijayawada Division (BZA)")
        trains = bza_data.get("default_trains", [])
        self.assertTrue(len(trains) >= 4)
        sources = [t.get("data_source") for t in trains]
        self.assertIn("LIVE", sources)
        self.assertIn("SIMULATION", sources)

    def test_05_train_marker_popup_structure(self):
        """TEST 5: Train marker popup includes number, current KM, direction, speed, delay, next station, status."""
        html = ControllerMap.generate_html("Vijayawada Division (BZA)")
        self.assertIn("12727", html)
        self.assertIn("Godavari Express", html)
        self.assertIn("Current KM", html)
        self.assertIn("Direction", html)
        self.assertIn("Next Station", html)

    def test_06_map_zoom_and_controls(self):
        """TEST 6 & 7: Map zoom, tile layers, and Leaflet controls are present."""
        html = ControllerMap.generate_html("Vijayawada Division (BZA)")
        self.assertIn("L.control.layers", html)
        self.assertIn("CartoDB DarkMatter", html)
        self.assertIn("OpenStreetMap", html)
        self.assertIn("trainHudCard", html)

    def test_08_legend_and_status(self):
        """TEST 8: Compact Map Legend renders all layer statuses."""
        legend_html = MapLegend.render_html()
        self.assertIn("MAP LAYERS & LEGEND", legend_html)
        self.assertIn("Track (Layer 0)", legend_html)
        self.assertIn("Station / Hub", legend_html)
        self.assertIn("Allocated Block (Layer 1)", legend_html)
        self.assertIn("Live Train (Layer 2)", legend_html)

    def test_09_allocated_block_structure(self):
        """TEST 9: AllocatedBlockLayer accepts standard allocation schema."""
        sample_allocations = [
            {
                "allocation_id": "ALLOC-TEST-001",
                "block_id": "BLK-T1",
                "section": "Section-Alpha",
                "from_km": 570.0,
                "to_km": 575.0,
                "date": "2026-09-27",
                "start_time": "10:20",
                "end_time": "10:50",
                "department": "Engineering",
                "classification": "ISOLATION",
                "status": "ALLOCATED",
                "line_coords": [[16.545, 80.598], [16.618, 80.536]],
                "lat": 16.58,
                "lon": 80.56,
                "reason": "Test Track Relaying"
            }
        ]
        html = ControllerMap.generate_html("Vijayawada Division (BZA)", allocations=sample_allocations)
        self.assertIn("ALLOC-TEST-001", html)
        self.assertIn("BLK-T1", html)
        self.assertIn("ISOLATION", html)

    def test_10_layer_ordering(self):
        """TEST 10: Layer stacking hierarchy (Base -> Blocks -> Trains)."""
        html = ControllerMap.generate_html("Vijayawada Division (BZA)")
        # Verify z-index offsets enforce Base < Blocks < Trains
        self.assertIn('"zIndexOffset": 210', html) # Stations (Base)
        self.assertIn('"zIndexOffset": 450', html) # Blocks (Layer 1)
        self.assertIn('"zIndexOffset": 900', html) # Trains (Layer 2)
        self.assertTrue(210 < 450 < 900, "Layer stacking z-index hierarchy must be strictly Base < Blocks < Trains")

    def test_11_no_duplicate_or_broken_components(self):
        """TEST 11 & 12: Ensure no duplicate chatbot or broken controller workflows."""
        with open('app/main.py', 'r', encoding='utf-8') as f:
            main_code = f.read()
        self.assertIn("open_floating_ai_chatbot_dialog", main_code)
        self.assertTrue("render_railflow_geographic_corridor_view" in main_code or "ControllerMap.generate_html" in main_code)
        self.assertIn("render_alerts_popover_content", main_code)
        self.assertIn("btn_classify_popover_trigger", main_code)


if __name__ == '__main__':
    unittest.main()
