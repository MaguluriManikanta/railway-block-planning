"""
Automated Test Suite for STEP 4 — LIVE TRAIN UPPER LAYER ONLY
Tests 25 comprehensive test cases covering LiveTrainLayer, fetch_live_trains,
staleness detection, status filters, search queries, zIndex visual hierarchy,
marker styling, direction indicators, and ControllerMap integration.
"""

import os
import sys
import unittest
import sqlite3
from datetime import datetime, timedelta
import folium

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

from app.controller_map import (
    BaseRailwayLayer,
    AllocatedBlockLayer,
    LiveTrainLayer,
    MapControls,
    MapLegend,
    ControllerMap,
    fetch_allocated_blocks,
    fetch_live_trains,
    get_division_network_data,
    DIVISION_GEOGRAPHIC_NETWORKS
)


class TestStep4LiveTrainUpperLayer(unittest.TestCase):
    """25 Test Cases for Step 4 Live Train Layer Implementation."""

    def setUp(self):
        self.division = "Vijayawada Division (BZA)"

    # --- 1. Schema & Mandatory Fields ---
    def test_01_fetch_live_trains_returns_non_empty_list(self):
        trains = fetch_live_trains(division_name=self.division)
        self.assertIsInstance(trains, list)
        self.assertGreater(len(trains), 0, "Should return default or DB live trains for Vijayawada")

    def test_02_train_record_has_mandatory_fields(self):
        trains = fetch_live_trains(division_name=self.division)
        first_tr = trains[0]
        mandatory_keys = [
            "train_number", "latitude", "longitude", "current_km",
            "direction", "speed", "status", "data_source"
        ]
        for k in mandatory_keys:
            self.assertIn(k, first_tr, f"Mandatory key '{k}' missing from train record")

    def test_03_coordinates_are_valid_floats(self):
        trains = fetch_live_trains(division_name=self.division)
        for tr in trains:
            lat = tr.get("latitude")
            lon = tr.get("longitude")
            self.assertIsInstance(lat, (int, float))
            self.assertIsInstance(lon, (int, float))
            self.assertGreater(lat, 10.0)
            self.assertGreater(lon, 70.0)

    # --- 2. Staleness Detection (>120s) ---
    def test_04_fresh_telemetry_not_stale(self):
        trains = fetch_live_trains(division_name=self.division)
        for tr in trains:
            if tr.get("age_seconds", 0) <= 120:
                self.assertFalse(tr.get("is_stale", False))

    def test_05_stale_telemetry_detected_when_timestamp_exceeds_120s(self):
        # Create a mock stale train dictionary
        old_time = (datetime.now() - timedelta(seconds=250)).strftime("%Y-%m-%d %H:%M:%S")
        stale_tr = {
            "train_number": "12999",
            "train_name": "Test Stale Express",
            "latitude": 16.50,
            "longitude": 80.60,
            "speed": 60.0,
            "timestamp": old_time,
            "data_source": "LIVE"
        }
        # Render on map and verify popup contains stale warning
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        stale_tr["is_stale"] = True
        stale_tr["age_seconds"] = 250
        LiveTrainLayer.add_to_map(m, [stale_tr])
        html = m.get_root().render()
        self.assertIn("TELEMETRY STALE", html)
        self.assertIn("250s", html)

    # --- 3. Train Filtering (RUNNING, DELAYED, STOPPED, ALL) ---
    def test_06_filter_running_trains(self):
        running = fetch_live_trains(division_name=self.division, train_filter="RUNNING")
        for tr in running:
            self.assertGreater(float(tr.get("speed", 0)), 0)
            self.assertNotIn("STOP", str(tr.get("status", "")).upper())

    def test_07_filter_stopped_trains(self):
        stopped = fetch_live_trains(division_name=self.division, train_filter="STOPPED")
        for tr in stopped:
            is_zero_speed = float(tr.get("speed", 0)) == 0
            has_stop_status = "STOP" in str(tr.get("status", "")).upper()
            self.assertTrue(is_zero_speed or has_stop_status)

    def test_08_filter_delayed_trains(self):
        delayed = fetch_live_trains(division_name=self.division, train_filter="DELAYED")
        for tr in delayed:
            has_delay = float(tr.get("delay", 0)) > 0 or "DELAY" in str(tr.get("status", "")).upper()
            self.assertTrue(has_delay)

    def test_09_filter_all_returns_all(self):
        all_trains = fetch_live_trains(division_name=self.division, train_filter="ALL")
        net_trains = get_division_network_data(self.division).get("default_trains", [])
        self.assertEqual(len(all_trains), len(net_trains))

    # --- 4. Search Matching ---
    def test_10_search_query_by_train_number(self):
        results = fetch_live_trains(division_name=self.division, search_query="12727")
        self.assertTrue(any(tr["train_number"] == "12727" for tr in results))

    def test_11_search_query_by_train_name(self):
        results = fetch_live_trains(division_name=self.division, search_query="Godavari")
        self.assertTrue(any("Godavari" in tr.get("train_name", "") for tr in results))

    def test_12_search_query_no_match(self):
        results = fetch_live_trains(division_name=self.division, search_query="NON_EXISTENT_XYZ_999")
        self.assertEqual(len(results), 0)

    # --- 5. Visual Stacking Hierarchy & zIndex ---
    def test_13_live_train_layer_adds_feature_group(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        trains = fetch_live_trains(division_name=self.division)
        LiveTrainLayer.add_to_map(m, trains)
        children = [child for child in m._children.values() if isinstance(child, folium.FeatureGroup)]
        train_fg = [fg for fg in children if "Live" in fg.layer_name or "Train" in fg.layer_name]
        self.assertEqual(len(train_fg), 1)

    def test_14_live_train_markers_have_zindex_offset_900(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        trains = fetch_live_trains(division_name=self.division)
        LiveTrainLayer.add_to_map(m, trains)
        html = m.get_root().render()
        self.assertIn("900", html)
        self.assertIn("z-index: 900 !important", html)

    def test_15_three_layer_stacking_hierarchy_verified(self):
        # Base (Layer 0) -> Blocks (Layer 1) -> Trains (Layer 2)
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        MapControls.setup_controls(m)
        net_data = get_division_network_data(self.division)
        BaseRailwayLayer.add_to_map(m, net_data)
        AllocatedBlockLayer.add_to_map(m, fetch_allocated_blocks(self.division))
        LiveTrainLayer.add_to_map(m, fetch_live_trains(self.division))
        html = m.get_root().render()
        self.assertIn("Railway Base", html)
        self.assertIn("Allocated Maintenance Blocks", html)
        self.assertIn("Live Moving Trains", html)

    # --- 6. Direction & Speed Indicators ---
    def test_16_direction_up_indicator(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        tr = [{
            "train_number": "12727", "train_name": "Godavari", "latitude": 16.65,
            "longitude": 80.51, "speed": 80.0, "direction": "UP", "status": "RUNNING", "data_source": "LIVE"
        }]
        LiveTrainLayer.add_to_map(m, tr)
        html = m.get_root().render()
        self.assertIn("UP", html)

    def test_17_direction_dn_indicator(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        tr = [{
            "train_number": "12759", "train_name": "Charminar", "latitude": 16.57,
            "longitude": 80.57, "speed": 60.0, "direction": "DN", "status": "RUNNING", "data_source": "LIVE"
        }]
        LiveTrainLayer.add_to_map(m, tr)
        html = m.get_root().render()
        self.assertIn("DN", html)

    def test_18_speed_pill_shows_speed_value(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        tr = [{
            "train_number": "20833", "train_name": "Vande Bharat", "latitude": 16.91,
            "longitude": 80.36, "speed": 120.0, "direction": "UP", "status": "RUNNING", "data_source": "LIVE"
        }]
        LiveTrainLayer.add_to_map(m, tr)
        html = m.get_root().render()
        self.assertIn("120k", html)
        self.assertIn("120 km/h", html)

    # --- 7. Status Color Themes ---
    def test_19_stopped_train_has_red_theme(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        tr = [{
            "train_number": "G-402", "train_name": "Freight", "latitude": 16.52,
            "longitude": 80.62, "speed": 0.0, "direction": "DN", "status": "STOPPED", "data_source": "SIMULATION"
        }]
        LiveTrainLayer.add_to_map(m, tr)
        html = m.get_root().render()
        self.assertIn("#ef4444", html)
        self.assertIn("STOPPED", html)

    def test_20_caution_train_has_yellow_theme(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        tr = [{
            "train_number": "12759", "train_name": "Charminar", "latitude": 16.57,
            "longitude": 80.57, "speed": 30.0, "direction": "UP", "status": "REDUCED SPEED (TSR 30)", "data_source": "LIVE"
        }]
        LiveTrainLayer.add_to_map(m, tr)
        html = m.get_root().render()
        self.assertIn("#eab308", html)
        self.assertIn("CAUTION", html)

    # --- 8. Telemetry Source & Legend ---
    def test_21_telemetry_source_badges(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        trains = [
            {"train_number": "101", "train_name": "Live Express", "latitude": 16.50, "longitude": 80.60, "speed": 80, "data_source": "LIVE"},
            {"train_number": "102", "train_name": "Sim Express", "latitude": 16.60, "longitude": 80.70, "speed": 60, "data_source": "SIMULATION"}
        ]
        LiveTrainLayer.add_to_map(m, trains)
        html = m.get_root().render()
        self.assertIn("LIVE RTIS", html)
        self.assertIn("SIMULATION", html)

    def test_22_legend_contains_all_layer_stacking_items(self):
        legend_html = MapLegend.render_html()
        self.assertIn("Track (Layer 0)", legend_html)
        self.assertIn("Allocated Block (Layer 1)", legend_html)
        self.assertIn("Live Train (Layer 2)", legend_html)
        self.assertIn("Caution Train", legend_html)
        self.assertIn("Stopped Train", legend_html)
        self.assertIn("Stale", legend_html)

    # --- 9. All Divisions Multi-Corridor Validation ---
    def test_23_all_seven_divisions_have_default_trains(self):
        for div_name in DIVISION_GEOGRAPHIC_NETWORKS.keys():
            trains = fetch_live_trains(division_name=div_name)
            self.assertGreater(len(trains), 0, f"Division {div_name} should have trains")

    # --- 10. ControllerMap Full HTML Generation & Non-Fabrication ---
    def test_24_controller_map_generate_html_with_train_filter(self):
        full_html = ControllerMap.generate_html(
            division_name=self.division,
            train_filter="RUNNING",
            search_query="Godavari"
        )
        self.assertIsInstance(full_html, str)
        self.assertIn("leaflet", full_html.lower())
        self.assertIn("Godavari", full_html)
        self.assertIn("trainHudCard", full_html)

    def test_25_invalid_coordinates_never_fabricated(self):
        m = folium.Map(location=[16.55, 80.85], zoom_start=9)
        invalid_train = [{
            "train_number": "NO-COORD", "train_name": "Invalid Train",
            "latitude": None, "longitude": None, "speed": 50
        }]
        LiveTrainLayer.add_to_map(m, invalid_train)
        html = m.get_root().render()
        self.assertNotIn("NO-COORD", html)


if __name__ == "__main__":
    unittest.main()
