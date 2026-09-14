"""
Generate TrackMind AI - Prototype Technical Specification PDF
Uses ReportLab to create a comprehensive, beautifully styled technical explanation PDF.
"""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

PDF_OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "TrackMind_AI_Prototype_Detailed_Explanation.pdf"
)

class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and render running headers, 
    footers, and total page numbers ('Page X of Y').
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        if self._pageNumber == 1:
            # Suppress headers/footers on the title page
            return

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))

        # Running Header
        self.drawString(54, 750, "TrackMind AI — Prototype Technical Specification & System Architecture")
        self.drawRightString(612 - 54, 750, "Smart India Hackathon • PS 26027")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 742, 612 - 54, 742)

        # Running Footer
        self.line(54, 45, 612 - 54, 45)
        self.setFont("Helvetica", 8)
        self.drawString(54, 32, "Confidential & Proprietary • Indian Railways AI Block Planning System")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 32, page_str)
        self.restoreState()


def create_explanation_pdf():
    doc = SimpleDocTemplate(
        PDF_OUTPUT_PATH,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    PRIMARY = colors.HexColor("#0f172a")     # Slate 900
    SECONDARY = colors.HexColor("#0284c7")   # Sky 600
    ACCENT = colors.HexColor("#1e3a8a")      # Blue 900
    TEXT_DARK = colors.HexColor("#1e293b")   # Slate 800
    TEXT_MUTED = colors.HexColor("#475569")  # Slate 600
    BG_LIGHT = colors.HexColor("#f8fafc")    # Slate 50
    BORDER_COLOR = colors.HexColor("#cbd5e1") # Slate 300

    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=PRIMARY,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=SECONDARY,
        spaceAfter=10
    )

    meta_style = ParagraphStyle(
        "CoverMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=TEXT_MUTED,
        spaceAfter=14
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=ACCENT,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=SECONDARY,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=TEXT_DARK,
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=TEXT_DARK,
        leftIndent=10,
        spaceAfter=3
    )

    story = []

    # =========================================================================
    # TITLE & HEADER SECTION
    # =========================================================================
    story.append(Paragraph("TrackMind AI — Full Prototype Technical Specification", title_style))
    story.append(Paragraph("AI-Powered Automatic Block Planning & Corridor Management System for Indian Railways", subtitle_style))
    story.append(Paragraph("<b>Smart India Hackathon • Problem Statement 26027</b> | System Architecture & Comprehensive Technical Documentation", meta_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=SECONDARY, spaceBefore=0, spaceAfter=10))

    # =========================================================================
    # SECTION 1: EXECUTIVE SUMMARY & PROBLEM STATEMENT
    # =========================================================================
    story.append(Paragraph("1. Executive Summary & Problem Statement", h1_style))
    story.append(Paragraph(
        "Indian Railways operates one of the densest rail networks globally. Maintenance disconnections ('blocks') "
        "are independently requested by three departments: <b>Engineering (Track/TMS)</b>, <b>Signal & Telecom (S&T/SMMS)</b>, "
        "and <b>Traction Distribution (TRD/TDMS)</b>. Operating in departmental silos via the Block Demand Management System (BDMS) "
        "creates critical operational inefficiencies:", body_style
    ))

    story.append(Paragraph("• <b>Departmental Conflicts:</b> Multiple departments request overlapping blocks on the same section at different times, causing redundant line shutdowns.", bullet_style))
    story.append(Paragraph("• <b>Timetable Disruption:</b> Uncoordinated blocks collide with scheduled passenger trains and high-priority freight rakes, escalating delay hours across railway divisions.", bullet_style))
    story.append(Paragraph("• <b>Asset Underutilization:</b> Heavy track machinery (tie tampers, ballast cleaners) sits idle awaiting manual safety clearance.", bullet_style))
    story.append(Paragraph("• <b>Lack of Real-Time Intelligence:</b> Maintenance decisions are reactive rather than predictive and risk-optimized.", bullet_style))

    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<b>The TrackMind AI Solution:</b> Our prototype introduces a fully automated, agentic AI block planning engine. "
        "It ingests multi-department defect records, corridor availability (COA), live timetables, and goods traffic forecasts. "
        "Using machine learning priority scoring, spatial anomaly detection, and a Google OR-Tools CP-SAT mathematical solver, "
        "TrackMind AI schedules maintenance blocks with <b>zero departmental collisions</b> and enforced timetable constraints while maximizing asset availability.", body_style
    ))

    story.append(Spacer(1, 6))

    # =========================================================================
    # SECTION 2: COMPLETE TECHNOLOGY STACK & TOOLS USED
    # =========================================================================
    story.append(Paragraph("2. Complete Technology Stack & Architecture ('What We Used')", h1_style))
    story.append(Paragraph("The system is engineered using open-source tools selected for performance, reliability, and ease of deployment:", body_style))

    tech_data = [
        [Paragraph("<b>Component Layer</b>", h2_style), Paragraph("<b>Technologies & Libraries Used</b>", h2_style), Paragraph("<b>Key Purpose & Functionality</b>", h2_style)],
        [Paragraph("<b>Frontend UI Framework</b>", body_style), Paragraph("Streamlit, HTML5, Custom CSS3, Plotly Express", body_style), Paragraph("Multi-role interactive dashboard (Admin, Engineering, S&T, TRD) with live Plotly Gantt timeline graphs.", body_style)],
        [Paragraph("<b>Backend & Relational DB</b>", body_style), Paragraph("Python 3.13, SQLite3 database", body_style), Paragraph("Lightweight relational database storing all defects, timetables, schedules, notifications, and audit logs.", body_style)],
        [Paragraph("<b>Optimization Engine</b>", body_style), Paragraph("Google OR-Tools (CP-SAT Solver)", body_style), Paragraph("Constraint programming solver enforcing hard zero-collision constraints and maximizing priority scores.", body_style)],
        [Paragraph("<b>Machine Learning Layer</b>", body_style), Paragraph("Scikit-Learn (RandomForest, IsolationForest), Pandas, NumPy", body_style), Paragraph("Predicts defect failure risk probability and identifies spatial defect clustering across 40 section IDs.", body_style)],
        [Paragraph("<b>Agentic AI Architecture</b>", body_style), Paragraph("Plain-Python OOP Framework (32 Agents)", body_style), Paragraph("Decoupled autonomous agents handling SLA compliance, cost optimization, crew rosters, and advisories.", body_style)],
        [Paragraph("<b>Conversational & Voice AI</b>", body_style), Paragraph("Groq Cloud API (llama-3.3-70b), Web Speech API", body_style), Paragraph("Multilingual voice assistant (English, Hindi, Telugu) and direct text-to-SQL time-window querying.", body_style)],
        [Paragraph("<b>Document & PDF Engine</b>", body_style), Paragraph("ReportLab, fpdf2", body_style), Paragraph("Generates official downloadable block summary reports, audit trails, and technical documentation.", body_style)],
        [Paragraph("<b>Synthetic Data Generator</b>", body_style), Paragraph("Faker, Python Random, DateTime", body_style), Paragraph("Generates 2,000+ realistic records per department across 40 sections in 5 railway divisions.", body_style)],
    ]

    t_tech = Table(tech_data, colWidths=[1.3*inch, 2.0*inch, 3.7*inch])
    t_tech.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BG_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_tech)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 3: DATA ARCHITECTURE & DATABASE SCHEMAS
    # =========================================================================
    story.append(Paragraph("3. Data Architecture & Database Schemas (`scripts/generate_data.py` & `setup_database.py`)", h1_style))
    story.append(Paragraph(
        "The system simulates realistic Indian Railways operations across <b>5 Divisions</b> "
        "(Secunderabad, Vijayawada, Guntakal, Guntur, Hyderabad) containing <b>40 Section IDs</b>. "
        "Data is persisted in an indexed SQLite database (`railway.db`).", body_style
    ))

    schema_data = [
        [Paragraph("<b>Database Table</b>", h2_style), Paragraph("<b>Key Columns / Attributes</b>", h2_style), Paragraph("<b>Description & Domain Purpose</b>", h2_style)],
        [Paragraph("<code>defects</code>", body_style), Paragraph("defect_id, department, section_id, defect_type, severity, reported_date, due_date, overdue_days, estimated_duration_hours, trains_affected_per_day, status, priority_score, risk_score", body_style), Paragraph("Registry of all disconnections requested by Engineering (TMS), S&T (SMMS), and TRD (TDMS). Stores ML score outputs.", body_style)],
        [Paragraph("<code>corridor_slots</code>", body_style), Paragraph("slot_id, section_id, date, start_time, end_time, duration_hours, slot_type, is_available", body_style), Paragraph("Corridor maintenance windows granted by Control Office (Day block, Night block, Maintenance window).", body_style)],
        [Paragraph("<code>train_timetable</code>", body_style), Paragraph("train_no, train_name, train_type, section_id, arrival_time, departure_time, frequency", body_style), Paragraph("Official passenger train movement timeline used as a hard constraint to prevent block collisions.", body_style)],
        [Paragraph("<code>goods_forecast</code>", body_style), Paragraph("forecast_id, section_id, date, expected_rakes, priority_level", body_style), Paragraph("Freight traffic demand forecasts (FOIS) protecting revenue-earning goods corridors from block overbooking.", body_style)],
        [Paragraph("<code>schedule</code>", body_style), Paragraph("schedule_id, defect_id, slot_id, section_id, department, planned_start, planned_end, horizon, status, decided_by", body_style), Paragraph("Final optimized block allocations output by CP-SAT solver and confirmed by Section Controllers.", body_style)],
        [Paragraph("<code>audit_log</code> & <code>notifications</code>", body_style), Paragraph("actor, action, details, timestamp, recipient_role, message, category, audience", body_style), Paragraph("Full audit trail recording agent decisions, controller overrides, and multi-department notification alerts.", body_style)],
    ]

    t_schema = Table(schema_data, colWidths=[1.2*inch, 2.8*inch, 3.0*inch])
    t_schema.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BG_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_schema)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 4: MACHINE LEARNING INTELLIGENCE LAYER
    # =========================================================================
    story.append(Paragraph("4. Machine Learning Intelligence Layer (`scripts/scoring_models.py`)", h1_style))
    story.append(Paragraph(
        "Prior to optimization, every defect is evaluated by a dual ML/rule-based intelligence pipeline:", body_style
    ))

    story.append(Paragraph("A. Multi-Factor Priority Scoring Model", h2_style))
    story.append(Paragraph(
        "Defect urgency is calculated using a multi-factor formula that balances safety severity, overdue delay, and operational impact:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>Priority Score</b> = Severity Weight + Overdue Component + Impact Component<br/>"
        "Where:<br/>"
        "• <b>Severity Weight:</b> Critical = 40, High = 25, Medium = 12, Low = 5.<br/>"
        "• <b>Overdue Component:</b> min(Overdue Days, 90) / 90 * 30 &nbsp;(scales 0–30 based on SLA overdue status).<br/>"
        "• <b>Impact Component:</b> min(Trains Affected per day, 50) / 50 * 30 &nbsp;(scales 0–30 based on corridor traffic density).", body_style
    ))

    story.append(Spacer(1, 3))
    story.append(Paragraph("B. Predictive Failure Risk Model (Random Forest)", h2_style))
    story.append(Paragraph(
        "A <code>RandomForestClassifier</code> (20 estimators, max depth 6) trains on historical defect features "
        "[<i>severity_component, overdue_component, impact_component, estimated_duration_hours</i>] to estimate the probability "
        "that a defect will fail prior to maintenance. "
        "The final ranking blends priority and predicted risk: <b>Final Score = 0.6 × Priority + 0.4 × Risk Probability</b>.", body_style
    ))

    story.append(Spacer(1, 3))
    story.append(Paragraph("C. Spatial Anomaly Detection Engine (Isolation Forest)", h2_style))
    story.append(Paragraph(
        "An <code>IsolationForest</code> model (contamination = 0.15) evaluates open defect counts and average overdue days across all 40 section IDs. "
        "Sections exhibiting abnormal defect clustering are flagged as infrastructure anomalies, notifying senior divisional engineers.", body_style
    ))

    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 5: MATHEMATICAL OPTIMIZATION ENGINE
    # =========================================================================
    story.append(Paragraph("5. Mathematical Optimization Engine (`scripts/optimizer.py`)", h1_style))
    story.append(Paragraph(
        "The scheduling engine utilizes <b>Google OR-Tools CP-SAT</b> (Constraint Programming - Satisfiability) "
        "to solve the combinatorial block allocation problem across weekly (7-day) and monthly (30-day) horizons.", body_style
    ))

    story.append(Paragraph("Mathematical Formulation & Hard Constraints:", h2_style))
    story.append(Paragraph("1. <b>Slot Capacity Constraint:</b> At most one defect task can be assigned to any corridor slot (zero departmental clashes).", bullet_style))
    story.append(Paragraph("2. <b>Task Uniqueness Constraint:</b> Each defect task is assigned to at most one slot per optimization cycle.", bullet_style))
    story.append(Paragraph("3. <b>Spatial & Duration Fit:</b> Task <i>i</i> can only pair with slot <i>j</i> if <code>defect.section_id == slot.section_id</code> and <code>defect.estimated_duration <= slot.duration</code>.", bullet_style))
    story.append(Paragraph("4. <b>Train Timetable Exclusion (Hard Constraint):</b> <code>filter_slots_against_timetable()</code> automatically filters out any slot whose window overlaps a scheduled passenger train departure on that section.", bullet_style))
    story.append(Paragraph("5. <b>Controller Lock Enforcement:</b> <code>filter_slots_against_locked_schedules()</code> excludes slots overlapping existing locked or controller emergency override schedules.", bullet_style))

    story.append(Spacer(1, 3))
    story.append(Paragraph("<b>Objective Function:</b> Maximize total scaled priority score of all scheduled maintenance tasks:<br/>"
                           "&nbsp;&nbsp;&nbsp;&nbsp;<b>Maximize</b> &sum;<sub>(i,j)</sub> (Priority Score<sub>i</sub> &times; 100) &middot; x<sub>i,j</sub>", body_style))

    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 6: AUTONOMOUS 32+ AGENT FRAMEWORK
    # =========================================================================
    story.append(Paragraph("6. Autonomous Agentic AI Layer (`scripts/agents.py`)", h1_style))
    story.append(Paragraph(
        "TrackMind AI incorporates a modular agent framework comprising <b>32 specialized autonomous agents</b> implemented as clean Python classes. "
        "Agents interact by updating state directly in SQLite database tables.", body_style
    ))

    agent_data = [
        [Paragraph("<b>Agent Category</b>", h2_style), Paragraph("<b>Key Autonomous Agents</b>", h2_style), Paragraph("<b>Responsibilities & Operational Logic</b>", h2_style)],
        [Paragraph("<b>Department Agents</b>", body_style), Paragraph("DepartmentAgent (Engg, S&T, TRD)", body_style), Paragraph("Filters, ranks, and submits department-specific block requests based on defect urgency.", body_style)],
        [Paragraph("<b>Core Coordination</b>", body_style), Paragraph("TrafficAgent, CoordinatorAgent, ReplanningAgent", body_style), Paragraph("Protects freight/timetable corridors, executes CP-SAT optimizer, and triggers dynamic re-planning when emergency defects occur.", body_style)],
        [Paragraph("<b>Governance & SLA</b>", body_style), Paragraph("DeadlineAlertAgent, ComplianceAgent, CostOptimizationAgent", body_style), Paragraph("Monitors overdue SLA days, tracks compliance percentages, and estimates economic impact of train delays.", body_style)],
        [Paragraph("<b>Field & Roster Ops</b>", body_style), Paragraph("CrewAvailabilityAgent, TrackMachinePackerAgent, LocopilotSpeedAgent", body_style), Paragraph("Verifies crew duty hours (HOER rules), schedules tie-tamping machines, and issues TSR speed restriction advisories.", body_style)],
        [Paragraph("<b>Network Capacity</b>", body_style), Paragraph("FreightInsertionAgent, SingleLineWorkingAgent, FOISDemurrageAgent, DeBunchingMeteringAgent", body_style), Paragraph("Inserts ad-hoc freight rakes during mini-gaps, manages single-line working on double tracks, and minimizes demurrage penalties.", body_style)],
        [Paragraph("<b>Safety & Risk</b>", body_style), Paragraph("SafetyClearanceAgent, OperationalRiskAgent, TSRLifecycleAgent", body_style), Paragraph("Enforces electrical/track safety clearances, calculates section risk indices, and manages Temporary Speed Restrictions.", body_style)],
    ]

    t_agent = Table(agent_data, colWidths=[1.3*inch, 2.2*inch, 3.5*inch])
    t_agent.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BG_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_agent)

    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>3-Tier Auto-Approval Risk Hierarchy:</b>", h2_style))
    story.append(Paragraph("• <b>Tier 1 (Low Risk):</b> Night blocks, duration &le; 2h, non-trunk sections. <i>Auto-approved and committed immediately.</i>", bullet_style))
    story.append(Paragraph("• <b>Tier 2 (Medium Risk):</b> Day blocks, duration 2–4h. <i>Provisional schedule generated; flagged for Section Controller confirmation.</i>", bullet_style))
    story.append(Paragraph("• <b>Tier 3 (High Risk):</b> Major trunk corridors, duration > 4h. <i>Requires manual emergency override by Senior Divisional Operations Manager (Sr. DOM).</i>", bullet_style))

    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 7: USER INTERFACE & MULTILINGUAL VOICE AI ASSISTANT
    # =========================================================================
    story.append(Paragraph("7. User Interface & Multilingual Voice AI Assistant (`app/main.py` & `chatbot.py`)", h1_style))
    story.append(Paragraph(
        "The frontend is built using Streamlit and provides a clean, role-based dashboard for railway controllers:", body_style
    ))

    story.append(Paragraph("• <b>Role-Based Dashboards:</b> Supports Admin (Central Controller, 10 full tabs), Engineering (Track), S&T, and TRD views with bcrypt password authentication.", bullet_style))
    story.append(Paragraph("• <b>Interactive Timeline & Plotly Analytics:</b> Visual Block Windows Timeline renders all maintenance tasks in zoomable Plotly Gantt charts with permanent axis labels.", bullet_style))
    story.append(Paragraph("• <b>Multilingual Voice AI Assistant:</b> Integrated right-side AI panel powered by Groq Cloud API (`llama-3.3-70b-versatile`) with automated model fallback. Utilizes the browser Web Speech API for voice recognition and text-to-speech in <b>English (`en-IN`)</b>, <b>Hindi (`hi-IN`)</b>, and <b>Telugu (`te-IN`)</b>.", bullet_style))
    story.append(Paragraph("• <b>Direct SQL Time-Window Querying:</b> Enables natural language queries such as <i>'What is scheduled between 2pm and 4pm on Vijayawada section?'</i> by parsing time windows directly into SQLite queries.", bullet_style))

    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 8: PDF REPORTING ENGINE
    # =========================================================================
    story.append(Paragraph("8. PDF Reporting Pipeline (`app/reports.py`)", h1_style))
    story.append(Paragraph(
        "TrackMind AI includes an automated PDF generation engine (`app/reports.py`) powered by <code>fpdf2</code>. "
        "Controllers can generate official, downloadable weekly and monthly block analysis reports detailing completion metrics, "
        "departmental summaries, and scheduled block details for executive reporting and audit compliance.", body_style
    ))

    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 9: STEP-BY-STEP BUILD PROCESS ("HOW WE MADE IT")
    # =========================================================================
    story.append(Paragraph("9. Step-by-Step Build Process ('How We Made It')", h1_style))
    story.append(Paragraph(
        "The development of TrackMind AI followed a structured 8-step engineering workflow:", body_style
    ))

    build_steps = [
        ("Step 1: Domain Analysis & Problem Definition", "Analyzed SIH Problem Statement 26027, mapping railway BDMS, TMS, SMMS, TDMS, and COA workflows to identify key pain points in disconnection planning."),
        ("Step 2: Synthetic Data Generation Pipeline", "Wrote `scripts/generate_data.py` using `faker` to synthesize 2,000+ records per dataset across 40 sections in 5 divisions, ensuring realistic defect distributions and timetable parameters."),
        ("Step 3: Database & Schema Initialization", "Developed `scripts/setup_database.py` to construct the indexed SQLite schema (`railway.db`), auto-load CSV datasets, and seed hashed default user credentials."),
        ("Step 4: Machine Learning Intelligence Layer", "Implemented `scripts/scoring_models.py` featuring the priority scoring algorithm, RandomForest failure risk estimator, and IsolationForest anomaly detector."),
        ("Step 5: Mathematical CP-SAT Optimizer Integration", "Built `scripts/optimizer.py` using Google OR-Tools CP-SAT solver, encoding slot uniqueness, duration fit, timetable clash prevention, and priority maximization."),
        ("Step 6: Agentic Architecture & Orchestration Workflow", "Created `scripts/agents.py` defining 32 specialized autonomous Python agents and the `CoordinatorAgent.run_cycle()` master execution flow."),
        ("Step 7: Streamlit Dashboard & Voice AI Integration", "Developed `app/main.py` and `app/chatbot.py` to deliver a multi-role UI, interactive Plotly Gantt timelines, Groq LLM integration, and Web Speech API voice synthesis."),
        ("Step 8: Automated PDF Reporting & End-to-End Testing", "Built `app/reports.py` for automated PDF report generation and created an end-to-end CLI test suite verifying scoring, optimization, and agent cycles."),
    ]

    for step_title, step_desc in build_steps:
        story.append(Paragraph(f"• <b>{step_title}:</b> {step_desc}", bullet_style))

    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 10: END-TO-END OPERATIONAL EXECUTION ("HOW IT HAPPENS STEP-BY-STEP")
    # =========================================================================
    story.append(Paragraph("10. End-to-End Operational Lifecycle ('How It Happens Step-by-Step')", h1_style))
    story.append(Paragraph(
        "When deployed in a Railway Central Control Office, a block request moves through an automated 7-step lifecycle:", body_style
    ))

    flow_data = [
        [Paragraph("<b>Step #</b>", h2_style), Paragraph("<b>Phase / Stage</b>", h2_style), Paragraph("<b>Operational Execution Details</b>", h2_style)],
        [Paragraph("<b>1</b>", body_style), Paragraph("<b>Defect Ingestion</b>", body_style), Paragraph("Engineering, S&T, and TRD log defect disconnections or voice-input tasks via BDMS/Streamlit dashboard into <code>defects</code> table.", body_style)],
        [Paragraph("<b>2</b>", body_style), Paragraph("<b>ML Scoring & Anomaly Flagging</b>", body_style), Paragraph("<code>compute_priority_scores()</code> computes priority scores and failure risks; <code>detect_anomalies()</code> flags defective track clusters.", body_style)],
        [Paragraph("<b>3</b>", body_style), Paragraph("<b>CP-SAT Optimization</b>", body_style), Paragraph("<code>run_optimizer()</code> filters slots against train timetables and locked schedules, then solves CP-SAT model to allocate blocks with zero clashes.", body_style)],
        [Paragraph("<b>4</b>", body_style), Paragraph("<b>Agent Conflict & SLA Check</b>", body_style), Paragraph("32 agents execute in cycle: TrafficAgent protects freight rakes, ComplianceAgent tracks SLAs, CrewAgent verifies rosters, SafetyAgent validates clearances.", body_style)],
        [Paragraph("<b>5</b>", body_style), Paragraph("<b>Controller Review & Approval</b>", body_style), Paragraph("Tier 1 auto-approves. Tier 2/3 flag provisional plans on Central Controller Dashboard for one-click confirmation or emergency override.", body_style)],
        [Paragraph("<b>6</b>", body_style), Paragraph("<b>Automated Advisory Dispatch</b>", body_style), Paragraph("PassengerAdvisoryAgent posts station bulletins; LocopilotSpeedAgent issues TSR advisories; CrewAgent dispatches machine operators.", body_style)],
        [Paragraph("<b>7</b>", body_style), Paragraph("<b>Real-Time Tracking & Audit</b>", body_style), Paragraph("Field engineers mark completion; FeedbackLoopAgent updates defect status; Audit log records complete execution history.", body_style)],
    ]

    t_flow = Table(flow_data, colWidths=[0.6*inch, 1.8*inch, 4.6*inch])
    t_flow.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BG_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_flow)

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=0, spaceAfter=8))
    story.append(Paragraph("<b>End of Technical Specification Document</b> • Generated for TrackMind AI Prototype Review.", ParagraphStyle("Ending", parent=body_style, alignment=1, textColor=TEXT_MUTED)))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated at: {PDF_OUTPUT_PATH}")

if __name__ == "__main__":
    create_explanation_pdf()
