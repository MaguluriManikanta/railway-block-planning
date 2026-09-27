import sqlite3
import os

db_path = "railway.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print("Tables:", tables)

    if "request_classification_history" in tables:
        cur.execute("SELECT classification_id, request_ids, classification, timestamp FROM request_classification_history")
        rows = cur.fetchall()
        print(f"request_classification_history ({len(rows)} rows):", rows)

    if "block_requests_v2" in tables:
        cur.execute("SELECT request_id, department, status FROM block_requests_v2")
        rows = cur.fetchall()
        print(f"block_requests_v2 ({len(rows)} rows):", rows)

    if "defects" in tables:
        cur.execute("SELECT defect_id, department, status FROM defects LIMIT 5")
        rows = cur.fetchall()
        print(f"defects ({len(rows)} rows):", rows)

    conn.close()
else:
    print("No DB file found at railway.db")
