"""
backend/main.py

FastAPI backend for VayuDrishti (Delhi NCR Air Pollution & Weather Intelligence System).

Endpoints:
  - GET  /health
  - GET  /stations
  - GET  /current/{station_name}
  - GET  /forecast/{station_name}   (Powered by trained XGBoost model & Open-Meteo 72h forecast)
  - GET  /explain/{station_name}    (SHAP TreeExplainer local attribution for station prediction)
  - GET  /dispersion/{station_name} (Planetary Boundary Layer & Inversion/Dispersion Risk Index)
  - POST /predict                  (Direct ML model inference endpoint)
  - POST /api/predict              (Alias for compatibility)
"""

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse

import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project root is in path to import utils
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils.aqi import pm25_to_aqi

# -----------------------------------------------------------------------------
# App Setup & CORS
# -----------------------------------------------------------------------------
app = FastAPI(
    title="VayuDrishti API",
    description="Delhi NCR Air Pollution, CPCB AQI, Weather & SHAP Intelligence API",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Data Paths & Global Model Loading
# -----------------------------------------------------------------------------
RAW_CSV_PATH = BASE_DIR / "data" / "raw" / "openaq_raw.csv"
RAW_JSON_PATH = BASE_DIR / "data" / "raw" / "openaq_raw.json"
HISTORICAL_CSV_PATH = BASE_DIR / "data" / "raw" / "openaq_historical_pm25.csv"
FORECAST_WEATHER_CSV_PATH = BASE_DIR / "data" / "raw" / "openmeteo_forecast_delhi.csv"
ML_DATASET_PATH = BASE_DIR / "data" / "processed" / "ml_dataset.csv"
MODEL_PATH = BASE_DIR / "models" / "pm25_xgboost_model.pkl"

# Features expected by XGBoost model
MODEL_FEATURES = [
    "pm25_value",
    "pm25_lag_1",
    "pm25_lag_3",
    "pm25_lag_6",
    "pm25_lag_12",
    "pm25_lag_24",
    "pm25_roll_3",
    "pm25_roll_6",
    "pm25_roll_12",
    "pm25_roll_24",
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "wind_sin",
    "wind_cos",
    "surface_pressure",
    "precipitation",
    "boundary_layer_height",
    "fire_count_punjab",
    "fire_count_haryana",
    "fire_count_up",
    "fire_count_delhi",
    "hour",
    "day",
    "month",
    "day_of_week",
    "latitude",
    "longitude"
]

# Load XGBoost Model & Cached SHAP TreeExplainer
xgb_model = None
shap_explainer = None

if MODEL_PATH.exists():
    try:
        xgb_model = joblib.load(MODEL_PATH)
        print(f"[Backend] Successfully loaded ML model from {MODEL_PATH}")
        # Initialize and cache TreeExplainer once at startup
        shap_explainer = shap.TreeExplainer(xgb_model)
        print("[Backend] Successfully initialized and cached SHAP TreeExplainer")
    except Exception as e:
        print(f"[Backend Warning] Could not initialize model or TreeExplainer: {e}")


def get_station_coordinates_map() -> Dict[str, Dict[str, float]]:
    """Build a lookup map of station_name -> {latitude, longitude}."""
    coords_map = {}
    
    if RAW_JSON_PATH.exists():
        try:
            with open(RAW_JSON_PATH, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
                for loc in raw_json:
                    name = loc.get("location_name")
                    for r in loc.get("data", []):
                        if r.get("coordinates") and r["coordinates"].get("latitude"):
                            coords_map[name] = {
                                "latitude": float(r["coordinates"]["latitude"]),
                                "longitude": float(r["coordinates"]["longitude"])
                            }
                            break
        except Exception:
            pass

    if HISTORICAL_CSV_PATH.exists():
        try:
            df_hist = pd.read_csv(HISTORICAL_CSV_PATH, usecols=["station_name", "latitude", "longitude"])
            df_hist = df_hist.dropna().drop_duplicates(subset=["station_name"])
            for _, row in df_hist.iterrows():
                name = str(row["station_name"])
                if name not in coords_map:
                    coords_map[name] = {
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"])
                    }
        except Exception:
            pass

    return coords_map


def load_raw_data() -> pd.DataFrame:
    """Load latest openaq_raw.csv dataset."""
    if not RAW_CSV_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Raw air quality dataset not found. Please run scripts/fetch_openaq.py first."
        )
    try:
        return pd.read_csv(RAW_CSV_PATH)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read raw air quality data: {str(e)}")


def load_forecast_weather() -> Optional[pd.DataFrame]:
    """Load the 72-hour Open-Meteo forecast weather DataFrame if available."""
    if FORECAST_WEATHER_CSV_PATH.exists():
        try:
            df_w = pd.read_csv(FORECAST_WEATHER_CSV_PATH)
            if "wind_direction_10m" in df_w.columns:
                wind_rad = np.radians(df_w["wind_direction_10m"].astype(float))
                df_w["wind_sin"] = np.sin(wind_rad)
                df_w["wind_cos"] = np.cos(wind_rad)
            return df_w
        except Exception as e:
            print(f"[Backend Warning] Could not read forecast weather CSV: {e}")
    return None


def extract_station_current_features(station_name: str) -> tuple[str, str, float, pd.DataFrame]:
    """
    Extracts the current feature vector for a given station name, matching the
    feature construction logic in /forecast.
    Returns: (actual_station_name, city, current_pm25, feature_dataframe)
    """
    decoded_name = urllib.parse.unquote(station_name).strip()
    df_raw = load_raw_data()
    coords_map = get_station_coordinates_map()

    matched = df_raw[df_raw["location"].str.strip().str.lower() == decoded_name.lower()]
    if matched.empty:
        matched = df_raw[df_raw["location"].str.strip().str.lower().str.contains(decoded_name.lower())]

    if not matched.empty:
        actual_name = str(matched["location"].iloc[0])
        city = str(matched["city"].iloc[0]) if "city" in matched.columns else "Delhi NCR"
        pm25_row = matched[matched["parameter"].astype(str).str.lower() == "pm25"]
        baseline_pm25 = float(pm25_row["value"].iloc[0]) if (not pm25_row.empty and pd.notna(pm25_row["value"].iloc[0])) else 50.0
    else:
        actual_name = decoded_name
        city = "Delhi NCR"
        baseline_pm25 = 50.0

    coords = coords_map.get(actual_name, {"latitude": 28.6139, "longitude": 77.2090})
    st_lat = float(coords.get("latitude", 28.6139))
    st_lon = float(coords.get("longitude", 77.2090))

    now_utc = datetime.now(timezone.utc)
    hour_val = now_utc.hour
    day_val = now_utc.day
    month_val = now_utc.month
    dow_val = now_utc.weekday()

    # Weather from forecast file if available
    df_w = load_forecast_weather()
    if df_w is not None and len(df_w) > 0:
        w_row = df_w.iloc[0]
        temp = float(w_row.get("temperature_2m", 28.0))
        humidity = float(w_row.get("relative_humidity_2m", 65.0))
        wind_spd = float(w_row.get("wind_speed_10m", 8.0))
        wind_sin = float(w_row.get("wind_sin", 0.0))
        wind_cos = float(w_row.get("wind_cos", 1.0))
        pressure = float(w_row.get("surface_pressure", 980.0))
        precip = float(w_row.get("precipitation", 0.0))
        blh = float(w_row.get("boundary_layer_height", 450.0))
    else:
        diurnal = math.sin(2 * math.pi * (hour_val - 8) / 24)
        temp = 28.0 + 5.0 * diurnal
        humidity = max(20.0, 65.0 - 15.0 * diurnal)
        wind_spd = max(1.0, 8.0 + 3.0 * diurnal)
        wind_sin = math.sin(math.radians(120.0))
        wind_cos = math.cos(math.radians(120.0))
        pressure = 980.0
        precip = 0.0
        blh = max(100.0, 450.0 + 300.0 * diurnal)

    current_pm = max(5.0, baseline_pm25)

    feature_dict = {
        "pm25_value": float(current_pm),
        "pm25_lag_1": float(current_pm),
        "pm25_lag_3": float(current_pm),
        "pm25_lag_6": float(current_pm),
        "pm25_lag_12": float(current_pm),
        "pm25_lag_24": float(current_pm),
        "pm25_roll_3": float(current_pm),
        "pm25_roll_6": float(current_pm),
        "pm25_roll_12": float(current_pm),
        "pm25_roll_24": float(current_pm),
        "temperature_2m": temp,
        "relative_humidity_2m": humidity,
        "wind_speed_10m": wind_spd,
        "wind_sin": wind_sin,
        "wind_cos": wind_cos,
        "surface_pressure": pressure,
        "precipitation": precip,
        "boundary_layer_height": blh,
        "fire_count_punjab": 0.0,
        "fire_count_haryana": 0.0,
        "fire_count_up": 0.0,
        "fire_count_delhi": 0.0,
        "hour": hour_val,
        "day": day_val,
        "month": month_val,
        "day_of_week": dow_val,
        "latitude": st_lat,
        "longitude": st_lon
    }

    feature_df = pd.DataFrame([feature_dict])[MODEL_FEATURES]
    return actual_name, city, current_pm, feature_df


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class StationSummary(BaseModel):
    name: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    latest_pm25: Optional[float] = None
    latest_aqi: Optional[int] = None
    aqi_category: Optional[str] = None
    unit: str = "µg/m³"
    timestamp: Optional[str] = None


class PollutantReading(BaseModel):
    parameter: str
    value: float
    unit: str
    timestamp: str


class CurrentStationReadings(BaseModel):
    station_name: str
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    current_pm25: Optional[float] = None
    current_aqi: Optional[int] = None
    aqi_category: Optional[str] = None
    readings_count: int
    readings: List[PollutantReading]


class ForecastHour(BaseModel):
    hour_offset: int
    timestamp: str
    predicted_pm25: float
    predicted_aqi: int
    unit: str = "µg/m³"
    aqi_category: str


class ForecastResponse(BaseModel):
    station_name: str
    city: str
    is_mock: bool = False
    model_name: str = "pm25_xgboost_model.pkl"
    note: str
    current_pm25: float
    current_aqi: int
    current_aqi_category: str
    forecast_hours: int = 72
    forecast: List[ForecastHour]


class ContributingFactor(BaseModel):
    feature: str
    value: float
    impact: str = Field(description="'increase' or 'decrease'")
    shap_value: float


class ExplainResponse(BaseModel):
    station_name: str
    predicted_pm25: float
    predicted_aqi: int
    aqi_category: str
    unit: str = "µg/m³"
    base_expected_value: float
    top_contributing_factors: List[ContributingFactor]


class DispersionResponse(BaseModel):
    station_name: str
    city: str
    wind_speed_10m: float
    boundary_layer_height: float
    temperature_2m: float
    relative_humidity_2m: float
    classification: str
    risk_level: str
    explanation: str
    timestamp: str


class HistoryPoint(BaseModel):
    timestamp: str
    pm25: float
    temperature: float


class HistoryResponse(BaseModel):
    station_name: str
    days: int
    points_count: int
    history: List[HistoryPoint]


class AlertItem(BaseModel):
    id: str
    station_name: str
    city: str
    alert_type: str
    severity: str
    current_value: str
    reason: str
    timestamp: str


class AlertsResponse(BaseModel):
    total_alerts: int
    critical_count: int
    warning_count: int
    advisory_count: int
    timestamp: str
    alerts: List[AlertItem]


class MovementStationItem(BaseModel):
    station_name: str
    city: str
    latitude: float
    longitude: float
    pm25: float
    aqi: int
    aqi_category: str


class MovementWindItem(BaseModel):
    speed_ms: float
    speed_kmh: float
    direction_deg: float
    direction_label: str


class MovementStepItem(BaseModel):
    step_index: int
    offset_hours: int
    label: str
    target_time_utc: str
    wind: MovementWindItem
    stations: List[MovementStationItem]


class MovementForecastResponse(BaseModel):
    model_version: str
    disclaimer: str
    available_steps: List[int]
    steps: List[MovementStepItem]


class FireItem(BaseModel):
    latitude: float
    longitude: float
    state: str
    acq_date: str
    acq_time: str
    frp: float
    confidence: str
    satellite: str
    instrument: str


class FiresResponse(BaseModel):
    total_fires: int
    source: str
    disclaimer: str
    fires: List[FireItem]


class PredictRequest(BaseModel):
    pm25_value: float
    pm25_lag_1: float
    pm25_lag_3: float
    pm25_lag_6: float
    pm25_lag_12: float
    pm25_lag_24: float
    pm25_roll_3: float
    pm25_roll_6: float
    pm25_roll_12: float
    pm25_roll_24: float
    temperature_2m: float
    relative_humidity_2m: float
    wind_speed_10m: float
    wind_sin: float
    wind_cos: float
    surface_pressure: float
    precipitation: float
    boundary_layer_height: float
    fire_count_punjab: float = 0.0
    fire_count_haryana: float = 0.0
    fire_count_up: float = 0.0
    fire_count_delhi: float = 0.0
    hour: int
    day: int
    month: int
    day_of_week: int
    latitude: float
    longitude: float


class PredictResponse(BaseModel):
    predicted_pm25: float
    predicted_aqi: int
    unit: str = "µg/m³"
    aqi_category: str
    model: str = "pm25_xgboost_model.pkl"


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@app.get("/health", summary="Health Check")
def health_check():
    return {
        "status": "ok",
        "service": "VayuDrishti Backend API",
        "cpcb_aqi_utility": "active",
        "ml_model_loaded": xgb_model is not None,
        "shap_explainer_loaded": shap_explainer is not None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/stations", response_model=List[StationSummary], summary="List All Monitoring Stations")
def get_stations():
    df = load_raw_data()
    coords_map = get_station_coordinates_map()

    stations_list = []
    grouped = df.groupby("location")

    for station_name, group in grouped:
        city = str(group["city"].iloc[0]) if "city" in group.columns else "Delhi NCR"
        pm25_row = group[group["parameter"].astype(str).str.lower() == "pm25"]
        latest_pm25 = None
        latest_aqi = None
        latest_cat = None
        latest_ts = None
        
        if not pm25_row.empty:
            latest_pm25 = round(float(pm25_row["value"].iloc[0]), 2)
            latest_aqi, latest_cat = pm25_to_aqi(latest_pm25)
            latest_ts = str(pm25_row["timestamp"].iloc[0])
        else:
            latest_ts = str(group["timestamp"].iloc[0]) if "timestamp" in group.columns else None

        coords = coords_map.get(str(station_name), {})

        stations_list.append(
            StationSummary(
                name=str(station_name),
                city=city,
                latitude=coords.get("latitude"),
                longitude=coords.get("longitude"),
                latest_pm25=latest_pm25,
                latest_aqi=latest_aqi,
                aqi_category=latest_cat,
                unit="µg/m³",
                timestamp=latest_ts
            )
        )

    stations_list.sort(key=lambda s: s.name)
    return stations_list


@app.get("/current/{station_name}", response_model=CurrentStationReadings, summary="Get Current Readings for Station")
def get_current_station_readings(station_name: str):
    decoded_name = urllib.parse.unquote(station_name).strip()
    df = load_raw_data()
    coords_map = get_station_coordinates_map()

    matched = df[df["location"].str.strip().str.lower() == decoded_name.lower()]
    if matched.empty:
        matched = df[df["location"].str.strip().str.lower().str.contains(decoded_name.lower())]

    if matched.empty:
        available_stations = sorted(df["location"].dropna().unique().tolist())
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Station '{decoded_name}' not found.",
                "available_stations_sample": available_stations[:10]
            }
        )

    actual_station_name = str(matched["location"].iloc[0])
    city = str(matched["city"].iloc[0]) if "city" in matched.columns else "Delhi NCR"
    coords = coords_map.get(actual_station_name, {})

    current_pm25 = None
    current_aqi = None
    aqi_category = None

    readings = []
    for _, row in matched.iterrows():
        param_name = str(row["parameter"]) if pd.notna(row["parameter"]) else "unknown"
        val = float(row["value"]) if pd.notna(row["value"]) else 0.0
        unit_str = str(row["unit"]) if pd.notna(row["unit"]) else "µg/m³"
        ts_str = str(row["timestamp"]) if pd.notna(row["timestamp"]) else ""

        if param_name.lower() == "pm25":
            current_pm25 = round(val, 2)
            current_aqi, aqi_category = pm25_to_aqi(current_pm25)

        readings.append(
            PollutantReading(
                parameter=param_name,
                value=round(val, 2),
                unit=unit_str,
                timestamp=ts_str
            )
        )

    return CurrentStationReadings(
        station_name=actual_station_name,
        city=city,
        latitude=coords.get("latitude"),
        longitude=coords.get("longitude"),
        current_pm25=current_pm25,
        current_aqi=current_aqi,
        aqi_category=aqi_category,
        readings_count=len(readings),
        readings=readings
    )


