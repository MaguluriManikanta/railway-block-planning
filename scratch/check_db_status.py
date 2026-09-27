import sqlite3

conn = sqlite3.connect('railway.db')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM request_classification_history')
print('Classification history count:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM block_requests_v2 WHERE status NOT IN ('ALLOCATED', 'ACTIVE', 'COMPLETED', 'CANCELLED', 'CLASSIFIED', 'REJECTED')")
print('Pending block_requests_v2:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM defects WHERE status NOT IN ('Closed', 'Fixed', 'Completed', 'Cancelled', 'ALLOCATED', 'CLASSIFIED', 'REJECTED')")
print('Pending defects:', cur.fetchone()[0])

cur.execute("SELECT request_ids FROM request_classification_history ORDER BY rowid DESC LIMIT 10")
print("Recent classified request_ids:", cur.fetchall())
conn.close()
