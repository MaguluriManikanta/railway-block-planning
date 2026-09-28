import unittest
import pandas as pd
import sqlite3
import os
import sys
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import (
    SHARED_DIVISION_LOCATIONS,
    get_shared_selected_division,
    get_active_trains_df,
    init_trains_10_state,
    render_live_corridor_map_plotly,
    get_full_schedule,
    generate_ai_block_plan_matrix_html,
    derive_system_dependencies_and_isolation,
    get_db,
    AutomaticBlockPlanningEngine,
    SafetyClearanceAgent,
    BlockMergingAgent,
    LocopilotSpeedAgent,
    TractionAwareRouterAgent,
    TrackMachinePackerAgent,
    TSRLifecycleAgent,
    render_railflow_geographic_corridor_view
)

class TestPhase6FullRegression(unittest.TestCase):
    
    # 1. SHARED DIVISIONS & CORRIDOR LOCATIONS
    def test_01_shared_divisions_consistency(self):
        self.assertEqual(len(SHARED_DIVISION_LOCATIONS), 7)
        for expected_div in ["Vijayawada Division (BZA)", "Khurda Road Division (KUR)", "Secunderabad Division (SC)", 
                              "Howrah Division (HWH)", "Guntakal Division (GTL)", "Guntur Division (GNT)", "Hyderabad Division (HYB)"]:
            self.assertIn(expected_div, SHARED_DIVISION_LOCATIONS)

    def test_02_active_trains_for_all_7_divisions(self):
        for div in SHARED_DIVISION_LOCATIONS:
            df_trains = get_active_trains_df(division=div)
            self.assertIsInstance(df_trains, pd.DataFrame)
            self.assertFalse(df_trains.empty, f"No trains returned for division {div}")
            self.assertTrue("train_number" in df_trains.columns or "train_no" in df_trains.columns)
            self.assertTrue("speed_kmh" in df_trains.columns or "speed" in df_trains.columns)

    # 2. SCHEMATIC & MAP GENERATION
    def test_03_plotly_linear_corridor_generation(self):
        for div in SHARED_DIVISION_LOCATIONS:
            df_trains = get_active_trains_df(division=div)
            fig = render_live_corridor_map_plotly(df_trains, division=div)
            self.assertIsNotNone(fig)
            self.assertTrue(len(fig.data) > 0)

    # 3. AI BLOCK PLANNING ENGINE & EVALUATION
    def test_04_automatic_block_planning_engine(self):
        if AutomaticBlockPlanningEngine:
            engine = AutomaticBlockPlanningEngine()
            payload = {
                "request_id": "REG-TEST-001",
                "department": "Engineering",
                "request_type": "Track renewal activity",
                "section": "Vijayawada-SEC-01",
                "duration_minutes": 60,
                "preferred_start": "02:30",
                "line": "DOWN Line",
                "from_km": 114.0,
                "to_km": 118.0
            }
            res = engine.plan_single_request(payload)
            self.assertIsInstance(res, dict)
            self.assertIn("feasibility", res)
            self.assertIn(res["feasibility"], ["FEASIBLE", "INFEASIBLE"])

    # 4. SYSTEM DEPENDENCIES & SAFETY ISOLATION MATRIX
    def test_05_system_dependencies_and_isolation(self):
        # TRD OHE work requires isolation
        dep_trd, iso_trd = derive_system_dependencies_and_isolation("Overhead equipment replacement", "TRD")
        self.assertTrue(iso_trd)
        self.assertIn("OHE Power Isolation", dep_trd)

        # S&T Point machine work requires isolation & clamping
        dep_st, iso_st = derive_system_dependencies_and_isolation("Point machine maintenance", "S&T")
        self.assertTrue(iso_st)
        self.assertIn("Point machine clamping", dep_st)

        # Engineering Independent Emergency Weld
        dep_eng, iso_eng = derive_system_dependencies_and_isolation("Rail fracture emergency weld", "Engineering")
        self.assertIn("Emergency", dep_eng)

    # 5. DEPARTMENT MAINTENANCE SCHEDULE & MATRIX HTML
    def test_06_department_maintenance_schedules(self):
        df_weekly = get_full_schedule(horizon="weekly")
        df_monthly = get_full_schedule(horizon="monthly")
        self.assertIsInstance(df_weekly, pd.DataFrame)
        self.assertIsInstance(df_monthly, pd.DataFrame)

        for dept in ["Engineering", "S&T", "TRD"]:
            html_w = generate_ai_block_plan_matrix_html(df_weekly, current_dept=dept, color_mode="department")
            self.assertIsInstance(html_w, str)
            self.assertIn("matrixGridWrapper", html_w)

    # 6. SPECIALIZED AGENTS & DECISION MODULES
    def test_07_specialized_subsystem_agents(self):
        # Safety clearance certificate
        safety_agent = SafetyClearanceAgent()
        cert = safety_agent.generate_gsr_certificate(schedule_id=1, section_id="Vijayawada-SEC-01")
        self.assertIn("certificate_id", cert)
        self.assertIn("safety_checks", cert)

        # Track machine packer
        packer_agent = TrackMachinePackerAgent()
        pack = packer_agent.optimize_machine_blocks(section_id="Vijayawada-SEC-01")
        self.assertIn("overall_machine_efficiency_pct", pack)

        # Traction router under OHE power block
        trac_agent = TractionAwareRouterAgent()
        routes = trac_agent.route_traffic_under_ptw(section_id="Vijayawada-SEC-01")
        self.assertIsInstance(routes, list)

        # TSR lifecycle delay padding
        tsr_agent = TSRLifecycleAgent()
        tsr = tsr_agent.calculate_tsr_delay_padding(section_id="Vijayawada-SEC-01")
        self.assertIsInstance(tsr, list)

    # 7. DATABASE INTEGRITY & CORE TABLES
    def test_08_database_integrity(self):
        conn = get_db()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()

        expected_tables = [
            "users", "defects", "schedule", "corridor_slots", "notifications",
            "block_requests_v2", "block_feasibility_evaluations", "final_block_allocations",
            "system_dependency_matrix", "reported_defects", "live_train_status"
        ]
        for t in expected_tables:
            self.assertIn(t, tables, f"Mandatory table '{t}' is missing from database!")

if __name__ == "__main__":
    unittest.main()
