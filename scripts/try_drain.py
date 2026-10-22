import numpy as np
from PIL import Image
from jheel.config import LAKE, BURST_DATE
from jheel import series, drain
from jheel.stac import search
aoi, seed = LAKE["aoi"], LAKE["seed"]
it=[i for i in search("sentinel-2-l2a", aoi, "2023-08-30/2023-08-30") if series.covers(i, aoi)][0]
r = series.segment_scene(it, aoi, seed)
grid = (r["transform"], r["mask"].shape, r["crs"])
b, a = drain.radar_pair(aoi, BURST_DATE)
print("pair", b.id, a.id)
res = drain.check(r["mask"], grid, aoi, b, a)
w0, w1 = res.pop("masks")
print(res)
img = np.zeros(r["mask"].shape+(3,),"uint8"); img[r["mask"]]=(60,60,60); img[w0]=(0,150,255); img[w1&~w0]=(255,255,0); img[w0&w1]=(0,255,120)
Image.fromarray(img).crop((250,350,950,700)).save("out/drain.png")
# stable control: two passes before the burst on the same orbit
items = sorted([i for i in search("sentinel-1-rtc", aoi, "2023-08-20/2023-10-02") if i.properties.get("sat:orbit_state")=="descending"], key=lambda i:i.datetime)
print("control pair", items[-2].datetime.date(), items[-1].datetime.date())
c = drain.check(r["mask"], grid, aoi, items[-2], items[-1]); c.pop("masks"); print("control", c)
