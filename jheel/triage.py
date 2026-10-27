"""Trigger triage: what should the control room do when a trigger arrives?

Without memory the system does what the alert engine has always done: any trigger sends alerts to every place.
With Hindsight memory the agent first recalls what happened the last times this source fired. The decision rule is
deliberately simple and one-sided:
  * radar says the lake drained (>= 25% of open water gone)  -> SEND ALL NOW, whatever the memory says;
  * radar says stable and this source has false-alarmed >= 2 times before -> HOLD for at most HOLD_MINUTES, then alerts go
    out automatically (the nearest place has 78+ minutes, a satellite pass can be days old, so a hold must expire);
  * a radar pass older than RADAR_FRESH_HOURS says nothing about now: it is treated as no pass, never as "stable";
  * a second independent source that agrees (corroborated) -> SEND ALL NOW;
  * radar says stable and it false-alarmed once before -> STAND BY and verify;
  * otherwise -> SEND ALL (precaution).
So memory can make the agent more careful about an unconfirmed trigger and can never talk it out of a confirmed one."""
import json
import re

from . import alerts, memory, reason

DRAIN_ALARM = 0.25
HOLD_MINUTES = 10          # a hold is a short verification window, never an open-ended wait
RADAR_FRESH_HOURS = 12     # older than this, a radar pass cannot vouch for the lake right now
SOURCE_WORDS = {"gauge": ("gauge", "river"), "station": ("lake station", "station", "sensor"),
                "manual": ("control-room", "control room", "button")}
DECISIONS = {
    "SEND_ALL_NOW": "Send alerts to every place now",
    "STANDBY_AND_VERIFY": "Stand by: warn the dam crew only, verify on the next radar pass",
    "HOLD_AND_VERIFY": f"Hold the alerts for up to {HOLD_MINUTES} minutes: verify, then they go out automatically",
}


def _false_alarm_docs(mems, source):
    """Distinct stored events that are false alarms from this source, read from Hindsight's own metadata."""
    return {m["doc"] for m in mems if m.get("kind") == "false-alarm" and m.get("trigger") == source and m.get("doc")}


_STOP = {"the", "and", "for", "with", "that", "this", "from", "before", "after", "into", "than", "were", "was", "are", "has", "have",
         "until", "when", "then", "also", "not", "all", "any", "its", "their", "which", "while", "because", "during"}


def _supported_by(lesson, mem):
    """A lesson must be made of the memory's own words: at least 60% of its content words (the opening verb aside) must
    occur in the memory it cites. 'Send SMS to Singtam immediately: previous failure delayed critical alerts' cites a memory
    about an out-of-date phone number and shares almost nothing with it, so it is dropped."""
    words = [w for w in re.findall(r"[a-z]{3,}", lesson.lower())[1:] if w not in _STOP]
    if not words:
        return False
    hay = set(re.findall(r"[a-z]{3,}", mem["text"].lower()))
    return sum(1 for w in words if w in hay or any(h.startswith(w[:5]) for h in hay if len(w) >= 5)) / len(words) >= 0.6


def _numbers_grounded(lesson, mems):
    """Every number in a lesson must appear in the memories it was drawn from (their text or dates). A model that turns 137
    into 139 is caught here and the lesson is dropped, instead of being shown to an officer."""
    hay = " ".join(m["text"] + " " + (m.get("when") or "") for m in mems)
    return all(re.search(r"(?<!\d)" + n + r"(?!\d)", hay) for n in re.findall(r"\d+", lesson))


HISTORY_KINDS = {"record", "radar-check"}
LESSON_QUERY = {
    "SEND_ALL_NOW": "Drills and past events: how long it takes to alert places and open dam gates, and what failed in delivering alerts.",
    "STANDBY_AND_VERIFY": "Past false alarms from this trigger source: the cause and what to check first, and how long dam gates take to open.",
    "HOLD_AND_VERIFY": "Past false alarms from this trigger source: the cause, what radar showed, and what to check before alerting anyone.",
}
LESSON_BRIEF = {
    "SEND_ALL_NOW": "The drain is confirmed or the trigger is being treated as real: give EXECUTION lessons (timings, failures to avoid). Do NOT suggest more verification.",
    "STANDBY_AND_VERIFY": "The officer is standing by to verify: give lessons about what to check and what is already known to be slow or fragile.",
    "HOLD_AND_VERIFY": "The officer is holding the alerts to verify: give lessons about what to check first, drawn from past false alarms.",
}


def _verbatim(mem, k):
    """A lesson in the memory's own words: its first two sentences, after the label, with the date it happened."""
    body = mem["text"].split(":", 1)[-1].strip()
    text = " ".join(re.split(r"(?<=[.!?])\s+", body)[:2]).strip()
    if not 12 <= len(text) <= 260:
        return None
    return {"text": text[0].upper() + text[1:], "memory": k, "from": mem["text"][:160], "when": mem.get("when"), "verbatim": True}


