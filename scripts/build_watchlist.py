"""Screen the North Sikkim glacier belt tile by tile and write data/watchlist.json: one ranked list of lakes.
Run:  .venv/Scripts/python scripts/build_watchlist.py   (about 1-2 minutes per tile; needs network)"""
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jheel import area  # noqa: E402

LATS = [27.78, 27.94, 28.08]
LONS = [88.12, 88.30, 88.48, 88.66]
OUT = Path(__file__).resolve().parent.parent / "data" / "watchlist.json"
KEEP = ("id", "class", "score", "why", "area_km2", "old_area_km2", "growth_pct", "new_lake", "elevation_m",
        "ice_contact", "glacier_fed", "outlet_slope_deg", "lat", "lon", "outline")


def near(a, b, deg=0.003):
    return abs(a["lat"] - b["lat"]) < deg and abs(a["lon"] - b["lon"]) < deg


def main():
    lakes, tiles, failed = [], [], []
    for lat in LATS:
        for lon in LONS:
            name = f"{lat:.2f}N {lon:.2f}E"
            t0 = time.time()
            try:
                res = area.analyse(area.box_around(lat, lon))
            except Exception as e:  # a tile with no clear scene is reported, not hidden
                failed.append({"tile": name, "error": f"{type(e).__name__}: {e}"})
                print("FAIL", name, e, flush=True)
                continue
            print(f"{name}: {res['counts']} recent {res['recent']['date']} older {res['older'] and res['older']['date']} "
                  f"({time.time() - t0:.0f}s)", flush=True)
            tiles.append({"tile": name, "box": res["box"], "counts": res["counts"], "recent": res["recent"]["date"],
                          "older": res["older"] and res["older"]["date"]})
            for lk in res["lakes"]:
                if lk["class"] in ("stable",):
                    continue
                row = {k: lk[k] for k in KEEP}
                row["tile"] = name
                if not any(near(row, x) for x in lakes):
                    lakes.append(row)
    lakes.sort(key=lambda x: -x["score"])
    for i, lk in enumerate(lakes):
        lk["id"] = f"S{i + 1}"
    out = {"built": dt.date.today().isoformat(), "region": "North Sikkim glacier belt", "tiles": tiles, "failed": failed,
           "lakes": lakes, "counts": {c: sum(1 for x in lakes if x["class"] == c) for c in ("high", "watch", "low")}}
    OUT.write_text(json.dumps(out))
    print("wrote", OUT, out["counts"], "failed tiles:", len(failed))


main()
