"""Lake area per date from the clearest Sentinel-2 scenes of the ice-free season."""
import datetime as dt

import numpy as np
from pyproj import Transformer
from rasterio.enums import Resampling
from scipy import ndimage
from shapely.geometry import box, shape

from . import segment
from .stac import read_window, search

SEASON = (8, 11)          # Aug-Nov: lake ice-free, after the worst of the monsoon
MAX_TILE_CLOUD = 70


def covers(item, aoi):
    """Only scenes whose footprint holds the whole AOI: an edge tile returns a half-empty window."""
    return shape(item.geometry).contains(box(*aoi))


def boa_offset(item):
    """Baseline 04.00+ L2A products carry a +1000 offset on reflectance digital numbers."""
    try:
        return 1000 if float(item.properties.get("s2:processing_baseline", "0")) >= 4.0 else 0
    except ValueError:
        return 0


def clear_fraction(item, aoi):
    scl, _, _ = read_window(item.assets["SCL"].href, aoi, resampling=Resampling.nearest)
    valid = scl > 0
    good = valid & ~np.isin(scl, segment.SCL_BAD)
    return float(good.sum()) / max(1, valid.sum())


def candidates(aoi, start, end):
    items = search("sentinel-2-l2a", aoi, f"{start}/{end}", {"eo:cloud_cover": {"lt": MAX_TILE_CLOUD}})
    return sorted([i for i in items if covers(i, aoi)], key=lambda it: it.properties["eo:cloud_cover"])


def best_scene(aoi, start, end, min_clear=0.9, max_checks=8):
    """Clearest scene over the AOI itself (tile cloud cover says little about one valley)."""
    best = None
    for it in candidates(aoi, start, end)[:max_checks]:
        f = clear_fraction(it, aoi)
        if best is None or f > best[0]:
            best = (f, it)
        if f >= min_clear:
            break
    return best


def seed_pixel(seed_lonlat, transform, crs):
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(*seed_lonlat)
    col, row = ~transform * (x, y)
    return int(row), int(col)


def pick_lake(water, seed_rc, ref_mask=None, search_px=30):
    """The lake: the water body at the seed; else the one overlapping last time's outline; else the
    nearest body within `search_px` of the seed (a frozen or cloudy seed pixel must not lose the lake)."""
    lake = segment.component_at(water, *seed_rc)
    if lake.any():
        return lake
    if ref_mask is not None and ref_mask.shape == water.shape:
        lake = segment.component_overlapping(water, ref_mask)
        if lake.any():
            return lake
    r, c = seed_rc
    near = np.zeros_like(water, bool)
    near[max(0, r - search_px):r + search_px + 1, max(0, c - search_px):c + search_px + 1] = True
    lab, n = ndimage.label(water)
    hits = np.unique(lab[near & water])
    hits = hits[hits > 0]
    if hits.size == 0:
        return np.zeros_like(water, bool)
    sizes = ndimage.sum(water, lab, hits)
    return lab == hits[int(np.argmax(sizes))]


def segment_scene(item, aoi, seed, ref_mask=None):
    """Water mask of the lake in one scene, on the 10 m grid of B03."""
    off = boa_offset(item)
    g, t, crs = read_window(item.assets["B03"].href, aoi)
    grid = (t, g.shape, crs)
    n, _, _ = read_window(item.assets["B08"].href, aoi, ref=grid)
    s, _, _ = read_window(item.assets["B11"].href, aoi, ref=grid)
    scl, _, _ = read_window(item.assets["SCL"].href, aoi, ref=grid, resampling=Resampling.nearest)
    nodata = g == 0
    G, N, S = (segment.reflectance(a, off) for a in (g, n, s))
    G[nodata] = np.nan
    water, valid = segment.water_s2(G, N, S, scl)
    water = segment.clean(water)
    lake = pick_lake(water, seed_pixel(seed, t, crs), ref_mask)
    return {"mask": lake, "valid": valid, "transform": t, "crs": crs,
            "date": item.datetime.date().isoformat(), "item": item.id,
            "area_m2": segment.area_m2(lake, t),
            "clear_in_lake": float(valid[lake].mean()) if lake.any() else 0.0}


def trend(points):
    """Theil-Sen slope (m2 per year): robust to one bad year."""
    if len(points) < 2:
        return None
    x = np.array([dt.date.fromisoformat(d).toordinal() / 365.25 for d, _ in points])
    y = np.array([a for _, a in points])
    slopes = [(y[j] - y[i]) / (x[j] - x[i]) for i in range(len(x)) for j in range(i + 1, len(x)) if x[j] != x[i]]
    return float(np.median(slopes))
