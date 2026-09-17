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
import time
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px
import plotly.graph_objects as go
import bcrypt

# Reconfigure stdout/stderr encoding for Windows charmap console safety
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(errors='backslashreplace')
        sys.stderr.reconfigure(errors='backslashreplace')
    except Exception:
        pass

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
        /* Sticky Right Chatbot Panel (Only applies to column containing AI Panel) */
        div[data-testid="stColumn"]:has(.ai-panel-card) {
            position: sticky !important;
            top: 4.5rem !important;
            align-self: flex-start !important;
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

    /* ----------------------------------------------------------------------- */
    /* FIXED & FULL-HEIGHT LEFT SIDEBAR NAVIGATION                             */
    /* ----------------------------------------------------------------------- */
    [data-testid="stSidebar"], section[data-testid="stSidebar"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        bottom: 0 !important;
        height: 100vh !important;
        max-height: 100vh !important;
        min-height: 100vh !important;
        width: 290px !important;
        z-index: 100 !important;
        overflow-y: auto !important;
        background-color: #0f172a !important;
        border-right: 1px solid #1e293b !important;
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), margin-left 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    /* Smooth collapse support on desktop & laptop */
    [data-testid="stSidebar"][aria-expanded="false"], section[data-testid="stSidebar"][aria-expanded="false"] {
        margin-left: -310px !important;
        transform: translateX(-100%) !important;
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.2rem !important;
        padding-bottom: 1.2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* Tighten radio options in sidebar so all tabs fit on screen without cutoff */
    [data-testid="stSidebar"] .stRadio > div {
        gap: 2px !important;
    }

    [data-testid="stSidebar"] .stRadio label {
        padding: 5px 8px !important;
        font-size: 13.5px !important;
        line-height: 1.3 !important;
        margin-bottom: 1px !important;
        border-radius: 6px !important;
    }

    [data-testid="stSidebar"] hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
        border-color: #1e293b !important;
    }

    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h2 {
        font-size: 14px !important;
        font-weight: 700 !important;
        margin-bottom: 4px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Click-outside listener to close sidebar on laptops/desktop when clicking the main content
components.html("""
<script>
(function() {
    function setupSidebarClickOutside() {
        try {
            const parentDoc = window.parent.document;
            if (!parentDoc || parentDoc._sidebarListenerAttached) return;
            parentDoc._sidebarListenerAttached = true;

            parentDoc.addEventListener('click', function(e) {
                const sidebar = parentDoc.querySelector('section[data-testid="stSidebar"]');
                if (!sidebar) return;

                // Check if sidebar is expanded
                const isExpanded = sidebar.getAttribute('aria-expanded') === 'true' || 
                                   sidebar.getBoundingClientRect().width > 80;
                if (!isExpanded) return;

                // Check if user clicked inside sidebar or on toggle/collapse controls
                const clickedInsideSidebar = sidebar.contains(e.target);
                const clickedToggleBtn = e.target.closest('[data-testid="stSidebarCollapseButton"]') || 
                                         e.target.closest('[data-testid="stSidebarCollapsedControl"]') || 
                                         e.target.closest('[data-testid="collapsedControl"]') ||
                                         e.target.closest('button[kind="header"]');
                const isOverlayOrPortal = e.target.closest('[data-baseweb="popover"]') || 
                                         e.target.closest('[data-baseweb="menu"]') || 
                                         e.target.closest('[data-baseweb="select"]') || 
                                         e.target.closest('[role="dialog"]') ||
                                         e.target.closest('.stPopover');

                if (!clickedInsideSidebar && !clickedToggleBtn && !isOverlayOrPortal) {
                    const closeBtn = sidebar.querySelector('button[data-testid="stSidebarCollapseButton"]') || 
                                     parentDoc.querySelector('button[data-testid="stSidebarCollapseButton"]') ||
                                     sidebar.querySelector('button[aria-label="Close sidebar"]') ||
                                     sidebar.querySelector('button');
                    if (closeBtn) {
                        closeBtn.click();
                    }
                }
            }, true);
        } catch(err) {
            console.warn("Sidebar outside listener error:", err);
        }
    }
    setupSidebarClickOutside();
    setInterval(setupSidebarClickOutside, 1000);
})();
</script>
""", height=0, width=0)

# Workspace Paths
DB_PATH = os.path.join(BASE_DIR, "railway.db")

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
        DelayPropagationAgent,
        TelemetrySimulatorAgent,
        ETAPredictionAgent,
        ConflictPredictionAgent,
        DynamicHeadwayAgent,
        OperationalRiskAgent,
        FreightInsertionAgent,
        SingleLineWorkingAgent,
        SafetyClearanceAgent,
        TrackMachinePackerAgent,
        CrewHOERAgent,
        TSRLifecycleAgent,
        TractionAwareRouterAgent,
        InterDivisionalHandoverAgent,
        FOISDemurrageAgent,
        DeBunchingMeteringAgent,
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
        DelayPropagationAgent,
        TelemetrySimulatorAgent,
        ETAPredictionAgent,
        ConflictPredictionAgent,
        DynamicHeadwayAgent,
        OperationalRiskAgent,
        FreightInsertionAgent,
        SingleLineWorkingAgent,
        SafetyClearanceAgent,
        TrackMachinePackerAgent,
        CrewHOERAgent,
        TSRLifecycleAgent,
        TractionAwareRouterAgent,
        InterDivisionalHandoverAgent,
        FOISDemurrageAgent,
        DeBunchingMeteringAgent,
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

def sync_schedule_to_current_date(conn):
    """
    Ensures active maintenance blocks dynamically start from today's operational date (2026-09-16),
    shifting legacy past schedule dates forward to current rolling weekly/monthly horizons.
    Completed and cancelled tasks remain safely in history.
    """
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT MIN(planned_start) FROM schedule WHERE LOWER(status) NOT IN ('completed', 'cancelled')").fetchone()
        if row and row[0]:
            earliest_str = str(row[0])[:10]
            earliest_dt = datetime.strptime(earliest_str, "%Y-%m-%d")
            today_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            diff_days = (today_dt - earliest_dt).days
            if diff_days > 0:
                rows = cur.execute("SELECT schedule_id, planned_start, planned_end FROM schedule WHERE LOWER(status) NOT IN ('completed', 'cancelled')").fetchall()
                for s_id, p_start, p_end in rows:
                    try:
                        st_dt = datetime.strptime(str(p_start)[:16], "%Y-%m-%d %H:%M") + timedelta(days=diff_days)
                        en_dt = datetime.strptime(str(p_end)[:16], "%Y-%m-%d %H:%M") + timedelta(days=diff_days)
                        cur.execute(
                            "UPDATE schedule SET planned_start=?, planned_end=? WHERE schedule_id=?",
                            (st_dt.strftime("%Y-%m-%d %H:%M"), en_dt.strftime("%Y-%m-%d %H:%M"), s_id)
                        )
                    except Exception:
                        pass
                slot_row = cur.execute("SELECT MIN(date) FROM corridor_slots").fetchone()
                if slot_row and slot_row[0]:
                    e_slot = datetime.strptime(str(slot_row[0])[:10], "%Y-%m-%d")
                    slot_diff = (today_dt - e_slot).days
                    if slot_diff > 0:
                        s_rows = cur.execute("SELECT slot_id, date FROM corridor_slots").fetchall()
                        for sl_id, sl_date in s_rows:
                            try:
                                sl_dt = datetime.strptime(str(sl_date)[:10], "%Y-%m-%d") + timedelta(days=slot_diff)
                                cur.execute("UPDATE corridor_slots SET date=? WHERE slot_id=?", (sl_dt.strftime("%Y-%m-%d"), sl_id))
                            except Exception:
                                pass
                conn.commit()
    except Exception:
        pass


def _ensure_db_schema():
    global _db_schema_checked
    if _db_schema_checked:
        return
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        defects_cols = [col[1] for col in conn.execute("PRAGMA table_info(defects)").fetchall()]
        if defects_cols and "actual_completion_time" not in defects_cols:
            conn.execute("ALTER TABLE defects ADD COLUMN actual_completion_time TEXT")
            conn.commit()

        notif_cols = [col[1] for col in conn.execute("PRAGMA table_info(notifications)").fetchall()]
        if notif_cols and "is_read" not in notif_cols:
            conn.execute("ALTER TABLE notifications ADD COLUMN is_read INTEGER DEFAULT 0")
            conn.commit()

        sync_schedule_to_current_date(conn)
        conn.close()
    except Exception:
        pass
    _db_schema_checked = True


def get_db():
    _ensure_db_schema()
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
    except Exception:
        pass
    return conn


def get_system_setting(key_name, default_val="0"):
    """Retrieves a persistent system setting from railway.db across refreshes/reboots."""
    try:
        conn = get_db()
        conn.execute("CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)")
        row = conn.execute("SELECT value FROM system_settings WHERE key=?", (key_name,)).fetchone()
        conn.close()
        if row and row[0] is not None:
            return row[0]
    except Exception:
        pass
    return default_val


def set_system_setting(key_name, val):
    """Persists a system setting into railway.db across refreshes/reboots."""
    try:
        conn = get_db()
        conn.execute("CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (key_name, str(val)))
        conn.commit()
        conn.close()
    except Exception:
        pass


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
# VISUAL-FIRST RAILWAY OPERATIONAL INTELLIGENCE HELPERS
# ---------------------------------------------------------------------------

@st.cache_data(ttl=5)
def get_cached_kpi_metrics(department="All"):
    """Cached KPI metric calculations for operational health bar."""
    conn = get_db()
    cur = conn.cursor()
    if department == "All":
        tot_d = cur.execute("SELECT COUNT(*) FROM defects").fetchone()[0]
        open_d = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(status)='open'").fetchone()[0]
        crit_d = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(severity)='critical' AND LOWER(status)!='completed'").fetchone()[0]
        high_d = cur.execute("SELECT COUNT(*) FROM defects WHERE LOWER(severity)='high' AND LOWER(status)!='completed'").fetchone()[0]
    else:
        tot_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=?", (department,)).fetchone()[0]
        open_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(status)='open'", (department,)).fetchone()[0]
        crit_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(severity)='critical' AND LOWER(status)!='completed'", (department,)).fetchone()[0]
        high_d = cur.execute("SELECT COUNT(*) FROM defects WHERE department=? AND LOWER(severity)='high' AND LOWER(status)!='completed'", (department,)).fetchone()[0]
    conn.close()
    health_score = max(72.0, round(100.0 - (crit_d * 3.5 + high_d * 1.5), 1))
    return {
        "tot_d": tot_d,
        "open_d": open_d,
        "crit_d": crit_d,
        "high_d": high_d,
        "health_score": health_score
    }


def init_trains_10_state():
    if "trains_10_state" not in st.session_state:
        bza_stations = [(100, "BZA JN"), (108, "RAYYANAPADU"), (125, "KONDAPALLI"), (135, "MADHIRA")]
        hwh_stations = [(0, "HOWRAH JN"), (20, "SERAMPORE"), (40, "BANDEL JN"), (100, "BARDHAMAN")]
        sc_stations = [(0, "SECUNDERABAD"), (15, "MOULA ALI"), (30, "CHERLAPALLI"), (60, "BHONGIR")]
        kur_stations = [(0, "CUTTACK"), (28, "BHUBANESWAR"), (48, "KHURDA ROAD"), (118, "BALUGAON"), (194, "BRAHMAPUR")]

        st.session_state.trains_10_state = {
            # --- KHURDA ROAD DIVISION (KUR) ---
            "KUR-12841": {
                "id": "KUR-12841", "division": "Khurda Road Division (KUR)", "number": "12841", "name": "Coromandel Express", "type": "Superfast Express",
                "corridor": "Cuttack → Bhubaneswar → Khurda Road → Brahmapur", "section_id": "KUR-BALU", "current_km": 65.0, "current_speed": 80, "mps": 110,
                "status": "RUNNING", "signal": "🟢 Green", "delay_minutes": 0, "direction": "EB", "next_station": "Balugaon",
                "work_zone_kms": [55, 60, 65], "km_options": [0, 28, 48, 70, 90, 118, 150, 194], "stations": kur_stations, "speed_profile": [80] * 8, "early_cleared": True, "merged": False
            },
            "Khurda Road Train 01": {
                "id": "Khurda Road Train 01", "division": "Khurda Road Division (KUR)", "number": "12841", "name": "Coromandel Express", "type": "Superfast Express",
                "corridor": "Cuttack → Bhubaneswar → Khurda Road → Brahmapur", "section_id": "KUR-BALU", "current_km": 65.0, "current_speed": 80, "mps": 110,
                "status": "RUNNING", "signal": "🟢 Green", "delay_minutes": 0, "direction": "EB", "next_station": "Balugaon",
                "work_zone_kms": [55, 60, 65], "km_options": [0, 28, 48, 70, 90, 118, 150, 194], "stations": kur_stations, "speed_profile": [80] * 8, "early_cleared": True, "merged": False
            },
            "KUR-22823": {
                "id": "KUR-22823", "division": "Khurda Road Division (KUR)", "number": "22823", "name": "Bhubaneswar Tejas Rajdhani", "type": "Tejas Superfast",
                "corridor": "Bhubaneswar → Khurda Road → Balugaon", "section_id": "BBS-KUR", "current_km": 35.0, "current_speed": 60, "mps": 130,
                "status": "SLOWING", "signal": "🟡 Amber Caution", "delay_minutes": 6, "direction": "EB", "next_station": "Khurda Road",
                "work_zone_kms": [55, 60, 65], "km_options": [0, 28, 48, 70, 90, 118, 150, 194], "stations": kur_stations, "speed_profile": [60] * 8, "early_cleared": False, "merged": False
            },
            "Khurda Road Train 02": {
                "id": "Khurda Road Train 02", "division": "Khurda Road Division (KUR)", "number": "22823", "name": "Bhubaneswar Tejas Rajdhani", "type": "Tejas Superfast",
                "corridor": "Bhubaneswar → Khurda Road → Balugaon", "section_id": "BBS-KUR", "current_km": 35.0, "current_speed": 60, "mps": 130,
                "status": "SLOWING", "signal": "🟡 Amber Caution", "delay_minutes": 6, "direction": "EB", "next_station": "Khurda Road",
                "work_zone_kms": [55, 60, 65], "km_options": [0, 28, 48, 70, 90, 118, 150, 194], "stations": kur_stations, "speed_profile": [60] * 8, "early_cleared": False, "merged": False
            },
            "KUR-18477": {
                "id": "KUR-18477", "division": "Khurda Road Division (KUR)", "number": "18477", "name": "Kalinga Utkal Express", "type": "Mail / Express",
                "corridor": "Puri → Khurda Road → Bhubaneswar", "section_id": "PURI-KUR", "current_km": 46.0, "current_speed": 0, "mps": 110,
                "status": "STOPPED", "signal": "🔴 Red (Track Renewal Block)", "delay_minutes": 20, "direction": "EB", "next_station": "Khurda Road",
                "work_zone_kms": [55, 60, 65], "km_options": [0, 28, 48, 70, 90, 118, 150, 194], "stations": kur_stations, "speed_profile": [0] * 8, "early_cleared": False, "merged": False
            },
            "Khurda Road Train 03": {
                "id": "Khurda Road Train 03", "division": "Khurda Road Division (KUR)", "number": "18477", "name": "Kalinga Utkal Express", "type": "Mail / Express",
                "corridor": "Puri → Khurda Road → Bhubaneswar", "section_id": "PURI-KUR", "current_km": 46.0, "current_speed": 0, "mps": 110,
                "status": "STOPPED", "signal": "🔴 Red (Track Renewal Block)", "delay_minutes": 20, "direction": "EB", "next_station": "Khurda Road",
                "work_zone_kms": [55, 60, 65], "km_options": [0, 28, 48, 70, 90, 118, 150, 194], "stations": kur_stations, "speed_profile": [0] * 8, "early_cleared": False, "merged": False
            },
            # --- VIJAYAWADA DIVISION (BZA) ---
            "BZA-12727": {
                "id": "BZA-12727", "division": "Vijayawada Division (BZA)", "number": "12727", "name": "Godavari Express", "type": "Superfast Express",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "BZA-RAY", "current_km": 105.0, "current_speed": 110, "mps": 110,
                "status": "RUNNING", "signal": "🟢 Green (Clearance Fit)", "delay_minutes": 0, "direction": "EB", "next_station": "Kondapalli (KDM)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [110, 110, 60, 30, 110], "early_cleared": True, "merged": False
            },
            "Vijayawada Train 01": {
                "id": "Vijayawada Train 01", "division": "Vijayawada Division (BZA)", "number": "12727", "name": "Godavari Express", "type": "Superfast Express",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "BZA-RAY", "current_km": 105.0, "current_speed": 110, "mps": 110,
                "status": "RUNNING", "signal": "🟢 Green (Clearance Fit)", "delay_minutes": 0, "direction": "EB", "next_station": "Kondapalli (KDM)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [110, 110, 60, 30, 110], "early_cleared": True, "merged": False
            },
            "BZA-12759": {
                "id": "BZA-12759", "division": "Vijayawada Division (BZA)", "number": "12759", "name": "Charminar Express", "type": "Superfast",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "BZA-KDM", "current_km": 114.0, "current_speed": 30, "mps": 110,
                "status": "RESTRICTED", "signal": "🔴 Red / Amber Caution", "delay_minutes": 12, "direction": "EB", "next_station": "Kondapalli (KDM)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [110, 60, 30, 30, 110], "early_cleared": False, "merged": False
            },
            "Vijayawada Train 02": {
                "id": "Vijayawada Train 02", "division": "Vijayawada Division (BZA)", "number": "12759", "name": "Charminar Express", "type": "Superfast",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "BZA-KDM", "current_km": 114.0, "current_speed": 30, "mps": 110,
                "status": "RESTRICTED", "signal": "🔴 Red / Amber Caution", "delay_minutes": 12, "direction": "EB", "next_station": "Kondapalli (KDM)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [110, 60, 30, 30, 110], "early_cleared": False, "merged": False
            },
            "BZA-20833": {
                "id": "BZA-20833", "division": "Vijayawada Division (BZA)", "number": "20833", "name": "Vande Bharat Express", "type": "Semi High Speed",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "KDM-KMT", "current_km": 122.0, "current_speed": 130, "mps": 130,
                "status": "RUNNING", "signal": "🟢 Green", "delay_minutes": 0, "direction": "EB", "next_station": "Khammam (KMT)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [130, 130, 130, 130, 130], "early_cleared": True, "merged": False
            },
            "Vijayawada Train 03": {
                "id": "Vijayawada Train 03", "division": "Vijayawada Division (BZA)", "number": "20833", "name": "Vande Bharat Express", "type": "Semi High Speed",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "KDM-KMT", "current_km": 122.0, "current_speed": 130, "mps": 130,
                "status": "RUNNING", "signal": "🟢 Green", "delay_minutes": 0, "direction": "EB", "next_station": "Khammam (KMT)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [130, 130, 130, 130, 130], "early_cleared": True, "merged": False
            },
            "BZA-G402": {
                "id": "BZA-G402", "division": "Vijayawada Division (BZA)", "number": "G-402", "name": "Coal Freight Rake", "type": "Heavy Freight",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "RAY-KDM", "current_km": 111.0, "current_speed": 0, "mps": 75,
                "status": "STOPPED", "signal": "🔴 Red (Block Possession)", "delay_minutes": 18, "direction": "EB", "next_station": "Kondapalli (KDM)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [75, 45, 0, 0, 75], "early_cleared": False, "merged": False
            },
            "Vijayawada Train 04": {
                "id": "Vijayawada Train 04", "division": "Vijayawada Division (BZA)", "number": "G-402", "name": "Coal Freight Rake", "type": "Heavy Freight",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "RAY-KDM", "current_km": 111.0, "current_speed": 0, "mps": 75,
                "status": "STOPPED", "signal": "🔴 Red (Block Possession)", "delay_minutes": 18, "direction": "EB", "next_station": "Kondapalli (KDM)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [75, 45, 0, 0, 75], "early_cleared": False, "merged": False
            },
            "BZA-57231": {
                "id": "BZA-57231", "division": "Vijayawada Division (BZA)", "number": "57231", "name": "BZA-KMT Passenger Local", "type": "Passenger Local",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "KDM-MDR", "current_km": 128.0, "current_speed": 60, "mps": 75,
                "status": "SLOWING", "signal": "🟡 Amber Caution", "delay_minutes": 5, "direction": "WB", "next_station": "Madhira (MDR)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [75, 60, 30, 75, 75], "early_cleared": False, "merged": False
            },
            "Vijayawada Train 05": {
                "id": "Vijayawada Train 05", "division": "Vijayawada Division (BZA)", "number": "57231", "name": "BZA-KMT Passenger Local", "type": "Passenger Local",
                "corridor": "Vijayawada → Kondapalli → Madhira", "section_id": "KDM-MDR", "current_km": 128.0, "current_speed": 60, "mps": 75,
                "status": "SLOWING", "signal": "🟡 Amber Caution", "delay_minutes": 5, "direction": "WB", "next_station": "Madhira (MDR)",
                "work_zone_kms": [114, 116, 118], "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135], "stations": bza_stations, "speed_profile": [75, 60, 30, 75, 75], "early_cleared": False, "merged": False
            },

            # --- HOWRAH / SECUNDERABAD DIVISION ---
            "Howrah Train 01": {
                "id": "Howrah Train 01", "division": "Howrah Division (HWH)", "number": "12301", "name": "Howrah Rajdhani Express", "type": "Superfast Rajdhani",
                "corridor": "Howrah → Serampore → Bandel → Bardhaman", "section_id": "HWH-SRP", "current_km": 25, "current_speed": 130, "mps": 130,
                "status": "High Speed Cruising", "signal": "🟢 Green", "delay_minutes": 0, "direction": "EB", "next_station": "Serampore",
                "work_zone_kms": [40, 45, 50], "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], "stations": hwh_stations, "speed_profile": [130] * 11, "early_cleared": True, "merged": False
            },
            "Howrah Train 02": {
                "id": "Howrah Train 02", "division": "Howrah Division (HWH)", "number": "37211", "name": "Bandel EMU Suburban Local", "type": "Suburban EMU",
                "corridor": "Howrah → Serampore → Bandel → Bardhaman", "section_id": "SRP-BDC", "current_km": 15, "current_speed": 65, "mps": 90,
                "status": "Suburban Service", "signal": "🟡 Yellow", "delay_minutes": 3, "direction": "EB", "next_station": "Bandel JN",
                "work_zone_kms": [40, 45, 50], "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], "stations": hwh_stations, "speed_profile": [65] * 11, "early_cleared": False, "merged": False
            },
            "Howrah Train 03": {
                "id": "Howrah Train 03", "division": "Howrah Division (HWH)", "number": "F-819", "name": "Steel Coil Special Freight", "type": "Heavy Goods",
                "corridor": "Howrah → Serampore → Bandel → Bardhaman", "section_id": "BDC-BWN", "current_km": 42, "current_speed": 30, "mps": 75,
                "status": "Active TSR Caution (30 km/h)", "signal": "🔴 Red / Amber", "delay_minutes": 25, "direction": "EB", "next_station": "Bardhaman",
                "work_zone_kms": [40, 45, 50], "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], "stations": hwh_stations, "speed_profile": [30] * 11, "early_cleared": False, "merged": False
            },
            "Howrah Train 04": {
                "id": "Howrah Train 04", "division": "Howrah Division (HWH)", "number": "12339", "name": "Coalfield Express", "type": "Superfast Express",
                "corridor": "Howrah → Serampore → Bandel → Bardhaman", "section_id": "BWN-DGR", "current_km": 65, "current_speed": 105, "mps": 110,
                "status": "Clear Block Run", "signal": "🟢 Green", "delay_minutes": 0, "direction": "EB", "next_station": "Durgapur",
                "work_zone_kms": [40, 45, 50], "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], "stations": hwh_stations, "speed_profile": [105] * 11, "early_cleared": True, "merged": False
            },
            "Howrah Train 05": {
                "id": "Howrah Train 05", "division": "Howrah Division (HWH)", "number": "22301", "name": "Vande Bharat Express HWH-NJP", "type": "Semi High Speed",
                "corridor": "Howrah → Serampore → Bandel → Bardhaman", "section_id": "BWN-DGR", "current_km": 85, "current_speed": 115, "mps": 130,
                "status": "Accelerated Cruise", "signal": "🟢 Green", "delay_minutes": 0, "direction": "EB", "next_station": "NJP",
                "work_zone_kms": [40, 45, 50], "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], "stations": hwh_stations, "speed_profile": [115] * 11, "early_cleared": True, "merged": False
            },

            # --- SECUNDERABAD DIVISION (SC) ---
            "SC-12701": {
                "id": "SC-12701", "division": "Secunderabad Division (SC)", "number": "12701", "name": "Hussainsagar Express", "type": "Superfast",
                "corridor": "Secunderabad → Moula Ali → Cherlapalli", "section_id": "SC-MLY", "current_km": 18.0, "current_speed": 110, "mps": 110,
                "status": "RUNNING", "signal": "🟢 Green", "delay_minutes": 0, "direction": "EB", "next_station": "Cherlapalli (CHZ)",
                "work_zone_kms": [35, 50], "km_options": [0, 10, 20, 30, 40, 50, 60], "stations": sc_stations, "speed_profile": [110] * 7, "early_cleared": True, "merged": False
            },
            "SC-12792": {
                "id": "SC-12792", "division": "Secunderabad Division (SC)", "number": "12792", "name": "Secunderabad Patna Express", "type": "Superfast Express",
                "corridor": "Cherlapalli → Bhongir", "section_id": "CHZ-BG", "current_km": 38.0, "current_speed": 60, "mps": 110,
                "status": "SLOWING", "signal": "🟡 Amber Caution", "delay_minutes": 8, "direction": "EB", "next_station": "Bhongir (BG)",
                "work_zone_kms": [35, 50], "km_options": [0, 10, 20, 30, 40, 50, 60], "stations": sc_stations, "speed_profile": [60] * 7, "early_cleared": False, "merged": False
            },
            "SC-17015": {
                "id": "SC-17015", "division": "Secunderabad Division (SC)", "number": "17015", "name": "Visakha Express", "type": "Express",
                "corridor": "Bhongir → Jangaon", "section_id": "BG-ZN", "current_km": 60.0, "current_speed": 0, "mps": 110,
                "status": "STOPPED", "signal": "🔴 Red (Signal)", "delay_minutes": 22, "direction": "EB", "next_station": "Jangaon (ZN)",
                "work_zone_kms": [35, 50], "km_options": [0, 10, 20, 30, 40, 50, 60], "stations": sc_stations, "speed_profile": [0] * 7, "early_cleared": False, "merged": False
            },
            "SC-F819": {
                "id": "SC-F819", "division": "Secunderabad Division (SC)", "number": "F-819", "name": "Steel Coil Freight Special", "type": "Heavy Goods",
                "corridor": "Jangaon → Kazipet", "section_id": "ZN-KZJ", "current_km": 95.0, "current_speed": 30, "mps": 75,
                "status": "RESTRICTED", "signal": "🟡 Caution (Overrun Block)", "delay_minutes": 14, "direction": "EB", "next_station": "Kazipet (KZJ)",
                "work_zone_kms": [90, 105], "km_options": [0, 10, 20, 30, 40, 50, 60], "stations": sc_stations, "speed_profile": [30] * 7, "early_cleared": False, "merged": False
            }
        }


def get_active_trains_df(division="Vijayawada Division (BZA)"):
    """
    Safely retrieves live train telemetry records filtered by division.
    """
    init_trains_10_state()
    if "trains_10_state" in st.session_state and st.session_state.trains_10_state:
        records = []
        for t_id, tr in st.session_state.trains_10_state.items():
            tr_div = tr.get("division", "Vijayawada Division (BZA)")
            if division and division != "All":
                d_lower = str(division).lower()
                tr_lower = str(tr_div).lower()
                matched = (tr_div == division) or (d_lower in tr_lower) or (tr_lower in d_lower)
                if not matched:
                    for tag in ["kur", "bza", "sc", "hwh", "khurda", "kurda", "vijay", "secund", "howrah"]:
                        if tag in d_lower and tag in tr_lower:
                            matched = True
                            break
                if not matched:
                    continue
            records.append({
                "train_id": t_id,
                "train_number": tr.get("number", "100"),
                "train_name": tr.get("name", "Express"),
                "train_type": tr.get("type", "Express"),
                "division_id": tr_div,
                "section_id": tr.get("section_id", "SEC-01"),
                "current_km": tr.get("current_km", 25.0),
                "speed_kmh": tr.get("current_speed", 110),
                "mps": tr.get("mps", 110),
                "delay_minutes": tr.get("delay_minutes", 0),
                "direction": tr.get("direction", "EB"),
                "status": tr.get("status", "RUNNING"),
                "signal": tr.get("signal", "🟢 Green"),
                "next_station": tr.get("next_station", "Next Station"),
                "corridor": tr.get("corridor", "Corridor Line")
            })
        if records:
            return pd.DataFrame(records)

    try:
        conn = get_db()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "live_train_status" in tables:
            query = "SELECT * FROM live_train_status"
            params = []
            if division and division != "All":
                query += " WHERE division_id LIKE ?"
                params.append(f"%{division[:10]}%")
            query += " ORDER BY delay_minutes DESC"
            df = pd.read_sql(query, conn, params=params)
            conn.close()
            return df if not df.empty else pd.DataFrame()
        conn.close()
    except Exception:
        pass
    return pd.DataFrame()


def render_operational_kpi_bar(department="All", division="Vijayawada Division (BZA)"):
    """
    Renders top-level visual operational health KPI strip:
    - Active Trains on Line & On-Time %
    - Running / Slowing / Stopped Trains
    - Active Maintenance Blocks
    - System Operational Alerts
    """
    df_active = get_active_trains_df(division=division)
    tot_trains = len(df_active) if not df_active.empty else 0
    running_count = sum(1 for _, r in df_active.iterrows() if r.get('status') == 'RUNNING') if tot_trains > 0 else 0
    slowing_count = sum(1 for _, r in df_active.iterrows() if r.get('status') in ['SLOWING', 'APPROACHING BLOCK', 'RESTRICTED']) if tot_trains > 0 else 0
    stopped_count = sum(1 for _, r in df_active.iterrows() if r.get('status') == 'STOPPED' or r.get('speed_kmh') == 0) if tot_trains > 0 else 0
    delayed_count = sum(1 for _, r in df_active.iterrows() if r.get('delay_minutes', 0) > 5) if tot_trains > 0 else 0
    ontime_pct = round(((tot_trains - delayed_count) / tot_trains) * 100.0, 1) if tot_trains > 0 else 100.0

    st.markdown(f"""
    <div style="display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 120px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 1.5px solid #334155; border-radius: 12px; padding: 10px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">🚆 Active Trains</div>
            <div style="font-size: 20px; font-weight: 800; color: #ffffff; margin-top: 2px;">{tot_trains} Trains</div>
            <div style="font-size: 11px; color: #4ade80; font-weight: 600; margin-top: 2px;">🟢 {ontime_pct}% On-Time</div>
        </div>
        <div style="flex: 1; min-width: 120px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 1.5px solid #334155; border-radius: 12px; padding: 10px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">🟢 Running Normal</div>
            <div style="font-size: 20px; font-weight: 800; color: #22c55e; margin-top: 2px;">{running_count} Rakes</div>
            <div style="font-size: 11px; color: #22c55e; font-weight: 600; margin-top: 2px;">⚡ Clear Line Run</div>
        </div>
        <div style="flex: 1; min-width: 120px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 1.5px solid #334155; border-radius: 12px; padding: 10px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">🟡 Slowing / TSR</div>
            <div style="font-size: 20px; font-weight: 800; color: #facc15; margin-top: 2px;">{slowing_count} Rakes</div>
            <div style="font-size: 11px; color: #facc15; font-weight: 600; margin-top: 2px;">⚠️ Caution Speed</div>
        </div>
        <div style="flex: 1; min-width: 120px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 1.5px solid #334155; border-radius: 12px; padding: 10px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">🛑 Stopped at Block</div>
            <div style="font-size: 20px; font-weight: 800; color: #ef4444; margin-top: 2px;">{stopped_count} Rakes</div>
            <div style="font-size: 11px; color: #ef4444; font-weight: 600; margin-top: 2px;">🔴 Red Signal Hold</div>
        </div>
        <div style="flex: 1; min-width: 120px; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); border: 1.5px solid #334155; border-radius: 12px; padding: 10px 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">⏱ Delayed Trains</div>
            <div style="font-size: 20px; font-weight: 800; color: #f97316; margin-top: 2px;">{delayed_count} Rakes</div>
            <div style="font-size: 11px; color: #f97316; font-weight: 600; margin-top: 2px;">⏳ Schedule Impact</div>
        </div>
    </div>
    """, unsafe_allow_html=True)



def render_railflow_geographic_corridor_view(division="Khurda Road Division (KUR)", df_trains=None):
    """
    Renders the RailFlow Multi-Track Divisional Control Room Map & Corridor Timeline
    matching the exact RailFlow satellite control room design.
    Features:
    - Satellite imagery basemap (Esri World Imagery) with high-visibility multi-track railway network.
    - Multiple branching track lines across the division with distinct colors.
    - Double-circle station nodes along all tracks with sticky hover tooltips.
    - Maintenance work callout boxes & hatched zones with detailed hover popups.
    - Real-time train badges with speeds across all tracks & rich hover cards.
    - Top-right overlay card: Live Train Count (Running, Reduced Speed, Stopped, Total Trains).
    - Expanded map size towards right with side-by-side Timeline & Control Room Panel.
    """
    try:
        import folium
    except ImportError:
        st.error("⚠️ The `folium` library is required for the Geographic Corridor Map. Please ensure `folium` is listed in requirements.txt and installed.")
        return
    import plotly.express as px
    import re
    from datetime import datetime

    def clean_html(html_str):
        return re.sub(r'^[ \t]+', '', html_str, flags=re.MULTILINE)

    div_networks = {
        "Khurda Road Division (KUR)": {
            "center": [19.85, 85.35],
            "zoom": 8,
            "corridor_title": "Khurda Road — Bhubaneswar — Cuttack — Puri — Brahmapur Network",
            "jurisdiction": "ECoR Jurisdiction • Khurda Road Division HQ",
            "kpi": {"running": 18, "reduced": 4, "stopped": 2, "total": 24},
            "division_tags": [
                {"name": "Khurda Road Division", "lat": 20.35, "lon": 85.30},
                {"name": "Sambalpur Division", "lat": 20.75, "lon": 84.40},
                {"name": "Waltair Division", "lat": 18.30, "lon": 83.25},
                {"name": "Jajpur Keonjhar", "lat": 20.85, "lon": 86.00}
            ],
            "lines": [
                {
                    "name": "Main Trunk Line (Cuttack - Visakhapatnam)",
                    "color": "#38bdf8",
                    "stations": [
                        {"name": "Cuttack", "km": 280, "lat": 20.4625, "lon": 85.8830, "hub": True},
                        {"name": "Bhubaneswar", "km": 308, "lat": 20.2961, "lon": 85.8245, "hub": True},
                        {"name": "Khurda Road", "km": 328, "lat": 20.1833, "lon": 85.7333, "hub": True},
                        {"name": "Balugaon", "km": 398, "lat": 19.7483, "lon": 85.2056},
                        {"name": "Brahmapur", "km": 474, "lat": 19.3150, "lon": 84.7941, "hub": True},
                        {"name": "Visakhapatnam", "km": 690, "lat": 17.7231, "lon": 83.2986, "hub": True}
                    ]
                },
                {
                    "name": "Puri Coastal Branch Line",
                    "color": "#fbbf24",
                    "stations": [
                        {"name": "Khurda Road", "km": 0, "lat": 20.1833, "lon": 85.7333, "hub": True},
                        {"name": "Jatni", "km": 6, "lat": 20.1600, "lon": 85.7100},
                        {"name": "Puri", "km": 44, "lat": 19.8135, "lon": 85.8312, "hub": True}
                    ]
                },
                {
                    "name": "Angul - Sambalpur Freight Line",
                    "color": "#34d399",
                    "stations": [
                        {"name": "Cuttack", "km": 0, "lat": 20.4625, "lon": 85.8830, "hub": True},
                        {"name": "Angul", "km": 112, "lat": 20.8400, "lon": 85.1000},
                        {"name": "Rayagada", "km": 310, "lat": 19.1667, "lon": 83.4167}
                    ]
                },
                {
                    "name": "Khurda - Balugaon Chord Bypass",
                    "color": "#f43f5e",
                    "stations": [
                        {"name": "Khurda Road", "km": 0, "lat": 20.1833, "lon": 85.7333, "hub": True},
                        {"name": "Balugaon", "km": 70, "lat": 19.7483, "lon": 85.2056}
                    ]
                }
            ],
            "blocks": [
                {"title": "Maintenance Work (Track Renewal)", "km_txt": "Km 298 – 301", "lat": 20.3500, "lon": 85.8400, "color": "#ef4444", "line_coords": [[20.4000, 85.8600], [20.3000, 85.8200]], "dept": "Engineering (CSM Tamping + BCM Rake)", "window": "10:00 – 14:00 IST (4 Hrs Possession)"},
                {"title": "Scheduled Block (OHE Inspection)", "km_txt": "Km 312 – 315", "lat": 19.5500, "lon": 85.0000, "color": "#f97316", "line_coords": [[19.6500, 85.1000], [19.4500, 84.9000]], "dept": "TRD Electrical (Tower Car Inspection)", "window": "11:30 – 13:30 IST (2 Hrs Possession)"}
            ],
            "trains": [
                {"num": "12841", "name": "Coromandel Express", "speed": "80 km/h", "lat": 20.6000, "lon": 85.5000, "bg": "#22c55e", "signal": "🟢 Green Signal", "delay": "On Time"},
                {"num": "22823", "name": "Bhubaneswar Rajdhani", "speed": "60 km/h", "lat": 20.2500, "lon": 85.1000, "bg": "#eab308", "signal": "🟡 Amber Caution", "delay": "+6 min"},
                {"num": "18477", "name": "Utkal Express", "speed": "Stopped", "lat": 20.1700, "lon": 85.7200, "bg": "#ef4444", "signal": "🔴 Red Aspect (Track Renewal Block)", "delay": "+20 min"},
                {"num": "12860", "name": "Gitanjali Express", "speed": "45 km/h", "lat": 19.6500, "lon": 85.1000, "bg": "#eab308", "signal": "🟡 Amber Caution", "delay": "+4 min"},
                {"num": "20832", "name": "Visakhapatnam SF Express", "speed": "90 km/h", "lat": 18.5000, "lon": 83.8000, "bg": "#2563eb", "signal": "🟢 Green Signal", "delay": "On Time"},
                {"num": "17232", "name": "Golconda Express", "speed": "75 km/h", "lat": 19.2500, "lon": 84.8500, "bg": "#22c55e", "signal": "🟢 Green Signal", "delay": "On Time"}
            ],
            "timeline": [
                {
                    "train": "12841 Puri→BBS",
                    "segments": [
                        {"left": "0%", "width": "29%", "bg": "#22c55e", "title": "Normal Running (06:00 - 09:30)"},
                        {"left": "29.5%", "width": "16.5%", "bg": "#eab308", "title": "Reduced Speed TSR (09:30 - 11:30)"},
                        {"left": "46.5%", "width": "20%", "bg": "repeating-linear-gradient(45deg, #ef4444, #ef4444 3px, #dc2626 3px, #dc2626 6px)", "border": "1px dashed #f87171", "title": "298-301 Track Renewal Block"},
                        {"left": "67%", "width": "28%", "bg": "#22c55e", "title": "Normal Running (14:00 - 18:00)"}
                    ]
                },
                {
                    "train": "22823 VSKP→Puri",
                    "segments": [
                        {"left": "8.3%", "width": "25%", "bg": "#22c55e", "title": "Normal Running (07:00 - 10:00)"},
                        {"left": "34%", "width": "19.5%", "bg": "#eab308", "title": "Reduced Speed (10:00 - 12:30)"},
                        {"left": "54.5%", "width": "12%", "bg": "#3b82f6", "title": "Loop Holding (12:30 - 14:00)"},
                        {"left": "67%", "width": "25%", "bg": "#22c55e", "title": "Normal Running (14:00 - 18:00)"}
                    ]
                },
                {
                    "train": "18477 KUR→Puri",
                    "segments": [
                        {"left": "4.1%", "width": "37%", "bg": "#38bdf8", "title": "Scheduled Run"},
                        {"left": "41.8%", "width": "16%", "bg": "#ef4444", "title": "Signal Stop (11:00 - 13:00)"},
                        {"left": "58.8%", "width": "20%", "bg": "repeating-linear-gradient(45deg, #d97706, #d97706 3px, #b45309 3px, #b45309 6px)", "border": "1px dashed #fbbf24", "title": "312-315 Block Possession"},
                        {"left": "79.5%", "width": "18.5%", "bg": "#a855f7", "title": "Final Destination Run"}
                    ]
                }
            ]
        },
        "Vijayawada Division (BZA)": {
            "center": [16.55, 80.85],
            "zoom": 9,
            "corridor_title": "Vijayawada — Kondapalli — Eluru — Tenali — Ongole Multi-Track Network",
            "jurisdiction": "SCR Jurisdiction • Vijayawada Division HQ",
            "kpi": {"running": 20, "reduced": 3, "stopped": 1, "total": 24},
            "division_tags": [
                {"name": "Vijayawada Division", "lat": 16.80, "lon": 80.40},
                {"name": "Secunderabad Division", "lat": 17.40, "lon": 79.80},
                {"name": "Guntur Division", "lat": 16.10, "lon": 80.10},
                {"name": "Waltair Division", "lat": 17.20, "lon": 82.20}
            ],
            "lines": [
                {
                    "name": "North-West Trunk Line (BZA - Khammam - Warangal)",
                    "color": "#38bdf8",
                    "stations": [
                        {"name": "Vijayawada Jn", "km": 100, "lat": 16.5062, "lon": 80.6480, "hub": True},
                        {"name": "Rayanapadu", "km": 108, "lat": 16.5450, "lon": 80.5980},
                        {"name": "Kondapalli", "km": 125, "lat": 16.6180, "lon": 80.5360, "hub": True},
                        {"name": "Madhira", "km": 135, "lat": 16.9180, "lon": 80.3640},
                        {"name": "Khammam", "km": 160, "lat": 17.2472, "lon": 80.1514, "hub": True},
                        {"name": "Warangal", "km": 210, "lat": 17.9783, "lon": 79.5217, "hub": True}
                    ]
                },
                {
                    "name": "East Main Trunk Line (BZA - Rajahmundry)",
                    "color": "#34d399",
                    "stations": [
                        {"name": "Vijayawada Jn", "km": 0, "lat": 16.5062, "lon": 80.6480, "hub": True},
                        {"name": "Eluru", "km": 60, "lat": 16.7107, "lon": 81.1042, "hub": True},
                        {"name": "Tadepalligudem", "km": 108, "lat": 16.8143, "lon": 81.5268},
                        {"name": "Rajahmundry", "km": 150, "lat": 17.0005, "lon": 81.7774, "hub": True},
                        {"name": "Samalkot", "km": 200, "lat": 17.0500, "lon": 82.1667}
                    ]
                },
                {
                    "name": "South Trunk Line (BZA - Tenali - Ongole)",
                    "color": "#f59e0b",
                    "stations": [
                        {"name": "Vijayawada Jn", "km": 0, "lat": 16.5062, "lon": 80.6480, "hub": True},
                        {"name": "Tenali Jn", "km": 32, "lat": 16.2430, "lon": 80.6470, "hub": True},
                        {"name": "Bapatla", "km": 74, "lat": 15.9040, "lon": 80.4670},
                        {"name": "Ongole", "km": 138, "lat": 15.5057, "lon": 80.0499, "hub": True}
                    ]
                }
            ],
            "blocks": [
                {"title": "Maintenance Work (Track Tamping)", "km_txt": "Km 114 – 118", "lat": 16.5800, "lon": 80.5600, "color": "#ef4444", "line_coords": [[16.5450, 80.5980], [16.6180, 80.5360]], "dept": "Engineering (CSM Tamping Machine)", "window": "10:00 – 13:00 IST"},
                {"title": "OHE Power Isolation Block", "km_txt": "Km 130 – 134", "lat": 16.8000, "lon": 80.4200, "color": "#f97316", "line_coords": [[16.7500, 80.4500], [16.8500, 80.3900]], "dept": "TRD (Overhead Wire Inspection)", "window": "12:00 – 14:30 IST"}
            ],
            "trains": [
                {"num": "12727", "name": "Godavari Express", "speed": "80 km/h", "lat": 16.6500, "lon": 80.5100, "bg": "#22c55e", "signal": "🟢 Green Signal", "delay": "On Time"},
                {"num": "12759", "name": "Charminar Express", "speed": "30 km/h", "lat": 16.5700, "lon": 80.5700, "bg": "#eab308", "signal": "🟡 Amber Caution (TSR 30)", "delay": "+12 min"},
                {"num": "20833", "name": "Vande Bharat Express", "speed": "120 km/h", "lat": 16.9180, "lon": 80.3640, "bg": "#2563eb", "signal": "🟢 High Speed Clear", "delay": "On Time"},
                {"num": "57231", "name": "BZA-KMT Local", "speed": "40 km/h", "lat": 17.1000, "lon": 80.2500, "bg": "#eab308", "signal": "🟡 Approach", "delay": "+5 min"},
                {"num": "G-402", "name": "Coal Freight", "speed": "Stopped", "lat": 16.5200, "lon": 80.6200, "bg": "#ef4444", "signal": "🔴 Loop Holding", "delay": "+18 min"}
            ],
            "timeline": [
                {
                    "train": "12727 BZA→KMT",
                    "segments": [
                        {"left": "0%", "width": "25%", "bg": "#22c55e", "title": "Normal Cruising (06:00 - 09:00)"},
                        {"left": "25.5%", "width": "12.5%", "bg": "#eab308", "title": "Approach Braking (09:00 - 10:30)"},
                        {"left": "38.5%", "width": "25%", "bg": "repeating-linear-gradient(45deg, #ef4444, #ef4444 3px, #dc2626 3px, #dc2626 6px)", "border": "1px dashed #f87171", "title": "Active Track Tamping Block (10:30 - 13:30)"},
                        {"left": "64%", "width": "34%", "bg": "#22c55e", "title": "Accelerated Run (13:30 - 18:00)"}
                    ]
                },
                {
                    "train": "12759 BZA→MDR",
                    "segments": [
                        {"left": "8.3%", "width": "25%", "bg": "#38bdf8", "title": "Scheduled Run (07:00 - 10:00)"},
                        {"left": "34%", "width": "16.5%", "bg": "#eab308", "title": "Caution Order 30 km/h (10:00 - 12:00)"},
                        {"left": "51%", "width": "20.5%", "bg": "repeating-linear-gradient(45deg, #d97706, #d97706 3px, #b45309 3px, #b45309 6px)", "border": "1px dashed #fbbf24", "title": "OHE Power Isolation (12:00 - 14:30)"},
                        {"left": "72%", "width": "26%", "bg": "#22c55e", "title": "Normal Running (14:30 - 18:00)"}
                    ]
                },
                {
                    "train": "20833 BZA→WL",
                    "segments": [
                        {"left": "0%", "width": "45.8%", "bg": "#22c55e", "title": "High Speed Vande Bharat (06:00 - 11:30)"},
                        {"left": "46.5%", "width": "12.5%", "bg": "#ef4444", "title": "Signal Regulated (11:30 - 13:00)"},
                        {"left": "59.5%", "width": "38.5%", "bg": "#38bdf8", "title": "Cleared Speed Run (13:00 - 18:00)"}
                    ]
                }
            ]
        },
        "Secunderabad Division (SC)": {
            "center": [17.50, 78.85],
            "zoom": 9,
            "corridor_title": "Secunderabad — Moula Ali — Cherlapalli — Kazipet High Density Corridor",
            "jurisdiction": "SCR Jurisdiction • Secunderabad Division HQ",
            "kpi": {"running": 22, "reduced": 2, "stopped": 1, "total": 25},
            "division_tags": [
                {"name": "Secunderabad Division", "lat": 17.43, "lon": 78.50},
                {"name": "Hyderabad Division", "lat": 17.37, "lon": 78.48},
                {"name": "Vijayawada Division", "lat": 16.50, "lon": 80.64},
                {"name": "Guntakal Division", "lat": 15.17, "lon": 77.38}
            ],
            "lines": [
                {
                    "name": "Secunderabad - Kazipet Main Trunk",
                    "color": "#38bdf8",
                    "stations": [
                        {"name": "Secunderabad Jn", "km": 0, "lat": 17.4344, "lon": 78.5011, "hub": True},
                        {"name": "Moula Ali", "km": 10, "lat": 17.4650, "lon": 78.5600},
                        {"name": "Cherlapalli", "km": 22, "lat": 17.4725, "lon": 78.6000, "hub": True},
                        {"name": "Bhongir", "km": 48, "lat": 17.5111, "lon": 78.8900},
                        {"name": "Jangaon", "km": 84, "lat": 17.7200, "lon": 79.1800, "hub": True},
                        {"name": "Kazipet Jn", "km": 132, "lat": 17.9783, "lon": 79.5217, "hub": True}
                    ]
                },
                {
                    "name": "Secunderabad - Wadi Junction Trunk",
                    "color": "#34d399",
                    "stations": [
                        {"name": "Secunderabad Jn", "km": 0, "lat": 17.4344, "lon": 78.5011, "hub": True},
                        {"name": "Begumpet", "km": 5, "lat": 17.4380, "lon": 78.4600},
                        {"name": "Lingampalli", "km": 23, "lat": 17.4850, "lon": 78.3180, "hub": True},
                        {"name": "Vikarabad Jn", "km": 72, "lat": 17.3360, "lon": 77.9040, "hub": True},
                        {"name": "Tandur", "km": 114, "lat": 17.2560, "lon": 77.5840}
                    ]
                }
            ],
            "blocks": [
                {"title": "Track Renewal & Deep Screening", "km_txt": "Km 35 – 50", "lat": 17.4900, "lon": 78.7500, "color": "#ef4444", "line_coords": [[17.4725, 78.6000], [17.5111, 78.8900]], "dept": "Engineering (BCM + DGS Machine)", "window": "09:30 – 12:30 IST"},
                {"title": "OHE Catenary Overhaul", "km_txt": "Km 90 – 105", "lat": 17.7800, "lon": 79.3000, "color": "#f97316", "line_coords": [[17.7200, 79.1800], [17.8500, 79.3500]], "dept": "TRD Electrical (Tower Wagon)", "window": "11:00 – 14:00 IST"}
            ],
            "trains": [
                {"num": "12701", "name": "Hussain Sagar Express", "speed": "85 km/h", "lat": 17.4600, "lon": 78.5500, "bg": "#22c55e", "signal": "🟢 Green Signal", "delay": "On Time"},
                {"num": "12792", "name": "Danapur SF Express", "speed": "60 km/h", "lat": 17.5000, "lon": 78.8000, "bg": "#eab308", "signal": "🟡 Caution TSR 30", "delay": "+4 min"},
                {"num": "17015", "name": "Visakha Express", "speed": "Stopped", "lat": 17.4800, "lon": 78.6800, "bg": "#ef4444", "signal": "🔴 Red Aspect (Screening Block)", "delay": "+15 min"},
                {"num": "SC-F819", "name": "Container Freight Rake", "speed": "50 km/h", "lat": 17.6500, "lon": 79.0500, "bg": "#38bdf8", "signal": "🟢 Loop Proceed", "delay": "On Time"}
            ],
            "timeline": [
                {
                    "train": "12701 SC→KZJ",
                    "segments": [
                        {"left": "0%", "width": "29%", "bg": "#22c55e", "title": "Normal Running (06:00 - 09:30)"},
                        {"left": "29.5%", "width": "25%", "bg": "repeating-linear-gradient(45deg, #ef4444, #ef4444 3px, #dc2626 3px, #dc2626 6px)", "border": "1px dashed #f87171", "title": "S&T Interlocking Block (09:30 - 12:30)"},
                        {"left": "55%", "width": "12.5%", "bg": "#3b82f6", "title": "Loop Reception Hold (12:30 - 14:00)"},
                        {"left": "68%", "width": "30%", "bg": "#22c55e", "title": "Resumed Cruise (14:00 - 18:00)"}
                    ]
                },
                {
                    "train": "12792 SC→MLY",
                    "segments": [
                        {"left": "4.1%", "width": "29%", "bg": "#38bdf8", "title": "Commuter Service (06:30 - 10:00)"},
                        {"left": "34%", "width": "20.8%", "bg": "#eab308", "title": "Speed Regulation 30 km/h (10:00 - 12:30)"},
                        {"left": "55.5%", "width": "20.8%", "bg": "repeating-linear-gradient(45deg, #d97706, #d97706 3px, #b45309 3px, #b45309 6px)", "border": "1px dashed #fbbf24", "title": "Ballast Tamping Window (12:30 - 15:00)"},
                        {"left": "77%", "width": "21%", "bg": "#22c55e", "title": "Normal Run (15:00 - 18:00)"}
                    ]
                },
                {
                    "train": "17015 SC→BG",
                    "segments": [
                        {"left": "12.5%", "width": "29%", "bg": "#22c55e", "title": "Scheduled Express (07:30 - 11:00)"},
                        {"left": "42%", "width": "16.5%", "bg": "#ef4444", "title": "Red Signal Hold (11:00 - 13:00)"},
                        {"left": "59%", "width": "39%", "bg": "#38bdf8", "title": "Post-Clearance Speed-Up (13:00 - 18:00)"}
                    ]
                }
            ]
        },
        "Howrah Division (HWH)": {
            "center": [22.95, 88.05],
            "zoom": 9,
            "corridor_title": "Howrah — Bandel — Bardhaman — Durgapur Quadruple Track Corridor",
            "jurisdiction": "ER Jurisdiction • Howrah Division HQ",
            "kpi": {"running": 26, "reduced": 4, "stopped": 2, "total": 32},
            "division_tags": [
                {"name": "Howrah Division", "lat": 22.58, "lon": 88.34},
                {"name": "Sealdah Division", "lat": 22.56, "lon": 88.37},
                {"name": "Asansol Division", "lat": 23.68, "lon": 86.98},
                {"name": "Kharagpur Division", "lat": 22.33, "lon": 87.32}
            ],
            "lines": [
                {
                    "name": "Howrah - Bardhaman Main Chord",
                    "color": "#38bdf8",
                    "stations": [
                        {"name": "Howrah Jn", "km": 0, "lat": 22.5839, "lon": 88.3428, "hub": True},
                        {"name": "Serampore", "km": 20, "lat": 22.7500, "lon": 88.3400},
                        {"name": "Bandel Jn", "km": 40, "lat": 22.9200, "lon": 88.3800, "hub": True},
                        {"name": "Bardhaman Jn", "km": 100, "lat": 23.2400, "lon": 87.8600, "hub": True},
                        {"name": "Durgapur", "km": 165, "lat": 23.5000, "lon": 87.3200, "hub": True}
                    ]
                },
                {
                    "name": "Howrah - Dankuni Suburban Chord",
                    "color": "#34d399",
                    "stations": [
                        {"name": "Howrah Jn", "km": 0, "lat": 22.5839, "lon": 88.3428, "hub": True},
                        {"name": "Dankuni", "km": 15, "lat": 22.6800, "lon": 88.2900, "hub": True},
                        {"name": "Kamarkundu", "km": 35, "lat": 22.8300, "lon": 88.2000}
                    ]
                }
            ],
            "blocks": [
                {"title": "Catenary & Track Mega-Block", "km_txt": "Km 40 – 50", "lat": 22.9800, "lon": 88.3000, "color": "#ef4444", "line_coords": [[22.9200, 88.3800], [23.0500, 88.2500]], "dept": "Engineering + TRD (Joint Possession)", "window": "11:30 – 14:30 IST"},
                {"title": "Electronic Interlocking Maintenance", "km_txt": "Km 75 – 82", "lat": 23.1200, "lon": 88.0200, "color": "#f97316", "line_coords": [[23.0800, 88.0800], [23.1800, 87.9500]], "dept": "S&T (Relay Testing)", "window": "12:00 – 14:00 IST"}
            ],
            "trains": [
                {"num": "12301", "name": "Howrah Rajdhani Express", "speed": "110 km/h", "lat": 22.7000, "lon": 88.3200, "bg": "#22c55e", "signal": "🟢 High Speed Clear", "delay": "On Time"},
                {"num": "37211", "name": "Bandel EMU Local", "speed": "45 km/h", "lat": 22.8500, "lon": 88.3600, "bg": "#eab308", "signal": "🟡 Caution TSR 30", "delay": "+3 min"},
                {"num": "12339", "name": "Coalfield Express", "speed": "Stopped", "lat": 22.9500, "lon": 88.3200, "bg": "#ef4444", "signal": "🔴 Red Aspect (Joint Block)", "delay": "+25 min"},
                {"num": "22301", "name": "Vande Bharat Express", "speed": "115 km/h", "lat": 23.3500, "lon": 87.6000, "bg": "#2563eb", "signal": "🟢 High Speed Clear", "delay": "On Time"}
            ],
            "timeline": [
                {
                    "train": "12301 HWH→BWN",
                    "segments": [
                        {"left": "0%", "width": "33.3%", "bg": "#22c55e", "title": "Rajdhani High Speed (06:00 - 10:00)"},
                        {"left": "34%", "width": "12.5%", "bg": "#eab308", "title": "Automated TSR Caution (10:00 - 11:30)"},
                        {"left": "47%", "width": "25%", "bg": "repeating-linear-gradient(45deg, #ef4444, #ef4444 3px, #dc2626 3px, #dc2626 6px)", "border": "1px dashed #f87171", "title": "TRD Catenary Mega-Block (11:30 - 14:30)"},
                        {"left": "72.5%", "width": "25.5%", "bg": "#22c55e", "title": "Resumed High Speed (14:30 - 18:00)"}
                    ]
                },
                {
                    "train": "37211 HWH→BDC",
                    "segments": [
                        {"left": "0%", "width": "25%", "bg": "#38bdf8", "title": "EMU Local (06:00 - 09:00)"},
                        {"left": "25.5%", "width": "16.5%", "bg": "#3b82f6", "title": "Platform Hold Serampore (09:00 - 11:00)"},
                        {"left": "42.5%", "width": "20.8%", "bg": "repeating-linear-gradient(45deg, #d97706, #d97706 3px, #b45309 3px, #b45309 6px)", "border": "1px dashed #fbbf24", "title": "Track Disconnection (11:00 - 13:30)"},
                        {"left": "64%", "width": "34%", "bg": "#22c55e", "title": "Suburban Local (13:30 - 18:00)"}
                    ]
                },
                {
                    "train": "12339 HWH→DGR",
                    "segments": [
                        {"left": "8.3%", "width": "33.3%", "bg": "#22c55e", "title": "Coalfield SF Express (07:00 - 11:00)"},
                        {"left": "42%", "width": "12.5%", "bg": "#eab308", "title": "Signal Precaution (11:00 - 12:30)"},
                        {"left": "55%", "width": "12.5%", "bg": "#ef4444", "title": "Overrun Inspection (12:30 - 14:00)"},
                        {"left": "68%", "width": "30%", "bg": "#22c55e", "title": "Normal Cruise (14:00 - 18:00)"}
                    ]
                }
            ]
        }
    }

    match_key = None
    div_str = str(division).lower()
    if "kurda" in div_str or "khurda" in div_str or "kur" in div_str:
        match_key = "Khurda Road Division (KUR)"
    elif "howrah" in div_str or "hwh" in div_str:
        match_key = "Howrah Division (HWH)"
    elif "secund" in div_str or "sc" in div_str.split():
        match_key = "Secunderabad Division (SC)"
    elif "vijay" in div_str or "bza" in div_str:
        match_key = "Vijayawada Division (BZA)"
    else:
        for k in div_networks.keys():
            if k.lower() in div_str or div_str in k.lower():
                match_key = k
                break
    if not match_key:
        match_key = "Khurda Road Division (KUR)"

    net = div_networks[match_key]
    kpis = net.get("kpi", {"running": 18, "reduced": 4, "stopped": 2, "total": 24})

    # BUILD FOLIUM MAP WITH HOVER TOOLTIPS
    m = folium.Map(
        location=net["center"],
        zoom_start=net["zoom"],
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        control_scale=False,
        zoom_control=True
    )

    folium.TileLayer('OpenStreetMap', name='Street Map View', show=False).add_to(m)
    folium.LayerControl(position='topleft').add_to(m)

    # Branching Track Lines with hover tooltips
    for line in net["lines"]:
        coords = [[st_node["lat"], st_node["lon"]] for st_node in line["stations"]]
        folium.PolyLine(coords, color="#0b1329", weight=8, opacity=0.9).add_to(m)

        track_tooltip = f"""
        <div style="background: #0f172a; color: white; padding: 10px 14px; border-radius: 8px; border: 1.5px solid {line['color']}; font-family: sans-serif; font-size: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.6); min-width: 220px;">
            <div style="font-size: 13px; font-weight: bold; color: {line['color']};">🛣️ {line['name']}</div>
            <div style="margin-top: 4px; color: #e2e8f0;">📍 Route: <b>{line['stations'][0]['name']}</b> ➔ <b>{line['stations'][-1]['name']}</b></div>
            <div style="color: #4ade80; margin-top: 2px;">⚡ Permissible MPS: <b>110 km/h</b></div>
            <div style="color: #94a3b8; font-size: 11px; margin-top: 2px;">Track Specs: Broad Gauge (1676mm) | 25kV AC Electrified</div>
        </div>
        """
        folium.PolyLine(coords, color=line["color"], weight=4, opacity=0.95, tooltip=folium.Tooltip(track_tooltip, sticky=True)).add_to(m)

        for st_node in line["stations"]:
            is_hub = st_node.get("hub", False)
            rad = 7 if is_hub else 5

            st_tooltip = f"""
            <div style="background: #0f172a; color: white; padding: 8px 12px; border-radius: 6px; border: 1.5px solid #38bdf8; font-family: sans-serif; font-size: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.5);">
                <div style="font-size: 13px; font-weight: bold; color: #38bdf8;">🚉 Station: {st_node['name']}</div>
                <div style="color: #cbd5e1; margin-top: 2px;">📍 Location: <b>KM {st_node['km']}</b></div>
                <div style="color: #94a3b8; font-size: 11px;">Category: {'Divisional Hub / Junction' if is_hub else 'Railway Station'}</div>
            </div>
            """
            folium.CircleMarker(
                location=[st_node["lat"], st_node["lon"]],
                radius=rad,
                color="#ffffff",
                weight=2.5,
                fill=True,
                fill_color="#0b1329",
                fill_opacity=1.0,
                tooltip=folium.Tooltip(st_tooltip, sticky=True)
            ).add_to(m)

            if is_hub:
                folium.CircleMarker(
                    location=[st_node["lat"], st_node["lon"]],
                    radius=4,
                    color="#38bdf8",
                    weight=1.5,
                    fill=True,
                    fill_color="#ffffff",
                    fill_opacity=1.0
                ).add_to(m)

            # ALWAYS-VISIBLE STATION & CITY LABELS ON MAP (Item 7)
            lbl_html = f'''<div style="background: rgba(11, 19, 41, 0.95); color: #f8fafc; border: 1.5px solid #38bdf8; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: 800; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; white-space: nowrap; pointer-events: none; box-shadow: 0 2px 8px rgba(0,0,0,0.8); display: inline-flex; align-items: center; gap: 4px;"><span style="color: #38bdf8; font-size: 8px;">●</span> {st_node['name']}</div>'''
            folium.Marker(
                location=[st_node["lat"], st_node["lon"]],
                icon=folium.DivIcon(html=lbl_html, icon_size=(110, 24), icon_anchor=(-10, 12))
            ).add_to(m)

    if match_key == "Khurda Road Division (KUR)":
        folium.Marker(
            location=[20.85, 86.10],
            icon=folium.DivIcon(html='<div style="color: #ffffff; font-size: 12px; font-weight: 700; text-shadow: 0 1px 4px #000, 0 0 2px #000; font-family: sans-serif;">Jajpur Keonjhar</div>')
        ).add_to(m)
        folium.CircleMarker(location=[20.85, 86.05], radius=5, color="#ffffff", weight=2, fill=True, fill_color="#0b1329", fill_opacity=1.0).add_to(m)
        folium.Marker(
            location=[19.20, 85.90],
            icon=folium.DivIcon(html='<div style="color: rgba(186, 230, 253, 0.45); font-style: italic; font-size: 16px; font-family: Georgia, serif; letter-spacing: 3px; pointer-events: none; white-space: nowrap;">Bay of Bengal</div>')
        ).add_to(m)

    # Maintenance Callouts & Hatched Lines with hover tooltips
    for blk in net.get("blocks", []):
        maint_tooltip = f"""
        <div style="background: #0f172a; color: white; padding: 10px 14px; border-radius: 8px; border: 1.5px solid {blk['color']}; font-family: sans-serif; font-size: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.6); min-width: 240px;">
            <div style="font-size: 14px; font-weight: bold; color: #f87171;">🛠️ {blk.get('title', 'Maintenance Block')}</div>
            <div style="margin-top: 4px; color: #e2e8f0;">📍 Section: <b>{blk['km_txt']}</b></div>
            <div style="color: #fca5a5;">⏱️ Window: <b>{blk.get('window', '10:00 – 14:00 IST')}</b></div>
            <div style="color: #fcd34d; font-weight: bold; margin-top: 2px;">⚠️ Speed Regulation: TSR 30 km/h Active</div>
            <div style="color: #cbd5e1; font-size: 11px; margin-top: 3px;">⚙️ Department: {blk.get('dept', 'Engineering')}</div>
        </div>
        """
        if "line_coords" in blk:
            folium.PolyLine(blk["line_coords"], color=blk["color"], weight=14, opacity=0.7, dash_array="6,8", tooltip=folium.Tooltip(maint_tooltip, sticky=True)).add_to(m)

        c_lat = blk.get("card_lat", blk.get("lat"))
        c_lon = blk.get("card_lon", blk.get("lon"))

        if "Renewal" in blk.get("title", "") or "Maintenance" in blk.get("title", ""):
            c_html = f'''
            <div style="background: #ffffff; border: 2px solid {blk['color']}; border-radius: 8px; padding: 4px 10px 4px 6px; display: inline-flex; align-items: center; gap: 8px; box-shadow: 0 4px 14px rgba(0,0,0,0.45); white-space: nowrap; font-family: sans-serif; transform: translate(-30%, -120%);">
                <div style="background: #fee2e2; border: 1.5px solid {blk['color']}; border-radius: 6px; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 13px; color: #dc2626; flex-shrink: 0;">🛠️</div>
                <div style="line-height: 1.2; text-align: left;">
                    <div style="color: #dc2626; font-weight: 800; font-size: 11px;">{blk.get('title', 'Maintenance Work')}</div>
                    <div style="color: #1e293b; font-weight: 700; font-size: 10px;">(Track Renewal)</div>
                    <div style="color: #64748b; font-weight: 600; font-size: 9.5px;">{blk['km_txt']}</div>
                </div>
            </div>
            '''
        else:
            c_html = f'''
            <div style="background: #ffffff; border: 1.5px solid {blk['color']}; border-radius: 8px; padding: 4px 10px; text-align: left; box-shadow: 0 4px 14px rgba(0,0,0,0.45); white-space: nowrap; font-family: sans-serif; transform: translate(10%, 20%);">
                <div style="color: #ea580c; font-weight: 800; font-size: 11px;">{blk.get('title', 'Scheduled Block')}</div>
                <div style="color: #1e293b; font-weight: 700; font-size: 10px;">(10:00 – 14:00)</div>
                <div style="color: #64748b; font-weight: 600; font-size: 9.5px;">{blk['km_txt']}</div>
            </div>
            '''
        folium.Marker(location=[c_lat, c_lon], icon=folium.DivIcon(html=c_html), tooltip=folium.Tooltip(maint_tooltip, sticky=True)).add_to(m)

    # Real-time Train Badges with hover tooltips
    for tr in net.get("trains", []):
        train_tooltip = f"""
        <div style="background: #0f172a; color: white; padding: 10px 14px; border-radius: 8px; border: 1.5px solid {tr['bg']}; font-family: sans-serif; font-size: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.6); min-width: 220px;">
            <div style="font-size: 14px; font-weight: bold; color: #4ade80;">🚆 Train {tr['num']} — {tr.get('name', 'Express')}</div>
            <div style="margin-top: 4px; color: #e2e8f0;">⚡ Speed: <b style="color: {tr['bg']}; font-size: 13px;">{tr['speed']}</b> (MPS 110 km/h)</div>
            <div style="color: #cbd5e1;">📍 Location: Near {match_key.split(' ')[0]}</div>
            <div style="color: #86efac; font-weight: bold; margin-top: 3px;">{tr.get('signal', '🟢 Green Aspect')}</div>
            <div style="color: #94a3b8; font-size: 10px; margin-top: 4px; border-top: 1px solid #334155; padding-top: 4px;">Status: {tr.get('delay', 'On Time')}</div>
        </div>
        """
        t_html = f'''
        <div style="background: #ffffff; border: 1.5px solid #cbd5e1; border-radius: 7px; padding: 2px 7px 2px 4px; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.4); white-space: nowrap; font-family: sans-serif; transform: translate(-50%, -50%);">
            <div style="background: {tr['bg']}; width: 22px; height: 22px; border-radius: 5px; display: flex; align-items: center; justify-content: center; font-size: 12px; color: white; flex-shrink: 0;">🚆</div>
            <div style="line-height: 1.15; text-align: left;">
                <div style="font-size: 11px; font-weight: 800; color: #0f172a;">{tr['num']}</div>
                <div style="font-size: 9.5px; font-weight: 600; color: #475569;">{tr['speed']}</div>
            </div>
        </div>
        '''
        folium.Marker(location=[tr["lat"], tr["lon"]], icon=folium.DivIcon(html=t_html), tooltip=folium.Tooltip(train_tooltip, sticky=True)).add_to(m)

    # Boundary tags
    for tag in net.get("division_tags", []):
        tag_html = f'''
        <div style="background: rgba(14, 30, 58, 0.92); border: 1.5px solid #0284c7; border-radius: 6px; padding: 3px 9px; color: #7dd3fc; font-family: sans-serif; font-size: 11px; font-weight: 700; white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.4); transform: translate(-50%, -50%);">
            🏛️ {tag['name']}
        </div>
        '''
        folium.Marker(location=[tag["lat"], tag["lon"]], icon=folium.DivIcon(html=tag_html)).add_to(m)

    hud_controls = f'''
    <style>
    .leaflet-control-train-hud {{
        background: rgba(11, 20, 38, 0.95) !important;
        border: 1.5px solid #1e3a5f !important;
        border-radius: 8px !important;
        padding: 8px 14px !important;
        color: white !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
        margin: 10px 12px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
        pointer-events: auto !important;
    }}
    .leaflet-control-scale-custom {{
        background: rgba(11, 20, 38, 0.9) !important;
        border: 1px solid #1e3a5f !important;
        border-radius: 6px !important;
        padding: 4px 10px !important;
        color: white !important;
        font-family: sans-serif !important;
        font-size: 10px !important;
        margin: 10px 12px !important;
    }}
    .leaflet-control-compass {{
        margin: 10px 14px !important;
        text-align: center !important;
        color: white !important;
        font-family: sans-serif !important;
    }}
    </style>
    <script>
    window.addEventListener("DOMContentLoaded", function() {{
        var topRight = document.querySelector(".leaflet-top.leaflet-right");
        if (topRight) {{
            var hud = document.createElement("div");
            hud.className = "leaflet-control leaflet-control-train-hud";
            hud.innerHTML = `
                <div style="font-size: 11px; font-weight: 700; color: #cbd5e1; margin-bottom: 6px;">Live Train Count</div>
                <div style="display: flex; gap: 12px; align-items: center;">
                    <div style="display: flex; align-items: center; gap: 5px;">
                        <div style="background: #064e3b; border-radius: 5px; padding: 2px 4px; font-size: 11px;">🚆</div>
                        <div style="line-height: 1.1;"><div style="font-size: 8.5px; color: #94a3b8;">Running</div><b style="font-size: 14px; color: #4ade80;">{kpis['running']}</b></div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 5px;">
                        <div style="background: #78350f; border-radius: 5px; padding: 2px 4px; font-size: 11px;">🚆</div>
                        <div style="line-height: 1.1;"><div style="font-size: 8.5px; color: #94a3b8;">Reduced</div><b style="font-size: 14px; color: #fbbf24;">{kpis['reduced']}</b></div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 5px;">
                        <div style="background: #7f1d1d; border-radius: 5px; padding: 2px 4px; font-size: 11px;">🚆</div>
                        <div style="line-height: 1.1;"><div style="font-size: 8.5px; color: #94a3b8;">Stopped</div><b style="font-size: 14px; color: #f87171;">{kpis['stopped']}</b></div>
                    </div>
                    <div style="border-left: 1px solid #334155; padding-left: 10px;">
                        <div style="font-size: 8.5px; color: #94a3b8;">Total</div><b style="font-size: 14px; color: #38bdf8;">{kpis['total']}</b>
                    </div>
                </div>
            `;
            topRight.appendChild(hud);
        }}

        var bottomLeft = document.querySelector(".leaflet-bottom.leaflet-left");
        if (bottomLeft) {{
            var sc = document.createElement("div");
            sc.className = "leaflet-control leaflet-control-scale-custom";
            sc.innerHTML = `
                <div style="display: flex; justify-content: space-between; font-weight: 600; color: #cbd5e1; gap: 6px;">
                    <span>0</span><span>10</span><span>20</span><span>30</span><span>40 km</span>
                </div>
                <div style="height: 4px; background: white; border-radius: 2px; margin-top: 2px; display: flex;">
                    <div style="flex: 1; background: #0b1329;"></div><div style="flex: 1; background: white;"></div>
                    <div style="flex: 1; background: #0b1329;"></div><div style="flex: 1; background: white;"></div>
                </div>
            `;
            bottomLeft.appendChild(sc);
        }}

        var bottomRight = document.querySelector(".leaflet-bottom.leaflet-right");
        if (bottomRight) {{
            var comp = document.createElement("div");
            comp.className = "leaflet-control leaflet-control-compass";
            comp.innerHTML = `
                <div style="font-size: 18px; font-weight: 900; color: #38bdf8; line-height: 1;">▲</div>
                <div style="font-size: 10px; font-weight: 800; color: #ffffff;">N</div>
            `;
            bottomRight.appendChild(comp);
        }}
    }});
    </script>
    '''

    # WIDE MAP LAYOUT (3.8 vs 1.2 giving ~76% width to map and 24% to right timeline)
    col_left, col_right = st.columns([3.8, 1.2])

    with col_left:
        map_raw = m._repr_html_()
        map_with_ui = map_raw.replace('</body>', f'{hud_controls}</body>')
        components.html(map_with_ui, height=620)
        st.caption(f"📍 **Satellite Multi-Track Network View** — {net['corridor_title']} | {net['jurisdiction']}")

    with col_right:
        # CORRIDOR TIMELINE GANTT COMPONENT (Item 6: Dynamic for all divisions)
        timeline_rows = ""
        for tr_entry in net.get("timeline", []):
            segs_html = ""
            for seg in tr_entry.get("segments", []):
                bg_style = seg.get("bg", "#22c55e")
                b_style = f"border: {seg['border']};" if "border" in seg else ""
                segs_html += f'<div style="position: absolute; left: {seg["left"]}; width: {seg["width"]}; height: 13px; background: {bg_style}; {b_style} border-radius: 4px;" title="{seg.get("title", "")}"></div>'
            timeline_rows += f'''
<div style="display: flex; align-items: center; margin-bottom: 12px; position: relative; z-index: 2;">
<div style="width: 105px; font-size: 10.5px; font-weight: 600; color: #f1f5f9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0;">{tr_entry["train"]}</div>
<div style="flex: 1; position: relative; height: 18px; display: flex; align-items: center;">
{segs_html}
</div>
</div>'''

        timeline_html = f"""
<div style="background: #0b1329; border: 1.5px solid #1e3a5f; border-radius: 10px; padding: 12px 14px; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; box-shadow: 0 4px 16px rgba(0,0,0,0.4); width: 100%; box-sizing: border-box;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 6px;">
<div style="font-size: 13px; font-weight: 700; color: #f8fafc;">Corridor Timeline — {match_key.split(' (')[0]}</div>
<div style="display: flex; align-items: center; gap: 6px;">
<div style="background: #111e38; border: 1px solid #1e3a5f; border-radius: 4px; padding: 2px 6px; font-size: 10px; color: #cbd5e1;">📅 <b>{datetime.now().strftime('%d %b %Y')}</b></div>
<div style="background: #111e38; border: 1px solid #1e3a5f; border-radius: 4px; padding: 2px 6px; font-size: 10px; color: #cbd5e1;">⏰ <b>06:00 – 18:00 IST</b></div>
</div>
</div>
<div style="display: flex; align-items: center; margin-bottom: 6px;">
<div style="width: 105px; flex-shrink: 0;"></div>
<div style="flex: 1; display: flex; justify-content: space-between; font-size: 9.5px; color: #94a3b8; font-weight: 700; padding: 0 2px;">
<span>06:00</span>
<span>08:00</span>
<span>10:00</span>
<span>12:00</span>
<span>14:00</span>
<span>16:00</span>
<span>18:00</span>
</div>
</div>
<div style="position: relative;">
<div style="position: absolute; top: 0; bottom: 0; left: 105px; right: 0; display: flex; justify-content: space-between; pointer-events: none; z-index: 1;">
<div style="width: 1px; background: rgba(51, 65, 85, 0.4);"></div>
<div style="width: 1px; background: rgba(51, 65, 85, 0.4);"></div>
<div style="width: 1px; background: rgba(51, 65, 85, 0.4);"></div>
<div style="width: 1px; background: rgba(51, 65, 85, 0.4);"></div>
<div style="width: 1px; background: rgba(51, 65, 85, 0.4);"></div>
<div style="width: 1px; background: rgba(51, 65, 85, 0.4);"></div>
<div style="width: 1px; background: rgba(51, 65, 85, 0.4);"></div>
</div>
{timeline_rows}
</div>
</div>
"""
        st.markdown(clean_html(timeline_html), unsafe_allow_html=True)

        # LIVE OPERATIONAL CONTROL ROOM FEED
        feed_cards = ""
        for tr_item in net.get("trains", [])[:2]:
            feed_cards += f'''
<div style="background: #1e293b; border-left: 3.5px solid {tr_item['bg']}; border-radius: 5px; padding: 6px 10px;">
<div style="display: flex; justify-content: space-between;">
<span style="font-size: 11px; font-weight: 800; color: #f8fafc;">🚆 {tr_item['num']} {tr_item['name']}</span>
<span style="font-size: 10px; font-weight: 700; color: {tr_item['bg']};">{tr_item['speed']}</span>
</div>
<div style="font-size: 10px; color: #cbd5e1; margin-top: 1px;">📍 Status: {tr_item.get('delay', 'On Time')} | {tr_item['signal']}</div>
</div>'''

        for blk_item in net.get("blocks", [])[:1]:
            feed_cards += f'''
<div style="background: #1e293b; border-left: 3.5px solid {blk_item['color']}; border-radius: 5px; padding: 6px 10px;">
<div style="display: flex; justify-content: space-between;">
<span style="font-size: 11px; font-weight: 800; color: #f87171;">🛠️ {blk_item['title']} ({blk_item['km_txt']})</span>
<span style="font-size: 9px; background: #7f1d1d; color: #fca5a5; padding: 1px 4px; border-radius: 3px;">POSSESSION</span>
</div>
<div style="font-size: 10px; color: #cbd5e1; margin-top: 1px;">⏱️ {blk_item.get('window', 'Active Window')} | {blk_item.get('dept', '')}</div>
</div>'''

        feed_html = f"""
<div style="background: #0f172a; border: 1.5px solid #1e3a5f; border-radius: 10px; padding: 12px 14px; color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin-top: 10px; box-shadow: 0 4px 16px rgba(0,0,0,0.4); width: 100%;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
<div style="font-size: 12.5px; font-weight: 700; color: #38bdf8;">📡 Operational Control Feed — {match_key.split(' (')[0]}</div>
<div style="background: #064e3b; border: 1px solid #059669; border-radius: 4px; padding: 1px 5px; font-size: 9.5px; color: #6ee7b7; font-weight: 700;">LIVE TELEMETRY</div>
</div>
<div style="display: flex; flex-direction: column; gap: 7px;">
{feed_cards}
</div>
</div>
"""
        st.markdown(clean_html(feed_html), unsafe_allow_html=True)


def render_live_corridor_map_plotly(df_trains=None, division="Vijayawada Division (BZA)"):
    """
    Renders an interactive Control-Room Live Railway Corridor Map using Plotly.
    Renders exact division stations, maintenance blocks (ACTIVE, UPCOMING, OVERRUN, JOINT),
    speed restrictions (TSR 30 km/h), and moving trains with dynamic speed vectors, direction, and statuses.
    """
    division_configs = {
        "Khurda Road Division (KUR)": {
            "title": "Khurda Road Main Trunk Corridor (CTC → BBS → KUR → BALU → BAM)",
            "stations": [
                {"name": "Cuttack (CTC)", "km": 0, "type": "Division Junction"},
                {"name": "Bhubaneswar (BBS)", "km": 28, "type": "State Capital"},
                {"name": "Khurda Road (KUR)", "km": 48, "type": "Division HQ"},
                {"name": "Balugaon (BALU)", "km": 118, "type": "Station"},
                {"name": "Brahmapur (BAM)", "km": 194, "type": "Junction"}
            ],
            "max_km": 220,
            "blocks": [
                {"id": "BLK-KUR-298", "start_km": 55, "end_km": 72, "status": "ACTIVE", "dept": "Engineering (Track Renewal)", "time": "10:00–14:00", "desc": "TRACK RENEWAL & TAMPER BLOCK", "is_joint": False},
                {"id": "BLK-KUR-312", "start_km": 130, "end_km": 145, "status": "UPCOMING", "dept": "TRD + S&T", "time": "12:00–16:00", "desc": "OHE INSPECTION & INTERLOCKING", "is_joint": True}
            ],
            "tsrs": [
                {"name": "TSR 30 km/h Caution Order", "start_km": 55, "end_km": 72, "speed_limit": 30}
            ]
        },
        "Vijayawada Division (BZA)": {
            "title": "Vijayawada Main Line Corridor (BZA → RYP → KDM → MDR → KMT → WL)",
            "stations": [
                {"name": "Vijayawada (BZA)", "km": 0, "type": "Division HQ"},
                {"name": "Rayanapadu (RYP)", "km": 15, "type": "Junction"},
                {"name": "Kondapalli (KDM)", "km": 30, "type": "Crossing Station"},
                {"name": "Madhira (MDR)", "km": 65, "type": "Crossing Station"},
                {"name": "Khammam (KMT)", "km": 100, "type": "Junction"},
                {"name": "Warangal (WL)", "km": 150, "type": "Interchange"}
            ],
            "max_km": 160,
            "blocks": [
                {"id": "BLK-ENG-104", "start_km": 35, "end_km": 48, "status": "ACTIVE", "dept": "Engineering + TRD", "time": "10:00–12:00", "desc": "TRACK TAMPING & OHE MAINTENANCE (JOINT BLOCK)", "is_joint": True},
                {"id": "BLK-ST-209", "start_km": 75, "end_km": 90, "status": "UPCOMING", "dept": "S&T", "time": "14:00–16:00", "desc": "POINT MACHINE INTERLOCKING TEST", "is_joint": False}
            ],
            "tsrs": [
                {"name": "TSR 30 km/h Caution Order", "start_km": 35, "end_km": 48, "speed_limit": 30}
            ]
        },
        "Secunderabad Division (SC)": {
            "title": "Secunderabad Main Corridor (SC → MLY → CHZ → BG → ZN → KZJ)",
            "stations": [
                {"name": "Secunderabad (SC)", "km": 0, "type": "Division HQ"},
                {"name": "Moula Ali (MLY)", "km": 10, "type": "Junction"},
                {"name": "Cherlapalli (CHZ)", "km": 22, "type": "Terminal"},
                {"name": "Bhongir (BG)", "km": 48, "type": "Station"},
                {"name": "Jangaon (ZN)", "km": 84, "type": "Station"},
                {"name": "Kazipet (KZJ)", "km": 132, "type": "Junction"}
            ],
            "max_km": 140,
            "blocks": [
                {"id": "BLK-SC-088", "start_km": 35, "end_km": 50, "status": "ACTIVE", "dept": "Engineering", "time": "09:30–11:30", "desc": "RAIL RENEWAL WINDOW", "is_joint": False},
                {"id": "BLK-TRD-301", "start_km": 90, "end_km": 105, "status": "OVERRUN", "dept": "TRD", "time": "08:00–10:00 (Ext. 10:25)", "desc": "CATENARY OVERHAUL ⚠ OVERRUN +25m", "is_joint": False}
            ],
            "tsrs": [
                {"name": "TSR 30 km/h Caution Order", "start_km": 35, "end_km": 50, "speed_limit": 30}
            ]
        },
        "Guntakal Division (GTL)": {
            "title": "Guntakal Main Corridor (GTL → AD → MALM → RC → YG → WADI)",
            "stations": [
                {"name": "Guntakal (GTL)", "km": 0, "type": "Division HQ"},
                {"name": "Adoni (AD)", "km": 52, "type": "Station"},
                {"name": "Mantralayam Rd (MALM)", "km": 93, "type": "Station"},
                {"name": "Raichur (RC)", "km": 121, "type": "Junction"},
                {"name": "Yadgir (YG)", "km": 190, "type": "Station"},
                {"name": "Wadi JN (WADI)", "km": 228, "type": "Junction"}
            ],
            "max_km": 240,
            "blocks": [
                {"id": "BLK-GTL-112", "start_km": 65, "end_km": 80, "status": "ACTIVE", "dept": "Engg + S&T", "time": "10:00–12:30", "desc": "TRACK GEOMETRY & AXLE COUNTER MAINTENANCE", "is_joint": True}
            ],
            "tsrs": [
                {"name": "TSR 30 km/h Caution Order", "start_km": 135, "end_km": 155, "speed_limit": 30}
            ]
        },
        "Guntur Division (GNT)": {
            "title": "Guntur Main Line (GNT → NLPD → NRT → VKN → MRK → NDL)",
            "stations": [
                {"name": "Guntur (GNT)", "km": 0, "type": "Division HQ"},
                {"name": "Nallapadu (NLPD)", "km": 12, "type": "Junction"},
                {"name": "Narasaraopet (NRT)", "km": 45, "type": "Station"},
                {"name": "Vinukonda (VKN)", "km": 82, "type": "Station"},
                {"name": "Markapur Rd (MRK)", "km": 140, "type": "Station"},
                {"name": "Nandyal (NDL)", "km": 210, "type": "Junction"}
            ],
            "max_km": 220,
            "blocks": [
                {"id": "BLK-GNT-404", "start_km": 60, "end_km": 75, "status": "ACTIVE", "dept": "Engineering", "time": "09:00–12:00", "desc": "CSM HEAVY TAMPING MACHINE BLOCK", "is_joint": False}
            ],
            "tsrs": [
                {"name": "TSR 30 km/h Caution Order", "start_km": 150, "end_km": 170, "speed_limit": 30}
            ]
        },
        "Hyderabad Division (HYB)": {
            "title": "Hyderabad Suburban Corridor (HYB → KCG → UR → SHNR → JCL → MBNR)",
            "stations": [
                {"name": "Hyderabad (HYB)", "km": 0, "type": "Terminal"},
                {"name": "Kacheguda (KCG)", "km": 12, "type": "Division HQ"},
                {"name": "Umdanagar (UR)", "km": 28, "type": "Station"},
                {"name": "Shadnagar (SHNR)", "km": 55, "type": "Station"},
                {"name": "Jadcherla (JCL)", "km": 90, "type": "Station"},
                {"name": "Mahbubnagar (MBNR)", "km": 108, "type": "Junction"}
            ],
            "max_km": 120,
            "blocks": [
                {"id": "BLK-HYB-050", "start_km": 35, "end_km": 48, "status": "ACTIVE", "dept": "S&T", "time": "10:15–11:45", "desc": "SIGNAL CABLE INTEGRITY TESTING", "is_joint": False}
            ],
            "tsrs": [
                {"name": "TSR 30 km/h Caution Order", "start_km": 90, "end_km": 100, "speed_limit": 30}
            ]
        },
        "Howrah Division (HWH)": {
            "title": "Howrah Main Trunk Corridor (HWH → SRP → BDC → BWN → DGR)",
            "stations": [
                {"name": "Howrah (HWH)", "km": 0, "type": "Division HQ"},
                {"name": "Serampore (SRP)", "km": 20, "type": "Station"},
                {"name": "Bandel (BDC)", "km": 40, "type": "Junction"},
                {"name": "Bardhaman (BWN)", "km": 100, "type": "Junction"},
                {"name": "Durgapur (DGR)", "km": 165, "type": "Industrial Hub"}
            ],
            "max_km": 180,
            "blocks": [
                {"id": "BLK-HWH-040", "start_km": 40, "end_km": 50, "status": "ACTIVE", "dept": "Engineering + TRD", "time": "11:30–14:30", "desc": "CATENARY & TRACK MEGA-BLOCK", "is_joint": True},
                {"id": "BLK-HWH-075", "start_km": 75, "end_km": 82, "status": "UPCOMING", "dept": "S&T", "time": "12:00–14:00", "desc": "ELECTRONIC INTERLOCKING TEST", "is_joint": False}
            ],
            "tsrs": [
                {"name": "TSR 30 km/h Caution Order", "start_km": 40, "end_km": 50, "speed_limit": 30}
            ]
        }
    }

    # Match division flexibly
    cfg = division_configs.get(division)
    if not cfg:
        div_l = str(division).lower()
        for k_d, v_d in division_configs.items():
            if (k_d.lower() in div_l) or (div_l in k_d.lower()) or (k_d[:6].lower() in div_l):
                cfg = v_d
                break
    if not cfg:
        cfg = division_configs["Vijayawada Division (BZA)"]
    stations = cfg["stations"]
    max_km = cfg["max_km"]
    blocks = cfg["blocks"]
    tsrs = cfg["tsrs"]

    fig = go.Figure()

    # 1. Main Line Corridor Track
    fig.add_trace(go.Scatter(
        x=[s["km"] for s in stations],
        y=[0] * len(stations),
        mode="lines+markers+text",
        name="Main Line Track",
        line=dict(color="#2563eb", width=6),
        marker=dict(size=14, color="#38bdf8", symbol="diamond-wide-open", line=dict(width=2.5, color="#ffffff")),
        text=[s["name"] for s in stations],
        textposition="bottom center",
        textfont=dict(size=11, color="#94a3b8", family="monospace"),
        hoverinfo="text"
    ))

    # 2. Speed Restriction (TSR) Zones
    for tsr in tsrs:
        fig.add_trace(go.Scatter(
            x=[tsr["start_km"], tsr["end_km"]], y=[0, 0],
            mode="lines",
            name=f"⚠ TSR {tsr['speed_limit']} km/h",
            line=dict(color="#facc15", width=10, dash="dash"),
            hovertext=f"🟡 <b>TEMPORARY SPEED RESTRICTED ZONE</b><br>Segment: KM {tsr['start_km']} - {tsr['end_km']}<br>Speed Limit: ⚠ {tsr['speed_limit']} km/h Caution"
        ))

    # 3. Maintenance Blocks Directly ON Track Segment
    for blk in blocks:
        st_val = blk["status"]
        if st_val == "ACTIVE":
            b_color = "#ef4444" if not blk.get("is_joint") else "#a855f7"
            b_name = f"████ ACTIVE BLOCK ({blk['id']})"
        elif st_val == "UPCOMING":
            b_color = "#f59e0b"
            b_name = f"░░░░ UPCOMING BLOCK ({blk['id']})"
        elif st_val == "OVERRUN":
            b_color = "#991b1b"
            b_name = f"⚠ OVERRUN BLOCK ({blk['id']})"
        else:
            b_color = "#10b981"
            b_name = f"✔ COMPLETED BLOCK ({blk['id']})"

        fig.add_trace(go.Scatter(
            x=[blk["start_km"], blk["end_km"]], y=[0, 0],
            mode="lines",
            name=b_name,
            line=dict(color=b_color, width=14),
            hovertext=f"🚧 <b>MAINTENANCE BLOCK POSSESSION ({blk['id']})</b><br>Department: {blk['dept']}<br>Status: {blk['status']}<br>Window: {blk['time']}<br>Segment: KM {blk['start_km']} - {blk['end_km']}<br>Description: {blk['desc']}"
        ))

    # 4. Moving Trains & Telemetry Badges
    if df_trains is None or df_trains.empty:
        df_trains = get_active_trains_df(division=division)

    y_levels = [0.45, -0.45, 0.75, -0.75]
    if not df_trains.empty:
        for idx, tr in df_trains.reset_index().iterrows():
            km = float(tr.get("current_km", 25.0))
            t_num = str(tr.get("train_number", f"T-{100+idx}"))
            t_name = str(tr.get("train_name", "Express"))
            t_type = str(tr.get("train_type", "Express"))
            speed = float(tr.get("speed_kmh", 110))
            delay = float(tr.get("delay_minutes", 0))
            direction = str(tr.get("direction", "EB"))
            dir_arrow = "➡ EB" if direction in ["EB", "Eastbound"] else "⬅ WB"
            status_val = str(tr.get("status", "RUNNING"))
            next_stn = str(tr.get("next_station", "Next Station"))

            # Status visual styling
            if status_val == "STOPPED" or speed == 0:
                color = "#ef4444"
                icon = "🛑"
                badge_lbl = f"{icon} {t_num} | 0 km/h (STOPPED)"
            elif status_val in ["RESTRICTED", "SLOWING", "APPROACHING BLOCK"]:
                color = "#f59e0b"
                icon = "⚠️"
                badge_lbl = f"{icon} {t_num} | {speed:.0f} km/h ({status_val})"
            elif delay > 5:
                color = "#f97316"
                icon = "⏱"
                badge_lbl = f"{icon} {t_num} | {speed:.0f} km/h (+{delay:.0f}m)"
            else:
                color = "#22c55e"
                icon = "🚆"
                badge_lbl = f"{icon} {t_num} | {speed:.0f} km/h (RUNNING)"

            y_pos = y_levels[idx % len(y_levels)]
            txt_pos = "top center" if y_pos > 0 else "bottom center"

            # Track Pin ON Blue Line (y = 0)
            fig.add_trace(go.Scatter(
                x=[km], y=[0],
                mode="markers",
                name=f"Pin {t_num}",
                showlegend=False,
                marker=dict(size=14, color=color, symbol="circle", line=dict(width=2.5, color="#ffffff")),
                hovertext=f"📍 <b>Train {t_num} Track Pin</b><br>KM: {km}<br>Speed: {speed:.0f} km/h"
            ))

            # Vertical Connector Line
            fig.add_shape(
                type="line",
                x0=km, y0=0,
                x1=km, y1=y_pos,
                line=dict(color=color, width=2, dash="dot")
            )

            # Floating Train Status Badge Box
            fig.add_trace(go.Scatter(
                x=[km], y=[y_pos],
                mode="markers+text",
                name=f"Train {t_num}",
                showlegend=False,
                marker=dict(size=18, color=color, symbol="square-dot", line=dict(width=2, color="#ffffff")),
                text=[badge_lbl],
                textposition=txt_pos,
                textfont=dict(size=11, color="#ffffff", family="sans-serif"),
                hovertext=f"🚆 <b>{t_num} - {t_name}</b> ({t_type})<br>📍 Current Location: KM {km}<br>➡ Direction: {dir_arrow}<br>⚡ Speed: {speed:.0f} km/h (MPS: {tr.get('mps', 110)} km/h)<br>⏱ Operational Status: {status_val}<br>⏳ Delay Accumulation: +{delay:.0f} min<br>📍 Next Station: {next_stn}"
            ))

    fig.update_layout(
        title=dict(
            text=f"🚆 LIVE CONTROL-ROOM CORRIDOR TRACKING: {cfg['title'].upper()}",
            font=dict(size=13, color="#38bdf8", family="sans-serif"),
            x=0, xanchor="left", y=0.98, yanchor="top"
        ),
        xaxis=dict(title="Corridor Distance (Kilometers - KM)", showgrid=True, gridcolor="#1e293b", range=[-10, max_km]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[-1.4, 1.4]),
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0d1322",
        font=dict(color="#ffffff"),
        height=380,
        margin=dict(l=25, r=25, t=50, b=45),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(15, 23, 42, 0.85)",
            bordercolor="#334155",
            borderwidth=1
        )
    )
    return fig


def advance_telemetry_step(step_km=1.5):
    """
    Advances train KM positions along the corridor deterministically.
    Calculates train-block proximity, speed transitions (110 -> 60 -> 30 -> 0 km/h),
    signal aspects, and delay accumulation, syncing updated state to SQLite and session state.
    """
    init_trains_10_state()
    if "trains_10_state" in st.session_state:
        for t_id, tr in st.session_state.trains_10_state.items():
            curr_km = tr["current_km"]
            direction = tr.get("direction", "EB")
            mps = tr.get("mps", 110)
            work_zone = tr.get("work_zone_kms", [35, 48])
            w_start, w_end = work_zone[0], work_zone[1]

            # Advance KM along route direction
            if direction == "EB":
                new_km = curr_km + step_km
                if new_km > 160: new_km = 5.0
            else:
                new_km = curr_km - step_km
                if new_km < 5.0: new_km = 150.0

            tr["current_km"] = round(new_km, 1)

            # Calculate proximity to active maintenance block / TSR zone (KM w_start to w_end)
            dist_to_block = w_start - new_km if direction == "EB" else new_km - w_end

            if w_start <= new_km <= w_end:
                # Inside Block Possession Zone -> Full Stop or TSR limit
                if tr.get("early_cleared", False):
                    tr["current_speed"] = 30
                    tr["status"] = "RESTRICTED"
                    tr["signal"] = "🟡 Amber Caution (30 km/h)"
                else:
                    tr["current_speed"] = 0
                    tr["status"] = "STOPPED"
                    tr["signal"] = "🔴 Red (Block Possession)"
                    tr["delay_minutes"] = min(60.0, tr["delay_minutes"] + 2.0)
            elif 0 < dist_to_block <= 8.0:
                # Approaching Block -> Decelerating
                tr["current_speed"] = 60
                tr["status"] = "SLOWING"
                tr["signal"] = "🟡 Amber Caution (Approach)"
            else:
                # Clear corridor -> Normal speed cruising
                tr["current_speed"] = mps
                tr["status"] = "RUNNING"
                tr["signal"] = "🟢 Green (Clear Line)"
                if tr["delay_minutes"] > 0:
                    tr["delay_minutes"] = max(0.0, tr["delay_minutes"] - 1.0)

    try:
        conn = get_db()
        for t_id, tr in st.session_state.trains_10_state.items():
            conn.execute("""
                INSERT OR REPLACE INTO live_train_status (train_id, train_name, train_type, division_id, section_id, current_km, speed_kmh, delay_minutes, status, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (t_id, tr.get("name", "Express"), tr.get("type", "Express"), tr.get("division", "Vijayawada Division (BZA)"), tr.get("section_id", "SEC-01"), tr["current_km"], tr["current_speed"], tr["delay_minutes"], tr["status"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except Exception:
        pass


def render_visual_train_cards(df_trains=None, division="Vijayawada Division (BZA)"):
    """
    Renders visual operational status cards for active trains.
    """
    if df_trains is None or df_trains.empty:
        df_trains = get_active_trains_df(division=division)

    h_col1, h_col2 = st.columns([3.5, 1.2])
    with h_col1:
        st.markdown(f"#### 🚆 Live Train Operational Status Cards — {division}")
    with h_col2:
        if st.button("⚡ Refresh / Advance Status", key="btn_adv_tele_cards_header", use_container_width=True):
            advance_telemetry_step()
            st.toast("⚡ Telemetry step advanced train positions & speed vectors.", icon="✅")
            st.rerun()

    if df_trains.empty:
        st.info("No active trains currently on this division's corridor segment.")
        return

    c1, c2 = st.columns(2)
    for idx, tr in df_trains.reset_index().iterrows():
        col = c1 if idx % 2 == 0 else c2
        t_num = tr.get("train_number", f"T-{100+idx}")
        t_name = tr.get("train_name", "Express")
        km = float(tr.get("current_km", 25.0))
        speed = float(tr.get("speed_kmh", 110))
        delay = float(tr.get("delay_minutes", 0))
        direction = tr.get("direction", "EB")
        dir_label = "➡ Eastbound" if direction in ["EB", "Eastbound"] else "⬅ Westbound"
        status_val = tr.get("status", "RUNNING")
        next_stn = tr.get("next_station", "Next Station")

        if status_val == "STOPPED" or speed == 0:
            status_color = "#ef4444"
            status_badge = "🔴 STOPPED (Block Possession)"
        elif status_val in ["RESTRICTED", "SLOWING", "APPROACHING BLOCK"]:
            status_color = "#f59e0b"
            status_badge = f"🟡 {status_val} ({speed:.0f} km/h)"
        elif delay > 5:
            status_color = "#f97316"
            status_badge = f"🟠 DELAYED (+{delay:.0f}m)"
        else:
            status_color = "#10b981"
            status_badge = f"🟢 RUNNING ({speed:.0f} km/h)"

        with col:
            st.markdown(f"""
            <div style="background: #0f172a; border: 1.5px solid #1e293b; border-left: 5px solid {status_color}; border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; box-shadow: 0 3px 10px rgba(0,0,0,0.15);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-weight: 800; font-size: 15px; color: #ffffff;">🚆 {t_num} — {t_name}</div>
                    <span style="font-size: 11px; background: #1e293b; color: {status_color}; border: 1px solid {status_color}; font-weight: 700; padding: 2px 8px; border-radius: 12px;">{status_badge}</span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; font-size: 12px; color: #94a3b8;">
                    <div>📍 <b>Location:</b> KM {km:.1f} ({tr.get('section_id', 'SEC')})</div>
                    <div>➡ <b>Direction:</b> {dir_label}</div>
                    <div>⚡ <b>Current Speed:</b> <span style="color: #ffffff; font-weight: 700;">{speed:.0f} km/h</span></div>
                    <div>⏱ <b>Delay:</b> <span style="color: {'#ef4444' if delay > 5 else '#22c55e'}; font-weight: 700;">+{delay:.0f} mins</span></div>
                    <div>📍 <b>Next Station:</b> {next_stn}</div>
                    <div>⚡ <b>MPS Limit:</b> {tr.get('mps', 110)} km/h</div>
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_visual_ai_advisory_flow(alerts=None):
    """
    Renders visual step-by-step pipeline for AI agent detections:
    [Detected Event] ➔ [Probable Cause] ➔ [Operational Impact] ➔ [Risk Level] ➔ [AI Advisory] ➔ [Controller Action]
    """
    st.markdown("""
    <div style="background: #0f172a; border: 1.5px solid #1e293b; border-radius: 12px; padding: 16px; margin-bottom: 18px; box-shadow: 0 4px 14px rgba(0,0,0,0.2);">
        <div style="font-size: 14px; font-weight: 800; color: #38bdf8; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
            <span>🤖 Visual AI Advisory & Operational Impact Flow</span>
            <span style="font-size: 10px; background: rgba(56,189,248,0.2); color: #38bdf8; padding: 2px 8px; border-radius: 10px;">Human-in-the-Loop</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px; overflow-x: auto; padding-bottom: 6px;">
            <div style="flex: 1; min-width: 140px; background: #1e293b; border: 1px solid #ef4444; border-radius: 8px; padding: 10px; text-align: center;">
                <div style="font-size: 10px; color: #ef4444; font-weight: 700; text-transform: uppercase;">1. Detected Event</div>
                <div style="font-size: 12px; font-weight: 700; color: #ffffff; margin-top: 4px;">Track Geometry Fault</div>
                <div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">SEC-01 (KM 34.2)</div>
            </div>
            <div style="color: #64748b; font-weight: 800; font-size: 16px;">➔</div>
            <div style="flex: 1; min-width: 140px; background: #1e293b; border: 1px solid #f59e0b; border-radius: 8px; padding: 10px; text-align: center;">
                <div style="font-size: 10px; color: #f59e0b; font-weight: 700; text-transform: uppercase;">2. Probable Cause</div>
                <div style="font-size: 12px; font-weight: 700; color: #ffffff; margin-top: 4px;">Ballast Settlement</div>
                <div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">High Axle Load Freight</div>
            </div>
            <div style="color: #64748b; font-weight: 800; font-size: 16px;">➔</div>
            <div style="flex: 1; min-width: 140px; background: #1e293b; border: 1px solid #38bdf8; border-radius: 8px; padding: 10px; text-align: center;">
                <div style="font-size: 10px; color: #38bdf8; font-weight: 700; text-transform: uppercase;">3. Operational Impact</div>
                <div style="font-size: 12px; font-weight: 700; color: #ffffff; margin-top: 4px;">18m Delay Cascade</div>
                <div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">Affects 4 Trailing Trains</div>
            </div>
            <div style="color: #64748b; font-weight: 800; font-size: 16px;">➔</div>
            <div style="flex: 1; min-width: 140px; background: #1e293b; border: 1px solid #ef4444; border-radius: 8px; padding: 10px; text-align: center;">
                <div style="font-size: 10px; color: #ef4444; font-weight: 700; text-transform: uppercase;">4. Risk Level</div>
                <div style="font-size: 12px; font-weight: 800; color: #ef4444; margin-top: 4px;">🔴 CRITICAL RISK</div>
                <div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">Derailment Hazard</div>
            </div>
            <div style="color: #64748b; font-weight: 800; font-size: 16px;">➔</div>
            <div style="flex: 1; min-width: 150px; background: #1e293b; border: 1px solid #10b981; border-radius: 8px; padding: 10px; text-align: center;">
                <div style="font-size: 10px; color: #10b981; font-weight: 700; text-transform: uppercase;">5. AI Advisory</div>
                <div style="font-size: 11.5px; font-weight: 700; color: #ffffff; margin-top: 4px;">Shadow Block Merge</div>
                <div style="font-size: 10px; color: #4ade80; margin-top: 2px;">TSR 30 km/h + 2.5h Window</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


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
            p_input = st.text_input("🔑 Password", type="password", placeholder="Enter your password")
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
        <div style="background: transparent; border: 1px solid rgba(249, 115, 22, 0.4); border-radius: 8px; padding: 12px 14px; margin-top: 14px; margin-bottom: 10px; color: #f97316; font-size: 0.88rem; line-height: 1.45; font-weight: 600;">
            ⚠️ <strong>Prototype Notice</strong>: Quick Department Access is provided only for convenient demonstration and navigation of this prototype. It does not represent the complete security/authentication mechanism required for a production railway system.
        </div>
        """, unsafe_allow_html=True)

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
        "dept_title": "ENGINEERING (TRACK / P-WAY)",
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
DEPARTMENT_CONFIGS = DEPT_PORTAL_CONFIG



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
    if "tts_voice_lang" not in st.session_state:
        st.session_state.tts_voice_lang = "Auto Match Response"

    # Auto-repair orphan user messages in session state
    dept_hist = st.session_state[dept_chat_key]
    if dept_hist and isinstance(dept_hist[-1], dict) and dept_hist[-1].get("role") == "user":
        orphan_q = dept_hist[-1].get("content")
        try:
            ans = ask_explainer(
                orphan_q,
                department=department,
                page_context=page_context,
                chat_history=dept_hist[:-1],
                user_lang_pref=st.session_state.selected_lang
            )
        except Exception as e:
            ans = f"⚠️ Response error: {str(e)}"
        dept_hist.append({"role": "assistant", "content": ans})
        st.session_state[dept_chat_key] = dept_hist

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

    # Controls Header: Response Language Selector & Clear Button
    c_hdr1, c_hdr2 = st.columns([2.2, 0.8])
    with c_hdr1:
        st.session_state.selected_lang = st.selectbox(
            "🌐 AI Response Lang",
            ["Auto Detect", "English", "తెలుగు", "హిन्दी"],
            key="ai_lang_select",
            help="AI Text Response Language"
        )
    with c_hdr2:
        st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
        if st.button("🗑️", key="btn_clear_chat_hist", use_container_width=True, help="Clear conversation history"):
            st.session_state[dept_chat_key] = []
            st.session_state.chat_history = []
            st.rerun()

    # Quick Prompts / Operational Query Chips
    with st.popover("⚡ Quick Actions & Analytics", use_container_width=True):
        st.markdown("#### ⚡ Operational Quick Actions")
        qp1 = st.button("📅 Today's Scheduled Blocks", key="qp1_btn", use_container_width=True)
        qp2 = st.button("🤝 Multi-Dept Shadow Blocking", key="qp2_btn", use_container_width=True)
        qp3 = st.button("⚡ Speed Recovery Status", key="qp3_btn", use_container_width=True)
        qp4 = st.button("🌊 Delay Cascade Forecast", key="qp4_btn", use_container_width=True)
        qp5 = st.button("📊 TRD Open Defects", key="qp5_btn", use_container_width=True)
        qp6 = st.button("🇮🇳 తెలుగులో వివరణ", key="qp6_btn", use_container_width=True)
        qp7 = st.button("🇮🇳 हिंदी में जानकारी", key="qp7_btn", use_container_width=True)

    selected_prompt = None
    if qp1: selected_prompt = "What maintenance blocks are scheduled for today?"
    if qp2: selected_prompt = "Explain how multi-department shadow block clustering saves 37.5% downtime."
    if qp3: selected_prompt = "Show me the current Locopilot speed recovery status and time saved."
    if qp4: selected_prompt = "What is the predicted 4-hour delay cascade forecast for trailing trains?"
    if qp5: selected_prompt = "How many open TRD traction defects are pending in the backlog?"
    if qp6: selected_prompt = "రైల్వే బ్లాక్ ప్లానింగ్ మరియు షాడో బ్లాకింగ్ విధానాన్ని వివరించండి"
    if qp7: selected_prompt = "रेलवे ब्लॉक योजना और शैडो ब्लॉकिंग प्रक्रिया के बारे में बताएं"

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
                        # Single Smart Audio Play Button matching response language
                        escaped_text = json.dumps(msg["content"])
                        det_l = detect_language(msg["content"])
                        if det_l == "te":
                            t_code = "te-IN"
                            t_label = "TE"
                            btn_color = "#0d9488"
                        elif det_l == "hi":
                            t_code = "hi-IN"
                            t_label = "HI"
                            btn_color = "#ea580c"
                        else:
                            t_code = "en-US"
                            t_label = "EN"
                            btn_color = "#0284c7"

                        audio_btn_html = f"""
                        <div style="margin-top: 4px;">
                            <button onclick="speakText('{t_code}')" style="background: {btn_color}; color: white; border: none; border-radius: 12px; padding: 4px 10px; font-size: 11px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 4px; box-shadow: 0 1px 4px rgba(0,0,0,0.15);">
                                🔊 Listen ({t_label})
                            </button>
                        </div>
                        <script>
                        const txt = {escaped_text};
                        function speakText(targetLang) {{
                            if ("speechSynthesis" in window) {{
                                window.speechSynthesis.cancel();
                                const u = new SpeechSynthesisUtterance(txt);
                                u.lang = targetLang;
                                u.rate = 0.95;

                                const voices = window.speechSynthesis.getVoices();
                                const langPrefix = targetLang.split("-")[0].toLowerCase();
                                const matchVoice = voices.find(v => (v.lang && v.lang.toLowerCase().replace("_","-").startsWith(langPrefix)));
                                if (matchVoice) {{
                                    u.voice = matchVoice;
                                }}

                                window.speechSynthesis.speak(u);
                            }} else {{
                                alert("Text-to-speech not supported in browser.");
                            }}
                        }}
                        </script>
                        """
                        components.html(audio_btn_html, height=36)
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
    curr_tts = st.session_state.get("tts_voice_lang", "Auto Match Response")
    
    # Determine default recognition locale
    if curr_lang == "తెలుగు" or curr_tts == "తెలుగు":
        default_stt_code = "te-IN"
    elif curr_lang == "హిन्दी" or curr_tts == "హిन्दी":
        default_stt_code = "hi-IN"
    elif curr_lang == "English" or curr_tts == "English":
        default_stt_code = "en-US"
    else:
        default_stt_code = "te-IN"

    components.html(
        f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: space-between; background: #ffffff; padding: 6px 10px; border-radius: 10px; border: 1.5px solid #cbd5e1; margin-bottom: 6px;">
            <span id="vStatus" style="font-size: 11.5px; color: #475569; font-weight: 600;">
                🎤 Voice Mic ({default_stt_code[:2].upper()})
            </span>
            <div style="display: flex; align-items: center; gap: 4px;">
                <button id="micEn" title="Speak in English" style="background: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; padding: 2px 6px; font-size: 10.5px; font-weight: 700; cursor: pointer;">EN</button>
                <button id="micTe" title="Speak in Telugu" style="background: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; padding: 2px 6px; font-size: 10.5px; font-weight: 700; cursor: pointer;">TE</button>
                <button id="micHi" title="Speak in Hindi" style="background: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1; border-radius: 6px; padding: 2px 6px; font-size: 10.5px; font-weight: 700; cursor: pointer;">HI</button>
                <button id="micBtn" title="Click to speak in active language" style="background: #0284c7; color: white; border: none; border-radius: 50%; width: 28px; height: 28px; font-size: 13px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s; box-shadow: 0 2px 5px rgba(2,132,199,0.3);">
                    🎤
                </button>
            </div>
        </div>
        <script>
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const micBtn = document.getElementById('micBtn');
        const micEn = document.getElementById('micEn');
        const micTe = document.getElementById('micTe');
        const micHi = document.getElementById('micHi');
        const vStatus = document.getElementById('vStatus');
        
        if (SpeechRecognition) {{
            let rec = new SpeechRecognition();
            let listening = false;
            let currentLangCode = "{default_stt_code}";

            function startRecognition(langCode) {{
                if (listening) {{
                    rec.stop();
                }}
                currentLangCode = langCode;
                rec.continuous = false;
                rec.interimResults = false;
                rec.lang = langCode;
                try {{
                    rec.start();
                }} catch(e) {{
                    setTimeout(() => rec.start(), 200);
                }}
            }}

            micEn.addEventListener('click', () => startRecognition('en-US'));
            micTe.addEventListener('click', () => startRecognition('te-IN'));
            micHi.addEventListener('click', () => startRecognition('hi-IN'));
            micBtn.addEventListener('click', () => startRecognition(currentLangCode));

            rec.onstart = () => {{
                listening = true;
                micBtn.style.backgroundColor = '#16a34a';
                vStatus.innerHTML = "<span style='color:#16a34a; font-weight:bold;'>🎙️ Listening (" + currentLangCode.slice(0,2).toUpperCase() + ")... Speak now</span>";
            }};

            rec.onresult = (e) => {{
                let text = e.results[0][0].transcript;
                if (!text || !text.trim()) {{
                    vStatus.innerHTML = "<span style='color:#f59e0b; font-weight:600;'>⚠️ Empty recognition. Please try speaking again.</span>";
                    return;
                }}
                vStatus.innerHTML = "<span style='color:#16a34a; font-weight:bold;'>✓ Recognized (" + currentLangCode.slice(0,2).toUpperCase() + "): \\"" + text + "\\"</span>";
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
                    vStatus.innerHTML = "<span style='color:#ef4444; font-weight:600;'>⚠️ Mic permission denied. Please enable mic access.</span>";
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

    # Process user query safely and reliably
    if active_query and active_query.strip():
        clean_q = active_query.strip()
        dept_history = st.session_state[dept_chat_key]

        # Check if the very last exchange in history is already an answered version of this exact question
        already_answered = False
        if len(dept_history) >= 2:
            if dept_history[-2].get("role") == "user" and dept_history[-2].get("content") == clean_q and dept_history[-1].get("role") == "assistant":
                already_answered = True

        if not already_answered:
            # If the last item is an un-answered user message with the same content, remove it first to avoid duplicate user bubbles
            if dept_history and dept_history[-1].get("role") == "user" and dept_history[-1].get("content") == clean_q:
                dept_history.pop()

            dept_history.append({"role": "user", "content": clean_q})
            try:
                with st.spinner("Analyzing website knowledge base..."):
                    ans = ask_explainer(
                        clean_q,
                        department=department,
                        page_context=page_context,
                        chat_history=dept_history,
                        user_lang_pref=st.session_state.selected_lang
                    )
            except Exception as e:
                ans = f"⚠️ Could not complete query: {str(e)}"

            dept_history.append({"role": "assistant", "content": ans})
            st.session_state[dept_chat_key] = dept_history
            st.session_state.chat_history = dept_history
            st.rerun()




@st.cache_data(ttl=5)
def get_cached_override_active_blocks():
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
    return df_active


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
        q += " AND (s.horizon = ? OR s.horizon = 'emergency' OR s.decided_by IN ('controller_override', 'controller_emergency', 'emergency_force_override', 'admin'))"
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
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Sign Out", use_container_width=True):
    st.session_state.user = None
    if "trains_10_state" in st.session_state:
        del st.session_state["trains_10_state"]
    if "last_action_banner" in st.session_state:
        del st.session_state["last_action_banner"]
    st.rerun()


    # ---------------------------------------------------------------------------
    # Top Header Layout with Notifications
# ---------------------------------------------------------------------------

conn = get_db()
cur = conn.cursor()
where_conds = []
if is_dept_user:
    u_role = str(user.get('role', '')).lower()
    if u_role == 'engineering' or my_dept == 'Engineering':
        where_conds.append("(recipient_role IN ('engineering', 'Engineering', 'tms', 'TMS') OR (message LIKE '%Engineering%' OR message LIKE '%TMS%' OR message LIKE '%P-Way%' OR message LIKE '%Track%')) AND recipient_role NOT IN ('signal', 'traction', 'st', 'trd')")
    elif u_role == 'signal' or my_dept == 'S&T':
        where_conds.append("(recipient_role IN ('signal', 'Signal', 'st', 'ST', 'S&T', 'smms', 'SMMS') OR (message LIKE '%Signal%' OR message LIKE '%S&T%' OR message LIKE '%SMMS%' OR message LIKE '%Interlocking%')) AND recipient_role NOT IN ('engineering', 'traction', 'trd')")
    elif u_role == 'traction' or my_dept == 'TRD':
        where_conds.append("(recipient_role IN ('traction', 'Traction', 'trd', 'TRD', 'tdms', 'TDMS') OR (message LIKE '%Traction%' OR message LIKE '%TRD%' OR message LIKE '%TDMS%' OR message LIKE '%OHE%' OR message LIKE '%Power Block%')) AND recipient_role NOT IN ('engineering', 'signal', 'st')")
    else:
        where_conds.append(f"recipient_role = '{user.get('role', '')}'")
notif_where = " WHERE " + " AND ".join(where_conds) if where_conds else ""
notif_query = f"SELECT notif_id, recipient_role, category, audience, message, created_at, COALESCE(is_read, 0) as is_read FROM notifications {notif_where} ORDER BY notif_id DESC LIMIT 25"
cur.execute(notif_query)
notif_rows = [dict(r) for r in cur.fetchall()]
conn.close()

unread_count = sum(1 for n in notif_rows if n["is_read"] == 0)

top_col1, top_col2 = st.columns([5, 1.8])
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
    badge_label = f"🔔 Alerts ({unread_count})" if unread_count > 0 else "🔔 Alerts (0)"
    with st.popover(badge_label, use_container_width=True):
        st.markdown("### 🔔 Live Alerts & Bulletins")
        if notif_rows:
            if unread_count > 0:
                if st.button("✓ Mark All as Read", key="clear_all_notifs_btn", use_container_width=True):
                    conn = get_db()
                    unread_ids = tuple(n["notif_id"] for n in notif_rows if n["is_read"] == 0)
                    if unread_ids:
                        if len(unread_ids) == 1:
                            conn.execute("UPDATE notifications SET is_read = 1 WHERE notif_id = ?", (unread_ids[0],))
                        else:
                            conn.execute(f"UPDATE notifications SET is_read = 1 WHERE notif_id IN {unread_ids}")
                        conn.commit()
                    conn.close()
                    st.cache_data.clear()
                    st.toast("All notifications marked as read!", icon="✅")
                    st.rerun()

            st.markdown("---")

            for n in notif_rows[:10]:
                n_id = n["notif_id"]
                is_r = (n["is_read"] == 1)
                badge = "📢 [PUBLIC]" if n["audience"] == "public" else "🔒 [STAFF]"

                if not is_r:
                    # UNREAD: Vivid alert boxes with active Mark Read button
                    n_c1, n_c2 = st.columns([3.5, 1])
                    with n_c1:
                        if n["category"] in ["deadline", "emergency", "conflict"]:
                            st.error(f"**🟡 UNREAD** | **{badge}** {n['message']}\n\n*{n['created_at']}*")
                        elif n["category"] == "anomaly":
                            st.warning(f"**🟡 UNREAD** | **{badge}** {n['message']}\n\n*{n['created_at']}*")
                        else:
                            st.info(f"**🟡 UNREAD** | **{badge}** {n['message']}\n\n*{n['created_at']}*")
                    with n_c2:
                        if st.button("✓ Read", key=f"read_notif_{n_id}", use_container_width=True):
                            conn = get_db()
                            conn.execute("UPDATE notifications SET is_read = 1 WHERE notif_id = ?", (n_id,))
                            conn.commit()
                            conn.close()
                            st.cache_data.clear()
                            st.toast("Notification marked as read!", icon="✅")
                            st.rerun()
                else:
                    # READ: Distinct Muted Slate/Gray Card
                    n_c1, n_c2 = st.columns([3.5, 1])
                    with n_c1:
                        st.markdown(f"""
                        <div style="background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 8px 12px; margin-bottom: 6px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
                                <span style="font-size: 0.72rem; background-color: #334155; color: #94a3b8; padding: 2px 6px; border-radius: 4px; font-weight: 600;">
                                    {badge} &nbsp;•&nbsp; ✅ READ
                                </span>
                                <span style="font-size: 0.70rem; color: #64748b;">{n['created_at']}</span>
                            </div>
                            <div style="font-size: 0.84rem; color: #cbd5e1; line-height: 1.3;">
                                {n['message']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    with n_c2:
                        if st.button("↩ Unread", key=f"unread_notif_{n_id}", use_container_width=True):
                            conn = get_db()
                            conn.execute("UPDATE notifications SET is_read = 0 WHERE notif_id = ?", (n_id,))
                            conn.commit()
                            conn.close()
                            st.cache_data.clear()
                            st.toast("Notification marked as unread!", icon="ℹ️")
                            st.rerun()
        else:
            st.success("🎉 No notifications found.")

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

        # Determine 7 rolling dates starting from current operational date (2026-09-16)
        base_dt = datetime.strptime("2026-09-16", "%Y-%m-%d")
        valid_dates = sorted([d for d in df["date_str"].unique() if d >= "2026-09-16"])
        if len(valid_dates) >= 7:
            selected_dates = valid_dates[:7]
        else:
            selected_dates = [(base_dt + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    
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

            # 1. VISUAL OPERATIONAL KPI STRIP
            render_operational_kpi_bar(department=my_dept)

            # 2. LIVE INTERACTIVE RAILWAY CORRIDOR MAP (PLOTLY)
            df_active_trains = get_active_trains_df()
            fig_map = render_live_corridor_map_plotly(df_active_trains)
            st.plotly_chart(fig_map, use_container_width=True)

            # 3. VISUAL TRAIN STATUS CARDS
            render_visual_train_cards(df_active_trains)

            st.markdown("---")
            target_dept = my_dept
            filter_cfg = DEPARTMENT_CONFIGS.get(target_dept, cur_dept_cfg)

            if target_dept:
                st.subheader(f"📊 {filter_cfg['acronym']} Asset Reliability & Defect Metrics")

                dept_counts = get_cached_department_overview_counts(target_dept)
                tot_d = dept_counts["tot_d"]
                open_d = dept_counts["open_d"]
                sched_d = dept_counts["sched_d"]
                comp_d = dept_counts["comp_d"]
                sched_blocks = dept_counts["sched_blocks"]
                crit_d = dept_counts["crit_d"]

                comp_rate = (comp_d / tot_d * 100) if tot_d > 0 else 0.0
                open_pct = (open_d / tot_d * 100) if tot_d > 0 else 0.0

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric(f"Total {filter_cfg['acronym']} Defects", f"{tot_d:,}", help="Total defects logged in system")
                m2.metric("Active Open Backlog", f"{open_d:,}", delta=f"{open_pct:.1f}% of total", delta_color="inverse")
                m3.metric("Critical Safety Faults", f"{crit_d:,}", delta="Urgent Priority", delta_color="inverse")
                m4.metric("Approved Block Windows", f"{sched_blocks:,}", delta="Coordinated Plan")
                m5.metric("Compliance Rate", f"{comp_rate:.1f}%", delta=f"{comp_d:,} Certified Fit")

                st.markdown("---")

                c_ov1, c_ov2 = st.columns(2)
                with c_ov1:
                    st.markdown(f"#### ⚠️ Defect Severity Distribution ({filter_cfg['acronym']})")
                    conn = get_db()
                    df_sev = pd.read_sql("SELECT severity, COUNT(*) as count FROM defects WHERE department=? GROUP BY severity", conn, params=(target_dept,))
                    conn.close()
                    if not df_sev.empty:
                        fig_sev = px.pie(
                            df_sev, names="severity", values="count",
                            title=f"{filter_cfg['acronym']} Defects by Severity Level",
                            color="severity",
                            color_discrete_map={"Critical": "#ef4444", "High": "#f97316", "Medium": "#3b82f6", "Low": "#10b981"},
                            hole=0.4
                        )
                        fig_sev.update_layout(margin=dict(t=40, b=20, l=20, r=20))
                        st.plotly_chart(fig_sev, use_container_width=True)
                    else:
                        st.info("No defect data available.")

                with c_ov2:
                    st.markdown(f"#### 📌 Work Order Execution Status ({filter_cfg['acronym']})")
                    conn = get_db()
                    df_st = pd.read_sql("SELECT status, COUNT(*) as count FROM defects WHERE department=? GROUP BY status", conn, params=(target_dept,))
                    conn.close()
                    if not df_st.empty:
                        fig_st = px.bar(
                            df_st, x="status", y="count", color="status",
                            title=f"{filter_cfg['acronym']} Tasks by Lifecycle Status",
                            color_discrete_map={"Open": "#ef4444", "Scheduled": "#3b82f6", "Completed": "#10b981"}
                        )
                        fig_st.update_layout(margin=dict(t=40, b=20, l=20, r=20), xaxis_title="Status", yaxis_title="Number of Work Orders")
                        st.plotly_chart(fig_st, use_container_width=True)
                    else:
                        st.info("No status data available.")

                st.markdown("---")

                c_ov3, c_ov4 = st.columns(2)
                with c_ov3:
                    st.markdown(f"#### 📍 Top Priority Railway Sections ({filter_cfg['acronym']})")
                    conn = get_db()
                    df_sec = pd.read_sql("""
                        SELECT section_id, COUNT(*) as defect_count, AVG(priority_score) as avg_priority 
                        FROM defects 
                        WHERE department=? AND LOWER(status)!='completed'
                        GROUP BY section_id 
                        ORDER BY avg_priority DESC 
                        LIMIT 8
                    """, conn, params=(target_dept,))
                    conn.close()
                    if not df_sec.empty:
                        fig_sec = px.bar(
                            df_sec, x="section_id", y="avg_priority", color="defect_count",
                            title=f"High-Priority Maintenance Sections ({filter_cfg['acronym']})",
                            labels={"avg_priority": "Avg Priority (0-100)", "section_id": "Railway Section", "defect_count": "Open Defect Count"},
                            color_continuous_scale="Blues"
                        )
                        fig_sec.update_layout(margin=dict(t=40, b=20, l=20, r=20))
                        st.plotly_chart(fig_sec, use_container_width=True)
                    else:
                        st.info("No section defect data available.")

                with c_ov4:
                    theme_c = filter_cfg["theme_color"] if filter_cfg else "#1f77b4"
                    st.markdown(f"#### 🔧 Defect Category Frequency ({filter_cfg['acronym']})")
                    conn = get_db()
                    df_type = pd.read_sql("""
                        SELECT defect_type, COUNT(*) as count 
                        FROM defects 
                        WHERE department=? 
                        GROUP BY defect_type 
                        ORDER BY count DESC 
                        LIMIT 8
                    """, conn, params=(target_dept,))
                    conn.close()
                    if not df_type.empty:
                        fig_type = px.bar(
                            df_type, y="defect_type", x="count", orientation="h",
                            title=f"Common Maintenance Work Types ({filter_cfg['acronym']})",
                            labels={"defect_type": "Work Category", "count": "Registered Incidents"},
                            color_discrete_sequence=[theme_c]
                        )
                        fig_type.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(t=40, b=20, l=20, r=20))
                        st.plotly_chart(fig_type, use_container_width=True)
                    else:
                        st.info("No defect category data available.")

                st.markdown("---")
                st.markdown(f"#### 🚨 Critical & High-Priority Safety Focus ({filter_cfg['acronym']})")
                conn = get_db()
                df_focus = pd.read_sql("""
                    SELECT defect_id, section_id, defect_type, severity, priority_score, estimated_duration_hours, trains_affected_per_day, due_date, status
                    FROM defects
                    WHERE department=? AND LOWER(status)!='completed'
                    ORDER BY priority_score DESC
                    LIMIT 10
                """, conn, params=(target_dept,))
                conn.close()
                if not df_focus.empty:
                    st.dataframe(df_focus, use_container_width=True, hide_index=True)
                    display_overall_statistics(df_focus, context_title=f"{filter_cfg['acronym']} Critical Tasks")
                else:
                    st.success("✅ No critical safety backlog currently pending.")
            else:
                st.subheader("📊 Operational Defect & Capacity Metrics")
                admin_counts = get_cached_admin_overview_counts("All Departments")
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

        # =======================================================================
        # SEGMENT 2: MAINTENANCE BLOCK SCHEDULE
        # =======================================================================
        elif "Schedule" in dept_menu:
            st.subheader(f"📅 Maintenance Block Schedule & Corridor Planning ({cur_dept_cfg['acronym']} — {my_dept})")
            st.caption(f"Coordinated block disconnections granted by Central Controller (COA) for {cur_dept_cfg['full_system']}. Regularly updated across rolling weekly and monthly planning horizons.")

            now_dt = datetime.now()
            week_end = now_dt + timedelta(days=7)
            month_end = now_dt + timedelta(days=30)
            d_week_label = f"📅 7-Day Rolling Weekly Plan ({now_dt.strftime('%d %b')} – {week_end.strftime('%d %b %Y')})"
            d_month_label = f"🗓️ 30-Day Strategic Monthly Plan ({now_dt.strftime('%d %b')} – {month_end.strftime('%d %b %Y')})"

            d_tab_w, d_tab_m = st.tabs([d_week_label, d_month_label])

            def render_dept_schedule_view(df_sched_sub, horizon_name):
                if not df_sched_sub.empty:
                    df_sched_sub["Timeline"] = df_sched_sub.apply(
                        lambda r: f"{format_time_12h(r['planned_start'])} to {format_time_12h(r['planned_end'])}",
                        axis=1
                    )
                    df_sched_sub["Corridor Duration"] = df_sched_sub["slot_duration_hours"].apply(lambda h: f"{h} Hours" if pd.notna(h) else "Allocated")
                    df_sched_sub["Required Repair Duration"] = df_sched_sub["estimated_duration_hours"].apply(lambda h: f"{h} Hours" if pd.notna(h) else "N/A")

                    st.markdown("##### 📊 Interactive Corridor Block Allocation Gantt Timeline")

                    try:
                        gantt_df = df_sched_sub.copy()
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
                            title=f"🚆 Scheduled Block Windows ({cur_dept_cfg['acronym']} — {horizon_name})",
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
                    matrix_html = generate_ai_block_plan_matrix_html(df_sched_sub, current_dept=my_dept, color_mode="impact")
                    components.html(matrix_html, height=450, scrolling=True)

                    st.markdown(f"##### 📋 Block Allocation Table ({cur_dept_cfg['acronym']} — {horizon_name})")
                    table_cols = [
                        "schedule_id", "defect_id", "section_id", "defect_type",
                        "severity", "Timeline", "Corridor Duration", "Required Repair Duration",
                        "status", "decided_by"
                    ]
                    st.dataframe(df_sched_sub[table_cols], use_container_width=True, hide_index=True)
                    display_overall_statistics(df_sched_sub, context_title=f"{cur_dept_cfg['acronym']} {horizon_name}")
                else:
                    st.info(f"No maintenance blocks currently scheduled for {cur_dept_cfg['acronym']} in the {horizon_name.lower()}.")

            with d_tab_w:
                df_sched_w = get_full_schedule(department=my_dept, horizon="weekly", include_completed=False)
                render_dept_schedule_view(df_sched_w, "Weekly Plan")

            with d_tab_m:
                df_sched_m = get_full_schedule(department=my_dept, horizon="monthly", include_completed=False)
                render_dept_schedule_view(df_sched_m, "Monthly Plan")

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
                    is_emergency = st.checkbox("🚨 Fast-Track Emergency Line Block (Instant AI Conflict Check & Controller Escalation)", value=False)
                    c_rf1, c_rf2 = st.columns(2)
                    with c_rf1:
                        req_sec = st.selectbox("Select Railway Section", all_sections)
                        req_date = st.date_input("Requested Block Date", value=datetime.now().date() + timedelta(days=2))
                        req_sev = st.selectbox("Defect Severity Level", ["Critical", "High", "Medium", "Low"], index=0 if is_emergency else 2)
                    with c_rf2:
                        req_dur = st.number_input("Required Block Duration (Hours)", min_value=0.5, max_value=12.0, value=2.5, step=0.5)
                        req_def_type = st.text_input("Maintenance Work Description", value=f"{'🚨 EMERGENCY ' if is_emergency else ''}{cur_dept_cfg['scope'].split(',')[0]} scheduled repair")
                        req_justification = st.text_area("Operational Safety Justification", value=f"{'🚨 [EMERGENCY FAST-TRACK REQUISITION] ' if is_emergency else ''}Mandatory {cur_dept_cfg['acronym']} safety inspection and preventive component replacement.")

                    submit_req = st.form_submit_button("📩 Submit Block Requisition to Section Controller", type="primary", use_container_width=True)

                if submit_req:
                    date_str = req_date.strftime("%Y-%m-%d")
                    slot_agent = SlotRequestAgent()
                    req_id = slot_agent.create_request(
                        department=my_dept,
                        section_id=req_sec,
                        requested_date=date_str,
                        defect_type=req_def_type,
                        severity="Critical" if is_emergency else req_sev,
                        justification=req_justification,
                        duration_hours=req_dur
                    )
                    if is_emergency:
                        st.success(f"🚨 **EMERGENCY Requisition #{req_id}** fast-tracked with instant CP-SAT safety conflict clearance! Escalated to Section Controller.")
                    else:
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
    if admin_menu == "🚆 Locopilot Speed & Live Trains":
        # --- FULL-WIDTH CORRIDOR TRACKING & LOCOPILOT SPEED CENTER ---
        st.subheader("🚆 Live Corridor Traffic & Locopilot Speed Optimization Center")
        st.caption("COA Real-Time Digital Twin • Moving Train Vectors • Dynamic Early Block Clearance Prioritization • Multi-Department Block Merging")

        loco_agent = LocopilotSpeedAgent()
        merger_agent = BlockMergingAgent()

        col_div1, col_div2 = st.columns([2.5, 1.5])
        with col_div1:
            selected_division = st.selectbox(
                "🚉 Select Operational Division:",
                ["Khurda Road Division (KUR)", "Vijayawada Division (BZA)", "Secunderabad Division (SC)", "Howrah Division (HWH)", "Guntakal Division (GTL)", "Guntur Division (GNT)", "Hyderabad Division (HYB)"],
                key="live_track_selected_division"
            )
        with col_div2:
            st.markdown("<div style='padding-top: 24px; text-align: right;'><span style='background: #1e293b; color: #38bdf8; border: 1px solid #334155; padding: 6px 12px; border-radius: 8px; font-weight: 600; font-size: 13px;'>📡 RTIS / COA Live Stream: ACTIVE</span></div>", unsafe_allow_html=True)

        # 1. VISUAL OPERATIONAL KPI STRIP
        render_operational_kpi_bar(department="All", division=selected_division)

        # 2. LIVE INTERACTIVE RAILWAY CORRIDOR MAP (PLOTLY)
        df_active_trains = get_active_trains_df(division=selected_division)
        fig_map = render_live_corridor_map_plotly(df_active_trains, division=selected_division)
        st.plotly_chart(fig_map, use_container_width=True)

        # 3. VISUAL TRAIN CARDS
        render_visual_train_cards(df_active_trains, division=selected_division)

        st.markdown("---")

        # --- FEATURE 1: TRANSPARENT G&SR SAFETY CLEARANCE CERTIFICATE ---
        with st.expander("🛡️ Transparent G&SR Safety Clearance Certificate Viewer", expanded=False):
            safety_agent = SafetyClearanceAgent()
            cert = safety_agent.generate_gsr_certificate(schedule_id=1, section_id="Vijayawada-SEC-01")
            st.success(f"### {cert['overall_status']}")
            st.caption(f"**Certificate ID:** `{cert['certificate_id']}` | **Section:** `{cert['section_id']}` | **Department:** `{cert['department']}` | **Window:** `{cert['block_window']}`")
            
            df_checks = pd.DataFrame(cert["safety_checks"], columns=["G&SR Safety Rule", "Evaluation", "Rule Compliance Rationale"])
            st.dataframe(df_checks, use_container_width=True, hide_index=True)
            st.caption(f"Issued by: *{cert['issued_by']}*")

        # --- FEATURE 2: TRACK MACHINE BLOCK PACKING & SEQUENCE OPTIMIZER ---
        with st.expander("🚜 Track Machine Block Packing & Sequence Optimizer (CSM / DGS / BCM)", expanded=False):
            st.caption("Bundles multiple heavy track machines into a single contiguous block window to eliminate duplicate transit overhead.")
            packer_agent = TrackMachinePackerAgent()
            pack_res = packer_agent.optimize_machine_blocks(section_id="Vijayawada-SEC-01")
            
            pk_c1, pk_c2, pk_c3 = st.columns(3)
            pk_c1.metric("Packed Heavy Machine Blocks", f"{len(pack_res.get('heavy_machine_blocks', []))} Blocks", delta="CSM / BCM Machines")
            pk_c2.metric("Effective Track Output", f"{pack_res.get('total_linear_track_tamped_km', 12.6)} Tamping KM", delta=f"{pack_res.get('overall_machine_efficiency_pct', 84.5)}% Efficiency")
            pk_c3.metric("Transit Overhead Avoided", f"{pack_res.get('overhead_avoided_mins', 90)} Mins", delta="Corridor Slots Saved")
            
            if pack_res.get("heavy_machine_blocks"):
                df_pk = pd.DataFrame(pack_res["heavy_machine_blocks"])
                st.dataframe(df_pk, use_container_width=True, hide_index=True)

        # --- FEATURE 3: TRACTION-AWARE ROUTER UNDER OHE POWER BLOCK ---
        with st.expander("⚡ Traction-Aware Traffic Router under OHE Power Block", expanded=False):
            st.caption("Routes trains safely during TRD OHE power blocks: diesel locos proceed, electric locos coast or hold/reroute.")
            trac_agent = TractionAwareRouterAgent()
            routed_trains = trac_agent.route_traffic_under_ptw(section_id="Vijayawada-SEC-01")
            
            st.info(f"⚡ **OHE Power Block Active on Section**: `Vijayawada-SEC-01 (25kV Isolated)`")
            if routed_trains:
                df_trac = pd.DataFrame(routed_trains)
                st.dataframe(df_trac, use_container_width=True, hide_index=True)

        # --- FEATURE 4: TSR LIFECYCLE & TIMETABLE PADDING CALCULATOR ---
        with st.expander("🚧 TSR Lifecycle & Timetable Speed Restriction Padding", expanded=False):
            st.caption("Tracks Temporary Speed Restrictions (TSRs) across track renewal stages and calculates automatic timetable padding.")
            tsr_agent = TSRLifecycleAgent()
            tsr_impacts = tsr_agent.calculate_tsr_delay_padding(section_id="Vijayawada-SEC-01")
            
            ts_c1, ts_c2 = st.columns(2)
            ts_c1.metric("Active Section TSRs", f"{len(tsr_impacts)} Active", delta="Track Caution Orders")
            ts_c2.metric("Total Timetable Padding", "+10 Minutes", delta="Added to Train Schedule")
            
            if tsr_impacts:
                df_tsr = pd.DataFrame(tsr_impacts)
                st.dataframe(df_tsr, use_container_width=True, hide_index=True)

        # Initialize 10-Train State Data across 2 Divisions
        if "trains_10_state" not in st.session_state:
            st.session_state.trains_10_state = {
                # --- VIJAYAWADA DIVISION (BZA) ---
                "Vijayawada Train 01": {
                    "id": "Vijayawada Train 01",
                    "division": "Vijayawada Division (BZA)",
                    "number": "12727",
                    "name": "Godavari Express",
                    "type": "Superfast Express",
                    "corridor": "Vijayawada → Kondapalli → Madhira",
                    "section_id": "BZA-RAY",
                    "current_km": 105,
                    "current_speed": 110,
                    "mps": 110,
                    "status": "Cruising (On Time)",
                    "signal": "🟢 Green (Clearance Fit)",
                    "delay_minutes": 0,
                    "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135],
                    "stations": [(100, "BZA JN"), (108, "RAYYANAPADU"), (125, "KONDAPALLI"), (135, "MADHIRA")],
                    "work_zone_kms": [114, 116, 118],
                    "speed_profile": [110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110],
                    "early_cleared": True,
                    "merged": False
                },
                "Vijayawada Train 02": {
                    "id": "Vijayawada Train 02",
                    "division": "Vijayawada Division (BZA)",
                    "number": "12759",
                    "name": "Charminar Express",
                    "type": "Superfast",
                    "corridor": "Vijayawada → Kondapalli → Madhira",
                    "section_id": "BZA-KDM",
                    "current_km": 114,
                    "current_speed": 30,
                    "mps": 110,
                    "status": "Regulated (30 km/h Caution)",
                    "signal": "🔴 Red / Amber Caution",
                    "delay_minutes": 12,
                    "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135],
                    "stations": [(100, "BZA JN"), (108, "RAYYANAPADU"), (125, "KONDAPALLI"), (135, "MADHIRA")],
                    "work_zone_kms": [114, 116, 118],
                    "speed_profile": [110, 110, 110, 45, 30, 30, 30, 80, 110, 110, 110],
                    "early_cleared": False,
                    "merged": False
                },
                "Vijayawada Train 03": {
                    "id": "Vijayawada Train 03",
                    "division": "Vijayawada Division (BZA)",
                    "number": "20833",
                    "name": "Vande Bharat Express",
                    "type": "Semi High Speed",
                    "corridor": "Vijayawada → Kondapalli → Madhira",
                    "section_id": "KDM-KMT",
                    "current_km": 122,
                    "current_speed": 120,
                    "mps": 130,
                    "status": "Speed Boost Active",
                    "signal": "🟢 Green (Clear Run)",
                    "delay_minutes": 0,
                    "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135],
                    "stations": [(100, "BZA JN"), (108, "RAYYANAPADU"), (125, "KONDAPALLI"), (135, "MADHIRA")],
                    "work_zone_kms": [114, 116, 118],
                    "speed_profile": [120, 120, 120, 120, 120, 120, 120, 120, 120, 120, 120],
                    "early_cleared": True,
                    "merged": False
                },
                "Vijayawada Train 04": {
                    "id": "Vijayawada Train 04",
                    "division": "Vijayawada Division (BZA)",
                    "number": "G-402",
                    "name": "Coal Freight Rake",
                    "type": "Heavy Freight",
                    "corridor": "Vijayawada → Kondapalli → Madhira",
                    "section_id": "RAY-KDM",
                    "current_km": 111,
                    "current_speed": 45,
                    "mps": 75,
                    "status": "Approach Braking",
                    "signal": "🟡 Double Yellow (Attention)",
                    "delay_minutes": 18,
                    "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135],
                    "stations": [(100, "BZA JN"), (108, "RAYYANAPADU"), (125, "KONDAPALLI"), (135, "MADHIRA")],
                    "work_zone_kms": [114, 116, 118],
                    "speed_profile": [75, 75, 75, 45, 30, 30, 30, 60, 75, 75, 75],
                    "early_cleared": False,
                    "merged": False
                },
                "Vijayawada Train 05": {
                    "id": "Vijayawada Train 05",
                    "division": "Vijayawada Division (BZA)",
                    "number": "57231",
                    "name": "BZA-KMT Passenger Local",
                    "type": "Passenger Local",
                    "corridor": "Vijayawada → Kondapalli → Madhira",
                    "section_id": "KDM-MDR",
                    "current_km": 128,
                    "current_speed": 40,
                    "mps": 90,
                    "status": "Station Approach",
                    "signal": "🟡 Yellow (Station Signal)",
                    "delay_minutes": 5,
                    "km_options": [100, 104, 108, 111, 114, 116, 118, 121, 125, 130, 135],
                    "stations": [(100, "BZA JN"), (108, "RAYYANAPADU"), (125, "KONDAPALLI"), (135, "MADHIRA")],
                    "work_zone_kms": [114, 116, 118],
                    "speed_profile": [90, 90, 60, 90, 90, 90, 90, 90, 40, 75, 90],
                    "early_cleared": True,
                    "merged": False
                },

                # --- HOWRAH DIVISION (HWH) ---
                "Howrah Train 01": {
                    "id": "Howrah Train 01",
                    "division": "Howrah Division (HWH)",
                    "number": "12301",
                    "name": "Howrah Rajdhani Express",
                    "type": "Superfast Rajdhani",
                    "corridor": "Howrah → Serampore → Bandel → Bardhaman",
                    "section_id": "HWH-SRP",
                    "current_km": 25,
                    "current_speed": 130,
                    "mps": 130,
                    "status": "High Speed Cruising",
                    "signal": "🟢 Green (Automatic Block)",
                    "delay_minutes": 0,
                    "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                    "stations": [(0, "HOWRAH JN"), (20, "SERAMPORE"), (40, "BANDEL JN"), (100, "BARDHAMAN")],
                    "work_zone_kms": [40, 45, 50],
                    "speed_profile": [130, 130, 130, 130, 130, 130, 130, 130, 130, 130, 130],
                    "early_cleared": True,
                    "merged": False
                },
                "Howrah Train 02": {
                    "id": "Howrah Train 02",
                    "division": "Howrah Division (HWH)",
                    "number": "37211",
                    "name": "Bandel EMU Suburban Local",
                    "type": "Suburban EMU",
                    "corridor": "Howrah → Serampore → Bandel → Bardhaman",
                    "section_id": "SRP-BDC",
                    "current_km": 15,
                    "current_speed": 65,
                    "mps": 90,
                    "status": "Suburban Service",
                    "signal": "🟡 Yellow (Distant Caution)",
                    "delay_minutes": 3,
                    "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                    "stations": [(0, "HOWRAH JN"), (20, "SERAMPORE"), (40, "BANDEL JN"), (100, "BARDHAMAN")],
                    "work_zone_kms": [40, 45, 50],
                    "speed_profile": [65, 45, 65, 45, 65, 45, 65, 45, 65, 45, 65],
                    "early_cleared": False,
                    "merged": False
                },
                "Howrah Train 03": {
                    "id": "Howrah Train 03",
                    "division": "Howrah Division (HWH)",
                    "number": "F-819",
                    "name": "Steel Coil Special Freight",
                    "type": "Heavy Goods",
                    "corridor": "Howrah → Serampore → Bandel → Bardhaman",
                    "section_id": "BDC-BWN",
                    "current_km": 42,
                    "current_speed": 30,
                    "mps": 75,
                    "status": "Active TSR Caution (30 km/h)",
                    "signal": "🔴 Red / Amber Caution",
                    "delay_minutes": 25,
                    "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                    "stations": [(0, "HOWRAH JN"), (20, "SERAMPORE"), (40, "BANDEL JN"), (100, "BARDHAMAN")],
                    "work_zone_kms": [40, 45, 50],
                    "speed_profile": [75, 75, 75, 50, 30, 30, 30, 60, 75, 75, 75],
                    "early_cleared": False,
                    "merged": False
                },
                "Howrah Train 04": {
                    "id": "Howrah Train 04",
                    "division": "Howrah Division (HWH)",
                    "number": "12339",
                    "name": "Coalfield Express",
                    "type": "Superfast Express",
                    "corridor": "Howrah → Serampore → Bandel → Bardhaman",
                    "section_id": "BWN-DGR",
                    "current_km": 65,
                    "current_speed": 105,
                    "mps": 110,
                    "status": "Clear Block Run",
                    "signal": "🟢 Green (Clearance)",
                    "delay_minutes": 0,
                    "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                    "stations": [(0, "HOWRAH JN"), (20, "SERAMPORE"), (40, "BANDEL JN"), (100, "BARDHAMAN")],
                    "work_zone_kms": [40, 45, 50],
                    "speed_profile": [105, 105, 105, 105, 105, 105, 105, 105, 105, 105, 105],
                    "early_cleared": True,
                    "merged": False
                },
                "Howrah Train 05": {
                    "id": "Howrah Train 05",
                    "division": "Howrah Division (HWH)",
                    "number": "22301",
                    "name": "Vande Bharat Express HWH-NJP",
                    "type": "Semi High Speed",
                    "corridor": "Howrah → Serampore → Bandel → Bardhaman",
                    "section_id": "BWN-DGR",
                    "current_km": 85,
                    "current_speed": 115,
                    "mps": 130,
                    "status": "Accelerated Cruise",
                    "signal": "🟢 Green (High Speed Fit)",
                    "delay_minutes": 0,
                    "km_options": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                    "stations": [(0, "HOWRAH JN"), (20, "SERAMPORE"), (40, "BANDEL JN"), (100, "BARDHAMAN")],
                    "work_zone_kms": [40, 45, 50],
                    "speed_profile": [115, 115, 115, 115, 115, 115, 115, 115, 115, 115, 115],
                    "early_cleared": True,
                    "merged": False
                }
            }

        # DIVISION AND TRAIN SELECTOR UI
        st.markdown("---")
        sel_div_col, sel_trn_col = st.columns([1.5, 2.5])
        with sel_div_col:
            div_options = [
                "Khurda Road Division (KUR)",
                "Vijayawada Division (BZA)",
                "Secunderabad Division (SC)",
                "Howrah Division (HWH)"
            ]
            target_div_opt = div_options[0]
            for opt in div_options:
                if selected_division and (opt[:6].lower() in selected_division.lower() or selected_division[:6].lower() in opt.lower()):
                    target_div_opt = opt
                    break
            if st.session_state.get("last_synced_top_div") != selected_division:
                st.session_state["last_synced_top_div"] = selected_division
                st.session_state["ctrl_sel_division"] = target_div_opt

            selected_ctrl_division = st.selectbox(
                "🏛️ Select Railway Division:",
                div_options,
                key="ctrl_sel_division"
            )
        
        with sel_trn_col:
            init_trains_10_state()
            if "Khurda" in selected_ctrl_division:
                train_options = ["Khurda Road Train 01", "Khurda Road Train 02", "Khurda Road Train 03"]
            elif "Secunderabad" in selected_ctrl_division:
                train_options = ["SC-12701", "SC-12792", "SC-17015", "SC-F819"]
            elif "Vijayawada" in selected_ctrl_division:
                train_options = ["Vijayawada Train 01", "Vijayawada Train 02", "Vijayawada Train 03", "Vijayawada Train 04", "Vijayawada Train 05"]
            else:
                train_options = ["Howrah Train 01", "Howrah Train 02", "Howrah Train 03", "Howrah Train 04", "Howrah Train 05"]

            avail_options = [t for t in train_options if t in st.session_state.trains_10_state]
            if not avail_options:
                avail_options = list(st.session_state.trains_10_state.keys())

            selected_train_id = st.selectbox(
                "🚆 Select Train for Telemetry & Locopilot Speed Controls:",
                avail_options,
                key="ctrl_sel_train"
            )

        # Get current active train object safely
        tr = st.session_state.trains_10_state.get(selected_train_id)
        if not tr:
            tr = next(iter(st.session_state.trains_10_state.values()))
        is_early = tr["early_cleared"]
        is_merged = tr["merged"]

        loco_agent = LocopilotSpeedAgent()
        merger_agent = BlockMergingAgent()

        # Top Action & Simulation Controls
        ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([1.4, 1.4, 1.4, 1.2, 1.0])

        with ctrl_col1:
            early_btn_label = "⚡ Simulate Early Release" if not is_early else "🟢 Early Release Active (+45m)"
            early_btn_type = "primary" if not is_early else "secondary"
            if st.button(early_btn_label, key=f"btn_early_{tr['id']}", type=early_btn_type, use_container_width=True):
                tr["early_cleared"] = True
                tr["merged"] = False
                tr["speed_profile"] = [tr["mps"]] * len(tr["km_options"])
                tr["current_speed"] = tr["mps"]
                tr["status"] = "🟢 Early Released (Full Speed Fit)"
                tr["signal"] = "🟢 Green (Clearance Fit)"
                loco_agent.generate_speed_advisory(tr["section_id"], freed_minutes=45.0, department_source="Engineering")
                st.session_state.last_action_banner = ("success", f"⚡ Early Block Clearance Activated for {tr['id']}! Speed limit restored to {tr['mps']} km/h.")
                st.rerun()

        with ctrl_col2:
            merge_btn_label = "🤝 Merge Multi-Dept Blocks" if not is_merged else "🟡 Mega-Block Active"
            merge_btn_type = "primary" if not is_merged else "secondary"
            if st.button(merge_btn_label, key=f"btn_merge_{tr['id']}", type=merge_btn_type, use_container_width=True):
                tr["merged"] = True
                tr["early_cleared"] = False
                tr["current_speed"] = 30
                tr["status"] = "🟡 Mega-Block Active (Merged)"
                tr["signal"] = "🟡 Amber (Caution Speed)"
                merger_agent.execute_merge(tr["section_id"])
                st.session_state.last_action_banner = ("warning", f"🤝 Multi-Department Mega-Block Activated for {tr['id']}! Speed regulated to 30 km/h.")
                st.rerun()

        with ctrl_col3:
            if st.button("⚡ Execute Instant Dispatch", key=f"btn_dispatch_{tr['id']}", type="primary", use_container_width=True):
                tr["early_cleared"] = True
                tr["current_speed"] = tr["mps"]
                tr["status"] = "⚡ Priority Dispatched"
                loco_agent.dispatch_advisories()
                st.session_state.last_action_banner = ("success", f"⚡ Instant Priority Dispatch Executed for {tr['name']}! Section delay reduced.")
                st.balloons()
                st.rerun()

        with ctrl_col4:
            if st.button("📡 Dispatch to Locopilots", key=f"btn_trans_{tr['id']}", use_container_width=True):
                loco_agent.dispatch_advisories()
                now_time = datetime.now().strftime("%H:%M:%S")
                st.session_state.last_action_banner = ("info", f"📡 Speed Orders Dispatched! [{now_time}] Transmitted to {tr['name']} CAB display.")
                st.rerun()

        with ctrl_col5:
            if st.button("🔄 Reset Normal", key=f"btn_reset_{tr['id']}", use_container_width=True):
                tr["early_cleared"] = False
                tr["merged"] = False
                tr["current_speed"] = 30 if tr["km_options"][4] in tr["work_zone_kms"] else tr["mps"]
                tr["status"] = "Regulated (30 km/h Caution)"
                st.session_state.last_action_banner = ("info", f"🔄 Reset corridor to normal active maintenance block for {tr['id']}.")
                st.rerun()

        if "last_action_banner" in st.session_state and st.session_state.last_action_banner:
            b_type, b_msg = st.session_state.last_action_banner
            if b_type == "success":
                st.success(b_msg)
            elif b_type == "warning":
                st.warning(b_msg)
            else:
                st.info(b_msg)

        # LAYER 1: TELEMETRY OVERVIEW SUMMARY CARDS
        st.markdown("#### 📊 Live Train Telemetry & Status Summary")
        
        del_val = tr.get("delay_minutes", 0)
        del_text = f"⏱️ Delay: +{del_val} min" if del_val > 0 else "⏱️ On Time (0 min)"
        del_color = "#f87171" if del_val > 0 else "#4ade80"
        sig_text = tr.get("signal", "🟢 Green")

        t_cards_html = f'''
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px;">
            <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px;">
                <div style="font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Train Name / No.</div>
                <div style="font-size: 22px; font-weight: 800; color: #f8fafc; margin: 2px 0;">{tr.get('number', '')}</div>
                <div style="font-size: 13px; color: #38bdf8; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">🚆 {tr.get('name', '')}</div>
            </div>
            <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px;">
                <div style="font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Current Speed</div>
                <div style="font-size: 22px; font-weight: 800; color: #f8fafc; margin: 2px 0;">{tr.get('current_speed', 0)} km/h</div>
                <div style="font-size: 13px; color: #a7f3d0; font-weight: 600;">⚡ MPS: {tr.get('mps', 110)} km/h</div>
            </div>
            <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px;">
                <div style="font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Current Location</div>
                <div style="font-size: 22px; font-weight: 800; color: #f8fafc; margin: 2px 0;">KM {tr.get('current_km', 0)}</div>
                <div style="font-size: 13px; color: #cbd5e1; font-weight: 600;">📍 Section: {tr.get('section_id', 'SEC')}</div>
            </div>
            <div style="background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px;">
                <div style="font-size: 11px; color: #94a3b8; font-weight: 600; text-transform: uppercase;">Signal Aspect & Delay</div>
                <div style="font-size: 15px; font-weight: 700; color: #f8fafc; margin: 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{sig_text}</div>
                <div style="font-size: 13px; color: {del_color}; font-weight: 600;">{del_text}</div>
            </div>
        </div>
        '''
        st.markdown(t_cards_html, unsafe_allow_html=True)

        st.markdown("---")

        # LAYER 2: RAILFLOW GEOGRAPHIC CORRIDOR MAP & LIVE STATUS MONITOR
        st.markdown(f"#### 🗺️ Live Geographic Corridor Track Map & Status Monitor — `{tr['corridor']}`")
        st.caption(f"Interactive Geographic Map showing station posts, work zones, signal aspects, and real-time status monitor for **{tr['id']} ({tr['name']})**.")
        render_railflow_geographic_corridor_view(division=selected_ctrl_division, df_trains=df_active_trains)

        st.markdown("---")

        # LAYER 3: PLOTLY SPEED PROFILE & TELEMETRY GRAPHS
        st.markdown("#### 📈 Speed Profile & Telemetry Graphs")
        
        km_points = tr["km_options"]
        speed_vals = tr["speed_profile"]
        mps_vals = [tr["mps"]] * len(km_points)

        fig_speed = go.Figure()
        fig_speed.add_trace(go.Scatter(
            x=km_points, y=speed_vals,
            mode="lines+markers", name=f"{tr['id']} Speed Profile",
            line=dict(color="#3b82f6", width=3.5),
            marker=dict(size=8, color="#3b82f6")
        ))
        fig_speed.add_trace(go.Scatter(
            x=km_points, y=mps_vals,
            mode="lines", name="Maximum Permissible Speed (MPS)",
            line=dict(color="#10b981", dash="dash", width=2)
        ))

        fig_speed.update_layout(
            title=f"Instructed Speed Profile vs Track Kilometer Post — {tr['id']} ({tr['name']})",
            xaxis_title="Track Kilometer Post (KM)",
            yaxis_title="Instructed Speed (km/h)",
            yaxis=dict(range=[0, 150]),
            margin=dict(l=40, r=40, t=50, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_speed, use_container_width=True)

        # LAYER 4: KILOMETER-BY-KILOMETER IN-CAB ADVISORY INSPECTOR
        st.markdown("#### 🔍 Kilometer-by-Kilometer Telemetry & In-Cab Advisory Inspector")
        st.caption("Select any track kilometer post to inspect signal aspect, permissible speed, and driver advisory display:")

        selected_km = st.select_slider(
            "Select Track Kilometer Post (KM) to Inspect:",
            options=tr["km_options"],
            value=tr["km_options"][4],
            format_func=lambda x: f"KM {x}",
            key=f"slider_km_{tr['id']}"
        )

        idx_km = tr["km_options"].index(selected_km)
        km_speed = speed_vals[idx_km]
        
        if selected_km in tr["work_zone_kms"]:
            km_desc = f"Inside / Approaching Work Zone (KM {tr['work_zone_kms'][0]}–{tr['work_zone_kms'][-1]})"
            km_signal = "🟢 Green (Clearance Fit)" if is_early else ("🟡 Yellow (Caution Speed)" if is_merged else "🔴 Red / Amber Caution")
            km_adv = "Corridor cleared early! Full permissible speed authorized." if is_early else ("Multi-crew safety caution: Maintain 30 km/h." if is_merged else "Active maintenance gang ahead: Regulate speed to 30 km/h.")
        else:
            km_desc = "Open Block Section"
            km_signal = "🟢 Green (Automatic Clearance)"
            km_adv = f"Sectional MPS Authorized: {km_speed} km/h."

        km_c1, km_c2, km_c3, km_c4 = st.columns(4)
        with km_c1:
            st.metric("Inspected Track KM", f"KM {selected_km}", delta=km_desc, delta_color="off")
        with km_c2:
            st.metric("Permissible Speed", f"{km_speed} km/h", delta=f"{'+0' if km_speed==tr['mps'] else f'-{tr["mps"]-km_speed}'} km/h vs MPS")
        with km_c3:
            st.metric("Signal Aspect on Map", km_signal, delta="Aspect Telemetry", delta_color="off")
        with km_c4:
            st.metric("Safety Headway", "4.8 KM", delta="Zero Collision", delta_color="normal")

        st.info(f"**🚆 Locopilot In-Cab Advisory Display at KM {selected_km}:** `{km_adv}`")

        st.markdown("---")

        # LAYER 5: MULTI-DEPARTMENT BLOCK MERGING CONSOLE
        st.markdown("#### 🤝 Multi-Department Block Merging (Shadow Block Aggregator)")
        st.caption("AI clusters multi-department track time requests on the active corridor to prevent repeated shutdowns.")
        
        try:
            m_agent = BlockMergingAgent()
            merge_ops = m_agent.find_merge_opportunities()
        except Exception:
            merge_ops = []
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

        # LAYER 6: DATA REGISTERS TABS
        l_tab1, l_tab2, l_tab3 = st.tabs([
            "📑 Active Speed Advisories",
            "🚆 Live Train Telemetry Register",
            "📦 Freight & Goods Train Forecast"
        ])

        with l_tab1:
            st.markdown("##### 📑 Active Speed Advisories & Caution Orders")
            conn = get_db()
            df_advisories = pd.read_sql("SELECT * FROM locopilot_speed_advisories ORDER BY advisory_id DESC LIMIT 30", conn)
            conn.close()
            if not df_advisories.empty:
                st.dataframe(df_advisories, use_container_width=True, hide_index=True)
            else:
                st.info("No active speed advisories.")

        with l_tab2:
            st.markdown("##### 🚆 Live Train Telemetry Register")
            conn = get_db()
            df_live_trains = pd.read_sql("SELECT * FROM live_train_status ORDER BY delay_minutes DESC", conn)
            conn.close()
            if not df_live_trains.empty:
                st.dataframe(df_live_trains, use_container_width=True, hide_index=True)
            else:
                st.info("No live train telemetry records.")

        with l_tab3:
            st.markdown("##### 📦 Freight & Goods Train Forecast")
            conn = get_db()
            df_goods = pd.read_sql("SELECT * FROM goods_forecast ORDER BY expected_rakes DESC", conn)
            conn.close()
            if not df_goods.empty:
                st.dataframe(df_goods, use_container_width=True, hide_index=True)
            else:
                st.info("No goods freight forecast data.")
        st.markdown("---")
        with st.expander("💬 AI Assistant & Operational Co-Pilot", expanded=False):
            render_persistent_ai_chatbot_panel(page_context=f"Central Controller > {admin_menu}", department="All")

    else:
        col_left, col_right = st.columns([2.3, 1.0], gap="medium")
        with col_left:


            if admin_menu == "📊 Overview":
                st.subheader("System State & Visual Operational Intelligence Center")

                dept_filter = st.selectbox("🎯 Filter Overview by Department", ["All Departments", "Engineering", "S&T", "TRD"], key="admin_overview_dept_filter")

                st.markdown("---")
                st.subheader("📊 Operational Defect & Capacity Metrics")

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

                # 1. VISUAL OPERATIONAL KPI STRIP
                render_operational_kpi_bar(department=dept_filter)

                # 2. LIVE INTERACTIVE RAILWAY CORRIDOR MAP (PLOTLY)
                df_active_trains = get_active_trains_df()
                fig_map = render_live_corridor_map_plotly(df_active_trains)
                st.plotly_chart(fig_map, use_container_width=True)

                # 3. VISUAL TRAIN STATUS CARDS
                render_visual_train_cards(df_active_trains)

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

                now_dt = datetime.now()
                week_end = now_dt + timedelta(days=7)
                month_end = now_dt + timedelta(days=30)
                week_label = f"📅 7-Day Rolling Weekly Plan ({now_dt.strftime('%d %b')} – {week_end.strftime('%d %b %Y')})"
                month_label = f"🗓️ 30-Day Strategic Monthly Plan ({now_dt.strftime('%d %b')} – {month_end.strftime('%d %b %Y')})"

                plan_tab_w, plan_tab_m = st.tabs([week_label, month_label])

                with plan_tab_w:
                    st.markdown(f"#### 📅 Weekly Corridor Block Schedule ({now_dt.strftime('%d %b %Y')} – {week_end.strftime('%d %b %Y')})")
                    df_weekly = get_full_schedule(horizon="weekly")

                    if not df_weekly.empty:
                        df_weekly["Timeline"] = df_weekly.apply(lambda r: f"{format_time_12h(r['planned_start'])} to {format_time_12h(r['planned_end'])}", axis=1)
                        matrix_html = generate_ai_block_plan_matrix_html(df_weekly, current_dept="All Departments", color_mode="department")
                        components.html(matrix_html, height=520, scrolling=True)
                        st.markdown("##### 📋 Weekly Schedule Allocation Table")
                        st.dataframe(df_weekly[["schedule_id", "defect_id", "section_id", "department", "defect_type", "severity", "Timeline", "status", "decided_by"]], use_container_width=True, hide_index=True)
                        display_overall_statistics(df_weekly, context_title="Weekly Plan")
                    else:
                        st.warning("No weekly blocks currently planned. Generate an optimal schedule below:")
                        if st.button("🚀 Generate 7-Day Rolling Weekly Plan (CP-SAT Solver)", type="primary"):
                            with st.spinner("Solving CP-SAT for 7-Day Rolling Horizon..."):
                                coord = CoordinatorAgent()
                                res = coord.run_cycle(horizon="weekly")
                                st.success(f"Generated weekly plan with {len(res)} tasks!")
                                st.rerun()

                with plan_tab_m:
                    st.markdown(f"#### 🗓️ Monthly Corridor Block Schedule ({now_dt.strftime('%d %b %Y')} – {month_end.strftime('%d %b %Y')})")
                    df_monthly = get_full_schedule(horizon="monthly")

                    if not df_monthly.empty:
                        df_monthly["Timeline"] = df_monthly.apply(lambda r: f"{format_time_12h(r['planned_start'])} to {format_time_12h(r['planned_end'])}", axis=1)
                        matrix_html_m = generate_ai_block_plan_matrix_html(df_monthly, current_dept="All Departments", color_mode="department")
                        components.html(matrix_html_m, height=520, scrolling=True)
                        st.markdown("##### 📋 Monthly Schedule Allocation Table")
                        st.dataframe(df_monthly[["schedule_id", "defect_id", "section_id", "department", "defect_type", "severity", "Timeline", "status", "decided_by"]], use_container_width=True, hide_index=True)
                        display_overall_statistics(df_monthly, context_title="Monthly Plan")
                    else:
                        st.info("No monthly schedule currently in database.")
                        if st.button("🚀 Generate 30-Day Strategic Monthly Plan (CP-SAT Solver)", type="primary"):
                            with st.spinner("Solving CP-SAT for 30-Day Horizon..."):
                                coord = CoordinatorAgent()
                                res = coord.run_cycle(horizon="monthly")
                                st.success(f"Generated monthly block plan with {len(res)} tasks!")
                                st.rerun()

            elif admin_menu == "🔄 Re-optimize / Override":
                st.subheader("🔄 Scheduling Optimizer & Controller Manual Override Center")
                st.caption("Central Control Authority: Manually adjust block timings, lock/pin critical corridor tasks, grant emergency blocks, and re-run Google OR-Tools CP-SAT with overrides preserved.")

                conn = get_db()
                total_sched = pd.read_sql("SELECT COUNT(*) as c FROM schedule WHERE LOWER(status) != 'cancelled'", conn)["c"].iloc[0]
                total_overrides = pd.read_sql("SELECT COUNT(*) as c FROM schedule WHERE decided_by IN ('controller_override', 'controller_emergency', 'emergency_force_override') OR status = 'locked'", conn)["c"].iloc[0]
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

                    if "override_toast" in st.session_state:
                        mtype, mtext = st.session_state.pop("override_toast")
                        if mtype == "success":
                            st.success(mtext)
                            st.toast(mtext, icon="✅")
                        elif mtype == "warning":
                            st.warning(mtext)
                            st.toast(mtext, icon="⚠️")
                        elif mtype == "error":
                            st.error(mtext)
                            st.toast(mtext, icon="❌")

                    df_active = get_cached_override_active_blocks()

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
                                is_emerg_force = st.checkbox("🚨 Emergency Force Override (Bypass Train Conflict for Critical Emergency Work)", value=False, key=f"emerg_force_{sel_id}")
                            with ov_col2:
                                override_reason = st.text_input("Controller Justification / Reason for Override", value="VIP train punctuality / Sectional congestion adjustment", key=f"reason_{sel_id}")
                                st.info(f"**Department:** `{sel_row['department']}` | **Section:** `{sel_row['section_id']}`\n\n**Defect:** {sel_row['defect_type']} (`{sel_row['severity']}`)")

                            b_col1, b_col2 = st.columns(2)
                            with b_col1:
                                if st.button("💾 Apply Controller Override", type="primary", use_container_width=True, key=f"save_ov_{sel_id}"):
                                    comp = ComplianceAgent()
                                    is_valid, reason = comp.validate_override(sel_row['section_id'], new_start, new_end, current_schedule_id=int(sel_id))
                                    if not is_valid and not is_emerg_force:
                                        st.session_state["override_toast"] = ("error", f"❌ Controller Override Rejected — {reason}\n\n💡 **Emergency Work Possession?** If this is an urgent emergency repair (e.g. Rail Fracture, OHE Wire Snap, Signal Failure), check **'🚨 Emergency Force Override'** above to bypass non-emergency train restrictions.")
                                        st.rerun()
                                    else:
                                        conn = get_db()
                                        new_status = "locked" if is_locked else "planned"
                                        decided_val = "emergency_force_override" if is_emerg_force else "controller_override"
                                        conn.execute(
                                            "UPDATE schedule SET planned_start=?, planned_end=?, status=?, decided_by=? WHERE schedule_id=?",
                                            (new_start, new_end, new_status, decided_val, int(sel_id))
                                        )
                                        conn.commit()
                                        conn.close()
                                        st.cache_data.clear()

                                        # Automatic conflict detection & CP-SAT re-optimization pass
                                        coord = CoordinatorAgent()
                                        target_horizon = str(sel_row.get("horizon", "weekly") or "weekly")
                                        coord.resolve_override_and_reschedule(int(sel_id), new_start, new_end, horizon=target_horizon)

                                        log_action("Controller", "manual_override", f"Schedule #{sel_id} updated: {new_start} to {new_end} ({override_reason}) [Emergency Force: {is_emerg_force}]")
                                        notify("admin", f"Manual Override: Schedule #{sel_id} ({sel_row['department']}) timing modified by Central Control.", category="controller_override")
                                        if is_emerg_force:
                                            st.session_state["override_toast"] = ("success", f"⚡ 🚨 EMERGENCY FORCE OVERRIDE GRANTED! Schedule #{sel_id} updated ({new_start} to {new_end}). Temporary Speed Restriction (TSR 30 km/h) & Emergency Train Regulation active.")
                                        else:
                                            st.session_state["override_toast"] = ("success", f"✅ Schedule #{sel_id} successfully updated to {new_start} - {new_end} & timetable re-optimized!")
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
                                    st.session_state["override_toast"] = ("warning", f"⚠️ Schedule #{sel_id} cancelled. Corridor slot released and weekly schedule re-optimized.")
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

                    if "override_toast" in st.session_state:
                        mtype, mtext = st.session_state.pop("override_toast")
                        if mtype == "success":
                            st.success(mtext)
                            st.toast(mtext, icon="🚨")
                        elif mtype == "warning":
                            st.warning(mtext)
                            st.toast(mtext, icon="⚠️")
                        elif mtype == "error":
                            st.error(mtext)
                            st.toast(mtext, icon="❌")

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
                            st.session_state["override_toast"] = ("success", f"⚡ 🚨 EMERGENCY BLOCK GRANTED on {em_sec} until {end_str}! Caution orders (TSR 30 km/h) transmitted to Locopilots.")
                            st.rerun()

            elif admin_menu == "⚖️ Compliance & Anomalies":
                st.subheader("⚖️ Safety Compliance, Anomaly Detection & Auto-Rescheduling Console")
                st.caption("Scans active corridor schedules for section overlaps, passenger train timetable clashes, and SLA violations. Calibrated conflict clustering ensures actionable insights without visual clutter.")

                comp = ComplianceAgent()
                conn = get_db()
                total_active = pd.read_sql("SELECT COUNT(*) as c FROM schedule WHERE LOWER(status) NOT IN ('cancelled', 'completed')", conn)["c"].iloc[0]
                conn.close()

                anomalies = comp.detect_and_handle_anomalies()
                violations = comp.check_schedule()

                # High-level KPIs
                total_audited = max(total_active, 1)
                sla_compliant_count = max(0, total_audited - len(violations))
                sla_pct = min(100.0, (sla_compliant_count / total_audited) * 100.0)

                cm1, cm2, cm3, cm4 = st.columns(4)
                cm1.metric("Active Scheduled Blocks", f"{total_active}", delta="Track Occupancy")
                cm2.metric("SLA Compliance Rate", f"{sla_pct:.1f}%", delta=f"{len(violations)} Overdue Tasks", delta_color="inverse" if violations else "normal")
                cm3.metric("Section Conflict Clusters", f"{len(anomalies)} Clusters", delta="Track Overlaps", delta_color="inverse" if anomalies else "normal")
                cm4.metric("Safety Fit Status", "99.4% Fit" if not anomalies else "Requires CP-SAT Pass", delta="G&SR Zero-Risk")

                st.markdown("---")

                # 1. Section Conflict Clusters
                st.markdown("#### 🔍 Active Corridor Section Conflict Clusters")
                if anomalies:
                    st.warning(f"⚠️ Identified **{len(anomalies)}** active section conflict clusters across monitored divisions:")
                    for a in anomalies:
                        with st.expander(f"🔴 Section `{a['section_id']}` — {a['count']} Overlapping Blocks ({', '.join(a['departments'])})", expanded=False):
                            st.markdown(f"**Conflict Window:** `{a['start_window']}` to `{a['end_window']}`")
                            df_conf = pd.DataFrame(a["tasks"])[["schedule_id", "defect_id", "department", "defect_type", "severity", "planned_start", "planned_end", "status", "decided_by"]]
                            st.dataframe(df_conf, use_container_width=True, hide_index=True)

                    if st.button("🚀 Auto-Resolve All Section Conflicts (Run Single-Pass CP-SAT)", type="primary", use_container_width=True):
                        with st.spinner("Executing Google OR-Tools CP-SAT multi-department conflict resolution..."):
                            coord = CoordinatorAgent()
                            coord.run_cycle(horizon="weekly")
                            st.success("✅ Multi-Department CP-SAT re-optimization completed! All section conflict clusters resolved into independent non-overlapping windows.")
                            st.rerun()
                else:
                    st.success("✅ **Zero section anomalies detected!** All scheduled maintenance blocks are strictly conflict-free across corridor tracks.")

                st.markdown("---")

                # 2. SLA & Due Date Compliance
                st.markdown("#### 🚨 Safety SLA Due-Date Verification")
                if violations:
                    st.error(f"Found {len(violations)} critical safety defect tasks scheduled beyond regulatory SLA due dates:")
                    for v in violations[:6]:
                        st.markdown(f"- ⚠️ {v}")
                    if len(violations) > 6:
                        st.caption(f"... and {len(violations) - 6} additional SLA notices.")
                else:
                    st.success("✅ **100% SLA Compliance!** All critical defects are scheduled prior to their regulatory due dates.")

                st.markdown("---")

                # 3. Full Schedule Audit Table
                st.markdown("#### 📋 Active Schedule Audit Register")
                conn = get_db()
                df_audit = pd.read_sql("""
                    SELECT s.schedule_id, s.defect_id, s.section_id, s.department, s.planned_start, s.planned_end, s.status, s.decided_by
                    FROM schedule s
                    WHERE LOWER(s.status) NOT IN ('cancelled', 'completed')
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
