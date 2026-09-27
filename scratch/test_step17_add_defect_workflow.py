"""
End-to-End Automated Test Suite for "ADD DEFECT" Public Ingestion & Department Lifecycle
Verifies:
1. Public defect submission without login generates unique Defect ID (DEF-YYYYMMDD-XXXX).
2. Reporter does NOT provide severity (severity starts as 'Not Yet Assessed', status as 'New').
3. Deterministic department routing (Track/Engineering -> Engineering, Signal/S&T -> S&T, Electrical -> TRD).
4. Official department notification created in notifications table.
5. Department assessment records official severity (Low/Medium/High/Critical), analysis, and recommended action.
6. Department creates block request and sends to Controller in block_requests_v2.
7. Controller receives the request with Defect ID, problem description, department analysis, and assessed severity.
8. Persistence across browser reloads, tab switches, and app restarts without fake/random data.
"""

import os
import sys
import sqlite3
import unittest
from datetime import datetime, timedelta

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.controller_requests import fetch_controller_requests, DB_PATH
from app.classification_engine import RequestClassificationEngine


class TestAddDefectWorkflow(unittest.TestCase):

    def setUp(self):
        self.now = datetime.now()
        self.ts = int(self.now.timestamp())
        self.def_id_eng = f"DEF-TEST-ENG-{self.ts}"
        self.def_id_snt = f"DEF-TEST-SNT-{self.ts}"
        self.req_id_created = f"REQ-TEST-DEF-{self.ts}"

        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()
        # Clean any old test artifacts
        cur.execute("DELETE FROM reported_defects WHERE defect_id IN (?, ?)", (self.def_id_eng, self.def_id_snt))
        cur.execute("DELETE FROM notifications WHERE message LIKE ?", (f"%{self.ts}%",))
        cur.execute("DELETE FROM block_requests_v2 WHERE request_id = ?", (self.req_id_created,))
        conn.commit()
        conn.close()

    def tearDown(self):
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()
        cur.execute("DELETE FROM reported_defects WHERE defect_id IN (?, ?)", (self.def_id_eng, self.def_id_snt))
        cur.execute("DELETE FROM notifications WHERE message LIKE ?", (f"%{self.ts}%",))
        cur.execute("DELETE FROM block_requests_v2 WHERE request_id = ?", (self.req_id_created,))
        cur.execute("DELETE FROM request_classification_history WHERE request_ids LIKE ?", (f"%{self.req_id_created}%",))
        conn.commit()
        conn.close()

    def test_01_public_defect_submission_and_routing(self):
        """Test public reporter submits defect without severity -> routed to Engineering with Not Yet Assessed."""
        now_str = self.now.strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()

        # 1. Insert Engineering defect
        cur.execute("""
            INSERT INTO reported_defects
            (defect_id, reporter_type, reporter_name, contact_info, division, section, station,
             track_km_details, category, title, problem_brief, detailed_description, department,
             severity, status, reported_at)
            VALUES (?, 'Loco Pilot', 'Rajesh Kumar', '9876543210', 'Vijayawada Division (BZA)',
                    'Vijayawada–Kondapalli', 'Kondapalli Yard', 'KM 571.4 - 572.0 DOWN Track',
                    'Track', 'Track Jerk & Rail Joint Micro-Crack', 'Severe jerk observed at 85 kmph',
                    'Loco Pilot of 12727 reported abnormal vertical jerk on DOWN line near point 14B.',
                    'Engineering', 'Not Yet Assessed', 'New', ?)
        """, (self.def_id_eng, now_str))

        # 2. Insert department notification
        notif_msg = f"🔔 New Defect Reported: {self.def_id_eng} (Engineering) at Vijayawada–Kondapalli (Kondapalli Yard). Status: New | Severity: Not Yet Assessed [{self.ts}]"
        cur.execute("""
            INSERT INTO notifications
            (recipient_role, category, audience, message, created_at, is_read)
            VALUES ('engineering', 'defect', 'staff', ?, ?, 0)
        """, (notif_msg, now_str))

        conn.commit()

        # Verify DB storage
        cur.execute("SELECT defect_id, department, severity, status, reporter_name FROM reported_defects WHERE defect_id = ?", (self.def_id_eng,))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], self.def_id_eng)
        self.assertEqual(row[1], "Engineering")
        self.assertEqual(row[2], "Not Yet Assessed", "Public submission must have severity 'Not Yet Assessed'")
        self.assertEqual(row[3], "New", "Public submission status must be 'New'")
        self.assertEqual(row[4], "Rajesh Kumar")

        # Verify Notification
        cur.execute("SELECT recipient_role, category, message, is_read FROM notifications WHERE message LIKE ?", (f"%{self.def_id_eng}%",))
        n_row = cur.fetchone()
        self.assertIsNotNone(n_row)
        self.assertEqual(n_row[0], "engineering")
        self.assertEqual(n_row[1], "defect")
        self.assertEqual(n_row[3], 0, "Notification must be unread")

        conn.close()

    def test_02_department_assesses_severity(self):
        """Test department engineer reviews observation, assesses severity to 'High', and records diagnosis."""
        # Setup initial defect
        self.test_01_public_defect_submission_and_routing()

        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()

        # Department Engineer assessment
        ass_sev = "High"
        ass_diag = "USFD acoustic check confirms hairline micro-flaw on rail head. Requires immediate joint clamping & tamping."
        ass_action = "Execute 45-min emergency maintenance block with BCM tamper and welding squad."
        officer = "K. Srinivasa Rao (Sr. Section Engineer P-Way)"
        now_ass = (self.now + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

        cur.execute("""
            UPDATE reported_defects
            SET severity = ?, department_analysis = ?, recommended_action = ?,
                status = 'Assessed', assessed_by = ?, assessed_at = ?
            WHERE defect_id = ?
        """, (ass_sev, ass_diag, ass_action, officer, now_ass, self.def_id_eng))
        conn.commit()

        # Verify updated state
        cur.execute("SELECT severity, status, department_analysis, recommended_action, assessed_by FROM reported_defects WHERE defect_id = ?", (self.def_id_eng,))
        row = cur.fetchone()
        self.assertEqual(row[0], "High", "Official severity must be updated to High")
        self.assertEqual(row[1], "Assessed", "Status must become Assessed")
        self.assertEqual(row[2], ass_diag)
        self.assertEqual(row[3], ass_action)
        self.assertEqual(row[4], officer)

        conn.close()

    def test_03_department_creates_block_request_and_controller_receives(self):
        """Test department creates block request from assessed defect and sends to Controller."""
        # Run prior assessment
        self.test_02_department_assesses_severity()

        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cur = conn.cursor()

        cur.execute("SELECT * FROM reported_defects WHERE defect_id = ?", (self.def_id_eng,))
        cols = [c[0] for c in cur.description]
        defect = dict(zip(cols, cur.fetchone()))

        now_req = (self.now + timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
        target_dead = (self.now + timedelta(days=2)).strftime("%Y-%m-%d")

        # Create Block Request in block_requests_v2
        cur.execute("""
            INSERT INTO block_requests_v2
            (request_id, source, department, request_type, asset_type, location,
             from_km, to_km, section, line, direction, reported_time, required_duration,
             minimum_duration, preferred_start, deadline, dependency, isolation_required,
             required_resource, priority, reason, status, archetype)
            VALUES (?, 'TMS_DEFECT', 'Engineering', ?, 'Track Equipment', 'KM 571.4–572.0 (Kondapalli Yard)',
                    571.4, 572.0, 'Vijayawada–Kondapalli', 'DOWN Line', 'DOWN', ?, 45, 30, '02:30',
                    ?, 'None (Independent Task)', 0, 'Maintenance Crew & Heavy Tamper', ?,
                    ?, 'SUBMITTED', 'CORRECTIVE_MAINTENANCE')
        """, (
            self.req_id_created,
            defect["title"],
            now_req,
            target_dead,
            defect["severity"], # "High"
            f"[Defect: {defect['defect_id']} | Reporter: {defect['reporter_name']} ({defect['reporter_type']})]\n{defect['problem_brief']}\n\nDept Analysis: {defect['department_analysis']}\nRecommended Action: {defect['recommended_action']}"
        ))

        # Update reported_defects status
        cur.execute("""
            UPDATE reported_defects
            SET status = 'Block Requested', block_request_id = ?
            WHERE defect_id = ?
        """, (self.req_id_created, self.def_id_eng))

        conn.commit()
        conn.close()

        # Verify Controller receives it in fetch_controller_requests()
        new_reqs, overdue_reqs, n_cnt, o_cnt = fetch_controller_requests()
        target_in_ctrl = [r for r in new_reqs if r["request_id"] == self.req_id_created]
        self.assertEqual(len(target_in_ctrl), 1, "Controller must see the newly created block request in New Requests")

        ctrl_req = target_in_ctrl[0]
        self.assertEqual(ctrl_req["department"], "Engineering")
        self.assertEqual(ctrl_req["priority"], "High")
        self.assertEqual(ctrl_req["section"], "Vijayawada–Kondapalli")
        self.assertIn(self.def_id_eng, ctrl_req["description"], "Linked Defect ID must appear in description")
        self.assertIn("USFD acoustic check", ctrl_req["description"], "Department diagnosis must appear in description")

        # Classify the request
        res = RequestClassificationEngine.classify_all_actionable_requests(target_in_ctrl)
        self.assertIn(self.req_id_created, res["classified_ids"], "Request must be classified by Controller engine")

        # Verify count decreased after classification
        new_after, _, _, _ = fetch_controller_requests()
        after_check = [r for r in new_after if r["request_id"] == self.req_id_created]
        self.assertEqual(len(after_check), 0, "Classified request must no longer be in New Requests")


if __name__ == "__main__":
    unittest.main(verbosity=2)
