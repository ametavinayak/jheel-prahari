"""Jheel Prahari prototype server: serves the dashboard and the lake data, runs live radar scans, fires alerts.
Run:  python -m uvicorn app:app --port 8000"""
import datetime
import json
import os
import uuid
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jheel import alerts, area, ask, drain
from jheel.config import LAKE

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / f"{LAKE['id']}.json"

app = FastAPI(title="Jheel Prahari")
# Serverless hosts freeze a function once it has answered and spread polls across instances, so there the scan and
# the area analysis run inside the POST and come back finished (the client stops polling on a non-running state).
SYNC = os.environ.get("JHEEL_SYNC") == "1"
_scan = {"state": "idle", "result": None, "error": None, "started": None, "finished": None, "alert": None}
_scan_lock = threading.Lock()


def lake():
    if not DATA.exists():
        raise HTTPException(503, "lake data not built yet: run  python -m jheel.pipeline")
    return json.loads(DATA.read_text())


class Trigger(BaseModel):
    source: str = "manual"
    detail: str | None = None


class Question(BaseModel):
    question: str


@app.get("/api/lake")
def get_lake():
    return lake()


@app.post("/api/trigger")
def trigger(t: Trigger):
    data = lake()
    try:
        return alerts.fire(data["lake"], data["eta"], t.source, t.detail)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/alerts")
def get_alerts():
    return alerts.recent()


@app.post("/api/ask")
def post_ask(q: Question):
    try:
        return ask.answer(q.question, lake())
    except ValueError as e:
        raise HTTPException(400, str(e))


def _run_scan(outline):
    try:
        res = drain.check_live(outline, LAKE["aoi"])
        ev = None
        if res["drained"]:
            data = lake()
            ev = alerts.fire(data["lake"], data["eta"], "drain_check",
                             f"{res['area_loss']:.0%} of open water gone, {res['before']['date']} -> {res['after']['date']}")
        with _scan_lock:
            _scan.update(state="done", result=res, alert=ev, finished=time.time())
    except Exception as e:  # network, catalogue or data problems are reported, not swallowed
        with _scan_lock:
            _scan.update(state="error", error=f"{type(e).__name__}: {e}", finished=time.time())


@app.post("/api/scan")
def start_scan():
    """Live drain check on the two latest Sentinel-1 passes (about a minute). Fires an alert if drained."""
    data = lake()
    with _scan_lock:
        if _scan["state"] == "running":
            return _scan
        _scan.update(state="running", result=None, error=None, alert=None, started=time.time(), finished=None)
    if SYNC:
        _run_scan(data["series"][-1]["outline"])
        with _scan_lock:
            return dict(_scan)
    threading.Thread(target=_run_scan, args=(data["series"][-1]["outline"],), daemon=True).start()
    return _scan


@app.get("/api/scan")
def get_scan():
    with _scan_lock:
        return dict(_scan)


class AreaRequest(BaseModel):
    query: str | None = None                 # a place name, geocoded with OpenStreetMap
    bbox: list[float] | None = None          # or [west, south, east, north] in degrees
    as_of: str | None = None                 # YYYY-MM-DD; replay the screening as it would have looked then


_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
MAX_RUNNING = 2


def _run_area(job_id, req):
    def log(msg):
        with _jobs_lock:
            _jobs[job_id]["stage"] = msg
    try:
        place = None
        if req.bbox:
            box = req.bbox
        else:
            log("finding the place")
            place = area.geocode(req.query)
            box = area.box_around(place["lat"], place["lon"])
        res = area.analyse(box, req.as_of, log=log)
        res["place"] = place
        with _jobs_lock:
            _jobs[job_id].update(state="done", result=res, finished=time.time())
    except (LookupError, ValueError) as e:
        with _jobs_lock:
            _jobs[job_id].update(state="error", error=str(e), finished=time.time())
    except Exception as e:  # network or catalogue failures are reported, not swallowed
        with _jobs_lock:
            _jobs[job_id].update(state="error", error=f"{type(e).__name__}: {e}", finished=time.time())


@app.post("/api/analyze")
def start_area(req: AreaRequest):
    """Screen an area for glacial-lake hazard (about a minute). Returns a job id to poll."""
    if not req.query and not req.bbox:
        raise HTTPException(400, "give a place name or a bbox")
    if req.bbox:
        if len(req.bbox) != 4:
            raise HTTPException(400, "bbox must be [west, south, east, north]")
        try:
            area.check_box(tuple(req.bbox))
        except ValueError as e:
            raise HTTPException(400, str(e))
    if req.as_of:
        try:
            datetime.date.fromisoformat(req.as_of)
        except ValueError:
            raise HTTPException(400, "as_of must be YYYY-MM-DD")
    with _jobs_lock:
        if sum(j["state"] == "running" for j in _jobs.values()) >= MAX_RUNNING:
            raise HTTPException(429, "two analyses already running; try again in a minute")
        job_id = uuid.uuid4().hex[:10]
        _jobs[job_id] = {"id": job_id, "state": "running", "stage": "queued", "result": None, "error": None,
                         "started": time.time(), "finished": None}
    if SYNC:
        _run_area(job_id, req)
        with _jobs_lock:
            return _jobs.pop(job_id)
    threading.Thread(target=_run_area, args=(job_id, req), daemon=True).start()
    return _jobs[job_id]


@app.get("/api/analyze/{job_id}")
def get_area(job_id: str):
    with _jobs_lock:
        if job_id not in _jobs:
            raise HTTPException(404, "no such analysis")
        return dict(_jobs[job_id])


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/", StaticFiles(directory=ROOT / "web"), name="web")
