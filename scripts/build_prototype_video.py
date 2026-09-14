import sys
import os
import asyncio
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# Add user site-packages if needed
user_site = os.path.expanduser('~\\AppData\\Roaming\\Python\\Python314\\site-packages')
if user_site not in sys.path:
    sys.path.append(user_site)

import edge_tts
import cv2

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
os.makedirs(OUTPUT_DIR, exist_ok=True)
VIDEO_PATH = os.path.join(OUTPUT_DIR, "prototype_explanation_video.mp4")

# Scene definitions: Title, Narrative Text, Image Generator Function
SCENES = [
    {
        "id": "scene_1",
        "title": "Scene 1: Problem Statement & Context (SIH 26027)",
        "voice_text": (
            "Welcome to the comprehensive demonstration of our AI-Powered Automatic Block Planning System for Indian Railways, "
            "developed for Smart India Hackathon Problem Statement 26027. In train operations, maintaining track infrastructure, "
            "signalling systems, and overhead electrical traction lines is vital for safety. However, three key departments—Engineering, "
            "Signal and Telecom, and Traction Distribution—independently request maintenance blocks without central coordination. "
            "This lack of integration leads to severe corridor congestion, conflicting disconnection windows, emergency track blockages, "
            "and costly passenger train delays. Our solution bridges this gap by unifying departmental requests, corridor availability, "
            "and passenger timetables into a single intelligent AI planning ecosystem."
        ),
        "sub_title": "Unifying Track, Signalling & Traction Disconnections",
        "type": "problem_overview"
    },
    {
        "id": "scene_2",
        "title": "Scene 2: Data Ingestion & Database Schema",
        "voice_text": (
            "Let us examine the data layer. Our prototype features a realistic synthetic data generator that simulates over 2,000 "
            "maintenance defect records across 40 railway sections and 5 divisions. Data is ingested from legacy systems including "
            "TMS for track defects, SMMS for signalling faults, and TDMS for overhead equipment maintenance. These are combined with "
            "Corridor Availability slots from COA, passenger train timetables, and goods traffic forecasts. Everything is stored in an "
            "acid-compliant SQLite database with optimized schemas covering defects, corridor slots, schedules, crew rosters, audit logs, "
            "and real-time system notifications."
        ),
        "sub_title": "Unified Data Layer with 2000+ Realistically Simulated Records",
        "type": "architecture_data"
    },
    {
        "id": "scene_3",
        "title": "Scene 3: ML Priority Scoring & Anomaly Detection",
        "voice_text": (
            "Before scheduling occurs, our Machine Learning layer scores and ranks every maintenance task. The explicit Priority Score "
            "combines defect severity—weighted up to 40 points—with overdue days normalized over a 90-day window, and operational train impact. "
            "Simultaneously, a Random Forest Classifier evaluates historical track telemetry to predict the probability of component failure prior "
            "to maintenance. We blend 60 percent explicit priority with 40 percent failure risk score for final task ranking. Additionally, "
            "an IsolationForest anomaly detection model continuously scans railway sections to detect abnormal defect clustering, flagging "
            "systemic infrastructure degradation before catastrophic failures occur."
        ),
        "sub_title": "Random Forest Risk Prediction & IsolationForest Defect Clustering",
        "type": "ml_scoring"
    },
    {
        "id": "scene_4",
        "title": "Scene 4: CP-SAT Optimization Engine",
        "voice_text": (
            "At the heart of the scheduling engine lies Google OR-Tools CP-SAT constraint programming solver. The optimizer models block allocation "
            "as a mathematical assignment problem with zero departmental collisions as a mandatory hard constraint. Crucially, the solver filters "
            "corridor windows against passenger train timetable departure times to prevent train hold-ups. It also enforces locked controller "
            "overrides as immutable boundaries. Operating over flexible 7-day weekly and 30-day monthly planning horizons, CP-SAT maximizes the "
            "total cumulative priority score of scheduled maintenance while guaranteeing perfect compliance with operational safety limits."
        ),
        "sub_title": "Google OR-Tools CP-SAT Solver for Collision-Free Horizons",
        "type": "cpsat_optimizer"
    },
    {
        "id": "scene_5",
        "title": "Scene 5: 13+ Autonomous AI Agents Swarm",
        "voice_text": (
            "Our prototype is driven by a swarm of over 13 autonomous, plain Python AI agents working in harmony. Departmental Agents for Track, "
            "Signal, and Traction filter priority workloads, while the Traffic Agent protects heavy goods freight corridors. The Coordinator Agent "
            "executes solver passes and resolves conflicts, while the Re-planning Agent dynamically fills freed schedule gaps when tasks finish early. "
            "We implement a three-tier auto-approval framework: Tier 1 routine tasks are auto-approved instantly; Tier 2 medium-risk tasks auto-approve "
            "with audit logs after a quiet window; and Tier 3 safety-critical tasks strictly await explicit human controller approval. Other specialized "
            "agents handle crew roster lookups, cost optimization, downtime simulation, and passenger advisories."
        ),
        "sub_title": "Multi-Agent System Architecture & 3 Auto-Approval Risk Tiers",
        "type": "agents_swarm"
    },
    {
        "id": "scene_6",
        "title": "Scene 6: Interactive Dashboard & AI Voice Assistant",
        "voice_text": (
            "Let us walk through the Streamlit dashboard experience. The Central Controller interface is organized into 10 comprehensive tabs. "
            "Controllers can monitor high-level KPIs, inspect interactive Plotly Gantt timelines, review departmental workloads, and execute manual "
            "overrides with instant conflict validation. Official PDF reports can be generated and downloaded with a single click using fpdf2. "
            "Additionally, a dedicated AI Assistant panel—powered by Groq's Llama 3.3 70B model with Web Speech API integration—enables hands-free "
            "multilingual voice querying in English, Hindi, and Telugu. Controllers can query time windows, request conflict trade-off explanations, "
            "and issue natural language task commands."
        ),
        "sub_title": "10-Tab Control Dashboard, fpdf2 PDF Reports & Groq Voice Assistant",
        "type": "dashboard_ui"
    },
    {
        "id": "scene_7",
        "title": "Scene 7: Impact, Results & Conclusion",
        "voice_text": (
            "In summary, our prototype delivers a 37.5 percent reduction in total track downtime compared to uncoordinated maintenance. By providing "
            "guaranteed zero departmental collisions, automated SLA tracking, predictive failure prevention, and hands-free voice assistance, this "
            "system transforms railway asset management. Deployed effortlessly on Streamlit Cloud with modular SQLite architecture ready for enterprise "
            "PostgreSQL scaling, this prototype sets a new standard for Indian Railways block planning. Thank you for watching our detailed technical overview."
        ),
        "sub_title": "37.5% Downtime Reduction & Production Deployment Readiness",
        "type": "impact_conclusion"
    }
]


