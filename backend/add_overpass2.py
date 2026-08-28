import sys

code_to_append = """

class PollutionSourceItem(BaseModel):
    name: str
    type: str
    distance_km: float

class NearbySourcesResponse(BaseModel):
    station: str
    sources: List[PollutionSourceItem]
    message: Optional[str] = None

_OVERPASS_CACHE = {}
_OVERPASS_CACHE_TTL = 3600

@app.get("/nearby-sources/{station_name}", response_model=NearbySourcesResponse, summary="Get nearby industrial sources from OpenStreetMap")
def get_nearby_sources(station_name: str):
    coords_map = get_station_coordinates_map()
    decoded_name = urllib.parse.unquote(station_name).strip()
    
    # Try to find exactly, or fallback to partial match
    target = None
    for name, coords in coords_map.items():
        if name.lower() == decoded_name.lower():
            target = {"name": name, "coords": coords}
            break
    
    if not target:
        for name, coords in coords_map.items():
            if decoded_name.lower() in name.lower():
                target = {"name": name, "coords": coords}
                break
                
    if not target:
        raise HTTPException(status_code=404, detail="Station coordinates not found.")
        
    lat = target["coords"]["latitude"]
    lon = target["coords"]["longitude"]
    
    cache_key = f"{lat},{lon}"
    import time
    now = time.time()
    
    if cache_key in _OVERPASS_CACHE:
        cached_data, timestamp = _OVERPASS_CACHE[cache_key]
        if now - timestamp < _OVERPASS_CACHE_TTL:
            return NearbySourcesResponse(station=target["name"], sources=cached_data)
            
    # Query Overpass
    overpass_url = "https://overpass-api.de/api/interpreter"
    query = f\"\"\"
    [out:json][timeout:25];
    (
      node["landuse"="industrial"](around:7000,{lat},{lon});
      way["landuse"="industrial"](around:7000,{lat},{lon});
      relation["landuse"="industrial"](around:7000,{lat},{lon});
      node["man_made"="works"](around:7000,{lat},{lon});
      way["man_made"="works"](around:7000,{lat},{lon});
      relation["man_made"="works"](around:7000,{lat},{lon});
      node["power"="plant"](around:7000,{lat},{lon});
      way["power"="plant"](around:7000,{lat},{lon});
      relation["power"="plant"](around:7000,{lat},{lon});
      node["landuse"="quarry"](around:7000,{lat},{lon});
      way["landuse"="quarry"](around:7000,{lat},{lon});
      relation["landuse"="quarry"](around:7000,{lat},{lon});
    );
    out center;
    \"\"\"
    
    try:
        import requests
        headers = {'User-Agent': 'VayuDrishti/1.0 (Delhi Air Quality App)'}
        resp = requests.get(overpass_url, params={'data': query}, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        sources = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            
            # Determine type
            source_type = "Industrial Area"
            if "man_made" in tags and tags["man_made"] == "works":
                source_type = "Factory/Works"
            elif "power" in tags and tags["power"] == "plant":
                source_type = "Power Plant"
            elif "landuse" in tags and tags["landuse"] == "quarry":
                source_type = "Quarry"
            
            name = tags.get("name", tags.get("operator", "Unnamed industrial area"))
            
            # Get coords
            elat = element.get("lat", element.get("center", {}).get("lat"))
            elon = element.get("lon", element.get("center", {}).get("lon"))
            
            if elat and elon:
                import math
                def haversine(lat1, lon1, lat2, lon2):
                    R = 6371.0
                    dLat = math.radians(lat2 - lat1)
                    dLon = math.radians(lon2 - lon1)
                    a = math.sin(dLat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2)**2
                    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                    return R * c
                    
                dist = haversine(lat, lon, elat, elon)
                sources.append(PollutionSourceItem(name=name, type=source_type, distance_km=round(dist, 1)))
        
        unique_sources = {}
        for s in sources:
            key = f"{s.name}_{s.type}"
            if key not in unique_sources or s.distance_km < unique_sources[key].distance_km:
                unique_sources[key] = s
                
        sorted_sources = sorted(unique_sources.values(), key=lambda x: x.distance_km)[:5]
        
        _OVERPASS_CACHE[cache_key] = (sorted_sources, now)
        
        msg = None
        if not sorted_sources:
            msg = "No tagged industrial sources found within 7km."
            
        return NearbySourcesResponse(station=target["name"], sources=sorted_sources, message=msg)
        
    except Exception as e:
        print(f"Overpass API error: {e}")
        return NearbySourcesResponse(
            station=target["name"], 
            sources=[], 
            message="Could not fetch nearby sources at this time."
        )

"""

with open("backend/main.py", "a", encoding="utf-8") as f:
    f.write(code_to_append)

print("Endpoint added.")
