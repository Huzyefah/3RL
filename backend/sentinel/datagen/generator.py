"""Synthetic NovaPay telemetry, `ps02` mode (FINAL_PLAN §5).

All 500 PS-02 rows are pinned at their minute in u-space (value and threshold kept, so each row keeps its band).
Dense 1-minute series are generated between anchors; every CRITICAL row becomes an incident episode or a hard
negative from backend/data/ps02_episode_map.yaml. Outside episodes the background stays below u = 0.93, so the
95% rule (B1) fires exactly once per CRITICAL row, like on the CSV.

    uv run python -m sentinel.datagen.generator --summary
"""

from __future__ import annotations

import argparse
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import cache

import numpy as np
import pandas as pd
from scipy.signal import lfilter

from sentinel.datagen.calendar import load_profile, static_events, tps_multiplier
from sentinel.datagen.episodes import Episode, load_map
from sentinel.eval.csv_bench import load_ps02
from sentinel.schemas import CRITICAL_U, utilisation
from sentinel.topology import Topology

START = datetime(2026, 8, 1)
END = datetime(2026, 8, 31, 1, 0)  # covers the last anchor's episode
DEFAULT_SEED = 7
PLATFORM_TPS = 150.0
AVG_TICKET_PKR = 3200.0
BANK_WEIGHTS = {"BANK_A": 0.3, "BANK_B": 0.25, "BANK_C": 0.2, "BANK_D": 0.15, "BANK_E": 0.1}
OTP_SHARE = {"P1": 0.9, "P2": 0.1}
INFRA_METRICS = [
    "cpu_usage",
    "memory_usage",
    "disk_io",
    "connection_pool",
    "queue_depth",
    "latency_p99",
    "error_rate",
]
LOAD_SENSITIVE = {"cpu_usage", "disk_io", "connection_pool", "queue_depth", "latency_p99"}
BACKGROUND_MAX = 0.85
OUTSIDE_EPISODE_MAX = 0.93
PRECURSOR_MAX = 0.947
PLATEAU = (0.951, 0.995)  # never reaches 1.0, like the CSV: static thresholds catch nothing
RECOVERY_MIN = 12

# Sympathetic metrics per root cause (corroboration for the detector), peak u below the alert band.
COUPLED = {
    "RC-BANK": ["latency_p99", "error_rate", "queue_depth"],
    "RC-DBPOOL": ["connection_pool", "latency_p99", "error_rate"],
    "RC-OTP-PROVIDER": ["latency_p99", "queue_depth", "error_rate"],
    "RC-QUEUE": ["queue_depth", "disk_io", "latency_p99"],
    "RC-MEMLEAK": ["memory_usage", "cpu_usage", "latency_p99"],
}
LOG_TEMPLATES = {
    "RC-BANK": ("ERROR", "IBFT {bank}: ISO8583 0210 RC=91 issuer unavailable"),
    "RC-DBPOOL": ("ERROR", "HikariPool-1 - Connection is not available, request timed out after 30000ms"),
    "RC-OTP-PROVIDER": ("WARN", "SMS P1 DLR timeout for msisdn 03xx-xxxx{n3}"),
    "RC-QUEUE": ("WARN", "consumer lag {lag} msgs on settlement-batch partition {p}"),
    "RC-MEMLEAK": ("WARN", "GC overhead: old gen {pct}% after full GC"),
    "N1": ("INFO", "traffic surge: rps x{mult} (campaign {name})"),
    "N3": ("INFO", "batch job {name} running rows={rows}"),
}

SeriesKey = tuple[str, str, str]  # (service, metric, segment_key)


@dataclass
class Series:
    service: str
    metric: str
    segment: str
    direction: str
    threshold: float
    u: np.ndarray
    thr: np.ndarray | None = None  # per-minute threshold where an anchor overrides the series default
    n_total: np.ndarray | None = None
    n_bad: np.ndarray | None = None

    def threshold_at(self, i: int) -> float:
        return float(self.thr[i]) if self.thr is not None and not np.isnan(self.thr[i]) else self.threshold

    def value_at(self, i: int) -> float:
        if self.n_total is not None:
            frac = self.n_bad[i] / max(self.n_total[i], 1)
            return float(1 - frac) if self.direction == "lower_bad" else float(frac)
        return float(self.u[i] * self.threshold_at(i))


