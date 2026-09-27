# Automatic Block Planning & Disconnection Management System (BDMS)
### AI-Powered Multi-Department Railway Corridor Optimization & Asset Availability Platform
**Ministry of Railways | Indian Railways Network**  
*Aligned with Smart India Hackathon Problem Statement 26027*

---

## 1. Project Title
**Automatic Block Planning & Disconnection Management System (BDMS)**  
*(Also referred to as TrackMind AI / RailFlow BDMS Engine)*

---

## 2. Project Overview
In Indian Railways, railway corridors operate at high traffic densities with express, passenger, and freight trains sharing tracks with critical infrastructure maintenance needs. Infrastructure maintenance requires temporary corridor closures termed **"Blocks"** or **"Disconnections"**.

Historically, maintenance planning has been fragmented: individual engineering departments submitted block requisitions independently through siloed channels without automated cross-departmental scheduling, timetable conflict checking, or combined execution.

**BDMS** transforms decentralized maintenance requests into an automated, mathematically optimized, and safety-verified corridor management system. It unifies public field defect reporting, departmental engineering assessments, automated candidate group classification, mathematical constraint optimization (Google OR-Tools CP-SAT), real-time GIS train monitoring, and multilingual AI decision support into a single operational platform.

---

## 3. Problem Statement
Three primary infrastructure maintenance departments independently request track possession:
1. **Engineering (Permanent Way / Track / TMS)**: Rail fracture repairs, deep screening, track tamping, weld renewal, turnouts, and bridge maintenance.
2. **Signal & Telecom (S&T / SMMS)**: Electronic interlocking, point machines, track circuits, axle counters, and signals.
3. **Traction Distribution (TRD / Electrical / TDMS)**: Overhead Equipment (OHE) wire replacement, catenary dropper inspection, insulator wash, and power isolation.

### Key Operational Challenges:
- **Scheduling Clashes**: Uncoordinated departmental possession requests competing for the same track section.
- **Punctuality Loss**: Unplanned or overlapping maintenance blocks delaying high-density passenger and freight traffic.
- **Underutilized Possession Windows**: Inability to systematically co-locate multiple department tasks into synchronized **Shadow Blocks** (e.g. TRD power isolation alongside Track tamping).
- **Manual Dependency Bottlenecks**: Section Controllers spending excessive operational time manually assessing safety interlocks, isolation protocols, and overdue maintenance backlogs.

---

## 4. Key Objectives
- **Zero Collision Guarantee**: Mathematically eliminate simultaneous conflicting block grants on the same track segment.
- **Punctuality & Timetable Protection**: Automatically verify block feasibility against live passenger timetables, scheduled departures, and section headways.
- **Unified Public & Field Defect Gateway**: Provide a public intake portal for Loco Pilots, Patrol Officers, and field personnel with strict separation of observation from severity assessment.
- **Departmental Assessment Authority**: Enable department engineers to analyze technical hazards, receive advisory AI recommendations, and record official severity before generating block requests.
- **Automated Candidate Group Classification**: Categorize unprocessed requisitions into **Isolation**, **Parallel**, **Sequential**, and **Review** archetypes with full database persistence.
- **Multi-Division Geographic Visualization**: Deliver interactive Folium GIS corridor maps with live train positions, block occupancy, and station pill markers.
- **Multilingual Decision Support**: Provide voice-enabled AI assistance in English, Hindi, and Telugu powered by Groq LLaMA 3.3 70B with verified live SQL execution.

---

## 5. Key Features

