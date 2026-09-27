import sqlite3

conn = sqlite3.connect('railway.db')
cur = conn.cursor()
cur.execute("SELECT request_id, department, status, reported_time, deadline FROM block_requests_v2 WHERE status NOT IN ('ALLOCATED', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'CLASSIFIED', 'REJECTED')")
pending = cur.fetchall()
print(f"Pending block_requests_v2 ({len(pending)} rows):")
for p in pending:
    print(" ", p)

cur.execute("SELECT COUNT(*) FROM request_classification_history")
print("Total history rows:", cur.fetchone()[0])
conn.close()
