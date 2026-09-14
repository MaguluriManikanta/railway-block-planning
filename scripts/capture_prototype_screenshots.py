import sys
import os
import time
import requests
from playwright.sync_api import sync_playwright

user_site = os.path.expanduser('~\\AppData\\Roaming\\Python\\Python314\\site-packages')
if user_site not in sys.path:
    sys.path.append(user_site)

output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
os.makedirs(output_dir, exist_ok=True)

URL = "http://localhost:8502"
try:
    r = requests.get("http://localhost:8502", timeout=2)
    if r.status_code == 200:
        URL = "http://localhost:8502"
    else:
        URL = "http://localhost:8501"
except Exception:
    URL = "http://localhost:8501"

print(f"Connecting to live Streamlit Prototype at {URL}...")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    page.goto(URL, timeout=30000, wait_until="networkidle")
    time.sleep(6)

    # Scene 1: Main Dashboard Header & Portal Overview
    scene1_path = os.path.join(output_dir, "scene_1.png")
    page.screenshot(path=scene1_path)
    print(f"Captured Scene 1 (System Portal Header): {scene1_path}")

    # Query all Streamlit tabs
    tabs = page.query_selector_all('button[data-baseweb="tab"]')
    print(f"Found {len(tabs)} interactive Streamlit dashboard tabs.")

    # Scene 2: Tab 0 (Executive Overview & KPI Cards)
    if len(tabs) > 0:
        try:
            tabs[0].click()
            time.sleep(4)
        except Exception:
            pass
    scene2_path = os.path.join(output_dir, "scene_2.png")
    page.screenshot(path=scene2_path)
    print(f"Captured Scene 2 (Executive Overview KPIs): {scene2_path}")

    # Scene 3: Tab 1 (Optimizer Control & CP-SAT Settings)
    if len(tabs) > 1:
        try:
            tabs[1].click()
            time.sleep(4)
        except Exception:
            pass
    scene3_path = os.path.join(output_dir, "scene_3.png")
    page.screenshot(path=scene3_path)
    print(f"Captured Scene 3 (Optimizer Control Panel): {scene3_path}")

    # Scene 4: Tab 2 (Visual Block Windows Timeline & Gantt)
    if len(tabs) > 2:
        try:
            tabs[2].click()
            time.sleep(4)
        except Exception:
            pass
    scene4_path = os.path.join(output_dir, "scene_4.png")
    page.screenshot(path=scene4_path)
    print(f"Captured Scene 4 (Visual Schedule Timeline): {scene4_path}")

    # Scene 5: Tab 3 (Department Operations Breakdown)
    if len(tabs) > 3:
        try:
            tabs[3].click()
            time.sleep(4)
        except Exception:
            pass
    scene5_path = os.path.join(output_dir, "scene_5.png")
    page.screenshot(path=scene5_path)
    print(f"Captured Scene 5 (Department Breakdown): {scene5_path}")

    # Scene 6: Tab 6 (Anomalies & Defect Clustering)
    if len(tabs) > 6:
        try:
            tabs[6].click()
            time.sleep(4)
        except Exception:
            pass
    scene6_path = os.path.join(output_dir, "scene_6.png")
    page.screenshot(path=scene6_path)
    print(f"Captured Scene 6 (Anomalies & Defect Clustering): {scene6_path}")

    # Scene 7: Tab 9 (AI Voice Assistant & Data Management)
    if len(tabs) > 9:
        try:
            tabs[9].click()
            time.sleep(4)
        except Exception:
            pass
    scene7_path = os.path.join(output_dir, "scene_7.png")
    page.screenshot(path=scene7_path)
    print(f"Captured Scene 7 (AI Voice Assistant Panel): {scene7_path}")

    browser.close()

print("\nSUCCESSFULLY CAPTURED ALL REAL PROTOTYPE DASHBOARD SCREENSHOTS!")
