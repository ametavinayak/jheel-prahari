"""Alert engine: a trigger becomes one message per place on that lake's flood path. Lookups only."""
import datetime as dt
import json
import os
import threading
import uuid
from pathlib import Path

import requests

LOG = Path(__file__).resolve().parent.parent / "data" / "alerts.jsonl"
SOURCES = {"drain_check": "Radar drain check", "gauge": "River gauge spike", "station": "Lake station alarm",
           "manual": "Control-room button"}
_lock = threading.Lock()
_events = []


def ist(t):
    return (t + dt.timedelta(hours=5, minutes=30)).strftime("%H:%M")


def message(lake_name, row, now):
    lo, hi = now + dt.timedelta(minutes=row["eta_min"]), now + dt.timedelta(minutes=row["eta_max"])
    return (f"JHEEL PRAHARI ALERT - {lake_name} lake outburst. {row['name']}: flood water expected in "
            f"{row['eta_min']}-{row['eta_max']} min (between {ist(lo)} and {ist(hi)} IST). {row['action']}")


def deliver(msg, row):
    """Real delivery when ALERT_WEBHOOK_URL is set (an SMS gateway or siren controller); otherwise simulated
    and marked so in the record."""
    url = os.environ.get("ALERT_WEBHOOK_URL")
    if not url:
        return {"channel": "sms", "status": "simulated"}
    try:
        r = requests.post(url, json={"to": row["id"], "text": msg}, timeout=10)
        return {"channel": "webhook", "status": "sent" if r.ok else f"failed {r.status_code}"}
    except requests.RequestException as e:
        return {"channel": "webhook", "status": f"failed {type(e).__name__}"}


def fire(lake, eta_rows, source, detail=None, now=None):
    if source not in SOURCES:
        raise ValueError(f"unknown trigger source {source!r}")
    if not eta_rows:
        raise ValueError("no places on this lake's flood path")
    now = now or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    sends = []
    for row in eta_rows:
        msg = message(lake["name"], row, now)
        sends.append({"place": row["id"], "name": row["name"], "kind": row["kind"], "river_km": row["river_km"],
                      "eta_min": row["eta_min"], "eta_max": row["eta_max"], "text": msg, **deliver(msg, row)})
    ev = {"id": uuid.uuid4().hex[:10], "lake": lake["id"], "source": source, "source_label": SOURCES[source],
          "detail": detail, "at_utc": now.isoformat(timespec="seconds") + "Z", "messages": sends}
    with _lock:
        _events.insert(0, ev)
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
    return ev


def recent(n=20):
    with _lock:
        return list(_events[:n])


def reset():
    with _lock:
        _events.clear()
