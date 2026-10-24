"""Ask the lake a question. Answers are built from the measured series, drain check and ETA table; every
answer carries the steps that produced it (what was read, from which source). With VLM_URL set, questions
the measurements can't answer go to a vision-language model service."""
import base64
import os
import re
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent / "web"


class Trace:
    def __init__(self):
        self.steps, self._t = [], time.perf_counter()

    def add(self, tool, detail, source=None):
        now = time.perf_counter()
        self.steps.append({"tool": tool, "detail": detail, "source": source,
                           "ms": round((now - self._t) * 1000, 2)})
        self._t = now


def _place(q, eta):
    for row in eta:
        for word in re.split(r"[\s·\-]+", row["name"].lower()):
            if len(word) > 3 and word in q:
                return row
    return None


def answer(q, lake):
    ql = q.lower().strip()
    if not ql:
        raise ValueError("empty question")
    tr = Trace()
    s, g, d, eta = lake["series"], lake["growth"], lake["drain_check"], lake["eta"]
    pre = [x for x in s if not x["after_burst"]]

    def out(text, evidence, intent):
        return {"answer": text, "evidence": evidence, "intent": intent, "steps": tr.steps}

    if any(w in ql for w in ("drain", "burst", "empt", "outburst", "breach")):
        tr.add("intent", "drain status")
        b, a = d["before"], d["after"]
        tr.add("radar.drain_check", f"{b['date']} → {a['date']}: {b['water_m2'] / 1e6:.2f} → {a['water_m2'] / 1e6:.2f} km², "
               f"threshold {d['threshold_db']} dB", "Sentinel-1 RTC")
        verdict = "Yes, it drained." if d["drained"] else "No sign of draining."
        return out(f"{verdict} Open water inside the lake outline fell from {b['water_m2'] / 1e6:.2f} km² ({b['date']}) "
                   f"to {a['water_m2'] / 1e6:.2f} km² ({a['date']}), a {d['area_loss']:.0%} loss on Sentinel-1 radar.",
                   ["drain_check"], "drain")
    row = _place(ql, eta)
    if row or any(w in ql for w in ("how much time", "when", "minutes", "reach", "eta", "arrive")):
        tr.add("intent", "arrival time" + (f" · place: {row['name']}" if row else " · all places"))
        tr.add("dem.flowpath", f"{lake['flowpath']['length_km']} km D8 path from the lake", "Copernicus DEM GLO-30")
        tr.add("eta.lookup", f"calibrated {lake['speed_kmh']['kmh_slow']}–{lake['speed_kmh']['kmh_fast']} km/h on 2023",
               "ETA table")
        if row:
            return out(f"{row['name']} is {row['river_km']} km down the river; water would arrive "
                       f"{row['eta_min']}-{row['eta_max']} minutes after an outburst. {row['action']}",
                       ["flowpath", "eta"], "eta")
        lines = "; ".join(f"{r['name']} {r['eta_min']}-{r['eta_max']} min" for r in eta)
        return out(f"Arrival after an outburst: {lines}.", ["flowpath", "eta"], "eta")
    if any(w in ql for w in ("grow", "bigger", "larger", "expand", "change", "trend")):
        tr.add("intent", "growth")
        tr.add("lake.series", f"{len(pre)} pre-burst scenes, {g['from']} → {g['to']}", "Sentinel-2 L2A")
        tr.add("trend.theil_sen", f"{g['trend_km2_per_year']:+.3f} km² per year", None)
        return out(f"Yes. {lake['lake']['name']} grew from {g['from_km2']:.2f} km² ({g['from']}) to {g['to_km2']:.2f} km² "
                   f"({g['to']}), +{g['pct']}% in {g['years']} years (trend {g['trend_km2_per_year']:+.3f} km² a year).",
                   ["series"], "growth")
    if any(w in ql for w in ("area", "big", "size", "large", "how much water")):
        tr.add("intent", "area")
        last = s[-1]
        tr.add("lake.segment", f"{last['date']}: NDWI + NIR rule, {last['clear_over_lake']:.0%} of lake cloud-free",
               "Sentinel-2 L2A")
        return out(f"{last['area_km2']:.2f} km² on {last['date']} (Sentinel-2, {last['clear_over_lake']:.0%} of the lake "
                   f"cloud-free). Before the 2023 burst: {pre[-1]['area_km2']:.2f} km² on {pre[-1]['date']}.",
                   ["series"], "area")
    if any(w in ql for w in ("who", "which", "places", "villages", "downstream", "risk")):
        tr.add("intent", "exposure")
        tr.add("dem.flowpath", f"{len(eta)} places within 2.5 km of the path", "Copernicus DEM GLO-30 + OSM")
        names = ", ".join(f"{r['name']} ({r['river_km']} km)" for r in eta)
        return out(f"On the flood path, nearest first: {names}.", ["flowpath"], "exposure")
    tr.add("intent", "not covered by measurements")
    vlm = ask_vlm(q, s[-1], tr)
    if vlm:
        return {**vlm, "intent": "vlm", "steps": tr.steps}
    return out("I can answer about the lake's area, growth, whether it drained, and arrival times for places "
               "downstream.", [], "help")


def ask_vlm(q, scene, tr):
    """Forward an image question to the vision-language model service, if one is configured."""
    url = os.environ.get("VLM_URL")
    if not url:
        return None
    img = ROOT / scene["image"]
    payload = {"query": q, "files": [{"name": img.name, "b64": base64.b64encode(img.read_bytes()).decode()}]}
    try:
        r = requests.post(url.rstrip("/") + "/answer", json=payload, timeout=60)
        r.raise_for_status()
        text = r.json().get("output", {}).get("text") or "No answer."
        tr.add("vlm.answer", f"scene {scene['date']}", "vision-language model")
        return {"answer": text, "evidence": ["vision-language model", scene["date"]]}
    except (requests.RequestException, ValueError) as e:
        tr.add("vlm.answer", f"unreachable: {type(e).__name__}", None)
        return {"answer": f"The vision-language model is unreachable ({type(e).__name__}).", "evidence": []}
