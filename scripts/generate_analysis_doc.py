# -*- coding: utf-8 -*-
import os
from fpdf import FPDF
from datetime import datetime

class AnalysisPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font('Helvetica', 'B', 8)
            self.set_text_color(100, 116, 139)
            self.cell(0, 6, 'TrackMind AI - Total System Analysis & Technology Stack (SIH 26027)', 0, 0, 'L')
            self.cell(0, 6, 'Indian Railways Block Planning', 0, 1, 'R')
            self.set_draw_color(226, 232, 240)
            self.line(15, self.get_y(), 195, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-14)
        self.set_font('Helvetica', '', 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 6, 'Confidential & Operational Prototype | Smart India Hackathon', 0, 0, 'L')
        self.cell(0, 6, f'Page {self.page_no()} of {{nb}}', 0, 0, 'R')

    def section_heading(self, number, title):
        self.ln(3)
        self.set_font('Helvetica', 'B', 11.5)
        self.set_fill_color(15, 23, 42)
        self.set_text_color(255, 255, 255)
        self.cell(0, 7, f'  {number}. {title}', 0, 1, 'L', fill=True)
        self.set_text_color(30, 41, 59)
        self.ln(2)

    def sub_heading(self, title):
        self.ln(1.5)
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(2, 132, 199)
        self.cell(0, 5.5, title, 0, 1, 'L')
        self.set_text_color(51, 65, 85)
        self.ln(1)

    def body_p(self, text):
        self.set_font('Helvetica', '', 8.5)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 4.2, text)
        self.ln(1.5)

    def bullet(self, title, desc):
        self.set_font('Helvetica', 'B', 8.5)
        self.set_text_color(15, 23, 42)
        w = self.get_string_width(title) + 5
        self.cell(4, 4.2, '-', 0, 0)
        self.cell(w, 4.2, title + ':', 0, 0)
        self.set_font('Helvetica', '', 8.5)
        self.set_text_color(71, 85, 105)
        self.multi_cell(0, 4.2, ' ' + desc)
        self.ln(1)

pdf = AnalysisPDF(orientation='P', unit='mm', format='A4')
pdf.alias_nb_pages()
pdf.set_auto_page_break(auto=True, margin=16)
pdf.set_margins(15, 15, 15)
pdf.add_page()

# Header banner
pdf.set_fill_color(11, 20, 38)
pdf.rect(15, 15, 180, 38, 'F')
pdf.set_xy(20, 19)
pdf.set_font('Helvetica', 'B', 17)
pdf.set_text_color(56, 189, 248)
pdf.cell(0, 7.5, 'TrackMind AI - Total System Analysis', 0, 1, 'L')
pdf.set_x(20)
pdf.set_font('Helvetica', 'B', 10.5)
pdf.set_text_color(255, 255, 255)
pdf.cell(0, 5.5, 'AI-Powered Automatic Block Planning for Indian Railways (SIH 26027)', 0, 1, 'L')
pdf.set_x(20)
pdf.set_font('Helvetica', '', 8)
pdf.set_text_color(148, 163, 184)
pdf.cell(0, 4.5, 'Architecture, Full Technology Stack, Optimization Algorithms & Multi-Agent Network', 0, 1, 'L')

pdf.set_xy(15, 56)
pdf.set_font('Helvetica', '', 8)
pdf.set_text_color(100, 116, 139)
pdf.cell(90, 4.5, f'Generated: {datetime.now().strftime("%B %d, %Y")}', 0, 0, 'L')
pdf.cell(90, 4.5, 'Author: Maguluri Manikanta / SIH 26027 Team', 0, 1, 'R')
pdf.set_draw_color(203, 213, 225)
pdf.line(15, 62, 195, 62)
pdf.ln(3)

# 1. Executive Summary
pdf.section_heading('1', 'Executive Overview & Problem Statement')
pdf.body_p('In Indian Railways, three core infrastructure departments constantly require track maintenance blocks (temporary corridor closures):')
pdf.bullet('Engineering (Track / P-Way)', 'Rail fractures, deep screening, track packing, rail renewal (tracked via TMS).')
pdf.bullet('Signal & Telecom (S&T)', 'Point machines, track circuits, axle counters, signals (tracked via SMMS).')
pdf.bullet('Traction Distribution (TRD)', 'OHE wire wear, catenary maintenance, power isolations (tracked via TDMS).')
pdf.body_p('Historically, these departments requested blocks in silos through BDMS with zero real-time cross-departmental coordination. This resulted in scheduling collisions, severe passenger train delays, and unexploited corridor windows. TrackMind AI solves this by unifying maintenance requests, train timetables, and goods traffic forecasts into an automated mathematical optimization and multi-agent AI system.')