| Domain | Implemented Features |
| :--- | :--- |
| **Authentication & Access** | • Role-Based Access Control (RBAC) via salted Bcrypt hashing.<br>• Quick Department Access for rapid demonstration.<br>• View Mode toggle on login page: `[ 🔐 Login ]` and `[ ⚠️ Add Defect ]`. |
| **Public Defect Intake** | • Wide horizontal 1160px desktop reporting form.<br>• Structured inputs: Reporter Details, Location & Chainage, Defect Details.<br>• **Defect Category restricted strictly to 3 departments**: `Engineering`, `S&T`, `TRD`.<br>• **Zero Severity Input**: Reporter provides only factual observations; severity defaults to `Not Yet Assessed`.<br>• Generates unique Defect ID (`DEF-YYYYMMDD-XXXX`), routes to responsible department, and creates standardized 5-line alert notifications. |
| **Department Portals** | • Dedicated interfaces for **Engineering (TMS)**, **S&T (SMMS)**, and **TRD (TDMS)**.<br>• Real-time KPI metrics with zero fake data (Total, Pending Assessment, Assessed, Block Requested).<br>• **Reported Defects Tab**: Full field observation inspection.<br>• **AI Advisory Suggestion Engine**: Analyzes keywords and safety hazards to provide `AI Suggested Severity` and technical reasoning with an interactive `[ Accept AI Suggestion ]` button.<br>• **Department Technical Assessment**: Official severity selector (`Low`, `Medium`, `High`, `Critical`), technical diagnosis, and recommended action text areas.<br>• **Block Requisition Creation**: Auto-populates defect data, duration, track line, and target date, and transmits requisition to Section Controller (`status = 'SUBMITTED'`).<br>• **My Requests & Pending Tabs**: Real-time possession status tracking and department notification feeds. |
| **Section Controller Portal** | • **Department Requests (Step 5)**: Split into **NEW REQUESTS** and **OVERDUE REQUESTS** with dynamic overdue duration computation (e.g. `16h 32m`).<br>• **Defect Lineage Display**: Visual callout linking Defect ID, reporter observations, department diagnosis, and assessed severity.<br>• **Candidate Group Preprocessing & Classification (Step 6)**: Automated derivation of safety dependencies (S&T point disconnection, TRD power isolation) and classification into `ISOLATION`, `PARALLEL`, `SEQUENTIAL`, and `REVIEW` with full SQLite persistence.<br>• **Block Allocation Engine (Step 7)**: Slot feasibility evaluation, timetable conflict filtering, and AI decision support ranking.<br>• **Controller Confirmation & Multi-Alternative Selection (Step 8)**: Punctuality delay metrics and confirmation workflow.<br>• **Live Allocation Synchronization (Step 9)**: Generates targeted department notifications with delivery state tracking. |
| **Geospatial GIS Engine** | • Interactive satellite multi-track maps powered by Folium & Leaflet.js.<br>• 4 Operational Divisions: **Vijayawada (BZA)**, **Khurda Road (KUR)**, **Secunderabad (SC)**, and **Howrah (HWH)**.<br>• Live train vector movement, color-coded block occupancy, and station pill markers. |
| **ChatMind AI Copilot** | • Floating multilingual conversational assistant accessible across all dashboard pages.<br>• Supported Languages: **English**, **Hindi (`hi-IN`)**, and **Telugu (`te-IN`)** with Web Speech API voice mic.<br>• Intent Parser & Dynamic SQL RAG: Single train lookup, delayed train queries, department comparisons, KPI metrics, and specific defect/request lookup. |
| **Data Integrity & Testing** | • SQLite `railway.db` with WAL mode and robust foreign key relationships.<br>• **18 Automated Test Suites** (`scratch/run_all_step_tests.py`) covering Steps 2–18 with **241/241 tests passing (100% success)**. |

---

## 6. User Roles & Access Hierarchy

```
                               ┌────────────────────────┐
                               │   Indian Railways BDMS  │
                               └───────────┬────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         │                                 │                                 │
┌────────▼────────┐               ┌────────▼────────┐               ┌────────▼────────┐
│  Public / Field │               │   Department    │               │     Section     │
│    Personnel    │               │    Engineers    │               │   Controller    │
└────────┬────────┘               └────────┬────────┘               └────────┬────────┘
         │                                 │                                 │
  • Loco Pilots                     • Engineering (TMS)               • Central Traffic
  • Patrol Officers                 • S&T (SMMS)                        Controller
  • Station Staff                   • TRD / Traction (TDMS)           • Full Corridor Map
  • Public Intake                   • Severity Assessment             • Request Approval
  • Zero Login                      • Requisition Creation            • AI Decision Queue
```

| Role | Username | Default Password | Scope of Responsibility |
| :--- | :--- | :--- | :--- |
| **Central Controller** | `admin1` | `admin123` | Central Section Controller. Oversees Department Requests, candidate classification, block allocations, live corridor maps, and timetable conflict resolutions. |
| **Engineering (Track)** | `engineer1` | `engineer123` | Sr. Section Engineer (Permanent Way). Receives track defect reports, performs engineering assessments, and submits traffic block requisitions. |
| **Signal & Telecom (S&T)** | `signal1` | `signal123` | Sr. Section Engineer (Signal & Telecom). Reviews interlocking and signal defects, determines severity, and requests S&T disconnection blocks. |
| **Traction Distribution (TRD)**| `traction1` | `traction123` | Sr. Section Engineer (Traction Distribution). Reviews OHE and electrical reports, conducts technical analysis, and requests power isolation blocks. |
| **Public / Field Reporter** | *None required* | *None required* | Field staff, Loco Pilots, Patrol Officers, or public users submitting factual defect observations without login credentials. |

