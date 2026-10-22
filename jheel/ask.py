"""Ask the lake a question. Answers are built from the measured series, drain check and ETA table, and
always name the evidence. With VLM_URL set, image questions also go to the vision-language model."""
import base64
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent / "web"


def _place(q, eta):
    for row in eta:
        for word in re.split(r"[\s·\-]+", row["name"].lower()):
            if len(word) > 3 and word in q:
                return row
    return None


def answer(q, lake):
    ql = q.lower().strip()
    s, g, d, eta = lake["series"], lake["growth"], lake["drain_check"], lake["eta"]
    pre = [x for x in s if not x["after_burst"]]
    if not ql:
        raise ValueError("empty question")
    if any(w in ql for w in ("drain", "burst", "empt", "outburst", "breach")):
        b, a = d["before"], d["after"]
        verdict = "Yes, it drained." if d["drained"] else "No sign of draining."
        return {"answer": f"{verdict} Open water inside the lake outline fell from {b['water_m2'] / 1e6:.2f} km² "
                          f"({b['date']}) to {a['water_m2'] / 1e6:.2f} km² ({a['date']}), a {d['area_loss']:.0%} loss "
                          f"on Sentinel-1 radar.", "evidence": ["drain_check"]}
    row = _place(ql, eta)
    if row or any(w in ql for w in ("how much time", "when", "minutes", "reach", "eta", "arrive")):
        if row:
            return {"answer": f"{row['name']} is {row['river_km']} km down the river; water would arrive "
                              f"{row['eta_min']}-{row['eta_max']} minutes after an outburst. {row['action']}",
                    "evidence": ["flowpath", "eta"]}
        lines = "; ".join(f"{r['name']} {r['eta_min']}-{r['eta_max']} min" for r in eta)
        return {"answer": f"Arrival after an outburst: {lines}.", "evidence": ["flowpath", "eta"]}
    if any(w in ql for w in ("grow", "bigger", "larger", "expand", "change", "trend")):
        return {"answer": f"Yes. {lake['lake']['name']} grew from {g['from_km2']:.2f} km² ({g['from']}) to "
                          f"{g['to_km2']:.2f} km² ({g['to']}), +{g['pct']}% in {g['years']} years "
                          f"(trend {g['trend_km2_per_year']:+.3f} km² a year).", "evidence": ["series"]}
    if any(w in ql for w in ("area", "big", "size", "large", "how much water")):
        last = s[-1]
        return {"answer": f"{last['area_km2']:.2f} km² on {last['date']} (Sentinel-2, "
                          f"{last['clear_over_lake']:.0%} of the lake cloud-free). Before the 2023 burst: "
                          f"{pre[-1]['area_km2']:.2f} km² on {pre[-1]['date']}.", "evidence": ["series"]}
    if any(w in ql for w in ("who", "which", "places", "villages", "downstream", "risk")):
        names = ", ".join(f"{r['name']} ({r['river_km']} km)" for r in eta)
        return {"answer": f"On the flood path, nearest first: {names}.", "evidence": ["flowpath"]}
    vlm = ask_vlm(q, s[-1])
    if vlm:
        return vlm
    return {"answer": "I can answer about the lake's area, growth, whether it drained, and arrival times for "
                      "places downstream.", "evidence": []}


def ask_vlm(q, scene):
    """Forward an image question to the vision-language model service, if one is configured."""
    url = os.environ.get("VLM_URL")
    if not url:
        return None
    img = ROOT / scene["image"]
    payload = {"query": q, "files": [{"name": img.name, "b64": base64.b64encode(img.read_bytes()).decode()}]}
    try:
        r = requests.post(url.rstrip("/") + "/answer", json=payload, timeout=60)
        r.raise_for_status()
        out = r.json().get("output", {})
        return {"answer": out.get("text") or "No answer.", "evidence": ["vision-language model", scene["date"]]}
    except (requests.RequestException, ValueError) as e:
        return {"answer": f"The vision-language model is unreachable ({type(e).__name__}).", "evidence": []}