@dataclass
class Dataset:
    mode: str
    seed: int
    index: pd.DatetimeIndex
    series: dict[SeriesKey, Series]
    episodes: list[Episode]
    events: pd.DataFrame
    logs: pd.DataFrame
    tps: dict[str, np.ndarray] = field(default_factory=dict)  # per bank, payments/s

    def loc(self, ts: datetime) -> int:
        return int((pd.Timestamp(ts).floor("min") - self.index[0]) / pd.Timedelta(minutes=1))

    @property
    def ground_truth(self) -> pd.DataFrame:
        rows = []
        for e in self.episodes:
            rows.append(
                {
                    "id": e.id,
                    "kind": e.kind,
                    "code": e.code,
                    "service": e.service,
                    "metric": e.metric,
                    "segment": e.segment,
                    "abrupt": e.abrupt,
                    "precursor_start": e.precursor_start,
                    "onset": e.onset,
                    "end": e.end,
                    "cascade_root": e.cascade_root,
                    "confounders": ",".join(e.confounders),
                }
            )
        return pd.DataFrame(rows)

    def gmv_pkr_per_min(self, bank: str) -> np.ndarray:
        return self.tps[bank] * 60 * AVG_TICKET_PKR


def _rng(seed: int, *key: str) -> np.random.Generator:
    return np.random.default_rng([seed, zlib.crc32("|".join(key).encode())])


def _ar1(rng: np.random.Generator, n: int, phi: float = 0.9, sigma: float = 0.012) -> np.ndarray:
    return lfilter([1.0], [1.0, -phi], rng.normal(0, sigma, n))


def _shape(code: str, tau: np.ndarray) -> np.ndarray:
    """Precursor shape on τ ∈ [0, 1): linear leak, convex pool, step-then-creep bank, accelerating lag."""
    if code in ("RC-DBPOOL",):
        return tau**2
    if code == "RC-BANK":
        return np.where(tau > 0, 0.35 + 0.65 * tau, 0.0)
    if code == "RC-QUEUE":
        return tau**2.5
    return tau  # RC-MEMLEAK, RC-OTP-PROVIDER, N1, N6


def _ramp_into(
    u: np.ndarray, i0: int, i1: int, start: float, target: float, shape: np.ndarray, noise
) -> None:
    if i1 <= i0:
        return
    u[i0:i1] = np.minimum(start + (target - start) * shape + noise[: i1 - i0], PRECURSOR_MAX)


def build(mode: str = "ps02", seed: int = DEFAULT_SEED) -> Dataset:
    if mode != "ps02":
        raise NotImplementedError("seeded mode arrives in phase 8e")
    return _build_ps02(seed)