@app.get("/forecast/{station_name}", response_model=ForecastResponse, summary="Get 72-Hour PM2.5 Forecast (XGBoost ML)")
def get_forecast_for_station(station_name: str):
    """
    Generates a 72-hour forecast for the station using the trained XGBoost model,
    real Open-Meteo hour-by-hour forecast weather, and official CPCB AQI.
    """
    decoded_name = urllib.parse.unquote(station_name).strip()
    df_raw = load_raw_data()
    coords_map = get_station_coordinates_map()

    # Find station in current readings
    matched = df_raw[df_raw["location"].str.strip().str.lower() == decoded_name.lower()]
    if matched.empty:
        matched = df_raw[df_raw["location"].str.strip().str.lower().str.contains(decoded_name.lower())]

    if not matched.empty:
        actual_name = str(matched["location"].iloc[0])
        city = str(matched["city"].iloc[0]) if "city" in matched.columns else "Delhi NCR"
        pm25_row = matched[matched["parameter"].astype(str).str.lower() == "pm25"]
        baseline_pm25 = float(pm25_row["value"].iloc[0]) if (not pm25_row.empty and pd.notna(pm25_row["value"].iloc[0])) else 50.0
    else:
        actual_name = decoded_name
        city = "Delhi NCR"
        baseline_pm25 = 50.0

    coords = coords_map.get(actual_name, {"latitude": 28.6139, "longitude": 77.2090})
    st_lat = coords.get("latitude", 28.6139)
    st_lon = coords.get("longitude", 77.2090)

    now_utc = datetime.now(timezone.utc)
    forecast_list = []
    is_using_real_model = (xgb_model is not None)
    forecast_weather_df = load_forecast_weather()

    # Autoregressive multi-step projection with XGBoost
    current_pm = max(5.0, baseline_pm25)
    current_aqi_num, current_aqi_cat = pm25_to_aqi(current_pm)
    pm_history = [current_pm] * 25  # for lags

    for h in range(1, 73):
        fc_time = now_utc + timedelta(hours=h)
        hour_val = fc_time.hour
        day_val = fc_time.day
        month_val = fc_time.month
        dow_val = fc_time.weekday()

        # Use real forecasted weather if available
        if forecast_weather_df is not None and (h - 1) < len(forecast_weather_df):
            w_row = forecast_weather_df.iloc[h - 1]
            temp = float(w_row.get("temperature_2m", 28.0))
            humidity = float(w_row.get("relative_humidity_2m", 65.0))
            wind_spd = float(w_row.get("wind_speed_10m", 8.0))
            wind_sin = float(w_row.get("wind_sin", 0.0))
            wind_cos = float(w_row.get("wind_cos", 1.0))
            pressure = float(w_row.get("surface_pressure", 980.0))
            precip = float(w_row.get("precipitation", 0.0))
            blh = float(w_row.get("boundary_layer_height", 450.0))
        else:
            diurnal = math.sin(2 * math.pi * (hour_val - 8) / 24)
            temp = 28.0 + 5.0 * diurnal
            humidity = max(20.0, 65.0 - 15.0 * diurnal)
            wind_spd = max(1.0, 8.0 + 3.0 * diurnal)
            wind_sin = math.sin(math.radians(120.0))
            wind_cos = math.cos(math.radians(120.0))
            pressure = 980.0
            precip = 0.0
            blh = max(100.0, 450.0 + 300.0 * diurnal)

        if is_using_real_model:
            feature_row = {
                "pm25_value": float(pm_history[-1]),
                "pm25_lag_1": float(pm_history[-1]),
                "pm25_lag_3": float(pm_history[-3]),
                "pm25_lag_6": float(pm_history[-6]),
                "pm25_lag_12": float(pm_history[-12]),
                "pm25_lag_24": float(pm_history[-24]),
                "pm25_roll_3": float(np.mean(pm_history[-3:])),
                "pm25_roll_6": float(np.mean(pm_history[-6:])),
                "pm25_roll_12": float(np.mean(pm_history[-12:])),
                "pm25_roll_24": float(np.mean(pm_history[-24:])),
                "temperature_2m": temp,
                "relative_humidity_2m": humidity,
                "wind_speed_10m": wind_spd,
                "wind_sin": wind_sin,
                "wind_cos": wind_cos,
                "surface_pressure": pressure,
                "precipitation": precip,
                "boundary_layer_height": blh,
                "fire_count_punjab": 0.0,
                "fire_count_haryana": 0.0,
                "fire_count_up": 0.0,
                "fire_count_delhi": 0.0,
                "hour": hour_val,
                "day": day_val,
                "month": month_val,
                "day_of_week": dow_val,
                "latitude": float(st_lat),
                "longitude": float(st_lon)
            }
            input_df = pd.DataFrame([feature_row])[MODEL_FEATURES]
            pred_val = round(max(5.0, float(xgb_model.predict(input_df)[0])), 1)
        else:
            diurnal = math.sin(2 * math.pi * (hour_val - 8) / 24)
            pred_val = round(max(5.0, current_pm * (1.0 + 0.25 * diurnal)), 1)

        pm_history.append(pred_val)
        pred_aqi, aqi_cat = pm25_to_aqi(pred_val)

        forecast_list.append(
            ForecastHour(
                hour_offset=h,
                timestamp=fc_time.strftime("%Y-%m-%dT%H:00:00Z"),
                predicted_pm25=pred_val,
                predicted_aqi=pred_aqi,
                unit="µg/m³",
                aqi_category=aqi_cat
            )
        )

    return ForecastResponse(
        station_name=actual_name,
        city=city,
        is_mock=not is_using_real_model,
        model_name="pm25_xgboost_model.pkl" if is_using_real_model else "diurnal_simulation",
        note="Trained XGBoost autoregressive 72-hour forecasting model powered by live Open-Meteo hour-by-hour weather forecast." if is_using_real_model else "Diurnal baseline forecast simulation.",
        current_pm25=round(current_pm, 2),
        current_aqi=current_aqi_num,
        current_aqi_category=current_aqi_cat,
        forecast_hours=72,
        forecast=forecast_list
    )


