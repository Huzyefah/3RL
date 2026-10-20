"""Detector engine: per-series state, corroboration, risk, and candidate emission per ablation config.

One update path (`SeriesState.update`) feeds two drivers:
- `DetectorEngine.step(...)` for the live path (envelopes from the sim or the replayer);
- `compute_signals(ds, ...)` for evaluation, which records per-minute signals so τ can be tuned cheaply.

Configs (FINAL_PLAN §6): B0 u≥1.0 · B1 u≥0.95 · S1 Holt predictive or band · S2 full risk ≥ τ (+ grouping).
B0/B1/S1 watch the 7 PS-02 infra metrics (today's monitor); S2 adds the binomial segment metrics.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from sentinel.detect.binom import binom_alarm
from sentinel.detect.ewma import EwmaZ, Persistence
from sentinel.detect.holt import HoltState
from sentinel.detect.risk import risk
from sentinel.schemas import CRITICAL_U, Candidate
from sentinel.topology import Topology

SeriesKey = tuple[str, str, str]
CONFIGS = ("B0", "B1", "S1", "S2")
COOLDOWN_MIN = 15
CLEAR_MIN = 10
CORROB_WINDOW_MIN = 5
RATE_WINDOW_MIN = 5
CORROB_KINDS = ("latency", "errors", "dependent", "segment", "logs")


class SeriesState:
    """Detector state for one (service, metric, segment)."""

    __slots__ = ("direction", "holt", "is_rate", "key", "pers", "slo", "win", "z")

    def __init__(self, key: SeriesKey, is_rate: bool, direction: str, slo: float) -> None:
        self.key, self.is_rate, self.direction, self.slo = key, is_rate, direction, slo
        self.holt, self.z, self.pers = HoltState(), EwmaZ(), Persistence()
        self.win: deque[tuple[int, int]] = deque(maxlen=RATE_WINDOW_MIN)

    def update(self, u: float, n_total: int | None = None, n_bad: int | None = None) -> dict:
        binom = False
        if self.is_rate:  # rate series: smooth over a 5-minute count window, then test it binomially
            self.win.append((int(n_total or 0), int(n_bad or 0)))
            nt = sum(a for a, _ in self.win)
            nb = sum(b for _, b in self.win)
            frac = nb / nt if nt else 0.0
            p_bad = (1 - self.slo) if self.direction == "lower_bad" else self.slo
            u = frac / p_bad
            binom = binom_alarm(nb, nt, p_bad)
        z = self.z.update(u)
        self.holt.update(u)
        z_ok = self.pers.update(z >= 4)
        return {
            "u": u,
            "eta": self.holt.eta(),
            "pred": self.holt.predictive_trigger(),
            "z": z if z_ok else min(z, 2.0),
            # On rate series the band alone is noise at low volume (Review Focus #1): require significance.
            "band": binom if self.is_rate else u >= CRITICAL_U,
            "binom": binom,
        }


def abnormal_kind(key: SeriesKey, sig: dict) -> str | None:
    _svc, metric, seg = key
    hot = sig["u"] >= 0.75 or sig["z"] >= 3 or sig["binom"]
    if not hot:
        return None
    if seg != "*" or metric in ("issuer_timeout_rate", "payment_success_rate", "otp_delivery_rate"):
        return "segment" if sig["binom"] else None
    if metric == "latency_p99":
        return "latency"
    if metric == "error_rate":
        return "errors"
    return "other"


@dataclass
class Corroboration:
    """Last time each (service, kind) was abnormal; corroboration = share of 5 kinds seen within 5 min."""

    topo: Topology

    def __post_init__(self) -> None:
        self.last: dict[tuple[str, str], int] = {}

    def mark(self, svc: str, kind: str, t: int) -> None:
        self.last[(svc, kind)] = t

    def score(self, svc: str, t: int) -> float:
        def seen(s: str, k: str) -> bool:
            return t - self.last.get((s, k), -(10**9)) <= CORROB_WINDOW_MIN

        hits = sum(seen(svc, k) for k in ("latency", "errors", "segment", "logs"))
        deps = self.topo.dependants(svc)
        hits += any(seen(d, k) for d in deps for k in ("latency", "errors", "other", "segment"))
        return hits / len(CORROB_KINDS)


def fires(config: str, key: SeriesKey, sig: dict, r: float, tau: float, infra: bool) -> bool:
    if config == "B0":
        return infra and sig["u"] >= 1.0
    if config == "B1":
        return infra and sig["u"] >= CRITICAL_U
    if config == "S1":
        return infra and (sig["pred"] or sig["band"])
    return r >= tau


class Emitter:
    """One open candidate per series; close after CLEAR_MIN quiet minutes; then COOLDOWN_MIN before re-opening."""

    def __init__(self) -> None:
        self.open: dict[SeriesKey, int] = {}  # key → last firing minute
        self.cool_until: dict[SeriesKey, int] = {}

    def update(self, key: SeriesKey, firing: bool, t: int) -> bool:
        """Returns True when a new candidate opens at minute t."""
        if key in self.open:
            if firing:
                self.open[key] = t
            elif t - self.open[key] >= CLEAR_MIN:
                del self.open[key]
                self.cool_until[key] = t + COOLDOWN_MIN
            return False
        if firing and t >= self.cool_until.get(key, -1):
            self.open[key] = t
            return True
        return False


class DetectorEngine:
    """Live driver. Call `step(ts, points)` once per minute (or per envelope) with that minute's points."""

    def __init__(self, config: str = "S2", tau: float = 0.5, topo: Topology | None = None) -> None:
        assert config in CONFIGS
        self.config, self.tau = config, tau
        self.topo = topo or Topology.load()
        self.states: dict[SeriesKey, SeriesState] = {}
        self.corrob = Corroboration(self.topo)
        self.emitter = Emitter()
        self.t0: datetime | None = None
        self.last_signal: dict[SeriesKey, dict] = {}

    def _minute(self, ts: datetime) -> int:
        if self.t0 is None:
            self.t0 = ts
        return int((ts - self.t0) / timedelta(minutes=1))

    def state(self, key: SeriesKey, direction: str, slo: float, is_rate: bool) -> SeriesState:
        if key not in self.states:
            self.states[key] = SeriesState(key, is_rate, direction, slo)
        return self.states[key]

    def step(self, ts: datetime, points: list[dict], log_services: set[str] = frozenset()) -> list[Candidate]:
        t = self._minute(ts)
        for svc in log_services:
            self.corrob.mark(svc, "logs", t)
        sigs = {}
        for p in points:
            key = (p["service"], p["metric"], p.get("segment_key", "*"))
            is_rate = p.get("n_total") is not None
            st = self.state(key, p["direction"], p["threshold"], is_rate)
            u = p["u"] if "u" in p else _u(p)
            sig = st.update(u, p.get("n_total"), p.get("n_bad"))
            sigs[key] = (sig, not is_rate)
            kind = abnormal_kind(key, sig)
            if kind:
                self.corrob.mark(key[0], kind, t)
        out = []
        for key, (sig, infra) in sigs.items():
            sig["corrob"] = self.corrob.score(key[0], t)
            r = risk(
                pred=sig["pred"],
                eta=sig["eta"],
                z=sig["z"],
                corrob=sig["corrob"],
                band=sig["band"],
                binom=sig["binom"],
            )
            sig["risk"] = r
            self.last_signal[key] = sig
            if self.emitter.update(key, fires(self.config, key, sig, r, self.tau, infra), t):
                out.append(_candidate(ts, key, sig))
        return out


