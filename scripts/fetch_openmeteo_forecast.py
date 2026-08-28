"""
scripts/fetch_openmeteo_forecast.py

Fetches a 3-day (72-hour) forecast for Delhi NCR from the
Open-Meteo Forecast API (no API key required) and saves the raw
response as JSON and a clean DataFrame as CSV.

Usage:
    python scripts/fetch_openmeteo_forecast.py
"""

import json
import sys
from pathlib import Path
import pandas as pd
import requests

# ── Configuration ─────────────────────────────────────────────────────────────
LAT = 28.6139
LON = 77.2090
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
    "precipitation",
    "boundary_layer_height",
]

OUTPUT_DIR = Path("data/raw")
JSON_OUT = OUTPUT_DIR / "openmeteo_forecast_delhi.json"
CSV_OUT = OUTPUT_DIR / "openmeteo_forecast_delhi.csv"
# ─────────────────────────────────────────────────────────────────────────────


def fetch_forecast_data() -> dict:
    """Make the API request to Open-Meteo Forecast API."""
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": ",".join(HOURLY_VARS),
        "forecast_days": 3,
        "timezone": "UTC"
    }

    print(f"Requesting Open-Meteo 72-hour forecast for Delhi ({LAT}, {LON}) ...")
    try:
        resp = requests.get(FORECAST_URL, params=params, timeout=30)
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to Open-Meteo API. Check your internet connection.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Error: Open-Meteo API timed out after 30s.")
        sys.exit(1)
    except requests.exceptions.RequestException as exc:
        print(f"Error: Network error - {exc}")
        sys.exit(1)

    print(f"HTTP Status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error: API returned HTTP {resp.status_code}.")
        try:
            err = resp.json()
            print(f"API reason: {err.get('reason', resp.text[:300])}")
        except Exception:
            print(f"Response: {resp.text[:300]}")
        sys.exit(1)

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print("Error: Could not parse response as JSON.")
        sys.exit(1)

    if "hourly" not in data:
        print("Error: 'hourly' key missing from response.")
        sys.exit(1)

    return data


def build_dataframe(data: dict) -> pd.DataFrame:
    """Convert the Open-Meteo hourly dict into a tidy DataFrame."""
    hourly = data["hourly"]
    df = pd.DataFrame(hourly)
    
    # Standardize timestamp
    df["timestamp"] = pd.to_datetime(df["time"])
    # Reorder columns
    cols = ["timestamp"] + [c for c in HOURLY_VARS if c in df.columns]
    df = df[cols].head(72).reset_index(drop=True)
    return df


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Fetch
    data = fetch_forecast_data()

    # 2. Save raw JSON
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Raw JSON saved  -> {JSON_OUT}")

    # 3. Build & save CSV
    df = build_dataframe(data)
    df.to_csv(CSV_OUT, index=False)
    print(f"Clean CSV saved -> {CSV_OUT}")

    # 4. Summary Output
    print(f"\nDate range covered : {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"Total hourly rows  : {len(df):,}")
    print(f"Columns            : {list(df.columns)}\n")
    print("First 5 rows:")
    print(df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