def render_slide_image(scene_info, output_png):
    """Render a 1920x1080 high-definition slide image for a scene."""
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
    fig.patch.set_facecolor('#0f172a')  # Dark blue / slate theme
    ax.set_facecolor('#0f172a')
    ax.axis('off')

    # Header banner
    header_rect = patches.FancyBboxPatch((0.02, 0.86), 0.96, 0.11, boxstyle="round,pad=0.02",
                                         facecolor='#1e293b', edgecolor='#3b82f6', linewidth=2)
    ax.add_patch(header_rect)

    plt.text(0.04, 0.92, scene_info["title"], color='#f8fafc', fontsize=20, fontweight='bold', va='center')
    plt.text(0.04, 0.88, scene_info["sub_title"], color='#60a5fa', fontsize=13, va='center')

    stype = scene_info["type"]

    if stype == "problem_overview":
        depts = [("Engineering (TMS)", "Track & Bed Defects", "#ef4444"),
                 ("Signal & Telecom (SMMS)", "Interlocking & Signals", "#f59e0b"),
                 ("Traction (TDMS)", "Overhead OHE Lines", "#10b981")]
        for idx, (dname, dsub, dcol) in enumerate(depts):
            x = 0.05 + idx * 0.31
            box = patches.FancyBboxPatch((x, 0.52), 0.28, 0.28, boxstyle="round,pad=0.02",
                                         facecolor='#1e293b', edgecolor=dcol, linewidth=2.5)
            ax.add_patch(box)
            plt.text(x + 0.14, 0.74, dname, color='#ffffff', fontsize=14, fontweight='bold', ha='center')
            plt.text(x + 0.14, 0.67, dsub, color='#cbd5e1', fontsize=11, ha='center')
            plt.text(x + 0.14, 0.58, "Uncoordinated Disconnections\n-> Traffic Blockages", color='#f87171', fontsize=10, ha='center')

        sol_box = patches.FancyBboxPatch((0.05, 0.08), 0.90, 0.36, boxstyle="round,pad=0.02",
                                          facecolor='#1e3a8a', edgecolor='#60a5fa', linewidth=2)
        ax.add_patch(sol_box)
        plt.text(0.50, 0.38, "Unified AI Automatic Block Planning System", color='#ffffff', fontsize=17, fontweight='bold', ha='center')
        plt.text(0.50, 0.26, "• Combines TMS + SMMS + TDMS defect feeds into single database\n• Enforces passenger timetable departure windows & COA availability\n• Eliminates collision conflicts & optimizes weekly / monthly horizons",
                 color='#e0f2fe', fontsize=12, ha='center', va='top')

    elif stype == "architecture_data":
        inputs = ["TMS Defects (Track)", "SMMS Faults (Signals)", "TDMS Maintenance (OHE)", "COA Corridor Slots", "Train Timetable", "Goods Forecast"]
        for i, inp in enumerate(inputs):
            y = 0.75 - i * 0.11
            box = patches.FancyBboxPatch((0.05, y), 0.25, 0.08, boxstyle="round,pad=0.01",
                                         facecolor='#1e293b', edgecolor='#38bdf8', linewidth=1.5)
            ax.add_patch(box)
            plt.text(0.175, y + 0.04, inp, color='#e0f2fe', fontsize=11, fontweight='bold', ha='center', va='center')

        db_box = patches.FancyBboxPatch((0.38, 0.20), 0.26, 0.60, boxstyle="round,pad=0.02",
                                         facecolor='#0f766e', edgecolor='#2dd4bf', linewidth=2.5)
        ax.add_patch(db_box)
        plt.text(0.51, 0.73, "SQLite Central DB", color='#ffffff', fontsize=16, fontweight='bold', ha='center')
        plt.text(0.51, 0.67, "(2000+ Synthetic Records)", color='#99f6e4', fontsize=11, ha='center')

        db_tables = ["defects", "corridor_slots", "train_timetable", "schedule", "crew_roster", "audit_log", "notifications"]
        for ti, tbl in enumerate(db_tables):
            plt.text(0.51, 0.58 - ti * 0.055, f"• {tbl}", color='#ffffff', fontsize=10, ha='center')

        out_box = patches.FancyBboxPatch((0.70, 0.28), 0.25, 0.44, boxstyle="round,pad=0.02",
                                          facecolor='#1e293b', edgecolor='#818cf8', linewidth=2)
        ax.add_patch(out_box)
        plt.text(0.825, 0.64, "Downstream Engine", color='#ffffff', fontsize=14, fontweight='bold', ha='center')
        plt.text(0.825, 0.52, "• CP-SAT Optimizer\n• ML Scoring Engine\n• 13 AI Agents\n• Streamlit Dashboard\n• fpdf2 PDF Reports", color='#c7d2fe', fontsize=11, ha='center')

    elif stype == "ml_scoring":
        fbox = patches.FancyBboxPatch((0.05, 0.48), 0.43, 0.34, boxstyle="round,pad=0.02",
                                       facecolor='#1e293b', edgecolor='#a855f7', linewidth=2)
        ax.add_patch(fbox)
        plt.text(0.265, 0.76, "1. Priority Score Formula", color='#c084fc', fontsize=14, fontweight='bold', ha='center')
        plt.text(0.07, 0.68, "Priority = Severity + (Overdue/90 * 30) + (Impact/50 * 30)",
                 color='#ffffff', fontsize=12, fontweight='bold')
        plt.text(0.07, 0.56, "Severity Weights: Critical=40, High=25, Medium=12, Low=5\nRisk Blend: 60% Priority Score + 40% Predicted Failure Risk", color='#cbd5e1', fontsize=10)

        abox = patches.FancyBboxPatch((0.52, 0.48), 0.43, 0.34, boxstyle="round,pad=0.02",
                                       facecolor='#1e293b', edgecolor='#ec4899', linewidth=2)
        ax.add_patch(abox)
        plt.text(0.735, 0.76, "2. Anomaly Detection (IsolationForest)", color='#f472b6', fontsize=14, fontweight='bold', ha='center')
        plt.text(0.54, 0.65, "Scans section defect density & overdue days.\nFlags defect clustering anomalies (contamination=0.15)\nprevents systemic rail line degradation.", color='#fbcfe8', fontsize=10)

        sub_ax = fig.add_axes([0.10, 0.10, 0.80, 0.32])
        sub_ax.set_facecolor('#1e293b')
        np.random.seed(42)
        x_norm = np.random.normal(15, 4, 35)
        y_norm = np.random.normal(10, 3, 35)
        x_anom = np.array([32, 38, 41, 35])
        y_anom = np.array([28, 31, 35, 29])

        sub_ax.scatter(x_norm, y_norm, color='#38bdf8', label='Normal Sections', s=60)
        sub_ax.scatter(x_anom, y_anom, color='#ef4444', label='Flagged Anomalies (Defect Clusters)', s=120, marker='^')
        sub_ax.set_title("Section Defect Density vs Avg Overdue Days", color='#ffffff', fontsize=11)
        sub_ax.set_xlabel("Defect Count per Section", color='#cbd5e1', fontsize=9)
        sub_ax.set_ylabel("Avg Overdue Days", color='#cbd5e1', fontsize=9)
        sub_ax.tick_params(colors='#cbd5e1')
        sub_ax.legend(facecolor='#0f172a', edgecolor='#38bdf8', labelcolor='#ffffff', fontsize=9)

    elif stype == "cpsat_optimizer":
        box1 = patches.FancyBboxPatch((0.05, 0.50), 0.42, 0.32, boxstyle="round,pad=0.02",
                                      facecolor='#1e293b', edgecolor='#f59e0b', linewidth=2)
        ax.add_patch(box1)
        plt.text(0.26, 0.76, "Decision Variables & Objective", color='#fbbf24', fontsize=14, fontweight='bold', ha='center')
        plt.text(0.07, 0.68, "Assign[i, j] in {0, 1} for Defect i, Slot j", color='#ffffff', fontsize=12, fontweight='bold')
        plt.text(0.07, 0.56, "Maximize Sum( PriorityScore[i] * Assign[i,j] )", color='#38bdf8', fontsize=12, fontweight='bold')

        box2 = patches.FancyBboxPatch((0.53, 0.50), 0.42, 0.32, boxstyle="round,pad=0.02",
                                      facecolor='#1e293b', edgecolor='#10b981', linewidth=2)
        ax.add_patch(box2)
        plt.text(0.74, 0.76, "Hard Safety Constraints", color='#34d399', fontsize=14, fontweight='bold', ha='center')
        plt.text(0.55, 0.65, "1. Slot Conflict: Sum(Assign[i,j]) <= 1 (Zero Clashes)\n2. Timetable Exclusion: Filter slots overlapping passenger train departures\n3. Override Lock: Respect controller manual locks", color='#e0e7ff', fontsize=10)

        sub_ax = fig.add_axes([0.08, 0.10, 0.84, 0.32])
        sub_ax.set_facecolor('#1e293b')
        df_gantt = pd.DataFrame([
            dict(Task="Engineering - Rails", Start=2, Duration=3, Color="#ef4444"),
            dict(Task="Signal & Telecom", Start=6, Duration=2, Color="#f59e0b"),
            dict(Task="Traction OHE", Start=9, Duration=4, Color="#10b981"),
            dict(Task="Train Timetable Window", Start=0, Duration=2, Color="#6366f1")
        ])
        for idx, r in df_gantt.iterrows():
            sub_ax.barh(r["Task"], r["Duration"], left=r["Start"], color=r["Color"], height=0.5)
        sub_ax.set_title("Optimized Corridor Block Schedule Timeline (24h View)", color='#ffffff', fontsize=11)
        sub_ax.set_xlabel("Hours of Day (00:00 - 24:00)", color='#cbd5e1', fontsize=9)
        sub_ax.tick_params(colors='#cbd5e1')

    elif stype == "agents_swarm":
        agent_categories = [
            ("Department & Operational Agents", ["1. Engineering Agent", "2. Signal & Telecom Agent", "3. TRD Traction Agent", "4. Traffic Agent"], "#ef4444"),
            ("Optimization & Re-planning", ["5. Coordinator Agent", "6. Re-planning Agent (3 Tiers)", "7. Deadline-Alert Agent", "8. Anomaly Agent"], "#3b82f6"),
            ("Safety, Crew & Analytics", ["9. Compliance Agent", "10. Crew Roster Agent", "11. Cost Optimization Agent", "12. Feedback Loop Agent", "13. Advisory & Simulation"], "#10b981")
        ]
        for idx, (cat_name, ag_list, cat_col) in enumerate(agent_categories):
            x = 0.04 + idx * 0.31
            box = patches.FancyBboxPatch((x, 0.40), 0.29, 0.42, boxstyle="round,pad=0.02",
                                         facecolor='#1e293b', edgecolor=cat_col, linewidth=2)
            ax.add_patch(box)
            plt.text(x + 0.145, 0.77, cat_name, color='#ffffff', fontsize=12, fontweight='bold', ha='center')
            for ai, ag in enumerate(ag_list):
                plt.text(x + 0.02, 0.70 - ai * 0.07, f"• {ag}", color='#e2e8f0', fontsize=10)

        tier_box = patches.FancyBboxPatch((0.04, 0.08), 0.91, 0.28, boxstyle="round,pad=0.02",
                                           facecolor='#312e81', edgecolor='#818cf8', linewidth=2)
        ax.add_patch(tier_box)
        plt.text(0.50, 0.30, "3-Tier Auto-Approval Framework (Re-planning Agent)", color='#ffffff', fontsize=13, fontweight='bold', ha='center')
        plt.text(0.18, 0.18, "Tier 1: Routine / Low Risk\n-> Auto-Approve Immediately", color='#86efac', fontsize=10, ha='center')
        plt.text(0.50, 0.18, "Tier 2: Medium Risk\n-> Auto-Approve with Audit Log", color='#fde047', fontsize=10, ha='center')
        plt.text(0.82, 0.18, "Tier 3: Safety-Critical\n-> Mandatory Admin Approval", color='#fca5a5', fontsize=10, ha='center')

    elif stype == "dashboard_ui":
        tabs = ["1. Executive Overview", "2. Optimizer Control", "3. Visual Timeline", "4. Department Breakdown",
                "5. Crew & Resources", "6. Cost & Savings", "7. Anomalies & Risk", "8. Public Advisories",
                "9. Data Management", "10. AI Voice Assistant"]

        plt.text(0.50, 0.80, "Central Controller Dashboard — 10 Interactive Tabs", color='#ffffff', fontsize=15, fontweight='bold', ha='center')

        for i, t in enumerate(tabs):
            row = i // 2
            col = i % 2
            x = 0.08 + col * 0.43
            y = 0.65 - row * 0.11
            tbox = patches.FancyBboxPatch((x, y), 0.40, 0.09, boxstyle="round,pad=0.01",
                                          facecolor='#1e293b', edgecolor='#38bdf8', linewidth=1.5)
            ax.add_patch(tbox)
            plt.text(x + 0.20, y + 0.045, t, color='#f0f9ff', fontsize=11, fontweight='bold', ha='center', va='center')

        f_box = patches.FancyBboxPatch((0.08, 0.08), 0.83, 0.16, boxstyle="round,pad=0.01",
                                        facecolor='#065f46', edgecolor='#34d399', linewidth=1.5)
        ax.add_patch(f_box)
        plt.text(0.50, 0.18, "Key Full-Stack Features", color='#ffffff', fontsize=12, fontweight='bold', ha='center')
        plt.text(0.50, 0.11, "• Hands-free Multilingual Voice Assistant (English, Hindi, Telugu) via Groq Llama 3.3 70B & Web Speech API\n• Downloadable Official PDF Reports generated automatically via fpdf2 with one click",
                 color='#a7f3d0', fontsize=10, ha='center')

    elif stype == "impact_conclusion":
        metrics = [("37.5%", "Track Downtime Reduction", "#10b981"),
                   ("100%", "Zero Departmental Collisions", "#3b82f6"),
                   ("13+", "Autonomous AI Agents", "#a855f7"),
                   ("3 Tiers", "Auto-Approval Risk Framework", "#f59e0b")]

        for idx, (val, lbl, col) in enumerate(metrics):
            x = 0.04 + idx * 0.235
            mbox = patches.FancyBboxPatch((x, 0.50), 0.21, 0.32, boxstyle="round,pad=0.02",
                                          facecolor='#1e293b', edgecolor=col, linewidth=2.5)
            ax.add_patch(mbox)
            plt.text(x + 0.105, 0.73, val, color=col, fontsize=24, fontweight='bold', ha='center')
            plt.text(x + 0.105, 0.60, lbl, color='#ffffff', fontsize=11, fontweight='bold', ha='center')

        c_box = patches.FancyBboxPatch((0.04, 0.10), 0.91, 0.34, boxstyle="round,pad=0.02",
                                        facecolor='#1e3a8a', edgecolor='#60a5fa', linewidth=2)
        ax.add_patch(c_box)
        plt.text(0.50, 0.36, "Ready for Smart India Hackathon & Enterprise Deployment", color='#ffffff', fontsize=16, fontweight='bold', ha='center')
        plt.text(0.50, 0.24, "• Streamlit Community Cloud instant public hosting with secrets management\n• Modular architecture supporting Turso / PostgreSQL enterprise database migration\n• Full compliance with Indian Railways operational safety standards",
                 color='#dbeafe', fontsize=11, ha='center')

    plt.savefig(output_png, facecolor=fig.get_facecolor(), edgecolor='none', bbox_inches='tight', pad_inches=0.1)
    plt.close()
    print(f"Rendered slide: {output_png}")


