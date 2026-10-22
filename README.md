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

## Run it

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # Windows; .venv/bin/pip on Linux/macOS
python -m jheel.pipeline                           # builds data/south-lhonak.json and web/scenes/ (~7 min)
python -m uvicorn app:app --port 8000              # open http://localhost:8000
python -m pytest tests                             # offline tests
```

Optional environment:

- `ALERT_WEBHOOK_URL`: POST each alert to an SMS gateway or siren controller instead of simulating it.
- `VLM_URL`: send image questions the rule-based answers can't handle to a vision-language model service.

## Dashboard

- Satellite map showing the lake outline for each year, the flood path and the downstream places.
- Area chart and a year slider.
- Radar drain check: the 2023 replay, plus a live scan on the latest passes. A live "drained" result fires an alert by itself.
- Trigger buttons for a river gauge, a lake station and the control room.
- Live countdown per place.
- "Ask the lake" questions, answered from the measurements with the evidence named.

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

## Limits

- We watch and rank lakes; we do not predict when one will burst.
- Satellites pass every few days and publish hours later. Between passes, the alert depends on other
  triggers (gauges, stations, the control room).
- Arrival times scale linearly with river distance from one calibration point. They are first-order estimates,
  shown as ranges, not a hydraulic model.
- The segmenter is the threshold baseline. A learned U-Net must beat it on held-out lakes
  before it replaces it.
- Downstream places are a hand-picked list of five (OpenStreetMap coordinates), not a full asset inventory.

## Sources

- Sattar et al., *Science* (2025): the 2023 Sikkim flood cascade.
- ICIMOD (Feb 2025): South Lhonak outburst impacts.
- Eos, The Landslide Blog: the 3–4 October 2023 Sikkim GLOF timeline.
- NDMA National GLOF Risk Mitigation Programme: 189 high-risk lakes.
- Rawlins et al., *ESSD* (2026): Glacial Lake Observatory (planned training labels).
