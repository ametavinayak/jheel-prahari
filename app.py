"""Jheel Prahari prototype server: serves the dashboard and the lake data, runs live radar scans, fires alerts.
Run:  python -m uvicorn app:app --port 8000"""
import json
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jheel import alerts, ask, drain
from jheel.config import LAKE

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / f"{LAKE['id']}.json"

app = FastAPI(title="Jheel Prahari")
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
    threading.Thread(target=_run_scan, args=(data["series"][-1]["outline"],), daemon=True).start()
    return _scan


@app.get("/api/scan")
def get_scan():
    with _scan_lock:
        return dict(_scan)


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/", StaticFiles(directory=ROOT / "web"), name="web")
