# Jheel Prahari

Early warning for glacial lake outburst floods (GLOFs). Team Anivortex · Colossal-A-Pitch, Avinya '26.

Satellites watch every high-risk glacial lake. When a lake grows, it moves up the risk list. When it drains, or any
other trigger arrives, every village, dam and bridge on its flood path gets its own countdown and action.

The prototype runs on **South Lhonak lake (North Sikkim)**, the lake that burst on 3 October 2023 and destroyed
the Teesta-III dam at Chungthang.

## What it does, on real data

| Part | What runs | Result on South Lhonak |
|---|---|---|
| Lake watch | Sentinel-2 L2A, clearest ice-free scene per year, lake outline from water indices | 1.27 km² (Oct 2016) → 1.65 km² (Aug 2023), +30%, ~0.05 km² a year |
| Drain check | Sentinel-1 RTC radar, last pass before vs first pass after, inside the lake outline | 28 Sep → 10 Oct 2023: 52% of open water gone → **DRAINED** |
| Control | Same check on two calm passes (16 → 28 Sep 2023) | −2%, no alarm |
| Live scan | Same check on the two latest passes, fetched when you click | 1 → 13 Oct 2026: 1% change, stable |
| Flood path | Copernicus DEM 30 m, D8 routing from the lake | 163 km down the Lhonak and Teesta valleys to Rangpo |
| Arrival times | River distance, calibrated on 2023 (Chungthang hit 107–137 min after the landslide) | Lachen 78–99 min, Chungthang 107–137, Dikchu 160–205, Singtam 203–260, Rangpo 218–279 |
| Alerts | One message per place on the path, with its time window and action | SMS simulated unless a gateway URL is set |

All imagery is public: ESA Copernicus Sentinel-1/2 and Copernicus DEM, read from Microsoft Planetary Computer.
No account is needed.

## Screening any area

Search a place in the console, or pan the map and press **Analyse view**. For a box of about 18 km, the backend:

1. Picks the clearest ice-free Sentinel-2 scene, plus one 5 to 8 years older.
2. Finds every lake and matches each one across the two dates.
3. Reads the Copernicus DEM for elevation and the slope of the valley below each lake.

A lake is flagged only if it is **glacier-fed** (snow or ice within 500 m, above 3,500 m), **at least 0.05 km²**, and
**measurably growing** (more than 5% and more than 0.02 km²). If the older scene was cloudy over a lake, its growth is
marked unknown rather than counted as a new lake. The score is growth 40 + glacier contact 20 + size 20 + valley
slope 20. It is a screening score of the kind used in published GLOF hazard rankings, not a probability.

Checked on real areas:

| Area | Result |
|---|---|
| South Lhonak, replayed as of 1 Oct 2023 (two days before it burst) | the only HIGH lake in the box: +27% since 2016, in contact with ice |
| Gurudongmar lake (1.09 km², glacial) | **stable**: +0.5% since 2019; nearby lakes that did grow (e.g. +28%, +0.26 km²) are the ones flagged |
| Tsomgo lake near Gangtok | **stable, not glacier-fed** (+9%, 3,751 m, no ice nearby) |

## Run it

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows; .venv/bin/pip on Linux/macOS
python -m jheel.pipeline                           # optional: rebuilds data/south-lhonak.json (~7 min)
python -m uvicorn app:app --port 8000              # API (+ a simple fallback page at :8000)

