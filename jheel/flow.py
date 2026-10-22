"""Impact model: D8 flow path from the lake down the valley on Copernicus DEM GLO-30, river distance to each
place, and arrival-time ranges calibrated on the 2023 South Lhonak flood. No inference at alarm time."""
import math
from pathlib import Path

import numpy as np
import rasterio

from .stac import read_window, search

# pysheds D8 direction codes -> (drow, dcol)
D8 = {64: (-1, 0), 128: (-1, 1), 1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1)}


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_dem(window, path):
    """Clip the Copernicus 30 m DEM to `window` and save it (pysheds reads from a file)."""
    path = Path(path)
    if path.exists():
        return path
    items = search("cop-dem-glo-30", window)
    if not items:
        raise LookupError("no Copernicus DEM tile covers the window")
    tiles = []
    for it in items:
        arr, t, crs = read_window(it.assets["data"].href, window)
        tiles.append((arr, t, crs))
    if len(tiles) > 1:
        raise NotImplementedError("window spans several DEM tiles; mosaic them first")
    arr, t, crs = tiles[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                       dtype="float32", crs=crs, transform=t, compress="deflate") as dst:
        dst.write(arr.astype("float32"), 1)
    return path


def flow_directions(dem_path):
    from pysheds.grid import Grid
    grid = Grid.from_raster(str(dem_path))
    dem = grid.read_raster(str(dem_path))
    conditioned = grid.resolve_flats(grid.fill_depressions(grid.fill_pits(dem)))
    fdir = grid.flowdir(conditioned, dirmap=(64, 128, 1, 2, 4, 8, 16, 32))
    return np.asarray(fdir), grid.affine, np.asarray(dem)


def trace(fdir, transform, start_lonlat, max_steps=200000):
    """Follow D8 directions from the start until the path leaves the grid or hits a sink.
    Returns [(lon, lat, elev_index_row, col, cumulative_m)]."""
    col, row = ~transform * start_lonlat
    r, c = int(row), int(col)
    pts, dist, seen = [], 0.0, set()
    lon0, lat0 = transform * (c + 0.5, r + 0.5)
    for _ in range(max_steps):
        if not (0 <= r < fdir.shape[0] and 0 <= c < fdir.shape[1]) or (r, c) in seen:
            break
        seen.add((r, c))
        lon, lat = transform * (c + 0.5, r + 0.5)
        if pts:
            dist += haversine_m(pts[-1][1], pts[-1][0], lat, lon)
        pts.append((lon, lat, r, c, dist))
        step = D8.get(int(fdir[r, c]))
        if step is None:
            break
        r, c = r + step[0], c + step[1]
    return pts


def snap_assets(path, assets, max_offset_m=2500):
    """River distance of each place: the nearest path point, if the river passes within `max_offset_m`."""
    out = []
    for a in assets:
        best = min(path, key=lambda p: haversine_m(a["lat"], a["lon"], p[1], p[0]))
        off = haversine_m(a["lat"], a["lon"], best[1], best[0])
        out.append({**a, "river_km": round(best[4] / 1000, 2), "offset_m": round(off),
                    "on_path": off <= max_offset_m})
    return out


def eta_table(snapped, calibration):
    """Arrival time per place as a range, scaled by river distance from the calibration point.
    Linear in distance: a first-order estimate (wave attenuation is ignored), shown as a range on purpose."""
    ref = next(a for a in snapped if a["id"] == calibration["asset"])
    if ref["river_km"] <= 0:
        raise ValueError("calibration point has no river distance")
    v_fast = ref["river_km"] / calibration["minutes_min"]   # km per minute
    v_slow = ref["river_km"] / calibration["minutes_max"]
    rows = []
    for a in snapped:
        if not a["on_path"]:
            continue
        rows.append({**a, "eta_min": round(a["river_km"] / v_fast), "eta_max": round(a["river_km"] / v_slow)})
    return sorted(rows, key=lambda x: x["river_km"]), {"kmh_fast": round(v_fast * 60, 1), "kmh_slow": round(v_slow * 60, 1)}
