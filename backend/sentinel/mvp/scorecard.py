"""Scorecard computed by code: CSV bench B0/B1 + quick S1/S2 over the Aug 21-30 test split (estimate)."""

from __future__ import annotations

import statistics
from datetime import datetime

from sentinel.calendar import events_at
from sentinel.datagen.episode_map import load_episode_map
from sentinel.eval.csv_bench import csv_bench


def compute() -> dict:
    from sentinel.mvp.engine import Holt

    rows = [r.model_dump() for r in csv_bench(split="all")]
    try:
        rows += _s1_s2(Holt)
    except Exception as e:  # noqa: BLE001
        rows.append(
            {"system": "S1/S2", "split": "test", "notes": f"not computed: {type(e).__name__}: {e}"}
        )
    return {
        "split": "test = onsets 2026-08-21..08-30; B0/B1 on all CSV rows",
        "label": "estimate",
        "rows": rows,
    }


def _s1_s2(Holt) -> list[dict]:
    from sentinel.datagen.generator import build

    ds = build("ps02", seed=0)
    m = ds.metrics
    eps = [e for e in load_episode_map() if "2026-08-21" <= e.onset_ts[:10] <= "2026-08-30"]
    res = {
        "S1": {"tp": 0, "fp": 0, "fn": 0, "leads": []},
        "S2": {"tp": 0, "fp": 0, "fn": 0, "leads": []},
    }
    for ep in eps:
        onset = datetime.fromisoformat(ep.onset_ts)
        sel = m[
            (m["service"] == ep.service)
            & (m["metric"] == ep.metric)
            & (m["ts"] >= onset - __import__("datetime").timedelta(minutes=60))
            & (m["ts"] <= onset + __import__("datetime").timedelta(minutes=2))
        ]
        if ep.segment_key and ep.segment_key != "*":
            sel = sel[sel["segment_key"].astype(str) == ep.segment_key]
        s = sel.groupby("ts", observed=True)["u"].max().sort_index()
        h, fired, lead, trend = Holt(), False, None, 0.0
        for ts, u in s.items():
            _, trig = h.update(float(u))
            if trig:
                fired, lead, trend = (
                    True,
                    (onset - ts.to_pydatetime()).total_seconds() / 60,
                    h.trend,
                )
                break
        benign = bool(events_at(onset)) and trend < 0.03
        for name, alert in (("S1", fired), ("S2", fired and not benign)):
            r = res[name]
            if ep.kind == "incident":
                if alert:
                    r["tp"] += 1
                    r["leads"].append(max(lead or 0.0, 0.0))
                else:
                    r["fn"] += 1
            elif alert:
                r["fp"] += 1
    out = []
    for name, r in res.items():
        tp, fp, fn = r["tp"], r["fp"], r["fn"]
        leads = r["leads"]
        out.append(
            {
                "system": name,
                "split": "test",
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                "recall": round(tp / (tp + fn), 3) if tp + fn else None,
                "median_lead_min": round(statistics.median(leads), 1) if leads else None,
                "pct_lead_gt0": round(sum(1 for x in leads if x > 0) / len(leads), 3)
                if leads
                else None,
                "notes": "estimate: Holt detector on synthetic dense series"
                + (" + calendar/flat-trend suppression" if name == "S2" else ""),
            }
        )
    return out