def _u(p: dict) -> float:
    from sentinel.schemas import utilisation

    return utilisation(p["value"], p["threshold"], p["direction"])


def _candidate(ts: datetime, key: SeriesKey, sig: dict) -> Candidate:
    triggers = [n for n in ("pred", "band", "binom") if sig[n]] + (["z"] if sig["z"] >= 4 else [])
    return Candidate(
        ts=ts,
        service=key[0],
        metric=key[1],
        segment_key=key[2],
        u=round(sig["u"], 4),
        eta_minutes=None if sig["eta"] is None else round(sig["eta"], 1),
        z=round(sig["z"], 2),
        corroboration=round(sig["corrob"], 2),
        band=sig["band"],
        binom=sig["binom"],
        predictive=sig["pred"],
        risk=round(sig["risk"], 3),
        triggers=triggers,
    )


# ---------------------------------------------------------------------------------------------------------
# Evaluation driver: record signals for every series and minute, then emit per config / τ from the arrays.


@dataclass
class Signals:
    index: list[datetime]
    keys: list[SeriesKey]
    infra: np.ndarray  # bool per key
    u: np.ndarray  # [keys, minutes]
    risk: np.ndarray
    pred: np.ndarray
    band: np.ndarray
    eta: np.ndarray  # nan when None
    z: np.ndarray | None = None
    corrob: np.ndarray | None = None
    binom: np.ndarray | None = None