@cache
def _build_ps02(seed: int) -> Dataset:
    index = pd.date_range(START, END, freq="min", inclusive="left")
    n = len(index)
    topo = Topology.load()
    csv = load_ps02()
    episodes = load_map()
    profile = load_profile(index)
    calmult = tps_multiplier(index)
    load = profile * (1 + 0.12 * (calmult - 1))

    # ---- background infra series -------------------------------------------------------------------------
    series: dict[SeriesKey, Series] = {}
    for svc in topo.services:
        for metric in INFRA_METRICS:
            rows = csv[(csv.service_name == svc) & (csv.metric_type == metric)]
            rng = _rng(seed, svc, metric)
            base = rng.uniform(0.35, 0.55)
            mod = 0.75 + 0.25 * load if metric in LOAD_SENSITIVE else np.ones(n)
            u = np.clip(base * mod + _ar1(rng, n), 0.05, BACKGROUND_MAX)
            thr = float(rows.threshold.median()) if len(rows) else 100.0
            series[(svc, metric, "*")] = Series(
                svc, metric, "*", "higher_bad", thr, u, thr=np.full(n, np.nan)
            )

    # ---- non-critical anchors: smooth bumps so the dense series pass through them ------------------------
    t = np.arange(n)
    for r in csv[csv.alert_level != "CRITICAL"].itertuples():
        s = series[(r.service_name, r.metric_type, "*")]
        m = _loc(index, r.timestamp)
        # Wide, gentle bumps: WARNING rows are wobbles toward the band, not incident-like ramps.
        lo, hi = max(0, m - 30), min(n, m + 31)
        w = np.exp(-((t[lo:hi] - m) ** 2) / (2 * 10.0**2))
        s.u[lo:hi] = s.u[lo:hi] + (r.u - s.u[m]) * w

    # ---- segment rate series (binomial counts) -----------------------------------------------------------
    tps_platform = PLATFORM_TPS * profile * calmult
    tps = {b: tps_platform * w for b, w in BANK_WEIGHTS.items()}
    p_timeout = {b: np.full(n, 0.004) for b in BANK_WEIGHTS}
    p_otp_fail = {p: np.full(n, 0.01) for p in OTP_SHARE}

    events: list[dict] = static_events(START, END)
    logs: list[dict] = []
    episode_mask: dict[SeriesKey, np.ndarray] = {k: np.zeros(n, bool) for k in series}

    for ep in episodes:
        rng = _rng(seed, ep.id)
        key = (ep.service, ep.metric, "*")
        s = series[key]
        i_on = _loc(index, ep.onset)
        i_pre = max(0, i_on - ep.lead_min)
        i_end = min(n, i_on + ep.duration_min + 1)
        i_rec = min(n, i_end + RECOVERY_MIN)
        episode_mask[key][i_pre:i_rec] = True
        noise = rng.normal(0, 0.006, max(1, i_on - i_pre))
        start_u = float(s.u[i_pre])

        if ep.kind == "incident":
            if not ep.abrupt:
                tau = np.linspace(0, 1, i_on - i_pre, endpoint=False)
                _ramp_into(s.u, i_pre, i_on, start_u, 0.94, _shape(ep.code, tau), noise)
            s.u[i_on:i_end] = np.clip(ep.u + rng.normal(0, 0.008, i_end - i_on), *PLATEAU)
            _recover(s.u, i_end, i_rec, start_u)
            if not ep.abrupt:
                _sympathetic(series, topo, ep, i_pre, i_on, i_end, i_rec, rng, episode_mask)
                _segment_precursor(ep, i_pre, i_on, i_end, i_rec, p_timeout, p_otp_fail)
            _episode_logs(logs, ep, index, i_pre if not ep.abrupt else i_on, i_end, rng)
            if "deploy" in ep.confounders:
                ts = index[max(0, i_pre - int(rng.integers(5, 21)))].to_pydatetime()
                events.append(_change(ts, ep.service, rng, caused=True))
            if "surge" in ep.confounders:
                events.append(
                    _surge(index[i_pre].to_pydatetime() - timedelta(minutes=10), index[i_rec - 1], ep, rng)
                )
        else:
            if ep.code == "N5":  # transient spike, already recovering
                s.u[i_on] = ep.u
                s.u[i_on + 1 : i_on + 4] = [0.9, 0.82, 0.75]
            elif ep.code == "N6":  # unexplained excursion: short ramp, short plateau, no benign evidence
                tau = np.linspace(0, 1, i_on - i_pre, endpoint=False)
                _ramp_into(s.u, i_pre, i_on, start_u, 0.9, tau, noise)
                s.u[i_on:i_end] = np.clip(ep.u + rng.normal(0, 0.008, i_end - i_on), *PLATEAU)
                _recover(s.u, i_end, i_rec, start_u)
            elif ep.code == "N1":  # surge: ramps exactly like an incident, every signal rises together
                tau = np.linspace(0, 1, i_on - i_pre, endpoint=False)
                _ramp_into(s.u, i_pre, i_on, start_u, 0.94, tau, noise)
                s.u[i_on:i_end] = np.clip(ep.u + rng.normal(0, 0.008, i_end - i_on), *PLATEAU)
                _recover(s.u, i_end, i_rec, start_u)
                _sympathetic(
                    series, topo, ep, i_pre, i_on, i_end, i_rec, rng, episode_mask, every_metric=True
                )
                events.append(
                    _surge(index[i_pre].to_pydatetime() - timedelta(minutes=10), index[i_rec - 1], ep, rng)
                )
            elif ep.code == "N3":  # scheduled batch: fast rise to a plateau at a known start
                tau = np.linspace(0, 1, i_on - i_pre, endpoint=False)
                _ramp_into(s.u, i_pre, i_on, start_u, 0.93, np.sqrt(tau), noise)
                s.u[i_on:i_end] = np.clip(ep.u + rng.normal(0, 0.004, i_end - i_on), *PLATEAU)
                _recover(s.u, i_end, min(n, i_end + 3), start_u)
                name = f"{ep.service.lower()}_{ep.metric}_batch"
                events.append(
                    {
                        "ts": index[i_pre].to_pydatetime(),
                        "end": index[i_end - 1].to_pydatetime(),
                        "kind": "cron",
                        "service": ep.service,
                        "name": name,
                        "attributes": {"note": f"Scheduled job {name}"},
                        "caused": False,
                    }
                )
            _episode_logs(logs, ep, index, i_pre, i_end, rng)

    # Benign deploys (about one a day) so "there was a deploy" is never a free pass.
    rng = _rng(seed, "deploys")
    for d in range(30):
        ts = START + timedelta(days=d, hours=int(rng.integers(9, 19)), minutes=int(rng.integers(0, 60)))
        events.append(_change(ts, str(rng.choice(list(topo.services))), rng, caused=False))

    # ---- clamp outside episodes, then pin all 500 anchors in u-space ------------------------------------
    for k, s in series.items():
        outside = ~episode_mask[k]
        s.u[outside] = np.minimum(s.u[outside], OUTSIDE_EPISODE_MAX)
    for r in csv.itertuples():
        s = series[(r.service_name, r.metric_type, "*")]
        m = _loc(index, r.timestamp)
        s.u[m] = r.u
        s.thr[m] = r.threshold

    _add_rate_series(series, seed, n, tps, p_timeout, p_otp_fail, profile, calmult)
    return Dataset(
        mode="ps02",
        seed=seed,
        index=index,
        series=series,
        episodes=episodes,
        events=pd.DataFrame(events).sort_values("ts", ignore_index=True),
        logs=pd.DataFrame(
            logs, columns=["ts", "service", "level", "template", "message", "count", "episode_id"]
        ),
        tps=tps,
    )


