"""Capture real responses from the live memory agent into frontend/public/recorded-memory.json. The deployed site has no
Hindsight server behind it, so its Memory tab replays this file, clearly labelled as a recorded run."""
import datetime as dt
import json
import sys
from pathlib import Path

import requests

B = "http://localhost:8000/api"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "recorded-memory.json"
st = requests.get(B + "/memory/status", timeout=30).json()
if not st.get("ok"):
    sys.exit("Hindsight is not reachable; nothing recorded")
data = {"captured": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "model": "qwen3:8b on an RTX 4060 (Ollama), memory in Hindsight " + str(st.get("version")),
        "triage": {}, "briefing": None}
for src in ("gauge", "station", "manual"):
    for radar in ("calm", "drained"):
        for mem in (True, False):
            r = requests.post(B + "/memory/triage", json={"source": src, "radar": radar, "use_memory": mem}, timeout=120)
            r.raise_for_status()
            data["triage"][f"{src}|{radar}|{int(mem)}"] = r.json()
            print(src, radar, mem, r.json()["decision"], flush=True)
data["briefing"] = requests.post(B + "/memory/briefing", timeout=120).json()
OUT.write_text(json.dumps(data, ensure_ascii=False))
print("wrote", OUT, OUT.stat().st_size, "bytes")
