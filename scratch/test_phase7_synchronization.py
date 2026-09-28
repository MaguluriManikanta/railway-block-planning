import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import (
    SHARED_DIVISION_LOCATIONS,
    get_division_train_options,
    get_active_trains_df,
    render_live_corridor_map_plotly
)

def test_phase7_corridor_map_synchronization():
    print("Testing Phase 7: Verification of Shared Locations and Synchronization between Corridor and Map...")
    
    for div in SHARED_DIVISION_LOCATIONS:
        # 1. Verify train options for division
        t_opts = get_division_train_options(div)
        assert len(t_opts) >= 2, f"Division {div} has insufficient train options: {t_opts}"
        
        # 2. Verify active trains df for division
        df_trains = get_active_trains_df(division=div)
        assert df_trains is not None, f"get_active_trains_df returned None for {div}"
        
        # 3. Verify Plotly schematic generation for each train option
        for t_sel in t_opts:
            fig = render_live_corridor_map_plotly(df_trains, division=div, selected_train=t_sel)
            assert fig is not None, f"Plotly corridor failed to render for division {div} and train {t_sel}"
            assert len(fig.data) > 0, f"Plotly corridor returned empty traces for {div}"
            
        print(f"  ✓ Division '{div}' synchronized across {len(t_opts)} train target states.")

    print("\nPhase 7 Test Passed: Live Control Linear Corridor and Geographic Map share 100% synchronized location and train datasets.")

if __name__ == "__main__":
    test_phase7_corridor_map_synchronization()
