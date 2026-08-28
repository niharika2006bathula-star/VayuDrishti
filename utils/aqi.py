"""
utils/aqi.py

Official Central Pollution Control Board (CPCB) Indian National Air Quality Index (NAQI)
calculation utilities for PM2.5 concentration.

CPCB Standard Breakpoints for 24-hr / Hourly PM2.5 (µg/m³):
  - Good          (AQI 0 - 50)    : PM2.5 in [0, 30]
  - Satisfactory  (AQI 51 - 100)  : PM2.5 in (30, 60]
  - Moderate      (AQI 101 - 200) : PM2.5 in (60, 90]
  - Poor          (AQI 201 - 300) : PM2.5 in (90, 120]
  - Very Poor     (AQI 301 - 400) : PM2.5 in (120, 250]
  - Severe        (AQI 401 - 500) : PM2.5 in (250, 380]
  - Severe+       (AQI > 500)     : PM2.5 > 380
"""

from typing import Tuple

# CPCB official breakpoint table: (C_low, C_high, I_low, I_high, category)
CPCB_PM25_BREAKPOINTS = [
    (0.0, 30.0, 0, 50, "Good"),
    (30.0, 60.0, 51, 100, "Satisfactory"),
    (60.0, 90.0, 101, 200, "Moderate"),
    (90.0, 120.0, 201, 300, "Poor"),
    (120.0, 250.0, 301, 400, "Very Poor"),
    (250.0, 380.0, 401, 500, "Severe"),
]


def pm25_to_aqi(pm25_value: float) -> Tuple[int, str]:
    """
    Converts a PM2.5 concentration (µg/m³) to the official Indian AQI (0-500 scale)
    and corresponding NAQI category using the linear interpolation sub-index formula:
    
        Ip = [(I_high - I_low) / (C_high - C_low)] * (Cp - C_low) + I_low

    Returns:
        (aqi_numeric: int, aqi_category: str)
    """
    if pm25_value is None or pm25_value < 0:
        return 0, "No Data"

    pm25 = float(pm25_value)

    # Standard range calculation
    for c_low, c_high, i_low, i_high, category in CPCB_PM25_BREAKPOINTS:
        if pm25 <= c_high:
            # Linear interpolation
            aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_low) + i_low
            return round(aqi), category

    # Beyond 380 µg/m³ (Severe Emergency / Beyond 500)
    # Extrapolate proportionally using the severe slope (approx 100 AQI per 130 µg/m³)
    c_low, c_high, i_low, i_high, category = CPCB_PM25_BREAKPOINTS[-1]
    extra_aqi = ((i_high - i_low) / (c_high - c_low)) * (pm25 - c_high)
    aqi = 500 + round(extra_aqi)
    return min(999, aqi), "Severe"


def get_aqi_theme(aqi_numeric: int) -> dict:
    """Helper to return UI color tokens based on numeric AQI."""
    if aqi_numeric <= 50:
        return {"color": "green", "hex": "#10b981", "category": "Good"}
    elif aqi_numeric <= 100:
        return {"color": "yellow", "hex": "#f59e0b", "category": "Satisfactory"}
    elif aqi_numeric <= 200:
        return {"color": "orange", "hex": "#f97316", "category": "Moderate"}
    elif aqi_numeric <= 300:
        return {"color": "red", "hex": "#ef4444", "category": "Poor"}
    elif aqi_numeric <= 400:
        return {"color": "purple", "hex": "#a855f7", "category": "Very Poor"}
    else:
        return {"color": "maroon", "hex": "#881337", "category": "Severe"}