async def generate_scene_audio(text, output_mp3):
    """Synthesize neural AI voice audio file using edge-tts."""
    voice = "en-IN-NeerjaNeural"
    c = edge_tts.Communicate(text, voice)
    await c.save(output_mp3)
    print(f"Generated audio: {output_mp3}")


def get_audio_duration_ffprobe(audio_file):
    """Fallback duration estimation using wave / file size or opencv / python."""
    try:
        import mutagen
        audio = mutagen.File(audio_file)
        return audio.info.length
    except Exception:
        size_bytes = os.path.getsize(audio_file)
        return size_bytes / (128 * 1024 / 8)


async def build_video():
    print("Starting Video Generation pipeline...")
    scene_clips = []
    
    for idx, scene in enumerate(SCENES):
        png_path = os.path.join(OUTPUT_DIR, f"{scene['id']}.png")
        mp3_path = os.path.join(OUTPUT_DIR, f"{scene['id']}.mp3")
        
        # 1. Render slide image
        render_slide_image(scene, png_path)
        
        # 2. Synthesize AI voice narration
        await generate_scene_audio(scene["voice_text"], mp3_path)
        
        duration = get_audio_duration_ffprobe(mp3_path)
        scene_clips.append({
            "image": png_path,
            "audio": mp3_path,
            "duration": duration,
            "title": scene["title"]
        })
    
    print("All slides and audio synthesized! Assembling video...")
    
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
        clips = []
        for sc in scene_clips:
            audioclip = AudioFileClip(sc["audio"])
            videoclip = ImageClip(sc["image"]).with_duration(audioclip.duration).with_audio(audioclip)
            clips.append(videoclip)
        
        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile(VIDEO_PATH, fps=24, codec="libx264", audio_codec="aac")
        print(f"\nSUCCESS: MP4 Video created at {VIDEO_PATH}")
        return True
    except Exception as ex:
        print(f"Moviepy video compilation notice: {ex}")
        return False


if __name__ == "__main__":
    asyncio.run(build_video())
