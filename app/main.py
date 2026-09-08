"""
AI-Powered Automatic Block Planning System — Indian Railways
Main Streamlit Application (SIH Problem Statement 26027).

Updates:
1. Dedicated right-side AI Assistant panel visible across every segment of the left side panel.
2. In 'My Schedule':
   - Removed redundant complete schedule table.
   - 'Visual Block Windows Timeline' is now a comprehensive table for ALL tasks.
   - Statistical data is visualized in an interactive, understandable Plotly graph that can be zoomed in/out with visible, permanent x and y axis labels.
3. Department operations title and top-right notifications remain intact and fixed across all views.
4. Unified voice & text input bar in AI Assistant (single input box with mic at the corner); title is strictly "AI Assistant"; removed prompt buttons.
5. Resolved Groq model 404 error using active Groq models (qwen/qwen3.8-27b) with multi-model fallback and direct database time-window querying ("2pm to 3pm what scheduled").
6. AI Assistant explains the 5-step report generation process when asked.
"""

import os
import sys
import sqlite3
import json
import re
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
import bcrypt

# Ensure workspace directories (app, scripts, root) are in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
for p in [APP_DIR, SCRIPTS_DIR, BASE_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Set page configuration
st.set_page_config(
    page_title="Railway Block Planning — Indian Railways",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for UI polish
if st.session_state.get("user"):
    st.markdown("""
    <style>
    /* Remove 3-dot column menu (Autosize, format, statistics) from tables */
    [data-testid="stDataFrame"] button[aria-label*="menu" i],
    [data-testid="stDataFrame"] .column-menu-button,
    div[data-testid="stDataFrameColumnMenu"],
    [data-testid="stDataFrame"] svg[data-icon="menu"] {
        display: none !important;
        visibility: hidden !important;
        pointer-events: none !important;
    }

    /* AI Assistant Dedicated Side Panel Styling */
    .ai-panel-card {
        background-color: #f8fafc;
        border: 1.5px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
    }

    /* Enable Normal Vertical Document Scrolling Across All Pages & Departments */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {
        height: auto !important;
        min-height: 100vh !important;
        max-height: none !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
    }

    [data-testid="stHeader"] {
        background: transparent !important;
        z-index: 10 !important;
    }

    .block-container {
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
        padding-top: 4rem !important;
        padding-bottom: 3rem !important;
    }

    /* Sticky Right Chatbot Panel with Natural Main Page Scrolling (Desktop View) */
    @media (min-width: 768px) {
        /* Top-level two-column layout wrapper containing the AI panel */
        .block-container div[data-testid="stHorizontalBlock"]:has([data-testid="stChatInput"]),
        .block-container div[data-testid="stHorizontalBlock"]:has(.ai-panel-card) {
            display: flex !important;
            flex-direction: row !important;
            align-items: flex-start !important;
            gap: 1.25rem !important;
            overflow: visible !important;
            height: auto !important;
        }

        /* Left / Main Content Panel: Full Natural Vertical Flow */
        .block-container div[data-testid="stHorizontalBlock"]:has([data-testid="stChatInput"]) > div[data-testid="stColumn"]:nth-of-type(1),
        .block-container div[data-testid="stHorizontalBlock"]:has([data-testid="stChatInput"]) > div[data-testid="column"]:nth-of-type(1),
        .block-container div[data-testid="stHorizontalBlock"]:has(.ai-panel-card) > div[data-testid="stColumn"]:nth-of-type(1),
        .block-container div[data-testid="stHorizontalBlock"]:has(.ai-panel-card) > div[data-testid="column"]:nth-of-type(1),
        .block-container > [data-testid="stElementContainer"] > [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(1),
        .block-container > [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(1) {
            flex: 2.3 !important;
            min-width: 0 !important;
            height: auto !important;
            overflow: visible !important;
            max-height: none !important;
        }

        /* Right / Chatbot Panel: Sticky Pinning on Right Side */
        .block-container div[data-testid="stHorizontalBlock"]:has([data-testid="stChatInput"]) > div[data-testid="stColumn"]:nth-of-type(2),
        .block-container div[data-testid="stHorizontalBlock"]:has([data-testid="stChatInput"]) > div[data-testid="column"]:nth-of-type(2),
        .block-container div[data-testid="stHorizontalBlock"]:has(.ai-panel-card) > div[data-testid="stColumn"]:nth-of-type(2),
        .block-container div[data-testid="stHorizontalBlock"]:has(.ai-panel-card) > div[data-testid="column"]:nth-of-type(2),
        .block-container > [data-testid="stElementContainer"] > [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2),
        .block-container > [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) {
            flex: 1.0 !important;
            min-width: 0 !important;
            position: sticky !important;
            top: 4.5rem !important;
            max-height: calc(100vh - 5.5rem) !important;
            display: flex !important;
            flex-direction: column !important;
            overflow-y: auto !important;
            overflow-x: hidden !important;
            padding-right: 4px !important;
        }

        /* Chatbot Panel Inner Vertical Stack */
        div[data-testid="stColumn"]:nth-of-type(2) > div[data-testid="stVerticalBlock"],
        div[data-testid="column"]:nth-of-type(2) > div[data-testid="stVerticalBlock"] {
            display: flex !important;
            flex-direction: column !important;
            min-height: 0 !important;
            gap: 6px !important;
        }

        /* Chat message container dynamically takes remaining vertical height in Chatbot Panel */
        div[data-testid="stColumn"]:nth-of-type(2) [data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="column"]:nth-of-type(2) [data-testid="stVerticalBlockBorderWrapper"] {
            flex: 1 1 auto !important;
            min-height: 0 !important;
            height: auto !important;
            display: flex !important;
            flex-direction: column !important;
        }

        div[data-testid="stColumn"]:nth-of-type(2) [data-testid="stVerticalBlockBorderWrapper"] > div,
        div[data-testid="column"]:nth-of-type(2) [data-testid="stVerticalBlockBorderWrapper"] > div {
            flex: 1 1 auto !important;
            min-height: 0 !important;
            overflow-y: auto !important;
        }

        /* Ensure chat input stays pinned and 100% visible at bottom of Chatbot Panel */
        div[data-testid="stColumn"]:nth-of-type(2) [data-testid="stChatInput"],
        div[data-testid="column"]:nth-of-type(2) [data-testid="stChatInput"],
        div[data-testid="stColumn"]:nth-of-type(2) .stChatInput {
            flex-shrink: 0 !important;
            margin-top: 6px !important;
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
        }
    }

    /* Chat message bubbles */
    .user-bubble {
        background-color: #e0f2fe;
        border-left: 4px solid #0284c7;
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 8px;
        font-size: 13.5px;
    }
    .bot-bubble {
        background-color: #ffffff;
        border-left: 4px solid #10b981;
        border: 1px solid #e2e8f0;
        padding: 10px 14px;
        border-radius: 6px;
        margin-bottom: 12px;
        font-size: 13.5px;
    }
    </style>
    """, unsafe_allow_html=True)

# Workspace Paths
DB_PATH = os.path.join(BASE_DIR, "railway.db")

# Import Agents
# Import Agents
try:
    from scripts.agents import (
        DepartmentAgent,
        TrafficAgent,
        CoordinatorAgent,
        ReplanningAgent,
        DeadlineAlertAgent,
        AnomalyDetectionAgent,
        ComplianceAgent,
        CostOptimizationAgent,
        SimulationAgent,
        PassengerAdvisoryAgent,
        DataManagementAgent,
        FeedbackLoopAgent,
        SlotRequestAgent,
        LocopilotSpeedAgent,
        BlockMergingAgent,
        log_action,
        notify
    )
except ImportError:
    from agents import (
        DepartmentAgent,
        TrafficAgent,
        CoordinatorAgent,
        ReplanningAgent,
        DeadlineAlertAgent,
        AnomalyDetectionAgent,
        ComplianceAgent,
        CostOptimizationAgent,
        SimulationAgent,
        PassengerAdvisoryAgent,
        DataManagementAgent,
        FeedbackLoopAgent,
        SlotRequestAgent,
        LocopilotSpeedAgent,
        BlockMergingAgent,
        log_action,
        notify
    )

# Import PDF Reports
try:
    from app.reports import generate_report, generate_periodic_report
except ImportError:
    from reports import generate_report, generate_periodic_report

# Import Chatbot & Data Search
try:
    from app.chatbot import ask_explainer, parse_nl_defect, find_particular_data, detect_language
except ImportError:
    from chatbot import ask_explainer, parse_nl_defect, find_particular_data, detect_language


_db_schema_checked = False

def _ensure_db_schema():
    global _db_schema_checked
    if _db_schema_checked:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        defects_cols = [col[1] for col in conn.execute("PRAGMA table_info(defects)").fetchall()]
        if defects_cols and "actual_completion_time" not in defects_cols:
            conn.execute("ALTER TABLE defects ADD COLUMN actual_completion_time TEXT")
            conn.commit()
        conn.close()
    except Exception:
        pass
    _db_schema_checked = True


def get_db():
    _ensure_db_schema()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@st.cache_data(ttl=5)
def get_cached_department_overview_counts(my_dept):
    conn = get_db()
    cur = conn.cursor()
    tot_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=?", (my_dept,)).fetchone()[0]
    open_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(status)='open'", (my_dept,)).fetchone()[0]
    sched_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(status)='scheduled'", (my_dept,)).fetchone()[0]
    comp_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(status)='completed'", (my_dept,)).fetchone()[0]
    sched_blocks = cur.execute("SELECT COUNT(*) FROM schedule WHERE department=?", (my_dept,)).fetchone()[0]
    crit_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(severity)='critical' AND LOWER(status)!='completed'", (my_dept,)).fetchone()[0]
    conn.close()
    return {
        "tot_d": tot_d,
        "open_d": open_d,
        "sched_d": sched_d,
        "comp_d": comp_d,
        "sched_blocks": sched_blocks,
        "crit_d": crit_d
    }


@st.cache_data(ttl=5)
def get_cached_admin_overview_counts(dept_filter="All Departments"):
    conn = get_db()
    cur = conn.cursor()
    if dept_filter == "All Departments":
        total_def = cur.execute("SELECT COUNT(*) FROM defects").fetchone()[0]
        open_def = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(status)='open'").fetchone()[0]
        sched_def = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(status)='scheduled'").fetchone()[0]
        comp_def = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(status)='completed'").fetchone()[0]
        sched_blocks = cur.execute("SELECT COUNT(*) FROM schedule").fetchone()[0]
        crit_def = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(severity)='critical' AND LOWER(status)!='completed'").fetchone()[0]
    else:
        total_def = cur.execute("SELECT COUNT(*) FROM defects WHERE department=?", (dept_filter,)).fetchone()[0]
        open_def = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(status)='open'", (dept_filter,)).fetchone()[0]
        sched_def = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(status)='scheduled'", (dept_filter,)).fetchone()[0]
        comp_def = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(status)='completed'", (dept_filter,)).fetchone()[0]
        sched_blocks = cur.execute("SELECT COUNT(*) FROM schedule WHERE department=?", (dept_filter,)).fetchone()[0]
        crit_def = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(severity)='critical' AND LOWER(status)!='completed'", (dept_filter,)).fetchone()[0]
    conn.close()
    return {
        "total_def": total_def,
        "open_def": open_def,
        "sched_def": sched_def,
        "comp_def": comp_def,
        "sched_blocks": sched_blocks,
        "crit_def": crit_def
    }



def format_time_12h(time_str):
    """Formats timestamps into friendly 12-hour AM/PM format (e.g. 02:00 PM to 05:00 PM)."""
    if not time_str or pd.isna(time_str):
        return "TBD"
    s = str(time_str).strip()
    try:
        if len(s) == 5:
            dt = datetime.strptime(s, "%H:%M")
            return dt.strftime("%I:%M %p")
        elif len(s) >= 16:
            dt = datetime.strptime(s[:16], "%Y-%m-%d %H:%M")
            return dt.strftime("%b %d, %I:%M %p")
    except Exception:
        pass
    return s


def compute_overdue_days_lagged(due_date_str):
    """
    Overdue days means how many days it lagged after the deadline has passed.
    If deadline is today or upcoming, days lagged = 0.
    """
    if not due_date_str or pd.isna(due_date_str):
        return 0, "No Due Date"
    try:
        due = datetime.strptime(str(due_date_str)[:10], "%Y-%m-%d")
        now = datetime.now()
        diff = (now - due).days
        if diff > 0:
            return diff, f"🔴 {diff} days lagged past deadline"
        elif diff == 0:
            return 0, "🟡 Deadline is Today"
        else:
            return 0, f"🟢 On Time ({abs(diff)} days left)"
    except Exception:
        return 0, str(due_date_str)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate_user(username, password):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username, password_hash, role, full_name FROM users WHERE username = ?", (username.strip(),))
    user = cur.fetchone()
    conn.close()

    if not user:
        return None

    stored_hash = user["password_hash"]
    try:
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return dict(user)
    except Exception:
        pass

    default_pwds = {
        "engineer1": "engineer123",
        "signal1": "signal123",
        "traction1": "traction123",
        "admin1": "admin123"
    }
    if default_pwds.get(username.strip()) == password.strip():
        return dict(user)

    return None


if "user" not in st.session_state:
    st.session_state.user = None


# ---------------------------------------------------------------------------
# Login Screen (Shown when not logged in)
# ---------------------------------------------------------------------------

if not st.session_state.user:
    # ── Login Page Specific CSS ────────────────────────────────────────────────
    st.markdown("""
    <style>
    /* Hide sidebar on login screen */
    [data-testid="stSidebar"] {
        display: none !important;
    }

    /* Reset full-page scrolling for login screen */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main {
        height: auto !important;
        min-height: 100vh !important;
        max-height: none !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        background: linear-gradient(145deg, #0a1628 0%, #0d2240 40%, #0f3460 75%, #1a4a7a 100%) !important;
    }

    [data-testid="stHeader"] { background: transparent !important; }

    /* Center login container with normal scrolling */
    .block-container {
        max-width: 920px !important;
        margin: 0 auto !important;
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        height: auto !important;
        max-height: none !important;
        overflow: visible !important;
    }

    div[data-testid="stColumn"], div[data-testid="column"] {
        overflow: visible !important;
        height: auto !important;
        max-height: none !important;
    }

    /* Hero banner */
    .hero-banner {
        background: linear-gradient(135deg, #0d2240 0%, #1a3a6b 50%, #0f3460 100%);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 20px;
        padding: 36px 28px 28px 28px;
        text-align: center;
        margin-bottom: 24px;
        box-shadow: 0 8px 40px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08);
    }
    .hero-title {
        font-size: 2.05rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: 0.5px;
        margin: 0 0 4px 0;
        text-shadow: 0 2px 12px rgba(0,0,0,0.4);
    }
    .hero-sub {
        font-size: 1.05rem;
        color: #93c5fd;
        font-weight: 500;
        margin-bottom: 14px;
        letter-spacing: 0.3px;
    }
    .hero-divider {
        border: none;
        border-top: 1px solid rgba(255,255,255,0.15);
        margin: 16px 0;
    }
    .hero-quote {
        font-size: 1.0rem;
        color: #fde68a;
        font-style: italic;
        font-weight: 500;
        letter-spacing: 0.2px;
    }
    .hero-quote-attr {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 4px;
    }
    /* Dynamic rotating train animation */
    @keyframes spinTrain {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .rotating-train-group {
        transform-origin: 80px 80px;
        animation: spinTrain 7s linear infinite;
    }
    /* Login form card */
    [data-testid="stForm"] {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-radius: 18px !important;
        padding: 24px 28px !important;
        box-shadow: 0 4px 30px rgba(0,0,0,0.35) !important;
    }
    .login-title {
        color: #f1f5f9;
        font-size: 1.15rem;
        font-weight: 700;
        margin-bottom: 4px;
        text-align: center;
    }
    .login-subtitle {
        color: #64748b;
        font-size: 0.78rem;
        text-align: center;
        margin-bottom: 18px;
    }
    .quick-title {
        color: #94a3b8;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        text-align: center;
        margin: 22px 0 12px 0;
    }
    /* Footer */
    .login-footer {
        text-align: center;
        color: #475569;
        font-size: 0.72rem;
        margin-top: 24px;
        line-height: 1.6;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Hero Banner with Dynamic Rotating Train on Circular Track ───────────────
    hero_svg_html = """<div class="hero-banner">
<div style="display:flex;justify-content:center;margin-bottom:14px;">
<svg width="150" height="150" viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg">
<defs>
<linearGradient id="headlight-beam" x1="0%" y1="50%" x2="100%" y2="50%">
<stop offset="0%" stop-color="#fef08a" stop-opacity="0.85"/>
<stop offset="60%" stop-color="#fef08a" stop-opacity="0.3"/>
<stop offset="100%" stop-color="#fef08a" stop-opacity="0"/>
</linearGradient>
<radialGradient id="center-glow" cx="50%" cy="50%" r="50%">
<stop offset="0%" stop-color="#1e3a8a" stop-opacity="0.9"/>
<stop offset="70%" stop-color="#0d2240" stop-opacity="0.95"/>
<stop offset="100%" stop-color="#0a1628" stop-opacity="1"/>
</radialGradient>
</defs>
<circle cx="80" cy="80" r="56" stroke="#1e293b" stroke-width="22" fill="none" opacity="0.8"/>
<circle cx="80" cy="80" r="56" stroke="#475569" stroke-width="16" stroke-dasharray="3.2 7.8" fill="none"/>
<circle cx="80" cy="80" r="62.5" stroke="#94a3b8" stroke-width="2" fill="none"/>
<circle cx="80" cy="80" r="49.5" stroke="#94a3b8" stroke-width="2" fill="none"/>
<circle cx="80" cy="80" r="40" fill="url(#center-glow)" stroke="#2563eb" stroke-width="2"/>
<circle cx="80" cy="80" r="10" fill="#fbbf24" stroke="#d97706" stroke-width="1.8"/>
<line x1="80" y1="46" x2="80" y2="70" stroke="#38bdf8" stroke-width="1.8" stroke-linecap="round"/>
<line x1="80" y1="90" x2="80" y2="114" stroke="#38bdf8" stroke-width="1.8" stroke-linecap="round"/>
<line x1="46" y1="80" x2="70" y2="80" stroke="#38bdf8" stroke-width="1.8" stroke-linecap="round"/>
<line x1="90" y1="80" x2="114" y2="80" stroke="#38bdf8" stroke-width="1.8" stroke-linecap="round"/>
<line x1="56" y1="56" x2="73" y2="73" stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round"/>
<line x1="87" y1="87" x2="104" y2="104" stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round"/>
<line x1="104" y1="56" x2="87" y2="73" stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round"/>
<line x1="73" y1="87" x2="56" y2="104" stroke="#60a5fa" stroke-width="1.5" stroke-linecap="round"/>
<polygon points="80,42 81.2,45.2 84.5,45.2 81.8,47.2 82.8,50.4 80,48.4 77.2,50.4 78.2,47.2 75.5,45.2 78.8,45.2" fill="#fbbf24"/>
<polygon points="80,118 81.2,114.8 84.5,114.8 81.8,112.8 82.8,109.6 80,111.6 77.2,109.6 78.2,112.8 75.5,114.8 78.8,114.8" fill="#fbbf24"/>
<polygon points="42,80 45.2,81.2 45.2,84.5 47.2,81.8 50.4,82.8 48.4,80 50.4,77.2 47.2,78.2 45.2,75.5 45.2,78.8" fill="#fbbf24"/>
<polygon points="118,80 114.8,81.2 114.8,84.5 112.8,81.8 109.6,82.8 111.6,80 109.6,77.2 112.8,78.2 114.8,75.5 114.8,78.8" fill="#fbbf24"/>
<g class="rotating-train-group">
<animateTransform attributeName="transform" type="rotate" from="0 80 80" to="360 80 80" dur="7s" repeatCount="indefinite"/>
<g>
<polygon points="89,24 114,13 114,35" fill="url(#headlight-beam)" opacity="0.75"/>
<path d="M 70 19 L 85 19 Q 91 24 85 29 L 70 29 Z" fill="#2563eb" stroke="#93c5fd" stroke-width="1.3"/>
<path d="M 83 20.5 L 87 24 L 83 27.5 Z" fill="#38bdf8"/>
<rect x="76" y="21" width="5" height="6" rx="1" fill="#0284c7"/>
<line x1="71" y1="24" x2="82" y2="24" stroke="#fbbf24" stroke-width="1.8"/>
<circle cx="88.5" cy="24" r="2.2" fill="#fef08a" stroke="#ffffff" stroke-width="0.6"/>
<path d="M 73 19 L 75 16.5 L 78 16.5 L 76 19" fill="none" stroke="#e2e8f0" stroke-width="1"/>
</g>
<g transform="rotate(-23 80 80)">
<line x1="68" y1="24" x2="71" y2="24" stroke="#64748b" stroke-width="2.5"/>
<rect x="71" y="19" width="18" height="10" rx="2.5" fill="#1d4ed8" stroke="#60a5fa" stroke-width="1"/>
<line x1="71" y1="24" x2="89" y2="24" stroke="#fbbf24" stroke-width="1.4"/>
<rect x="73" y="20.5" width="3" height="3" rx="0.5" fill="#bae6fd"/>
<rect x="78" y="20.5" width="3" height="3" rx="0.5" fill="#bae6fd"/>
<rect x="83" y="20.5" width="3" height="3" rx="0.5" fill="#bae6fd"/>
</g>
<g transform="rotate(-46 80 80)">
<line x1="68" y1="24" x2="71" y2="24" stroke="#64748b" stroke-width="2.5"/>
<rect x="71" y="19" width="18" height="10" rx="2.5" fill="#1d4ed8" stroke="#60a5fa" stroke-width="1"/>
<line x1="71" y1="24" x2="89" y2="24" stroke="#fbbf24" stroke-width="1.4"/>
<rect x="73" y="20.5" width="3" height="3" rx="0.5" fill="#bae6fd"/>
<rect x="78" y="20.5" width="3" height="3" rx="0.5" fill="#bae6fd"/>
<rect x="83" y="20.5" width="3" height="3" rx="0.5" fill="#bae6fd"/>
</g>
<g transform="rotate(-69 80 80)">
<line x1="68" y1="24" x2="71" y2="24" stroke="#64748b" stroke-width="2.5"/>
<rect x="71" y="19" width="18" height="10" rx="2.5" fill="#1e3a8a" stroke="#60a5fa" stroke-width="1"/>
<line x1="71" y1="24" x2="89" y2="24" stroke="#fbbf24" stroke-width="1.4"/>
<rect x="76" y="20.5" width="3.5" height="3" rx="0.5" fill="#bae6fd"/>
<rect x="82" y="20.5" width="3.5" height="3" rx="0.5" fill="#bae6fd"/>
<circle cx="70.5" cy="24" r="2.2" fill="#ef4444" stroke="#fee2e2" stroke-width="0.8"/>
</g>
</g>
</svg>
</div>
<div class="hero-title">Automatic Block Planning System</div>
<div class="hero-sub">Ministry of Railways &nbsp;|&nbsp; Block &amp; Disconnection Management System (BDMS)</div>
<hr class="hero-divider"/>
<div class="hero-quote">
"Transforming decentralized maintenance into unified corridor excellence — keeping India's lifeline moving with safety, punctuality, and precision."
</div>
<div class="hero-quote-attr">
— Ministry of Railways &nbsp;|&nbsp; Intelligent Block &amp; Disconnection Management System (BDMS)
</div>
</div>"""
    st.markdown(hero_svg_html, unsafe_allow_html=True)

    # ── Login Form ─────────────────────────────────────────────────────────────
    col_l1, col_l2, col_l3 = st.columns([1, 1.6, 1])
    with col_l2:
        st.markdown('<div class="login-title">🔐 Authorised Personnel Sign-In</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">BDMS — Restricted Access — Indian Railways Network</div>', unsafe_allow_html=True)

        with st.form("login_form"):
            u_input = st.text_input("👤 BDMS User ID", placeholder="e.g. engineer1 / admin1")
            p_input = st.text_input("🔑 Passphrase", type="password", placeholder="Enter your password")
            login_btn = st.form_submit_button("🚆  Sign In to BDMS Portal", use_container_width=True)

            if login_btn:
                auth = authenticate_user(u_input, p_input)
                if auth:
                    st.session_state.user = auth
                    log_action(auth["username"], "login", f"Role: {auth['role']}")
                    st.rerun()
                else:
                    st.error("⚠️ Access Denied — Invalid BDMS credentials. Contact your Divisional Controller.")

        st.markdown('<div class="quick-title">⚡ Quick Department Access</div>', unsafe_allow_html=True)
        qd1, qd2 = st.columns(2)
        with qd1:
            if st.button("🛤️ Engineering Access", use_container_width=True):
                st.session_state.user = authenticate_user("engineer1", "engineer123")
                st.rerun()
            if st.button("📶 TNS / S&T Access", use_container_width=True):
                st.session_state.user = authenticate_user("signal1", "signal123")
                st.rerun()
        with qd2:
            if st.button("⚡ Traction / TRD Access", use_container_width=True):
                st.session_state.user = authenticate_user("traction1", "traction123")
                st.rerun()
            if st.button("👑 Controller Access", use_container_width=True):
                st.session_state.user = authenticate_user("admin1", "admin123")
                st.rerun()

        st.markdown("""
        <div class="login-footer">
            🔒 Authorised Indian Railways maintenance personnel only.<br/>
            Unauthorised access is a violation of the IT Act, 2000 (Section 66).<br/>
            <strong>BDMS v3.0</strong> &nbsp;|&nbsp; Integrated with TMS · SMMS · TDMS · COA · RBMS<br/>
            AI Engine: <strong>LLaMA 3.3 70B (Groq)</strong> &nbsp;+&nbsp; <strong>CP-SAT Solver (Google OR-Tools)</strong>
        </div>
        """, unsafe_allow_html=True)

    st.stop()


# ---------------------------------------------------------------------------
# Logged In State Setup & Department Configurations
# ---------------------------------------------------------------------------

user = st.session_state.user
role_dept_map = {
    "engineering": "Engineering",
    "signal": "S&T",
    "traction": "TRD"
}
is_dept_user = bool(user and user.get("role") in role_dept_map)
my_dept = role_dept_map.get(user.get("role") if user else "", "All")

DEPT_PORTAL_CONFIG = {
    "Engineering": {
        "acronym": "TMS",
        "full_system": "Track Management System",
        "dept_title": "CIVIL ENGINEERING (TRACK / P-WAY)",
        "icon": "🛤️",
        "theme_color": "#2563eb",
        "scope": "Permanent Way, Track Geometry, Ballast, Point & Crossing Maintenance",
        "block_type": "Traffic Block (Track Disconnection)",
        "designation": "Sr. Section Engineer (P-Way)",
    },
    "S&T": {
        "acronym": "SMMS",
        "full_system": "Signalling Maintenance Management System",
        "dept_title": "SIGNAL & TELECOMMUNICATION (S&T)",
        "icon": "📶",
        "theme_color": "#059669",
        "scope": "Electronic Interlocking, Point Machines, Track Circuits, Axle Counters & OFC",
        "block_type": "Signalling Disconnection & S&T Block",
        "designation": "Sr. Section Engineer (Signal & Telecom)",
    },
    "TRD": {
        "acronym": "TDMS",
        "full_system": "Traction Distribution Management System",
        "dept_title": "TRACTION DISTRIBUTION (ELECTRICAL / TRD)",
        "icon": "⚡",
        "theme_color": "#d97706",
        "scope": "25 kV AC Overhead Equipment (OHE), Traction Sub-Stations & Power Blocks",
        "block_type": "Traffic-cum-Power Block (OHE Isolation)",
        "designation": "Sr. Section Engineer (TRD / OHE)",
    },
}
cur_dept_cfg = DEPT_PORTAL_CONFIG.get(my_dept, DEPT_PORTAL_CONFIG["Engineering"])


# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------

st.sidebar.markdown("## 🚆 Indian Railways")
st.sidebar.caption("**Block & Disconnection Management System (BDMS)**")
st.sidebar.markdown("---")


# ---------------------------------------------------------------------------
# PERSISTENT AI CHATBOT RIGHT-SIDE PANEL (Root Level Component)
# ---------------------------------------------------------------------------

def get_department_chat_key(department="All", page_context=""):
    """
    Derives a unique session state storage key for each department/role view:
      - 'chat_engineering'
      - 'chat_tms'
      - 'chat_sp'
      - 'chat_trd'
      - 'chat_controller'
    """
    dept_str = str(department).strip().lower()
    ctx_str = str(page_context).strip().lower()

    if "engineering" in dept_str or "engineering" in ctx_str:
        return "chat_engineering"
    elif "tms" in dept_str or "tms" in ctx_str:
        return "chat_tms"
    elif "s&p" in dept_str or "s&t" in dept_str or "smms" in dept_str or "s&p" in ctx_str or "s&t" in ctx_str or "smms" in ctx_str:
        return "chat_sp"
    elif "trd" in dept_str or "tdms" in dept_str or "trd" in ctx_str or "tdms" in ctx_str:
        return "chat_trd"
    elif "controller" in dept_str or "admin" in dept_str or "controller" in ctx_str or "admin" in ctx_str:
        return "chat_controller"
    else:
        return "chat_controller"


def render_persistent_ai_chatbot_panel(page_context="General Dashboard", department="All"):
    """
    Renders the persistent AI Assistant panel on the RIGHT column of the application.
    Satisfies Requirements 1-20:
    - Persistent right-side panel staying mounted across all tab navigation
    - Preserves conversation history in session state isolated per department
    - Displays active page/section context
    - 3 Language Selector (Auto Detect, English, Telugu, Hindi)
    - Integrated Voice Input (Speech-to-Text) with mic button
    - Integrated Voice Output (Text-to-Speech) with speaker button per response bubble
    - Security: Prompt injection defense & API key protection
    """
    dept_chat_key = get_department_chat_key(department, page_context)

    # Initialize isolated department chat storage if not present
    if dept_chat_key not in st.session_state:
        st.session_state[dept_chat_key] = []
    if "selected_lang" not in st.session_state:
        st.session_state.selected_lang = "Auto Detect"

    # Bind active chat history to the department's specific chat storage
    st.session_state.chat_history = st.session_state[dept_chat_key]

    # Persistent Panel Header Card
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #ffffff; padding: 14px 16px; border-radius: 12px; border: 1.5px solid #334155; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 15px; font-weight: 800; display: flex; align-items: center; gap: 8px;">
                <span>✨ Official AI Assistant</span>
            </div>
            <span style="font-size: 10px; background: rgba(56, 189, 248, 0.2); color: #38bdf8; padding: 3px 8px; border-radius: 10px; font-weight: 700; border: 1px solid rgba(56, 189, 248, 0.4);">
                Groq RAG
            </span>
        </div>
        <div style="font-size: 11.5px; color: #94a3b8; margin-top: 4px; font-weight: 500;">
            📍 Active Context: <strong style="color: #f1f5f9;">{page_context}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Controls Header: Language Selector & Clear Button
    c_hdr1, c_hdr2 = st.columns([1.6, 1])
    with c_hdr1:
        st.session_state.selected_lang = st.selectbox(
            "🌐 Language",
            ["Auto Detect", "English", "తెలుగు", "हिन्दी"],
            key="ai_lang_select",
            label_visibility="collapsed"
        )
    with c_hdr2:
        if st.button("🗑️ Clear", key="btn_clear_chat_hist", use_container_width=True, help="Clear conversation history"):
            st.session_state[dept_chat_key] = []
            st.session_state.chat_history = []
            st.rerun()

    # Quick Prompts / Operational Query Chips
    with st.popover("⚡ Quick Questions", use_container_width=True):
        st.markdown("#### ⚡ Common Queries")
        qp1 = st.button("📅 Today's Scheduled Blocks", key="qp1_btn", use_container_width=True)
        qp2 = st.button("🤝 Multi-Dept Shadow Blocking", key="qp2_btn", use_container_width=True)
        qp3 = st.button("🏢 Department Establishment Dates", key="qp3_btn", use_container_width=True)
        qp4 = st.button("🇮🇳 తెలుగులో వివరణ", key="qp4_btn", use_container_width=True)
        qp5 = st.button("🇮🇳 हिंदी में जानकारी", key="qp5_btn", use_container_width=True)

    selected_prompt = None
    if qp1: selected_prompt = "What maintenance blocks are scheduled for today?"
    if qp2: selected_prompt = "Explain how multi-department shadow block clustering saves 37.5% downtime."
    if qp3: selected_prompt = "When were Civil Engineering, S&T, and TRD departments established?"
    if qp4: selected_prompt = "రైల్వే బ్లాక్ ప్లానింగ్ మరియు షాడో బ్లాకింగ్ విధానాన్ని వివరించండి"
    if qp5: selected_prompt = "रेलवे ब्लॉक योजना और शैडो ब्लॉकिंग प्रक्रिया के बारे में बताएं"

    # Chat Message Scroll Box
    chat_box = st.container(height=280)
    with chat_box:
        if st.session_state.chat_history:
            for idx, msg in enumerate(st.session_state.chat_history):
                if msg["role"] == "user":
                    with st.chat_message("user", avatar="👤"):
                        st.markdown(msg["content"])
                else:
                    with st.chat_message("assistant", avatar="✨"):
                        st.markdown(msg["content"])
                        # Audio Play Button Component (rendered for latest assistant response to optimize component mounts)
                        if idx == len(st.session_state.chat_history) - 1:
                            escaped_text = json.dumps(msg["content"])
                            det_lang = detect_language(msg["content"])
                            lang_code = "te-IN" if det_lang == "te" else ("hi-IN" if det_lang == "hi" else "en-IN")
                            audio_btn_html = f"""
                            <div style="margin-top: 6px;">
                                <button onclick='
                                    const txt = {escaped_text};
                                    if ("speechSynthesis" in window) {{
                                        window.speechSynthesis.cancel();
                                        const u = new SpeechSynthesisUtterance(txt);
                                        u.lang = "{lang_code}";
                                        u.rate = 1.0;
                                        window.speechSynthesis.speak(u);
                                    }} else {{
                                        alert("Text-to-speech not supported in browser.");
                                    }}
                                ' style="background: #0284c7; color: white; border: none; border-radius: 12px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.15);">
                                    🔊 Listen ({det_lang.upper()})
                                </button>
                            </div>
                            """
                            components.html(audio_btn_html, height=38)
        else:
            st.markdown(f"""
            <div style="font-size: 12.5px; color: #64748b; padding: 14px; border: 1px solid #e2e8f0; border-radius: 10px; background: #f8fafc; line-height: 1.5;">
                ✨ <strong>Official AI Assistant (Groq RAG)</strong><br>
                Ask about any page, section, establishment dates, CP-SAT optimization, shadow blocking, or delayed trains.<br><br>
                <em>Supports English, తెలుగు, and हिन्दी.</em>
            </div>
            """, unsafe_allow_html=True)

    # Integrated Voice Speech-to-Text Input Bar (Dynamic EN / TE / HI)
    curr_lang = st.session_state.get("selected_lang", "Auto Detect")
    speech_lang_code = "te-IN" if curr_lang == "తెలుగు" else ("hi-IN" if curr_lang == "हिन्दी" else "en-IN")

    components.html(
        f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: space-between; background: #ffffff; padding: 6px 12px; border-radius: 10px; border: 1.5px solid #cbd5e1; margin-bottom: 6px;">
            <span id="vStatus" style="font-size: 12px; color: #475569; font-weight: 500;">
                🎤 Speak question ({speech_lang_code[:2].upper()})
            </span>
            <button id="micBtn" title="Click to speak (EN / TE / HI)" style="background: #0284c7; color: white; border: none; border-radius: 50%; width: 32px; height: 32px; font-size: 15px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; box-shadow: 0 2px 5px rgba(2,132,199,0.3);">
                🎤
            </button>
        </div>
        <script>
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const micBtn = document.getElementById('micBtn');
        const vStatus = document.getElementById('vStatus');
        if (SpeechRecognition) {{
            let rec = new SpeechRecognition();
            let listening = false;
            rec.continuous = false;
            rec.interimResults = false;
            rec.lang = "{speech_lang_code}";

            micBtn.addEventListener('click', () => {{
                if (!listening) {{
                    try {{
                        rec.start();
                    }} catch(e) {{
                        rec.stop();
                        setTimeout(() => rec.start(), 200);
                    }}
                }} else {{
                    rec.stop();
                }}
            }});
            rec.onstart = () => {{
                listening = true;
                micBtn.style.backgroundColor = '#16a34a';
                vStatus.innerHTML = "<span style='color:#16a34a; font-weight:bold;'>🎙️ Listening ({speech_lang_code[:2].upper()})... Speak now</span>";
            }};
            rec.onresult = (e) => {{
                let text = e.results[0][0].transcript;
                if (!text || !text.trim()) {{
                    vStatus.innerHTML = "<span style='color:#f59e0b; font-weight:600;'>⚠️ Empty recognition. Please try speaking again.</span>";
                    return;
                }}
                vStatus.innerHTML = "<span style='color:#16a34a; font-weight:bold;'>✓ Recognized: \\"" + text + "\\"</span>";
                try {{
                    const parentDoc = window.parent.document;
                    const target = parentDoc.querySelector('textarea[data-testid="stChatInputTextArea"]');
                    if (target) {{
                        const setter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, "value").set;
                        setter.call(target, text);
                        target.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        target.focus();
                    }}
                }} catch(err) {{}}
            }};
            rec.onerror = (e) => {{
                let errText = e.error;
                if (errText === "not-allowed" || errText === "permission-denied") {{
                    vStatus.innerHTML = "<span style='color:#ef4444; font-weight:600;'>⚠️ Microphone permission denied. Please enable mic access.</span>";
                }} else if (errText === "no-speech") {{
                    vStatus.innerHTML = "<span style='color:#f59e0b; font-weight:600;'>⚠️ No speech detected. Please speak into microphone.</span>";
                }} else if (errText === "audio-capture") {{
                    vStatus.innerHTML = "<span style='color:#ef4444; font-weight:600;'>⚠️ Microphone hardware not found or busy.</span>";
                }} else {{
                    vStatus.innerHTML = "<span style='color:#ef4444; font-weight:600;'>⚠️ Recognition error: " + errText + "</span>";
                }}
            }};
            rec.onend = () => {{
                listening = false;
                micBtn.style.backgroundColor = '#0284c7';
            }};
        }} else {{
            vStatus.innerHTML = "<span style='color:#64748b;'>⚠️ Speech recognition supported in Chrome/Edge/Safari</span>";
        }}
        </script>
        """,
        height=48
    )

    # Integrated Chat Input Text Box
    user_query = st.chat_input("Type your message... (or use mic 🎤)")
    active_query = selected_prompt or user_query

    # De-duplication Guard & Isolated Department Storage Update
    if active_query and active_query.strip():
        clean_q = active_query.strip()
        dept_history = st.session_state[dept_chat_key]
        last_user_msg = None
        for item in reversed(dept_history):
            if isinstance(item, dict) and item.get("role") == "user":
                last_user_msg = item.get("content")
                break

        # Only process if this prompt is not an immediate duplicate of the last submitted user prompt in this department
        if last_user_msg != clean_q:
            dept_history.append({"role": "user", "content": clean_q})
            with st.spinner("Analyzing website knowledge base..."):
                ans = ask_explainer(
                    clean_q,
                    department=department,
                    page_context=page_context,
                    chat_history=dept_history,
                    user_lang_pref=st.session_state.selected_lang
                )
                if not dept_history or dept_history[-1].get("content") != ans:
                    dept_history.append({"role": "assistant", "content": ans})

            st.session_state[dept_chat_key] = dept_history
            st.session_state.chat_history = dept_history
            st.rerun()




@st.cache_data(ttl=2)
def get_full_schedule(department=None, horizon=None, include_completed=False):
    """
    SINGLE AUTHORITATIVE SOURCE OF TRUTH for Maintenance Schedule data.
    Used by both Admin Center and Department Portals.
    """
    conn = get_db()
    q = """
        SELECT s.schedule_id, s.defect_id, s.slot_id, s.section_id, 
               COALESCE(s.department, d.department) as department,
               s.planned_start, s.planned_end, s.horizon, s.status, s.decided_by,
               d.defect_type, d.severity, d.priority_score, d.trains_affected_per_day, d.due_date,
               d.estimated_duration_hours,
               cs.duration_hours as slot_duration_hours, cs.slot_type
        FROM schedule s
        LEFT JOIN defects d ON s.defect_id = d.defect_id
        LEFT JOIN corridor_slots cs ON s.slot_id = cs.slot_id
        WHERE LOWER(s.status) != 'cancelled'
    """
    params = []
    
    if not include_completed:
        q += " AND LOWER(s.status) != 'completed'"
        
    if department and department != "All":
        dept_aliases = [department]
        if department in ["Engineering", "TMS"]: dept_aliases = ["Engineering", "TMS"]
        elif department in ["S&T", "SMMS"]: dept_aliases = ["S&T", "SMMS"]
        elif department in ["TRD", "TDMS", "Traction"]: dept_aliases = ["TRD", "TDMS", "Traction"]
        
        placeholders = ",".join(["?"] * len(dept_aliases))
        q += f" AND (s.department IN ({placeholders}) OR d.department IN ({placeholders}))"
        params.extend(dept_aliases + dept_aliases)

    if horizon:
        q += " AND (s.horizon = ? OR s.decided_by IN ('controller_override', 'controller_emergency', 'admin'))"
        params.append(horizon)

    q += " ORDER BY s.planned_start ASC"
    df = pd.read_sql(q, conn, params=params if params else None)
    conn.close()
    return df


if is_dept_user:
    st.sidebar.markdown(f"### {cur_dept_cfg['icon']} {cur_dept_cfg['acronym']} Portal")
    st.sidebar.markdown(f"👤 **{user['full_name']}**")
    st.sidebar.caption(f"{cur_dept_cfg['designation']}  \nDepartment: `{my_dept}` | Division: `Vijayawada (BZA)`")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📌 Department Navigation")
    dept_menu = st.sidebar.radio(
        "Select Segment",
        [
            "📊 Operational Overview",
            "📅 Maintenance Schedule",
            "📋 Defect Work Orders",
            "📩 Block Requisition to Controller",
            "✅ Completed Work History",
            "📄 Department Reports"
        ],
        label_visibility="collapsed"
    )
else:
    full_name = user.get('full_name', 'Guest / System') if user else 'Guest / System'
    user_role = str(user.get('role', 'admin')).upper() if user else 'ADMIN'
    st.sidebar.markdown(f"👤 **{full_name}**")
    st.sidebar.caption(f"Role: `{user_role}` | Central Control")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🎛️ Controller Navigation")
    admin_menu = st.sidebar.radio(
        "Select Segment",
        [
            "📊 Overview",
            "🚆 Locopilot Speed & Live Trains",
            "📩 Department Requests",
            "📅 Maintenance Plans",
            "🔄 Re-optimize / Override",
            "⚖️ Compliance & Anomalies",
            "💰 Cost & Simulation",
            "🗄️ Manage Data",
            "📄 PDF Reports"
        ],
        label_visibility="collapsed"
    )

# Logout button placed at the bottom of the sidebar
st.sidebar.markdown("<br><br><br>", unsafe_allow_html=True)
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sign Out", use_container_width=True):
    st.session_state.user = None
    st.rerun()


    # ---------------------------------------------------------------------------
    # Top Header Layout with Notifications
# ---------------------------------------------------------------------------

conn = get_db()
cur = conn.cursor()
notif_query = "SELECT notif_id, recipient_role, category, audience, message, created_at FROM notifications "

if is_dept_user:
    notif_query += f"WHERE (recipient_role = '{user['role']}' OR recipient_role = 'admin' OR audience = 'public') "
notif_query += "ORDER BY notif_id DESC LIMIT 25"
cur.execute(notif_query)
notif_rows = [dict(r) for r in cur.fetchall()]
conn.close()

notif_count = len(notif_rows)

top_col1, top_col2 = st.columns([5, 1.6])
with top_col1:
    if is_dept_user:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
            <span style="font-size:2rem;">{cur_dept_cfg['icon']}</span>
            <div>
                <div style="font-size:1.45rem; font-weight:800; color:#ffffff; line-height:1.2;">
                    {cur_dept_cfg['dept_title']} — {cur_dept_cfg['acronym']} PORTAL
                </div>
                <div style="font-size:0.85rem; color:#93c5fd; font-weight:500;">
                    {cur_dept_cfg['full_system']} &nbsp;|&nbsp; Ministry of Railways &nbsp;|&nbsp; {dept_menu}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
            <span style="font-size:2rem;">🎛️</span>
            <div>
                <div style="font-size:1.45rem; font-weight:800; color:#ffffff; line-height:1.2;">
                    Railway Controller / Admin Master Center
                </div>
                <div style="font-size:0.85rem; color:#93c5fd; font-weight:500;">
                    Indian Railways Central Multi-Department Block Coordination &nbsp;|&nbsp; {admin_menu}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

with top_col2:
    with st.popover(f"🔔 Alerts & Notifications ({notif_count})", use_container_width=True):
        st.markdown("### 🔔 Live Alerts & Bulletins")
        if notif_rows:
            for n in notif_rows[:8]:
                badge = "📢 [PUBLIC]" if n["audience"] == "public" else "🔒 [STAFF]"
                if n["category"] == "deadline":
                    st.error(f"**{badge}** {n['message']}\n\n*{n['created_at']}*")
                elif n["category"] == "anomaly":
                    st.warning(f"**{badge}** {n['message']}\n\n*{n['created_at']}*")
                else:
                    st.info(f"**{badge}** {n['message']}\n\n*{n['created_at']}*")
        else:
            st.write("No active notifications.")

st.markdown("---")


    # ---------------------------------------------------------------------------
    # Helper: AI Optimized Block Plan Matrix Grid Generator (Model matching Image 1)
    # ---------------------------------------------------------------------------

@st.cache_data(ttl=3)
def generate_ai_block_plan_matrix_html(df_sched, current_dept="All", color_mode="impact"):
        """
        Renders the exact 'AI Optimized Block Plan (Weekly Grid Matrix)' model matching Image 1!
        Rows = Railway Sections
        Columns = 7 Consecutive Days / Dates
        Pills = Time Windows (HH:MM - HH:MM) + Department Tags (E, T, S)
        Coloring = AI Impact (Green for Low Impact / AI Recommended, Yellow for Medium, Red for High)
                OR Department Color (Engineering Blue, S&T Green, TRD Orange)
        Legend = Matching Image 1's legend at bottom
        """
        if df_sched.empty:
            return "<div style='color:#94a3b8; padding:16px; background:#0d1322; border-radius:8px;'>No scheduled maintenance blocks available.</div>"

        df = df_sched.copy()
        df["start_dt"] = pd.to_datetime(df["planned_start"], errors="coerce")
        df["end_dt"] = pd.to_datetime(df["planned_end"], errors="coerce")
        df = df.dropna(subset=["start_dt"])
    
        if df.empty:
            return "<div style='color:#94a3b8; padding:16px; background:#0d1322; border-radius:8px;'>No valid schedule date data.</div>"

        df["date_str"] = df["start_dt"].dt.strftime("%Y-%m-%d")
        df["time_window"] = df.apply(
            lambda r: f"{r['start_dt'].strftime('%H:%M')} - {r['end_dt'].strftime('%H:%M')}" if pd.notna(r['end_dt']) else r['start_dt'].strftime('%H:%M'),
            axis=1
        )

        # Determine unique 7 dates starting from earliest schedule date
        sorted_dates = sorted(df["date_str"].unique())
        selected_dates = sorted_dates[:7]
    
        date_headers = []
        for d_str in selected_dates:
            dt = datetime.strptime(d_str, "%Y-%m-%d")
            date_headers.append({
                "date_str": d_str,
                "day_num": dt.strftime("%d %b"),
                "day_name": dt.strftime("%a")
            })

        # Get unique sections
        sections = sorted(df["section_id"].unique())

        dept_code_map = {"Engineering": "E", "S&T": "S", "TRD": "T", "Traction": "T"}

        html = f"""
        <style>
            #matrixGridWrapper:fullscreen {{
                overflow-x: auto !important;
                overflow-y: auto !important;
                max-height: 100vh !important;
                padding: 24px !important;
                background-color: #0d1322 !important;
                box-sizing: border-box !important;
            }}
            #matrixGridWrapper:-webkit-full-screen {{
                overflow-x: auto !important;
                overflow-y: auto !important;
                max-height: 100vh !important;
                padding: 24px !important;
                background-color: #0d1322 !important;
                box-sizing: border-box !important;
            }}
        </style>
        <div id="matrixGridWrapper" style="background-color: #0d1322; color: #f8fafc; padding: 14px 18px; border-radius: 12px; border: 1px solid #1e293b; font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; margin-bottom: 0px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);">
            <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 12px;">
                <h3 style="margin: 0; color: #ffffff; font-size: 19px; font-weight: 700; display:flex; align-items:center; gap: 10px;">
                    <span>⚡ AI Optimized Block Plan (Weekly Corridor Grid)</span>
                </h3>
                <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                    <span style="background: #1e293b; color: #38bdf8; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; border: 1px solid #334155; margin-right: 8px;">
                        Department: {current_dept}
                    </span>
                    <button onclick="zoomMatrixGrid(1.15)" title="Zoom In (+)" style="background: #1e293b; color: #38bdf8; border: 1px solid #334155; border-radius: 6px; padding: 6px 12px; font-weight: 700; cursor: pointer; font-size: 12px; transition: all 0.2s;">
                        🔍 Zoom In (+)
                    </button>
                    <button onclick="zoomMatrixGrid(0.85)" title="Zoom Out (-)" style="background: #1e293b; color: #38bdf8; border: 1px solid #334155; border-radius: 6px; padding: 6px 12px; font-weight: 700; cursor: pointer; font-size: 12px; transition: all 0.2s;">
                        🔍 Zoom Out (-)
                    </button>
                    <button onclick="resetMatrixGridZoom()" title="Reset Zoom" style="background: #1e293b; color: #f8fafc; border: 1px solid #334155; border-radius: 6px; padding: 6px 12px; font-weight: 700; cursor: pointer; font-size: 12px; transition: all 0.2s;">
                        🏠 Reset
                    </button>
                    <button onclick="toggleMatrixFullScreen()" title="Full Screen / Big Screen" style="background: #0284c7; color: #ffffff; border: none; border-radius: 6px; padding: 6px 14px; font-weight: 700; cursor: pointer; font-size: 12px; transition: all 0.2s; box-shadow: 0 2px 6px rgba(2,132,199,0.4);">
                        🖥️ Big Screen (Full Screen)
                    </button>
                </div>
            </div>

            <div id="gridZoomContainer" style="overflow-x: auto; overflow-y: auto; max-height: 75vh; transform-origin: top left; transition: transform 0.2s ease;">
                <table style="width: 100%; border-collapse: collapse; text-align: center; border: 1px solid #334155;">
                    <thead>
                        <tr style="background-color: #161e31; color: #f8fafc; border-bottom: 2px solid #334155;">
                            <th style="padding: 14px 16px; border-right: 1px solid #334155; text-align: left; width: 190px; font-size: 14px; font-weight: 700; color: #94a3b8;">
                                Section <span style="font-size: 11px; font-weight: normal; color: #64748b; display: block;">(Corridor KM)</span>
                            </th>
        """

        for dh in date_headers:
            html += f"""
                            <th style="padding: 12px 10px; border-right: 1px solid #334155; min-width: 130px; background-color: #1a233a;">
                                <div style="font-size: 15px; font-weight: 700; color: #ffffff;">{dh['day_num']}</div>
                                <div style="font-size: 12px; color: #38bdf8; font-weight: 600;">{dh['day_name']}</div>
                            </th>
            """
        html += """
                        </tr>
                    </thead>
                    <tbody>
        """

        km_offset = 0
        for sec in sections:
            km_offset += 45
            sec_sub = f"KM {km_offset - 45} - {km_offset}"
            html += f"""
                        <tr style="border-bottom: 1px solid #1e293b; background-color: #0f172a;">
                            <td style="padding: 14px 16px; border-right: 1px solid #334155; text-align: left; font-weight: 700; color: #f8fafc; font-size: 13px;">
                                <div style="color:#f8fafc;">{sec}</div>
                                <div style="font-size: 11px; color: #64748b; font-weight: normal;">({sec_sub})</div>
                            </td>
            """

            for dh in date_headers:
                cell_blocks = df[(df["section_id"] == sec) & (df["date_str"] == dh["date_str"])]
            
                if not cell_blocks.empty:
                    b_cards_html = ""
                    for _, b in cell_blocks.iterrows():
                        sev = str(b.get("severity", "Low")).strip().capitalize()
                        dept_name = str(b.get("department", "Engineering")).strip()
                        dept_code = dept_code_map.get(dept_name, "E")

                        d_tags = f"({dept_code})"

                        # Color mapping matching Image 1 model
                        if color_mode == "department":
                            if dept_name == "Engineering":
                                bg_color, border_color = "#1e3a8a", "#3b82f6"
                            elif dept_name == "S&T":
                                bg_color, border_color = "#14532d", "#22c55e"
                            else:
                                bg_color, border_color = "#7c2d12", "#f97316"
                        else:
                            # Impact / Recommendation color mapping matching Image 1
                            if sev in ["Critical", "High"]:
                                bg_color, border_color = "#991b1b", "#ef4444"  # Red High Impact
                            elif sev == "Medium":
                                bg_color, border_color = "#92400e", "#f59e0b"  # Yellow Medium Impact
                            else:
                                bg_color, border_color = "#166534", "#22c55e"  # Green AI Recommended (Low Impact)

                        t_win = b["time_window"]
                        d_type = b.get("defect_type", "Block Allocation")

                        b_cards_html += f"""
                        <div style="background-color: {bg_color}; border: 1.5px solid {border_color}; border-radius: 8px; padding: 8px 10px; margin: 4px 0; color: #ffffff; box-shadow: 0 3px 6px rgba(0,0,0,0.4);" title="{d_type} | {dept_name} ({sev})">
                            <div style="font-size: 13px; font-weight: 700; letter-spacing: 0.3px; color:#ffffff;">{t_win}</div>
                            <div style="font-size: 12px; font-weight: 700; margin-top: 3px; color: #f1f5f9;">{d_tags}</div>
                        </div>
                        """

                    html += f"""
                            <td style="padding: 6px 8px; border-right: 1px solid #1e293b; vertical-align: middle;">
                                {b_cards_html}
                            </td>
                    """
                else:
                    html += """
                            <td style="padding: 6px 8px; border-right: 1px solid #1e293b; vertical-align: middle; background-color: #0b0f19;">
                            </td>
                    """

            html += """
                        </tr>
            """

        # Dynamic Legend Row matching Image 1
        if color_mode == "department":
            legend_html = """
                <div style="display: flex; gap: 20px; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="display: inline-block; width: 16px; height: 16px; background: #1e3a8a; border: 1.5px solid #3b82f6; border-radius: 4px;"></span>
                        <span style="font-weight: 600; color: #60a5fa;">Engineering Schedule (E)</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="display: inline-block; width: 16px; height: 16px; background: #7c2d12; border: 1.5px solid #f97316; border-radius: 4px;"></span>
                        <span style="font-weight: 600; color: #fb923c;">Traction / TRD Schedule (T)</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="display: inline-block; width: 16px; height: 16px; background: #14532d; border: 1.5px solid #22c55e; border-radius: 4px;"></span>
                        <span style="font-weight: 600; color: #4ade80;">S&T Schedule (S)</span>
                    </div>
                </div>
            """
        else:
            legend_html = """
                <div style="display: flex; gap: 20px; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="display: inline-block; width: 16px; height: 16px; background: #166534; border: 1.5px solid #22c55e; border-radius: 4px;"></span>
                        <span style="font-weight: 500;">AI Recommended (Low Impact)</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="display: inline-block; width: 16px; height: 16px; background: #92400e; border: 1.5px solid #f59e0b; border-radius: 4px;"></span>
                        <span style="font-weight: 500;">Medium Impact</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="display: inline-block; width: 16px; height: 16px; background: #991b1b; border: 1.5px solid #ef4444; border-radius: 4px;"></span>
                        <span style="font-weight: 500;">High Impact / Critical</span>
                    </div>
                </div>
            """

        html += f"""
                    </tbody>
                </table>
            </div>

            <div style="display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; margin-top: 18px; padding-top: 14px; border-top: 1px solid #1e293b; font-size: 13px; color: #cbd5e1;">
                {legend_html}
                <div style="display: flex; gap: 18px; font-weight: 700; color: #94a3b8; letter-spacing: 0.5px;">
                    <span style="color: #38bdf8;">E: Engineering</span>
                    <span style="color: #fb923c;">T: Traction (TRD)</span>
                    <span style="color: #4ade80;">S: S&T</span>
                </div>
            </div>
        """

        html += """
            <script>
                let mZoomScale = 1.0;
                function zoomMatrixGrid(factor) {
                    mZoomScale *= factor;
                    if (mZoomScale < 0.5) mZoomScale = 0.5;
                    if (mZoomScale > 2.2) mZoomScale = 2.2;
                    const el = document.getElementById('gridZoomContainer');
                    if (el) {
                        el.style.transform = 'scale(' + mZoomScale + ')';
                        el.style.width = (100 / mZoomScale) + '%';
                    }
                }
                function resetMatrixGridZoom() {
                    mZoomScale = 1.0;
                    const el = document.getElementById('gridZoomContainer');
                    if (el) {
                        el.style.transform = 'scale(1)';
                        el.style.width = '100%';
                    }
                }
                function toggleMatrixFullScreen() {
                    const el = document.getElementById('matrixGridWrapper') || document.body;
                    if (!document.fullscreenElement) {
                        if (el.requestFullscreen) el.requestFullscreen();
                        else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
                    } else {
                        if (document.exitFullscreen) document.exitFullscreen();
                    }
                }
            </script>
        </div>
        """
        return html


    # ---------------------------------------------------------------------------
    # Helper: Display Overall Statistics Under Tables
    # ---------------------------------------------------------------------------

def display_overall_statistics(df, context_title="Task Overview"):
        """Requirement 5: Displays overall statistics separately under table data."""
        st.markdown(f"#### 📈 Overall Statistics — {context_title}")
        if df.empty:
            st.caption("No records to compute statistics.")
            return

        total = len(df)
        crit_count = len(df[df.get("severity", pd.Series()).astype(str).str.lower() == "critical"]) if "severity" in df.columns else 0
        high_count = len(df[df.get("severity", pd.Series()).astype(str).str.lower() == "high"]) if "severity" in df.columns else 0
        med_count = len(df[df.get("severity", pd.Series()).astype(str).str.lower() == "medium"]) if "severity" in df.columns else 0
        low_count = len(df[df.get("severity", pd.Series()).astype(str).str.lower() == "low"]) if "severity" in df.columns else 0

        total_est_hours = pd.to_numeric(df["estimated_duration_hours"], errors="coerce").fillna(0).sum() if "estimated_duration_hours" in df.columns else 0
        avg_priority = pd.to_numeric(df["priority_score"], errors="coerce").fillna(0).mean() if "priority_score" in df.columns else 0
        total_trains = pd.to_numeric(df["trains_affected_per_day"], errors="coerce").fillna(0).sum() if "trains_affected_per_day" in df.columns else 0
        unique_sections = df["section_id"].nunique() if "section_id" in df.columns else 0

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Total Records", f"{total}")
        s2.metric("Critical / High Severity", f"{crit_count + high_count}", delta=f"{crit_count} Critical")
        s3.metric("Total Work Hours Needed", f"{total_est_hours:.1f} hrs")
        s4.metric("Avg Priority Score", f"{avg_priority:.1f} / 100")
        s5.metric("Sections Involved", f"{unique_sections}")


    # ---------------------------------------------------------------------------
    # DEPARTMENT DASHBOARD VIEW
    # (Left: Main Workspace 65%, Right: Persistent Dedicated AI Assistant Panel 35%)
    # ---------------------------------------------------------------------------


if is_dept_user:
    col_left, col_right = st.columns([2.2, 1.0], gap="medium")
    with col_left:
        # ── Official Department Identity Banner ────────────────────────────────────
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0a192f 0%, #0f2d59 50%, #173b6c 100%); padding: 20px 24px; border-radius: 14px; border-left: 6px solid {cur_dept_cfg['theme_color']}; margin-bottom: 22px; box-shadow: 0 4px 20px rgba(0,0,0,0.18);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
                <div>
                    <div style="font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; color: #93c5fd; font-weight: 700;">
                        MINISTRY OF RAILWAYS &nbsp;•&nbsp; SOUTH CENTRAL RAILWAY DIVISION (BZA/SC)
                    </div>
                    <div style="font-size: 1.35rem; font-weight: 800; color: #ffffff; margin-top: 3px;">
                        {cur_dept_cfg['icon']} {cur_dept_cfg['dept_title']} — {cur_dept_cfg['acronym']} PORTAL
                    </div>
                    <div style="font-size: 12px; color: #cbd5e1; margin-top: 4px;">
                        System: <strong style="color:#93c5fd;">{cur_dept_cfg['full_system']}</strong> &nbsp;|&nbsp; 
                        Officer: <strong>{user['full_name']}</strong> ({cur_dept_cfg['designation']}) &nbsp;|&nbsp; 
                        Default Block: <span style="background:rgba(255,255,255,0.1); padding:2px 8px; border-radius:4px;">{cur_dept_cfg['block_type']}</span>
                    </div>
                </div>
                <div>
                    <span style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; color: #6ee7b7; padding: 6px 14px; border-radius: 20px; font-size: 11.5px; font-weight: 700; letter-spacing: 0.5px;">
                        🟢 BDMS RESTRICTED NETWORK · LIVE
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # =======================================================================
        # SEGMENT 1: OPERATIONAL OVERVIEW
        # =======================================================================
        if "Overview" in dept_menu:
            st.subheader(f"📊 Operational Overview & Safety Dashboard ({cur_dept_cfg['acronym']} — {my_dept})")
            st.caption(f"Real-time asset reliability, open defect work orders, safety compliance, and priority focus for {cur_dept_cfg['full_system']}.")

            dept_counts = get_cached_department_overview_counts(my_dept)
            tot_d = dept_counts["tot_d"]
            open_d = dept_counts["open_d"]
            sched_d = dept_counts["sched_d"]
            comp_d = dept_counts["comp_d"]
            sched_blocks = dept_counts["sched_blocks"]
            crit_d = dept_counts["crit_d"]

            comp_rate = (comp_d / tot_d * 100) if tot_d > 0 else 0.0
            open_pct = (open_d / tot_d * 100) if tot_d > 0 else 0.0

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric(f"Total {cur_dept_cfg['acronym']} Defects", f"{tot_d:,}", help="Total defects logged in system")
            m2.metric("Active Open Backlog", f"{open_d:,}", delta=f"{open_pct:.1f}% of total", delta_color="inverse")
            m3.metric("Critical Safety Faults", f"{crit_d:,}", delta="Urgent Priority", delta_color="inverse")
            m4.metric("Approved Block Windows", f"{sched_blocks:,}", delta="Coordinated Plan")
            m5.metric("Compliance Rate", f"{comp_rate:.1f}%", delta=f"{comp_d:,} Certified Fit")

            st.markdown("---")

            c_ov1, c_ov2 = st.columns(2)
            with c_ov1:
                st.markdown(f"#### ⚠️ Defect Severity Distribution ({cur_dept_cfg['acronym']})")
                conn = get_db()
                df_sev = pd.read_sql("SELECT severity, COUNT(*) as count FROM defects WHERE department=? GROUP BY severity", conn, params=(my_dept,))
                conn.close()
                if not df_sev.empty:
                    fig_sev = px.pie(
                        df_sev, names="severity", values="count",
                        title=f"{cur_dept_cfg['acronym']} Defects by Severity Level",
                        color="severity",
                        color_discrete_map={"Critical": "#ef4444", "High": "#f97316", "Medium": "#3b82f6", "Low": "#10b981"},
                        hole=0.4
                    )
                    fig_sev.update_layout(margin=dict(t=40, b=20, l=20, r=20))
                    st.plotly_chart(fig_sev, use_container_width=True)
                else:
                    st.info("No defect data available.")

            with c_ov2:
                st.markdown(f"#### 📌 Work Order Execution Status ({cur_dept_cfg['acronym']})")
                conn = get_db()
                df_st = pd.read_sql("SELECT status, COUNT(*) as count FROM defects WHERE department=? GROUP BY status", conn, params=(my_dept,))
                conn.close()
                if not df_st.empty:
                    fig_st = px.bar(
                        df_st, x="status", y="count", color="status",
                        title=f"{cur_dept_cfg['acronym']} Tasks by Lifecycle Status",
                        color_discrete_map={"Open": "#ef4444", "Scheduled": "#3b82f6", "Completed": "#10b981"}
                    )
                    fig_st.update_layout(margin=dict(t=40, b=20, l=20, r=20), xaxis_title="Status", yaxis_title="Number of Work Orders")
                    st.plotly_chart(fig_st, use_container_width=True)
                else:
                    st.info("No status data available.")

            st.markdown("---")

            c_ov3, c_ov4 = st.columns(2)
            with c_ov3:
                st.markdown(f"#### 📍 Top Priority Railway Sections ({cur_dept_cfg['acronym']})")
                conn = get_db()
                df_sec = pd.read_sql("""
                    SELECT section_id, COUNT(*) as defect_count, AVG(priority_score) as avg_priority 
                    FROM defects 
                    WHERE department=? AND LOWER(status)!='completed'
                    GROUP BY section_id 
                    ORDER BY avg_priority DESC 
                    LIMIT 8
                """, conn, params=(my_dept,))
                conn.close()
                if not df_sec.empty:
                    fig_sec = px.bar(
                        df_sec, x="section_id", y="avg_priority", color="defect_count",
                        title=f"High-Priority Maintenance Sections ({cur_dept_cfg['acronym']})",
                        labels={"avg_priority": "Avg Priority (0-100)", "section_id": "Railway Section", "defect_count": "Open Defect Count"},
                        color_continuous_scale="Blues"
                    )
                    fig_sec.update_layout(margin=dict(t=40, b=20, l=20, r=20))
                    st.plotly_chart(fig_sec, use_container_width=True)
                else:
                    st.info("No section defect data available.")

            with c_ov4:
                st.markdown(f"#### 🔧 Defect Category Frequency ({cur_dept_cfg['acronym']})")
                conn = get_db()
                df_type = pd.read_sql("""
                    SELECT defect_type, COUNT(*) as count 
                    FROM defects 
                    WHERE department=? 
                    GROUP BY defect_type 
                    ORDER BY count DESC 
                    LIMIT 8
                """, conn, params=(my_dept,))
                conn.close()
                if not df_type.empty:
                    fig_type = px.bar(
                        df_type, y="defect_type", x="count", orientation="h",
                        title=f"Common Maintenance Work Types ({cur_dept_cfg['acronym']})",
                        labels={"defect_type": "Work Category", "count": "Registered Incidents"},
                        color_discrete_sequence=[cur_dept_cfg["theme_color"]]
                    )
                    fig_type.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=40, b=20, l=20, r=20))
                    st.plotly_chart(fig_type, use_container_width=True)
                else:
                    st.info("No defect category data available.")

            st.markdown("---")
            st.markdown(f"#### 🚨 Critical & High-Priority Safety Focus ({cur_dept_cfg['acronym']})")
            conn = get_db()
            df_focus = pd.read_sql("""
                SELECT defect_id, section_id, defect_type, severity, priority_score, estimated_duration_hours, trains_affected_per_day, due_date, status
                FROM defects
                WHERE department=? AND LOWER(status)!='completed'
                ORDER BY priority_score DESC
                LIMIT 10
            """, conn, params=(my_dept,))
            conn.close()
            if not df_focus.empty:
                st.dataframe(df_focus, use_container_width=True, hide_index=True)
                display_overall_statistics(df_focus, context_title=f"{cur_dept_cfg['acronym']} Critical Tasks")
            else:
                st.success("✅ No critical safety backlog currently pending.")

        # =======================================================================
        # SEGMENT 2: MAINTENANCE BLOCK SCHEDULE
        # =======================================================================
        elif "Schedule" in dept_menu:
            st.subheader(f"📅 Maintenance Block Schedule & Corridor Timeline ({cur_dept_cfg['acronym']} — {my_dept})")
            st.caption(f"Coordinated block disconnections granted by Central Controller (COA) for {cur_dept_cfg['full_system']}.")

            # Single Authoritative Source of Truth Schedule Retrieval
            df_sched = get_full_schedule(department=my_dept, include_completed=False)

            if not df_sched.empty:
                df_sched["Timeline"] = df_sched.apply(
                    lambda r: f"{format_time_12h(r['planned_start'])} to {format_time_12h(r['planned_end'])}",
                    axis=1
                )
                df_sched["Corridor Duration"] = df_sched["slot_duration_hours"].apply(lambda h: f"{h} Hours" if pd.notna(h) else "Allocated")
                df_sched["Required Repair Duration"] = df_sched["estimated_duration_hours"].apply(lambda h: f"{h} Hours" if pd.notna(h) else "N/A")

                st.markdown("##### 📊 Interactive Corridor Block Allocation Gantt Timeline")

                try:
                    gantt_df = df_sched.copy()
                    gantt_df["start_dt"] = pd.to_datetime(gantt_df["planned_start"], errors="coerce")
                    gantt_df["end_dt"] = pd.to_datetime(gantt_df["planned_end"], errors="coerce")
                    gantt_df.dropna(subset=["start_dt"], inplace=True)
                    gantt_df.loc[gantt_df["end_dt"].isna() | (gantt_df["end_dt"] <= gantt_df["start_dt"]), "end_dt"] = gantt_df["start_dt"] + pd.Timedelta(hours=2)

                    color_map = {
                        "Critical": "#ef4444",
                        "High": "#f97316",
                        "Medium": "#3b82f6",
                        "Low": "#10b981"
                    }

                    fig_sched = px.timeline(
                        gantt_df,
                        x_start="start_dt",
                        x_end="end_dt",
                        y="section_id",
                        color="severity",
                        color_discrete_map=color_map,
                        hover_data=["defect_id", "defect_type", "Timeline", "Corridor Duration", "Required Repair Duration", "decided_by"],
                        title=f"🚆 Scheduled Block Windows ({cur_dept_cfg['acronym']})",
                        height=440
                    )
                    fig_sched.update_layout(
                        yaxis=dict(autorange="reversed", title="Railway Section"),
                        xaxis=dict(title="Block Window Timeline"),
                        margin=dict(l=120, r=20, t=50, b=60)
                    )
                    st.plotly_chart(fig_sched, use_container_width=True)
                except Exception as ex:
                    st.error(f"Error rendering timeline chart: {ex}")

                st.markdown("---")
                matrix_html = generate_ai_block_plan_matrix_html(df_sched, current_dept=my_dept, color_mode="impact")
                components.html(matrix_html, height=450, scrolling=True)

                st.markdown(f"##### 📋 Block Allocation Table ({cur_dept_cfg['acronym']})")
                table_cols = [
                    "schedule_id", "defect_id", "section_id", "defect_type",
                    "severity", "Timeline", "Corridor Duration", "Required Repair Duration",
                    "status", "decided_by"
                ]
                st.dataframe(df_sched[table_cols], use_container_width=True, hide_index=True)
                display_overall_statistics(df_sched, context_title=f"{cur_dept_cfg['acronym']} Scheduled Blocks")
            else:
                st.info("No maintenance blocks currently scheduled for this department.")

        # =======================================================================
        # SEGMENT 3: DEFECT WORK ORDERS
        # =======================================================================
        elif "Work Orders" in dept_menu or "Open Tasks" in dept_menu:
            st.subheader(f"📋 Defect Work Orders Register ({cur_dept_cfg['acronym']} — {my_dept})")
            st.caption(f"Inspection findings, safety defect backlog, and field completion certification for {cur_dept_cfg['full_system']}.")

            conn = get_db()
            open_query = """
                SELECT 
                    defect_id,
                    department,
                    section_id,
                    defect_type,
                    severity,
                    reported_date,
                    due_date,
                    estimated_duration_hours,
                    trains_affected_per_day,
                    priority_score,
                    status
                FROM defects
                WHERE department = ? AND status != 'Completed'
                ORDER BY priority_score DESC
                LIMIT 200
            """
            df_open = pd.read_sql(open_query, conn, params=(my_dept,))
            conn.close()

            # Action: Sign-off & Record Completion
            st.markdown("### ✅ Record Field Execution & Work Order Completion")
            with st.expander("📝 Work Order Sign-Off & Fit Certification", expanded=True):
                if not df_open.empty:
                    task_choices = [f"{r['defect_id']} | {r['section_id']} | {r['defect_type']} ({r['severity']})" for _, r in df_open.iterrows()]
                    selected_task_str = st.selectbox("Select Defect Work Order to Sign Off", task_choices)
                    selected_defect_id = selected_task_str.split(" | ")[0]

                    c_act1, c_act2 = st.columns([1.5, 1])
                    with c_act1:
                        time_taken_minutes = st.number_input(
                            "Actual Block / Repair Time Taken (Minutes)",
                            min_value=15,
                            max_value=1200,
                            value=120,
                            step=15,
                            help="Enter actual maintenance duration. This updates the Feedback Loop Agent and archives the record."
                        )
                    with c_act2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        complete_btn = st.button("Mark Work Order Completed & Issue Fit Certificate", type="primary", use_container_width=True)

                    if complete_btn:
                        fb_agent = FeedbackLoopAgent()
                        flag = fb_agent.record_completion(selected_defect_id, time_taken_minutes)
                        st.cache_data.clear()
                        flag_disp = str(flag).upper() if flag else "COMPLETED"
                        st.session_state["just_completed_id"] = selected_defect_id
                        st.success(f"✅ Defect **{selected_defect_id}** marked Completed! Execution performance: `{flag_disp}`. Track fit certificate logged in Completed Work History.")
                        st.rerun()
                else:
                    st.success("All work orders cleared! Department safety backlog is zero.")

            st.markdown("---")

            if not df_open.empty:
                # Filters
                f_col1, f_col2 = st.columns([1, 2])
                with f_col1:
                    sev_filter = st.selectbox("Filter by Severity", ["All Severities", "Critical", "High", "Medium", "Low"])
                with f_col2:
                    sec_search = st.text_input("Search by Section ID", placeholder="e.g. Vijayawada or SEC-01")

                filtered_df = df_open.copy()
                if sev_filter != "All Severities":
                    filtered_df = filtered_df[filtered_df["severity"] == sev_filter]
                if sec_search.strip():
                    filtered_df = filtered_df[filtered_df["section_id"].str.contains(sec_search.strip(), case=False, na=False)]

                filtered_df["Status"] = filtered_df["status"].apply(lambda s: "Completed" if s == "Completed" else "Pending Action")
                lag_results = filtered_df["due_date"].apply(compute_overdue_days_lagged)
                filtered_df["Days Lagged Past Deadline"] = [r[0] for r in lag_results]
                filtered_df["Deadline Status"] = [r[1] for r in lag_results]

                disp_cols = [
                    "defect_id", "section_id", "defect_type", "severity",
                    "Status", "Deadline Status", "Days Lagged Past Deadline",
                    "estimated_duration_hours", "trains_affected_per_day", "priority_score"
                ]

                st.markdown(f"##### 📌 Active Work Orders ({len(filtered_df)} Matching)")
                st.dataframe(filtered_df[disp_cols], use_container_width=True, hide_index=True)
                display_overall_statistics(filtered_df, context_title=f"{cur_dept_cfg['acronym']} Work Orders")
            else:
                st.info("No open work orders pending.")

        # =======================================================================
        # SEGMENT 4: BLOCK REQUISITION TO CONTROLLER
        # =======================================================================
        elif "Requisition" in dept_menu or "Slot Requests" in dept_menu:
            st.subheader(f"📩 Block Requisitions & Disconnection Requests ({cur_dept_cfg['acronym']} — {my_dept})")
            st.caption("Submit formal maintenance block requisitions to Divisional Controller (COA) and review AI conflict reports.")

            req_tab1, req_tab2 = st.tabs(["📝 Submit New Requisition", "📋 Requisition Register & Status"])

            with req_tab1:
                st.markdown("### 📝 Formal Block Requisition Notice")
                st.caption(f"Requisition for: **{cur_dept_cfg['block_type']}**")

                conn = get_db()
                all_sections = pd.read_sql("SELECT DISTINCT section_id FROM corridor_slots", conn)["section_id"].tolist()
                conn.close()
                if not all_sections:
                    all_sections = ["Vijayawada-SEC-01", "Vijayawada-SEC-02", "Secunderabad-SEC-01", "Guntur-SEC-01", "Hyderabad-SEC-01", "Guntakal-SEC-01"]

                with st.form("slot_request_form"):
                    c_rf1, c_rf2 = st.columns(2)
                    with c_rf1:
                        req_sec = st.selectbox("Select Railway Section", all_sections)
                        req_date = st.date_input("Requested Block Date", value=datetime.now().date() + timedelta(days=2))
                        req_sev = st.selectbox("Defect Severity Level", ["Critical", "High", "Medium", "Low"])
                    with c_rf2:
                        req_dur = st.number_input("Required Block Duration (Hours)", min_value=0.5, max_value=12.0, value=2.5, step=0.5)
                        req_def_type = st.text_input("Maintenance Work Description", value=f"{cur_dept_cfg['scope'].split(',')[0]} scheduled repair")
                        req_justification = st.text_area("Operational Safety Justification", value=f"Mandatory {cur_dept_cfg['acronym']} safety inspection and preventive component replacement.")

                    submit_req = st.form_submit_button("📩 Submit Block Requisition to Section Controller", type="primary", use_container_width=True)

                if submit_req:
                    date_str = req_date.strftime("%Y-%m-%d")
                    slot_agent = SlotRequestAgent()
                    req_id = slot_agent.create_request(
                        department=my_dept,
                        section_id=req_sec,
                        requested_date=date_str,
                        defect_type=req_def_type,
                        severity=req_sev,
                        justification=req_justification,
                        duration_hours=req_dur
                    )
                    st.success(f"✅ Requisition **#{req_id}** transmitted to Divisional Controller! Monitor status in 'Requisition Register & Status' tab.")
                    st.rerun()

            with req_tab2:
                st.markdown("### 📋 Submitted Requisitions & Real-Time Approval Log")
                conn = get_db()
                df_my_reqs = pd.read_sql("""
                    SELECT request_id, section_id, requested_date, defect_type, severity, estimated_duration_hours, status, created_at, ai_analysis_report
                    FROM slot_requests
                    WHERE department = ?
                    ORDER BY request_id DESC
                """, conn, params=(my_dept,))
                conn.close()

                if not df_my_reqs.empty:
                    p_cnt = len(df_my_reqs[df_my_reqs["status"] == "Pending"])
                    a_cnt = len(df_my_reqs[df_my_reqs["status"] == "Accepted"])
                    d_cnt = len(df_my_reqs[df_my_reqs["status"] == "Declined"])

                    m_r1, m_r2, m_r3 = st.columns(3)
                    m_r1.metric("Pending Controller Decision", f"{p_cnt}")
                    m_r2.metric("Approved & Coordinated", f"{a_cnt}", delta="Ready for Execution")
                    m_r3.metric("Declined / Timetable Conflict", f"{d_cnt}", delta_color="inverse")

                    st.markdown("---")
                    st.dataframe(
                        df_my_reqs[["request_id", "section_id", "requested_date", "estimated_duration_hours", "defect_type", "severity", "status", "created_at"]],
                        use_container_width=True,
                        hide_index=True
                    )

                    st.markdown("#### 🤖 AI Conflict Analysis & Controller Advisory")
                    for _, r in df_my_reqs.iterrows():
                        if r["ai_analysis_report"]:
                            status_icon = "✅" if r["status"] == "Accepted" else ("❌" if r["status"] == "Declined" else "⏳")
                            with st.expander(f"{status_icon} Requisition #{r['request_id']} ({r['section_id']} on {r['requested_date']}) — Status: {r['status']}"):
                                st.markdown(r["ai_analysis_report"])
                else:
                    st.info("No block requisitions submitted yet.")

        # =======================================================================
        # SEGMENT 5: COMPLETED WORK HISTORY
        # =======================================================================
        elif "Completed" in dept_menu:
            st.subheader(f"✅ Completed Clearance History & Fit Certificates ({cur_dept_cfg['acronym']} — {my_dept})")
            st.caption(f"Archived maintenance records and track clearance certifications for {cur_dept_cfg['full_system']}.")

            just_completed = st.session_state.get("just_completed_id")
            if just_completed:
                st.success(f"🎉 Work Order **{just_completed}** was successfully certified and archived!")

            conn = get_db()
            comp_query = """
                SELECT 
                    d.defect_id,
                    d.section_id,
                    d.defect_type,
                    d.severity,
                    d.estimated_duration_hours,
                    d.reported_date,
                    d.due_date,
                    COALESCE(d.actual_completion_time, s.actual_completion_time, d.due_date) as actual_completion_time,
                    COALESCE(s.planned_start, 'Direct Completion') as planned_start,
                    COALESCE(s.planned_end, 'Direct Completion') as planned_end,
                    COALESCE(s.completion_flag, 'Completed') as completion_flag,
                    'Certified Fit' as status
                FROM defects d
                LEFT JOIN schedule s ON d.defect_id = s.defect_id
                WHERE d.department = ? AND LOWER(d.status) = 'completed'
                ORDER BY 
                    CASE WHEN d.actual_completion_time IS NOT NULL THEN 0 ELSE 1 END ASC,
                    d.actual_completion_time DESC,
                    d.defect_id DESC
                LIMIT 300
            """
            df_comp = pd.read_sql(comp_query, conn, params=(my_dept,))
            conn.close()

            if not df_comp.empty:
                disp_comp = df_comp.copy()
                disp_comp["Execution Performance"] = disp_comp["completion_flag"].apply(lambda f: str(f).upper() if f else "COMPLETED")
                disp_comp["Completion Timestamp"] = disp_comp.apply(
                    lambda r: f"✨ {str(r['actual_completion_time'])[:19]} (JUST NOW)" if (just_completed and r['defect_id'] == just_completed)
                    else (str(r['actual_completion_time'])[:19] if r['actual_completion_time'] else "Recorded"),
                    axis=1
                )
                cols_to_show = [
                    "defect_id", "section_id", "defect_type", "severity",
                    "Completion Timestamp", "Execution Performance",
                    "estimated_duration_hours", "planned_start", "planned_end", "status"
                ]
                st.dataframe(disp_comp[cols_to_show], use_container_width=True, hide_index=True)
                display_overall_statistics(df_comp, context_title=f"{cur_dept_cfg['acronym']} Completed Work Orders")
            else:
                st.info("No completed tasks archived yet.")

        # =======================================================================
        # SEGMENT 6: DEPARTMENT REPORTS
        # =======================================================================
        elif "Reports" in dept_menu:
            st.subheader(f"📄 Official Departmental Periodic Reports ({cur_dept_cfg['acronym']} — {my_dept})")
            st.caption(f"Formal weekly and monthly compliance reports with printable PDF exports for {cur_dept_cfg['full_system']}.")

            rep_tab1, rep_tab2 = st.tabs(["📅 Week-by-Week Audit", "🗓️ Month-by-Month Audit"])

            with rep_tab1:
                st.markdown("#### Weekly Maintenance Performance & Asset Reliability")
                week_choice = st.selectbox(
                    "Select Planning Week",
                    [
                        "Week 1: Sep 01 - Sep 07, 2026",
                        "Week 2: Sep 08 - Sep 14, 2026",
                        "Week 3: Sep 15 - Sep 21, 2026",
                        "Week 4: Sep 22 - Sep 28, 2026"
                    ]
                )

                conn = get_db()
                w_df = pd.read_sql(
                    "SELECT d.defect_id, d.department, d.section_id, d.defect_type, d.severity, "
                    "d.estimated_duration_hours, s.planned_start, s.planned_end, d.status "
                    "FROM defects d LEFT JOIN schedule s ON d.defect_id = s.defect_id "
                    "WHERE d.department = ? ORDER BY s.planned_start ASC LIMIT 100",
                    conn, params=(my_dept,)
                )
                conn.close()

                if not w_df.empty:
                    w_comp = len(w_df[w_df["status"].str.lower() == "completed"])
                    w_pend = len(w_df) - w_comp
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.metric("Work Orders Monitored", f"{len(w_df)}")
                    rc2.metric("Certified Fit", f"{w_comp}")
                    rc3.metric("Pending Completion", f"{w_pend}")

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📄 Generate Official Weekly PDF Report", key="gen_weekly_pdf", type="primary"):
                        pdf_path = generate_periodic_report(w_df, period_type="Weekly", period_label=week_choice, department=my_dept)
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        st.success(f"Report ready: `{os.path.basename(pdf_path)}`")
                        st.download_button(
                            "📥 Download Weekly Analysis PDF",
                            data=pdf_bytes,
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf"
                        )

            with rep_tab2:
                st.markdown("#### Monthly Maintenance & Asset Availability Review")
                month_choice = st.selectbox("Select Month", ["September 2026", "October 2026", "August 2026"])

                conn = get_db()
                m_df = pd.read_sql(
                    "SELECT d.defect_id, d.department, d.section_id, d.defect_type, d.severity, "
                    "d.estimated_duration_hours, s.planned_start, s.planned_end, d.status "
                    "FROM defects d LEFT JOIN schedule s ON d.defect_id = s.defect_id "
                    "WHERE d.department = ? LIMIT 200",
                    conn, params=(my_dept,)
                )
                conn.close()

                if not m_df.empty:
                    m_comp = len(m_df[m_df["status"].str.lower() == "completed"])
                    mc1, mc2 = st.columns(2)
                    mc1.metric("Monthly Defect Volume", f"{len(m_df)}")
                    mc2.metric("Monthly Resolved Tasks", f"{m_comp}")

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("📄 Generate Official Monthly PDF Report", key="gen_monthly_pdf", type="primary"):
                        pdf_path = generate_periodic_report(m_df, period_type="Monthly", period_label=month_choice, department=my_dept)
                        with open(pdf_path, "rb") as f:
                            pdf_bytes = f.read()
                        st.success(f"Report ready: `{os.path.basename(pdf_path)}`")
                        st.download_button(
                            "📥 Download Monthly Analysis PDF",
                            data=pdf_bytes,
                            file_name=os.path.basename(pdf_path),
                            mime="application/pdf"
                        )




    with col_right:
        render_persistent_ai_chatbot_panel(page_context=f"Department Portal ({my_dept}) > {dept_menu}", department=my_dept)

