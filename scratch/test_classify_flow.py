import sys, os
sys.path.insert(0, os.path.abspath("."))
from app.controller_requests import fetch_controller_requests
from app.classification_engine import RequestClassificationEngine

new_reqs, overdue_reqs, total_new, total_overdue = fetch_controller_requests()
print(f"BEFORE CLASSIFY -> total_new: {total_new}, total_overdue: {total_overdue}")
actionable = new_reqs + overdue_reqs

res = RequestClassificationEngine.classify_all_actionable_requests(actionable)
print(f"CLASSIFIED {len(res['classified_ids'])} requests: {res['classified_ids']}")

new_reqs_after, overdue_reqs_after, total_new_after, total_overdue_after = fetch_controller_requests()
print(f"AFTER CLASSIFY -> total_new: {total_new_after}, total_overdue: {total_overdue_after}")
print("New requests IDs after:")
for r in new_reqs_after:
    print(" ", r.get("request_id"), r.get("department"), r.get("status"), r.get("source"))