---

## 7. End-to-End Operational Workflow

```
[ Field Observation ]
        │ (Loco Pilot / Patrol Officer observes track, signal, or OHE defect)
        ▼
[ Public Add Defect Gateway ]
        │ (Submits factual details; Category: Engineering, S&T, or TRD; No severity input)
        ▼
[ Deterministic Department Routing ]
        │ (Generates DEF-YYYYMMDD-XXXX, persists in SQLite, dispatches 5-line alert notification)
        ▼
[ Department Portal Assessment ]
        │ (Engineer inspects observations, reviews AI Advisory Severity, sets official Severity,
        │  records Technical Diagnosis & Recommended Action, clicks Save Assessment)
        ▼
[ Block Requisition Creation ]
        │ (Auto-populates defect & assessment info, sets duration & track line, transmits to Controller)
        ▼
[ Controller Department Requests Pipeline ]
        │ (Categorized into NEW and OVERDUE; displays Defect Lineage & Assessment)
        ▼
[ Automated Classification Engine ]
        │ (Derives safety dependencies & power isolations; classifies into ISOLATION, PARALLEL, SEQUENTIAL, REVIEW)
        ▼
[ Optimization & Block Allocation ]
        │ (Google OR-Tools CP-SAT filters timetable departures and computes optimal possession windows)
        ▼
[ Controller Confirmation & Live Synchronization ]
        │ (Controller confirms allocation; notifications dispatched to affected departments; GIS map updated)
```

---

## 8. Artificial Intelligence & Mathematical Optimization Components

### A. Mathematical Constraint Optimization (`scripts/optimizer.py` & `app/block_allocation_engine.py`)
Formulated as an integer constraint satisfaction problem solved using **Google OR-Tools CP-SAT**:
- **Constraint 1 (Collision Prevention)**: Enforces that no two conflicting maintenance blocks occupy the same track segment simultaneously unless merged into a verified Parallel/Shadow block.
- **Constraint 2 (Timetable Departure Protection)**: Prohibits block grants that overlap scheduled passenger train departure windows on the same corridor.
- **Constraint 3 (Section & Duration Feasibility)**: Matches task spatial requirements with valid corridor slots where $\text{Slot Duration} \ge \text{Task Required Duration}$.
- **Objective Function**:
  $$\max \sum_{i \in \text{Tasks}} \sum_{j \in \text{Slots}} x_{i,j} \cdot \left(0.60 \times \text{PriorityScore}_i + 0.40 \times \text{RiskScore}_i\right)$$

### B. Machine Learning Failure Risk Prediction (`scripts/scoring_models.py`)
- **RandomForestClassifier**: Trained on historical defect features (severity, overdue days, traffic density, estimated duration) to predict probability of asset failure before maintenance.
- **IsolationForest Anomaly Detector**: Unsupervised model identifying track sections with statistically anomalous defect clustering.

### C. AI Advisory Defect Severity Engine (`app/main.py`)
- Evaluates technical keywords, structural hazards, signaling dependencies, and power risks from problem descriptions to suggest advisory severity (`Critical`, `High`, `Medium`, `Low`) and safety rationale without overriding the engineer's manual authority.

### D. 32 Autonomous Domain Agents Network (`scripts/agents.py`)
Divided into 5 operational clusters:
1. **Core Operations**: `CoordinatorAgent`, `ReplanningAgent`, `TrafficAgent`, `DepartmentAgent`.
2. **Safety & Compliance**: `ComplianceAgent`, `SafetyClearanceAgent` (G&SR rules), `AnomalyDetectionAgent`.
3. **Telemetry & Speed**: `LocopilotSpeedAgent`, `TelemetrySimulatorAgent`, `DynamicHeadwayAgent`, `SingleLineWorkingAgent`, `TSRLifecycleAgent`.
4. **Logistics & Resources**: `TrackMachinePackerAgent`, `CrewHOERAgent`, `TractionAwareRouterAgent`, `FOISDemurrageAgent`.
5. **Passenger Information**: `PassengerAdvisoryAgent` (automated bilingual passenger delay notifications), `CostOptimizationAgent`, `FeedbackLoopAgent`.

