import time, json
from jheel.config import LAKE, ASSETS, CALIBRATION, DEM_WINDOW
from jheel import flow
t0=time.time()
p = flow.fetch_dem(DEM_WINDOW, "data/dem_teesta.tif"); print("dem", time.time()-t0)
fdir, aff, dem = flow.flow_directions(p); print("fdir", time.time()-t0, fdir.shape)
path = flow.trace(fdir, aff, LAKE["seed"]); print("path pts", len(path), "km", path[-1][4]/1000, "end", path[-1][:2], "elev start/end", dem[path[0][2],path[0][3]], dem[path[-1][2],path[-1][3]])
snapped = flow.snap_assets(path, ASSETS)
for a in snapped: print(a["name"], a["river_km"], a["offset_m"], a["on_path"])
rows, v = flow.eta_table(snapped, CALIBRATION); print(v)
for r in rows: print(r["name"], r["river_km"], r["eta_min"], r["eta_max"])
