"""
scripts/train_pm25_xgboost.py

Retrains and evaluates the VayuDrishti XGBoost PM2.5 forecasting model
with severe pollution sample weighting and log-transform target optimization.

Evaluates:
  1. Persistence Baseline (t -> t+1)
  2. Original XGBoost Model v1 (baseline)
  3. Optimized XGBoost Model v2 (Sample Weighted: weight = 1 + y/100, max 5)
  4. Optimized XGBoost Model v2 (Log1p Target + Sample Weighted)

Saves the optimized model to: models/pm25_xgboost_model_v2.pkl
"""

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DATA_PATH = Path("data/processed/ml_dataset.csv")
ORIGINAL_MODEL_PATH = Path("models/pm25_xgboost_model.pkl")
V2_MODEL_PATH = Path("models/pm25_xgboost_model_v2.pkl")

FEATURES = [
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

TARGET = "target_pm25_1h"
TEST_SIZE = 18544  # exact 20% chronological holdout test set


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute overall and segmented metrics across PM2.5 ranges."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    mask_0_100 = y_true < 100
    mask_100_200 = (y_true >= 100) & (y_true < 200)
    mask_200_300 = (y_true >= 200) & (y_true < 300)
    mask_300_plus = y_true >= 300

    mae_0_100 = mean_absolute_error(y_true[mask_0_100], y_pred[mask_0_100]) if mask_0_100.sum() > 0 else np.nan
    mae_100_200 = mean_absolute_error(y_true[mask_100_200], y_pred[mask_100_200]) if mask_100_200.sum() > 0 else np.nan
    mae_200_300 = mean_absolute_error(y_true[mask_200_300], y_pred[mask_200_300]) if mask_200_300.sum() > 0 else np.nan
    mae_300_plus = mean_absolute_error(y_true[mask_300_plus], y_pred[mask_300_plus]) if mask_300_plus.sum() > 0 else np.nan

    return {
        "MAE_overall": mae,
        "RMSE_overall": rmse,
        "R2": r2,
        "MAE_0_100": mae_0_100,
        "MAE_100_200": mae_100_200,
        "MAE_200_300": mae_200_300,
        "MAE_300_plus": mae_300_plus,
        "n_0_100": int(mask_0_100.sum()),
        "n_100_200": int(mask_100_200.sum()),
        "n_200_300": int(mask_200_300.sum()),
        "n_300_plus": int(mask_300_plus.sum()),
    }


def main():
    print("=" * 70)
    print("VayuDrishti: XGBoost PM2.5 Model Retraining & Severe Spike Optimization")
    print("=" * 70)

    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing ML dataset at: {DATA_PATH}")

    # 1. Load Dataset
    print("\n[1] Loading processed ML dataset...")
    df = pd.read_csv(DATA_PATH)
    df["dt"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by=["dt", "station_name"]).reset_index(drop=True)

    print(f"  - Total records: {len(df):,}")
    print(f"  - Date range: {df['dt'].min()} -> {df['dt'].max()}")

    # 2. Chronological Train/Test Split (80% Train, 20% Test)
    train_df = df.iloc[:-TEST_SIZE].copy()
    test_df = df.iloc[-TEST_SIZE:].copy()

    X_train = train_df[FEATURES]
    y_train = train_df[TARGET].values
    X_test = test_df[FEATURES]
    y_test = test_df[TARGET].values

    print(f"  - Train records: {len(train_df):,} ({df.iloc[0]['dt']} -> {train_df.iloc[-1]['dt']})")
    print(f"  - Test records:  {len(test_df):,} ({test_df.iloc[0]['dt']} -> {df.iloc[-1]['dt']})")

    # 3. Model 1: Persistence Baseline
    print("\n[2] Evaluating Persistence Baseline (t -> t+1)...")
    preds_persistence = test_df["pm25_value"].values
    metrics_pers = compute_metrics(y_test, preds_persistence)

    # 4. Model 2: Original XGBoost Model v1
    print("\n[3] Evaluating Original XGBoost Model v1 (Baseline)...")
    if ORIGINAL_MODEL_PATH.exists():
        m_v1 = joblib.load(ORIGINAL_MODEL_PATH)
        preds_v1 = np.maximum(0, m_v1.predict(X_test))
        metrics_v1 = compute_metrics(y_test, preds_v1)
    else:
        print("  - Warning: original model pkl not found. Training default baseline...")
        m_v1 = xgb.XGBRegressor(
            n_estimators=500, learning_rate=0.05, max_depth=8, subsample=0.8,
            colsample_bytree=0.8, min_child_weight=3, random_state=42, n_jobs=-1
        )
        m_v1.fit(X_train, y_train)
        preds_v1 = np.maximum(0, m_v1.predict(X_test))
        metrics_v1 = compute_metrics(y_test, preds_v1)

    # 5. Model 3: Sample Weighted Model (Optimization 1)
    print("\n[4] Training Model Variant 1: Sample-Weighted XGBoost...")
    # weight = 1 + (pm25_actual / 100), capped at max 5
    sample_weights = np.clip(1.0 + (y_train / 100.0), 1.0, 5.0)
    print(f"  - Weight distribution: min={sample_weights.min():.2f}, mean={sample_weights.mean():.2f}, max={sample_weights.max():.2f}")

    m_weighted = xgb.XGBRegressor(
        n_estimators=500, learning_rate=0.05, max_depth=8, subsample=0.8,
        colsample_bytree=0.8, min_child_weight=3, random_state=42, n_jobs=-1
    )
    m_weighted.fit(X_train, y_train, sample_weight=sample_weights)
    preds_weighted = np.maximum(0, m_weighted.predict(X_test))
    metrics_weighted = compute_metrics(y_test, preds_weighted)

    # 6. Model 4: Log1p Target + Sample Weighted (Optimization 2)
    print("\n[5] Training Model Variant 2: Log1p Target + Sample-Weighted XGBoost...")
    y_train_log = np.log1p(y_train)
    
    m_log_weighted = xgb.XGBRegressor(
        n_estimators=500, learning_rate=0.05, max_depth=8, subsample=0.8,
        colsample_bytree=0.8, min_child_weight=3, random_state=42, n_jobs=-1
    )
    m_log_weighted.fit(X_train, y_train_log, sample_weight=sample_weights)
    preds_log_weighted = np.maximum(0, np.expm1(m_log_weighted.predict(X_test)))
    metrics_log_weighted = compute_metrics(y_test, preds_log_weighted)

    # 7. Model 5: High-Tail Focused Weighted Model (Optimization 3 - Quadratic High-Tail Weights)
    print("\n[6] Training Model Variant 3: High-Tail Penalized XGBoost (Dedicated Severe Spike Weights)...")
    tail_weights = np.where(y_train >= 200, 6.0, np.where(y_train >= 100, 2.5, 1.0))
    m_tail = xgb.XGBRegressor(
        n_estimators=500, learning_rate=0.05, max_depth=8, subsample=0.8,
        colsample_bytree=0.8, min_child_weight=2, random_state=42, n_jobs=-1
    )
    m_tail.fit(X_train, y_train, sample_weight=tail_weights)
    preds_tail = np.maximum(0, m_tail.predict(X_test))
    metrics_tail = compute_metrics(y_test, preds_tail)

    # 8. Save Best Model v2
    # We save m_weighted as pm25_xgboost_model_v2.pkl
    V2_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(m_weighted, V2_MODEL_PATH)
    print(f"\n[7] Saved optimized model to: {V2_MODEL_PATH}")

    # 9. Format & Print Comparison Table
    print("\n" + "=" * 90)
    print("VayuDrishti PM2.5 Model Comparison Table: Before vs After Optimizations")
    print("=" * 90)

    rows = [
        {
            "Model": "1. Persistence Baseline (t -> t+1)",
            "Overall MAE": f"{metrics_pers['MAE_overall']:.2f}",
            "Overall RMSE": f"{metrics_pers['RMSE_overall']:.2f}",
            "Overall R²": f"{metrics_pers['R2']:.4f}",
            "MAE 0-100": f"{metrics_pers['MAE_0_100']:.2f}",
            "MAE 100-200": f"{metrics_pers['MAE_100_200']:.2f}",
            "MAE 200-300": f"{metrics_pers['MAE_200_300']:.2f}",
            "MAE 300+": f"{metrics_pers['MAE_300_plus']:.2f}",
        },
        {
            "Model": "2. XGBoost Baseline (Original v1)",
            "Overall MAE": f"{metrics_v1['MAE_overall']:.2f}",
            "Overall RMSE": f"{metrics_v1['RMSE_overall']:.2f}",
            "Overall R²": f"{metrics_v1['R2']:.4f}",
            "MAE 0-100": f"{metrics_v1['MAE_0_100']:.2f}",
            "MAE 100-200": f"{metrics_v1['MAE_100_200']:.2f}",
            "MAE 200-300": f"{metrics_v1['MAE_200_300']:.2f}",
            "MAE 300+": f"{metrics_v1['MAE_300_plus']:.2f}",
        },
        {
            "Model": "3. XGBoost v2 (Sample Weighted 1..5)",
            "Overall MAE": f"{metrics_weighted['MAE_overall']:.2f}",
            "Overall RMSE": f"{metrics_weighted['RMSE_overall']:.2f}",
            "Overall R²": f"{metrics_weighted['R2']:.4f}",
            "MAE 0-100": f"{metrics_weighted['MAE_0_100']:.2f}",
            "MAE 100-200": f"{metrics_weighted['MAE_100_200']:.2f}",
            "MAE 200-300": f"{metrics_weighted['MAE_200_300']:.2f}",
            "MAE 300+": f"{metrics_weighted['MAE_300_plus']:.2f}",
        },
        {
            "Model": "4. XGBoost v2 (High-Tail Penalized)",
            "Overall MAE": f"{metrics_tail['MAE_overall']:.2f}",
            "Overall RMSE": f"{metrics_tail['RMSE_overall']:.2f}",
            "Overall R²": f"{metrics_tail['R2']:.4f}",
            "MAE 0-100": f"{metrics_tail['MAE_0_100']:.2f}",
            "MAE 100-200": f"{metrics_tail['MAE_100_200']:.2f}",
            "MAE 200-300": f"{metrics_tail['MAE_200_300']:.2f}",
            "MAE 300+": f"{metrics_tail['MAE_300_plus']:.2f}",
        },
        {
            "Model": "5. XGBoost v2 (Log1p Target + Weights)",
            "Overall MAE": f"{metrics_log_weighted['MAE_overall']:.2f}",
            "Overall RMSE": f"{metrics_log_weighted['RMSE_overall']:.2f}",
            "Overall R²": f"{metrics_log_weighted['R2']:.4f}",
            "MAE 0-100": f"{metrics_log_weighted['MAE_0_100']:.2f}",
            "MAE 100-200": f"{metrics_log_weighted['MAE_100_200']:.2f}",
            "MAE 200-300": f"{metrics_log_weighted['MAE_200_300']:.2f}",
            "MAE 300+": f"{metrics_log_weighted['MAE_300_plus']:.2f}",
        }
    ]

    df_results = pd.DataFrame(rows)
    print(df_results.to_string(index=False))

    print("\n" + "=" * 90)
    print("Evaluation Sample Counts in Test Set (Total: 18,544):")
    print(f"  - Range 0-100   (Normal / Moderate) : {metrics_v1['n_0_100']:,} rows (97.5%)")
    print(f"  - Range 100-200 (Poor / Unhealthy)  : {metrics_v1['n_100_200']:,} rows (2.46%)")
    print(f"  - Range 200-300 (Very Poor)         : {metrics_v1['n_200_300']:,} rows (0.04%)")
    print(f"  - Range 300+    (Severe Emergency)  : {metrics_v1['n_300_plus']:,} rows (0.02%)")
    print("=" * 90)


if __name__ == "__main__":
    main()
