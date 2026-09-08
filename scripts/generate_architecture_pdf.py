"""
Generate Complete System Architecture PDF with Diagrams for Indian Railways Block Planning System.
Uses Pillow (PIL) for high-resolution diagram rendering and FPDF2 for PDF compilation.
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
PDF_PATH = os.path.join(OUTPUT_DIR, "Indian_Railways_Block_Planning_Architecture.pdf")
IMG_DIR = os.path.join(BASE_DIR, "scratch_arch_diagrams")
os.makedirs(IMG_DIR, exist_ok=True)

# Helper to get font
def get_font(size=14, bold=False):
    try:
        # Default Windows font
        font_path = "C:\\Windows\\Fonts\\arial.ttf" if not bold else "C:\\Windows\\Fonts\\arialbd.ttf"
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    except Exception:
        pass
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 1. GENERATE DIAGRAM 1: High-Level System Architecture
# ---------------------------------------------------------------------------
def generate_diagram1():
    w, h = 1600, 900
    img = Image.new('RGB', (w, h), '#ffffff')
    draw = ImageDraw.Draw(img)

    f_title = get_font(24, bold=True)
    f_box_t = get_font(18, bold=True)
    f_box_b = get_font(14, bold=False)

    # Header
    draw.text((w//2, 40), "INDIAN RAILWAYS AUTOMATIC BLOCK PLANNING SYSTEM ARCHITECTURE", 
              fill='#0f172a', font=f_title, anchor='mm')

    # Draw Boxes
    def draw_card(x, y, bw, bh, title, lines, color_bg, color_border):
        draw.rounded_rectangle([x, y, x + bw, y + bh], radius=16, fill=color_bg, outline=color_border, width=3)
        draw.text((x + bw//2, y + 25), title, fill='#0f172a', font=f_box_t, anchor='mm')
        
        cur_y = y + 60
        for line in lines:
            draw.text((x + 20, cur_y), line, fill='#334155', font=f_box_b)
            cur_y += 26

    # Tier 1: Data Layer
    draw_card(80, 140, 360, 260, "1. DATA INTEGRATION LAYER", [
        "• TMS (Track Management)",
        "• SMMS (Signals Management)",
        "• TDMS (Traction / OHE)",
        "• Train Time Table (2,000)",
        "• Goods Trains Forecast",
        "• SQLite3 Database Store"
    ], '#eff6ff', '#3b82f6')

    # Tier 2: AI/ML Engine
    draw_card(480, 140, 360, 260, "2. AI/ML ENGINE", [
        "• Math Priority Scoring Formula",
        "• RF Failure Risk Predictor",
        "• Isolation Forest Anomaly ML",
        "• Overdue Lag Days Calculator",
        "• Dynamic SLA Risk Weights"
    ], '#f5f3ff', '#8b5cf6')

    # Tier 3: Optimization & Multi-Agent
    draw_card(880, 140, 640, 260, "3. OPTIMIZATION & GOVERNANCE AGENTS", [
        "• Google OR-Tools CP-SAT Constraint Solver",
        "• Shadow Block Clustering (Engineering + S&T + TRD)",
        "• Multi-Horizon Planner (7-Day Weekly & 30-Day Monthly)",
        "• 13 Autonomous Governance Agents (Traffic, Compliance, etc.)",
        "• 3 Auto-Approval Risk Tiers (Replanning Agent)"
    ], '#ecfdf5', '#10b981')

    # Tier 4: Presentation & UI Layer
    draw_card(240, 480, 1120, 340, "4. PRESENTATION & INTERACTIVE USER INTERFACE LAYER", [
        "• Streamlit Dual-Panel Workspace (My Schedule, Open Tasks, Completed History, Weekly & Monthly Reports)",
        "• Interactive Plotly Zoomable Corridor Timeline Graph (Permanent X/Y Axis Labels & Data Visibility)",
        "• Dedicated AI Assistant Panel (Groq API Qwen 27B + Speech Recognition 🎤 + Speech Synthesis 🔊)",
        "• Single Unified Prompt Box (Combined Speech-to-Text & Send Trigger)",
        "• Automated Periodic PDF Report Generator (Official Weekly & Monthly Performance Summaries)",
        "• Role-Based Access Control (Engineering, S&T, TRD, Admin) & BCrypt Security Hashing"
    ], '#fffbe6', '#d97706')

    # Arrows
    draw.line([440, 270, 480, 270], fill='#475569', width=4)
    draw.line([840, 270, 880, 270], fill='#475569', width=4)
    draw.line([260, 400, 260, 480], fill='#475569', width=4)
    draw.line([1200, 400, 1200, 480], fill='#475569', width=4)

    img_path = os.path.join(IMG_DIR, "diagram1_system_architecture.png")
    img.save(img_path)
    return img_path


# ---------------------------------------------------------------------------
# 2. GENERATE DIAGRAM 2: AI/ML Pipeline
# ---------------------------------------------------------------------------
def generate_diagram2():
    w, h = 1600, 700
    img = Image.new('RGB', (w, h), '#ffffff')
    draw = ImageDraw.Draw(img)

    f_title = get_font(22, bold=True)
    f_box_t = get_font(16, bold=True)
    f_box_b = get_font(13, bold=False)

    draw.text((w//2, 40), "AI/ML DEFECT PRIORITIZATION & RISK SCORING PIPELINE", 
              fill='#0f172a', font=f_title, anchor='mm')

    def draw_step(x, y, bw, bh, step_num, title, text_lines, color):
        draw.rounded_rectangle([x, y, x + bw, y + bh], radius=14, fill='#f8fafc', outline=color, width=3)
        draw.rectangle([x, y, x + bw, y + 40], fill=color)
        draw.text((x + bw//2, y + 20), f"STEP {step_num}: {title}", fill='#ffffff', font=f_box_t, anchor='mm')
        
        cur_y = y + 60
        for line in text_lines:
            draw.text((x + 15, cur_y), line, fill='#1e293b', font=f_box_b)
            cur_y += 24

    draw_step(60, 140, 330, 450, "1", "DATA INGESTION", [
        "Ingests defect backlog",
        "from TMS, SMMS, TDMS.",
        "",
        "Extracted Features:",
        "• Severity Level",
        "• Reported & Due Date",
        "• Estimated Duration",
        "• Daily Trains Affected",
        "• Railway Section ID"
    ], '#0284c7')

    draw_step(440, 140, 330, 450, "2", "RISK PREDICTION", [
        "Random Forest Classifier",
        "predicts Failure Risk P(f).",
        "",
        "Model Metrics:",
        "• Trained on historical",
        "  defect breakdowns",
        "• Evaluates defect age",
        "  vs. section density",
        "• Outputs probability (0-1)"
    ], '#7c3aed')

    draw_step(820, 140, 330, 450, "3", "ANOMALY DETECTION", [
        "Isolation Forest ML",
        "detects operational outliers.",
        "",
        "Anomaly Checks:",
        "• Abnormal duration",
        "  estimates (over/under)",
        "• High-risk section spikes",
        "• Flags outlier maintenance",
        "  for Controller audit"
    ], '#d97706')

    draw_step(1200, 140, 340, 450, "4", "PRIORITY SCORING", [
        "Computes final Priority",
        "Score (0 to 100).",
        "",
        "Formula Weighting:",
        "• 40% Severity Weight",
        "• 25% Overdue Lag Days",
        "• 20% Train Impact",
        "• 15% ML Failure Risk",
        "Highest score scheduled first!"
    ], '#059669')

    # Arrow connections
    for ax_x in [390, 770, 1150]:
        draw.line([ax_x, 365, ax_x + 50, 365], fill='#0284c7', width=4)

    img_path = os.path.join(IMG_DIR, "diagram2_ml_pipeline.png")
    img.save(img_path)
    return img_path


# ---------------------------------------------------------------------------
# 3. GENERATE DIAGRAM 3: Shadow Block Optimization
# ---------------------------------------------------------------------------
def generate_diagram3():
    w, h = 1600, 700
    img = Image.new('RGB', (w, h), '#ffffff')
    draw = ImageDraw.Draw(img)

    f_title = get_font(22, bold=True)
    f_box_t = get_font(16, bold=True)
    f_box_b = get_font(13, bold=False)

    draw.text((w//2, 40), "MULTI-DEPARTMENT SHADOW BLOCK CLUSTERING OPTIMIZATION", 
              fill='#0f172a', font=f_title, anchor='mm')

    # Traditional Box
    draw.rounded_rectangle([80, 120, 760, 460], radius=16, fill='#fef2f2', outline='#ef4444', width=3)
    draw.text((420, 155), "TRADITIONAL DECENTRALIZED PLANNING (3 LINE STOPPAGES)", fill='#991b1b', font=f_box_t, anchor='mm')
    
    t_lines = [
        "❌ Eng Track Maintenance: 02:00 PM - 05:00 PM (Section A) [Train Stop 1]",
        "❌ S&T Signal Maintenance:  06:00 PM - 08:00 PM (Section A) [Train Stop 2]",
        "❌ TRD OHE Maintenance:    10:00 PM - 01:00 AM (Section A) [Train Stop 3]",
        "",
        "Total Line Downtime = 8 Hours across 3 separate windows!",
        "Causes high train disruption & delayed freight movements."
    ]
    cur_y = 200
    for line in t_lines:
        draw.text((110, cur_y), line, fill='#7f1d1d', font=f_box_b)
        cur_y += 36

    # AI Optimized Box
    draw.rounded_rectangle([840, 120, 1520, 460], radius=16, fill='#ecfdf5', outline='#10b981', width=3)
    draw.text((1180, 155), "AI SHADOW BLOCK OPTIMIZED (1 CONCURRENT STOPPAGE)", fill='#065f46', font=f_box_t, anchor='mm')

    o_lines = [
        "✅ SINGLE CONCURRENT SHADOW WINDOW: 02:00 PM - 06:00 PM (Section A)",
        "",
        "✓ Engineering (Track) + S&T (Signals) + TRD (Traction OHE)",
        "  all execute simultaneously during ONE line stoppage!",
        "",
        "✓ SAVES 4+ HOURS OF LINE DISRUPTION PER DAY!",
        "✓ Maximizes track availability and train punctuality."
    ]
    cur_y = 200
    for line in o_lines:
        draw.text((870, cur_y), line, fill='#047857', font=f_box_b)
        cur_y += 34

    # Bottom OR-Tools Box
    draw.rounded_rectangle([80, 490, 1520, 650], radius=14, fill='#f8fafc', outline='#64748b', width=2)
    draw.text((800, 525), "GOOGLE OR-TOOLS CP-SAT CONSTRAINED OPTIMIZATION SOLVER", fill='#0f172a', font=f_box_t, anchor='mm')
    draw.text((800, 565), "• Objective: Minimize total train delay hours while maximizing critical maintenance resolution rate.", fill='#334155', font=f_box_b, anchor='mm')
    draw.text((800, 605), "• Constraints: Non-overlapping train timetables, crew availability limits, multi-horizon (7-day weekly & 30-day monthly).", fill='#334155', font=f_box_b, anchor='mm')

    img_path = os.path.join(IMG_DIR, "diagram3_shadow_block.png")
    img.save(img_path)
    return img_path


# ---------------------------------------------------------------------------
# PDF REPORT CLASS
# ---------------------------------------------------------------------------
class ArchitecturePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(100, 116, 139)
        self.cell(140, 10, "INDIAN RAILWAYS AUTOMATIC BLOCK PLANNING SYSTEM - ARCHITECTURE SPECIFICATION")
        self.cell(0, 10, "SIH PS 26027", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(226, 232, 240)
        self.line(10, 18, 200, 18)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f"Page {self.page_no()} | Technical Architecture Specification", align="C")

    def chapter_title(self, title):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(15, 23, 42)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(2, 132, 199)
        self.set_line_width(0.8)
        self.line(10, self.get_y() + 1, 200, self.get_y() + 1)
        self.ln(5)

    def chapter_sub_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(2, 132, 199)
        self.cell(0, 6, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text):
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 4.5, text)
        self.ln(3)


# ---------------------------------------------------------------------------
# MAIN BUILDER
# ---------------------------------------------------------------------------
def build_pdf():
    d1 = generate_diagram1()
    d2 = generate_diagram2()
    d3 = generate_diagram3()

    pdf = ArchitecturePDF()
    pdf.set_auto_page_break(auto=True, margin=18)

    # PAGE 1: Executive Summary & System Architecture
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 10, "System Architecture Specification Document", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(2, 132, 199)
    pdf.cell(0, 6, "AI-Powered Automatic Block Planning System (Smart India Hackathon PS 26027)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.chapter_title("1. Architectural Overview & Vision")
    pdf.body_text(
        "The Indian Railways Automatic Block Planning System replaces decentralized, manual corridor block requests "
        "with an AI-driven, multi-departmental constraint optimization engine. It integrates live maintenance defects "
        "from TMS (Track), SMMS (Signals), and TDMS (Traction) with passenger train timetables and Control Office freight forecasts."
    )

    pdf.image(d1, x=10, w=190)
    pdf.ln(4)

    pdf.chapter_sub_title("Key Architectural Layers:")
    pdf.body_text(
        "- Data Layer: Unified SQLite schema ingesting 6,300+ defects, 2,400 corridor slots, 2,000 timetables, and 2,000 freight forecasts.\n"
        "- AI/ML Layer: Random Forest failure risk prediction + Isolation Forest anomaly detection + mathematical priority scoring.\n"
        "- Optimization & Agent Layer: Google OR-Tools CP-SAT constraint solver + Multi-Department Shadow Block Clustering + 13 Governance Agents.\n"
        "- Presentation Layer: Streamlit dual-panel workspace with Plotly zoomable interactive charts, automated PDF reporting, and Groq-powered voice AI assistant."
    )

    # PAGE 2: AI/ML Prioritization & Optimization Engine
    pdf.add_page()
    pdf.chapter_title("2. AI/ML Prioritization & Mathematical Scoring")
    pdf.body_text(
        "Maintenance tasks are ranked dynamically using a combined mathematical and Machine Learning scoring model. "
        "Defects are evaluated based on structural severity, overdue lag days past deadline, daily train impact, and ML-predicted failure probability."
    )

    pdf.image(d2, x=10, w=190)
    pdf.ln(4)

    pdf.chapter_sub_title("Prioritization Formula:")
    pdf.body_text(
        "Priority Score = (Severity_Weight * 0.40) + (Overdue_Lag_Days * 0.25) + (Trains_Affected * 0.20) + (ML_Failure_Risk * 0.15)\n\n"
        "Where Severity Weights are: Critical = 100, High = 75, Medium = 50, Low = 25. Overdue lag represents actual days delayed past deadline."
    )

    pdf.chapter_title("3. Google OR-Tools Constraint Optimization & Shadow Blocks")
    pdf.body_text(
        "The optimization core uses Google OR-Tools CP-SAT to solve multi-horizon corridor block schedules (7-day Weekly tactical and 30-day Monthly strategic plans). "
        "A key innovation is Shadow Block Clustering, which groups Engineering, S&T, and TRD tasks into single concurrent maintenance windows."
    )

    pdf.image(d3, x=10, w=190)

    # PAGE 3: Governance Agents, Voice AI & Compliance
    pdf.add_page()
    pdf.chapter_title("4. Multi-Agent Architecture & Governance Tiers")
    pdf.body_text(
        "The system deploys 13 specialized autonomous agents that coordinate tasks, monitor safety SLAs, and execute auto-approvals:\n\n"
        "1. Department Agent: Filters and manages department-specific defects.\n"
        "2. Traffic Agent: Ensures train timetable non-overlap and passenger advisories.\n"
        "3. Coordinator Agent: Orchestrates cross-department shadow block clustering.\n"
        "4. Replanning Agent: Manages real-time disruptions using 3 Risk Tiers:\n"
        "   - Tier 1 (Routine): Auto-approves minor gap-filling.\n"
        "   - Tier 2 (Medium Risk): Auto-approves and logs controller alert.\n"
        "   - Tier 3 (Critical Risk): Escalates to manual Controller override.\n"
        "5. Feedback Loop Agent: Records execution minutes and computes Early/On-Time/Late performance variance.\n"
        "6. Compliance Agent: Enforces max block duration limits and safety regulations."
    )

    pdf.chapter_title("5. AI Assistant & Multilingual Voice Architecture")
    pdf.body_text(
        "The application integrates a dedicated, persistent AI Assistant powered by Groq API (Qwen 27B model):\n"
        "- Speech Recognition: Web Speech API transcribes English, Hindi, and Telugu in real-time.\n"
        "- Direct SQL NLP Querying: Understands natural time queries like '2pm to 3pm what scheduled' and defect lookups ('TMS-00010').\n"
        "- Automated Explainer: Explains the 5-step report generation process on demand.\n"
        "- Unified UI: Single rounded prompt container combining voice mic and text send button."
    )

    pdf.chapter_title("6. Security & Auditability")
    pdf.body_text(
        "- Role-Based Access Control (RBAC): Engineering, S&T, TRD, Admin.\n"
        "- Password Security: BCrypt password hashing.\n"
        "- Audit Logging: All controller overrides and agent decisions recorded in audit_log table with timestamps."
    )

    pdf.output(PDF_PATH)
    print(f"[SUCCESS] Architecture PDF successfully generated at: {PDF_PATH}")
    return PDF_PATH


if __name__ == "__main__":
    build_pdf()
