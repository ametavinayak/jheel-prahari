import sys, time, json
from jheel import area
cases = {
  "lhonak-2023": (area.box_around(27.905, 88.20, 0.07), "2023-10-01"),
  "lhonak-now": (area.box_around(27.905, 88.20, 0.07), None),
  "tsomgo": (area.box_around(27.375, 88.762, 0.03), None),
  "gurudongmar": (area.box_around(28.0270885, 88.7106908), None),
}
for name in sys.argv[1:] or cases:
    b, asof = cases[name]; t = time.time()
    r = area.analyse(b, asof)
    print(f"== {name} {round(time.time()-t)}s recent {r['recent']['date']} older {r['older'] and r['older']['date']} counts {r['counts']}")
    for lk in [x for x in r["lakes"] if x["class"]!="stable"][:12] + [x for x in r["lakes"] if x["area_km2"]>0.3][:6]:
        print("  ", lk["id"], lk["class"], lk["score"], lk["area_km2"], lk["old_area_km2"], lk["growth_pct"], lk["elevation_m"], lk["glacier_fed"], lk["ice_contact"], lk["outlet_slope_deg"], (lk["lat"], lk["lon"]), lk["why"])
