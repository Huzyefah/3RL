"""Deterministic data tools for the agents. Every result carries an evidence_id `<kind>:<hash8>`.

Tools return aggregates and redacted samples only, so no PII ever reaches an LLM (FINAL_PLAN §7.3).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from sentinel.datagen.corpus import MemoryDoc, corpus
from sentinel.impact.business import AVG_TICKET_PKR, FAILURE_RATE_BY_TIER
from sentinel.redact import redact
from sentinel.topology import Topology


def _eid(kind: str, payload: dict) -> str:
    return f"{kind}:{hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:8]}"


def _wrap(kind: str, payload: dict, registry: dict) -> dict:
    eid = _eid(kind, payload)
    out = {"evidence_id": eid, **payload}
    registry[eid] = out
    return out


@dataclass
class ToolContext:
    ds: object  # sentinel.datagen.generator.Dataset
    now: datetime
    topo: Topology = field(default_factory=Topology.load)
    evidence: dict = field(default_factory=dict)
    last_signal: dict = field(default_factory=dict)

    def i(self) -> int:
        return self.ds.loc(self.now)


def get_metric_window(
    ctx: ToolContext, service: str, metric: str, segment: str = "*", minutes: int = 30
) -> dict:
    s = ctx.ds.series[(service, metric, segment)]
    i = ctx.i()
    w = s.u[max(0, i - minutes) : i + 1]
    slope = float(np.polyfit(np.arange(len(w)), w, 1)[0]) if len(w) > 2 else 0.0
    return _wrap(
        "metric",
        {
            "service": service,
            "metric": metric,
            "segment": segment,
            "u_now": round(float(w[-1]), 3),
            "u_start": round(float(w[0]), 3),
            "u_max": round(float(w.max()), 3),
            "slope_per_min": round(slope, 4),
            "minutes": minutes,
        },
        ctx.evidence,
    )


def get_segment_breakdown(ctx: ToolContext, service: str) -> dict:
    i = ctx.i()
    rows = []
    for (svc, metric, seg), s in ctx.ds.series.items():
        if svc != service or seg == "*" or s.n_total is None:
            continue
        nt, nb = int(s.n_total[max(0, i - 4) : i + 1].sum()), int(s.n_bad[max(0, i - 4) : i + 1].sum())
        rows.append({"segment": seg, "metric": metric, "bad_rate": round(nb / nt, 4) if nt else 0.0, "n": nt})
    rows.sort(key=lambda r: -r["bad_rate"])
    peers = [r["bad_rate"] for r in rows[1:] if r["metric"] == (rows[0]["metric"] if rows else None)]
    ratio = round(rows[0]["bad_rate"] / max(np.mean(peers), 1e-4), 1) if rows and peers else None
    return _wrap(
        "segment",
        {"service": service, "worst": rows[0] if rows else None, "x_vs_peers": ratio, "segments": rows[:6]},
        ctx.evidence,
    )


def get_logs(ctx: ToolContext, service: str, minutes: int = 15) -> dict:
    lg = ctx.ds.logs
    w = lg[(lg.service == service) & (lg.ts <= ctx.now) & (lg.ts > ctx.now - timedelta(minutes=minutes))]
    top = Counter()
    sample = {}
    for r in w.itertuples():
        top[r.template] += int(r.count)
        sample[r.template] = redact(r.message)
    templates = [
        {"template": t, "count": c, "sample": sample[t], "baseline_per_15m": 1} for t, c in top.most_common(3)
    ]
    return _wrap("log", {"service": service, "minutes": minutes, "novel_templates": templates}, ctx.evidence)


def _events(
    ctx: ToolContext, kinds: tuple[str, ...], service: str, before_min: int, after_min: int
) -> list[dict]:
    ev = ctx.ds.events
    lo, hi = ctx.now - timedelta(minutes=before_min), ctx.now + timedelta(minutes=after_min)
    w = ev[(ev.kind.isin(kinds)) & (ev.ts <= hi) & (ev.end >= lo) & (ev.service.isin([service, "*"]))]
    return [
        {
            "kind": r.kind,
            "name": r.name,
            "service": r.service,
            "start": r.ts.isoformat(),
            "end": r.end.isoformat(),
        }
        for r in w.itertuples()
    ]  # the hidden `caused` ground-truth column is never exposed


def get_change_events(ctx: ToolContext, service: str, minutes: int = 90) -> dict:
    return _wrap(
        "change",
        {"service": service, "changes": _events(ctx, ("change",), service, minutes, 0)},
        ctx.evidence,
    )


def get_calendar(ctx: ToolContext, service: str) -> dict:
    return _wrap(
        "calendar",
        {"service": service, "events": _events(ctx, ("calendar", "cron"), service, 60, 5)},
        ctx.evidence,
    )


def get_forecast(ctx: ToolContext, service: str, metric: str, segment: str = "*") -> dict:
    sig = ctx.last_signal.get((service, metric, segment), {})
    eta = sig.get("eta")
    return _wrap(
        "forecast",
        {
            "service": service,
            "metric": metric,
            "segment": segment,
            "eta_minutes": None if eta is None else round(eta, 1),
            "predictive_trigger": bool(sig.get("pred")),
            "u": round(sig.get("u", 0.0), 3),
        },
        ctx.evidence,
    )


def get_topology(ctx: ToolContext, service: str) -> dict:
    t = ctx.topo
    return _wrap(
        "topology",
        {
            "service": service,
            "team": t.team(service),
            "tier": t.tier(service),
            "depends_on": t.depends_on(service),
            "blast_radius": t.blast_radius(service),
        },
        ctx.evidence,
    )


def estimate_impact(ctx: ToolContext, service: str) -> dict:
    tps = float(sum(v[ctx.i()] for v in ctx.ds.tps.values()))
    fr = FAILURE_RATE_BY_TIER[ctx.topo.tier(service)]
    pkr = tps * 60 * AVG_TICKET_PKR * fr
    return _wrap(
        "impact",
        {
            "service": service,
            "platform_tps": round(tps, 1),
            "failure_rate_assumed": fr,
            "pkr_at_risk_per_min": round(pkr),
            "customers_affected_est_per_10min": int(tps * 600 * fr * 0.85),
            "label": "estimate",
        },
        ctx.evidence,
    )


class Memory:
    """recall_similar: metadata pre-filter + TF-IDF cosine over train-split postmortems (no LLM hop)."""

    def __init__(self, docs: list[MemoryDoc] | None = None) -> None:
        self.docs = docs if docs is not None else corpus("train")
        self.df = Counter(w for d in self.docs for w in set(self._tok(d)))

    @staticmethod
    def _tok(d) -> list[str]:
        text = d if isinstance(d, str) else f"{d.text} {d.code} {d.service} {d.metric}"
        return [w.strip(".,:;()").lower() for w in text.split() if len(w) > 2]

    def _vec(self, toks: list[str]) -> dict[str, float]:
        n = len(self.docs)
        tf = Counter(toks)
        return {w: c * math.log((n + 1) / (self.df.get(w, 0) + 1)) for w, c in tf.items()}

    def search(self, query: str, service: str, k: int = 3) -> list[tuple[MemoryDoc, float]]:
        q = self._vec(self._tok(query))
        qn = math.sqrt(sum(v * v for v in q.values())) or 1.0
        out = []
        for d in self.docs:
            v = self._vec(self._tok(d))
            dot = sum(q.get(w, 0) * x for w, x in v.items())
            sim = dot / (qn * (math.sqrt(sum(x * x for x in v.values())) or 1.0))
            sim += 0.15 * (d.service == service)
            out.append((d, min(0.99, sim)))
        return sorted(out, key=lambda t: -t[1])[:k]


def recall_similar(ctx: ToolContext, mem: Memory, query: str, service: str) -> dict:
    hits = [
        {"id": d.id, "similarity": round(s, 2), "code": d.code, "label": d.label, "fix": d.fix}
        for d, s in mem.search(query, service)
        if s >= 0.2
    ]
    return _wrap("memory", {"query_service": service, "hits": hits}, ctx.evidence)
