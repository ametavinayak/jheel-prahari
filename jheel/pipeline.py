"""Build everything the app serves for one lake: area series with outlines, the radar drain check, the flood
path and the arrival-time table. Run once (minutes); the app then only reads data/<lake>.json."""
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Transformer
from shapely.geometry import mapping
from shapely.ops import transform as shp_transform

from . import drain, flow, series
from .config import ASSETS, BURST_DATE, CALIBRATION, DEM_WINDOW, LAKE
from .stac import read_window

ROOT = Path(__file__).resolve().parent.parent
DATA, SCENES = ROOT / "data", ROOT / "web" / "scenes"


def to_wgs84(geom, crs):
    tf = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    return shp_transform(tf, geom)


def bounds_wgs84(transform, shape, crs):
    tf = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    h, w = shape
    xs, ys = zip(*[transform * (c, r) for c, r in ((0, 0), (w, 0), (0, h), (w, h))])
    lons, lats = tf.transform(xs, ys)
    return [[min(lats), min(lons)], [max(lats), max(lons)]]


def save_rgb(item, aoi, grid, path):
    off = series.boa_offset(item)
    bands = [read_window(item.assets[b].href, aoi, ref=grid)[0].astype("float32") - off for b in ("B04", "B03", "B02")]
    rgb = np.dstack(bands)
    rgb = np.clip(rgb / np.nanpercentile(rgb, 99) * 255, 0, 255).astype("uint8")
    Image.fromarray(rgb).save(path)


def lake_series(log):
    aoi, seed = LAKE["aoi"], LAKE["seed"]
    windows = [(f"{y}-08-01", f"{y}-11-30") for y in range(2016, 2023)]
    windows += [("2023-08-01", "2023-10-02"), ("2023-10-04", "2023-11-30")]
    rows, ref, keep = [], None, {}
    for start, end in windows:
        best = series.best_scene(aoi, start, end)
        if not best:
            log(f"  {start[:4]}: no scene")
            continue
        clear, item = best
        r = series.segment_scene(item, aoi, seed, ref)
        if not r["mask"].any():
            log(f"  {r['date']}: lake not found")
            continue
        ref = r["mask"]
        geom = to_wgs84(series.segment.outline(r["mask"], r["transform"]), r["crs"]).simplify(0.00005)
        grid = (r["transform"], r["mask"].shape, r["crs"])
        png = f"{r['date']}.png"
        save_rgb(item, aoi, grid, SCENES / png)
        after = r["date"] > BURST_DATE
        rows.append({"date": r["date"], "scene": r["item"], "area_km2": round(r["area_m2"] / 1e6, 4),
                     "clear_over_lake": round(r["clear_in_lake"], 3), "after_burst": after,
                     "outline": mapping(geom), "image": f"scenes/{png}",
                     "image_bounds": bounds_wgs84(r["transform"], r["mask"].shape, r["crs"])})
        keep[r["date"]] = (r["mask"], grid)
        log(f"  {r['date']}: {r['area_m2'] / 1e6:.3f} km2 (clear {clear:.2f})")
    pre = [(x["date"], x["area_km2"] * 1e6) for x in rows if not x["after_burst"]]
    slope = series.trend(pre)
    return rows, slope, keep


def run(log=print):
    t0 = time.time()
    DATA.mkdir(exist_ok=True)
    SCENES.mkdir(parents=True, exist_ok=True)
    aoi = LAKE["aoi"]

    log("lake series (Sentinel-2)")
    rows, slope, keep = lake_series(log)
    last_pre = [x for x in rows if not x["after_burst"]][-1]
    mask, grid = keep[last_pre["date"]]

    log("radar drain check (Sentinel-1)")
    before, after = drain.radar_pair(aoi, BURST_DATE)
    d = drain.check(mask, grid, aoi, before, after)
    d.pop("masks")
    log(f"  {d['before']['date']} -> {d['after']['date']}: loss {d['area_loss']:.1%}, drained={d['drained']}")

    log("flood path (Copernicus DEM)")
    dem = flow.fetch_dem(DEM_WINDOW, DATA / "dem_teesta.tif")
    fdir, aff, _ = flow.flow_directions(dem)
    path = flow.trace(fdir, aff, LAKE["seed"])
    snapped = flow.snap_assets(path, ASSETS)
    eta, speed = flow.eta_table(snapped, CALIBRATION)
    line = [[round(p[0], 5), round(p[1], 5)] for p in path[::3]] + [[round(path[-1][0], 5), round(path[-1][1], 5)]]
    log(f"  {path[-1][4] / 1000:.1f} km; {len(eta)} places on the path")

    first, last = rows[0], last_pre
    years = (np.datetime64(last["date"]) - np.datetime64(first["date"])).astype(int) / 365.25
    out = {
        "lake": {**LAKE, "aoi": list(LAKE["aoi"]), "seed": list(LAKE["seed"])},
        "series": rows,
        "growth": {"from": first["date"], "to": last["date"], "from_km2": first["area_km2"], "to_km2": last["area_km2"],
                   "pct": round((last["area_km2"] / first["area_km2"] - 1) * 100, 1),
                   "trend_km2_per_year": round(slope / 1e6, 4) if slope else None, "years": round(float(years), 1)},
        "drain_check": d,
        "flowpath": {"type": "LineString", "coordinates": line, "length_km": round(path[-1][4] / 1000, 1)},
        "eta": eta, "speed_kmh": speed, "calibration": CALIBRATION,
        "method": {"segmenter": "NDWI > 0.2 and NIR < 0.15 on Sentinel-2 L2A; cloud labels kept only where SWIR > 0.10",
                   "drain": f"Sentinel-1 RTC VV, 5x5 median, Otsu threshold on the pre pass, alarm at {drain.LOSS_ALARM:.0%} loss",
                   "flow": "Copernicus DEM GLO-30, pysheds fill + resolve flats + D8"},
        "built_s": round(time.time() - t0),
    }
    (DATA / f"{LAKE['id']}.json").write_text(json.dumps(out, indent=1))
    log(f"done in {out['built_s']} s -> data/{LAKE['id']}.json")
    return out


if __name__ == "__main__":
    run()
