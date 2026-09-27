import sqlite3

conn = sqlite3.connect('railway.db')
cur = conn.cursor()
cur.execute("PRAGMA table_info(block_requests_v2)")
cols = cur.fetchall()
print("block_requests_v2 columns:")
for c in cols:
    print(" ", c)

cur.execute("SELECT COUNT(*), status FROM block_requests_v2 GROUP BY status")
print("Status counts:", cur.fetchall())
conn.close()
