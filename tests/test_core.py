"""Offline tests: no network. They guard the rules the demo relies on."""
import datetime as dt

import numpy as np
import pytest
from rasterio.transform import from_origin

from jheel import alerts, ask, flow, segment, series


def test_water_rule_rejects_snow_and_keeps_turbid_water():
    green = np.array([[0.30, 0.80, 0.22]], "f4")   # turbid lake, snow, clear lake
    nir = np.array([[0.08, 0.75, 0.02]], "f4")
    swir = np.array([[0.06, 0.20, 0.01]], "f4")
    w, _ = segment.water_s2(green, nir, swir)
    assert w.tolist() == [[True, False, True]]


def test_cloud_label_over_dark_swir_water_is_kept():
    g, n, s = (np.full((1, 2), v, "f4") for v in (0.30, 0.08, 0.06))
    s[0, 1] = 0.40                                   # real cloud: bright SWIR
    scl = np.array([[8, 8]])
    w, valid = segment.water_s2(g, n, s, scl)
    assert valid.tolist() == [[True, False]] and w.tolist() == [[True, False]]


def test_area_uses_pixel_size():
    m = np.zeros((10, 10), bool); m[2:5, 2:6] = True
    assert segment.area_m2(m, from_origin(0, 0, 10, 10)) == 12 * 100


def test_pick_lake_follows_seed_not_largest():
    w = np.zeros((40, 40), bool); w[0:20, 0:20] = True; w[30:34, 30:34] = True
    lake = series.pick_lake(w, (31, 31))
    assert lake.sum() == 16


def test_pick_lake_falls_back_near_a_frozen_seed():
    w = np.zeros((40, 40), bool); w[10:14, 15:19] = True
    assert series.pick_lake(w, (10, 10)).sum() == 16


def test_trend_is_robust_to_one_bad_year():
    pts = [("2016-10-01", 1.0e6), ("2017-10-01", 1.1e6), ("2018-10-01", 0.2e6), ("2019-10-01", 1.3e6)]
    assert 0.05e6 < series.trend(pts) < 0.2e6


def _eta():
    snapped = [{"id": "a", "name": "A", "kind": "village", "river_km": 50.0, "on_path": True, "action": "go"},
               {"id": "dam", "name": "Dam", "kind": "dam", "river_km": 100.0, "on_path": True, "action": "open"},
               {"id": "far", "name": "Far", "kind": "town", "river_km": 9.0, "on_path": False, "action": "x"}]
    return flow.eta_table(snapped, {"asset": "dam", "minutes_min": 100, "minutes_max": 150})


def test_eta_scales_from_calibration_and_skips_places_off_path():
    rows, speed = _eta()
    assert [r["id"] for r in rows] == ["a", "dam"]
    assert (rows[0]["eta_min"], rows[0]["eta_max"]) == (50, 75)
    assert speed == {"kmh_fast": 60.0, "kmh_slow": 40.0}


def test_alert_fires_one_message_per_place_and_rejects_unknown_source(tmp_path, monkeypatch):
    monkeypatch.setattr(alerts, "LOG", tmp_path / "a.jsonl")
    monkeypatch.delenv("ALERT_WEBHOOK_URL", raising=False)
    alerts.reset()
    rows, _ = _eta()
    ev = alerts.fire({"id": "l", "name": "Test"}, rows, "gauge", now=dt.datetime(2026, 10, 22, 18, 0))
    assert len(ev["messages"]) == 2 and all(m["status"] == "simulated" for m in ev["messages"])
    assert "between 00:20 and 00:45 IST" in ev["messages"][0]["text"]
    with pytest.raises(ValueError):
        alerts.fire({"id": "l", "name": "Test"}, rows, "rumour")
    with pytest.raises(ValueError):
        alerts.fire({"id": "l", "name": "Test"}, [], "gauge")


def test_ask_answers_from_measurements():
    rows, _ = _eta()
    lake = {"lake": {"name": "Test"}, "eta": rows,
            "series": [{"date": "2020-10-01", "area_km2": 1.0, "after_burst": False, "clear_over_lake": 1.0},
                       {"date": "2023-10-01", "area_km2": 1.5, "after_burst": False, "clear_over_lake": 1.0}],
            "growth": {"from": "2020-10-01", "to": "2023-10-01", "from_km2": 1.0, "to_km2": 1.5, "pct": 50.0,
                       "years": 3.0, "trend_km2_per_year": 0.167},
            "drain_check": {"drained": True, "area_loss": 0.5, "before": {"date": "d1", "water_m2": 2e6},
                            "after": {"date": "d2", "water_m2": 1e6}}}
    assert "+50.0%" in ask.answer("has it grown?", lake)["answer"]
    assert "drained" in ask.answer("did it burst?", lake)["answer"]
    rows[1]["name"] = "Dam Chungthang"
    assert "100-150 minutes" in ask.answer("when does water reach chungthang?", lake)["answer"]
    with pytest.raises(ValueError):
        ask.answer("  ", lake)
