import sqlite3
from datetime import datetime

conn = sqlite3.connect('railway.db')
cur = conn.cursor()
cur.execute("SELECT defect_id, department, defect_type, reported_date, due_date, status FROM defects WHERE status NOT IN ('Closed', 'Fixed', 'Completed', 'Cancelled', 'ALLOCATED', 'CLASSIFIED', 'REJECTED') LIMIT 15")
rows = cur.fetchall()
print(f"Pending defects ({len(rows)} sampled):")
for r in rows:
    print(" ", r)

cur.execute("SELECT request_id, department, request_type, reported_time, deadline, status FROM block_requests_v2 WHERE status NOT IN ('ALLOCATED', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'CLASSIFIED', 'REJECTED') LIMIT 15")
b_rows = cur.fetchall()
print(f"Pending block_requests_v2 ({len(b_rows)} sampled):")
for r in b_rows:
    print(" ", r)

conn.close()
