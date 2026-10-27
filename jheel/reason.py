"""Plain-language explainer on a GPU. The measured answer (jheel/ask.py) stays the source of truth; this layer only
re-words it, in the asker's language and at a child's reading level, from a fixed block of facts. It runs on any
Ollama server (OLLAMA_URL, e.g. the office RTX 4060 over Tailscale). If the server is unreachable the caller keeps the
measured answer, so the console never depends on it."""
import os
import time

import requests

MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
LANGS = {"en": "English", "hi": "Hindi (Devanagari script)", "ne": "Nepali (Devanagari script)"}
KEEP_ALIVE = "10m"          # unload after ten idle minutes so the shared GPU is given back


def url():
    u = os.environ.get("OLLAMA_URL", "").strip().rstrip("/")
    return u or None


def available():
    u = url()
    if not u:
        return False
    try:
        return requests.get(u + "/api/tags", timeout=3).ok
    except requests.RequestException:
        return False


def _sections(lake, watch=None):
    g, d = lake["growth"], lake["drain_check"]
    b, a = d["before"], d["after"]
    sec = {
        "lake": f"The lake is {lake['lake']['name']} in Sikkim, India.",
        "growth": f"Its area grew from {g['from_km2']:.2f} km2 ({g['from']}) to {g['to_km2']:.2f} km2 ({g['to']}), +{g['pct']}%.",
        "drain": (f"Radar measured the open water inside the lake fall from {b['water_m2'] / 1e6:.2f} km2 ({b['date']}) to "
                  f"{a['water_m2'] / 1e6:.2f} km2 ({a['date']}), a {d['area_loss']:.0%} loss. Verdict: "
                  f"{'DRAINED' if d['drained'] else 'stable'}. Some water remained: the lake did not become empty."),
        "eta": ("Places on the flood path, with minutes until water arrives after a burst: "
                + "; ".join(f"{r['name']} {r['eta_min']}-{r['eta_max']}" for r in lake["eta"]) + "."),
        "actions": "Action for each place: " + "; ".join(f"{r['name']}: {r['action']}" for r in lake["eta"]),
        "limits": "Jheel Prahari does not predict when a lake will burst. Satellites pass every few days.",
    }
    if watch and watch.get("lakes"):
        top = watch["lakes"][:3]
        sec["watch"] = (f"Screening of the {watch['region']} found {watch['counts']['high']} high, {watch['counts']['watch']} watch and "
                        f"{watch['counts']['low']} low hazard lakes. Top: " + "; ".join(
                            f"{x['id']} score {x['score']}, {x['area_km2']:.2f} km2, {x['elevation_m']} m" for x in top) + ".")
    return sec


def facts_for(question, lake, watch=None):
    """Only the facts the question is about. A model given everything wanders into advice nobody asked for."""
    q = question.lower()
    sec = _sections(lake, watch)
    want = ["lake"]
    if any(w in q for w in ("grow", "bigger", "larger", "area", "size", "change", "trend")):
        want.append("growth")
    if any(w in q for w in ("drain", "burst", "empt", "radar", "outburst", "breach", "happen", "what")):
        want += ["growth", "drain"]
    if any(w in q for w in ("when", "minute", "reach", "arrive", "time", "place", "village", "downstream", "flood", "path")):
        want.append("eta")
    if any(w in q for w in ("do", "action", "evacuat", "safe", "advice", "should")):
        want.append("actions")
    if any(w in q for w in ("predict", "forecast", "next", "future", "sure", "accurate")):
        want.append("limits")
    if any(w in q for w in ("rank", "danger", "risk", "sikkim", "other lakes", "which lake", "worst")) and "watch" in sec:
        want.append("watch")
    if len(want) == 1:
        want += ["growth", "drain", "eta"]
    want.append("limits")
    return chr(10).join(sec[k] for k in dict.fromkeys(want) if k in sec)


def facts(lake, watch=None):
    return chr(10).join(_sections(lake, watch).values())


