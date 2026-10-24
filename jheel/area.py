"""Screen any area for glacial-lake outburst hazard.

For a box of up to ~25 x 25 km: find every lake in a recent and an older ice-free Sentinel-2 scene, match each
lake across the two dates, and score it. A lake is only treated as a hazard candidate if it is glacier-fed
(snow/ice next to it and high altitude). Growth, glacier contact, size and the steepness of the valley below
it then set a 0-100 screening score. This is a ranking of the kind published GLOF hazard assessments use,
not a probability of outburst."""
import datetime as dt
import re

import numpy as np
import requests
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from scipy import ndimage
from shapely.geometry import mapping
from shapely.ops import transform as shp_transform

import rasterio
from . import segment, series
from .stac import GDAL_ENV, read_window, search

MAX_DEG = 0.25           # box side limit, keeps one analysis around a minute
RES = 20                 # metres; enough for lakes >= 0.01 km2 (25 px)
MIN_LAKE_KM2 = 0.01
ICE_BUFFER_M = 500
CONTACT_M = 100
GLACIAL_MIN_ELEV = 3500
HAZARD_MIN_KM2 = 0.05     # smaller lakes cannot hold enough water to threaten the valley
GROWTH_MIN_KM2 = 0.02     # growth must be real in absolute terms, not a big % of a puddle
OLD_CLEAR_MIN = 0.8       # the older scene must actually see the lake's footprint
SEASON = (8, 11)


def geocode(q):
    """OpenStreetMap Nominatim first (exact), then Photon (fuzzy, tolerates spelling variants)."""
    q = q.strip()
    if not q:
        raise ValueError("empty place name")
    ua = {"User-Agent": "jheel-prahari/0.1"}
    # OSM often names a lake without the word "lake" ("Gurudongmar"); retry without generic words.
    bare = re.sub(r"\b(lake|lakes|tal|taal|tso|glacial|glacier|jheel)\b", " ", q, flags=re.I).strip()
    for attempt in dict.fromkeys([q, bare]):
        if not attempt:
            continue
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={"q": attempt, "format": "json", "limit": 1}, headers=ua, timeout=20)
        r.raise_for_status()
        if r.json():
            h = r.json()[0]
            return {"name": h["display_name"], "lat": float(h["lat"]), "lon": float(h["lon"])}
    r = requests.get("https://photon.komoot.io/api/", params={"q": q, "limit": 1}, headers=ua, timeout=20)
    r.raise_for_status()
    feats = r.json().get("features", [])
    if not feats:
        raise LookupError(f"no place called {q!r}")
    p = feats[0]["properties"]
    lon, lat = feats[0]["geometry"]["coordinates"]
    name = ", ".join(x for x in (p.get("name"), p.get("county"), p.get("state"), p.get("country")) if x)
    return {"name": name, "lat": float(lat), "lon": float(lon)}


def box_around(lat, lon, half=0.08):
    return (lon - half, lat - half, lon + half, lat + half)


def check_box(b):
    w, s, e, n = b
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise ValueError("invalid area")
    if e - w > MAX_DEG or n - s > MAX_DEG:
        raise ValueError(f"area too large: zoom in to at most {MAX_DEG} degrees a side")
    return b


def scene_for(b, year, until=None):
    start, end = f"{year}-{SEASON[0]:02d}-01", until or f"{year}-{SEASON[1]:02d}-30"
    best = series.best_scene(b, start, end, min_clear=0.85, max_checks=6)
    return best


