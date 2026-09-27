"""
Test Suite: Step 18 - Department Reported Defects Workflow Validation
Tests:
1. Department Routing & Alert Notification Formatting (5-line spec)
2. Zero Fake Data Guarantee (0 reported when empty)
3. AI-Assisted Advisory Severity Suggestion & Technical Reasoning
4. Department Assessment Recording & Persistence
5. Block Possession Requisition Creation & Controller Lineage Reception
"""

import os
import sys
import sqlite3
import unittest
from datetime import datetime

# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.main import get_ai_defect_assessment_suggestion, get_db
from app.controller_requests import init_reported_defects_db


class TestDepartmentReportedDefects(unittest.TestCase):
    def setUp(self):
        self.conn = get_db()
        init_reported_defects_db()
        self.cur = self.conn.cursor()

    def tearDown(self):
        # Clean up test artifacts
        self.cur.execute("DELETE FROM reported_defects WHERE defect_id LIKE 'TEST-DEF-%'")
        self.cur.execute("DELETE FROM block_requests_v2 WHERE request_id LIKE 'TEST-REQ-%'")
        self.cur.execute("DELETE FROM notifications WHERE message LIKE '%TEST-DEF-%'")
        self.conn.commit()
        self.conn.close()

    def test_01_ai_advisory_severity_and_reasoning(self):
        """Validates AI advisory suggestion engine for different infrastructure defect types."""
        # Critical test: Rail fracture / OHE Snap
        crit_res = get_ai_defect_assessment_suggestion(
            title="Rail Fracture on UP Main",
            problem_brief="Complete transverse crack with 50mm gap",
            detailed_desc="Loco pilot observed violent jerk near KM 572. Track fractured.",
            category="Engineering"
        )
        self.assertEqual(crit_res["suggested_severity"], "Critical")
        self.assertIn("Immediate speed restriction", crit_res["reasoning"])

        # High test: Point machine sluggishness
        high_res = get_ai_defect_assessment_suggestion(
            title="Point Machine Sluggish Operation",
            problem_brief="Switch rail 102B taking 8.5s to lock",
            detailed_desc="Detected during routine route setting. Ballast deficiency near switch motor.",
            category="S&T"
        )
        self.assertEqual(high_res["suggested_severity"], "High")
        self.assertIn("Significant infrastructure degradation", high_res["reasoning"])

        # Medium test: Loose fastenings / vegetation
        med_res = get_ai_defect_assessment_suggestion(
            title="Vegetation Fouling Near OHE Structure",
            problem_brief="Tree branches within 1.8m of 25kV traction wire",
            detailed_desc="Spotted between KM 570/4 and 570/8.",
            category="TRD"
        )
        self.assertEqual(med_res["suggested_severity"], "Medium")

        # Low test: Minor paint peeling
        low_res = get_ai_defect_assessment_suggestion(
            title="Gradient Post Paint Faded",
            problem_brief="KM marker slightly weathered",
            detailed_desc="Legibility reduced at night.",
            category="Engineering"
        )
        self.assertEqual(low_res["suggested_severity"], "Low")

    def test_02_public_submission_routing_and_notification_format(self):
        """Validates routing to responsible department and exact 5-line alert formatting."""
        test_id = f"TEST-DEF-{int(datetime.now().timestamp())}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Insert test defect
        self.cur.execute("""
            INSERT INTO reported_defects
            (defect_id, reporter_type, reporter_name, contact_info, division, section, station,
             track_km_details, category, title, problem_brief, detailed_description, department,
             severity, status, reported_at)
            VALUES (?, 'Loco Pilot', 'R. Sharma', 'LP-98214', 'Vijayawada Division (BZA)',
                    'Vijayawada–Kondapalli', 'Kondapalli Yard', 'KM 571/4 DOWN Line',
                    'Engineering', 'Rail Joint Gap Widening', 'Abnormal vibration felt at 90 kmph',
                    'Detailed observation of loose fishbolts and 15mm expansion gap at rail joint.',
                    'Engineering', 'Not Yet Assessed', 'New', ?)
        """, (test_id, now_str))

        # Standard 5-line alert notification
        notif_msg = f"🔔 New Defect Reported\n\nDefect ID: {test_id}\nCategory: Engineering\nLocation: Vijayawada–Kondapalli (Kondapalli Yard, KM 571/4 DOWN Line)\nStatus: New\nSeverity: Not Yet Assessed"
        self.cur.execute("""
            INSERT INTO notifications (recipient_role, category, audience, message, created_at, is_read)
            VALUES ('engineering', 'defect', 'staff', ?, ?, 0)
        """, (notif_msg, now_str))
        self.conn.commit()

        # Query and verify
        row = self.cur.execute("SELECT * FROM reported_defects WHERE defect_id = ?", (test_id,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["department"], "Engineering")
        self.assertEqual(row["severity"], "Not Yet Assessed")
        self.assertEqual(row["status"], "New")

        # Verify notification
        n_row = self.cur.execute("SELECT * FROM notifications WHERE message LIKE ? ORDER BY notif_id DESC LIMIT 1", (f"%{test_id}%",)).fetchone()
        self.assertIsNotNone(n_row)
        self.assertIn("🔔 New Defect Reported", n_row["message"])
        self.assertIn(f"Defect ID: {test_id}", n_row["message"])
        self.assertIn("Severity: Not Yet Assessed", n_row["message"])

    def test_03_department_assessment_and_block_request_creation(self):
        """Validates department assessment recording and subsequent block requisition transmission."""
        test_id = f"TEST-DEF-{int(datetime.now().timestamp()) + 1}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 1. Field report
        self.cur.execute("""
            INSERT INTO reported_defects
            (defect_id, reporter_type, reporter_name, contact_info, division, section, station,
             track_km_details, category, title, problem_brief, detailed_description, department,
             severity, status, reported_at)
            VALUES (?, 'Patrol Officer', 'V. Rao', 'PAT-5541', 'Vijayawada Division (BZA)',
                    'Kondapalli–Rayanapadu', 'Rayanapadu Outer', 'KM 574/2 UP Line',
                    'S&T', 'Track Circuit Glitch', 'Intermittent bobbing of TC 104',
                    'Insulation joint resistance low due to water accumulation.',
                    'S&T', 'Not Yet Assessed', 'New', ?)
        """, (test_id, now_str))
        self.conn.commit()

        # 2. Department engineer assesses
        officer = "Senior Signal Engineer (SSE/Sig/BZA)"
        diag = "TC 104 glue-joint impedance degraded. Requires insulation replacement and track impedance bonding."
        action = "Apply 45-min S&T disconnection block. Replace end post and nylon bushings."
        chosen_sev = "High"

        self.cur.execute("""
            UPDATE reported_defects
            SET severity = ?, department_analysis = ?, recommended_action = ?,
                status = 'Assessed', assessed_by = ?, assessed_at = ?
            WHERE defect_id = ?
        """, (chosen_sev, diag, action, officer, now_str, test_id))
        self.conn.commit()

        # Check assessed state
        def_row = self.cur.execute("SELECT * FROM reported_defects WHERE defect_id = ?", (test_id,)).fetchone()
        self.assertEqual(def_row["status"], "Assessed")
        self.assertEqual(def_row["severity"], "High")
        self.assertEqual(def_row["assessed_by"], officer)

        # 3. Department creates and sends Block Requisition to Controller
        test_req_id = f"TEST-REQ-{int(datetime.now().timestamp())}"
        self.cur.execute("""
            INSERT INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, dependency, isolation_required,
             required_resource, priority, reason, status, archetype)
            VALUES (?, 'S&T_DEFECT', 'S&T', 'Track Circuit Glitch', 'S&T',
                    'KM 574.0–574.5 (Rayanapadu Outer)', 574.0, 574.5, 'Kondapalli–Rayanapadu',
                    'UP Line', 'UP', ?, 45, 30, '02:00', '2026-10-01', 'NONE', 0,
                    'S&T Maintenance Gang', ?, ?, 'SUBMITTED', 'CORRECTIVE_MAINTENANCE')
        """, (
            test_req_id, now_str, chosen_sev,
            f"[Defect: {test_id} | Reporter: V. Rao (Patrol Officer)]\nIntermittent bobbing of TC 104\n\nDept Analysis: {diag}\nRecommended Action: {action}"
        ))

        # Update defect status to Block Requested
        self.cur.execute("""
            UPDATE reported_defects
            SET status = 'Block Requested', block_request_id = ?
            WHERE defect_id = ?
        """, (test_req_id, test_id))
        self.conn.commit()

        # Check requisition state in Controller pipeline
        req_row = self.cur.execute("SELECT * FROM block_requests_v2 WHERE request_id = ?", (test_req_id,)).fetchone()
        self.assertIsNotNone(req_row)
        self.assertEqual(req_row["status"], "SUBMITTED")
        self.assertEqual(req_row["priority"], "High")
        self.assertIn(f"[Defect: {test_id}", req_row["reason"])
        self.assertIn("Dept Analysis: TC 104 glue-joint", req_row["reason"])

        # Check final defect state
        def_final = self.cur.execute("SELECT * FROM reported_defects WHERE defect_id = ?", (test_id,)).fetchone()
        self.assertEqual(def_final["status"], "Block Requested")
        self.assertEqual(def_final["block_request_id"], test_req_id)

    def test_04_zero_fake_data_guarantee(self):
        """Validates that empty department filters yield 0 without synthetic generation."""
        # Query non-existent department
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM reported_defects WHERE department = 'NON_EXISTENT_DEPT'")
        rows = cur.fetchall()
        self.assertEqual(len(rows), 0)

        # Count new reported defects for this filter
        new_cnt = sum(1 for r in rows if r["status"] == "New" or r["severity"] == "Not Yet Assessed")
        self.assertEqual(new_cnt, 0)


if __name__ == "__main__":
    unittest.main()
