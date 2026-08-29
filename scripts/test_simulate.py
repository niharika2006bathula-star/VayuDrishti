import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from backend.main import app
import json

client = TestClient(app)

print("Testing /simulate endpoint...")
payload = {
    'pm25': 250,
    'wind_speed': 1.0,
    'wind_direction': 270,
    'temperature': 12,
    'humidity': 85,
    'pbl': 300,
    'precipitation': 0,
    'enable_feedback': True
}

response = client.post("/simulate", json=payload)
if response.status_code == 200:
    data = response.json()
    baseline = data["baseline_forecast"]
    feedback = data["feedback_forecast"]
    print("Baseline:")
    print(baseline)
    print("With Feedback:")
    print(feedback)
    
    diff = sum(1 for b, f in zip(baseline, feedback) if b != f)
    if diff > 0:
        print(f"SUCCESS: The two forecasts differ in {diff} out of {len(baseline)} hours.")
    else:
        print("WARNING: The two forecasts are identical.")
else:
    print("FAILED /simulate", response.status_code, response.text)

print("\nTesting /forecast/Wazirpur endpoint...")
response2 = client.get("/forecast/Wazirpur")
if response2.status_code == 200:
    fc_data = response2.json()
    print(f"SUCCESS: /forecast/Wazirpur returned {len(fc_data['forecast'])} hours.")
else:
    print("FAILED /forecast/Wazirpur", response2.status_code, response2.text)