---

## 9. ChatMind AI — Multilingual Copilot Architecture

ChatMind AI is an integrated, floating conversational assistant embedded across the entire application:

- **LLM Engine**: Groq API using **LLaMA 3.3 70B Versatile** (with fallback support).
- **Multilingual Support**: English (`en-IN`), Telugu (`te-IN`), and Hindi (`hi-IN`).
- **Voice Mic Integration**: Browser-native Web Speech API (`webkitSpeechRecognition`) for hands-free operational queries.
- **Intent Parsing & Dynamic SQL RAG**:
  - `TRAIN_SINGLE_QUERY`: Live speed, section, next station, and delay for specific train numbers.
  - `TRAIN_DELAYED_FILTER_QUERY`: Locates all trains delayed beyond a threshold near a specific junction.
  - `TRAIN_COMPARISON_QUERY`: Identifies the fastest train or highest delay on the network.
  - `DB_QUERY`: Computes real-time defect counts, percentage completions, and department rankings directly from `railway.db`.
  - `REQUEST_LOOKUP` & `DEFECT_LOOKUP`: Instantly retrieves complete status, assessment, and track coordinates for specific request or defect IDs.
- **Zero Hallucination Guardrail**: Queries execute directly against the live database before response synthesis.

---

## 10. Data Architecture & Relational Schema

The platform uses SQLite 3 (`railway.db`) configured with **Write-Ahead Logging (WAL)** mode for concurrent multi-user stability:

```
┌─────────────────────────────────┐       ┌──────────────────────────────────┐
│        reported_defects         │       │        block_requests_v2         │
├─────────────────────────────────┤       ├──────────────────────────────────┤
│ PK defect_id                    │ 1───N │ PK request_id                    │
│    reporter_type, name, contact │       │    source, department            │
│    division, section, station   │       │    request_type, asset_type      │
│    track_km_details, category   │       │    section, line, direction      │
│    title, problem_brief         │       │    from_km, to_km, reported_time │
│    detailed_description         │       │    required_duration, deadline   │
│    department, severity         │       │    priority, dependency          │
│    status, department_analysis  │       │    isolation_required, reason    │
│    recommended_action           │       │    status, archetype             │
│    assessed_by, assessed_at     │       │    is_classified, classified_at  │
│    block_request_id             │       │    classification_run_id         │
│    reported_at                  │       └────────────────┬─────────────────┘
└─────────────────────────────────┘                        │
                                                           │ 1
                                                           ▼ N
┌─────────────────────────────────┐       ┌──────────────────────────────────┐
│          notifications          │       │   department_notifications_v4    │
├─────────────────────────────────┤       ├──────────────────────────────────┤
│ PK notif_id                     │       │ PK notif_id                      │
│    recipient_role, category     │       │    department, request_id        │
│    audience, message            │       │    allocation_id, block, section │
│    created_at, is_read          │       │    from_km, to_km, allocated_time│
└─────────────────────────────────┘       │    delivery_status, timestamp    │
                                          └──────────────────────────────────┘
```

---

## 11. Technology Stack

- **Application Framework**: Python 3.13, Streamlit 1.38+
- **Mathematical Optimization**: Google OR-Tools CP-SAT 9.10+
- **Machine Learning**: Scikit-Learn 1.5+ (`RandomForestClassifier`, `IsolationForest`)
- **Geospatial GIS**: Folium 0.20+, Leaflet.js, OpenStreetMap Satellite Tile Servers
- **Data Manipulation**: Pandas 2.2+, NumPy 2.0+
- **Database**: SQLite 3 (WAL Mode, PRAGMA busy_timeout=30000)
- **Authentication & Cryptography**: Bcrypt 4.2+ (Salted SHA-256 password hashing)
- **AI / LLM**: Groq Cloud SDK (`groq`), LLaMA 3.3 70B Versatile
- **Voice Processing**: Browser Web Speech API (`SpeechRecognition` & `SpeechSynthesis`)
- **PDF Reporting Engine**: ReportLab 4.2+, FPDF2 2.8+
- **Testing & Verification**: Python `unittest`, 18 Automated Test Suites

---

## 12. Local Installation & Setup

### Prerequisites
- Python 3.13 (or Python 3.10+)
- Git

