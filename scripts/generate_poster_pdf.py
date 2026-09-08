import os
import sys
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

PNG_PATH = os.path.join(OUTPUT_DIR, 'TrackMind_AI_Project_Poster_A3.png')
PDF_PATH = os.path.join(OUTPUT_DIR, 'TrackMind_AI_Project_Poster_A3.pdf')

def get_font(size=30, bold=False):
    fonts_to_try = [
        ('C:\\Windows\\Fonts\\segoeuib.ttf' if bold else 'C:\\Windows\\Fonts\\segoeui.ttf'),
        ('C:\\Windows\\Fonts\\arialbd.ttf' if bold else 'C:\\Windows\\Fonts\\arial.ttf'),
    ]
    for font_path in fonts_to_try:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_wrapped_text(draw, text, x, y, max_width, font, fill, line_spacing=6):
    words = text.split(' ')
    lines = []
    current_line = ''
    for word in words:
        test_line = current_line + (' ' if current_line else '') + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    
    cur_y = y
    for line in lines:
        draw.text((x, cur_y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        line_h = bbox[3] - bbox[1]
        cur_y += line_h + line_spacing
    return cur_y

def render_poster():
    w, h = 3508, 2480  # A3 at 300 DPI (Landscape)
    img = Image.new('RGB', (w, h), '#f8fafc')
    draw = ImageDraw.Draw(img)

    f_sec_hdr = get_font(38, bold=True)
    f_body = get_font(24, bold=False)

    # -------------------------------------------------------------
    # HEADER BAR
    # -------------------------------------------------------------
    draw.rounded_rectangle([40, 40, w - 40, 320], radius=24, fill='#ffffff', outline='#cbd5e1', width=4)

    # Left: Team Name
    draw.text((70, 70), 'TEAM NAME', fill='#94a3b8', font=get_font(22, bold=True))
    draw.text((70, 110), 'TrackMind AI', fill='#0284c7', font=get_font(52, bold=True))
    draw.text((70, 185), 'Smart India Hackathon • PS 26027', fill='#64748b', font=get_font(24, bold=True))
    draw.line([640, 60, 640, 300], fill='#e2e8f0', width=3)

    # Center: Government Emblem
    cx = w // 2 - 220
    draw.text((cx, 85), 'भारत सरकार', fill='#0f172a', font=get_font(36, bold=True))
    draw.text((cx, 135), 'GOVERNMENT OF INDIA', fill='#0f172a', font=get_font(42, bold=True))
    draw.text((cx, 195), 'MINISTRY OF RAILWAYS', fill='#0284c7', font=get_font(26, bold=True))

    # Right: Team Members
    rx = w - 900
    draw.line([rx - 40, 60, rx - 40, 300], fill='#e2e8f0', width=3)
    draw.text((rx, 65), 'TEAM MEMBERS NAMES', fill='#94a3b8', font=get_font(22, bold=True))
    draw.text((rx, 105), '• Sk.Kalesha Vali (Team Lead)', fill='#0369a1', font=get_font(26, bold=True))
    draw.text((rx, 145), '• K.Vaishika   • G.Navya Sri   • K.Nikitha', fill='#1e293b', font=get_font(24, bold=False))
    draw.text((rx, 185), '• M.Sravani   • M.Manikanta', fill='#1e293b', font=get_font(24, bold=False))
    draw.text((rx, 230), 'Contact: n220895@gmail.com  |  +91 8498898017', fill='#64748b', font=get_font(22, bold=True))

    # -------------------------------------------------------------
    # 4 QUADRANTS GRID SETUP
    # -------------------------------------------------------------
    qw = (w - 120) // 2
    qh = (h - 410) // 2

    q1_rect = [40, 350, 40 + qw, 350 + qh]
    q2_rect = [60 + qw, 350, w - 40, 350 + qh]
    q3_rect = [40, 370 + qh, 40 + qw, h - 40]
    q4_rect = [60 + qw, 370 + qh, w - 40, h - 40]

    def draw_quadrant_card(rect, border_color, title_text, badge_text):
        draw.rounded_rectangle(rect, radius=20, fill='#ffffff', outline='#cbd5e1', width=3)
        draw.rounded_rectangle([rect[0], rect[1], rect[0] + 16, rect[3]], radius=8, fill=border_color)
        draw.text((rect[0] + 40, rect[1] + 30), title_text, fill='#0f172a', font=f_sec_hdr)
        draw.line([rect[0] + 40, rect[1] + 85, rect[2] - 40, rect[1] + 85], fill='#e2e8f0', width=3)

    # Q1: TOP-LEFT -> TITLE & ABSTRACT
    draw_quadrant_card(q1_rect, '#0284c7', 'Title & Abstract', 'EXECUTIVE OVERVIEW')
    tb_x, tb_y = q1_rect[0] + 40, q1_rect[1] + 110
    tb_w, tb_h = qw - 80, 200
    draw.rounded_rectangle([tb_x, tb_y, tb_x + tb_w, tb_y + tb_h], radius=16, fill='#0f172a')
    draw.text((tb_x + 25, tb_y + 20), 'PROJECT TITLE', fill='#38bdf8', font=get_font(20, bold=True))
    draw_wrapped_text(draw, 'AI-Powered Automatic Block Planning to Maximize Asset Availability for Train Operations on Indian Railways', 
                      tb_x + 25, tb_y + 55, tb_w - 50, get_font(30, bold=True), '#ffffff', line_spacing=6)

    ab_y = tb_y + tb_h + 30
    draw.text((q1_rect[0] + 40, ab_y), 'ABSTRACT', fill='#0f172a', font=get_font(30, bold=True))
    
    abs_p1 = ('Indian Railways operates one of the world's densest train networks. Currently, corridor maintenance block '
              '(track outage) requests from three independent departments—Track Engineering (TMS), Signal & Telecom (SMMS), '
              'and Traction Distribution (TDMS)—are submitted in isolation without synchronized coordination. This causes severe '
              'corridor wastage, repetitive line stoppages (8+ hours daily per section), and heavy freight/passenger train detentions.')
    
    cur_y = draw_wrapped_text(draw, abs_p1, q1_rect[0] + 40, ab_y + 45, qw - 80, f_body, '#334155', line_spacing=10)

    abs_p2 = ('TrackMind AI solves this by delivering an intelligent, full-stack automated block planning platform. '
              'The system unifies multi-departmental defects with real-time Corridor Availability (COA), timetables, and goods forecasts. '
              'Using a Random Forest ML failure risk model combined with Google OR-Tools CP-SAT constraint optimization, '
              'the platform automatically schedules maintenance into unified Shadow Blocks—saving 4+ hours of daily corridor downtime!')
    
    draw_wrapped_text(draw, abs_p2, q1_rect[0] + 40, cur_y + 25, qw - 80, f_body, '#334155', line_spacing=10)

    # Q2: TOP-RIGHT -> WORKFLOW
    draw_quadrant_card(q2_rect, '#7c3aed', 'Workflow', 'PIPELINE BLUEPRINT')

    steps = [
        ('1. Multi-Department Data Ingestion', 'Ingests 6,300+ live records: Track (TMS), Signals (SMMS), Traction (TDMS), Corridor Slots (COA), Timetable (2,000 trains) & Goods Forecasts into SQLite DB.', '#0284c7', '#f0f9ff'),
        ('2. AI/ML Prioritization & Anomaly Engine', 'Mathematical Priority Score = 40% Severity + 25% Overdue Days + 20% Train Impact + 15% RF ML Failure Risk P(f). IsolationForest detects duration anomalies.', '#7c3aed', '#f5f3ff'),
        ('3. Google OR-Tools CP-SAT & Shadow Blocks', 'Constraint solver bundles Engineering + Signals + Traction into single concurrent maintenance windows. Generates 7-Day Weekly & 30-Day Monthly optimal schedules.', '#059669', '#ecfdf5'),
        ('4. 13 Governance Agents & Multilingual Voice UI', 'Autonomous agents manage 3 Auto-Approval Risk Tiers, SLA compliance & public advisories. Groq LLM voice assistant supports English, Hindi & Telugu.', '#d97706', '#fffbe6')
    ]

    sy = q2_rect[1] + 110
    for title, desc, col_border, col_bg in steps:
        box_rect = [q2_rect[0] + 40, sy, q2_rect[2] - 40, sy + 180]
        draw.rounded_rectangle(box_rect, radius=14, fill=col_bg, outline=col_border, width=3)
        draw.text((box_rect[0] + 25, box_rect[1] + 20), title, fill='#0f172a', font=get_font(28, bold=True))
        draw_wrapped_text(draw, desc, box_rect[0] + 25, box_rect[1] + 65, qw - 130, get_font(22, bold=False), '#334155', line_spacing=6)
        sy += 210

    # Q3: BOTTOM-LEFT -> CHALLENGES / LIMITATIONS
    draw_quadrant_card(q3_rect, '#d97706', 'Challenges / Limitations', 'OPERATIONAL BOTTLENECKS')

    ch_items = [
        ('❌ Uncoordinated Line Stoppages', 'Track, Signals, and OHE departments request isolated blocks on the same section, causing 3 separate train shutdowns totaling 8+ hours of downtime.', '#fef2f2', '#ef4444'),
        ('⚠️ Multi-Departmental Data Silos', 'Lack of real-time integration between TMS, SMMS, TDMS, COA, and Control Office freight movement forecasts results in frequent conflict spikes.', '#fffbe6', '#d97706'),
        ('⌛ Complex Math Constraints', 'Balancing overdue safety defect SLAs, crew availability limits, and non-overlapping passenger train timetables is manually intractable.', '#f8fafc', '#64748b'),
        ('📌 Scope & Operational Limits', 'Requires standardized digital API feeds from legacy railway software. Initial prototype uses SQLite; production transitions to Turso / PostgreSQL.', '#f0f9ff', '#0284c7')
    ]

    cx1, cx2 = q3_rect[0] + 40, q3_rect[0] + 40 + (qw - 100) // 2 + 20
    cw_box = (qw - 100) // 2
    
    positions = [(cx1, q3_rect[1] + 120), (cx2, q3_rect[1] + 120), (cx1, q3_rect[1] + 520), (cx2, q3_rect[1] + 520)]
    
    for idx, (title, text, bg_c, border_c) in enumerate(ch_items):
        px, py = positions[idx]
        b_rect = [px, py, px + cw_box, py + 360]
        draw.rounded_rectangle(b_rect, radius=14, fill=bg_c, outline=border_c, width=3)
        draw.text((px + 20, py + 20), title, fill='#0f172a', font=get_font(25, bold=True))
        draw_wrapped_text(draw, text, px + 20, py + 70, cw_box - 40, get_font(22, bold=False), '#334155', line_spacing=8)

    # Q4: BOTTOM-RIGHT -> PROPOSED SOLUTION / APPROACH
    draw_quadrant_card(q4_rect, '#059669', 'Proposed Solution / Approach', 'TECHNICAL CORE')

    solutions = [
        ('01', 'Concurrent Shadow Block Clustering', 'Bundles Track + Signal + OHE maintenance into a single 4-hour window, reducing line stoppage frequency by 66% and maximizing corridor availability.', '#059669'),
        ('02', 'Mathematical CP-SAT Constraint Optimization', 'Google OR-Tools solver optimizes 7-day tactical & 30-day strategic horizons under hard constraints: zero passenger train delay & crew availability limits.', '#0284c7'),
        ('03', 'Hybrid ML Risk Scoring & Anomaly Detection', 'Random Forest predicts breakdown probability P(f) while IsolationForest flags abnormal duration estimates & defect clustering across 40 rail sections.', '#7c3aed'),
        ('04', 'Multilingual AI Voice Assistant & Streamlit UI', 'Groq LLM (llama-3.3-70b) with Web Speech API offers voice control in English, Hindi (हिन्दी), and Telugu (తెలుగు) + automated PDF report generation.', '#d97706')
    ]

    sy4 = q4_rect[1] + 110
    for num, title, desc, accent_col in solutions:
        box_rect = [q4_rect[0] + 40, sy4, q4_rect[2] - 40, sy4 + 180]
        draw.rounded_rectangle(box_rect, radius=14, fill='#f8fafc', outline='#cbd5e1', width=3)
        
        draw.rounded_rectangle([box_rect[0] + 20, box_rect[1] + 20, box_rect[0] + 90, box_rect[1] + 80], radius=10, fill=accent_col)
        draw.text((box_rect[0] + 35, box_rect[1] + 30), num, fill='#ffffff', font=get_font(32, bold=True))

        draw.text((box_rect[0] + 110, box_rect[1] + 20), title, fill='#0f172a', font=get_font(26, bold=True))
        draw_wrapped_text(draw, desc, box_rect[0] + 110, box_rect[1] + 65, qw - 200, get_font(22, bold=False), '#334155', line_spacing=6)
        sy4 += 210

    img.save(PNG_PATH, quality=95)
    print('[SUCCESS] High-res A3 Poster PNG saved to:', PNG_PATH)

    pdf = FPDF(orientation='L', unit='mm', format='A3')
    pdf.add_page()
    pdf.image(PNG_PATH, x=0, y=0, w=420, h=297)
    pdf.output(PDF_PATH)
    print('[SUCCESS] High-res A3 Poster PDF saved to:', PDF_PATH)

if __name__ == '__main__':
    render_poster()
