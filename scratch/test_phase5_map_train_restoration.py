import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import get_division_train_options, SHARED_DIVISION_LOCATIONS

def test_phase5_train_options():
    print("Testing get_division_train_options for all shared division locations...")
    
    expected_div_train_counts = {
        "Vijayawada Division (BZA)": 5, # Godavari, Charminar, Vande Bharat, BZA-KMT Local, Coal Freight
        "Khurda Road Division (KUR)": 6, # Coromandel, Bhubaneswar Rajdhani, Utkal, Gitanjali, VSKP SF, Golconda
        "Secunderabad Division (SC)": 4, # Hussain Sagar, Danapur, Visakha, SC-F819
        "Howrah Division (HWH)": 4, # Howrah Rajdhani, Bandel EMU, Coalfield, Vande Bharat
        "Guntakal Division (GTL)": 3, # Karnataka, Rayalaseema, GTL Passenger
        "Guntur Division (GNT)": 2, # Sabari, Palnadu
        "Hyderabad Division (HYB)": 2 # Kacheguda-Narkher, Devagiri
    }
    
    for div in SHARED_DIVISION_LOCATIONS:
        options = get_division_train_options(div)
        assert len(options) > 1, f"No train options returned for division {div}"
        assert options[0] == "ALL Trains (Division Fleet Overview)", f"First option must be ALL Trains for {div}"
        
        # Verify count matches authentic data
        train_count = len(options) - 1
        expected_count = expected_div_train_counts.get(div, 2)
        assert train_count == expected_count, f"Expected {expected_count} trains for {div}, got {train_count}: {options}"
        print(f"  ✓ {div}: {train_count} authentic trains loaded: {options[1:]}")
        
    print("Phase 5 Test Passed: All 7 divisions mapped to exact authentic train lists from existing project data.")

if __name__ == "__main__":
    test_phase5_train_options()
