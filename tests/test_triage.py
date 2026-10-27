"""Trigger triage: the decision rule is deterministic and one-sided, and lessons are the memory's own words."""
import json

from jheel import memory, reason, triage

LAKE = {"lake": {"name": "South Lhonak"}, "eta": [{"name": f"p{i}", "eta_min": 78 + i} for i in range(5)]}


def mem(text, kind=None, doc=None, trigger=None, when=None):
    return {"text": text, "type": "world", "kind": kind, "doc": doc, "trigger": trigger, "when": when}


def setup(monkeypatch, mems, picks=None):
    monkeypatch.setattr(memory, "recall", lambda q, n=8, budget="mid": list(mems))
    monkeypatch.setattr(reason, "chat", lambda *a, **k: (json.dumps({"pick": picks or []}), 1))


def test_two_false_alarms_and_calm_radar_hold(monkeypatch):
    setup(monkeypatch, [mem("fa1", "false-alarm", "d1", "gauge"), mem("fa1b", "false-alarm", "d1", "gauge"),
                        mem("fa2", "false-alarm", "d2", "gauge")])
    r = triage.triage("gauge", -0.02, LAKE)
    assert r["decision"] == "HOLD_AND_VERIFY" and r["false_alarms"] == 2      # two facts of one event count once


def test_memory_can_never_hold_back_a_confirmed_drain(monkeypatch):
    setup(monkeypatch, [mem("x", "false-alarm", f"d{i}", "gauge") for i in range(9)])
    assert triage.triage("gauge", 0.52, LAKE)["decision"] == "SEND_ALL_NOW"


def test_false_alarms_are_counted_per_source(monkeypatch):
    setup(monkeypatch, [mem("x", "false-alarm", "d1", "gauge"), mem("y", "false-alarm", "d2", "gauge")])
    assert triage.triage("station", -0.02, LAKE)["decision"] == "SEND_ALL_NOW"
    assert triage.triage("gauge", -0.02, LAKE)["decision"] == "HOLD_AND_VERIFY"


def test_no_radar_pass_never_holds(monkeypatch):
    setup(monkeypatch, [mem("x", "false-alarm", "d1", "gauge"), mem("y", "false-alarm", "d2", "gauge")])
    assert triage.triage("gauge", None, LAKE)["decision"] == "STANDBY_AND_VERIFY"


def test_a_hold_is_a_short_window_that_ends_in_alerts(monkeypatch):
    setup(monkeypatch, [mem("x", "false-alarm", "d1", "gauge"), mem("y", "false-alarm", "d2", "gauge")])
    r = triage.triage("gauge", -0.02, LAKE)
    assert r["hold_minutes"] == triage.HOLD_MINUTES == 10
    assert "automatically" in r["why"] and "78 minutes" in r["why"]           # the nearest place sets the deadline


def test_an_old_calm_radar_pass_cannot_vouch_for_the_lake_now(monkeypatch):
    setup(monkeypatch, [mem("x", "false-alarm", "d1", "gauge"), mem("y", "false-alarm", "d2", "gauge")])
    r = triage.triage("gauge", -0.02, LAKE, radar_age_hours=96)               # a four-day-old pass
    assert r["decision"] == "STANDBY_AND_VERIFY" and "no recent pass" in r["radar"]
    assert triage.triage("gauge", -0.02, LAKE, radar_age_hours=3)["decision"] == "HOLD_AND_VERIFY"


def test_an_old_pass_that_shows_a_drain_still_alerts(monkeypatch):
    setup(monkeypatch, [mem("x", "false-alarm", f"d{i}", "gauge") for i in range(4)])
    assert triage.triage("gauge", 0.52, LAKE, radar_age_hours=96)["decision"] == "SEND_ALL_NOW"


def test_a_second_source_that_agrees_ends_the_hold(monkeypatch):
    setup(monkeypatch, [mem("x", "false-alarm", "d1", "gauge"), mem("y", "false-alarm", "d2", "gauge")])
    r = triage.triage("gauge", -0.02, LAKE, corroborated=True)
    assert r["decision"] == "SEND_ALL_NOW" and "second independent source" in r["why"]


def test_without_memory_every_trigger_alerts_everyone(monkeypatch):
    setup(monkeypatch, [])
    assert triage.triage("gauge", -0.02, LAKE, use_memory=False)["decision"] == "SEND_ALL_NOW"


GATES = "EXERCISE LOG, synthetic. 12 October 2026 walk-through: opening the spillway gates fully takes 18 minutes. So the Chungthang alert must reach the dam at least 25 minutes before the flood arrives."
SMS = "EXERCISE LOG, synthetic. OPEN ITEM, 22 October 2026: repeat the Singtam SMS drill after the phone number was corrected. Due 5 November 2026."


def test_lessons_are_the_memorys_own_sentences_not_a_paraphrase(monkeypatch):
    setup(monkeypatch, [mem(SMS, kind="open-item", doc="o1"), mem(GATES, kind="drill", doc="d1")], picks=[0, 1])
    lessons = triage.triage("manual", -0.02, LAKE)["lessons"]
    assert lessons[0]["text"].startswith("Repeat the Singtam SMS drill after the phone number was corrected.")
    assert "repeated" not in lessons[0]["text"] and lessons[0]["verbatim"] and lessons[1]["text"].startswith("Opening the spillway gates fully takes 18 minutes.")


def test_the_historical_record_and_false_alarms_are_not_offered_as_lessons_when_sending(monkeypatch):
    rec = mem("RECORD. The flood reached Chungthang 107 to 137 minutes after the landslide.", kind="record", doc="r1")
    fa = mem("EXERCISE LOG. The gauge false-alarmed in rain.", kind="false-alarm", doc="f1", trigger="gauge")
    setup(monkeypatch, [rec, fa, mem(GATES, kind="drill", doc="d1")], picks=[0, 1, 2])
    texts = [x["text"] for x in triage.triage("manual", -0.02, LAKE)["lessons"]]
    assert len(texts) == 1 and texts[0].startswith("Opening the spillway gates")


def test_a_bad_pick_is_ignored_and_lessons_survive_a_model_outage(monkeypatch):
    setup(monkeypatch, [mem(GATES, kind="drill", doc="d1")], picks=[7, -1])
    assert len(triage.triage("manual", -0.02, LAKE)["lessons"]) == 1                   # nothing valid picked: time-critical first

    def boom(*a, **k):
        raise RuntimeError("no GPU")
    monkeypatch.setattr(reason, "chat", boom)
    r = triage.triage("manual", -0.02, LAKE)
    assert r["decision"] == "SEND_ALL_NOW" and len(r["lessons"]) == 1


def test_one_logged_note_is_one_document_however_many_facts_it_yields(monkeypatch):
    import app as appmod
    seen = []
    monkeypatch.setattr(memory, "retain", lambda text, kind, when=None, meta=None, wait=True, doc_id=None: seen.append(doc_id))
    assert appmod.memory_log(appmod.Note(text="gauge rain surge, false alarm", outcome="false-alarm", trigger="gauge")) == {"stored": True}
    assert appmod.memory_log(appmod.Note(text="another note")) == {"stored": True}
    assert all(d and d.startswith("note-") for d in seen) and seen[0] != seen[1]
