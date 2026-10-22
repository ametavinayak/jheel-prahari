"""Drained-lake check: Sentinel-1 radar before vs after, read inside the lake's last known outline."""
import numpy as np
from scipy import ndimage

from . import segment
from .stac import read_window, search, to_db

LOSS_ALARM = 0.25  # a quarter of the open water gone between two passes = drained


def radar_pair(aoi, event_date, orbit="descending", days=24):
    """Last pass before and first pass after `event_date` on the same orbit direction (same geometry)."""
    import datetime as dt
    d = dt.date.fromisoformat(event_date)
    items = search("sentinel-1-rtc", aoi, f"{d - dt.timedelta(days=days)}/{d + dt.timedelta(days=days)}")
    items = [i for i in items if i.properties.get("sat:orbit_state") == orbit]
    before = sorted([i for i in items if i.datetime.date() < d], key=lambda i: i.datetime)[-1:]
    after = sorted([i for i in items if i.datetime.date() > d], key=lambda i: i.datetime)[:1]
    if not before or not after:
        raise LookupError(f"no {orbit} radar pass on both sides of {event_date}")
    return before[0], after[0]


def vv_db(item, aoi, grid):
    vv, _, _ = read_window(item.assets["vv"].href, aoi, ref=grid)
    db = to_db(vv.astype("float32"))
    return ndimage.median_filter(np.nan_to_num(db, nan=0.0), size=5)  # speckle down before thresholding


def check(lake_mask, grid, aoi, before, after, buffer_px=10):
    """Water area inside (lake outline + buffer) on both passes; `drained` if the loss crosses the alarm."""
    zone = ndimage.binary_dilation(lake_mask, iterations=buffer_px)
    pre, post = vv_db(before, aoi, grid), vv_db(after, aoi, grid)
    _, _, t = segment.water_s1(np.where(zone, pre, np.nan))   # one threshold, learned on the pre-burst pass
    w_pre = segment.clean((pre < t) & zone)
    w_post = segment.clean((post < t) & zone)
    px = abs(grid[0].a * grid[0].e)
    a_pre, a_post = float(w_pre.sum()) * px, float(w_post.sum()) * px
    loss = 1.0 - a_post / a_pre if a_pre else 0.0
    with np.errstate(invalid="ignore"):
        log_ratio = float(np.nanmean((post - pre)[lake_mask]))
    return {"before": {"item": before.id, "date": before.datetime.date().isoformat(), "water_m2": a_pre},
            "after": {"item": after.id, "date": after.datetime.date().isoformat(), "water_m2": a_post},
            "threshold_db": round(t, 2), "area_loss": round(loss, 4), "mean_log_ratio_db": round(log_ratio, 2),
            "drained": bool(loss >= LOSS_ALARM),
            "masks": (w_pre, w_post)}


def latest_pair(aoi, orbit="descending", days=40, today=None):
    """The two most recent passes on one orbit direction: what a live scan compares."""
    import datetime as dt
    today = today or dt.date.today()
    items = search("sentinel-1-rtc", aoi, f"{today - dt.timedelta(days=days)}/{today}")
    items = sorted([i for i in items if i.properties.get("sat:orbit_state") == orbit], key=lambda i: i.datetime)
    if len(items) < 2:
        raise LookupError(f"fewer than two {orbit} radar passes in the last {days} days")
    return items[-2], items[-1]


def check_live(outline_geojson, aoi, orbit="descending"):
    """Drain check on the latest pair, with the lake zone taken from the most recent optical outline."""
    from pyproj import Transformer
    from rasterio.features import rasterize
    from shapely.geometry import shape as to_shape
    from shapely.ops import transform as shp_transform

    before, after = latest_pair(aoi, orbit)
    vv, t, crs = read_window(before.assets["vv"].href, aoi)
    tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    geom = shp_transform(tf, to_shape(outline_geojson))
    mask = rasterize([(geom, 1)], out_shape=vv.shape, transform=t, fill=0).astype(bool)
    res = check(mask, (t, vv.shape, crs), aoi, before, after)
    res.pop("masks")
    return res