GLOSSARY = {
    "en": "",
    "hi": "Use these words: lake = झील (never जलाशय), radar = रडार, flood = बाढ़, minutes = मिनट. Natural spoken Hindi.",
    "ne": "Write real Nepali, not Hindi. Use: lake = ताल, radar = रडार, flood = बाढी, minutes = मिनेट, and the endings छ, हुन्छ, मा, को, बाट, पछि. Never use है, से, का, की, में.",
}
_DEVA = str.maketrans("०१२३४५६७८९", "0123456789")


def _numbers(text):
    return set(__import__("re").findall(r"\d+(?:\.\d+)?", text.translate(_DEVA)))


def _faithful(answer, fact_block):
    """Every number in the answer must be in the facts (Devanagari digits read as ASCII)."""
    return _numbers(answer) <= _numbers(fact_block)


def _split(text):
    """Sentences of an answer (. ! ? and the Devanagari danda)."""
    return [x.strip() for x in __import__("re").split(r"(?<=[.!?।])\s+", text.strip()) if x.strip()]


def explain(question, measured, fact_block, lang="en", simple=True):
    """Return (text, ms, dropped). The model re-words; it may not add a number or a claim. A second pass marks every
    sentence supported or not by the FACTS and the unsupported ones are removed, so a motivational or invented sentence
    never reaches the reader. If nothing supported is left, raise and the caller keeps the measured answer."""
    if not url():
        raise RuntimeError("no GPU server configured")
    level = "very simple words that a 12-year-old understands, no jargon" if simple else "clear, short sentences"
    system = (f"You explain a glacial-lake early-warning system. Use ONLY the FACTS below. Every sentence must restate a fact; "
              f"no conclusions, no encouragement, no cause, advice, number, place or detail that is not written in the FACTS, "
              f"and never say more than the FACTS say (if some water remained, never say the lake is empty). If the FACTS do not "
              f"contain the answer, say you do not know. Write in {LANGS.get(lang, 'English')}, in {level}. {GLOSSARY.get(lang, '')} "
              f"At most 3 short sentences.{chr(10)}{chr(10)}FACTS:{chr(10)}{fact_block}")
    user = question if not measured else f"{question}{chr(10)}{chr(10)}(The measured answer is: {measured})"
    text, total = chat(system, user, max_tokens=240)
    sents = [x for x in _split(text) if _faithful(x, fact_block)]          # a sentence with a number the facts lack is out
    dropped = len(_split(text)) - len(sents)
    kept = []
    for x in sents:                      # one check per sentence, and the checker must quote the fact that backs it
        verdict, ms2 = chat('You check ONE sentence against FACTS. Reply JSON only: {"fact": "<copy ONE line of FACTS word for word that says '
                            'the same thing as the sentence, or empty string>"}. If no single FACT line says what the sentence says, '
                            "return an empty string. Advice, causes, predictions, reassurance, comparisons such as 'largest', and "
                            "'empty' when some water remained are NOT supported. Related is not enough: it must say the same thing.",
                            f"FACTS:{chr(10)}{fact_block}{chr(10)}{chr(10)}SENTENCE ({LANGS.get(lang)}):{chr(10)}{x}", json_mode=True, max_tokens=140)
        total += ms2
        try:
            quote = str(__import__("json").loads(verdict).get("fact", "")).strip()
        except ValueError:
            quote = ""
        if len(quote) >= 12 and any(quote in line or line in quote for line in fact_block.split(chr(10))):
            kept.append(x)
    dropped += len(sents) - len(kept)
    sents = kept
    if not sents:
        raise RuntimeError("no sentence passed the fact check")
    return " ".join(sents), total, dropped


def chat(system, user, json_mode=False, max_tokens=320):
    """One grounded call to the GPU server. Returns (text, ms)."""
    u = url()
    if not u:
        raise RuntimeError("no GPU server configured")
    body = {"model": MODEL, "stream": False, "think": False, "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0.1, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["format"] = "json"
    t = time.perf_counter()
    r = requests.post(u + "/api/chat", timeout=90, json=body)
    r.raise_for_status()
    text = (r.json().get("message", {}).get("content") or "").strip()
    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()
    if not text:
        raise RuntimeError("empty answer from the model")
    return text, round((time.perf_counter() - t) * 1000)
