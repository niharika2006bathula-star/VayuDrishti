"""
scripts/fetch_openaq_historical.py

Fetches historical PM2.5 hourly/sub-hourly measurements for active Delhi NCR
monitoring stations from the OpenAQ API v3 for the past 90 days.

Outputs:
  - CSV: data/raw/openaq_historical_pm25.csv
    Columns: station_name, city, latitude, longitude, timestamp, pm25_value
"""

import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BASE_URL = "https://api.openaq.org/v3"
OUTPUT_DIR = Path("data/raw")
RAW_LOCATIONS_FILE = OUTPUT_DIR / "openaq_raw.json"
OUTPUT_CSV = OUTPUT_DIR / "openaq_historical_pm25.csv"

# 90-day historical window matching Open-Meteo weather dataset
DAYS_LOOKBACK = 90

# Rate limiting
REQUEST_DELAY_SEC = 0.6  # delay between successive API calls
MAX_RETRIES = 3


def get_headers():
    load_dotenv()
    api_key = os.getenv("OPENAQ_API_KEY")
    if not api_key or not api_key.strip():
        print("Error: OPENAQ_API_KEY is missing from .env.")
        print("Please add your OpenAQ v3 key: OPENAQ_API_KEY=your_key")
        sys.exit(1)
    return {
        "Accept": "application/json",
        "User-Agent": "VayuDrishti/1.0",
        "X-API-Key": api_key.strip()
    }


