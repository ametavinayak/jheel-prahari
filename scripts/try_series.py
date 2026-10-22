import time
from jheel.config import LAKE
from jheel import series
aoi, seed = LAKE["aoi"], LAKE["seed"]; ref = None
windows = [(f"{y}-08-01", f"{y}-11-30") for y in range(2016, 2023)] + [("2023-08-01", "2023-10-02"), ("2023-10-04", "2023-11-30")]
for start, end in windows:
    t0 = time.time()
    b = series.best_scene(aoi, start, end)
    if not b: print(start, "no scene"); continue
    f, it = b
    r = series.segment_scene(it, aoi, seed, ref)
    if r["mask"].any(): ref = r["mask"]
    print(start[:4], it.datetime.date(), f"clear {f:.2f}", f"area {r['area_m2']/1e6:.3f} km2", f"lake-clear {r['clear_in_lake']:.2f}", f"{time.time()-t0:.0f}s")
