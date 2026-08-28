"""
scripts/fetch_openmeteo_historical.py

Fetches the last 90 days of hourly weather data for Delhi (NCR) from the
Open-Meteo Historical Weather API (no API key required) and saves the raw
response as JSON and a clean DataFrame as CSV.

Usage:
    python scripts/fetch_openmeteo_historical.py
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

# ── Config ────────────────────────────────────────────────────────────────────
LAT = 28.6139
LON = 77.2090
BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

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
JSON_OUT = OUTPUT_DIR / "openmeteo_historical_delhi.json"
CSV_OUT  = OUTPUT_DIR / "openmeteo_historical_delhi.csv"
# ─────────────────────────────────────────────────────────────────────────────


def fetch_data(start: date, end: date) -> dict:
    """Make the API request and return the parsed JSON response."""
    params = {
        "latitude":  LAT,
        "longitude": LON,
        "start_date": start.isoformat(),
        "end_date":   end.isoformat(),
        "hourly":     ",".join(HOURLY_VARS),
        "timezone":   "Asia/Kolkata",
    }

    print(f"Requesting Open-Meteo archive for {start} -> {end} ...")
    try:
        resp = requests.get(BASE_URL, params=params, timeout=30)
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the Open-Meteo API. Check your internet connection.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Error: The request to Open-Meteo timed out after 30 s.")
        sys.exit(1)
    except requests.exceptions.RequestException as exc:
        print(f"Error: Unexpected network error — {exc}")
        sys.exit(1)

    print(f"HTTP Status: {resp.status_code}")

    if resp.status_code != 200:
        print(f"Error: API returned status {resp.status_code}.")
        try:
            err = resp.json()
            print(f"API message: {err.get('reason', resp.text[:300])}")
        except Exception:
            print(f"Raw response: {resp.text[:300]}")
        sys.exit(1)

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print("Error: Could not parse the API response as JSON.")
        print(f"Raw response (first 300 chars): {resp.text[:300]}")
        sys.exit(1)

    if "hourly" not in data:
        print("Error: 'hourly' key missing from API response. Unexpected format.")
        print(f"Top-level keys returned: {list(data.keys())}")
        sys.exit(1)

    return data


def build_dataframe(data: dict) -> pd.DataFrame:
    """Convert the Open-Meteo hourly dict into a tidy DataFrame."""
    hourly = data["hourly"]

    missing = [v for v in ["time"] + HOURLY_VARS if v not in hourly]
    if missing:
        print(f"Warning: The following expected columns are missing from the response: {missing}")

    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df = df.set_index("time").sort_index()
    return df


def main() -> None:
    # -- Ensure output directory exists ----------------------------------------
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # -- Compute date window ---------------------------------------------------
    end_date   = date.today() - timedelta(days=1)   # yesterday (archive is complete)
    start_date = end_date - timedelta(days=89)       # 90-day window

    # -- Fetch -----------------------------------------------------------------
    data = fetch_data(start_date, end_date)

    # -- Save raw JSON ---------------------------------------------------------
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Raw JSON saved  -> {JSON_OUT}")

    # -- Build & save CSV ------------------------------------------------------
    df = build_dataframe(data)
    df.to_csv(CSV_OUT)
    print(f"Clean CSV saved -> {CSV_OUT}")

    # -- Summary ---------------------------------------------------------------
    print(f"\nDate range covered : {df.index.min()} -> {df.index.max()}")
    print(f"Total hourly rows  : {len(df):,}")
    print(f"Columns            : {list(df.columns)}\n")
    print("First 5 rows:")
    print(df.head().to_string())


if __name__ == "__main__":
    main()
