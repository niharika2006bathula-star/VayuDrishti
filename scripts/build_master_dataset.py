"""
scripts/build_master_dataset.py

Merges all raw data sources into one clean modeling dataset:
  1. OpenAQ Station-Level PM2.5 (resampled to hourly mean)
  2. Open-Meteo Regional Weather (hourly temperature, humidity, wind, pressure, precipitation, BLH)
  3. NASA FIRMS Active Fire Counts (daily counts for Punjab, Haryana, UP, Delhi)
  4. Derived Temporal Features (hour, day, month, day_of_week)

Saves the result to: data/processed/master_dataset.csv
"""

from pathlib import Path
import pandas as pd
import numpy as np

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

OPENAQ_CSV = RAW_DIR / "openaq_historical_pm25.csv"
WEATHER_CSV = RAW_DIR / "openmeteo_historical_delhi.csv"
FIRMS_CSV = RAW_DIR / "firms_processed.csv"
OUTPUT_CSV = PROCESSED_DIR / "master_dataset.csv"


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 65)
    print("VayuDrishti: Building Master Modeling Dataset")
    print("=" * 65)

    # -------------------------------------------------------------------------
    # Step 1 & 2: Load OpenAQ PM2.5 & Resample to Hourly
    # -------------------------------------------------------------------------
    print("\n[Step 1 & 2] Loading & Resampling OpenAQ PM2.5 Data...")
    if not OPENAQ_CSV.exists():
        raise FileNotFoundError(f"Missing required file: {OPENAQ_CSV}")

    df_aq = pd.read_csv(OPENAQ_CSV)
    print(f"  - Loaded raw PM2.5 records: {len(df_aq):,}")

    # Convert timestamp to timezone-aware IST (Asia/Kolkata) and floor to hour
    df_aq["dt_ist"] = pd.to_datetime(df_aq["timestamp"], utc=True).dt.tz_convert("Asia/Kolkata")
    df_aq["timestamp_hour"] = df_aq["dt_ist"].dt.floor("h")

    # Resample to hourly mean per station
    df_hourly_aq = (
        df_aq.groupby(["station_name", "city", "latitude", "longitude", "timestamp_hour"], as_index=False)
        .agg({"pm25_value": "mean"})
    )
    # Format timestamp as clean ISO string without timezone offset for unified merging
    df_hourly_aq["time_str"] = df_hourly_aq["timestamp_hour"].dt.strftime("%Y-%m-%d %H:00:00")
    print(f"  - Resampled to hourly station rows: {len(df_hourly_aq):,}")

    # -------------------------------------------------------------------------
    # Step 3 & 4: Load Open-Meteo Weather & Merge
    # -------------------------------------------------------------------------
    print("\n[Step 3 & 4] Loading & Merging Open-Meteo Weather Data...")
    if not WEATHER_CSV.exists():
        raise FileNotFoundError(f"Missing required file: {WEATHER_CSV}")

    df_weather = pd.read_csv(WEATHER_CSV)
    print(f"  - Loaded weather hourly rows: {len(df_weather):,}")

    # Ensure time column matches 'YYYY-MM-DD HH:00:00'
    df_weather["time_str"] = pd.to_datetime(df_weather["time"]).dt.strftime("%Y-%m-%d %H:00:00")
    
    weather_cols = [
        "temperature_2m",
        "relative_humidity_2m",
        "wind_speed_10m",
        "wind_direction_10m",
        "surface_pressure",
        "precipitation",
        "boundary_layer_height"
    ]

    # Forward-fill small weather gaps (<= 2 hours) on the weather source
    df_weather[weather_cols] = df_weather[weather_cols].interpolate(method="linear", limit=2)
    df_weather[weather_cols] = df_weather[weather_cols].ffill(limit=2)

    # Merge PM2.5 with weather
    df_merged = pd.merge(
        df_hourly_aq,
        df_weather[["time_str"] + weather_cols],
        on="time_str",
        how="left"
    )
    print(f"  - Merged AQ + Weather rows: {len(df_merged):,}")

    # -------------------------------------------------------------------------
    # Step 5 & 6: Load NASA FIRMS Fire Detections & Aggregate Daily Counts
    # -------------------------------------------------------------------------
    print("\n[Step 5 & 6] Loading & Merging NASA FIRMS Fire Counts...")
    fire_daily = pd.DataFrame(columns=["date_str", "fire_count_punjab", "fire_count_haryana", "fire_count_up", "fire_count_delhi"])

    if FIRMS_CSV.exists():
        df_firms = pd.read_csv(FIRMS_CSV)
        print(f"  - Loaded active fire detections: {len(df_firms):,}")

        if not df_firms.empty and "acq_date" in df_firms.columns and "state" in df_firms.columns:
            # Pivot daily state counts
            state_piv = (
                df_firms.groupby(["acq_date", "state"])
                .size()
                .unstack(fill_value=0)
                .reset_index()
            )
            state_piv = state_piv.rename(columns={"acq_date": "date_str"})
            
            # Standardize column names
            state_piv["fire_count_punjab"] = state_piv.get("Punjab", 0)
            state_piv["fire_count_haryana"] = state_piv.get("Haryana", 0)
            state_piv["fire_count_up"] = state_piv.get("Uttar Pradesh", 0)
            state_piv["fire_count_delhi"] = state_piv.get("Delhi", 0)
            
            fire_daily = state_piv[["date_str", "fire_count_punjab", "fire_count_haryana", "fire_count_up", "fire_count_delhi"]]
    else:
        print("  - [Note] firms_processed.csv not found; defaulting fire counts to 0.")

    # Extract date string for merging daily fires
    df_merged["date_str"] = df_merged["timestamp_hour"].dt.strftime("%Y-%m-%d")

    df_merged = pd.merge(df_merged, fire_daily, on="date_str", how="left")
    
    # Fill fire counts with 0 for days where no fires occurred
    fire_cols = ["fire_count_punjab", "fire_count_haryana", "fire_count_up", "fire_count_delhi"]
    df_merged[fire_cols] = df_merged[fire_cols].fillna(0).astype(int)

    # -------------------------------------------------------------------------
    # Step 7: Add Derived Temporal Features
    # -------------------------------------------------------------------------
    print("\n[Step 7] Generating Derived Time Features...")
    dt_series = df_merged["timestamp_hour"]
    df_merged["hour"] = dt_series.dt.hour
    df_merged["day"] = dt_series.dt.day
    df_merged["month"] = dt_series.dt.month
    df_merged["day_of_week"] = dt_series.dt.dayofweek  # 0=Monday, 6=Sunday

    # -------------------------------------------------------------------------
    # Step 8: Handle Missing Values & Cleanup
    # -------------------------------------------------------------------------
    print("\n[Step 8] Missing Value Inspection & Handling...")
    initial_count = len(df_merged)
    missing_pm25 = df_merged["pm25_value"].isna().sum()
    missing_weather = df_merged[weather_cols].isna().any(axis=1).sum()

    print(f"  - Rows with missing PM2.5 : {missing_pm25:,}")
    print(f"  - Rows with missing Weather: {missing_weather:,}")

    # Drop rows without PM2.5 (target variable)
    df_clean = df_merged.dropna(subset=["pm25_value"]).copy()

    # Drop rows where weather is still missing after 2h forward fill
    df_clean = df_clean.dropna(subset=weather_cols).copy()

    dropped_count = initial_count - len(df_clean)
    print(f"  - Total rows dropped due to missing values: {dropped_count:,}")

    # Rename timestamp column for clarity
    df_clean = df_clean.rename(columns={"time_str": "timestamp"})

    # Order columns logically
    final_cols = [
        "station_name",
        "city",
        "latitude",
        "longitude",
        "timestamp",
        "pm25_value",
        # Weather features
        "temperature_2m",
        "relative_humidity_2m",
        "wind_speed_10m",
        "wind_direction_10m",
        "surface_pressure",
        "precipitation",
        "boundary_layer_height",
        # Fire features
        "fire_count_punjab",
        "fire_count_haryana",
        "fire_count_up",
        "fire_count_delhi",
        # Temporal features
        "hour",
        "day",
        "month",
        "day_of_week"
    ]

    df_final = df_clean[final_cols].sort_values(by=["station_name", "timestamp"]).reset_index(drop=True)

    # -------------------------------------------------------------------------
    # Step 9: Save Processed Dataset
    # -------------------------------------------------------------------------
    df_final.to_csv(OUTPUT_CSV, index=False)
    print(f"\n[Step 9] Master dataset successfully saved -> {OUTPUT_CSV}")

    # -------------------------------------------------------------------------
    # Step 10: Print Final Dataset Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("Master Dataset Summary")
    print("=" * 65)
    print(f"Total Rows           : {len(df_final):,}")
    print(f"Total Columns        : {len(df_final.columns)}")
    print(f"Unique Stations      : {df_final['station_name'].nunique()}")
    print(f"Date Range Covered   : {df_final['timestamp'].min()} -> {df_final['timestamp'].max()}")
    print(f"Columns List         : {list(df_final.columns)}")

    print("\nFirst 5 Rows:")
    print(df_final.head(5).to_string(index=False))


if __name__ == "__main__":
    main()
