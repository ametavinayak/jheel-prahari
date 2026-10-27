"""Alert engine: a trigger becomes one message per place on that lake's flood path. Lookups only."""
import datetime as dt
import json
import os
import threading
import uuid
from pathlib import Path

import requests

from . import memory

# JHEEL_STATE_DIR moves the log off a read-only deploy (serverless allows writes only under /tmp).
LOG = Path(os.environ.get("JHEEL_STATE_DIR") or Path(__file__).resolve().parent.parent / "data") / "alerts.jsonl"
SOURCES = {"drain_check": "Radar drain check", "gauge": "River gauge spike", "station": "Lake station alarm",
           "manual": "Control-room button"}
_lock = threading.Lock()
_events = []


def ist(t):
    return (t + dt.timedelta(hours=5, minutes=30)).strftime("%H:%M")


LANGS = {"en": "English", "hi": "हिन्दी", "ne": "नेपाली"}
# The action sentences come from the ETA table in English; these are their Hindi and Nepali forms. An action with no
# entry here is sent in English rather than guessed. Have a native speaker review before any real send.
ACTIONS = {
    "Move everyone uphill, away from the river, now.": {
        "hi": "सभी लोग अभी नदी से दूर ऊँचाई की ओर जाएँ।",
        "ne": "सबै जना अहिले नै नदीबाट टाढा, माथि उकालितिर जानुहोस्।"},
    "Open spillway gates, evacuate the powerhouse and dam crew.": {
        "hi": "स्पिलवे गेट खोलें, पावरहाउस और बाँध के कर्मचारियों को निकालें।",
        "ne": "स्पिलवे गेट खोल्नुहोस्, पावरहाउस र बाँधका कर्मचारीलाई बाहिर निकाल्नुहोस्।"},
    "Clear the riverbank and the bridge approach; move uphill.": {
        "hi": "नदी किनारे और पुल के पास का इलाका खाली करें; ऊँचाई की ओर जाएँ।",
        "ne": "नदी किनार र पुलको छेउ खाली गर्नुहोस्; माथि उकालितिर जानुहोस्।"},
    "Close the Teesta bridge, clear riverside homes and the bazaar.": {
        "hi": "तीस्ता पुल बंद करें, नदी किनारे के घरों और बाज़ार को खाली कराएँ।",
        "ne": "तिस्ता पुल बन्द गर्नुहोस्, नदी किनारका घर र बजार खाली गराउनुहोस्।"},
    "Close NH10 along the river, clear riverside settlements.": {
        "hi": "नदी के किनारे NH10 बंद करें, नदी किनारे की बस्तियाँ खाली कराएँ।",
        "ne": "नदी किनारमा NH10 बन्द गर्नुहोस्, नदी किनारका बस्ती खाली गराउनुहोस्।"},
}


def message(lake_name, row, now, lang="en"):
    lo, hi = now + dt.timedelta(minutes=row["eta_min"]), now + dt.timedelta(minutes=row["eta_max"])
    a, b, t1, t2 = row["eta_min"], row["eta_max"], ist(lo), ist(hi)
    action = ACTIONS.get(row["action"], {}).get(lang, row["action"])
    if lang == "hi":
        return (f"झील प्रहरी चेतावनी - {lake_name} झील फट गई है। {row['name']}: बाढ़ का पानी {a}-{b} मिनट में "
                f"पहुँचेगा ({t1} से {t2} IST के बीच)। {action}")
    if lang == "ne":
        return (f"झील प्रहरी चेतावनी - {lake_name} ताल फुटेको छ। {row['name']}: बाढीको पानी {a}-{b} मिनेटमा "
                f"आइपुग्नेछ ({t1} देखि {t2} IST बीच)। {action}")
    return (f"JHEEL PRAHARI ALERT - {lake_name} lake outburst. {row['name']}: flood water expected in "
            f"{a}-{b} min (between {t1} and {t2} IST). {action}")


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
        texts = {lg: message(lake["name"], row, now, lg) for lg in LANGS}
        msg = texts["en"]
        sends.append({"place": row["id"], "name": row["name"], "kind": row["kind"], "river_km": row["river_km"],
                      "eta_min": row["eta_min"], "eta_max": row["eta_max"], "text": msg, "texts": texts,
                      **deliver(msg, row)})
    ev = {"id": uuid.uuid4().hex[:10], "lake": lake["id"], "source": source, "source_label": SOURCES[source],
          "detail": detail, "at_utc": now.isoformat(timespec="seconds") + "Z", "messages": sends}
    if os.environ.get("JHEEL_MEMORY") == "1":
        names = ", ".join(f"{m['name']} {m['eta_min']}-{m['eta_max']} min" for m in sends)
        memory.retain_background(
            f"ALERT SENT. {SOURCES[source]} triggered an alert for {lake['name']}"
            + (f" ({detail})" if detail else "") + f". Messages went to {len(sends)} places: {names}.",
            "alert", now, {"lake": lake["id"], "source": source})
    with _lock:
        _events.insert(0, ev)
        try:                       # an unwritable log (read-only deploy) must never stop an alarm: the event stays in memory
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev) + "\n")
        except OSError:
            ev["logged"] = False
    return ev


def recent(n=20):
    with _lock:
        return list(_events[:n])


def reset():
    with _lock:
        _events.clear()
