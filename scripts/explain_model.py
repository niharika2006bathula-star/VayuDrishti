"""
scripts/explain_model.py

SHAP TreeExplainer Analysis for VayuDrishti PM2.5 Forecasting Model.
Loads models/pm25_xgboost_model.pkl, computes SHAP values for recent sample observations,
and displays the top-5 feature attributions pushing predictions UP or DOWN.
"""

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import shap

# -----------------------------------------------------------------------------
# Configuration & Paths
# -----------------------------------------------------------------------------
MODEL_PATH = Path("models/pm25_xgboost_model.pkl")
DATA_PATH = Path("data/processed/ml_dataset.csv")

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


def explain_samples(sample_size: int = 100, display_count: int = 5):
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at: {MODEL_PATH}")
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"ML dataset not found at: {DATA_PATH}")

    print("=" * 80)
    print("VayuDrishti SHAP Model Explainability Engine")
    print("=" * 80)

    # 1. Load Model
    print(f"\n[1] Loading production XGBoost model from: {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)

    # 2. Load Recent Data Sample
    print(f"[2] Loading recent {sample_size} records from: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    df_sample = df.tail(sample_size).copy().reset_index(drop=True)
    X_sample = df_sample[FEATURES]

    # 3. Create TreeExplainer & Compute SHAP Values
    print("[3] Initializing shap.TreeExplainer and computing Shapley values...")
    explainer = shap.TreeExplainer(model)
    shap_explanation = explainer(X_sample)
    shap_values = shap_explanation.values  # (N, num_features)
    base_val = float(explainer.expected_value)

    print(f"    - Baseline / Expected Model Value: {base_val:.2f} µg/m³")
    print(f"    - Explaining first {display_count} sample predictions:")

    # 4. Display Top Contributing Features for Samples
    for i in range(min(display_count, len(df_sample))):
        st_name = df_sample.loc[i, "station_name"] if "station_name" in df_sample.columns else f"Sample #{i+1}"
        timestamp = df_sample.loc[i, "timestamp"] if "timestamp" in df_sample.columns else ""
        actual_val = df_sample.loc[i, "target_pm25_1h"] if "target_pm25_1h" in df_sample.columns else None
        
        row_features = X_sample.iloc[i]
        row_shap = shap_values[i]
        predicted_val = float(model.predict(X_sample.iloc[i:i+1])[0])

        EXCLUDED_EXPLAIN_FEATURES = {"latitude", "longitude", "day", "day_of_week"}
        # Rank features by absolute SHAP attribution, filtering out spatial/calendar IDs
        ranked_indices = np.argsort(np.abs(row_shap))[::-1]

        print("\n" + "-" * 80)
        print(f"Prediction #{i+1}: {st_name} | Timestamp: {timestamp}")
        print(f"Predicted PM2.5: {predicted_val:.2f} µg/m³  (Base Value: {base_val:.2f} µg/m³)")
        if actual_val is not None:
            print(f"Actual Target PM2.5: {actual_val:.2f} µg/m³")
        print("Top 5 Physical & Environmental Contributing Factors:")

        displayed = 0
        for idx in ranked_indices:
            feat_name = FEATURES[idx]
            if feat_name in EXCLUDED_EXPLAIN_FEATURES:
                continue

            feat_val = row_features[feat_name]
            shap_val = row_shap[idx]
            impact = "pushed prediction UP (+)" if shap_val > 0 else "pushed prediction DOWN (-)"
            displayed += 1

            print(f"  {displayed}. {feat_name:24s} = {feat_val:10.2f} | SHAP: {shap_val:+7.2f} µg/m³ | [{impact}]")
            if displayed == 5:
                break

    print("\n" + "=" * 80)
    print("SHAP analysis completed successfully.")
    print("=" * 80)


if __name__ == "__main__":
    explain_samples(sample_size=100, display_count=5)