@app.get("/explain/{station_name}", response_model=ExplainResponse, summary="Get SHAP Explainability for Station Prediction")
def explain_station_prediction(station_name: str):
    """
    Computes SHAP feature attributions for a station's current prediction
    using the cached TreeExplainer instance, with CPCB AQI.
    """
    if xgb_model is None or shap_explainer is None:
        raise HTTPException(
            status_code=503,
            detail="XGBoost model or SHAP TreeExplainer is not initialized."
        )

    try:
        actual_name, city, current_pm, feature_df = extract_station_current_features(station_name)
        
        # Compute prediction and SHAP values for single feature vector
        predicted_val = round(max(0.0, float(xgb_model.predict(feature_df)[0])), 2)
        predicted_aqi, aqi_cat = pm25_to_aqi(predicted_val)

        shap_explanation = shap_explainer(feature_df)
        shap_vals = shap_explanation.values[0]  # shape: (28,)
        base_val = round(float(shap_explainer.expected_value), 2)

        PM25_GROUP_FEATURES = {
            "pm25_value", "pm25_lag_1", "pm25_lag_3", "pm25_lag_6",
            "pm25_lag_12", "pm25_lag_24", "pm25_roll_3", "pm25_roll_6",
            "pm25_roll_12", "pm25_roll_24"
        }
        EXCLUDED_EXPLAIN_FEATURES = {"latitude", "longitude", "day", "day_of_week"}

        candidates = []

        # 1. Grouped recent_pollution_trend
        pm25_shap_sum = sum(
            shap_vals[idx]
            for idx, feat in enumerate(MODEL_FEATURES)
            if feat in PM25_GROUP_FEATURES
        )
        pm25_rep_val = float(feature_df.iloc[0]["pm25_value"])
        candidates.append({
            "feature": "recent_pollution_trend",
            "value": round(pm25_rep_val, 2),
            "shap_value": round(float(pm25_shap_sum), 2),
            "abs_shap": abs(float(pm25_shap_sum)),
            "impact": "increase" if pm25_shap_sum > 0 else "decrease"
        })

        # 2. Individual remaining features (weather, fire counts, hour, month)
        for idx, feat in enumerate(MODEL_FEATURES):
            if feat in PM25_GROUP_FEATURES or feat in EXCLUDED_EXPLAIN_FEATURES:
                continue
            s_val = float(shap_vals[idx])
            f_val = float(feature_df.iloc[0][feat])
            candidates.append({
                "feature": feat,
                "value": round(f_val, 2),
                "shap_value": round(s_val, 2),
                "abs_shap": abs(s_val),
                "impact": "increase" if s_val > 0 else "decrease"
            })

        # 3. Sort by absolute SHAP value descending and take top 5
        candidates.sort(key=lambda c: c["abs_shap"], reverse=True)

        factors = [
            ContributingFactor(
                feature=c["feature"],
                value=c["value"],
                impact=c["impact"],
                shap_value=c["shap_value"]
            )
            for c in candidates[:5]
        ]

        return ExplainResponse(
            station_name=actual_name,
            predicted_pm25=predicted_val,
            predicted_aqi=predicted_aqi,
            aqi_category=aqi_cat,
            unit="µg/m³",
            base_expected_value=base_val,
            top_contributing_factors=factors
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SHAP explanation error: {str(e)}")


@app.get("/dispersion/{station_name}", response_model=DispersionResponse, summary="Get Inversion and Atmospheric Dispersion Conditions")
def get_dispersion_conditions(station_name: str):
    """
    Evaluates atmospheric ventilation, thermal inversion, and boundary layer mixing
    depth for the station based on real-time meteorological indicators.
    """
    try:
        actual_name, city, current_pm, feature_df = extract_station_current_features(station_name)
        
        wind_spd = float(feature_df.iloc[0]["wind_speed_10m"])
        blh = float(feature_df.iloc[0]["boundary_layer_height"])
        temp = float(feature_df.iloc[0]["temperature_2m"])
        humidity = float(feature_df.iloc[0]["relative_humidity_2m"])

        # Classification logic based on physical thresholds
        if wind_spd < 2.0 and blh < 500.0:
            classification = "STRONG INVERSION / POOR DISPERSION"
            risk_level = "high"
            explanation = (
                f"Low wind speed ({wind_spd:.1f} m/s) and shallow planetary boundary layer ({blh:.0f} m) "
                f"create a severe thermal inversion, trapping surface emissions near ground level."
            )
        elif wind_spd < 4.0 or blh < 1000.0:
            classification = "MODERATE DISPERSION"
            risk_level = "moderate"
            explanation = (
                f"Moderate surface winds ({wind_spd:.1f} m/s) and mixing height ({blh:.0f} m) "
                f"allow partial atmospheric ventilation across Delhi NCR."
            )
        else:
            classification = "GOOD DISPERSION"
            risk_level = "low"
            explanation = (
                f"Favorable wind speeds ({wind_spd:.1f} m/s) and deep boundary layer mixing ({blh:.0f} m) "
                f"actively dilute and disperse airborne pollutants."
            )

        return DispersionResponse(
            station_name=actual_name,
            city=city,
            wind_speed_10m=round(wind_spd, 1),
            boundary_layer_height=round(blh, 0),
            temperature_2m=round(temp, 1),
            relative_humidity_2m=round(humidity, 1),
            classification=classification,
            risk_level=risk_level,
            explanation=explanation,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dispersion analysis error: {str(e)}")


@app.get("/history/{station_name}", response_model=HistoryResponse, summary="Get Historical PM2.5 & Temperature Trend for Station")
def get_station_history(station_name: str, days: int = 7):
    """
    Returns real historical hourly PM2.5 and temperature timeseries from the
    master dataset for the requested station and day range (7 or 30 days).
    """
    decoded_name = urllib.parse.unquote(station_name).strip()
    df_raw = load_raw_data()
    matched = df_raw[df_raw["location"].str.strip().str.lower() == decoded_name.lower()]
    if matched.empty:
        matched = df_raw[df_raw["location"].str.strip().str.lower().str.contains(decoded_name.lower())]
    actual_name = str(matched["location"].iloc[0]) if not matched.empty else decoded_name

    MASTER_PATH = BASE_DIR / "data" / "processed" / "master_dataset.csv"
    if not MASTER_PATH.exists():
        raise HTTPException(status_code=500, detail="Master historical dataset not found.")

    try:
        df_m = pd.read_csv(MASTER_PATH, usecols=["station_name", "timestamp", "pm25_value", "temperature_2m"])
        st_df = df_m[df_m["station_name"] == actual_name].sort_values("timestamp")

        if st_df.empty:
            st_df = df_m[df_m["station_name"].str.contains(actual_name.split(",")[0], case=False, na=False)].sort_values("timestamp")
            if st_df.empty:
                st_df = df_m[df_m["station_name"] == df_m["station_name"].iloc[0]].sort_values("timestamp")

        hours_needed = min(len(st_df), max(24, days * 24))
        sub_df = st_df.tail(hours_needed)

        # Downsample slightly for clean rendering (step=2 for 7d => ~84 points, step=4 for 30d => ~180 points)
        step = 4 if days > 14 else 2
        sampled = sub_df.iloc[::step]

        history_points = [
            HistoryPoint(
                timestamp=str(row["timestamp"]),
                pm25=round(float(row["pm25_value"]), 1),
                temperature=round(float(row["temperature_2m"]), 1)
            )
            for _, row in sampled.iterrows()
        ]

        return HistoryResponse(
            station_name=actual_name,
            days=days,
            points_count=len(history_points),
            history=history_points
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History extraction error: {str(e)}")


@app.get("/alerts", response_model=AlertsResponse, summary="Get Active Rule-Based Air Quality Alerts Across All Stations")
def get_active_alerts():
    """
    Evaluates real-time data across all 50 stations against automated threshold rules:
      1. AQI > 200 -> 'Poor Air Quality Alert'
      2. Predicted PM2.5 (12h trend) rising > 20% vs current -> 'Rising Pollution Trend Alert'
      3. Dispersion status is STRONG INVERSION / POOR DISPERSION -> 'Poor Dispersion Alert'
    """
    df_raw = load_raw_data()
    forecast_w_df = load_forecast_weather()
    coords_map = get_station_coordinates_map()
    now_iso = datetime.now(timezone.utc).isoformat()

    alerts_list = []
    grouped = df_raw.groupby("location")

    stations_eval = []
    for station_name, group in grouped:
        st_name = str(station_name)
        city = str(group["city"].iloc[0]) if "city" in group.columns else "Delhi NCR"
        pm25_row = group[group["parameter"].astype(str).str.lower() == "pm25"]

        if pm25_row.empty or pd.isna(pm25_row["value"].iloc[0]):
            continue

        current_pm = float(pm25_row["value"].iloc[0])
        aqi_val, aqi_cat = pm25_to_aqi(current_pm)

        coords = coords_map.get(st_name, {"latitude": 28.6139, "longitude": 77.2090})
        st_lat = coords.get("latitude", 28.6139)
        st_lon = coords.get("longitude", 77.2090)

        # Rule 1: AQI > 200 (Poor / Very Poor / Severe)
        if aqi_val > 200:
            sev = "critical" if aqi_val > 300 else "warning"
            alerts_list.append(
                AlertItem(
                    id=f"aqi-{abs(hash(st_name)) % 10000}",
                    station_name=st_name,
                    city=city,
                    alert_type="Poor Air Quality Alert",
                    severity=sev,
                    current_value=f"AQI {aqi_val} ({current_pm:.1f} µg/m³ PM2.5)",
                    reason=f"Current AQI is {aqi_val} ({aqi_cat}), exceeding safe national ambient air quality thresholds.",
                    timestamp=now_iso
                )
            )

        stations_eval.append({
            "st_name": st_name,
            "city": city,
            "current_pm": current_pm,
            "current_cat": aqi_cat,
            "st_lat": st_lat,
            "st_lon": st_lon,
            "pm_hist": [current_pm] * 25
        })

    # Rule 2: Vectorized 12-hour simulation across all stations
    if xgb_model is not None and stations_eval:
        now_utc = datetime.now(timezone.utc)
        AQI_TIER_RANK = {"Good": 1, "Satisfactory": 2, "Moderate": 3, "Poor": 4, "Very Poor": 5, "Severe": 6}

        for h in range(1, 13):
            fc_time = now_utc + timedelta(hours=h)
            if forecast_w_df is not None and (h - 1) < len(forecast_w_df):
                w_row = forecast_w_df.iloc[h - 1]
                temp = float(w_row.get("temperature_2m", 28.0))
                hum = float(w_row.get("relative_humidity_2m", 65.0))
                wspd = float(w_row.get("wind_speed_10m", 8.0))
                wsin = float(w_row.get("wind_sin", 0.0))
                wcos = float(w_row.get("wind_cos", 1.0))
                press = float(w_row.get("surface_pressure", 980.0))
                prec = float(w_row.get("precipitation", 0.0))
                blh = float(w_row.get("boundary_layer_height", 450.0))
            else:
                diurnal = math.sin(2 * math.pi * (fc_time.hour - 8) / 24)
                temp = 28.0 + 5.0 * diurnal
                hum = max(20.0, 65.0 - 15.0 * diurnal)
                wspd = max(1.0, 8.0 + 3.0 * diurnal)
                wsin = math.sin(math.radians(120.0))
                wcos = math.cos(math.radians(120.0))
                press = 980.0
                prec = 0.0
                blh = max(100.0, 450.0 + 300.0 * diurnal)

            batch_rows = []
            for st in stations_eval:
                pm_hist = st["pm_hist"]
                row_feat = {
                    "pm25_value": float(pm_hist[-1]),
                    "pm25_lag_1": float(pm_hist[-1]),
                    "pm25_lag_3": float(pm_hist[-3]),
                    "pm25_lag_6": float(pm_hist[-6]),
                    "pm25_lag_12": float(pm_hist[-12]),
                    "pm25_lag_24": float(pm_hist[-24]),
                    "pm25_roll_3": float(np.mean(pm_hist[-3:])),
                    "pm25_roll_6": float(np.mean(pm_hist[-6:])),
                    "pm25_roll_12": float(np.mean(pm_hist[-12:])),
                    "pm25_roll_24": float(np.mean(pm_hist[-24:])),
                    "temperature_2m": temp,
                    "relative_humidity_2m": hum,
                    "wind_speed_10m": wspd,
                    "wind_sin": wsin,
                    "wind_cos": wcos,
                    "surface_pressure": press,
                    "precipitation": prec,
                    "boundary_layer_height": blh,
                    "fire_count_punjab": 0.0,
                    "fire_count_haryana": 0.0,
                    "fire_count_up": 0.0,
                    "fire_count_delhi": 0.0,
                    "hour": fc_time.hour,
                    "day": fc_time.day,
                    "month": fc_time.month,
                    "day_of_week": fc_time.weekday(),
                    "latitude": float(st["st_lat"]),
                    "longitude": float(st["st_lon"])
                }
                batch_rows.append(row_feat)

            batch_df = pd.DataFrame(batch_rows)[MODEL_FEATURES]
            batch_preds = xgb_model.predict(batch_df)
            for idx, st in enumerate(stations_eval):
                pred_v = float(batch_preds[idx])
                st["pm_hist"].append(pred_v)
                if h == 12:
                    st["pred_12h"] = pred_v

        # Evaluate Rule 2 on 12h forecast
        for st in stations_eval:
            current_pm = st["current_pm"]
            pred_12h = st.get("pred_12h", current_pm)
            pred_aqi, pred_cat = pm25_to_aqi(pred_12h)
            current_cat = st["current_cat"]
            pct_rise = ((pred_12h - current_pm) / max(1.0, current_pm)) * 100.0
            # Must worsen category AND cross into Moderate or worse (Moderate, Poor, Very Poor, Severe)
            is_worse_category = AQI_TIER_RANK.get(pred_cat, 0) > AQI_TIER_RANK.get(current_cat, 0)
            is_unhealthy_tier = AQI_TIER_RANK.get(pred_cat, 0) >= 3

            if pct_rise >= 20.0 and is_worse_category and is_unhealthy_tier:
                alerts_list.append(
                    AlertItem(
                        id=f"trend-{abs(hash(st['st_name'])) % 10000}",
                        station_name=st["st_name"],
                        city=st["city"],
                        alert_type="Rising Pollution Trend Alert",
                        severity="warning",
                        current_value=f"+{pct_rise:.1f}% expected ({current_cat} → {pred_cat})",
                        reason=f"PM2.5 projected to climb {pct_rise:.1f}% (from {current_pm:.1f} to {pred_12h:.1f} µg/m³) over next 12 hours, worsening AQI category from '{current_cat}' into '{pred_cat}'.",
                        timestamp=now_iso
                    )
                )

    # Rule 3: Poor Dispersion / Strong Inversion
    if forecast_w_df is not None and len(forecast_w_df) > 0:
        w_now = forecast_w_df.iloc[0]
        wspd_now = float(w_now.get("wind_speed_10m", 8.0))
        blh_now = float(w_now.get("boundary_layer_height", 450.0))
        if wspd_now < 2.0 and blh_now < 500.0:
            for st in stations_eval:
                alerts_list.append(
                    AlertItem(
                        id=f"disp-{abs(hash(st['st_name'])) % 10000}",
                        station_name=st["st_name"],
                        city=st["city"],
                        alert_type="Poor Dispersion Alert",
                        severity="warning",
                        current_value=f"{wspd_now:.1f} m/s wind | {blh_now:.0f}m PBL",
                        reason=f"Surface wind speed ({wspd_now:.1f} m/s) and shallow planetary boundary layer ({blh_now:.0f} m) are trapping pollutants near the surface.",
                        timestamp=now_iso
                    )
                )

    crit = sum(1 for a in alerts_list if a.severity == "critical")
    warn = sum(1 for a in alerts_list if a.severity == "warning")
    adv = sum(1 for a in alerts_list if a.severity == "advisory")

    return AlertsResponse(
        total_alerts=len(alerts_list),
        critical_count=crit,
        warning_count=warn,
        advisory_count=adv,
        timestamp=now_iso,
        alerts=alerts_list
    )


def degrees_to_cardinal(deg: float) -> str:
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    idx = int(round(deg / 22.5)) % 16
    return dirs[idx]


@app.get("/movement-forecast", response_model=MovementForecastResponse, summary="Pollution Movement Time-Step Forecasts (Now, +6h, +12h, +24h, +48h, +72h)")
def get_movement_forecast():
    """
    Computes synchronized multi-step spatial PM2.5 and wind forecasts across all 50 monitoring stations
    for offsets [0, 6, 12, 24, 48, 72] hours ahead.
    Uses real Open-Meteo forecasted weather and autoregressive XGBoost model inferences.
    """
    df_raw = load_raw_data()
    forecast_w_df = load_forecast_weather()
    coords_map = get_station_coordinates_map()
    now_utc = datetime.now(timezone.utc)

    grouped = df_raw.groupby("location")
    stations_data = []

    for station_name, group in grouped:
        st_name = str(station_name)
        city = str(group["city"].iloc[0]) if "city" in group.columns else "Delhi NCR"
        pm25_row = group[group["parameter"].astype(str).str.lower() == "pm25"]

        if pm25_row.empty or pd.isna(pm25_row["value"].iloc[0]):
            continue

        current_pm = float(pm25_row["value"].iloc[0])
        coords = coords_map.get(st_name, {"latitude": 28.6139, "longitude": 77.2090})
        st_lat = coords.get("latitude", 28.6139)
        st_lon = coords.get("longitude", 77.2090)

        stations_data.append({
            "st_name": st_name,
            "city": city,
            "latitude": st_lat,
            "longitude": st_lon,
            "current_pm": current_pm,
            "pm_hist": [current_pm] * 25
        })

    target_offsets = [0, 6, 12, 24, 48, 72]
    offset_labels = {0: "Now", 6: "+6h", 12: "+12h", 24: "+24h", 48: "+48h", 72: "+72h"}
    steps_result = []

    # Step 0: Current time
    w_now_row = forecast_w_df.iloc[0] if (forecast_w_df is not None and len(forecast_w_df) > 0) else {}
    wspd_0 = float(w_now_row.get("wind_speed_10m", 8.0))
    wdir_0 = float(w_now_row.get("wind_direction_10m", 270.0))
    
    st_items_0 = []
    for st in stations_data:
        pm_val = round(st["current_pm"], 1)
        aqi_val, aqi_cat = pm25_to_aqi(pm_val)
        st_items_0.append(
            MovementStationItem(
                station_name=st["st_name"],
                city=st["city"],
                latitude=st["latitude"],
                longitude=st["longitude"],
                pm25=pm_val,
                aqi=aqi_val,
                aqi_category=aqi_cat
            )
        )

    steps_result.append(
        MovementStepItem(
            step_index=0,
            offset_hours=0,
            label="Now",
            target_time_utc=now_utc.isoformat(),
            wind=MovementWindItem(
                speed_ms=round(wspd_0, 1),
                speed_kmh=round(wspd_0 * 3.6, 1),
                direction_deg=round(wdir_0, 1),
                direction_label=degrees_to_cardinal(wdir_0)
            ),
            stations=st_items_0
        )
    )

    # Future steps 1..72 using vectorized XGBoost
    if xgb_model is not None and stations_data:
        for h in range(1, 73):
            fc_time = now_utc + timedelta(hours=h)
            if forecast_w_df is not None and (h - 1) < len(forecast_w_df):
                w_row = forecast_w_df.iloc[h - 1]
                temp = float(w_row.get("temperature_2m", 28.0))
                hum = float(w_row.get("relative_humidity_2m", 65.0))
                wspd = float(w_row.get("wind_speed_10m", 8.0))
                wdir = float(w_row.get("wind_direction_10m", 270.0))
                wsin = float(w_row.get("wind_sin", math.sin(math.radians(wdir))))
                wcos = float(w_row.get("wind_cos", math.cos(math.radians(wdir))))
                press = float(w_row.get("surface_pressure", 980.0))
                prec = float(w_row.get("precipitation", 0.0))
                blh = float(w_row.get("boundary_layer_height", 450.0))
            else:
                diurnal = math.sin(2 * math.pi * (fc_time.hour - 8) / 24)
                temp = 28.0 + 5.0 * diurnal
                hum = max(20.0, 65.0 - 15.0 * diurnal)
                wspd = max(1.0, 8.0 + 3.0 * diurnal)
                wdir = 270.0
                wsin = math.sin(math.radians(wdir))
                wcos = math.cos(math.radians(wdir))
                press = 980.0
                prec = 0.0
                blh = max(100.0, 450.0 + 300.0 * diurnal)

            batch_rows = []
            for st in stations_data:
                pm_hist = st["pm_hist"]
                row_feat = {
                    "pm25_value": float(pm_hist[-1]),
                    "pm25_lag_1": float(pm_hist[-1]),
                    "pm25_lag_3": float(pm_hist[-3]),
                    "pm25_lag_6": float(pm_hist[-6]),
                    "pm25_lag_12": float(pm_hist[-12]),
                    "pm25_lag_24": float(pm_hist[-24]),
                    "pm25_roll_3": float(np.mean(pm_hist[-3:])),
                    "pm25_roll_6": float(np.mean(pm_hist[-6:])),
                    "pm25_roll_12": float(np.mean(pm_hist[-12:])),
                    "pm25_roll_24": float(np.mean(pm_hist[-24:])),
                    "temperature_2m": temp,
                    "relative_humidity_2m": hum,
                    "wind_speed_10m": wspd,
                    "wind_sin": wsin,
                    "wind_cos": wcos,
                    "surface_pressure": press,
                    "precipitation": prec,
                    "boundary_layer_height": blh,
                    "fire_count_punjab": 0.0,
                    "fire_count_haryana": 0.0,
                    "fire_count_up": 0.0,
                    "fire_count_delhi": 0.0,
                    "hour": fc_time.hour,
                    "day": fc_time.day,
                    "month": fc_time.month,
                    "day_of_week": fc_time.weekday(),
                    "latitude": float(st["latitude"]),
                    "longitude": float(st["longitude"])
                }
                batch_rows.append(row_feat)

            batch_df = pd.DataFrame(batch_rows)[MODEL_FEATURES]
            batch_preds = xgb_model.predict(batch_df)

            for idx, st in enumerate(stations_data):
                pred_v = max(0.0, float(batch_preds[idx]))
                st["pm_hist"].append(pred_v)

            if h in target_offsets:
                st_items_h = []
                for st in stations_data:
                    val_h = round(float(st["pm_hist"][-1]), 1)
                    aqi_h, cat_h = pm25_to_aqi(val_h)
                    st_items_h.append(
                        MovementStationItem(
                            station_name=st["st_name"],
                            city=st["city"],
                            latitude=st["latitude"],
                            longitude=st["longitude"],
                            pm25=val_h,
                            aqi=aqi_h,
                            aqi_category=cat_h
                        )
                    )

                steps_result.append(
                    MovementStepItem(
                        step_index=len(steps_result),
                        offset_hours=h,
                        label=offset_labels.get(h, f"+{h}h"),
                        target_time_utc=fc_time.isoformat(),
                        wind=MovementWindItem(
                            speed_ms=round(wspd, 1),
                            speed_kmh=round(wspd * 3.6, 1),
                            direction_deg=round(wdir, 1),
                            direction_label=degrees_to_cardinal(wdir)
                        ),
                        stations=st_items_h
                    )
                )

    return MovementForecastResponse(
        model_version="pm25_xgboost_model.pkl",
        disclaimer="AI-assisted pollution transport estimate based on forecasted conditions",
        available_steps=target_offsets,
        steps=steps_result
    )


FIRMS_PROCESSED_CSV = BASE_DIR / "data" / "raw" / "firms_processed.csv"


@app.get("/fires", response_model=FiresResponse, summary="Get NASA FIRMS Regional Fire Hotspots")
def get_regional_fires():
    """
    Returns real NASA FIRMS active fire and thermal anomaly detections from Punjab, Haryana, and UP.
    """
    if not FIRMS_PROCESSED_CSV.exists():
        return FiresResponse(
            total_fires=0,
            source="NASA FIRMS (VIIRS)",
            disclaimer="Regional fire activity (NASA FIRMS) — estimated influence based on wind transport, not exact source attribution.",
            fires=[]
        )

    try:
        df = pd.read_csv(FIRMS_PROCESSED_CSV)
        fires_list = []
        for _, row in df.iterrows():
            fires_list.append(
                FireItem(
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    state=str(row.get("state", "Regional")),
                    acq_date=str(row.get("acq_date", "2026-08-20")),
                    acq_time=str(row.get("acq_time", "0000")),
                    frp=round(float(row.get("frp", 1.0)), 2),
                    confidence=str(row.get("confidence", "nominal")),
                    satellite=str(row.get("satellite", "VIIRS")),
                    instrument=str(row.get("instrument", "VIIRS"))
                )
            )

        return FiresResponse(
            total_fires=len(fires_list),
            source="NASA FIRMS (VIIRS / Suomi-NPP & NOAA-20)",
            disclaimer="Regional fire activity (NASA FIRMS) — estimated influence based on wind transport, not exact source attribution.",
            fires=fires_list
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading FIRMS data: {str(e)}")


@app.post("/predict", response_model=PredictResponse, summary="Direct Model Inference")
@app.post("/api/predict", response_model=PredictResponse, include_in_schema=False)
def predict_pm25(payload: PredictRequest):
    """
    Direct inference endpoint for the trained XGBoost PM2.5 model.
    Accepts 28 environmental, lag, fire, and temporal features.
    """
    if xgb_model is None:
        raise HTTPException(
            status_code=503,
            detail="Trained XGBoost model not loaded. Check models/pm25_xgboost_model.pkl"
        )
    
    try:
        input_data = payload.model_dump()
        input_df = pd.DataFrame([input_data])[MODEL_FEATURES]
        pred = max(0.0, float(xgb_model.predict(input_df)[0]))
        pred_rounded = round(pred, 2)
        pred_aqi, aqi_cat = pm25_to_aqi(pred_rounded)
        
        return PredictResponse(
            predicted_pm25=pred_rounded,
            predicted_aqi=pred_aqi,
            unit="µg/m³",
            aqi_category=aqi_cat,
            model="pm25_xgboost_model.pkl"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
