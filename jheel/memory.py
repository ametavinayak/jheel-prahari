"""Jheel Smriti: the control room's long-term memory, kept in Hindsight (https://github.com/vectorize-io/hindsight).

What is remembered: every alert that was sent, every drill and field check, every officer's note on how an event really
went. What it is used for: when a trigger arrives, the agent recalls what happened the last times (false alarms from the
same source, how long the dam gates take to open, which phone numbers failed) and says what to do. The memory can make
the agent more careful about an UNCONFIRMED trigger; it can never suppress a radar-confirmed drain (see triage.py).

Configuration: HINDSIGHT_URL (default http://127.0.0.1:8888), HINDSIGHT_API_KEY (Hindsight Cloud only),
HINDSIGHT_BANK (default sikkim-sdma-control-room)."""
import datetime as dt
import os
import concurrent.futures
import threading
import time

BANK = os.environ.get("HINDSIGHT_BANK", "sikkim-sdma-control-room")
MISSION = ("You are the long-term memory of a state disaster control room that watches glacial lakes in Sikkim. "
           "Remember every alert, drill, field check and officer note with its date, the lake and the place involved. "
           "Track which trigger sources have given false alarms, how long real actions take (opening dam gates, "
           "reaching a village), and what failed. Prefer exact numbers and dates over summaries.")
DISPOSITION = {"skepticism": 4, "literalism": 4, "empathy": 2}   # careful with unconfirmed claims, exact, unsentimental

_client = None
_lock = threading.Lock()
# The Hindsight client keeps one event loop and breaks if it is driven from different threads (the web server uses a
# thread per request). So every call runs on this single dedicated thread, one at a time.
_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="hindsight")


def _on_pool(fn, *a, **kw):
    return _pool.submit(fn, *a, **kw).result()


_status = {"ok": False, "checked": 0.0, "error": None}


def _cli():
    global _client
    with _lock:
        if _client is None:
            from hindsight_client import Hindsight
            kw = {"base_url": os.environ.get("HINDSIGHT_URL", "http://127.0.0.1:8888"), "timeout": 120.0}
            if os.environ.get("HINDSIGHT_API_KEY"):
                kw["api_key"] = os.environ["HINDSIGHT_API_KEY"]
            _client = Hindsight(**kw)
        return _client


def status(max_age=15):
    """Is a Hindsight server reachable? Cached for a few seconds so polling the console stays cheap."""
    if time.time() - _status["checked"] < max_age:
        return dict(_status, bank=BANK)
    try:
        v = _on_pool(lambda: _cli().get_version())
        _status.update(ok=True, error=None, version=getattr(v, "api_version", None))
    except Exception as e:  # unreachable, not installed, wrong key: reported, never raised into the console
        _status.update(ok=False, error=f"{type(e).__name__}: {str(e)[:120]}")
    _status["checked"] = time.time()
    return dict(_status, bank=BANK)


def ensure_bank():
    _on_pool(lambda: _cli().create_bank(bank_id=BANK, name="Sikkim control room", mission=MISSION, disposition=DISPOSITION))


def retain(text, kind, when=None, meta=None, wait=True, doc_id=None):
    """Store one event. `when` is when it HAPPENED (not now), so recall can reason about order and recency."""
    kw = {"bank_id": BANK, "content": text, "context": kind, "retain_async": not wait}
    if when:
        kw["timestamp"] = when
    if doc_id:
        kw["document_id"] = doc_id          # same id again replaces the entry, so seeding twice never duplicates
    if meta:
        kw["metadata"] = {k: str(v) for k, v in meta.items()}
    return _on_pool(lambda: _cli().retain(**kw))


def retain_background(text, kind, when=None, meta=None):
    """Fire-and-forget, for events that must never slow the alarm path (alerts being sent)."""
    def run():
        try:
            retain(text, kind, when or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None), meta, wait=False)
        except Exception:
            pass  # the alert already went out; losing its memory entry must not matter to the caller
    threading.Thread(target=run, daemon=True).start()


def recall(query, n=8, budget="mid"):
    """Memories relevant to `query`. Each carries the kind it was stored under, its document id and its metadata, so the
    caller can count events from what Hindsight returns instead of trusting a language model's arithmetic."""
    res = _on_pool(lambda: _cli().recall(bank_id=BANK, query=query, budget=budget, max_tokens=2048, include_chunks=True, max_chunk_tokens=400))
    chunks = getattr(res, "chunks", None) or {}
    out = []
    for r in res.results[:n]:
        md = getattr(r, "metadata", None) or {}
        out.append({"text": r.text, "type": getattr(r, "type", None), "kind": getattr(r, "context", None),
                    "doc": getattr(r, "document_id", None), "trigger": md.get("trigger"),
                    "source": (chunks.get(getattr(r, "chunk_id", None)).text if chunks.get(getattr(r, "chunk_id", None)) else None),
                    "when": str(getattr(r, "occurred_start", None) or getattr(r, "mentioned_at", None) or "") or None})
    return out


def reflect(query, context=None, budget="low"):
    r = _on_pool(lambda: _cli().reflect(bank_id=BANK, query=query, budget=budget, context=context))
    return r.text


def originals(mems):
    """One entry per stored event, carrying the text as it was written (Hindsight rewrites facts; the original keeps the
    owner, the due date and the exact wording). Order is kept."""
    seen, out = set(), []
    for m in mems:
        key = m.get("doc") or m["text"]
        if key in seen:
            continue
        seen.add(key)
        out.append({"text": m.get("source") or m["text"], "when": m.get("when"), "kind": m.get("kind"), "doc": m.get("doc")})
    return out