cd frontend && npm install && npm run build && npm start   # the full app at http://localhost:3000
python -m pytest tests                             # offline tests
```

The Next.js app talks to the API only through its own `/api/jheel/*` route, which forwards a fixed list of
endpoints. Set `JHEEL_API_URL` if the API isn't on `127.0.0.1:8000`.

Optional environment:

- `ALERT_WEBHOOK_URL`: POST each alert to an SMS gateway or siren controller instead of simulating it.
- `VLM_URL`: send questions the measurements can't answer to a vision-language model service.

## Frontend

- **Landing page (`/`)**: the real Sentinel-2 time-lapse of South Lhonak with its measured outline, stats that
  count up from the API, how it works, the screening comparison and the 2023 proof.
- **Console (`/console`)**: a satellite map with three panels.
  - **Watched lake**: area chart and year slider, radar drain check with a live scan, triggers, per-place countdowns.
  - **Area scan**: place search with every lake scored and outlined on the map.
  - **Ask Lake AI**: answers from the measurements, with the steps behind each answer.
- Built with Next.js 15, Tailwind 4, framer-motion and Leaflet.

## How it works

```
Sentinel-2 ──► lake outline + area ──► area series ──► growth trend / risk
Sentinel-1 ──► drain check (inside the outline) ──┐
gauge / station / control room ───────────────────┼──► alert engine ──► per-place SMS, siren, map
Copernicus DEM ──► flow path ──► arrival-time table ┘   (lookups only)
```

- `jheel/segment.py`: water mask. Water means NDWI > 0.2 and NIR < 0.15; snow is bright in NIR, turbid
  glacial water is not. Sen2Cor often labels silty lake water as cloud, so a cloud label only counts where SWIR
  is also bright.
- `jheel/series.py`: picks scenes and follows the lake body at the seed point from year to year.
- `jheel/drain.py`: Sentinel-1 VV in dB, 5×5 median filter, Otsu threshold on the pre-burst pass. The alarm
  fires at 25% loss of open water.
- `jheel/flow.py`: pysheds fill, flat resolution and D8 flow routing; river distance to each place; arrival
  times as a range.
- `jheel/alerts.py`: the alert engine. `jheel/ask.py`: question answering over the measurements.
- `app.py`: FastAPI server. `web/index.html`: Leaflet dashboard.

## Jheel Smriti: the control room's memory (Hindsight)

An agent that remembers every alert, drill and field check, so it can tell a river gauge that cries wolf from a real
drain. Memory lives in [Hindsight](https://github.com/vectorize-io/hindsight) (retain, recall, metadata, a bank with a
mission and a disposition). Console: the **Memory** tab.

**The decision is a fixed rule, one-sided on purpose** (`jheel/triage.py`):

| Radar pass after the trigger | False alarms from this source in memory | Decision |
|---|---|---|
| drained (25% or more of open water gone) | any | **SEND ALL NOW**: memory can never hold back a confirmed drain |
| calm | 2 or more | HOLD for at most 10 minutes (the nearest place has 78), then alerts go out automatically |
| calm | 1 | STAND BY (warn the dam crew, verify) |
| calm | 0 | SEND ALL (precaution) |
| older than 12 hours | any | treated as no pass, never as calm: STAND BY at most |
| a second independent source agrees | any | SEND ALL NOW |

- **Retain**: every event is stored with the date it happened and metadata (`trigger`, outcome as the memory's kind).
  Officers add notes in the console ("Teach it"); fired alerts are retained when `JHEEL_MEMORY=1`.
- **Recall**: on a trigger the agent recalls the history for that source. The false-alarm count is read from
  Hindsight's returned metadata (distinct stored events), never counted by a language model.
- **Lessons** (`triage._lessons`): a second, targeted recall feeds a model that only **picks** which memories matter. The lessons
  shown are those memories' own sentences, word for word, with their dates, so nothing is paraphrased. They still appear if the
  GPU is down.
- **Handover briefing** (`jheel/briefing.py`): several recalls become one briefing, numbers checked against the originals.
- **Plain-language answers** (`jheel/reason.py`, Ask AI): the model sees only the facts relevant to the question; each
  sentence must be backed by a quoted fact line or it is removed; the measured answer is always shown beside it.

The seeded history (`scripts/seed_memory.py`) is the documented 2023 record plus a **synthetic exercise log**, labelled
EXERCISE inside the memory itself. It is not real incident data.

```bash
python -m venv .hs-venv
.hs-venv/Scripts/pip install "hindsight-api-slim[embedded-db,local-onnx]" hindsight-client
scripts/start_hindsight.ps1                     # memory server on :8888 (LLM: Ollama, default qwen3:8b)
export OLLAMA_URL=http://127.0.0.1:11434        # the GPU server for lessons and plain-language answers
.venv/Scripts/python scripts/seed_memory.py --reset
.venv/Scripts/python -m uvicorn app:app --port 8000
.venv/Scripts/python scripts/e2e_memory.py      # drives the real HTTP API: 6 PASS expected
```

Without a Hindsight server the Memory tab says so (or, on a deployment with `public/recorded-memory.json`, replays a
recorded run and is labelled RECORDED RUN). The alert path never uses AI: it is a table lookup.

Other additions: alerts in English, Hindi and Nepali (the Hindi and Nepali texts need native review before any real send),
and `scripts/build_watchlist.py`, a ranked screening of the North Sikkim glacier belt (`data/watchlist.json`).

## Limits

- We watch and rank lakes; we do not predict when one will burst.
- Satellites pass every few days and publish hours later. Between passes, the alert depends on other
  triggers (gauges, stations, the control room).
- Arrival times scale linearly with river distance from one calibration point. They are first-order estimates,
  shown as ranges, not a hydraulic model.
- The segmenter is the threshold baseline. A learned U-Net must beat it on held-out lakes
  before it replaces it.
- Downstream places are a hand-picked list of five (OpenStreetMap coordinates), not a full asset inventory.
- The memory history is a labelled synthetic exercise log until a control room supplies real entries; SMS sending is simulated.

## Sources

- Sattar et al., *Science* (2025): the 2023 Sikkim flood cascade.
- ICIMOD (Feb 2025): South Lhonak outburst impacts.
- Eos, The Landslide Blog: the 3–4 October 2023 Sikkim GLOF timeline.
- NDMA National GLOF Risk Mitigation Programme: 189 high-risk lakes.
- Rawlins et al., *ESSD* (2026): Glacial Lake Observatory (planned training labels).