def load_active_stations(headers):
    """
    Load active Delhi NCR stations (reporting within last 30 days).
    Uses data/raw/openaq_raw.json if present, or queries /v3/locations.
    """
    data = None
    if RAW_LOCATIONS_FILE.exists():
        try:
            with open(RAW_LOCATIONS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = None

    if not data:
        print(f"Querying Delhi NCR stations from {BASE_URL}/locations...")
        try:
            r = requests.get(
                f"{BASE_URL}/locations",
                headers=headers,
                params={"bbox": "76.8,28.2,77.6,28.9", "limit": 100},
                timeout=25
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                data = []
                for loc in results:
                    data.append({
                        "location_id": loc.get("id"),
                        "location_name": loc.get("name"),
                        "locality": loc.get("locality"),
                        "sensors": loc.get("sensors", []),
                        "data": []
                    })
        except Exception as e:
            print(f"Error fetching locations: {e}")
            return []

    now_utc = datetime.now(timezone.utc)
    active_stations = []

    for loc in data:
        readings = loc.get("data", [])
        # Check staleness if readings present
        is_active = True
        coords = None

        if readings:
            latest_timestamps = [
                r.get("datetime", {}).get("utc") if isinstance(r.get("datetime"), dict) else r.get("datetime")
                for r in readings
            ]
            valid_ts = [ts for ts in latest_timestamps if ts]
            if valid_ts:
                try:
                    max_ts = pd.to_datetime(max(valid_ts), utc=True)
                    if (now_utc - max_ts).days > 30:
                        is_active = False
                except Exception:
                    pass

            for r in readings:
                if r.get("coordinates"):
                    coords = r.get("coordinates")
                    break

        if not is_active:
            continue

        # Extract PM2.5 sensors (prefer newest sensor IDs first)
        pm25_sensors = []
        for s in loc.get("sensors", []):
            s_id = s.get("id")
            p_obj = s.get("parameter") or {}
            p_name = p_obj.get("name") or s.get("name") or ""
            if "pm25" in str(p_name).lower() or p_name == "pm25":
                pm25_sensors.append(s_id)

        # Sort descending so newest sensors are queried first
        pm25_sensors.sort(reverse=True)

        if pm25_sensors:
            active_stations.append({
                "id": loc.get("location_id"),
                "name": loc.get("location_name", "Unknown Station"),
                "city": loc.get("locality") or "Delhi NCR",
                "latitude": coords.get("latitude") if coords else None,
                "longitude": coords.get("longitude") if coords else None,
                "pm25_sensors": pm25_sensors
            })

    return active_stations


def fetch_sensor_measurements(sensor_id, start_dt, end_dt, headers):
    """
    Fetch all historical measurements for a sensor within date range,
    handling pagination and rate limits.
    """
    records = []
    page = 1
    max_pages = 10  # safety cap up to 10,000 records per sensor

    while page <= max_pages:
        url = f"{BASE_URL}/sensors/{sensor_id}/measurements"
        params = {
            "datetime_from": start_dt,
            "datetime_to": end_dt,
            "limit": 1000,
            "page": page
        }

        resp = None
        for attempt in range(MAX_RETRIES):
            try:
                time.sleep(REQUEST_DELAY_SEC)
                resp = requests.get(url, headers=headers, params=params, timeout=20)
                if resp.status_code == 200:
                    break
                elif resp.status_code == 429:
                    wait_time = (attempt + 1) * 4
                    print(f"    [Rate limit 429] Sensor {sensor_id}, page {page}: backing off for {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    break
            except requests.exceptions.RequestException as e:
                time.sleep(2)
                if attempt == MAX_RETRIES - 1:
                    print(f"    [Network warning] Sensor {sensor_id} page {page}: {e}")

        if not resp or resp.status_code != 200:
            break

        try:
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break

            for r in results:
                val = r.get("value")
                # Extract timestamp
                p_period = r.get("period") or {}
                dt_from = p_period.get("datetimeFrom") or {}
                ts = dt_from.get("utc") if isinstance(dt_from, dict) else None
                if not ts:
                    ts = r.get("datetime", {}).get("utc") if isinstance(r.get("datetime"), dict) else r.get("datetime")
                
                # Extract coordinates if present
                coords = r.get("coordinates") or {}

                if ts and val is not None:
                    records.append({
                        "timestamp": ts,
                        "value": val,
                        "lat": coords.get("latitude"),
                        "lon": coords.get("longitude")
                    })

            if len(results) < 1000:
                # Reached last page
                break

            page += 1

        except Exception as e:
            print(f"    [JSON parse error] Sensor {sensor_id}: {e}")
            break

    return records


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    headers = get_headers()

    # 1. Determine date range
    end_date = date.today()
    start_date = end_date - timedelta(days=DAYS_LOOKBACK)
    start_dt_str = f"{start_date.isoformat()}T00:00:00Z"
    end_dt_str = f"{end_date.isoformat()}T23:59:59Z"

    print("=" * 60)
    print("OpenAQ Historical PM2.5 Fetcher (Last 90 Days)")
    print("=" * 60)
    print(f"Target date window : {start_dt_str} -> {end_dt_str}")

    # 2. Identify active stations
    stations = load_active_stations(headers)
    print(f"Active stations found with PM2.5 sensors: {len(stations)}\n")

    if not stations:
        print("No active stations found to query.")
        sys.exit(0)

    all_rows = []
    stations_with_data = 0

    # 3. Fetch PM2.5 measurements per station
    for idx, st in enumerate(stations, 1):
        st_name = st["name"]
        st_city = st["city"]
        st_lat = st["latitude"]
        st_lon = st["longitude"]
        pm25_sensor_ids = st["pm25_sensors"]

        print(f"[{idx}/{len(stations)}] Querying: {st_name} (Sensors: {pm25_sensor_ids})")

        station_records = []
        for s_id in pm25_sensor_ids:
            try:
                rec = fetch_sensor_measurements(s_id, start_dt_str, end_dt_str, headers)
                if rec:
                    station_records.extend(rec)
                    # If primary active sensor yielded data, we don't necessarily need older archived sensors
                    if len(rec) >= 100:
                        break
            except Exception as e:
                print(f"    Warning: Error fetching sensor {s_id} for {st_name}: {e}")

        if station_records:
            stations_with_data += 1
            print(f"    -> Collected {len(station_records):,} PM2.5 measurements")
            for r in station_records:
                lat = r["lat"] if r["lat"] is not None else st_lat
                lon = r["lon"] if r["lon"] is not None else st_lon
                all_rows.append({
                    "station_name": st_name,
                    "city": st_city,
                    "latitude": lat,
                    "longitude": lon,
                    "timestamp": r["timestamp"],
                    "pm25_value": r["value"]
                })
        else:
            print("    -> No records in the 90-day window")

    # 4. Save and summarize DataFrame
    print("\n" + "=" * 60)
    print("Summary of Data Collection")
    print("=" * 60)
    print(f"Total stations queried          : {len(stations)}")
    print(f"Stations with historical data   : {stations_with_data}")
    print(f"Total PM2.5 records collected   : {len(all_rows):,}")

    if not all_rows:
        print("No historical PM2.5 records retrieved across stations.")
        sys.exit(0)

    df = pd.DataFrame(all_rows)

    # Clean & Deduplicate
    df = df.dropna(subset=["timestamp", "pm25_value"])
    df = df.drop_duplicates(subset=["station_name", "timestamp"]).sort_values(by="timestamp").reset_index(drop=True)

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Historical PM2.5 dataset saved  -> {OUTPUT_CSV}")

    # Timestamp coverage
    min_ts = df["timestamp"].min()
    max_ts = df["timestamp"].max()
    print(f"Actual timestamp coverage       : {min_ts} -> {max_ts}")
    print(f"Final deduplicated rows         : {len(df):,}")

    print("\nFirst 5 rows:")
    print(df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
