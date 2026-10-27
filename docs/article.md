# Hindsight taught my flood-warning agent which sensor cries wolf

The river gauge fired again at 02:10. It had been raining all night upstream, and I knew what would happen next: the control room would alert every village on the flood path, nothing would happen, and the next real alarm would be a little less believed.

That is the problem I could not solve with better satellites. So I gave the agent a memory.

## What the system does

I build early warning for glacial lake outburst floods (GLOFs). In October 2023 South Lhonak lake in Sikkim burst at night, destroyed the Teesta-III dam and took 55 lives. The lake was on the high-risk list. Nobody downstream was warned.

The first half of the project, Jheel Prahari ("lake watchman"), does the physics:

- **See.** Sentinel-2 imagery gives the lake outline and area (1.27 km² in 2016, 1.65 km² in August 2023). Sentinel-1 radar checks whether the open water inside that outline has disappeared. Between 28 September and 10 October 2023 it fell from 1.63 to 0.78 km², a 52% loss, and a calm control pair gave minus 2%.
- **Count.** A 30 m Copernicus elevation model gives the flood path and an arrival range for each village, dam and bridge: Chungthang dam 107 to 137 minutes, calibrated on what really happened in 2023.
- **Alert.** One message per place, with its own window and action, in English, Hindi and Nepali. This path is a table lookup. There is no model in it on purpose.

