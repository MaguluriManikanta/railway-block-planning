import sys, os, unittest

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

test_files = [
    "scratch/test_step2_map_verification.py",
    "scratch/test_step3_allocated_blocks.py",
    "scratch/test_step4_live_trains.py",
    "scratch/test_step5_controller_requests.py",
    "scratch/test_step6_classification.py",
    "scratch/test_step7_block_allocation.py",
    "scratch/test_step8_controller_selection.py",
    "scratch/test_step9_notifications.py",
    "scratch/test_step10_final_integration.py",
    "scratch/test_step11_acceptance_audit.py",
    "scratch/test_step12_sidebar_scrolling.py",
    "scratch/test_step13_department_overview_visuals.py",
    "scratch/test_step14_chatbot_intelligence.py",
    "scratch/test_step15_classified_persistence.py",
    "scratch/test_step15_acceptance_exact.py",
    "scratch/test_user_exact_example.py",
    "scratch/test_step17_add_defect_workflow.py",
    "scratch/test_step18_department_reported_defects.py",
]

total_passed = 0
total_failed = 0

for tf in test_files:
    full_path = os.path.join(base_dir, tf)
    if os.path.exists(full_path):
        print(f"\n>>> RUNNING: {tf}")
        loader = unittest.TestLoader()
        suite = loader.discover(start_dir=os.path.dirname(full_path), pattern=os.path.basename(full_path))
        runner = unittest.TextTestRunner(verbosity=1)
        res = runner.run(suite)
        if res.wasSuccessful():
            print(f"  [PASS] {tf}: {res.testsRun} tests passed.")
            total_passed += res.testsRun
        else:
            print(f"  [FAIL] {tf}: {len(res.failures)} failures, {len(res.errors)} errors.")
            total_failed += len(res.failures) + len(res.errors)

print("\n" + "=" * 60)
print(f"SUMMARY: Total Tests Run: {total_passed + total_failed} | Passed: {total_passed} | Failed: {total_failed}")
print("=" * 60)