def _lessons(source, lake_name, decision_key):
    """Lessons for THIS decision, shown word for word. A second, targeted recall feeds the model, but the model only PICKS
    which memories matter; what the officer reads is the memory's own sentences, so a paraphrase can never turn 'repeat the
    drill by 5 November' into 'the drill was repeated'. It counts nothing: the false-alarm tally comes from Hindsight metadata."""
    # Lessons are operational: they come from drills, false alarms and field notes. The 2023 record and its radar replay are
    # history. When the answer is to send, false-alarm stories argue for holding back, so they are not offered as lessons.
    pool = [m for m in memory.originals(memory.recall(LESSON_QUERY[decision_key], n=12, budget="low"))
            if m.get("kind") not in HISTORY_KINDS | ({"false-alarm"} if decision_key == "SEND_ALL_NOW" else set())]
    mems = pool[:6]
    if not mems:
        return [], 0
    block = chr(10).join(f"[{i}] {m['text']}" for i, m in enumerate(mems))
    system = (
        "You are the memory of a state disaster control room. From the numbered MEMORIES pick the (at most 3) that matter most for the "
        "officer right now. " + LESSON_BRIEF[decision_key] + " Time-critical ones (minutes, seconds, deadlines) first. Pick each "
        'memory at most once. Return JSON only: {"pick": [<memory numbers>]}.')
    user = f"Trigger: {source} on {lake_name}.{chr(10)}MEMORIES:{chr(10)}{block}"
    ms = 0
    picks = []
    try:
        text, ms = reason.chat(system, user, json_mode=True, max_tokens=80)
        picks = [int(i) for i in json.loads(text).get("pick", []) if str(i).isdigit() or isinstance(i, int)]
    except Exception:                              # model down or malformed: the verbatim lessons do not need it
        picks = []
    order = [k for k in dict.fromkeys(picks) if 0 <= k < len(mems)]
    if not order:                                  # no usable pick: time-critical memories first
        order = sorted(range(len(mems)), key=lambda i: not re.search(r"minute|second", mems[i]["text"]))
    out = [x for x in (_verbatim(mems[k], k) for k in order) if x]
    return out[:3], ms


def triage(source, radar_loss, lake, use_memory=True, radar_age_hours=None, corroborated=False):
    if source not in alerts.SOURCES or source == "drain_check":
        raise ValueError(f"unknown trigger source {source!r}")
    name = lake["lake"]["name"]
    stale = radar_loss is not None and radar_age_hours is not None and radar_age_hours > RADAR_FRESH_HOURS
    if stale and radar_loss < DRAIN_ALARM:
        radar_loss = None            # an old "calm" pass is not evidence about the lake now
    radar = (f"Radar: {radar_loss:.0%} of open water gone. " + ("DRAINED." if radar_loss >= DRAIN_ALARM else "Stable.")
             if radar_loss is not None else "Radar: no recent pass to compare.")
    plain = {"decision": "SEND_ALL_NOW", "label": DECISIONS["SEND_ALL_NOW"],
             "why": f"A {alerts.SOURCES[source].lower()} fired. The system has no history, so it treats every trigger the same: alert all {len(lake['eta'])} places."}
    if not use_memory:
        return {"source": source, "radar": radar, "memory": False, **plain}

    out = {"source": source, "radar": radar, "memory": True, "without_memory": plain}
    confirmed = (radar_loss is not None and radar_loss >= DRAIN_ALARM) or corroborated
    q = (f"Past triggers from the {alerts.SOURCES[source].lower()} at {name}: were they false alarms or real, what did radar show, "
         f"and what did we learn about alerting places and opening dam gates?")
    mems = memory.recall(q, n=8)
    seen = {m["text"] for m in mems}
    for m in memory.recall(f"false alarm {alerts.SOURCES[source].lower()}", n=8, budget="low"):   # make sure none are missed
        if m["text"] not in seen:
            mems.append(m)
    out["recalled"] = mems
    docs = _false_alarm_docs(mems, source)
    fa = len(docs)
    note = None
    out["false_alarms"] = fa
    out["false_alarm_ids"] = [i for i, m in enumerate(mems) if m.get("doc") in docs]
    if confirmed:
        dec = "SEND_ALL_NOW"
        what = (f"Radar confirms the lake has drained ({radar_loss:.0%} of open water gone)" if radar_loss is not None and radar_loss >= DRAIN_ALARM
                else "A second independent source agrees with the trigger")
        why = (f"{what}. Memory is never allowed to hold back a confirmed event, so alerts go to all {len(lake['eta'])} places now.")
    elif fa >= 2 and radar_loss is not None:
        dec = "HOLD_AND_VERIFY"
        first = min(e["eta_min"] for e in lake["eta"])
        why = (f"This source has false-alarmed {fa} times before in the control room's memory, and radar now shows the lake "
               f"stable ({radar_loss:.0%} change). Verify with a second source before alerting anyone. The hold lasts at most "
               f"{HOLD_MINUTES} minutes: the nearest place has {first} minutes, so the hold expires on its own: at the deadline "
               f"the recommendation becomes SEND ALL NOW (sent automatically where the authority enables auto-escalation), and at once if a second source agrees.")
        out["hold_minutes"] = HOLD_MINUTES
    elif fa >= 1:
        dec = "STANDBY_AND_VERIFY"
        why = (f"This source has false-alarmed {fa} time{'s' if fa > 1 else ''} before and radar cannot confirm a drain. "
               f"Warn the dam crew to stand by and verify.")
    else:
        dec = "SEND_ALL_NOW"
        why = "Nothing in memory says this source is unreliable, so a trigger is treated as real as a precaution."
    out.update(decision=dec, label=DECISIONS[dec], why=why)
    try:
        out["lessons"], out["reader_ms"] = _lessons(source, name, dec)
    except Exception as e:                                   # GPU server down or malformed JSON: the decision stands
        out["lessons"], out["reader_ms"] = [], 0
        out["note"] = f"GPU reader unavailable ({type(e).__name__}); lessons skipped, decision and count unaffected"
    return out
