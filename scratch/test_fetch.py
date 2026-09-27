import sys, os
sys.path.insert(0, os.path.abspath("."))
from app.controller_requests import fetch_controller_requests

new_reqs, overdue_reqs, total_new, total_overdue = fetch_controller_requests()
print(f"fetch_controller_requests -> total_new: {total_new}, total_overdue: {total_overdue}")
print("New requests IDs:")
for r in new_reqs:
    print(" ", r.get("request_id"), r.get("department"), r.get("status"), r.get("source"))

print("Overdue requests IDs:")
for r in overdue_reqs:
    print(" ", r.get("request_id"), r.get("department"), r.get("status"), r.get("source"))
