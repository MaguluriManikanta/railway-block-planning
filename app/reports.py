"""
Report generation — Automatic week-by-week and month-by-month analysis reports as downloadable PDFs.
"""

import os
from datetime import datetime
from fpdf import FPDF
import pandas as pd

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_report(schedule_df: pd.DataFrame) -> str:
    """General block planning summary report."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Block Planning Report - Indian Railways", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.ln(5)

    if schedule_df.empty:
        pdf.cell(0, 8, "No scheduled tasks found.", ln=True)
    else:
        counts = schedule_df["status"].value_counts()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Execution Summary", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for status, count in counts.items():
            pdf.cell(0, 6, f"  {status.capitalize()}: {count} tasks", ln=True)

        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Task Details", ln=True)
        pdf.set_font("Helvetica", "", 8)
        for _, row in schedule_df.head(60).iterrows():
            start = row.get('planned_start', 'N/A')
            end = row.get('planned_end', 'N/A')
            line = f"{row.get('defect_id', 'N/A')} | {row.get('department', 'N/A')} | {row.get('section_id', 'N/A')} | {start} to {end} | Status: {row.get('status', 'N/A')}"
            pdf.cell(0, 5, line, ln=True)

    filename = f"block_plan_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = os.path.join(OUTPUT_DIR, filename)
    pdf.output(path)
    return path


def generate_periodic_report(df: pd.DataFrame, period_type="Weekly", period_label="Week 1 (Sep 2026)", department="All") -> str:
    """
    Automatic generation of reports (week by week, month by month) with
    completion analysis and performance metrics.
    """
    pdf = FPDF()
    pdf.add_page()
    
    # Title & Header
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Indian Railways - {period_type} Block Analysis Report", ln=True)
    pdf.set_font("Helvetica", "B", 12)
    dept_label = department if department and department != "All" else "All Departments (Engineering, S&T, TRD)"
    pdf.cell(0, 8, f"Period: {period_label} | Scope: {dept_label}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(4)

    if df.empty:
        pdf.cell(0, 8, "No records found for this period.", ln=True)
    else:
        total_tasks = len(df)
        completed_tasks = len(df[df["status"].str.lower() == "completed"])
        pending_tasks = total_tasks - completed_tasks
        comp_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        # Performance KPI Block
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"{period_type} Performance Metrics", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"  * Total Maintenance Tasks Monitored: {total_tasks}", ln=True)
        pdf.cell(0, 6, f"  * Tasks Successfully Completed: {completed_tasks} ({comp_rate:.1f}%)", ln=True)
        pdf.cell(0, 6, f"  * Tasks Pending / Scheduled: {pending_tasks}", ln=True)
        
        # Severity summary
        if "severity" in df.columns:
            sev_counts = df["severity"].value_counts().to_dict()
            pdf.cell(0, 6, f"  * Defect Breakdown: Critical: {sev_counts.get('Critical', 0)}, High: {sev_counts.get('High', 0)}, Medium: {sev_counts.get('Medium', 0)}, Low: {sev_counts.get('Low', 0)}", ln=True)
        
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"{period_type} Detailed Task Log (Sample)", ln=True)
        pdf.set_font("Helvetica", "", 8)

        for _, row in df.head(55).iterrows():
            d_id = row.get("defect_id", "N/A")
            dept = row.get("department", "N/A")
            sec = row.get("section_id", "N/A")
            status = row.get("status", "Pending")
            dur = row.get("estimated_duration_hours", "N/A")
            win = f"{str(row.get('planned_start', ''))[11:16]} - {str(row.get('planned_end', ''))[11:16]}" if row.get('planned_start') else "Pending"
            line = f"{d_id} | {dept:11} | {sec:18} | Dur: {dur}h | Window: {win} | Status: {status}"
            pdf.cell(0, 5, line, ln=True)

    clean_period = period_label.replace(" ", "_").replace("(", "").replace(")", "").replace(":", "")
    filename = f"{period_type.lower()}_report_{clean_period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = os.path.join(OUTPUT_DIR, filename)
    pdf.output(path)
    return path
