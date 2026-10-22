import sys, numpy as np
from PIL import Image
from jheel.config import LAKE
from jheel.stac import search, read_window
from jheel import series
aoi, seed = LAKE["aoi"], LAKE["seed"]
for day in sys.argv[1:]:
    it = [i for i in search("sentinel-2-l2a", aoi, f"{day}/{day}") if series.covers(i, aoi)][0]
    r = series.segment_scene(it, aoi, seed)
    t, crs = r["transform"], r["crs"]
    grid = (t, r["mask"].shape, crs)
    rgb = np.dstack([read_window(it.assets[b].href, aoi, ref=grid)[0] for b in ("B04","B03","B02")]).astype("f4")
    rgb = np.clip(rgb/np.percentile(rgb,99)*255,0,255).astype("uint8")
    ov = rgb.copy(); ov[r["mask"]] = (0.5*ov[r["mask"]] + 0.5*np.array([255,60,0])).astype("uint8")
    Image.fromarray(np.hstack([rgb, ov])).crop((250,350,1192*2 if False else 2384,700)).save(f"out/viz_{day}.png")
    print(day, r["area_m2"]/1e6, it.properties.get("s2:processing_baseline"))
