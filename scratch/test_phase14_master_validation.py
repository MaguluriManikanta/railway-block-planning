import sys
import os
import subprocess

def run_test(script_path):
    result = subprocess.run([sys.executable, script_path], capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr

def test_phase14_master_validation():
    print("======================================================================")
    print("PHASE 14: MASTER REGRESSION AND END-TO-END VALIDATION SUITE")
    print("======================================================================")
    
    tests = [
        ("Phase 1: Merged 'My Request' & 'Pending Request'", "scratch/test_phase1_merge_my_requests.py"),
        ("Phase 2: Merged Work-Status Tabs (Approved, Active, Completed, Overdue)", "scratch/test_phase2_merge_work_status.py"),
        ("Phase 3: Department Overview as Default Landing Page", "scratch/test_phase3_department_overview_default.py"),
        ("Phase 4: Department Overview Content Order (Corridor -> Map -> Analytics)", "scratch/test_phase4_department_overview_order.py"),
        ("Phase 5: Restored Original Map Behavior (7 Divisions + Authentic Trains)", "scratch/test_phase5_map_train_restoration.py"),
        ("Phase 6: Department Map Division + Train Selection Integration", "scratch/test_phase6_department_map_division_train.py"),
        ("Phase 7: Live Control & Map Corridor Synchronization (All 7 Divisions)", "scratch/test_phase7_synchronization.py"),
        ("Phase 8: Removed Unnecessary Division Selector from Controller Overview", "scratch/test_phase8_remove_controller_overview_div_selector.py"),
        ("Phase 9: Eliminated Duplicate Map in Controller Loco Pilot Tab", "scratch/test_phase9_controller_single_map.py"),
        ("Phase 10: Controller Loco Pilot Order (Corridor First -> Map Second)", "scratch/test_phase10_controller_tab_order.py"),
        ("Phase 11: Controller Map Division + Train Selection Integration", "scratch/test_phase11_controller_division_train.py"),
        ("Phase 12: Unified Map & Corridor Subsystem Architecture", "scratch/test_phase12_unified_map_subsystem.py"),
        ("Phase 13: Full Navigation Structure Audit (Departments + Controller)", "scratch/test_phase13_structure_audit.py")
    ]
    
    passed_count = 0
    for name, script in tests:
        success, out, err = run_test(script)
        if success:
            passed_count += 1
            print(f"[PASS] {name}")
        else:
            print(f"[FAIL] {name}")
            print("--- Output ---")
            print(out)
            print("--- Error ---")
            print(err)
            
    print("======================================================================")
    print(f"MASTER VALIDATION RESULT: {passed_count}/{len(tests)} PHASES PASSED")
    print("======================================================================")
    
    assert passed_count == len(tests), f"Failed {len(tests) - passed_count} test(s)"

if __name__ == "__main__":
    test_phase14_master_validation()
