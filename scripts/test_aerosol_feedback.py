import sys
import os

# Add the parent directory to sys.path so we can import backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.aerosol_feedback import apply_feedback

def run_tests():
    print("Testing Aerosol-Radiation Feedback PBL Adjustment:")
    print("-" * 50)
    
    test_cases = [
        {"pm25": 200, "wind": 1.5, "pbl": 500, "desc": "High PM2.5, Low Wind (Stagnant)"},
        {"pm25": 50, "wind": 3.0, "pbl": 800, "desc": "Low PM2.5, High Wind (Clear)"},
        {"pm25": 180, "wind": 1.0, "pbl": 600, "desc": "High PM2.5, Very Low Wind (Stagnant)"},
        {"pm25": 160, "wind": 2.5, "pbl": 500, "desc": "High PM2.5, High Wind (Not Stagnant)"}
    ]
    
    for case in test_cases:
        adjusted_pbl = apply_feedback(case["pm25"], case["wind"], case["pbl"])
        print(f"Condition: {case['desc']}")
        print(f"  Inputs: PM2.5 = {case['pm25']}, Wind = {case['wind']}, Initial PBL = {case['pbl']}")
        print(f"  Result: Adjusted PBL = {adjusted_pbl}")
        if adjusted_pbl < case["pbl"]:
            print("  -> PBL was reduced due to aerosol feedback.")
        else:
            print("  -> PBL remained unchanged.")
        print("-" * 50)

if __name__ == "__main__":
    run_tests()
