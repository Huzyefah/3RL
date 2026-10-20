"""Scorer (FINAL_PLAN §9).

- Detected: an alert on the root service, a dependency-linked service, or the incident's segment falls inside
  [precursor_start − 30 min, onset + 5 min].
- Lead time: onset − first matching alert, clipped at 0.
- False positive: no related incident onset falls inside [t − 5, t + 60] min. Extra alerts for an incident that
  was already matched are duplicates, not FPs.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from sentinel.impact.business import FAILURE_RATE_BY_TIER, pkr_protected
from sentinel.topology import Topology

PRE_SLACK = timedelta(minutes=30)
POST_SLACK = timedelta(minutes=5)
FP_BEFORE = timedelta(minutes=5)
FP_AFTER = timedelta(minutes=60)


def _related(topo: Topology, alert: dict, inc) -> bool:
    if alert["segment"] != "*" and alert["segment"] == inc.segment:
        return True
    return alert["service"] == inc.service or topo.linked(alert["service"], inc.service)


def match(alerts: list[dict], incidents: list, topo: Topology | None = None) -> dict:
    """Per-incident first matching alert + FP / duplicate classification of every alert."""
    topo = topo or Topology.load()
    first: dict[str, dict] = {}
    for inc in incidents:
        lo, hi = inc.precursor_start - PRE_SLACK, inc.onset + POST_SLACK
        hits = [a for a in alerts if lo <= a["ts"] <= hi and _related(topo, a, inc)]
        if hits:
            first[inc.id] = min(hits, key=lambda a: a["ts"])
    fps, dups = [], []
    for a in alerts:
        near = [
            i
            for i in incidents
            if a["ts"] - FP_BEFORE <= i.onset <= a["ts"] + FP_AFTER and _related(topo, a, i)
        ]
        near += [i for i in incidents if i.id in first and first[i.id] is a]
        if not near:
            fps.append(a)
        elif not any(first.get(i.id) is a for i in near):
            dups.append(a)
    return {"first": first, "fps": fps, "dups": dups}


def score(
    alerts: list[dict],
    incidents: list,
    days: list[datetime],
    gmv_per_min=None,
    n_services: int = 8,
    topo: Topology | None = None,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict:
    """Headline metrics with day-block bootstrap 95% CIs."""
    topo = topo or Topology.load()
    m = match(alerts, incidents, topo)
    res = _metrics(m, alerts, incidents, len(days), n_services, gmv_per_min, topo)
    rng = np.random.default_rng(seed)
    day_of = lambda t: t.replace(hour=0, minute=0, second=0, microsecond=0)
    by_day_alerts = {d: [a for a in alerts if day_of(a["ts"]) == d] for d in days}
    by_day_inc = {d: [i for i in incidents if day_of(i.onset) == d] for d in days}
    boots: dict[str, list[float]] = {
        k: [] for k in ("recall", "precision", "fp_per_service_day", "lead_median")
    }
    for _ in range(n_boot):
        pick = rng.choice(len(days), size=len(days), replace=True)
        a = [x for p in pick for x in by_day_alerts[days[p]]]
        inc = [x for p in pick for x in by_day_inc[days[p]]]
        if not inc:
            continue
        mm = _resample_match(m, a, inc)
        r = _metrics(mm, a, inc, len(days), n_services, None, topo, light=True)
        for k, vals in boots.items():
            if r[k] is not None:
                vals.append(r[k])
    res["ci95"] = {
        k: [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if vals else None
        for k, vals in boots.items()
    }
    return res


def _resample_match(m: dict, alerts: list[dict], incidents: list) -> dict:
    ids = {id(a) for a in alerts}
    first = {i.id: m["first"][i.id] for i in incidents if i.id in m["first"]}
    return {"first": first, "fps": [a for a in m["fps"] if id(a) in ids], "dups": []}


def _metrics(m, alerts, incidents, n_days, n_services, gmv_per_min, topo, light: bool = False) -> dict:
    n_inc = len(incidents)
    detected = [i for i in incidents if i.id in m["first"]]
    tp = len(detected)
    fp = len(m["fps"])
    leads = [max(0.0, (i.onset - m["first"][i.id]["ts"]).total_seconds() / 60) for i in detected]
    nonabrupt = [i for i in detected if not i.abrupt]
    leads_na = [max(0.0, (i.onset - m["first"][i.id]["ts"]).total_seconds() / 60) for i in nonabrupt]
    out = {
        "recall": tp / n_inc if n_inc else None,
        "precision": tp / (tp + fp) if tp + fp else None,
        "fp_per_service_day": fp / (n_services * n_days) if n_days else None,
        "lead_median": float(np.median(leads)) if leads else None,
    }
    if light:
        return out
    pkr = 0.0
    if gmv_per_min is not None:
        for i in nonabrupt:
            lead = (i.onset - m["first"][i.id]["ts"]).total_seconds() / 60
            pkr += pkr_protected(
                lead, i.duration_min, gmv_per_min(i.onset), FAILURE_RATE_BY_TIER[topo.tier(i.service)]
            )
    out.update(
        {
            "incidents": n_inc,
            "detected": tp,
            "false_positives": fp,
            "duplicates": len(m["dups"]),
            "alerts": len(alerts),
            "alerts_per_day": len(alerts) / n_days if n_days else None,
            "lead_p25": float(np.percentile(leads, 25)) if leads else None,
            "lead_p75": float(np.percentile(leads, 75)) if leads else None,
            "lead_median_non_abrupt": float(np.median(leads_na)) if leads_na else None,
            "pct_lead_gt0_non_abrupt": float(np.mean([x > 0 for x in leads_na])) if leads_na else None,
            "abrupt_detected": sum(i.abrupt for i in detected),
            "leads": {
                i.id: round(max(0.0, (i.onset - m["first"][i.id]["ts"]).total_seconds() / 60), 1)
                for i in detected
            },
            "pkr_protected_est": round(pkr),
        }
    )
    return out