def water_and_ice(item, b):
    """Water mask, ice mask and grid at RES metres."""
    off = series.boa_offset(item)
    g, t, crs = read_window(item.assets["B03"].href, b, res=RES)
    grid = (t, g.shape, crs)
    n = read_window(item.assets["B08"].href, b, ref=grid)[0]
    s = read_window(item.assets["B11"].href, b, ref=grid)[0]
    scl = read_window(item.assets["SCL"].href, b, ref=grid, resampling=Resampling.nearest)[0]
    nodata = g == 0
    G, N, S = (segment.reflectance(a, off) for a in (g, n, s))
    G[nodata] = np.nan
    water, valid = segment.water_s2(G, N, S, scl)
    water = segment.clean(water, open_iter=1, close_iter=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ndsi = (G - S) / (G + S)
    ice = (ndsi > 0.4) & (N > 0.2) & ~water & valid
    return water, ice, valid, grid


def dem_on(grid, b):
    """Copernicus DEM resampled onto the scene grid (handles tile edges and CRS)."""
    t, shape, crs = grid
    out = np.full(shape, np.nan, "float32")
    for it in search("cop-dem-glo-30", b):
        with rasterio.Env(**GDAL_ENV), rasterio.open(it.assets["data"].href) as src, \
                WarpedVRT(src, crs=crs, transform=t, width=shape[1], height=shape[0],
                          resampling=Resampling.bilinear) as vrt:
            a = vrt.read(1).astype("float32")
            a[a <= -1000] = np.nan
            out = np.where(np.isnan(out) & (a != 0), a, out)
    if np.isnan(out).all():
        raise LookupError("no elevation data for this area")
    return out


def downstream_slope(dem, lake, reach_m=2000):
    """Mean slope from the lake surface to the lowest ground within `reach_m` of its shore, in degrees.
    Steep ground below a lake means a flood that would gather speed and debris."""
    z = float(np.nanmedian(dem[lake]))
    dist = ndimage.distance_transform_edt(~lake) * RES
    zone = (dist > RES) & (dist <= reach_m) & np.isfinite(dem)
    if not zone.any():
        return None
    k = np.argmin(np.where(zone, dem, np.inf))
    drop, run = z - dem.flat[k], dist.flat[k]
    return float(np.degrees(np.arctan(max(drop, 0) / run)))


def classify(lk):
    """Hazard screening. Only glacier-fed lakes that are big enough and measurably growing are flagged.
    Static lakes, small ponds and lakes whose history we could not see are never scored as hazards."""
    g, area = lk["growth_pct"], lk["area_km2"]
    if not lk["glacier_fed"]:
        return 0, "stable", "Not glacier-fed: no snow or ice within 500 m, or below 3,500 m."
    if area < HAZARD_MIN_KM2:
        return 0, "low", f"Glacier-fed but small ({area:.3f} km²): too little water to threaten the valley."
    if lk["old_area_km2"] is None:
        return 0, "low", "Glacier-fed; the older scene was cloudy or snow-covered here, so growth is unknown. Rescan."
    gained = area - lk["old_area_km2"]
    if lk["new_lake"]:
        growth_pts = 30  # new lake: growth is real but its rate is unknown
    elif g is None or g <= 5 or gained < GROWTH_MIN_KM2:
        return 0, "stable", f"Glacier-fed but not growing ({(g or 0):+.0f}%, {gained:+.3f} km²)."
    else:
        growth_pts = 40 * min(g / 50, 1)
    score = round(growth_pts + (20 if lk["ice_contact"] else 0) + 20 * min(area / 1.0, 1)
                  + 20 * min((lk["outlet_slope_deg"] or 0) / 20, 1))
    lead = "New glacial lake" if lk["new_lake"] else f"Glacier-fed, grew {g:+.0f}% ({gained:+.2f} km²)"
    detail = (", in contact with ice" if lk["ice_contact"] else "") + (", steep valley below" if (lk["outlet_slope_deg"] or 0) >= 10 else "")
    if score >= 60:
        return score, "high", lead + detail + "."
    if score >= 35:
        return score, "watch", lead + detail + "; keep watching."
    return score, "low", lead + "; slow change."


def analyse(b, as_of=None, log=lambda *_: None):
    b = check_box(tuple(b))
    as_of = as_of or dt.date.today().isoformat()
    year = int(as_of[:4])
    if as_of[5:7] < f"{SEASON[0] + 1:02d}":
        year -= 1  # season not started yet this year
    log("recent scene")
    new = None
    for y in (year, year - 1):
        new = scene_for(b, y, as_of if y == int(as_of[:4]) else None)
        if new:
            break
    if not new:
        raise LookupError("no clear ice-free Sentinel-2 scene of this area (try another area)")
    new_y = new[1].datetime.year
    log("older scene")
    old = None
    for y in (new_y - 7, new_y - 6, new_y - 5, new_y - 8):
        if y >= 2016:
            old = scene_for(b, y)
            if old:
                break
    w_new, ice, valid_new, grid = water_and_ice(new[1], b)
    w_old, _, valid_old, _ = water_and_ice(old[1], b) if old else (None, None, None, None)
    log("elevation")
    dem = dem_on(grid, b)
    t, shape, crs = grid
    px_km2 = RES * RES / 1e6
    to_wgs = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    ice_near = ndimage.binary_dilation(ice, iterations=ICE_BUFFER_M // RES)

    lab, n = ndimage.label(w_new)
    lakes = []
    for k in range(1, n + 1):
        m = lab == k
        area = m.sum() * px_km2
        if area < MIN_LAKE_KM2:
            continue
        rr, cc = np.nonzero(m)
        if rr.min() == 0 or cc.min() == 0 or rr.max() == shape[0] - 1 or cc.max() == shape[1] - 1:
            continue  # cut by the box edge: area would be wrong
        old_area = None
        if w_old is not None and valid_old.shape == m.shape and valid_old[m].mean() >= OLD_CLEAR_MIN:
            old_lab, _ = ndimage.label(w_old)
            ids = np.unique(old_lab[m & w_old])
            ids = ids[ids > 0]
            old_area = float(np.isin(old_lab, ids).sum() * px_km2) if ids.size else 0.0
        elev = float(np.nanmedian(dem[m]))
        ring = ndimage.binary_dilation(m, iterations=1) & ~m
        contact = bool((ndimage.binary_dilation(m, iterations=max(1, CONTACT_M // RES)) & ice).any())
        glacier_fed = bool((ice_near & ring).any() or (ndimage.binary_dilation(m, iterations=ICE_BUFFER_M // RES) & ice).any()) \
            and elev >= GLACIAL_MIN_ELEV
        growth = None if old_area in (None, 0.0) else round((area / old_area - 1) * 100, 1)
        lk = {"area_km2": round(area, 3), "old_area_km2": None if old_area is None else round(old_area, 3),
              "growth_pct": growth, "new_lake": old_area == 0.0, "elevation_m": round(elev),
              "ice_contact": contact, "glacier_fed": glacier_fed,
              "outlet_slope_deg": None if np.isnan(elev) else round(downstream_slope(dem, m) or 0, 1)}
        lk["score"], lk["class"], lk["why"] = classify(lk)
        geom = shp_transform(to_wgs, segment.outline(m, t)).simplify(0.0001)
        c = geom.centroid
        lk.update({"outline": mapping(geom), "lat": round(c.y, 5), "lon": round(c.x, 5)})
        lakes.append(lk)
    lakes.sort(key=lambda x: -x["score"])
    for i, lk in enumerate(lakes):
        lk["id"] = f"L{i + 1}"
    counts = {c: sum(1 for x in lakes if x["class"] == c) for c in ("high", "watch", "low", "stable")}
    return {"box": list(b), "as_of": as_of,
            "recent": {"item": new[1].id, "date": new[1].datetime.date().isoformat(), "clear": round(new[0], 2)},
            "older": ({"item": old[1].id, "date": old[1].datetime.date().isoformat(), "clear": round(old[0], 2)} if old else None),
            "lakes": lakes, "counts": counts,
            "method": "Sentinel-2 water (NDWI>0.2, NIR<0.15) and ice (NDSI>0.4, NIR>0.2) at 20 m; Copernicus DEM. "
                      "Score = growth 40 + ice contact 20 + size 20 + valley slope 20, only for glacier-fed lakes."}
