# AI-Powered Automatic Block Planning — Indian Railways

A full-stack, deployable AI system for **Smart India Hackathon Problem Statement 26027**:  
*"AI-Powered Automatic Block Planning to Maximize Asset Availability for Train Operations on Indian Railways."*

---

## What this is

Three railway departments — **Engineering (Track)**, **Signal & Telecom (S&T)**, and **Traction Distribution (TRD)** — independently request track maintenance "blocks" (disconnections) via BDMS, with no coordination between them. This causes scheduling conflicts, wasted corridor time, and train delays.

This system integrates their maintenance data with corridor availability (COA), the train timetable, and goods traffic forecasts, then uses AI/ML to prioritize and optimally schedule all maintenance blocks across weekly and monthly horizons.

### Key Capabilities
- **Realistic Synthetic Data Generation**: Simulates 2,000+ records per source for TMS, SMMS, TDMS, COA, Timetables, and Goods Forecasts across 40 sections in 5 divisions.
- **Priority Scoring & Failure Risk (ML)**: Combines severity, overdue days, and operational impact, blended with a Random Forest failure probability score.
- **Anomaly Detection (ML)**: IsolationForest identifies track sections with systemic defect clustering.
- **Mathematical Optimization**: Google OR-Tools CP-SAT solver guarantees zero departmental collisions and enforces train timetable constraints.
- **13+ Autonomous Agents**: Plain Python agents coordinate re-planning, SLA compliance, cost optimization, downtime simulation, crew roster lookup, and public passenger advisories with 3 auto-approval risk tiers.
- **Multilingual AI Explainer & Voice Assistant**: Groq API (`llama-3.3-70b-versatile`) with Web Speech API for English (`en-IN`), Hindi (`hi-IN`), and Telugu (`te-IN`).
- **Official PDF Reports**: Downloadable maintenance block summaries generated using `fpdf2`.

---

## Project Structure

```
railway_block_planning/
├── data/                   # Generated dummy CSV datasets (2000+ rows each)
│   ├── tms_defects.csv
│   ├── smms_defects.csv
│   ├── tdms_defects.csv
│   ├── corridor_availability.csv
│   ├── train_timetable.csv
│   └── goods_forecast.csv
├── scripts/
│   ├── generate_data.py    # Dataset generator
│   ├── setup_database.py   # DB schema + data loading + default users
│   ├── scoring_models.py   # Priority scoring, failure prediction, anomaly detection
│   ├── optimizer.py        # CP-SAT scheduling engine
│   └── agents.py           # All non-LLM agents
├── app/
│   ├── main.py             # Streamlit dashboard (login, role routing, all tabs)
│   ├── chatbot.py          # Explainer + NL Task Entry agents (Groq)
│   └── reports.py          # PDF report generation
├── railway.db              # SQLite database (created by setup_database.py)
├── requirements.txt
├── runtime.txt             # "3.13" (Pins Python 3.13 for Streamlit Cloud)
├── .env.example            # GROQ_API_KEY=your_groq_api_key_here
├── .gitignore
└── README.md
```

---

## Local Setup (Step by Step)

### 1. Create and Activate Python 3.13 Environment
Create and activate a virtual environment using Python 3.13:
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Free Groq API Key
1. Go to [https://console.groq.com/keys](https://console.groq.com/keys) and create a free API key (no credit card required).
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and set your key:
   ```
   GROQ_API_KEY=gsk_your_actual_groq_key_here
   ```

### 4. Generate the Datasets (Optional, already provided in `/data`)
```bash
python scripts/generate_data.py
```

### 5. Initialize the Database
Creates `railway.db`, loads datasets, and seeds default users:
```bash
python scripts/setup_database.py
```

### 6. Run the Pipeline from CLI (Optional verification)
```bash
python scripts/scoring_models.py
python scripts/optimizer.py
python scripts/agents.py
```

### 7. Launch the Streamlit Dashboard
```bash
streamlit run app/main.py
```
Open **[http://localhost:8501](http://localhost:8501)** in your browser.

---

## Default Login Credentials

| Username | Password | Role | Access Level |
| :--- | :--- | :--- | :--- |
| **admin1** | `admin123` | Admin | Full Central Controller Dashboard (All 10 Tabs) |
| **engineer1** | `engineer123` | Engineering | Track Department Dashboard (My Tasks, My Schedule, Mark Completed) |
| **signal1** | `signal123` | S&T | Signalling Department Dashboard |
| **traction1** | `traction123` | TRD | Traction Distribution Dashboard |

---

## Deploying to Streamlit Community Cloud (Free)

1. Push this repository to GitHub (public or private).
2. Verify `.env` is **not** committed (`.gitignore` excludes it).
3. Sign in to [share.streamlit.io](https://share.streamlit.io) with your GitHub account.
4. Click **New app**, select your repository, and set:
   - **Main file path**: `app/main.py`
5. Under **Advanced settings** → **Secrets**, add:
   ```toml
   GROQ_API_KEY = "gsk_your_actual_groq_key_here"
   ```
6. Click **Deploy**. Streamlit Cloud will build and host your app with a public URL.

> **Production Persistence Roadmap Note**:  
> SQLite storage on Streamlit Community Cloud is ephemeral — changes made while the app is running persist during that active session but reset to what is committed in GitHub if the cloud container restarts or sleeps. This is completely acceptable for a hackathon demo. For enterprise production persistence, swap the SQLite connection layer to a hosted database (e.g. Turso / Supabase / PostgreSQL).

---

## Verification & Test Suite

Run end-to-end checks against the real generated data:
```bash
# Verify scoring and anomaly detection
python scripts/scoring_models.py

# Verify CP-SAT optimization on weekly and monthly horizons
python scripts/optimizer.py

# Verify full 13-agent orchestration cycle
python scripts/agents.py
```
