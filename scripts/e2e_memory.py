"""End-to-end check of the memory agent through the real HTTP API (needs API on :8000, Hindsight on :8888, seeded bank)."""
import sys
import time

import requests

B = "http://localhost:8000/api"
for _ in range(40):
    try:
        if requests.get(B + "/alerts", timeout=2).ok:
            break
    except requests.RequestException:
        time.sleep(1)
else:
    sys.exit("API not reachable on :8000")

want = {("gauge", "calm"): "HOLD_AND_VERIFY", ("gauge", "drained"): "SEND_ALL_NOW", ("station", "calm"): "STANDBY_AND_VERIFY",
        ("manual", "calm"): "SEND_ALL_NOW", ("station", "drained"): "SEND_ALL_NOW"}
bad = 0
for (src, radar), exp in want.items():
    t = time.time()
    r = requests.post(B + "/memory/triage", json={"source": src, "radar": radar, "use_memory": True}, timeout=150)
    j = r.json()
    ok = r.status_code == 200 and j.get("decision") == exp
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'} [{time.time() - t:4.1f}s] {src:8}{radar:8} -> {j.get('decision', j.get('detail'))} (want {exp}) false_alarms={j.get('false_alarms')}")
    for l in j.get("lessons", []):
        print("       -", l["text"])
    if j.get("note"):
        print("       note:", j["note"])
off = requests.post(B + "/memory/triage", json={"source": "gauge", "radar": "calm", "use_memory": False}, timeout=30).json()
ok = off.get("decision") == "SEND_ALL_NOW"
bad += not ok
print(f"{'PASS' if ok else 'FAIL'} memory-off gauge/calm -> {off.get('decision')}")
sys.exit(1 if bad else 0)