### 1. Clone the Repository
```bash
git clone https://github.com/MaguluriManikanta/railway-block-planning.git
cd railway-block-planning
```

### 2. Create and Activate Virtual Environment
```bash
# On Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1

# On Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Required Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and set your free Groq API key:
```bash
cp .env.example .env
```
Inside `.env`:
```ini
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
```

### 5. Launch the Streamlit Platform
```bash
streamlit run app/main.py
```
Open your browser at **`http://localhost:8501`**.

---

## 13. Running the Automated Test Suites

The repository contains 18 comprehensive automated test suites verifying all workflows, mathematical optimization models, persistence, and UI logic:

```bash
python scratch/run_all_step_tests.py
```

### Test Suite Summary:
```text
============================================================
SUMMARY: Total Tests Run: 241 | Passed: 241 | Failed: 0
============================================================
```

---

## 14. Repository Structure

```text
railway-block-planning/
├── app/
│   ├── main.py                        # Main Streamlit application and view router
│   ├── controller_requests.py         # Step 5: Department Requests (New vs Overdue, Lineage)
│   ├── classification_engine.py       # Step 6: Safety Dependency & Archetype Classification
│   ├── block_allocation_engine.py     # Step 7: CP-SAT Optimization & Slot Feasibility
│   ├── department_notifications.py    # Step 9: Multi-Department Notifications & Sync
│   ├── controller_map.py              # Geospatial Folium Corridor GIS Maps
│   ├── chatbot.py                     # Multilingual ChatMind AI Copilot (Groq LLaMA 3.3 70B)
│   ├── reports.py                     # Automated PDF Generation (FPDF2)
│   └── static/                        # Visual assets and background styling
├── scripts/
│   ├── agents.py                      # 32 Autonomous Domain Agents
│   ├── scoring_models.py              # ML Defect Urgency & Anomaly Detection
│   ├── optimizer.py                   # Standalone CP-SAT Optimization Engine
│   ├── generate_data.py               # Synthetic Multi-Source Railway Data Generator
│   ├── setup_database.py              # SQLite Schema Initializer & Seeder
│   ├── generate_analysis_doc.py       # PDF Generator for System Analysis Document
│   └── generate_pdf_explanation.py    # PDF Generator for Technical Specification
├── data/                              # Multi-Department Operational Datasets (CSV & DB)
├── scratch/                           # 18 Automated Test Suites (Steps 2 through 18)
├── frontend/                          # Supplementary Vite + React User Interface
├── railway.db                         # Production SQLite Database
├── requirements.txt                   # Project Dependencies
├── runtime.txt                        # Python Runtime Specification (3.13)
├── TrackMind_AI_System_Analysis_and_TechStack.md   # Comprehensive Technical Analysis
├── TrackMind_AI_System_Analysis_and_TechStack.pdf  # Publication-Grade Analysis PDF
├── TrackMind_AI_Prototype_Detailed_Explanation.pdf # Technical Specification PDF
└── README.md                          # Master Project Documentation
```

---

## 15. Operational Limitations & Boundaries
1. **Satellite GIS Offline Caching**: Folium interactive tiles require internet connectivity for dynamic satellite basemap tiles.
2. **Speech Recognition Browser Support**: Web Speech API speech recognition is natively supported in Chromium-based browsers (Chrome, Edge) and Safari.
3. **Groq API Rate Limits**: ChatMind AI uses free-tier Groq API endpoints; fallback models (`llama-3.1-8b-instant`, `mixtral-8x7b`) engage automatically upon rate limit events.

---

## 16. Future Scope
- **Direct FOIS / COA Kafka Integration**: Direct ingestion of live telemetry streams from Indian Railways FOIS and COA servers.
- **Drone & Track Recording Car (TRC) Computer Vision Ingestion**: Automatic parsing of rail surface imagery into the `reported_defects` table.
- **Edge Deployment on Locomotives**: On-premise offline deployment of lightweight SLMs for Loco Pilot defect voice-logging without cellular coverage.

---

## 17. Authors & Acknowledgments
- **Lead Developer & Architect**: Maguluri Manikanta
- **Project**: Automatic Block Planning & Disconnection Management System (BDMS)
- **Domain Focus**: Indian Railways Operations, P-Way Maintenance, S&T Interlocking, and TRD Electrification
- **Hackathon Reference**: Smart India Hackathon — Problem Statement 26027