# 2. Technology Stack
pdf.section_heading('2', 'Comprehensive Technology Stack Architecture')
headers = ['Layer', 'Technologies Used', 'Role & Operational Implementation']
widths = [30, 48, 102]

pdf.set_font('Helvetica', 'B', 8)
pdf.set_fill_color(30, 41, 59)
pdf.set_text_color(255, 255, 255)
for i, h in enumerate(headers):
    pdf.cell(widths[i], 5.8, f' {h}', 1, 0, 'L', fill=True)
pdf.ln(5.8)

rows = [
    ('Frontend UI', 'Streamlit (1.38+), Custom CSS3', 'Reactive full-stack web dashboard with dark glassmorphic styling and state management.'),
    ('Geospatial GIS', 'Folium (0.20+), Leaflet.js', 'Satellite multi-track map, station pill markers (DivIcon), live train positions & telemetry.'),
    ('Data Visualization', 'Plotly Express & Graph Objects', 'Interactive corridor Gantt timelines, capacity heatmaps, KPI meters, and defect charts.'),
    ('Voice & Audio', 'Web Speech API (STT / TTS)', 'Browser-native multilingual speech recognition & synthesis (English, Hindi, Telugu).'),
    ('Operations Research', 'Google OR-Tools CP-SAT', 'Constraint Programming engine ensuring zero collisions and timetable conflict avoidance.'),
    ('Machine Learning', 'Scikit-Learn (RandomForest, Isolation)', 'Failure risk prediction (RandomForest) and track anomaly defect clustering (IsolationForest).'),
    ('Data Processing', 'Pandas (2.2+), NumPy, Faker', 'Vectorized DataFrame transformations and 2,000+ realistic synthetic railway records.'),
    ('GenAI & LLM', 'Groq SDK (LLaMA-3.3-70B)', 'Sub-second AI reasoning with automated fallback to LLaMA-3.1-8B, Mixtral, and Gemma2.'),
    ('Knowledge RAG', 'Custom NL-to-SQL + Vector RAG', 'Live database querying engine against railway.db for zero-hallucination factual stats.'),
    ('Database & Storage', 'SQLite3 (WAL Mode)', 'Relational database with Write-Ahead Logging and 30s busy timeout for concurrent safety.'),
    ('Security & RBAC', 'Bcrypt (4.2+)', 'Salted password encryption and Role-Based Access Control (Admin, Eng, S&T, TRD).'),
    ('Reporting Engine', 'FPDF2 (2.8+)', 'Automated server-side generation of downloadable maintenance block PDF schedules.'),
    ('DevOps & Deploy', 'GitHub, Streamlit Cloud, Python 3.13', 'Continuous deployment with pinned runtime and automated dependency management.')
]

pdf.set_font('Helvetica', '', 7.5)
fill = False
for r in rows:
    pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(widths[0], 5.2, f' {r[0]}', 1, 0, 'L', fill=fill)
    pdf.cell(widths[1], 5.2, f' {r[1]}', 1, 0, 'L', fill=fill)
    pdf.cell(widths[2], 5.2, f' {r[2]}', 1, 1, 'L', fill=fill)
    fill = not fill

pdf.ln(2)

# 3. Optimization
pdf.section_heading('3', 'Mathematical Optimization Engine (Google OR-Tools CP-SAT)')
pdf.body_p('The scheduling core (scripts/optimizer.py) formulates maintenance planning as a binary integer constraint satisfaction and optimization problem (CP-SAT):')
pdf.bullet('Hard Constraint 1 (No Collisions)', 'Each corridor time slot can hold at most one maintenance block unless merged into an approved shadow block.')
pdf.bullet('Hard Constraint 2 (Train Timetable Protection)', 'Slots overlapping scheduled passenger train departures on the same section are purged via filter_slots_against_timetable().')
pdf.bullet('Hard Constraint 3 (Section & Duration Matching)', 'Tasks can only be scheduled into slots on their identical section ID with slot duration >= estimated task duration.')
pdf.bullet('Objective Function', 'Maximize cumulative Priority Score of all scheduled tasks across 7-day weekly and 30-day monthly rolling horizons.')

# 4. Machine Learning
pdf.section_heading('4', 'Predictive Risk & Defect Scoring (ML Layer)')
pdf.body_p('Every maintenance defect across TMS, SMMS, and TDMS undergoes dual scoring before reaching the solver (scripts/scoring_models.py):')
pdf.bullet('Priority Score (0-100)', 'Severity Weight (Critical=40, High=25, Medium=12, Low=5) + Overdue Factor (up to 30 pts) + Trains Affected Impact (up to 30 pts).')
pdf.bullet('Failure Risk Score (RandomForest)', 'Trained on historical failure features to compute the probability (0-100%) of in-service failure before scheduled repair.')
pdf.bullet('Final Priority Blending', 'Final Priority = 0.60 * Priority Score + 0.40 * Failure Risk Score.')
pdf.bullet('Anomaly Detection (IsolationForest)', 'Detects abnormal defect clustering per track section, automatically alerting controllers to systemic track degradation.')

