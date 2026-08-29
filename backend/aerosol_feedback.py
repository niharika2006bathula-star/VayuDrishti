def apply_feedback(pm25: float, wind_speed: float, pbl: float) -> float:
    """
    Applies an aerosol-radiation feedback adjustment to the Planetary Boundary Layer (PBL) height.
    
    If PM2.5 is high (> 150) and wind speed is low (< 2.0 m/s) indicating stagnant conditions,
    the PBL height is reduced by 12%. Otherwise, it is returned unchanged.
    
    NOTE: This is a literature-informed illustrative approximation (based on published 
    aerosol-radiation feedback research on Delhi, e.g. WRF-Chem studies showing aerosol 
    loading confines pollution to the lowest 400-500m), NOT a precisely measured physical 
    coefficient. This is a simplified proxy for demonstration purposes.
    
    Args:
        pm25 (float): Particulate matter 2.5 concentration (ug/m3)
        wind_speed (float): Wind speed (m/s)
        pbl (float): Planetary boundary layer height (m)
        
    Returns:
        float: Adjusted planetary boundary layer height
    """
    if pm25 > 150 and wind_speed < 2.0:
        return pbl * 0.88  # Reduce by 12%
    return pbl