def compute_signals(ds, start: datetime, end: datetime, warmup_min: int = 180) -> Signals:
    """Run the detector over [start − warmup, end) of a generated dataset. Signals before `start` are dropped."""
    from sentinel.datagen.generator import INFRA_METRICS

    topo = Topology.load()
    i0 = max(0, ds.loc(start) - warmup_min)
    i1 = min(len(ds.index), ds.loc(end))
    keys = list(ds.series)
    states = {
        k: SeriesState(k, ds.series[k].n_total is not None, ds.series[k].direction, ds.series[k].threshold)
        for k in keys
    }
    corrob = Corroboration(topo)
    logs_by_min: dict[int, set[str]] = {}
    for r in ds.logs.itertuples():
        logs_by_min.setdefault(ds.loc(r.ts), set()).add(r.service)
    n_keep = i1 - ds.loc(start)
    shape = (len(keys), n_keep)
    U, R, P, B, E = (
        np.zeros(shape),
        np.zeros(shape),
        np.zeros(shape, bool),
        np.zeros(shape, bool),
        np.full(shape, np.nan),
    )
    Z, C, BN = np.zeros(shape), np.zeros(shape), np.zeros(shape, bool)
    keep0 = ds.loc(start)
    for i in range(i0, i1):
        for svc in logs_by_min.get(i, ()):
            corrob.mark(svc, "logs", i)
        sigs = []
        for k in keys:
            s = ds.series[k]
            sig = states[k].update(
                float(s.u[i]),
                None if s.n_total is None else int(s.n_total[i]),
                None if s.n_bad is None else int(s.n_bad[i]),
            )
            kind = abnormal_kind(k, sig)
            if kind:
                corrob.mark(k[0], kind, i)
            sigs.append(sig)
        if i < keep0:
            continue
        j = i - keep0
        for a, (k, sig) in enumerate(zip(keys, sigs)):
            c = corrob.score(k[0], i)
            U[a, j] = sig["u"]
            R[a, j] = risk(
                pred=sig["pred"], eta=sig["eta"], z=sig["z"], corrob=c, band=sig["band"], binom=sig["binom"]
            )
            P[a, j] = sig["pred"]
            B[a, j] = sig["band"]
            Z[a, j], C[a, j], BN[a, j] = sig["z"], c, sig["binom"]
            if sig["eta"] is not None:
                E[a, j] = sig["eta"]
    infra = np.array([k[2] == "*" and k[1] in INFRA_METRICS for k in keys])
    return Signals(list(ds.index[keep0:i1].to_pydatetime()), keys, infra, U, R, P, B, E, Z, C, BN)


def emit(sig: Signals, config: str, tau: float = 0.5) -> list[dict]:
    """Alerts (candidate opens) for a config from recorded signals: [{ts, service, metric, segment, risk, eta}]."""
    if config == "B0":
        firing = sig.infra[:, None] & (sig.u >= 1.0)
    elif config == "B1":
        firing = sig.infra[:, None] & (sig.u >= CRITICAL_U)
    elif config == "S1":
        firing = sig.infra[:, None] & (sig.pred | sig.band)
    else:
        firing = sig.risk >= tau
    alerts = []
    for a, k in enumerate(sig.keys):
        row = firing[a]
        if not row.any():
            continue
        em = Emitter()
        for j in range(len(row)):
            if em.update(k, bool(row[j]), j):
                eta = sig.eta[a, j]
                alerts.append(
                    {
                        "ts": sig.index[j],
                        "service": k[0],
                        "metric": k[1],
                        "segment": k[2],
                        "risk": float(sig.risk[a, j]),
                        "eta": None if np.isnan(eta) else float(eta),
                    }
                )
    alerts.sort(key=lambda x: x["ts"])
    return alerts
