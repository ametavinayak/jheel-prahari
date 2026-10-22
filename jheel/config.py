"""Fixed facts for the prototype: the watched lake, the places below it, and the 2023 calibration."""

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# South Lhonak lake, North Sikkim. The seed point sits inside the lake (checked on the 18 Nov 2021 scene);
# the pipeline follows the water body that contains it, not simply the largest one in the box.
LAKE = {
    "id": "south-lhonak",
    "name": "South Lhonak",
    "aoi": (88.15, 27.86, 88.27, 27.96),  # lon_min, lat_min, lon_max, lat_max
    "seed": (88.19515, 27.91192),          # lon, lat
}

# Downstream places (OpenStreetMap / Nominatim coordinates, fetched 22 Oct 2026).
ASSETS = [
    {"id": "lachen", "name": "Lachen", "kind": "village", "lat": 27.7306, "lon": 88.5495,
     "action": "Move everyone uphill, away from the river, now."},
    {"id": "chungthang", "name": "Chungthang · Teesta-III dam", "kind": "dam", "lat": 27.6042, "lon": 88.6465,
     "action": "Open spillway gates, evacuate the powerhouse and dam crew."},
    {"id": "dikchu", "name": "Dikchu", "kind": "town", "lat": 27.4022, "lon": 88.5224,
     "action": "Clear the riverbank and the bridge approach; move uphill."},
    {"id": "singtam", "name": "Singtam", "kind": "town", "lat": 27.2320, "lon": 88.4971,
     "action": "Close the Teesta bridge, clear riverside homes and the bazaar."},
    {"id": "rangpo", "name": "Rangpo", "kind": "town", "lat": 27.1744, "lon": 88.5303,
     "action": "Close NH10 along the river, clear riverside settlements."},
]

# 2023 event used to calibrate arrival times (Eos landslide blog; Science, Sattar et al. 2025):
# landslide into the lake at 22:13 IST on 3 Oct; flood at Chungthang between ~00:00 and ~00:30 on 4 Oct.
CALIBRATION = {"asset": "chungthang", "minutes_min": 107, "minutes_max": 137}

BURST_DATE = "2023-10-03"
DEM_WINDOW = (88.10, 27.10, 88.80, 27.96)  # covers lake -> Rangpo