def _loc(index: pd.DatetimeIndex, ts) -> int:
    return int((pd.Timestamp(ts).floor("min") - index[0]) / pd.Timedelta(minutes=1))


def _recover(u: np.ndarray, i0: int, i1: int, to: float) -> None:
    if i1 > i0:
        u[i0:i1] = np.linspace(min(u[i0 - 1], 0.93), to, i1 - i0)


def _sympathetic(series, topo, ep, i_pre, i_on, i_end, i_rec, rng, mask, every_metric: bool = False) -> None:
    """Coupled golden signals on the same service (lag 3–10 min) and dependants (lag 5–15 min), below the band."""
    metrics = INFRA_METRICS if every_metric else COUPLED[ep.code]
    targets = [
        (ep.service, m, int(rng.integers(3, 11)), rng.uniform(0.78, 0.88)) for m in metrics if m != ep.metric
    ]
    targets += [
        (d, "latency_p99", int(rng.integers(5, 16)), rng.uniform(0.75, 0.84))
        for d in topo.dependants(ep.service)
    ]
    for svc, metric, lag, peak in targets:
        s = series[(svc, metric, "*")]
        a = min(i_pre + lag, i_on - 1)
        if a < i_on:
            s.u[a:i_on] = np.maximum(s.u[a:i_on], np.linspace(s.u[a], peak, i_on - a) + rng.normal(0, 0.01, i_on - a))
        s.u[i_on:i_end] = np.maximum(s.u[i_on:i_end], peak + rng.normal(0, 0.01, i_end - i_on))
        if i_rec > i_end:
            s.u[i_end:i_rec] = np.maximum(s.u[i_end:i_rec], np.linspace(peak, s.u[i_rec - 1], i_rec - i_end))
        s.u[a:i_rec] = np.minimum(s.u[a:i_rec], 0.9)
        mask[(svc, metric, "*")][a:i_rec] = True


def _segment_precursor(ep, i_pre, i_on, i_end, i_rec, p_timeout, p_otp_fail) -> None:
    """RC-BANK: one bank's issuer timeouts climb before the infra anchor breaches; RC-OTP: P1 delivery falls."""
    tau = np.linspace(0, 1, max(1, i_on - i_pre), endpoint=False)
    if ep.code == "RC-BANK":
        p = p_timeout[ep.segment.split("=")[1]]
        p[i_pre:i_on] = 0.004 + (0.03 - 0.004) * _shape("RC-BANK", tau)[: i_on - i_pre]
        p[i_on:i_end] = 0.05
        p[i_end:i_rec] = np.linspace(0.05, 0.004, i_rec - i_end)
    elif ep.code == "RC-OTP-PROVIDER":
        p = p_otp_fail["P1"]
        p[i_pre:i_on] = 0.01 + (0.07 - 0.01) * tau[: i_on - i_pre]
        p[i_on:i_end] = 0.12
        p[i_end:i_rec] = np.linspace(0.12, 0.01, i_rec - i_end)