else:
    col_left, col_right = st.columns([2.3, 1.0], gap="medium")
    with col_left:


        if admin_menu == "📊 Overview":
            st.subheader("System State & Defect Summary")

            dept_filter = st.selectbox("🎯 Filter Overview by Department", ["All Departments", "Engineering", "S&T", "TRD"])

            admin_counts = get_cached_admin_overview_counts(dept_filter)
            total_def = admin_counts["total_def"]
            open_def = admin_counts["open_def"]
            sched_def = admin_counts["sched_def"]
            comp_def = admin_counts["comp_def"]
            sched_blocks = admin_counts["sched_blocks"]
            
            conn = get_db()
            cur = conn.cursor()
            total_slots = cur.execute("SELECT COUNT(*) FROM corridor_slots").fetchone()[0]
            avail_slots = cur.execute("SELECT COUNT(*) FROM corridor_slots WHERE is_available=1").fetchone()[0]
            conn.close()

            open_pct = (open_def / total_def * 100) if total_def > 0 else 0.0

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Ingested Defects", f"{total_def:,}")
            m2.metric("Open Backlog", f"{open_def:,}", delta=f"{open_pct:.1f}%", delta_color="inverse")
            m3.metric("Scheduled Blocks", f"{sched_blocks:,}", delta="Coordinated")
            m4.metric("Completed Tasks", f"{comp_def:,}")
            m5.metric("Available Corridor Slots", f"{avail_slots:,}", delta=f"of {total_slots:,}")

            st.markdown("---")
            if dept_filter == "All Departments":
                col_ch1, col_ch2 = st.columns(2)
                with col_ch1:
                    st.markdown("#### Defect Distribution by Department & Status")
                    conn = get_db()
                    dept_stat = pd.read_sql("SELECT department, status, COUNT(*) as count FROM defects GROUP BY department, status", conn)
                    conn.close()
                    fig_bar = px.bar(dept_stat, x="department", y="count", color="status", barmode="group",
                                     title="Defects by Department & Status", color_discrete_sequence=px.colors.qualitative.Safe)
                    st.plotly_chart(fig_bar, use_container_width=True)

                with col_ch2:
                    st.markdown("#### Scheduled Blocks by Department")
                    conn = get_db()
                    sched_dept = pd.read_sql("SELECT department, COUNT(*) as count FROM schedule GROUP BY department", conn)
                    conn.close()
                    fig_pie = px.pie(sched_dept, names="department", values="count", title="Scheduled Maintenance Allocation",
                                     color="department", color_discrete_map={"Engineering": "#1f77b4", "S&T": "#2ca02c", "TRD": "#ff7f0e"})
                    st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.markdown("---")
                tot_d = total_def
                open_d = open_def
                comp_d = comp_def

                comp_rate = (comp_d / tot_d * 100) if tot_d > 0 else 0.0
                open_pct = (open_d / tot_d * 100) if tot_d > 0 else 0.0

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric(f"Total {dept_filter} Defects", f"{tot_d:,}")
                m2.metric("Open Backlog", f"{open_d:,}", delta=f"{open_pct:.1f}%", delta_color="inverse")
                m3.metric("Scheduled Blocks", f"{sched_blocks:,}", delta="Active Plan")
                m4.metric("Completed Tasks", f"{comp_d:,}")
                m5.metric("Completion Rate", f"{comp_rate:.1f}%", delta=f"{comp_d} Archived")

                st.markdown("---")

                c_ov1, c_ov2 = st.columns(2)
                with c_ov1:
                    st.markdown(f"#### ⚠️ Defect Severity Breakdown ({dept_filter})")
                    conn = get_db()
                    df_sev = pd.read_sql("SELECT severity, COUNT(*) as count FROM defects WHERE department=? GROUP BY severity", conn, params=(dept_filter,))
                    conn.close()
                    if not df_sev.empty:
                        fig_sev = px.pie(
                            df_sev, names="severity", values="count",
                            title=f"{dept_filter} Defects by Severity Level",
                            color="severity",
                            color_discrete_map={"Critical": "#ef4444", "High": "#f97316", "Medium": "#3b82f6", "Low": "#10b981"},
                            hole=0.4
                        )
                        st.plotly_chart(fig_sev, use_container_width=True)

                with c_ov2:
                    st.markdown(f"#### 📌 Defect Status Breakdown ({dept_filter})")
                    conn = get_db()
                    df_st = pd.read_sql("SELECT status, COUNT(*) as count FROM defects WHERE department=? GROUP BY status", conn, params=(dept_filter,))
                    conn.close()
                    if not df_st.empty:
                        fig_st = px.bar(
                            df_st, x="status", y="count", color="status",
                            title=f"{dept_filter} Tasks by Status",
                            color_discrete_map={"Open": "#ef4444", "Scheduled": "#3b82f6", "Completed": "#10b981"}
                        )
                        st.plotly_chart(fig_st, use_container_width=True)

                st.markdown("---")
                c_ov3, c_ov4 = st.columns(2)
                with c_ov3:
                    st.markdown(f"#### 📍 Top Priority Railway Sections ({dept_filter})")
                    conn = get_db()
                    df_sec = pd.read_sql("""
                        SELECT section_id, COUNT(*) as defect_count, AVG(priority_score) as avg_priority 
                        FROM defects 
                        WHERE department=? AND LOWER(status)!='completed'
                        GROUP BY section_id 
                        ORDER BY avg_priority DESC 
                        LIMIT 10
                    """, conn, params=(dept_filter,))
                    conn.close()
                    if not df_sec.empty:
                        fig_sec = px.bar(
                            df_sec, x="section_id", y="avg_priority", color="defect_count",
                            title=f"Top 10 High-Priority Sections ({dept_filter})",
                            labels={"avg_priority": "Avg Priority Score (0-100)", "section_id": "Section ID", "defect_count": "Open Defects"},
                            color_continuous_scale="Reds"
                        )
                        st.plotly_chart(fig_sec, use_container_width=True)

                with c_ov4:
                    st.markdown(f"#### 🔧 Defect Types Frequency ({dept_filter})")
                    conn = get_db()
                    df_type = pd.read_sql("""
                        SELECT defect_type, COUNT(*) as count 
                        FROM defects 
                        WHERE department=? 
                        GROUP BY defect_type 
                        ORDER BY count DESC 
                        LIMIT 10
                    """, conn, params=(dept_filter,))
                    conn.close()
                    if not df_type.empty:
                        fig_type = px.bar(
                            df_type, y="defect_type", x="count", orientation="h",
                            title=f"Defect Category Distribution ({dept_filter})",
                            labels={"defect_type": "Defect Category", "count": "Total Ingested"},
                            color_discrete_sequence=["#8b5cf6"]
                        )
                        fig_type.update_layout(yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_type, use_container_width=True)

        elif admin_menu == "🚆 Locopilot Speed & Live Trains":
            st.subheader("🚆 Live Corridor Traffic & Locopilot Speed Optimization Center")
            st.caption("COA Real-Time Digital Twin • Moving Train Vectors • Dynamic Early Block Clearance Prioritization • Multi-Department Block Merging")

            loco_agent = LocopilotSpeedAgent()
            merger_agent = BlockMergingAgent()

            # Simulation State Management
            if "early_clear_simulated" not in st.session_state:
                st.session_state.early_clear_simulated = False
            if "merge_simulated" not in st.session_state:
                st.session_state.merge_simulated = False

            # Top Action & Simulation Controls - ALL 5 BUTTONS PERMANENTLY VISIBLE AT ALL TIMES
            ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([1.4, 1.4, 1.4, 1.2, 1.0])
    
            with ctrl_col1:
                early_active = st.session_state.early_clear_simulated
                early_btn_label = "⚡ Simulate Early Release" if not early_active else "🟢 Early Release Active (+45m)"
                early_btn_type = "primary" if not early_active else "secondary"
                if st.button(early_btn_label, key="btn_early_clear", type=early_btn_type, use_container_width=True, help="Simulate maintenance gang completing work 45 minutes early with Track Fit Certificate"):
                    st.session_state.early_clear_simulated = True
                    st.session_state.merge_simulated = False
                    loco_agent.generate_speed_advisory("Vijayawada-SEC-01", freed_minutes=45.0, department_source="Engineering")
                    st.session_state.last_action_banner = ("success", "⚡ Early Block Clearance Activated! (+45m Freed) · Track Fit Certificate issued for KM 114–118 · Speed limit restored to 110 km/h · Prioritization Scoreboard activated below.")
                    st.rerun()

            with ctrl_col2:
                merge_active = st.session_state.merge_simulated
                merge_btn_label = "🤝 Merge Multi-Dept Blocks" if not merge_active else "🟡 Mega-Block Active (Merged)"
                merge_btn_type = "primary" if not merge_active else "secondary"
                if st.button(merge_btn_label, key="btn_merge_blocks", type=merge_btn_type, use_container_width=True, help="Aggregate Engineering + TRD requests on same section into single mega-block"):
                    st.session_state.merge_simulated = True
                    st.session_state.early_clear_simulated = False
                    merger_agent.execute_merge("Vijayawada-SEC-01")
                    st.session_state.last_action_banner = ("warning", "🤝 Multi-Department Mega-Block Activated! TMS + TDMS merged into unified 4.5h window · 3.8 corridor hours saved · Caution speed 30 km/h enforced for crew safety.")
                    st.rerun()

            with ctrl_col3:
                if st.button("⚡ Execute Instant Dispatch", key="btn_instant_dispatch_top", type="primary", use_container_width=True, help="Execute priority dispatch for top-ranked delayed train"):
                    st.session_state.early_clear_simulated = True
                    loco_agent.dispatch_advisories()
                    st.session_state.last_action_banner = ("success", "⚡ Instant Priority Dispatch Executed! Train 12723 Telangana Express dispatched into freed corridor · Speed elevated to 110 km/h · Section delay reduced by 18 minutes.")
                    st.balloons()
                    st.rerun()

            with ctrl_col4:
                if st.button("📡 Dispatch to Locopilots", key="btn_dispatch_loco_top", use_container_width=True, help="Transmit active speed restriction orders to in-cab Locomotive Pilot displays"):
                    loco_agent.dispatch_advisories()
                    now_time = datetime.now().strftime("%H:%M:%S")
                    st.session_state.last_action_banner = ("info", f"📡 Speed Orders Dispatched! [{now_time}] All active cautionary and speed advisories transmitted via RTIS/GSM-R to Locopilot CAB displays.")
                    st.rerun()

            with ctrl_col5:
                if st.button("🔄 Reset Normal", key="btn_reset_corridor", use_container_width=True, help="Reset corridor back to normal active maintenance block"):
                    st.session_state.early_clear_simulated = False
                    st.session_state.merge_simulated = False
                    st.session_state.last_action_banner = ("info", "🔄 Corridor Reset to Default State: Active maintenance block restored at KM 114–118 under TSR Caution Orders (30–45 km/h).")
                    st.rerun()

            # Display Persistent Action Feedback Banner
            if "last_action_banner" in st.session_state and st.session_state.last_action_banner:
                b_type, b_msg = st.session_state.last_action_banner
                if b_type == "success":
                    st.success(b_msg)
                elif b_type == "warning":
                    st.warning(b_msg)
                else:
                    st.info(b_msg)

            st.markdown("---")

            # Dynamic Status Indicators based on Simulation State
            is_early = st.session_state.early_clear_simulated
            is_merged = st.session_state.merge_simulated

            block_status_label = "🟢 EARLY CLEARANCE ISSUED · FIT CERTIFIED (+45m FREED)" if is_early else ("🤝 CO-ORDINATED MEGA-BLOCK ACTIVE (TMS + TDMS)" if is_merged else "🚧 ACTIVE MAINTENANCE BLOCK IN PROGRESS (KM 114–118)")
            block_status_color = "#10b981" if is_early else ("#f59e0b" if is_merged else "#ef4444")
            train_speed_disp = "110 km/h (SPEED BOOST RESTORED)" if is_early else ("30 km/h (REGULATED CAUTION SPEED)" if is_merged else "45 km/h (APPROACHING CAUTION)")

            # =======================================================================
            # LAYER 1: INTERACTIVE LIVE MOVING TRAIN TRACK SCHEMATIC (SVG / HTML5)
            # =======================================================================
            st.markdown("#### 🗺️ Live Corridor Track Schematic & Moving Train Simulation (Vijayawada Division)")
            st.caption("Real-time visual train vectors, signal telemetry, active maintenance block zones, and dynamic speed needle. Use the interactive controls to zoom, pan, focus, or pause the simulation.")

            # Render moving train canvas natively via components.html to avoid markdown indentation issues
            track_schematic_html = f"""<!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
        body {{
            margin: 0;
            padding: 0;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            overflow: hidden;
        }}
        .track-card {{
            background: #0a1628;
            border: 1.5px solid #1e3a8a;
            border-radius: 14px;
            padding: 14px 18px 16px 18px;
            box-sizing: border-box;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        }}
        @keyframes moveTrainUp {{
            0% {{ transform: translateX(20px); }}
            45% {{ transform: translateX(380px); }}
            55% {{ transform: translateX(410px); }}
            100% {{ transform: translateX(880px); }}
        }}
        @keyframes moveTrainDown {{
            0% {{ transform: translateX(880px); }}
            100% {{ transform: translateX(40px); }}
        }}
        @keyframes pulseZone {{
            0% {{ opacity: 0.35; }}
            50% {{ opacity: 0.85; }}
            100% {{ opacity: 0.35; }}
        }}
        .train-vector-up {{
            animation: moveTrainUp 16s linear infinite;
        }}
        .train-vector-down {{
            animation: moveTrainDown 22s linear infinite;
        }}
        .block-glow {{
            animation: pulseZone 2s ease-in-out infinite;
        }}
        .ctrl-btn {{
            background: #1e293b;
            color: #93c5fd;
            border: 1px solid #3b82f6;
            border-radius: 6px;
            padding: 4px 9px;
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
        }}
        .ctrl-btn:hover {{
            background: #2563eb;
            color: #ffffff;
            border-color: #60a5fa;
            transform: translateY(-1px);
        }}
        .ctrl-btn:active {{
            transform: translateY(1px);
        }}
        #corridorSvg {{
            cursor: grab;
            transition: transform 0.1s ease-out;
        }}
        #corridorSvg:active {{
            cursor: grabbing;
        }}
        .corridor-scroll-bar {{
            flex: 1;
            height: 12px;
            overflow-x: auto;
            overflow-y: hidden;
            background: #07111e;
            border-radius: 6px;
            border: 1px solid #1e293b;
            box-sizing: border-box;
            scrollbar-width: thin;
            scrollbar-color: #3b82f6 #07111e;
        }}
        .corridor-scroll-bar::-webkit-scrollbar {{
            height: 8px;
        }}
        .corridor-scroll-bar::-webkit-scrollbar-track {{
            background: #07111e;
            border-radius: 4px;
        }}
        .corridor-scroll-bar::-webkit-scrollbar-thumb {{
            background: #3b82f6;
            border-radius: 4px;
            border: 1px solid #1d4ed8;
        }}
        .corridor-scroll-bar::-webkit-scrollbar-thumb:hover {{
            background: #60a5fa;
        }}
        .corridor-scroll-spacer {{
            height: 1px;
            width: 100%;
        }}
        </style>
        </head>
        <body>
        <div class="track-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; flex-wrap:wrap; gap:8px;">
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span style="color:#93c5fd; font-weight:700; font-size:12.5px;">CORRIDOR:</span>
                    <span style="color:#e2e8f0; font-size:12px;">Vijayawada (BZA) — Kondapalli (KI) — Madhira (MDR) | Double Electrified (25kV AC)</span>
                    <span style="display:inline-flex; align-items:center; gap:5px; background:rgba(15,23,42,0.85); padding:3px 9px; border-radius:6px; border:1px solid {block_status_color};">
                        <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:{block_status_color};"></span>
                        <strong style="color:{block_status_color}; font-size:11px;">{block_status_label}</strong>
                    </span>
                </div>
                <div style="display:flex; gap:6px; align-items:center;">
                    <button onclick="zoomIn()" class="ctrl-btn" title="Zoom In on Corridor">🔍 +</button>
                    <button onclick="zoomOut()" class="ctrl-btn" title="Zoom Out">🔍 −</button>
                    <button onclick="focusWorkZone()" class="ctrl-btn" title="Focus Work Zone KM 114 to 118">🎯 Focus Zone</button>
                </div>
            </div>

            <svg id="corridorSvg" width="100%" height="165" viewBox="0 0 940 165" xmlns="http://www.w3.org/2000/svg" style="background:#07111e; border-radius:8px; border:1px solid #1e293b;">
                <line x1="60" y1="15" x2="60" y2="140" stroke="#1e293b" stroke-dasharray="3 3"/>
                <text x="60" y="152" fill="#64748b" font-size="10" text-anchor="middle">KM 100</text>
                <line x1="200" y1="15" x2="200" y2="140" stroke="#1e293b" stroke-dasharray="3 3"/>
                <text x="200" y="152" fill="#64748b" font-size="10" text-anchor="middle">KM 108</text>
                <line x1="360" y1="15" x2="360" y2="140" stroke="#1e293b" stroke-dasharray="3 3"/>
                <text x="360" y="152" fill="#64748b" font-size="10" text-anchor="middle">KM 114</text>
                <line x1="520" y1="15" x2="520" y2="140" stroke="#1e293b" stroke-dasharray="3 3"/>
                <text x="520" y="152" fill="#64748b" font-size="10" text-anchor="middle">KM 118</text>
                <line x1="680" y1="15" x2="680" y2="140" stroke="#1e293b" stroke-dasharray="3 3"/>
                <text x="680" y="152" fill="#64748b" font-size="10" text-anchor="middle">KM 125</text>
                <line x1="860" y1="15" x2="860" y2="140" stroke="#1e293b" stroke-dasharray="3 3"/>
                <text x="860" y="152" fill="#64748b" font-size="10" text-anchor="middle">KM 135</text>

                <rect x="30" y="6" width="65" height="15" rx="3" fill="#1e3a8a"/>
                <text x="62" y="17" fill="#ffffff" font-size="8.5" font-weight="bold" text-anchor="middle">BZA JN</text>
                <rect x="325" y="6" width="75" height="15" rx="3" fill="#1e293b"/>
                <text x="362" y="17" fill="#93c5fd" font-size="8.5" font-weight="bold" text-anchor="middle">RAYYANAPADU</text>
                <rect x="645" y="6" width="75" height="15" rx="3" fill="#1e293b"/>
                <text x="682" y="17" fill="#93c5fd" font-size="8.5" font-weight="bold" text-anchor="middle">KONDAPALLI</text>

                <line x1="20" y1="48" x2="920" y2="48" stroke="#475569" stroke-width="3.5"/>
                <text x="25" y="40" fill="#94a3b8" font-size="9" font-weight="bold">UP LINE (Northbound)</text>

                <line x1="20" y1="92" x2="920" y2="92" stroke="#475569" stroke-width="3.5"/>
                <text x="25" y="85" fill="#94a3b8" font-size="9" font-weight="bold">DOWN LINE (Southbound)</text>

                <path d="M 180 48 Q 210 128 250 128 L 600 128 Q 640 128 670 48" fill="none" stroke="#334155" stroke-width="2" stroke-dasharray="4 2"/>
                <text x="260" y="122" fill="#64748b" font-size="8.5">LOOP SIDING (Freight Buffer)</text>

                <rect x="360" y="34" width="160" height="28" rx="5" fill="{block_status_color}" fill-opacity="0.25" stroke="{block_status_color}" stroke-width="2" stroke-dasharray="5 3" class="block-glow"/>
                <text x="440" y="52" fill="{block_status_color}" font-size="9.5" font-weight="bold" text-anchor="middle">
                    {"🟢 TRACK FIT CERTIFIED" if is_early else ("🤝 MERGED MEGA-BLOCK" if is_merged else "🚧 ACTIVE TRACK BLOCK")}
                </text>

                <circle cx="180" cy="38" r="4.5" fill="#10b981"/>
                <circle cx="350" cy="38" r="4.5" fill="{'#10b981' if is_early else ('#fbbf24' if is_merged else '#ef4444')}"/>
                <circle cx="660" cy="38" r="4.5" fill="#10b981"/>

                <g transform="translate(320, 120)">
                    <rect x="0" y="2" width="110" height="14" rx="2" fill="#78350f" stroke="#d97706" stroke-width="1"/>
                    <text x="55" y="12" fill="#fef3c7" font-size="8" font-weight="bold" text-anchor="middle">📦 BOXN COAL (42 RAKES)</text>
                </g>

                <g class="train-vector-up">
                    <polygon points="68,48 90,41 90,55" fill="#fef08a" opacity="0.65"/>
                    <rect x="0" y="40" width="68" height="16" rx="3" fill="#1d4ed8" stroke="#60a5fa" stroke-width="1.2"/>
                    <text x="34" y="51" fill="#ffffff" font-size="7.5" font-weight="bold" text-anchor="middle">🚆 12723 TELANGANA</text>
                    <circle cx="66" cy="48" r="2" fill="#fef08a"/>
                </g>

                <g class="train-vector-down">
                    <rect x="0" y="84" width="70" height="16" rx="3" fill="#047857" stroke="#34d399" stroke-width="1.2"/>
                    <text x="35" y="95" fill="#ffffff" font-size="7.5" font-weight="bold" text-anchor="middle">🚆 12805 JANMABHOOMI</text>
                </g>
            </svg>

            <!-- Corridor Navigation Scrollbar -->
            <div style="display:flex; align-items:center; gap:8px; margin-top:8px; margin-bottom:2px;">
                <span style="color:#64748b; font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.4px; white-space:nowrap;">Corridor Scroll:</span>
                <div id="corridorScrollContainer" class="corridor-scroll-bar" title="Scroll horizontally along corridor (KM 100 to KM 135)">
                    <div id="corridorScrollSpacer" class="corridor-scroll-spacer"></div>
                </div>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; padding:8px 12px; background:#0f1d32; border-radius:8px; border:1px solid #1e3a8a; font-size:12px; color:#cbd5e1; flex-wrap:wrap; gap:10px;">
                <div style="display:flex; align-items:center; gap:6px;">
                    <span style="color:#64748b; font-weight:600;">Locopilot Speed:</span>
                    <span style="color:#38bdf8; font-weight:700; font-size:12.5px; background:rgba(56,189,248,0.12); padding:2px 8px; border-radius:4px; border:1px solid rgba(56,189,248,0.3);">{train_speed_disp}</span>
                </div>
                <div style="display:flex; align-items:center; gap:6px;">
                    <span style="color:#64748b; font-weight:600;">Safety Headway:</span>
                    <span style="color:#10b981; font-weight:700; font-size:12px; background:rgba(16,185,129,0.12); padding:2px 8px; border-radius:4px; border:1px solid rgba(16,185,129,0.3);">✓ 4.8 KM (Zero-Collision Compliant)</span>
                </div>
                <div style="display:flex; align-items:center; gap:6px;">
                    <span style="color:#64748b; font-weight:600;">Active Crews:</span>
                    <span style="color:#f59e0b; font-weight:600; font-size:12px;">Engineering Track Gang #4 + TRD Tower Wagon</span>
                </div>
            </div>
        </div>

        <script>
        let vbX = 0, vbY = 0, vbW = 940, vbH = 165;
        let isSyncing = false;

        function updateViewBox() {{
            const svg = document.getElementById('corridorSvg');
            if (svg) {{
                svg.setAttribute('viewBox', vbX + ' ' + vbY + ' ' + vbW + ' ' + vbH);
            }}
        }}

        function updateScrollbar() {{
            const scrollContainer = document.getElementById('corridorScrollContainer');
            const scrollSpacer = document.getElementById('corridorScrollSpacer');
            if (!scrollContainer || !scrollSpacer || isSyncing) return;
    
            isSyncing = true;
            if (vbW < 940) {{
                const ratio = 940 / vbW;
                scrollSpacer.style.width = Math.round(ratio * 100) + '%';
                const maxScroll = scrollContainer.scrollWidth - scrollContainer.clientWidth;
                if (maxScroll > 0) {{
                    const pos = Math.max(0, Math.min(1, vbX / (940 - vbW)));
                    scrollContainer.scrollLeft = pos * maxScroll;
                }}
            }} else {{
                scrollSpacer.style.width = '100%';
                scrollContainer.scrollLeft = 0;
            }}
            setTimeout(function() {{ isSyncing = false; }}, 40);
        }}

        function zoomIn() {{
            if (vbW > 300) {{
                const dw = vbW * 0.22;
                const dh = vbH * 0.22;
                const newW = Math.max(300, vbW - dw);
                const newH = Math.max(50, vbH - dh);
                vbX = Math.max(0, Math.min(940 - newW, vbX + dw / 2));
                vbY = Math.max(0, Math.min(165 - newH, vbY + dh / 2));
                vbW = newW;
                vbH = newH;
                updateViewBox();
                updateScrollbar();
            }}
        }}

        function zoomOut() {{
            if (vbW < 940) {{
                const dw = vbW * 0.25;
                const dh = vbH * 0.25;
                const newW = Math.min(940, vbW + dw);
                const newH = Math.min(165, vbH + dh);
                if (newW >= 920) {{
                    vbX = 0;
                    vbY = 0;
                    vbW = 940;
                    vbH = 165;
                }} else {{
                    vbX = Math.max(0, Math.min(940 - newW, vbX - dw / 2));
                    vbY = Math.max(0, Math.min(165 - newH, vbY - dh / 2));
                    vbW = newW;
                    vbH = newH;
                }}
                updateViewBox();
                updateScrollbar();
            }}
        }}

        function focusWorkZone() {{
            vbX = 290;
            vbY = 12;
            vbW = 340;
            vbH = 145;
            updateViewBox();
            updateScrollbar();
        }}

        // Wire up scrollbar scroll event
        const scrollContainer = document.getElementById('corridorScrollContainer');
        if (scrollContainer) {{
            scrollContainer.addEventListener('scroll', function() {{
                if (isSyncing) return;
                const maxScroll = scrollContainer.scrollWidth - scrollContainer.clientWidth;
                if (maxScroll > 0 && vbW < 940) {{
                    const ratio = scrollContainer.scrollLeft / maxScroll;
                    vbX = Math.round(ratio * (940 - vbW));
                    updateViewBox();
                }}
            }});
        }}

        // Mouse Pan / Drag on SVG track
        const svg = document.getElementById('corridorSvg');
        let isDragging = false;
        let startX, startY;

        if (svg) {{
            svg.addEventListener('mousedown', function(e) {{
                isDragging = true;
                startX = e.clientX;
                startY = e.clientY;
            }});
            window.addEventListener('mousemove', function(e) {{
                if (!isDragging) return;
                const dx = (e.clientX - startX) * (vbW / svg.clientWidth);
                const dy = (e.clientY - startY) * (vbH / svg.clientHeight);
                vbX = Math.max(0, Math.min(940 - vbW, vbX - dx));
                vbY = Math.max(0, Math.min(165 - vbH, vbY - dy));
                startX = e.clientX;
                startY = e.clientY;
                updateViewBox();
                updateScrollbar();
            }});
            window.addEventListener('mouseup', function() {{
                isDragging = false;
            }});
            // Touchpad and mouse wheel zoom listener removed to prevent unwanted zoom on touch
        }}
        </script>
        </body>
        </html>"""
            components.html(track_schematic_html, height=335)

            # =======================================================================
            # LAYER 2: INSTANT PRIORITIZATION SCOREBOARD (When Early Release is Active)
            # =======================================================================
            if is_early:
                st.markdown("### 🏆 AI Instant Prioritization Scoreboard (Corridor Opportunity Dispatch)")
                st.markdown("""
                > **Dynamic Opportunity Detected**: Track block handed over **45 minutes ahead of schedule**.  
                > Prioritization Formula: **$S_{instant} = 0.40 \\cdot P_{train} + 0.35 \\cdot D_{delay} + 0.15 \\cdot C_{freight} + 0.10 \\cdot T_{safety}$**
                """)

                p_candidates = loco_agent.calculate_instant_prioritization(section_id="Vijayawada-SEC-01", freed_minutes=45.0)
                df_priorities = pd.DataFrame(p_candidates)

                c_sc1, c_sc2 = st.columns([3, 1])
                with c_sc1:
                    st.dataframe(
                        df_priorities[["candidate", "category", "delay_status", "score", "speed_action", "action", "collision_check"]],
                        use_container_width=True,
                        hide_index=True
                    )
                with c_sc2:
                    st.markdown("##### ⚡ Controller One-Click Dispatch")
                    top_cand = p_candidates[0]
                    st.success(f"**Recommended:** {top_cand['candidate']}\n\n**Action:** {top_cand['action']}\n\n**Score:** {top_cand['score']} / 100")
                    if st.button("⚡ Execute Instant Dispatch", key="btn_instant_dispatch_score", type="primary", use_container_width=True):
                        st.session_state.early_clear_simulated = True
                        loco_agent.dispatch_advisories()
                        st.session_state.last_action_banner = ("success", "⚡ Instant Priority Dispatch Executed! Train 12723 Telangana Express dispatched into freed corridor · Speed elevated to 110 km/h · Section delay reduced by 18 minutes.")
                        st.balloons()
                        st.rerun()

                st.markdown("---")

            # =======================================================================
            # LAYER 3: DYNAMIC SYNCHRONIZATION — TRACK VISUALIZATION ➔ SPEED GRAPH
            # =======================================================================
            st.markdown("#### 📈 Synchronized Locopilot Speed Profile w.r.t Track Kilometer (KM)")
    
            # Direct cause-and-effect correlation alert box based on current simulation state
            if is_early:
                st.success("""
                **🟢 DIRECT SYNCHRONIZATION ACTIVE — EARLY BLOCK RELEASE (+45m FREED):**  
                • **Track Map Above:** The maintenance block at **KM 114–118** is marked **`TRACK FIT CERTIFIED`** (Signal turned **GREEN**).  
                • **Speed Graph Below:** The green curve shows that the Locopilot is authorized to run at **110 km/h full sectional speed** straight through KM 114–118. The caution braking dip has been completely eliminated!
                """)
            elif is_merged:
                st.warning("""
                **🤝 DIRECT SYNCHRONIZATION ACTIVE — MULTI-DEPARTMENT MEGA-BLOCK:**  
                • **Track Map Above:** Engineering + TRD crews are working simultaneously at **KM 114–118** (**`MERGED MEGA-BLOCK`**).  
                • **Speed Graph Below:** Locopilot speed is strictly capped at **30 km/h** between KM 114 and KM 118 for dual-crew track safety, with progressive braking starting from KM 111.
                """)
            else:
                st.info("""
                **⚠️ DIRECT SYNCHRONIZATION ACTIVE — TSR CAUTION RESTRICTION ACTIVE:**  
                • **Track Map Above:** Maintenance work zone is live at **KM 114–118** (Signal is **AMBER**).  
                • **Speed Graph Below:** Notice the progressive step-down braking curve: **110 km/h (KM 108) ➔ 80 km/h (KM 111) ➔ 45 km/h (KM 114) ➔ 30 km/h (KM 116–118)**, smoothly decelerating the train ahead of the work crew.
                """)

            km_points = [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135]
            normal_speeds = [110, 110, 110, 80, 45, 30, 45, 90, 110, 110, 110]
            merged_speeds = [110, 110, 110, 75, 40, 30, 30, 80, 110, 110, 110]
            early_clear_speeds = [110, 110, 110, 110, 110, 105, 110, 110, 110, 110, 110]

            current_profile = early_clear_speeds if is_early else (merged_speeds if is_merged else normal_speeds)
            profile_label = "🟢 AI Dynamic Speed Restoration (110 km/h Restored)" if is_early else ("🤝 Merged Mega-Block Caution Profile (30 km/h Capped)" if is_merged else "⚠️ Caution Restricted Profile (TSR Active)")
            profile_color = "#10b981" if is_early else ("#f59e0b" if is_merged else "#f97316")

            fig_speed = go.Figure()

            # Max Permissible Sectional Speed Reference
            fig_speed.add_trace(go.Scatter(
                x=km_points, y=[120]*len(km_points),
                mode="lines", name="Max Permissible Speed (120 km/h)",
                line=dict(color="#64748b", dash="dash")
            ))

            # Active Instructed Speed Curve
            fig_speed.add_trace(go.Scatter(
                x=km_points, y=current_profile,
                mode="lines+markers", name=profile_label,
                line=dict(color=profile_color, width=3.5),
                marker=dict(size=8, color=profile_color)
            ))

            # Normal baseline for comparison if in early release or merged state
            if is_early or is_merged:
                fig_speed.add_trace(go.Scatter(
                    x=km_points, y=normal_speeds,
                    mode="lines", name="Previous Caution Restricted Baseline",
                    line=dict(color="#94a3b8", dash="dot", width=1.5)
                ))

            # Highlight the Work Zone (KM 114 to KM 118) directly on the graph to link with Track Map
            zone_fill = "rgba(16,185,129,0.18)" if is_early else ("rgba(245,158,11,0.18)" if is_merged else "rgba(239,68,68,0.18)")
            zone_text = "🟢 WORK ZONE FREED (110 km/h)" if is_early else ("🤝 MERGED MEGA-BLOCK (30 km/h)" if is_merged else "🚧 ACTIVE TSR CAUTION ZONE (30 km/h)")

            fig_speed.add_vrect(
                x0=114, x1=118,
                fillcolor=zone_fill,
                line=dict(color=profile_color, width=1.5, dash="dash"),
                annotation_text=zone_text,
                annotation_position="top left",
                annotation=dict(font_size=10, font_color=profile_color)
            )

            # Physical Station & Asset Markers matching the SVG Track Map
            stations_info = [
                (100, "BZA JN", "top center"),
                (108, "RAYYANAPADU", "top center"),
                (125, "KONDAPALLI", "top center"),
                (135, "MADHIRA", "top center")
            ]
            for st_km, st_name, st_pos in stations_info:
                fig_speed.add_vline(x=st_km, line=dict(color="#334155", width=1, dash="dot"))
                fig_speed.add_annotation(
                    x=st_km, y=130, text=st_name, showarrow=False,
                    font=dict(size=9, color="#94a3b8")
                )

            fig_speed.update_layout(
                title="Locopilot Instructed Speed Profile vs Track Kilometer Post (KM 100 to KM 135)",
                xaxis_title="Track Kilometer Post (KM) — Corresponds 1:1 with Track Map Above",
                yaxis_title="Instructed Speed (km/h)",
                yaxis=dict(range=[0, 140]),
                margin=dict(l=40, r=40, t=50, b=40),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_speed, use_container_width=True)

            # Interactive KM-by-KM Synchronized Telemetry Inspector
            st.markdown("##### 🔍 Kilometer-by-Kilometer Telemetry & In-Cab Advisory Inspector")
            st.caption("Select any track kilometer to inspect the exact signal aspect, permissible speed, and driver advisory linked to both the map and graph above:")

            km_col1, km_col2, km_col3, km_col4 = st.columns(4)
            selected_km = st.select_slider(
                "Select Kilometer Post to Inspect:",
                options=[100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135],
                value=114,
                format_func=lambda x: f"KM {x}"
            )

            # Dynamic lookup based on inspected KM and current simulation state
            km_speed_val = current_profile[km_points.index(selected_km)]
            if selected_km in [114, 116, 118]:
                km_loc_desc = "Inside / Approaching Work Zone (KM 114–118)"
                km_signal_disp = "🟢 Green (Clearance Fit)" if is_early else ("🟡 Yellow (Caution Speed)" if is_merged else "🔴 Red / Amber Caution")
                km_advisory_disp = "Corridor cleared early! Full 110 km/h acceleration authorized." if is_early else ("Multi-crew safety caution: Maintain strict 30 km/h." if is_merged else "Active maintenance gang ahead: Regulate speed to 30 km/h.")
            elif selected_km == 111:
                km_loc_desc = "Advance Distant Warning Signal Post"
                km_signal_disp = "🟢 Green (No Caution)" if is_early else "🟡 Double Yellow (Attention)"
                km_advisory_disp = "Clear run — Maintain cruise speed." if is_early else "Begin gradual service brake application (Target: 45 km/h by KM 114)."
            elif selected_km in [100, 108, 125, 135]:
                km_loc_desc = f"Station Zone ({'BZA JN' if selected_km==100 else ('RAYYANAPADU' if selected_km==108 else ('KONDAPALLI' if selected_km==125 else 'MADHIRA'))})"
                km_signal_disp = "🟢 Green (All Clear)"
                km_advisory_disp = f"Sectional MPS Authorized: {km_speed_val} km/h."
            else:
                km_loc_desc = "Open Intermediate Block Section"
                km_signal_disp = "🟢 Green (Automatic Block)"
                km_advisory_disp = f"Normal cruise running: {km_speed_val} km/h."

            with km_col1:
                st.metric("Inspected Track KM", f"KM {selected_km}", delta=km_loc_desc, delta_color="off")
            with km_col2:
                st.metric("Permissible Speed", f"{km_speed_val} km/h", delta=f"{'+0' if km_speed_val==110 else f'-{110-km_speed_val}'} km/h vs MPS")
            with km_col3:
                st.metric("Signal Aspect on Map", km_signal_disp, delta="Aspect Telemetry", delta_color="off")
            with km_col4:
                st.metric("Safety Headway", "4.8 KM", delta="✓ Zero Collision", delta_color="normal")

            st.info(f"**🧑‍✈️ Locopilot In-Cab Advisory Display at KM {selected_km}:** `{km_advisory_disp}`")

            st.markdown("---")

            # =======================================================================
            # LAYER 4: MULTI-DEPARTMENT BLOCK MERGING CONSOLE (SHADOW BLOCKING)
            # =======================================================================
            st.markdown("#### 🤝 Multi-Department Block Merging (Shadow Block Aggregator)")
            st.caption("When multiple departments request track time on different days, AI clusters them into a single Mega-Block, eliminating repeated corridor shutdowns.")

            merge_ops = merger_agent.find_merge_opportunities()
            if merge_ops:
                for mop in merge_ops[:2]:
                    m_c1, m_c2, m_c3, m_c4 = st.columns([1.5, 1.2, 1.2, 1.5])
                    with m_c1:
                        st.markdown(f"**Section: `{mop['section_id']}`**")
                        depts_badge = " + ".join(mop["departments"])
                        st.caption(f"Departments: `{depts_badge}` ({mop['task_count']} Tasks)")
                    with m_c2:
                        st.metric("Separate Shutdowns", f"{mop['separate_hours']} hrs", delta="3 Days Interrupted", delta_color="inverse")
                    with m_c3:
                        st.metric("Merged Mega-Block", f"{mop['merged_duration_hours']} hrs", delta=f"{mop['corridor_hours_saved']} hrs Saved!", delta_color="normal")
                    with m_c4:
                        st.markdown(f"**Caution Order:** `{mop['caution_order_km']}`")
                        st.caption(f"Speed Regulated to: `{mop['approach_speed_kmh']} km/h` ({mop['recommended_slot']})")
            else:
                st.info("No unmerged multi-department conflicts on the active corridor.")

            st.markdown("---")

            # Detail Tabs
            l_tab1, l_tab2, l_tab3 = st.tabs([
                "📋 Locopilot Speed Advisories Register",
                "🚆 Live Trains Telemetry",
                "🚂 Goods Freight Allocation"
            ])

            with l_tab1:
                df_advisories = loco_agent.get_active_advisories()
                if not df_advisories.empty:
                    st.dataframe(df_advisories, use_container_width=True, hide_index=True)
                else:
                    st.info("No active speed advisories.")

            with l_tab2:
                df_live_trains = loco_agent.get_live_trains()
                if not df_live_trains.empty:
                    st.dataframe(df_live_trains, use_container_width=True, hide_index=True)
                else:
                    st.info("No live train telemetry.")

            with l_tab3:
                conn = get_db()
                df_goods = pd.read_sql("SELECT * FROM goods_forecast ORDER BY expected_rakes DESC", conn)
                conn.close()
                if not df_goods.empty:
                    st.dataframe(df_goods, use_container_width=True, hide_index=True)
                else:
                    st.info("No goods freight forecast data.")

        elif admin_menu == "📩 Department Requests":
            st.subheader("📩 Department Time Slot Requests & Approval Center")
            st.caption("Review incoming corridor maintenance block requests from Engineering, S&T, and TRD. Accept to schedule or Decline to generate AI Conflict Reports.")

            slot_agent = SlotRequestAgent()
            conn = get_db()
            df_reqs = pd.read_sql("SELECT * FROM slot_requests ORDER BY request_id DESC", conn)
            conn.close()

            if not df_reqs.empty:
                pending_df = df_reqs[df_reqs["status"] == "Pending"]
                processed_df = df_reqs[df_reqs["status"] != "Pending"]

                p_cnt = len(pending_df)
                a_cnt = len(df_reqs[df_reqs["status"] == "Accepted"])
                d_cnt = len(df_reqs[df_reqs["status"] == "Declined"])

                m1, m2, m3 = st.columns(3)
                m1.metric("Pending Requests", f"{p_cnt}", delta="Requires Review")
                m2.metric("Accepted Requests", f"{a_cnt}", delta="Scheduled")
                m3.metric("Declined Requests", f"{d_cnt}", delta="AI Conflict Report Sent")

                st.markdown("---")
                st.markdown("### ⏳ Action Panel — Pending Slot Requests")

                if not pending_df.empty:
                    for _, r in pending_df.iterrows():
                        with st.expander(f"📩 Request #{r['request_id']} | {r['department']} | {r['section_id']} | Requested Date: {r['requested_date']} ({r['estimated_duration_hours']} Hours Needed)", expanded=True):
                            c_p1, c_p2 = st.columns([2, 1])
                            with c_p1:
                                st.write(f"• **Department**: `{r['department']}`")
                                st.write(f"• **Section**: `{r['section_id']}`")
                                st.write(f"• **Requested Date & Duration**: `{r['requested_date']}` ({r['estimated_duration_hours']} hours block needed)")
                                st.write(f"• **Defect / Repair**: {r['defect_type']} (`{r['severity']}`)")
                                st.write(f"• **Justification**: {r['justification']}")
                                st.caption(f"Submitted at: {r['created_at']}")

                            with c_p2:
                                st.markdown("##### ⚙️ Decision Controls")
                                admin_note = st.text_input(f"Controller Note / Reason (Req #{r['request_id']})", key=f"note_{r['request_id']}")
                        
                                col_bt1, col_bt2 = st.columns(2)
                                with col_bt1:
                                    if st.button(f"✅ Accept", key=f"acc_{r['request_id']}", type="primary", use_container_width=True):
                                        ok, msg = slot_agent.accept_request(r['request_id'])
                                        st.success(f"Approved Request #{r['request_id']}! Scheduled in tasks to be done.")
                                        st.rerun()

                                with col_bt2:
                                    if st.button(f"❌ Decline", key=f"dec_{r['request_id']}", use_container_width=True):
                                        ok, msg = slot_agent.decline_request(r['request_id'], admin_reason=admin_note)
                                        st.warning(f"Declined Request #{r['request_id']}. AI Conflict Error Report sent to {r['department']}.")
                                        st.rerun()
                else:
                    st.success("✅ All department slot requests have been reviewed and processed!")

                st.markdown("---")
                st.markdown("### 📋 All Department Requests History")
                st.dataframe(df_reqs[["request_id", "department", "section_id", "requested_date", "estimated_duration_hours", "defect_type", "severity", "status", "created_at"]], use_container_width=True, hide_index=True)

                with st.expander("🤖 View Generated AI Conflict & Confirmation Reports"):
                    for _, r in df_reqs.iterrows():
                        if r["ai_analysis_report"]:
                            st.markdown(f"#### Request #{r['request_id']} ({r['department']} — {r['status']})")
                            st.markdown(r["ai_analysis_report"])
                            st.markdown("---")
            else:
                st.info("No slot requests received from departments yet.")

        elif admin_menu == "📅 Maintenance Plans":
            st.subheader("📅 Corridor Maintenance Block Planning Center")
            st.caption("Central Traffic Control periodic schedule view: Switch between the 7-day operational rolling matrix and the 30-day strategic horizon.")

            plan_tab_w, plan_tab_m = st.tabs([
                "📅 7-Day Rolling Weekly Plan",
                "🗓️ 30-Day Strategic Monthly Plan"
            ])

            with plan_tab_w:
                st.markdown("#### 📅 Weekly Corridor Block Schedule (7-Day Horizon)")
                df_weekly = get_full_schedule(horizon="weekly")

                if not df_weekly.empty:
                    df_weekly["Timeline"] = df_weekly.apply(lambda r: f"{format_time_12h(r['planned_start'])} to {format_time_12h(r['planned_end'])}", axis=1)
                    matrix_html = generate_ai_block_plan_matrix_html(df_weekly, current_dept="All Departments", color_mode="department")
                    components.html(matrix_html, height=520, scrolling=True)
                    st.markdown("##### 📋 Weekly Schedule Allocation Table")
                    st.dataframe(df_weekly[["schedule_id", "defect_id", "section_id", "department", "defect_type", "severity", "Timeline", "status", "decided_by"]], use_container_width=True, hide_index=True)
                    display_overall_statistics(df_weekly, context_title="Weekly Plan")
                else:
                    st.warning("No weekly blocks currently planned.")

            with plan_tab_m:
                st.markdown("#### 🗓️ Monthly Corridor Block Schedule (30-Day Strategic Horizon)")
                df_monthly = get_full_schedule(horizon="monthly")

                if df_monthly.empty:
                    st.info("No monthly schedule currently exists.")
                    if st.button("Generate Monthly Plan (30-Day Pass)", type="primary"):
                        with st.spinner("Solving CP-SAT for 30-Day Horizon..."):
                            coord = CoordinatorAgent()
                            res = coord.run_cycle(horizon="monthly")
                            st.success(f"Generated monthly block plan with {len(res)} tasks!")
                            st.rerun()
                else:
                    df_monthly["Timeline"] = df_monthly.apply(lambda r: f"{format_time_12h(r['planned_start'])} to {format_time_12h(r['planned_end'])}", axis=1)
                    st.dataframe(df_monthly[["schedule_id", "defect_id", "section_id", "department", "defect_type", "severity", "Timeline", "status", "decided_by"]], use_container_width=True, hide_index=True)
                    display_overall_statistics(df_monthly, context_title="Monthly Plan")

        elif admin_menu == "🔄 Re-optimize / Override":
            st.subheader("🔄 Scheduling Optimizer & Controller Manual Override Center")
            st.caption("Central Control Authority: Manually adjust block timings, lock/pin critical corridor tasks, grant emergency blocks, and re-run Google OR-Tools CP-SAT with overrides preserved.")

            conn = get_db()
            total_sched = pd.read_sql("SELECT COUNT(*) as c FROM schedule WHERE LOWER(status) != 'cancelled'", conn)["c"].iloc[0]
            total_overrides = pd.read_sql("SELECT COUNT(*) as c FROM schedule WHERE decided_by IN ('controller_override', 'controller_emergency') OR status = 'locked'", conn)["c"].iloc[0]
            open_defects = pd.read_sql("SELECT COUNT(*) as c FROM defects WHERE status = 'Open'", conn)["c"].iloc[0]
            avail_slots = pd.read_sql("SELECT COUNT(*) as c FROM corridor_slots WHERE is_available = 1", conn)["c"].iloc[0]
            conn.close()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Active Scheduled Blocks", f"{total_sched}", delta="Committed Corridor Slots")
            m2.metric("Controller Overrides / Pinned", f"{total_overrides}", delta="Protected from AI")
            m3.metric("Open Backlog Tasks", f"{open_defects}", delta="Pending Allocation")
            m4.metric("Available Corridor Slots", f"{avail_slots}", delta="Track Capacity")

            st.markdown("---")

            ro_tab1, ro_tab2, ro_tab3 = st.tabs([
                "🛠️ Manual Controller Override Console",
                "⚡ Multi-Department CP-SAT Re-Optimizer",
                "🚨 Immediate Emergency Block Grant"
            ])

            with ro_tab1:
                st.markdown("#### 🛠️ Manual Block Override & Schedule Adjuster")
                st.caption("Select any scheduled corridor maintenance block to shift its start/end time, lock it against AI changes, or cancel it to free the corridor slot.")

                conn = get_db()
                df_active = pd.read_sql("""
                    SELECT s.schedule_id, s.defect_id, s.section_id, s.department, s.planned_start, s.planned_end,
                           s.status, s.decided_by, s.slot_id, d.defect_type, d.severity, d.estimated_duration_hours
                    FROM schedule s
                    LEFT JOIN defects d ON s.defect_id = d.defect_id
                    WHERE LOWER(s.status) != 'cancelled'
                    ORDER BY s.schedule_id DESC
                """, conn)
                conn.close()

                if not df_active.empty:
                    st.dataframe(
                        df_active[["schedule_id", "department", "section_id", "defect_type", "severity", "planned_start", "planned_end", "status", "decided_by"]],
                        use_container_width=True,
                        hide_index=True
                    )

                    st.markdown("##### ⚙️ Edit & Override Selected Block")
                    sched_map = {
                        f"Schedule #{r['schedule_id']} | {r['department']} | {r['section_id']} | {r['planned_start']} ({r['defect_type']})": r['schedule_id']
                        for _, r in df_active.iterrows()
                    }
                    selected_label = st.selectbox("Select Block to Modify:", list(sched_map.keys()))
                    sel_id = sched_map[selected_label]
                    sel_row = df_active[df_active["schedule_id"] == sel_id].iloc[0]

                    with st.container():
                        ov_col1, ov_col2 = st.columns(2)
                        with ov_col1:
                            new_start = st.text_input("Planned Start (YYYY-MM-DD HH:MM)", value=str(sel_row['planned_start']), key=f"start_{sel_id}")
                            new_end = st.text_input("Planned End (YYYY-MM-DD HH:MM)", value=str(sel_row['planned_end']), key=f"end_{sel_id}")
                            is_locked = st.checkbox("📌 Lock & Pin this Block (Prevent AI from re-optimizing or moving)", value=(sel_row['status'] == 'locked' or sel_row['decided_by'] == 'controller_override'), key=f"lock_{sel_id}")
                        with ov_col2:
                            override_reason = st.text_input("Controller Justification / Reason for Override", value="VIP train punctuality / Sectional congestion adjustment", key=f"reason_{sel_id}")
                            st.info(f"**Department:** `{sel_row['department']}` | **Section:** `{sel_row['section_id']}`\n\n**Defect:** {sel_row['defect_type']} (`{sel_row['severity']}`)")

                        b_col1, b_col2 = st.columns(2)
                        with b_col1:
                            if st.button("💾 Apply Controller Override", type="primary", use_container_width=True, key=f"save_ov_{sel_id}"):
                                comp = ComplianceAgent()
                                is_valid, reason = comp.validate_override(sel_row['section_id'], new_start, new_end, current_schedule_id=int(sel_id))
                                if not is_valid:
                                    st.error(f"❌ Controller Override Rejected — {reason}")
                                else:
                                    conn = get_db()
                                    new_status = "locked" if is_locked else "planned"
                                    conn.execute(
                                        "UPDATE schedule SET planned_start=?, planned_end=?, status=?, decided_by='controller_override' WHERE schedule_id=?",
                                        (new_start, new_end, new_status, int(sel_id))
                                    )
                                    conn.commit()
                                    conn.close()
                                    st.cache_data.clear()

                                    # Automatic conflict detection & CP-SAT re-optimization pass
                                    coord = CoordinatorAgent()
                                    target_horizon = str(sel_row.get("horizon", "weekly") or "weekly")
                                    coord.resolve_override_and_reschedule(int(sel_id), new_start, new_end, horizon=target_horizon)

                                    log_action("Controller", "manual_override", f"Schedule #{sel_id} updated: {new_start} to {new_end} ({override_reason})")
                                    notify("admin", f"Manual Override: Schedule #{sel_id} ({sel_row['department']}) timing modified by Central Control.", category="controller_override")
                                    st.success(f"✅ Schedule #{sel_id} updated & weekly timetable re-optimized with Controller Override!")
                                    st.rerun()

                        with b_col2:
                            if st.button("❌ Cancel / Postpone Block (Release Slot)", use_container_width=True, key=f"cancel_ov_{sel_id}"):
                                conn = get_db()
                                conn.execute("UPDATE schedule SET status='cancelled', decided_by='controller_cancelled' WHERE schedule_id=?", (int(sel_id),))
                                if sel_row['defect_id']:
                                    conn.execute("UPDATE defects SET status='Open' WHERE defect_id=?", (sel_row['defect_id'],))
                                if sel_row['slot_id']:
                                    conn.execute("UPDATE corridor_slots SET is_available=1 WHERE slot_id=?", (sel_row['slot_id'],))
                                conn.commit()
                                conn.close()
                                st.cache_data.clear()

                                # Re-run optimization pass to allocate released slot
                                coord = CoordinatorAgent()
                                target_horizon = str(sel_row.get("horizon", "weekly") or "weekly")
                                coord.run_cycle(horizon=target_horizon)

                                log_action("Controller", "cancel_block", f"Schedule #{sel_id} cancelled by Controller: {override_reason}")
                                st.warning(f"⚠️ Schedule #{sel_id} cancelled. Corridor slot released and weekly schedule re-optimized.")
                                st.rerun()
                else:
                    st.info("No active scheduled blocks found in the system.")

            with ro_tab2:
                st.markdown("#### ⚡ AI Constraint Re-Optimization (CP-SAT Engine)")
                st.caption("Re-compute the optimal multi-department schedule using Google OR-Tools CP-SAT solver, respecting timetable hard constraints and controller overrides.")

                c_opt1, c_opt2 = st.columns(2)
                with c_opt1:
                    ro_horizon = st.radio("Optimization Horizon", ["weekly", "monthly"], horizontal=True, help="Select weekly (7-day) or monthly (30-day) optimization cycle.")
                    preserve_locked = st.checkbox("🔒 Strictly Preserve Controller Locked / Overridden Blocks", value=True, help="Prevents solver from moving or replacing blocks manually modified by the Controller.")
                with c_opt2:
                    st.info("""
                    **CP-SAT Hard Constraints Enforced:**
                    1. **Zero Department Clashes:** At most 1 maintenance gang per corridor slot.
                    2. **Train Timetable Protection:** Excludes slots that overlap scheduled passenger train paths.
                    3. **Section Spatial Matching:** Defect must match physical corridor slot section.
                    4. **Controller Overrides:** Locked blocks pinned in place.
                    """)

                if st.button("🚀 Run Multi-Department CP-SAT Re-Optimization", type="primary", use_container_width=True):
                    with st.spinner("Evaluating candidate tasks and solving CP-SAT constraint model..."):
                        coord = CoordinatorAgent()
                        result_df = coord.run_cycle(horizon=ro_horizon)
                        if not result_df.empty:
                            st.balloons()
                            st.success(f"✅ Optimization Complete! Successfully scheduled {len(result_df)} candidate tasks into conflict-free corridor slots ({ro_horizon} horizon).")
                            st.dataframe(result_df[["defect_id", "slot_id", "section_id", "department", "planned_start", "planned_end", "decided_by"]], use_container_width=True, hide_index=True)
                        else:
                            st.warning("All eligible open backlog defects have already been allocated, or remaining tasks exceed available conflict-free slot durations.")

            with ro_tab3:
                st.markdown("#### 🚨 Grant Immediate Emergency Block (Direct Line Grant)")
                st.caption("For rail fractures, OHE wire snags, or critical signal failures requiring urgent track access outside pre-scheduled slots.")

                with st.form("emergency_block_form"):
                    em_c1, em_c2 = st.columns(2)
                    with em_c1:
                        em_dept = st.selectbox("Department Requesting Emergency Block", ["Engineering", "S&T", "TRD"])
                        conn = get_db()
                        secs = [s[0] for s in conn.execute("SELECT DISTINCT section_id FROM corridor_slots").fetchall()]
                        conn.close()
                        em_sec = st.selectbox("Track Section", secs if secs else ["Vijayawada-SEC-01", "Guntur-SEC-08", "Hyderabad-SEC-02"])
                        em_defect = st.text_input("Emergency Defect Nature", value="Rail Fracture / Track Weld Displacement (Immediate Danger)")
                    with em_c2:
                        em_sev = st.selectbox("Severity Classification", ["Critical", "High"])
                        em_duration = st.slider("Required Block Duration (Hours)", min_value=0.5, max_value=4.0, value=2.0, step=0.5)
                        em_reason = st.text_input("Emergency Justification / Authority", value="G&SR Rule 4.09 Emergency Track Protection")

                    em_submit = st.form_submit_button("🚨 Authorize & Impose Emergency Corridor Block", type="primary", use_container_width=True)
                    if em_submit:
                        now_dt = datetime.now()
                        end_dt = now_dt + pd.Timedelta(hours=em_duration)
                        now_str = now_dt.strftime("%Y-%m-%d %H:%M")
                        end_str = end_dt.strftime("%Y-%m-%d %H:%M")
                        em_defect_id = f"EMERG-{now_dt.strftime('%m%d%H%M')}"

                        conn = get_db()
                        conn.execute("""
                            INSERT INTO defects (defect_id, section_id, department, defect_type, severity, priority_score, status, estimated_duration_hours, overdue_days, trains_affected_per_day)
                            VALUES (?, ?, ?, ?, ?, 99.9, 'Emergency Active', ?, 0, 15)
                        """, (em_defect_id, em_sec, em_dept, em_defect, em_sev, em_duration))

                        conn.execute("""
                            INSERT INTO schedule (defect_id, slot_id, section_id, department, planned_start, planned_end, horizon, status, decided_by)
                            VALUES (?, 'SLOT-EMERGENCY', ?, ?, ?, ?, 'emergency', 'locked', 'controller_emergency')
                        """, (em_defect_id, em_sec, em_dept, now_str, end_str))

                        # Issue Caution Order into locopilot_speed_advisories
                        try:
                            conn.execute("""
                                INSERT INTO locopilot_speed_advisories (train_id, section_id, station_from, station_to, km_start, km_end, normal_speed_kmh, recommended_speed_kmh, time_saved_minutes, reason, department_notified, status, created_at)
                                VALUES ('ALL-TRAINS', ?, 'BZA', 'KI', 114.0, 118.0, 110.0, 30.0, 0.0, ?, ?, 'Dispatched to Locopilots', ?)
                            """, (em_sec, f"EMERGENCY BLOCK ({em_dept}): {em_defect}", em_dept, now_dt.strftime("%Y-%m-%d %H:%M:%S")))
                        except Exception as adv_err:
                            log_action("Controller", "advisory_warning", f"Locopilot advisory insert note: {adv_err}")

                        conn.commit()
                        conn.close()

                        log_action("Controller", "emergency_block", f"Imposed emergency block on {em_sec} ({em_dept}) for {em_duration} hrs: {em_reason}")
                        notify("admin", f"🚨 EMERGENCY BLOCK IMPOSED on {em_sec} ({em_dept}) until {end_str}. Caution order 30 km/h dispatched.", category="emergency")
                        st.error(f"🚨 EMERGENCY BLOCK GRANTED on {em_sec} until {end_str}! Caution orders transmitted to Locopilots.")
                        st.rerun()

        elif admin_menu == "⚖️ Compliance & Anomalies":
            st.subheader("⚖️ Safety Compliance, Anomaly Detection & Auto-Rescheduling Console")
            st.caption("Scans active corridor schedules for section overlaps, passenger train timetable clashes, and SLA violations. Performs automatic CP-SAT re-optimization or alerts Controller for manual review.")

            comp = ComplianceAgent()

            # 1. Run Anomaly Detection & Auto-Rescheduling Engine
            anomalies = comp.detect_and_handle_anomalies()
            if anomalies:
                st.warning(f"⚠️ Detected {len(anomalies)} schedule anomaly/conflict events across corridor sections:")
                for a in anomalies:
                    st.write(f"- 🔴 **{a['anomaly_id']}** (`{a['section_id']}`): Schedule #{a['r1']['schedule_id']} ({a['r1']['department']}) overlaps with Schedule #{a['r2']['schedule_id']} ({a['r2']['department']}).")
            else:
                st.success("✅ Zero active section schedule anomalies detected! All scheduled windows are conflict-free.")

            st.markdown("---")
            st.markdown("#### 🚨 SLA & Operational Hard Constraint Violations")
            violations = comp.check_schedule()
            if violations:
                st.error(f"Found {len(violations)} SLA violations:")
                for v in violations[:6]:
                    st.write(f"- ⚠️ {v}")
            else:
                st.success("✅ Zero SLA violations detected!")

            st.markdown("---")
            st.markdown("#### 🔍 Active Schedule Backlog Audit")
            conn = get_db()
            df_audit = pd.read_sql("""
                SELECT s.schedule_id, s.defect_id, s.section_id, s.department, s.planned_start, s.planned_end, s.status, s.decided_by
                FROM schedule s
                WHERE LOWER(s.status) != 'cancelled'
                ORDER BY s.section_id, s.planned_start
            """, conn)
            conn.close()
            if not df_audit.empty:
                st.dataframe(df_audit, use_container_width=True, hide_index=True)

        elif admin_menu == "💰 Cost & Simulation":
            st.subheader("Cost Optimization & Downtime Simulation Analytics")
            cost_agent = CostOptimizationAgent()
            cost_metrics = cost_agent.estimate_schedule_cost()
            sim_agent = SimulationAgent()
            sim_metrics = sim_agent.simulate_downtime_avoided()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Labor Cost", f"₹{cost_metrics['total_cost']:,.2f}")
            c2.metric("Grouped Task Savings", f"₹{cost_metrics['grouped_savings']:,.2f}", delta="Saved")
            c3.metric("Corridor Hours Saved", f"{sim_metrics['hours_saved']:.1f} hrs", delta="+37.5%")

        elif admin_menu == "🗄️ Manage Data":
            st.subheader("Data Management & Bulk Multi-Department Ingestion")
            dm_agent = DataManagementAgent()

            c_b1, c_b2 = st.columns([3, 1.2])
            with c_b1:
                st.markdown("### 📁 Batch CSV Defect Upload (All Departments)")
                st.caption("Upload a CSV file containing defect records for Engineering, S&T, and TRD. The AI will classify them by department, assign priority scores, and populate department backlogs.")
            with c_b2:
                st.markdown("<br>", unsafe_allow_html=True)
                show_add_defect = st.button("➕ Add Defect (Manual Entry)", type="primary", use_container_width=True, help="Click to expand single defect entry form")

            with st.expander("➕ Add Single Defect Manually (Quick Entry)", expanded=show_add_defect):
                with st.form("admin_add_defect_quick"):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        d_dept = st.selectbox("Department", ["Engineering", "S&T", "TRD"], key="qd_dept")
                        d_sec = st.text_input("Section ID", "Secunderabad-SEC-01", key="qd_sec")
                    with c2:
                        d_type = st.text_input("Defect Type", "Track geometry deviation", key="qd_type")
                        d_sev = st.selectbox("Severity", ["Critical", "High", "Medium", "Low"], key="qd_sev")
                    with c3:
                        d_dur = st.number_input("Estimated Duration (Hours)", 0.5, 12.0, 2.5, key="qd_dur")
                        d_due = st.date_input("Due Date", datetime.now() + timedelta(days=5), key="qd_due")

                    if st.form_submit_button("➕ Submit & Ingest Single Defect", type="primary", use_container_width=True):
                        new_id = dm_agent.add_defect(d_dept, d_sec, d_type, d_sev, d_due.strftime("%Y-%m-%d"), d_dur, 20)
                        st.success(f"✅ Defect **{new_id}** created successfully and assigned to **{d_dept}** backlog!")
                        st.rerun()

            sample_csv_data = """department,section_id,defect_type,severity,due_date,estimated_duration_hours,trains_affected_per_day
        Engineering,Vijayawada-SEC-02,Rail fracture critical,Critical,2026-09-12,3.5,25
        S&T,Secunderabad-SEC-01,Axle counter failure,High,2026-09-14,2.0,18
        TRD,Guntur-SEC-03,OHE wire sag deviation,Medium,2026-09-15,1.5,12
        Engineering,Hyderabad-SEC-04,Turnout point wear,High,2026-09-16,2.5,20
        S&T,Vijayawada-SEC-03,Signal lamp filament blow,Low,2026-09-20,1.0,8
        """
            st.download_button(
                "📥 Download Sample CSV Template",
                data=sample_csv_data,
                file_name="railway_defects_template.csv",
                mime="text/csv",
                help="Click to download a pre-formatted sample CSV template for multi-department defects upload."
            )

            uploaded_file = st.file_uploader("Choose CSV File to Upload", type=["csv"], key="batch_csv_uploader")
            if uploaded_file is not None:
                try:
                    df_upload = pd.read_csv(uploaded_file)
                    st.markdown("##### 🔍 Uploaded Data Preview")
                    st.dataframe(df_upload.head(10), use_container_width=True, hide_index=True)

                    if st.button("🚀 Process & Ingest Multi-Department CSV Defects", type="primary"):
                        with st.spinner("AI classifying defects by department and calculating priority scores..."):
                            added, errors = dm_agent.bulk_upload_defects(df_upload, source_label="CSV_UPLOAD", uploaded_by="admin")
                            if added > 0:
                                st.success(f"🎉 Successfully ingested **{added}** defects across departments! They are now live in Engineering, S&T, and TRD open backlogs.")
                            if errors:
                                st.warning(f"Notices during ingestion: {errors[:3]}")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error parsing uploaded CSV: {e}")

            st.markdown("---")
            if st.button("🚀 Recompute & Re-schedule All Departments Now", type="primary"):
                coord = CoordinatorAgent()
                res = coord.run_cycle(horizon="weekly")
                st.success(f"Optimization cycle complete. Auto-scheduled {len(res)} tasks.")
                st.rerun()

            st.markdown("---")
            st.markdown("### 📋 Live Ingested Defects & Backlog Registry")
            st.caption("Inspect, search, and verify all maintenance defects currently stored in `railway.db` across departments.")

            col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 1.2, 1.2, 2.5])
            with col_f1:
                f_dept = st.selectbox("Filter Department", ["All Departments", "Engineering", "S&T", "TRD"], key="mg_f_dept")
            with col_f2:
                f_stat = st.selectbox("Status", ["All Statuses", "Open", "Scheduled", "Completed"], key="mg_f_stat")
            with col_f3:
                f_sev = st.selectbox("Severity", ["All Severities", "Critical", "High", "Medium", "Low"], key="mg_f_sev")
            with col_f4:
                f_search = st.text_input("🔍 Search Defect ID / Section / Type", "", key="mg_f_search")

            conn = get_db()
            query = "SELECT defect_id, department, section_id, defect_type, severity, status, priority_score, due_date, estimated_duration_hours, trains_affected_per_day, created_via FROM defects WHERE 1=1"
            params = []

            if f_dept != "All Departments":
                query += " AND department = ?"
                params.append(f_dept)
            if f_stat != "All Statuses":
                query += " AND LOWER(status) = ?"
                params.append(f_stat.lower())
            if f_sev != "All Severities":
                query += " AND severity = ?"
                params.append(f_sev)
            if f_search.strip():
                s_term = f"%{f_search.strip()}%"
                query += " AND (defect_id LIKE ? OR section_id LIKE ? OR defect_type LIKE ?)"
                params.extend([s_term, s_term, s_term])

            query += " ORDER BY priority_score DESC LIMIT 100"
            df_defects_view = pd.read_sql(query, conn, params=params)
            conn.close()

            st.markdown(f"**Showing `{len(df_defects_view)}` records (sorted by AI Priority Score):**")
            st.dataframe(
                df_defects_view,
                column_config={
                    "defect_id": st.column_config.TextColumn("Defect ID", width="small"),
                    "department": st.column_config.TextColumn("Dept", width="small"),
                    "section_id": st.column_config.TextColumn("Section", width="medium"),
                    "defect_type": st.column_config.TextColumn("Defect Description", width="large"),
                    "severity": st.column_config.TextColumn("Severity", width="small"),
                    "status": st.column_config.TextColumn("Status", width="small"),
                    "priority_score": st.column_config.NumberColumn("Priority Score", format="%.1f"),
                    "due_date": st.column_config.TextColumn("Due Date"),
                    "estimated_duration_hours": st.column_config.NumberColumn("Duration (h)", format="%.1f"),
                    "trains_affected_per_day": st.column_config.NumberColumn("Trains/Day"),
                    "created_via": st.column_config.TextColumn("Source", width="small"),
                },
                use_container_width=True,
                hide_index=True
            )


        elif admin_menu == "📄 PDF Reports":
            st.subheader("Export Official Block Plan PDF")
            if st.button("Generate Official Block Plan PDF", type="primary"):
                sch_df = get_full_schedule()
                pdf_path = generate_report(sch_df)
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                st.download_button("📥 Download Block Plan PDF", data=pdf_bytes, file_name=os.path.basename(pdf_path), mime="application/pdf")

    with col_right:
        render_persistent_ai_chatbot_panel(page_context=f"Central Controller > {admin_menu}", department="All")