That works. It also has a flaw nobody talks about: the first alarm is easy, the hundredth is the problem. The second half, Jheel Smriti ("lake memory"), is an agent built on [Hindsight](https://github.com/vectorize-io/hindsight) that remembers every alert, drill and field check and uses that history when a trigger arrives.

## One bank, with a mission

Hindsight keeps memories in banks. The control room gets one, with a mission and a deliberately sceptical disposition:

```python
MISSION = ("You are the long-term memory of a state disaster control room that watches glacial lakes. "
           "Remember every alert, drill, field check and officer note with its date... "
           "Track which trigger sources have given false alarms, how long real actions take, and what failed.")
DISPOSITION = {"skepticism": 4, "literalism": 4, "empathy": 2}
```

Every event goes in with the date it happened, not the date I typed it, plus metadata I will need later:

```python
client.retain(bank_id=BANK, content=text, context="false-alarm",
              timestamp=when, document_id="seed-3",
              metadata={"source": "exercise", "trigger": "gauge"})
```

Two choices here paid off. `timestamp` means recall can reason about order and recency. `context` and `metadata` mean I can count things later without asking a language model to count, which turned out to matter.

## The decision is not the model's opinion

When a trigger fires, the agent recalls the history for that source and a plain rule decides. I wrote the rule to be one-sided:

```python
if confirmed:                       # radar: 25% or more of the open water is gone
    dec = "SEND_ALL_NOW"            # memory can never hold this back
elif fa >= 2 and radar_loss is not None:
    dec = "HOLD_AND_VERIFY"
elif fa >= 1:
    dec = "STANDBY_AND_VERIFY"
else:
    dec = "SEND_ALL_NOW"
```

Memory can make the agent more careful about an unconfirmed trigger. It cannot argue it out of a confirmed disaster. There is a test for exactly that sentence.

A hold is also never open-ended. It lasts at most 10 minutes, because the nearest village on the flood path has about 78 minutes. When the window ends the recommendation becomes SEND ALL NOW, and a second independent source that agrees ends it at once. A radar pass older than 12 hours counts as no pass at all, never as "calm": satellites revisit every few days, so the fast alarm always comes from ground triggers.

The count `fa` comes from what Hindsight hands back, not from a model:

```python
def _false_alarm_docs(mems, source):
    return {m["doc"] for m in mems
            if m.get("kind") == "false-alarm" and m.get("trigger") == source and m.get("doc")}
```

Two facts extracted from the same logbook entry count once, because I count distinct documents.

## Before and after

Same trigger, same radar (calm, minus 2%).

- **Without memory:** send alerts to every place now. This is how the engine always behaved.
- **With Hindsight memory:** hold the alerts and verify first. This river gauge false-alarmed twice before, on 14 August and 2 September, and the radar shows the lake stable.

Then an officer logs one more false alarm, "River gauge fired at 02:10 after heavy rain, radar showed no change", chooses *false alarm* and *river gauge*, and presses a button. Fire the trigger again: three. No retraining, one more dated fact.

The history I seeded is a labelled synthetic exercise log, marked as such inside the memory itself, plus the real 2023 record. A real control room log does not exist yet, so I would rather say so than pretend.

## Lessons: I stopped letting the model write them

Counting is exact, but the useful part of a logbook is the sentences: "opening the spillway gates takes 18 minutes", "the Singtam phone number was out of date". A model on my own GPU (Qwen3 8B through Ollama) can read a targeted recall and write the lessons an officer should see. My first version did, with a citation requirement and a check that every number in a lesson appeared in the memories.

That caught the obvious failure: the model wrote that the dam window was "107 to 139 minutes" when the memory said 137. It did not catch the subtle one. A memory said "repeat the Singtam SMS drill after the phone number was corrected, due 5 November". The model's lesson said the drill "was repeated". Every word and number was in the source. The meaning was reversed.

So the model no longer writes anything an officer reads. It only picks:

```python
text, ms = reason.chat(system, user, json_mode=True, max_tokens=80)   # {"pick": [2, 0, 5]}
order = [k for k in dict.fromkeys(picks) if 0 <= k < len(mems)]
out = [x for x in (_verbatim(mems[k], k) for k in order) if x]       # the memory's own sentences
```

What the officer sees is the memory's own sentence with its date: "Opening the spillway gates fully takes 18 minutes. So the Chungthang alert must reach the dam at least 25 minutes before the flood arrives." It is less polished and always right. If the GPU is down the lessons still appear, time-critical ones first.

The same lesson applies to the plain-language answers I let the model give in Hindi and Nepali. It sees only the facts relevant to the question, each sentence must be backed by a quoted fact line, and unsupported sentences are removed. It once told me, in Hindi, that people "will survive" a flood. That sentence is no longer shown to anyone.

## The bug that only showed up in the real interface

The agent passed every test I wrote. Then I clicked through the console and the Memory tab said `RuntimeError: Timeout context manager should be used inside a task`. Two requests had arrived together, and the Hindsight Python client keeps one event loop that cannot be driven from different threads. The web server uses a thread per request.

The fix is boring and correct: every Hindsight call runs on one dedicated thread.

```python
_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="hindsight")

def _on_pool(fn, *a, **kw):
    return _pool.submit(fn, *a, **kw).result()
```

A related lesson came from the GPU. Hindsight's background work plus my own calls froze the single shared Ollama server, so Hindsight now runs with one language-model call at a time and no automatic consolidation.

## What I would tell another engineer

- **Store structure next to the story.** Free text is how people write, metadata is how you count. Keep both.
- **Let memory tighten, never loosen, a safety decision.** The asymmetric rule is what made the agent safe to demo to a disaster authority.
- **Do not let the model do arithmetic.** Count in code. And do not let it reword safety-relevant sentences either: it will keep every number and flip the meaning.
- **Pick, do not paraphrase.** If the source sentence is already the lesson, show the source.
- **Test through the real interface.** My bug lived in the gap between unit tests and a browser.

## Limits

I do not predict when a lake will burst, and nothing here claims to. Satellites pass every few days, so triggers between passes come from gauges and stations. The lake outline is a water-index rule, arrival times are ranges calibrated on one event, SMS sending is simulated, and the Hindi and Nepali alert texts need native review before they go anywhere near a real phone. The point of the memory is narrow and real: fewer false alarms, so the true one is believed.

If you want to read the code or try the pattern on your own sensors, start with [Hindsight on GitHub](https://github.com/vectorize-io/hindsight), the [Hindsight documentation](https://hindsight.vectorize.io/), and [Vectorize's overview of agent memory](https://vectorize.io/what-is-agent-memory).


---

Code: [github.com/ametavinayak/jheel-prahari](https://github.com/ametavinayak/jheel-prahari) · Live: [jheel-prahari.vercel.app](https://jheel-prahari.vercel.app) · Team Anivortex: Vinayak Ameta, Ankit Dubey, Chirag, Toshika Verma
