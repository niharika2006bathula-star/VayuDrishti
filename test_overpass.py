import requests

overpass_url = "https://overpass-api.de/api/interpreter"
lat, lon = 28.6473, 77.3159 # Anand Vihar coords
query = f"""
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
"""
print("Querying overpass...")
try:
    resp = requests.post(overpass_url, data={'data': query}, timeout=30)
    print("Status:", resp.status_code)
    if resp.status_code != 200:
        print("Error text:", resp.text)
    data = resp.json()
    print("Got", len(data.get("elements", [])), "elements")
    for el in data.get("elements", [])[:5]:
        print(el.get("tags", {}).get("name", "Unnamed"), el.get("tags"))
except Exception as e:
    print("Error:", e)
