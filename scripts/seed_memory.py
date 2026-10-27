"""Seed the control room's memory. Two kinds of entries, labelled in the text itself so nobody can mistake them:
  RECORD   - what is documented about the real 2023 South Lhonak event and what this system measured on it
  EXERCISE - a synthetic control-room log for the demonstration: drills and field checks that show what the memory
             is for. These are NOT real incidents.
Run:  .venv/Scripts/python scripts/seed_memory.py     (needs the Hindsight server and its LLM; ~15 s per entry)"""
import datetime as dt
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jheel import memory  # noqa: E402

D = dt.datetime
ENTRIES = [
    ("RECORD", D(2023, 10, 3, 22, 0), "record",
     "RECORD. On 3 October 2023, at night, South Lhonak lake in North Sikkim burst. About 50 million cubic metres of water went "
     "down the Teesta. The Teesta-III dam at Chungthang (1,200 MW) was destroyed and 13 bridges were lost. The flood reached "
     "Chungthang 107 to 137 minutes after the landslide. Nobody downstream was warned."),
    ("RECORD", D(2023, 10, 10, 0, 0), "radar-check",
     "RECORD. Radar replay of South Lhonak: Sentinel-1 on 28 September 2023 showed 1.63 square kilometres of open water inside "
     "the lake outline; the pass on 10 October 2023 showed 0.78. A 52 percent loss, so the radar drain check says DRAINED. "
     "On two calm passes (16 to 28 September 2023) the same check showed minus 2 percent and gave no alarm."),
    ("EXERCISE", D(2026, 8, 14, 3, 20), "false-alarm",
     "EXERCISE LOG, synthetic. 14 August 2026: the river gauge trigger fired for South Lhonak during a cloudburst. "
     "The next Sentinel-1 radar pass showed minus 2 percent change in open water, so the lake had not drained. It was a FALSE "
     "ALARM caused by a rain surge at the gauge. The control room held the alerts and nobody was evacuated."),
    ("EXERCISE", D(2026, 9, 2, 2, 45), "false-alarm",
     "EXERCISE LOG, synthetic. 2 September 2026: the river gauge trigger fired again for South Lhonak in heavy monsoon rain. "
     "Radar showed minus 1 percent change, no drain. FALSE ALARM again, second time for the river gauge. Officer note: the "
     "gauge reads high whenever it rains hard upstream; always check the radar pass before alerting villages."),
    ("EXERCISE", D(2026, 9, 20, 11, 10), "false-alarm",
     "EXERCISE LOG, synthetic. 20 September 2026: the lake station alarm at South Lhonak fired. A technician found a low battery "
     "fault; no change in the lake. FALSE ALARM from the lake station. Battery replaced the same day."),
    ("EXERCISE", D(2026, 10, 5, 10, 0), "drill",
     "EXERCISE LOG, synthetic. 5 October 2026 SMS drill: Lachen received its alert in 9 seconds and Dikchu in 11 seconds. The "
     "Singtam message FAILED because the control room's phone number for Singtam was out of date. Number corrected the same day."),
    ("EXERCISE", D(2026, 10, 12, 15, 30), "drill",
     "EXERCISE LOG, synthetic. 12 October 2026 walk-through with the Teesta-III dam staff: opening the spillway gates fully takes "
     "18 minutes. So the Chungthang alert must reach the dam at least 25 minutes before the flood arrives."),
    ("EXERCISE", D(2026, 10, 20, 9, 0), "field-check",
     "EXERCISE LOG, synthetic. 20 October 2026 field verification: the lake flagged HIGH by the area screening was visited by a "
     "field team. They confirmed it is a glacier-fed moraine lake that grew since 2019. It is now on the weekly watch list."),
    ("EXERCISE", D(2026, 10, 22, 12, 0), "open-item",
     "EXERCISE LOG, synthetic. OPEN ITEM, 22 October 2026: repeat the Singtam SMS drill after the phone number was corrected. "
     "Owner: the district control room. Due 5 November 2026. Until then Singtam alerts must also be phoned through."),
]

# which trigger source each false alarm came from, stored as metadata so the tally is read, not guessed
TRIGGER = {2: {"trigger": "gauge"}, 3: {"trigger": "gauge"}, 4: {"trigger": "station"}}


def main():
    if "--reset" in sys.argv:           # start from a clean bank: drops everything, including notes taught since
        memory._on_pool(lambda: memory._cli().delete_bank(bank_id=memory.BANK))
        print("bank reset", flush=True)
    memory.ensure_bank()
    for i, (kind, when, ctx, text) in enumerate(ENTRIES):
        t = time.time()
        memory.retain(text, ctx, when, {"source": kind.lower(), **TRIGGER.get(i, {})}, doc_id=f"seed-{i + 1}")
        print(f"{kind:8} {when:%Y-%m-%d} stored in {time.time() - t:.0f}s: {text[:70]}...", flush=True)
    print("seeded", len(ENTRIES))


main()