# 5. Autonomous Agents
pdf.section_heading('5', '32 Autonomous Domain Agents')
pdf.body_p('The system deploys 32 specialized autonomous Python agents (scripts/agents.py) organized into functional clusters:')
pdf.bullet('Core Coordination', 'CoordinatorAgent, ReplanningAgent, TrafficAgent, DepartmentAgent (proposes departmental blocks).')
pdf.bullet('Safety & Compliance', 'ComplianceAgent (SLA and section conflict clustering), SafetyClearanceAgent (G&SR rules), AnomalyDetectionAgent.')
pdf.bullet('Locopilot & Speed', 'LocopilotSpeedAgent, TelemetrySimulatorAgent, DynamicHeadwayAgent, SingleLineWorkingAgent, TSRLifecycleAgent.')
pdf.bullet('Resource & Freight', 'TrackMachinePackerAgent, CrewHOERAgent (Hours of Employment Regulations), TractionAwareRouterAgent, FOISDemurrageAgent.')
pdf.bullet('Passenger & Dispatch', 'PassengerAdvisoryAgent (automated delay bulletins), CostOptimizationAgent, FeedbackLoopAgent.')

# 6. GenAI & Voice
pdf.section_heading('6', 'Multilingual Generative AI & Voice Assistant')
pdf.body_p('Integrated in app/chatbot.py for hands-free and natural language interaction:')
pdf.bullet('Groq LLaMA-3.3-70B API', 'Sub-second reasoning with strict 4-second timeout and multi-model fallback (LLaMA-3.1-8B, Mixtral, Gemma).')
pdf.bullet('Dynamic NL-to-SQL RAG', 'Converts plain English/Hindi/Telugu queries into verified live SQLite SELECT queries against railway.db.')
pdf.bullet('Voice STT & TTS', 'Web Speech API integration supporting English (en-IN), Hindi (hi-IN), and Telugu (te-IN) natively in-browser.')
pdf.bullet('Zero Hallucination Guard', 'Rigid domain prompting ensures the model never invents metrics, citing railway.db as the source of truth.')

# 7. Geographic Corridors
pdf.section_heading('7', 'Geospatial Multi-Division Corridors')
pdf.body_p('Dynamic satellite mapping and Gantt timelines support 4 prominent Indian Railways divisions:')
pdf.bullet('Khurda Road (KUR)', 'East Coast Railway (ECoR) - Main Trunk Cuttack-Bhubaneswar-Puri-Brahmapur network.')
pdf.bullet('Vijayawada (BZA)', 'South Central Railway (SCR) - High-density trunk route connecting Rajahmundry-Vijayawada-Tenali.')
pdf.bullet('Secunderabad (SC)', 'South Central Railway (SCR) - Kazipet-Secunderabad-Vikarabad passenger/freight crossroads.')
pdf.bullet('Howrah (HWH)', 'Eastern Railway (ER) - Suburban and mainline high-frequency corridor.')

# 8. Database & Security
pdf.section_heading('8', 'Database Reliability & Security')
pdf.bullet('SQLite WAL Mode', 'Enabled PRAGMA journal_mode=WAL and PRAGMA busy_timeout=30000 for concurrent non-blocking reads and writes.')
pdf.bullet('Role-Based Access Control', 'Bcrypt password hashing with strict separation between Central Controller and Engineering/S&T/TRD portals.')
pdf.bullet('Department Alert Isolation', 'Department users receive only role-specific alerts (e.g. S&T never sees OHE electrical notifications).')

# 9. Business Impact
pdf.section_heading('9', 'Business & Operational Impact on Indian Railways')
pdf.bullet('100% Conflict Elimination', 'Zero departmental clashes through mathematical constraint satisfaction.')
pdf.bullet('Punctuality Maximization', 'Train timetable departure protection eliminates passenger train detentions during maintenance windows.')
pdf.bullet('Capacity Expansion', 'Shadow block clustering allows Track, S&T, and TRD to work in unified windows, saving up to 35% corridor hours.')
pdf.bullet('Safety Governance', 'Automatic G&SR safety certificate generation ensures full statutory compliance before power restoration.')

out_pdf = 'TrackMind_AI_System_Analysis_and_TechStack.pdf'
pdf.output(out_pdf)
print('PDF created successfully:', os.path.abspath(out_pdf))
