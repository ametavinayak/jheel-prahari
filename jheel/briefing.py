"""Shift handover briefing, built from what Hindsight recalls. Several targeted recalls (events, trusted sources, real
timings, failures, open items) feed one grounded write-up; each bullet must cite its memories and every number in it must
appear in them, so the briefing cannot contain a figure the control room never recorded. (Hindsight's agentic `reflect`
is kept in memory.reflect for a machine with a GPU to itself; on a shared one it takes minutes.)"""
import json

from . import memory, reason
from .triage import _numbers_grounded

QUERIES = [
    "What real events and radar checks have been recorded for South Lhonak, with dates?",
    "Which trigger sources gave false alarms, why, and what did radar show?",
    "How long do real actions take: alerting places, opening dam gates?",
    "What failed in drills or field checks and was fixed or is still open?",
]


def build():
    mems, seen = [], set()
    for q in QUERIES:
        for m in memory.recall(q, n=6, budget="low"):
            if m["text"] not in seen:
                seen.add(m["text"])
                mems.append(m)
    mems.sort(key=lambda m: m.get("when") or "")
    originals = memory.originals(mems)
    if not mems:
        return {"bullets": [], "memories": 0, "note": "Memory is empty: nothing to brief on yet."}
    tally = {}
    for m in mems:
        if m.get("kind") == "false-alarm" and m.get("trigger") and m.get("doc"):
            tally.setdefault(m["trigger"], {})[m["doc"]] = (m.get("when") or "")[:10]
    names = {"gauge": "River gauge", "station": "Lake station", "manual": "Control-room button"}
    counted = [f"{names.get(k, k)}: {len(v)} false alarm{'s' if len(v) != 1 else ''} (" + ", ".join(sorted(v.values())) + ")"
               for k, v in sorted(tally.items())]
    facts = ("COUNTED FROM THE RECORDS (use these exactly under 'Which sources to trust'): " + "; ".join(counted)) if counted else ""
    block = facts + chr(10) + chr(10).join(f"[{i}] {(m.get('when') or '')[:10]} ({m.get('kind') or 'note'}) {m['text']}" for i, m in enumerate(originals))
    system = (
        "You write the shift-handover briefing for a state disaster control room that watches glacial lakes. Use ONLY the "
        "numbered MEMORIES. Return JSON: "
        '{"bullets": [{"heading": "...", "text": "...", "memories": [<numbers>]}]} with exactly these headings in order: '
        '"What happened", "Which sources to trust", "How long real actions take", "What failed and was fixed", "Open items". '
        "A memory whose kind is open-item belongs under Open items (say who owns it and when it is due). Each text: 1 to 3 plain sentences, with the exact dates and numbers from the memories. If the memories say nothing "
        'for a heading, write "Nothing recorded." Never invent a fact.')
    text, ms = reason.chat(system, "MEMORIES:" + chr(10) + block, json_mode=True, max_tokens=700)
    bullets = []
    for b in json.loads(text).get("bullets", []):
        try:
            h, t = str(b["heading"]).strip(), str(b["text"]).strip()
            ids = [int(i) for i in b.get("memories", []) if 0 <= int(i) < len(originals)]
        except (KeyError, TypeError, ValueError):
            continue
        if h and t and _numbers_grounded(t, originals):
            bullets.append({"heading": h, "text": t, "memories": ids})
    if counted:       # the sources bullet is built from the counted records, never from the model's wording
        trust = "; ".join(counted) + ". A radar drain (25% or more of the open water gone) overrides all of them."
        hit = [b for b in bullets if b["heading"] == "Which sources to trust"]
        if hit:
            hit[0]["text"] = trust
        else:
            bullets.insert(min(1, len(bullets)), {"heading": "Which sources to trust", "text": trust, "memories": []})
    return {"bullets": bullets, "memories": len(originals), "ms": ms}
