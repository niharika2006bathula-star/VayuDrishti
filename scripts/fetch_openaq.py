"""
scripts/fetch_openaq.py

Fetches current air quality data for Delhi NCR (Delhi, Noida, Ghaziabad, Gurugram, Faridabad)
from the OpenAQ API v3.

Saves:
  - Raw JSON: data/raw/openaq_raw.json
  - Cleaned CSV: data/raw/openaq_raw.csv (columns: location, city, parameter, value, unit, timestamp)

Includes sensor parameter mapping from location metadata and filters / warns on stale data (>30 days old).
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BASE_URL = "https://api.openaq.org/v3"

# Delhi NCR Bounding Box: [min_lon, min_lat, max_lon, max_lat]
NCR_BBOX = "76.8,28.2,77.6,28.9"

OUTPUT_DIR = Path("data/raw")
JSON_OUT = OUTPUT_DIR / "openaq_raw.json"
CSV_OUT = OUTPUT_DIR / "openaq_raw.csv"


def get_headers():
    load_dotenv()
    api_key = os.getenv("OPENAQ_API_KEY")
    if api_key:
        api_key = api_key.strip()
    headers = {
        "Accept": "application/json",
        "User-Agent": "VayuDrishti/1.0"
    }
    if api_key:
        headers["X-API-Key"] = api_key
    return headers, api_key


def fetch_ncr_locations(headers):
    """Fetch air monitoring stations in Delhi NCR."""
    url = f"{BASE_URL}/locations"
    params = {
        "bbox": NCR_BBOX,
        "limit": 100
    }
    print(f"Fetching stations in Delhi NCR from {url}...")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=25)
    except requests.exceptions.RequestException as e:
        print(f"Network error while connecting to OpenAQ: {e}")
        return None

    if response.status_code == 401:
        print("\n[HTTP 401 Unauthorized]")
        print("OpenAQ v3 requires a free API key.")
        print("1. Sign up for free at: https://explore.openaq.org/register")
        print("2. Add OPENAQ_API_KEY=your_key in your .env file.")
        return None
    elif response.status_code != 200:
        print(f"Error: OpenAQ API returned HTTP {response.status_code}")
        print(f"Response: {response.text[:300]}")
        return None

    try:
        data = response.json()
        return data.get("results", [])
    except json.JSONDecodeError:
        print("Error: Failed to parse JSON response from OpenAQ.")
        return None


def fetch_latest_measurements(location_id, headers):
    """Fetch latest measurements for a specific location."""
    url = f"{BASE_URL}/locations/{location_id}/latest"
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json().get("results", [])
    except requests.exceptions.RequestException:
        pass
    return []


def determine_city(loc_name, locality):
    """Extract city name from locality or location name."""
    if locality and locality.strip():
        return locality.strip()
    name_lower = (loc_name or "").lower()
    for city in ["delhi", "noida", "ghaziabad", "gurugram", "gurgaon", "faridabad"]:
        if city in name_lower:
            return city.capitalize() if city != "delhi" else "Delhi"
    return "Delhi NCR"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    headers, api_key = get_headers()

    if not api_key:
        print("[Info] OPENAQ_API_KEY not found in .env. Attempting request without key...")

    locations = fetch_ncr_locations(headers)
    if locations is None:
        sys.exit(1)

    if not locations:
        print("No monitoring locations returned for Delhi NCR bounding box.")
        sys.exit(0)

    print(f"Found {len(locations)} monitoring stations in Delhi NCR. Fetching latest readings...")

    all_raw_data = []
    cleaned_records = []
    now_utc = datetime.now(timezone.utc)

    # Process locations
    for loc in locations:
        loc_id = loc.get("id")
        loc_name = loc.get("name", "Unknown")
        loc_city = determine_city(loc_name, loc.get("locality"))

        # Build sensor lookup map: sensorsId -> {parameter, units}
        sensor_map = {}
        for sensor in loc.get("sensors", []):
            s_id = sensor.get("id")
            p_obj = sensor.get("parameter") or {}
            param_name = p_obj.get("name") or sensor.get("name")
            unit = p_obj.get("units")
            sensor_map[s_id] = {
                "parameter": param_name,
                "unit": unit
            }

        readings = fetch_latest_measurements(loc_id, headers)
        if not readings:
            continue

        all_raw_data.append({
            "location_id": loc_id,
            "location_name": loc_name,
            "locality": loc_city,
            "sensors": loc.get("sensors", []),
            "data": readings
        })

        for r in readings:
            s_id = r.get("sensorsId")
            s_info = sensor_map.get(s_id, {})
            
            # Timestamp parsing
            dt_obj = r.get("datetime") or {}
            timestamp_str = dt_obj.get("utc") if isinstance(dt_obj, dict) else dt_obj

            cleaned_records.append({
                "location": loc_name,
                "city": loc_city,
                "parameter": s_info.get("parameter"),
                "value": r.get("value"),
                "unit": s_info.get("unit"),
                "timestamp": timestamp_str
            })

    # Save raw JSON
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(all_raw_data, f, indent=2)
    print(f"Raw response saved -> {JSON_OUT}")

    if not cleaned_records:
        print("No measurement records found across stations.")
        sys.exit(0)

    # Build DataFrame
    df = pd.DataFrame(cleaned_records, columns=["location", "city", "parameter", "value", "unit", "timestamp"])

    # Calculate staleness
    df["dt_parsed"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    stale_mask = (now_utc - df["dt_parsed"]).dt.days > 30
    stale_count = stale_mask.sum()
    active_count = len(df) - stale_count

    print(f"\nTotal records fetched: {len(df)}")
    print(f"Active records (<= 30 days old): {active_count}")
    print(f"Stale records (> 30 days old): {stale_count}")

    if stale_count > 0:
        print(f"\n[Warning] {stale_count} records are from inactive/stale monitoring stations (>30 days old).")

    # Filter out stale records for the primary clean dataset, or sort by latest
    # We will keep active records in CSV and sort by most recent timestamp
    df_clean = df[~stale_mask].drop(columns=["dt_parsed"]).reset_index(drop=True)
    
    # Save CSV
    df_clean.to_csv(CSV_OUT, index=False)
    print(f"Active cleaned data saved ({len(df_clean)} rows) -> {CSV_OUT}")

    print("\nFirst 10 rows of cleaned data:")
    print(df_clean.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
