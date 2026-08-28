"""
scripts/fetch_firms.py

Fetches NASA FIRMS active fire detections (VIIRS SNPP NRT) for the last 7 days
over Northwest India (Punjab, Haryana, Delhi NCR, Uttar Pradesh) and enriches
the detections with state-level classifications.

Outputs:
  - Raw CSV: data/raw/firms_raw.csv
  - Enriched CSV: data/raw/firms_processed.csv

Note: NASA FIRMS Area API restricts single requests to a maximum of 5 days (day_range in [1..5]).
This script automatically batches requests to cover the full 7-day window.
"""

import io
import os
import sys
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
# Bounding box: west, south, east, north
BBOX = "73,27,84,33"
SOURCE = "VIIRS_SNPP_NRT"
BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

OUTPUT_DIR = Path("data/raw")
RAW_CSV = OUTPUT_DIR / "firms_raw.csv"
PROCESSED_CSV = OUTPUT_DIR / "firms_processed.csv"


def classify_state(lat, lon):
    """
    Classify geographic coordinates into Indian states / regions
    using approximate bounding boxes.
    """
    # 1. Delhi NCR (checked first due to overlapping boundaries)
    if 28.38 <= lat <= 28.92 and 76.82 <= lon <= 77.40:
        return "Delhi"

    # 2. Punjab
    if 29.50 <= lat <= 32.55 and 73.80 <= lon <= 76.95:
        return "Punjab"

    # 3. Haryana
    if 27.65 <= lat <= 30.95 and 74.40 <= lon <= 77.60:
        return "Haryana"

    # 4. Uttar Pradesh
    if 23.80 <= lat <= 30.50 and 77.10 <= lon <= 84.65:
        return "Uttar Pradesh"

    return "Other"


def fetch_firms_batch(map_key, days=5, start_date=None):
    """
    Fetch a batch of fire detections from NASA FIRMS Area API.
    NASA FIRMS limits day_range to max 5 days per call.
    """
    if start_date:
        url = f"{BASE_URL}/{map_key}/{SOURCE}/{BBOX}/{days}/{start_date}"
    else:
        url = f"{BASE_URL}/{map_key}/{SOURCE}/{BBOX}/{days}"

    try:
        response = requests.get(url, timeout=30)
    except requests.exceptions.Timeout:
        print("Error: NASA FIRMS API request timed out after 30 seconds.")
        return None
    except requests.exceptions.RequestException as e:
        safe_err = str(e).replace(map_key, "***MASKED***")
        print(f"Error: Network error while connecting to NASA FIRMS API: {safe_err}")
        return None

    if response.status_code != 200:
        safe_msg = response.text.replace(map_key, "***MASKED***")[:300]
        print(f"Error: NASA FIRMS API returned HTTP {response.status_code} - {safe_msg}")
        return None

    content = response.text.strip()
    if content.startswith("Invalid MAP_KEY") or ("invalid" in content.lower() and len(content) < 100):
        print("Error: NASA FIRMS rejected the MAP_KEY as invalid or unauthorized.")
        return None

    return response.text


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    load_dotenv()

    map_key = os.getenv("FIRMS_MAP_KEY")
    if not map_key or not map_key.strip():
        print("Error: FIRMS_MAP_KEY is missing from the .env file.")
        print("Please add your NASA FIRMS map key to .env: FIRMS_MAP_KEY=your_key")
        sys.exit(1)

    map_key = map_key.strip()
    today = date.today()
    prior_date = (today - timedelta(days=7)).isoformat()

    print("Fetching NASA FIRMS fire detections (last 7 days) for Northwest India...")
    
    # NASA FIRMS limits single requests to 5 days max.
    # We make two 5-day requests to seamlessly cover the full 7-day window:
    # 1. Starting 7 days ago (5 days)
    # 2. Most recent 5 days
    csv_chunks = []
    
    batch1 = fetch_firms_batch(map_key, days=5, start_date=prior_date)
    if batch1 and len(batch1.splitlines()) > 1:
        csv_chunks.append(batch1)

    batch2 = fetch_firms_batch(map_key, days=5)
    if batch2 and len(batch2.splitlines()) > 1:
        csv_chunks.append(batch2)

    if not csv_chunks:
        print("Error: Could not retrieve fire detections from NASA FIRMS.")
        sys.exit(1)

    # Combine CSV data and deduplicate
    dfs = []
    for chunk in csv_chunks:
        try:
            df_part = pd.read_csv(io.StringIO(chunk))
            dfs.append(df_part)
        except Exception as e:
            print(f"Warning: Could not parse a CSV chunk: {e}")

    if not dfs:
        print("No valid fire data parsed.")
        sys.exit(1)

    df_combined = pd.concat(dfs, ignore_index=True)
    
    # Deduplicate detections
    dedup_cols = [c for c in ["latitude", "longitude", "acq_date", "acq_time"] if c in df_combined.columns]
    if dedup_cols:
        df_combined = df_combined.drop_duplicates(subset=dedup_cols).reset_index(drop=True)

    # 1. Save raw CSV
    df_combined.to_csv(RAW_CSV, index=False)
    print(f"Raw CSV saved -> {RAW_CSV}")

    # 2. Classify state and save enriched version
    df_combined["state"] = df_combined.apply(lambda row: classify_state(row["latitude"], row["longitude"]), axis=1)
    df_combined.to_csv(PROCESSED_CSV, index=False)
    print(f"Enriched CSV saved -> {PROCESSED_CSV}")

    # 3. Print Summary
    total_fires = len(df_combined)
    state_counts = df_combined["state"].value_counts().to_dict()

    print("\n" + "=" * 50)
    print("NASA FIRMS Fire Detection Summary (Last 7 Days)")
    print("=" * 50)
    print(f"Total Fire Detections: {total_fires:,}")
    print("\nBreakdown by State / Region:")
    for state in ["Punjab", "Haryana", "Delhi", "Uttar Pradesh", "Other"]:
        count = state_counts.get(state, 0)
        pct = (count / total_fires * 100) if total_fires > 0 else 0
        print(f"  - {state:15s}: {count:5d} ({pct:5.1f}%)")

    print("\nFirst 5 fire detections:")
    cols_to_show = ["latitude", "longitude", "acq_date", "acq_time", "confidence", "frp", "state"]
    available_cols = [c for c in cols_to_show if c in df_combined.columns]
    print(df_combined[available_cols].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
