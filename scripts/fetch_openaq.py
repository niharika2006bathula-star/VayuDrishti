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

    # We will keep active records in CSV and sort by most recent timestamp
    df_clean = df[~stale_mask].drop(columns=["dt_parsed"]).reset_index(drop=True)
    
    if len(df_clean) < 10:
        print("\n[Warning] Fetch returned too few valid rows — aborting to protect existing data.")
        sys.exit(1)
        
    # Save CSV
    df_clean.to_csv(CSV_OUT, index=False)
    print(f"Active cleaned data saved ({len(df_clean)} rows) -> {CSV_OUT}")

    # Accumulate into rolling live history log (openaq_live_history.csv)
    LIVE_HISTORY_OUT = OUTPUT_DIR / "openaq_live_history.csv"
    append_to_live_history(df_clean, LIVE_HISTORY_OUT)

    print("\nFirst 10 rows of cleaned data:")
    print(df_clean.head(10).to_string(index=False))


def append_to_live_history(df_clean, live_history_path):
    """
    Appends active station PM2.5 readings to the accumulating live history log.
    Enforces deduplication on (station_name, timestamp) and caps data at 35 days.
    """
    if df_clean.empty or "parameter" not in df_clean.columns:
        return
    
    pm25_mask = df_clean["parameter"].astype(str).str.lower().isin(["pm25", "pm2.5", "pm2_5"])
    pm_df = df_clean[pm25_mask & df_clean["value"].notna()].copy()
    if pm_df.empty:
        return

    new_rows = pd.DataFrame({
        "station_name": pm_df["location"].astype(str).str.strip(),
        "timestamp": pm_df["timestamp"].astype(str).str.strip(),
        "pm25_value": pm_df["value"].astype(float).round(2)
    })
    new_rows = new_rows[(new_rows["timestamp"] != "") & (new_rows["pm25_value"] >= 0)]
    if new_rows.empty:
        return

    now_utc = datetime.now(timezone.utc)
    cutoff_time = now_utc - pd.Timedelta(days=35)

    if live_history_path.exists():
        try:
            existing_df = pd.read_csv(live_history_path)
            if not all(col in existing_df.columns for col in ["station_name", "timestamp", "pm25_value"]):
                existing_df = pd.DataFrame(columns=["station_name", "timestamp", "pm25_value"])
        except Exception:
            existing_df = pd.DataFrame(columns=["station_name", "timestamp", "pm25_value"])
    else:
        existing_df = pd.DataFrame(columns=["station_name", "timestamp", "pm25_value"])

    combined = pd.concat([existing_df, new_rows], ignore_index=True)
    combined["station_name"] = combined["station_name"].astype(str).str.strip()
    combined["timestamp"] = combined["timestamp"].astype(str).str.strip()
    combined = combined.drop_duplicates(subset=["station_name", "timestamp"], keep="last")

    # Safety Cap: keep only last 35 days
    combined["dt_temp"] = pd.to_datetime(combined["timestamp"], errors="coerce", utc=True)
    valid_mask = combined["dt_temp"].notna() & (combined["dt_temp"] >= cutoff_time)
    combined_capped = combined[valid_mask].sort_values("dt_temp").drop(columns=["dt_temp"]).reset_index(drop=True)

    temp_path = live_history_path.with_suffix(".tmp")
    combined_capped.to_csv(temp_path, index=False)
    temp_path.replace(live_history_path)
    print(f"Accumulated live history updated -> {live_history_path} ({len(combined_capped)} total rows, +{len(new_rows)} new/checked)")


if __name__ == "__main__":
    main()