def _add_rate_series(series, seed, n, tps, p_timeout, p_otp_fail, profile, calmult) -> None:
    rng = _rng(seed, "rates")
    for bank in BANK_WEIGHTS:
        n_tot = rng.poisson(tps[bank] * 60)
        n_to = rng.binomial(n_tot, p_timeout[bank])
        n_fail = n_to + rng.binomial(n_tot - n_to, 0.006)
        seg = f"bank={bank}"
        series[("PaymentGateway", "issuer_timeout_rate", seg)] = _rate(
            "PaymentGateway", "issuer_timeout_rate", seg, "higher_bad", 0.02, n_tot, n_to
        )
        series[("PaymentGateway", "payment_success_rate", seg)] = _rate(
            "PaymentGateway", "payment_success_rate", seg, "lower_bad", 0.97, n_tot, n_fail
        )
    otp_volume = 300 * profile * calmult
    for prov, share in OTP_SHARE.items():
        n_tot = rng.poisson(otp_volume * share)
        n_bad = rng.binomial(n_tot, p_otp_fail[prov])
        seg = f"provider={prov}"
        series[("NotificationHub", "otp_delivery_rate", seg)] = _rate(
            "NotificationHub", "otp_delivery_rate", seg, "lower_bad", 0.95, n_tot, n_bad
        )
    n_tot = rng.poisson(600 * profile * calmult)
    series[("AuthService", "login_failure_rate", "*")] = _rate(
        "AuthService", "login_failure_rate", "*", "higher_bad", 0.08, n_tot, rng.binomial(n_tot, 0.03)
    )


def _rate(svc, metric, seg, direction, slo, n_tot, n_bad) -> Series:
    frac = n_bad / np.maximum(n_tot, 1)
    value = 1 - frac if direction == "lower_bad" else frac
    u = utilisation(value, slo, direction)  # vectorised: same formula as schemas.utilisation
    return Series(svc, metric, seg, direction, slo, u, n_total=n_tot, n_bad=n_bad)


def _change(ts: datetime, service: str, rng, caused: bool) -> dict:
    ver = f"v2026.08.{int(rng.integers(1, 99)):02d}"
    return {
        "ts": ts,
        "end": ts + timedelta(minutes=5),
        "kind": "change",
        "service": service,
        "name": f"deploy {service} {ver}",
        "attributes": {"version": ver, "author": "ci-bot"},
        "caused": caused,  # ground truth only; tools never expose it
    }


def _surge(ts: datetime, end, ep: Episode, rng) -> dict:
    name = str(
        rng.choice(
            ["NovaPay cashback week", "Bill-pay weekend", "Merchant QR promo", "Mobile top-up blitz"]
        )
    )
    return {
        "ts": ts,
        "end": pd.Timestamp(end).to_pydatetime(),
        "kind": "calendar",
        "service": ep.service,
        "name": f"campaign: {name}",
        "attributes": {"tps_multiplier": 1.8, "note": "Marketing campaign traffic surge"},
        "caused": False,
    }


def _episode_logs(logs: list, ep: Episode, index, i0: int, i1: int, rng) -> None:
    if ep.code not in LOG_TEMPLATES or (ep.kind == "incident" and ep.abrupt and i1 - i0 < 1):
        return
    level, tpl = LOG_TEMPLATES[ep.code]
    span = max(1, i1 - i0)
    for k, i in enumerate(range(i0, i1)):
        count = int(1 + 40 * (k + 1) / span)
        msg = tpl.format(
            bank=ep.segment.split("=")[-1],
            n3=f"{int(rng.integers(0, 1000)):03d}",
            lag=int(20000 + 3000 * k),
            p=int(rng.integers(0, 12)),
            pct=min(99, 70 + k),
            mult=1.8,
            name=ep.service.lower(),
            rows=int(rng.integers(1e5, 9e5)),
        )
        logs.append(
            {
                "ts": index[i],
                "service": ep.service,
                "level": level,
                "template": tpl,
                "message": msg,
                "count": count,
                "episode_id": ep.id,
            }
        )


def alert_runs(u: np.ndarray, cut: float = CRITICAL_U, merge_gap: int = 10) -> list[tuple[int, int]]:
    """Contiguous minutes with u ≥ cut, merging gaps ≤ merge_gap (one alert episode each)."""
    idx = np.flatnonzero(u >= cut)
    if idx.size == 0:
        return []
    runs, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > merge_gap:
            runs.append((int(s), int(p)))
            s = i
        p = i
    runs.append((int(s), int(p)))
    return runs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()
    ds = build("ps02", args.seed)
    infra = [s for (svc, m, seg), s in ds.series.items() if seg == "*" and m in INFRA_METRICS]
    runs = sum(len(alert_runs(s.u)) for s in infra)
    print(
        f"minutes={len(ds.index)} series={len(ds.series)} episodes={len(ds.episodes)} B1-runs={runs} "
        f"events={len(ds.events)} log-rows={len(ds.logs)}"
    )


if __name__ == "__main__":
    main()
