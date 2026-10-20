"""Data generator (FP 5, FP 13 Task 2). ``build(mode, seed, window) -> Dataset``.

``ps02`` mode (the only mode until Phase 10):

1. **Background.** Every (service, PS-02 metric) series gets a low-noise diurnal ``u`` (shape from
   ``daily_tps_factor``, about 0.35-0.80, small uplift on high-traffic calendar days), capped at
   0.895 so the background never reaches 0.90.
2. **Anchors.** All 500 CSV rows are pinned verbatim (value, threshold, so ``u`` and band) at
   their timestamp floored to the minute, ``is_anchor=True``. Non-CRITICAL anchors get a smooth
   local bump so the dense series flows into them instead of jumping.
3. **Episodes.** Each of the 50 ``ps02_episode_map.yaml`` entries gets its shape
   (``precursor_shape`` for incidents, ``negative_shape`` for hard negatives) on the anchor
   series, reaching the anchor
   ``u`` exactly at onset, plus co-metrics (lagged latency), and for incidents a sympathetic ramp
   on dependants (``services.yaml``) 5-15 min later. Every non-anchor minute of the PS-02 series is
   capped at 0.945, so B1 (``u >= 0.95``) over the dense data finds exactly the 50 CSV CRITICAL
   minutes, each a one-minute run, and B0 (``u >= 1.0``) finds nothing (CSV max u is 0.996).
4. **Segment rate metrics** (``payment_success_rate``/``issuer_timeout_rate`` per bank,
   ``otp_delivery_rate`` per provider, ``login_failure_rate``) carry binomial ``n_total``/``n_bad``;
   RC-BANK, RC-OTP-PROVIDER and RC-AUTH-ATTACK degrade their segment. D3: filter B0/B1 input with
   ``metric in PS02_METRICS``.
5. **Logs** from episode templates (masked/fictional identifiers only), INFO heartbeats, and
   background WARN/ERROR noise reusing incident template ids (a few per service-day); N1/N6 and
   some N4/N5 also carry an incident-looking WARN precursor. **Events**: calendar occurrences,
   the map's N4 deploys, causing deploys before 25% of RC-DBPOOL/RC-MEMLEAK precursors, benign
   background deploys, and benign deploys before a seeded share of all other episodes (except
   N6). Every deploy has an opaque id and the same text, so ids never reveal a label.
6. **Anti-leakage (FP 1.4 F4).** Construction artifacts must not label episodes: "a WARN/ERROR
   log in the 3 h before onset", "rising for >= 20 min", "u at onset-15 > 0.6" and "a deploy
   in the 3 h before onset" each fire on a sizeable share of negatives (tested).
7. **Custom windows.** Episodes overlapping the window are kept whole in ``ground_truth``
   (unclipped times) and their in-window part is blended; those entirely outside are dropped.
8. **Segment volume floor.** A segment minute with ``n_total < MIN_SEGMENT_N`` (30) gets
   ``u = 0.0`` (neutral); ``value``/``n_total``/``n_bad`` stay as observed.
9. ``anchor_ts`` holds each anchor's original CSV timestamp with seconds ("" elsewhere).

Deterministic given ``seed``: each series and episode draws from its own
``default_rng([seed, ...])``.
``build`` caches results in-process by ``(mode, seed, window)``; treat a cached ``Dataset`` as
read-only (pass ``use_cache=False`` for a private copy).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
from scipy.signal import lfilter

from sentinel.calendar import CalendarEvent, load_calendar
from sentinel.datagen import episode_map
from sentinel.datagen.episodes import (
    NOISE_TEMPLATES,
    LogTemplate,
    daily_tps_factor,
    deploy_event_id,
    deploy_text,
    negative_shape,
    precursor_shape,
    render_log,
)
from sentinel.datagen.types import (
    EVENT_COLUMNS,
    LOG_COLUMNS,
    METRIC_COLUMNS,
    Dataset,
    EpisodeAssignment,
    GroundTruthEpisode,
    Mode,
)
from sentinel.topology import Topology
from sentinel.utilisation import Direction, utilisation

CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "ps02_system_telemetry.csv"
PS02_METRIC_ORDER: tuple[str, ...] = (
    "cpu_usage",
    "memory_usage",
    "disk_io",
    "connection_pool",
    "queue_depth",
    "latency_p99",
    "error_rate",
)
PS02_METRICS = frozenset(PS02_METRIC_ORDER)
DEFAULT_WINDOW = (datetime(2026, 8, 1, 0, 0), datetime(2026, 8, 30, 23, 59))
SOURCE = "ps02_replay"

BACKGROUND_CAP = 0.895  # background never reaches 0.90 (FP 5)
NON_ANCHOR_CAP = 0.945  # no generated minute is CRITICAL; only CSV anchors are
# A segment minute with fewer transactions than this carries the neutral u = 0.0 (no budget used):
# the rate is too noisy to mean anything, matching the binomial detector's n_total >= 30 rule
# (FP 6). value / n_total / n_bad stay as observed.
MIN_SEGMENT_N = 30
NOISE_LOGS_PER_SERVICE_DAY = 3.0  # Poisson mean of background WARN/ERROR lines (FP 1.4 F4)
NEARBY_DEPLOY_P = 0.35  # share of episodes given a benign deploy in the 3 h before onset
_GENERIC_NOISE_CODES = ("RC-DBPOOL", "RC-MEMLEAK", "RC-QUEUE", "RC-ABRUPT")
_SLOW_METRICS = ("memory_usage", "disk_io")  # weakly diurnal

# Segment volumes (transactions per minute at daily factor 1.0) and healthy bad-probabilities.
# Sized so that, outside episodes, fewer than 0.5% of segment minutes with n_total >= 30 breach
# (u >= 1) by binomial noise alone; the smallest bank still dips under MIN_SEGMENT_N at night.
_BANK_VOLUME = {"BANK_A": 600.0, "BANK_B": 450.0, "BANK_C": 300.0, "BANK_D": 200.0, "BANK_E": 125.0}
_PROVIDER_VOLUME = {"P1": 400.0, "P2": 200.0}
_LOGIN_VOLUME = 750.0
_P_HEALTHY = {
    "issuer_timeout_rate": 0.001,
    "payment_other_fail": 0.001,
    "otp_delivery_rate": 0.004,
    "login_failure_rate": 0.02,
}
_P_PEAK = {"issuer_timeout_rate": 0.08, "otp_delivery_rate": 0.15, "login_failure_rate": 0.35}
_SEGMENT_FOR_CODE = {
    "RC-BANK": "issuer_timeout_rate",
    "RC-OTP-PROVIDER": "otp_delivery_rate",
    "RC-AUTH-ATTACK": "login_failure_rate",
    "N2": "issuer_timeout_rate",
}
_CAL_KIND = {
    "salary_day": "campaign",
    "campaign": "campaign",
    "maintenance": "maintenance",
    "eod_settlement": "cron",
}


def build(
    mode: Mode = "ps02",
    seed: int = 0,
    window: tuple[datetime, datetime] | None = None,
    *,
    use_cache: bool = True,
) -> Dataset:
    """Build the dataset. ``window`` defaults to Aug 1-30 2026 (inclusive, 1-minute resolution).

    Cached by ``(mode, seed, window)`` unless ``use_cache=False``; do not mutate a cached result.
    ``mode='seeded'`` arrives in Phase 10 and raises ``NotImplementedError`` for now.
    """
    win = window or DEFAULT_WINDOW
    if use_cache:
        return _cached(mode, seed, win)
    return _build(mode, seed, win)


@lru_cache(maxsize=4)
def _cached(mode: Mode, seed: int, window: tuple[datetime, datetime]) -> Dataset:
    return _build(mode, seed, window)


def _build(mode: Mode, seed: int, window: tuple[datetime, datetime]) -> Dataset:
    if mode == "seeded":
        raise NotImplementedError("seeded mode lands in Phase 10")
    if mode != "ps02":
        raise ValueError(f"unknown mode {mode!r}")
    return _Ps02Builder(seed, window).run()


# --- implementation ----------------------------------------------------------------------------


class _Ps02Builder:
    def __init__(self, seed: int, window: tuple[datetime, datetime]) -> None:
        self.seed = seed
        self.t0 = window[0].replace(second=0, microsecond=0)
        self.t1 = window[1].replace(second=0, microsecond=0)
        self.window = (self.t0, self.t1)
        self.T = self._idx(self.t1) + 1
        self.minutes = np.datetime64(self.t0, "m") + np.arange(self.T).astype("timedelta64[m]")
        first = self.t0.replace(hour=0, minute=0)
        self.days = [
            first + timedelta(days=i) for i in range((self.t1.date() - self.t0.date()).days + 1)
        ]
        self.topo = Topology.from_yaml()
        self.cal = load_calendar()

        # series layout: PS-02 metric series first, then segment rate series
        self.services = list(self.topo.services)
        self.ps_keys = [(s, m) for s in self.services for m in PS02_METRIC_ORDER]
        self.ps_index = {k: i for i, k in enumerate(self.ps_keys)}
        self.seg_keys: list[tuple[str, str, str]] = []  # (service, metric, segment_key)
        for s, svc in self.topo.services.items():
            dims = list(svc.segments.items())
            for metric in svc.segment_metrics:
                if dims:
                    name, values = dims[0]
                    self.seg_keys += [(s, metric, f"{name}={v}") for v in values]
                else:
                    self.seg_keys.append((s, metric, "*"))
        self.seg_index = {k: i for i, k in enumerate(self.seg_keys)}

        self.base, self.mult = self._load_curves()
        self.u = np.zeros((len(self.ps_keys), self.T))
        self.is_anchor = np.zeros_like(self.u, dtype=bool)
        self.anchor_code = np.zeros(self.u.shape, dtype=np.int16)  # index into anchor_ts_cats
        self.anchor_ts_cats: list[str] = [""]
        self.cause: dict[str, datetime] = {}  # episode_id -> causing deploy ts
        self.value = np.zeros_like(self.u)
        self.threshold = np.array(
            [self.topo.services[s].metrics[m].threshold for s, m in self.ps_keys]
        )[:, None].repeat(self.T, axis=1)
        self.seg_p: dict[tuple[str, str, str], np.ndarray] = {
            k: np.full(self.T, _P_HEALTHY[k[1]]) for k in self.seg_keys if k[1] in _P_HEALTHY
        }
        self.logs: list[tuple[datetime, str, str, str, str]] = []
        self.events: list[tuple[datetime, str, str, str, str]] = []
        self.ground_truth: list[GroundTruthEpisode] = []

    # -- helpers --------------------------------------------------------------------------------

    def _rng(self, *key: int) -> np.random.Generator:
        return np.random.default_rng([self.seed, *key])

    def _idx(self, ts: datetime) -> int:
        return int((ts - self.t0) // timedelta(minutes=1))

    def _in(self, ts: datetime) -> bool:
        return self.t0 <= ts <= self.t1

    def _load_curves(self) -> tuple[np.ndarray, np.ndarray]:
        """Daily TPS curve (no calendar) and the calendar multiplier, one value per minute."""
        day0 = datetime(2026, 1, 1)
        daily = np.array([daily_tps_factor(day0 + timedelta(minutes=i), []) for i in range(1440)])
        mod = (np.arange(self.T) + self.t0.hour * 60 + self.t0.minute) % 1440
        base = daily[mod]
        mult = np.ones(self.T)
        boosters = [e for e in self.cal if e.tps_multiplier > 1.0]
        if boosters:
            for i in range(self.T):
                ts = self.t0 + timedelta(minutes=i)
                active = [e.tps_multiplier for e in boosters if e.active_at(ts)]
                if active:
                    mult[i] = max(active)
        return base, mult

    def _blend(self, row: np.ndarray, start: int, profile: np.ndarray, target: float) -> None:
        """``row[start+i] = (1 - p_i) * row[start+i] + p_i * target`` within the window."""
        lo, hi = max(start, 0), min(start + len(profile), self.T)
        if lo >= hi:
            return
        p = profile[lo - start : hi - start]
        row[lo:hi] = (1.0 - p) * row[lo:hi] + p * target

    # -- stages ---------------------------------------------------------------------------------

    def run(self) -> Dataset:
        self._background()
        anchors = self._anchors()
        self._bumps(anchors)
        np.minimum(self.u, BACKGROUND_CAP, out=self.u)
        self._episodes(anchors)
        np.minimum(self.u, NON_ANCHOR_CAP, out=self.u)
        self._pin(anchors)
        self._calendar_events()
        self._map_events()
        self._deploys()
        self._heartbeat_logs()
        self._noise_logs()
        return Dataset(
            mode="ps02",
            seed=self.seed,
            window=self.window,
            metrics=self._metrics_frame(),
            logs=self._logs_frame(),
            events=self._events_frame(),
            ground_truth=sorted(self.ground_truth, key=lambda g: g.episode_id),
        )

    def _background(self) -> None:
        f = (self.base - self.base.min()) / (self.base.max() - self.base.min())
        uplift = 0.04 * (self.mult > 1.0)
        for j, (_s, m) in enumerate(self.ps_keys):
            rng = self._rng(1, j)
            lo, hi = rng.uniform(0.35, 0.48), rng.uniform(0.62, 0.76)
            w = 0.35 if m in _SLOW_METRICS else 1.0
            noise = lfilter([1.0], [1.0, -0.9], rng.normal(0.0, 0.006, self.T))
            self.u[j] = lo + (hi - lo) * (w * f + (1 - w) * 0.5) + uplift + noise
        np.clip(self.u, 0.05, BACKGROUND_CAP, out=self.u)

    def _anchors(self) -> pd.DataFrame:
        """In-window CSV rows; ``self.crit_u`` keeps every CRITICAL anchor's u, window or not."""
        d = pd.read_csv(CSV_PATH)
        ts = pd.to_datetime(d["timestamp"])
        d["minute"] = ts.dt.floor("min")
        d["anchor_ts"] = ts.dt.strftime("%Y-%m-%dT%H:%M:%S")
        d["u"] = [
            utilisation(float(v), float(t), "higher_bad")
            for v, t in zip(d["value"], d["threshold"], strict=True)
        ]
        crit = d[d["alert_level"] == "CRITICAL"]
        self.crit_u = {
            (m.to_pydatetime(), s, k): float(u)
            for m, s, k, u in zip(
                crit["minute"], crit["service_name"], crit["metric_type"], crit["u"], strict=True
            )
        }
        d = d[(d["minute"] >= pd.Timestamp(self.t0)) & (d["minute"] <= pd.Timestamp(self.t1))]
        d = d.assign(
            j=[
                self.ps_index[(s, m)]
                for s, m in zip(d["service_name"], d["metric_type"], strict=True)
            ],
            k=((d["minute"] - pd.Timestamp(self.t0)) // pd.Timedelta(minutes=1)).astype(int),
        )
        return d.reset_index(drop=True)

    def _bumps(self, anchors: pd.DataFrame) -> None:
        """Smooth local bumps so the dense series flows into each non-CRITICAL anchor."""
        rng = self._rng(4)
        nc = anchors[anchors["alert_level"] != "CRITICAL"]
        for j, k, ua in zip(nc["j"], nc["k"], nc["u"], strict=True):
            sigma = rng.uniform(5.0, 12.0)
            half = int(3 * sigma)
            lo, hi = max(k - half, 0), min(k + half + 1, self.T)
            d = np.arange(lo, hi) - k
            resid = float(ua) - self.u[j, k]
            self.u[j, lo:hi] += resid * np.exp(-0.5 * (d / sigma) ** 2)

    def _episodes(self, anchors: pd.DataFrame) -> None:
        """Every mapped episode that overlaps the window: the in-window part is blended (an onset
        outside a custom window still shapes the precursor or tail inside it) and its ground
        truth is kept with its full, unclipped times. Episodes entirely outside are dropped."""
        del anchors  # targets come from self.crit_u so out-of-window onsets still have one
        for a in episode_map.load_episode_map():
            onset = datetime.fromisoformat(a.onset_ts)
            self._episode(a, onset, self.crit_u[(onset, a.service, a.metric)])

    def _episode(self, a: EpisodeAssignment, onset: datetime, target: float) -> None:
        num = int(a.episode_id.split("-")[1])
        rng = self._rng(2, (0 if a.kind == "incident" else 100) + num)
        shape = (
            precursor_shape(a.code, rng) if a.kind == "incident" else negative_shape(a.code, rng)
        )
        profile = np.asarray(shape.u_offset, dtype=float)
        if a.kind == "incident":  # hold in WARNING after onset, then recover
            n_post = int(rng.integers(10, 31))
            profile = np.concatenate([profile, np.linspace(0.85, 0.0, n_post + 1)[:-1]])
        k = self._idx(onset)
        start = k - shape.onset_index
        tail = len(profile) - shape.onset_index - 1

        self._blend(self.u[self.ps_index[(a.service, a.metric)]], start, profile, target)
        max_lag = 0
        for m in shape.co_metrics:
            if m not in PS02_METRICS or m == a.metric:
                continue
            lag = shape.latency_lag_min if m == "latency_p99" else int(rng.integers(0, 3))
            max_lag = max(max_lag, lag)
            co_target = rng.uniform(0.86, 0.93)
            self._blend(self.u[self.ps_index[(a.service, m)]], start + lag, profile, co_target)
        if a.kind == "incident":
            lo, hi = shape.dependant_lag_min
            lag = int(rng.integers(lo, hi + 1))
            for dep in sorted(self.topo.dependants(a.service)):
                for m in ("latency_p99", "error_rate"):
                    tgt = rng.uniform(0.78, 0.86)
                    self._blend(self.u[self.ps_index[(dep, m)]], start + lag, profile, tgt)

        self._segment_effect(a, start, profile)
        bank, provider = _bank_provider(a.segment_key)
        for tpl in shape.log_templates:
            self._log(onset + timedelta(minutes=tpl.offset_min), a.service, tpl, bank, provider)

        precursor_start = onset - timedelta(minutes=shape.onset_index)
        end = onset + timedelta(minutes=max(tail + max_lag, 1))
        if precursor_start > self.t1 or end < self.t0:
            return  # entirely outside the window
        cause_id = None
        if "deploy" in shape.event_kinds and a.kind == "incident":
            ts = precursor_start - timedelta(minutes=int(rng.integers(5, 21)))
            cause_id = deploy_event_id(a.service, ts)
            self.cause[a.episode_id] = ts
            if self._in(ts):
                self.events.append((ts, "deploy", a.service, deploy_text(a.service, ts), cause_id))
        self.ground_truth.append(
            GroundTruthEpisode(
                episode_id=a.episode_id,
                kind=a.kind,
                code=a.code,
                service=a.service,
                segment_key=a.segment_key,
                precursor_start=precursor_start,
                onset=onset,
                end=end,
                abrupt=a.abrupt,
                anchor_ts=a.anchor_ts,
                cascade_parent=a.cascade_parent,
                benign_evidence=a.benign_evidence,
                cause_event_id=cause_id,
            )
        )

    def _segment_effect(self, a: EpisodeAssignment, start: int, profile: np.ndarray) -> None:
        metric = _SEGMENT_FOR_CODE.get(a.code)
        if metric is None:
            return
        keys = [k for k in self.seg_keys if k[0] == a.service and k[1] == metric]
        if not keys:
            return
        key = next((k for k in keys if k[2] == a.segment_key), keys[0])
        self._blend(self.seg_p[key], start, profile, _P_PEAK[metric])

    def _log(self, ts: datetime, service: str, tpl: LogTemplate, bank: str, provider: str) -> None:
        if self._in(ts):
            msg = render_log(tpl, bank=bank, provider=provider)
            self.logs.append((ts, service, tpl.level, tpl.template_id, msg))

    def _pin(self, anchors: pd.DataFrame) -> None:
        self.value = self.u * self.threshold
        j = anchors["j"].to_numpy()
        k = anchors["k"].to_numpy()
        self.value[j, k] = anchors["value"].to_numpy()
        self.threshold[j, k] = anchors["threshold"].to_numpy()
        self.u[j, k] = anchors["u"].to_numpy()
        self.is_anchor[j, k] = True
        self.anchor_ts_cats = ["", *sorted(set(anchors["anchor_ts"]))]
        pos = {t: i for i, t in enumerate(self.anchor_ts_cats)}
        self.anchor_code[j, k] = [pos[t] for t in anchors["anchor_ts"]]

    def _calendar_events(self) -> None:
        days = self.days
        for e in self.cal:
            kind = _CAL_KIND.get(e.kind, "campaign")
            svc = e.service or "*"
            if e.days_of_month is not None:
                for d in days:
                    if d.day in e.days_of_month:
                        self._cal_event(d, kind, svc, e, recurring=True)
            elif e.cron is not None:
                minute, hour = e.cron.split()[:2]
                for d in days:
                    self._cal_event(
                        d.replace(hour=int(hour), minute=int(minute)), kind, svc, e, True
                    )
            elif e.weekday is not None and e.start is not None:
                h, mi = (int(x) for x in e.start.split(":"))
                for d in days:
                    if d.weekday() == e.weekday:
                        self._cal_event(d.replace(hour=h, minute=mi), kind, svc, e, True)
            elif e.start is not None:
                self._cal_event(datetime.fromisoformat(e.start), kind, svc, e, recurring=False)

    def _cal_event(
        self, ts: datetime, kind: str, svc: str, e: CalendarEvent, recurring: bool
    ) -> None:
        if self._in(ts):
            eid = f"{e.id}_{ts:%Y%m%d}" if recurring else e.id
            self.events.append((ts, kind, svc, e.description, eid))

    def _map_events(self) -> None:
        for e in episode_map.events():
            ts = datetime.fromisoformat(e["ts"])
            if self._in(ts):
                self.events.append((ts, e["kind"], e["service"], e["text"], e["event_id"]))

    def _deploys(self) -> None:
        """Benign deploys, so "there was a deploy nearby" is never a free label (FP 1.4 F4).

        Background deploys land on random services in business hours; on top, a seeded
        ``NEARBY_DEPLOY_P`` share of episodes (incidents, abrupt ones included, and negatives)
        get a benign deploy 10-170 min before onset. The only exclusion zones are around a
        causing deploy (so the cause stays unambiguous) and N6 (which must have no evidence).
        All deploys share one id/text format (``deploy_event_id``/``deploy_text``).
        """
        busy: dict[str, list[tuple[datetime, datetime]]] = {}
        for g in self.ground_truth:
            if g.code == "N6":
                lo = g.precursor_start - timedelta(hours=3)
                busy.setdefault(g.service, []).append((lo, g.end))
            elif g.episode_id in self.cause:
                lo = self.cause[g.episode_id] - timedelta(hours=3)
                busy.setdefault(g.service, []).append((lo, g.end + timedelta(hours=1)))
        taken = {e[4] for e in self.events}

        def add(svc: str, ts: datetime) -> None:
            if not self._in(ts) or any(lo <= ts <= hi for lo, hi in busy.get(svc, [])):
                return
            eid = deploy_event_id(svc, ts)
            if eid not in taken:
                taken.add(eid)
                self.events.append((ts, "deploy", svc, deploy_text(svc, ts), eid))

        rng = self._rng(3)
        for d in self.days:
            for _ in range(int(rng.poisson(1.5))):
                svc = self.services[int(rng.integers(len(self.services)))]
                add(svc, d + timedelta(minutes=int(rng.integers(9 * 60, 18 * 60))))
        rng = self._rng(7)
        for g in sorted(self.ground_truth, key=lambda g: g.episode_id):
            hit = rng.random() < NEARBY_DEPLOY_P
            ts = g.onset - timedelta(minutes=int(rng.integers(10, 171)))
            if hit and g.code not in ("N4", "N6") and g.episode_id not in self.cause:
                add(g.service, ts)

    def _noise_logs(self) -> None:
        """Background WARN/ERROR lines reusing incident template ids at random minutes, a few
        per service-day (FP 1.4 F4), so "a WARN/ERROR log before onset" is not a label. Each
        service draws from the generic incident templates plus those of its mapped codes."""
        codes: dict[str, set[str]] = {s: set(_GENERIC_NOISE_CODES) for s in self.services}
        for a in episode_map.load_episode_map():
            if a.kind == "incident":
                codes[a.service].add(a.code)
        by_code: dict[str, set[str]] = {}
        for code in sorted({c for cs in codes.values() for c in cs}):
            tpls = precursor_shape(code, np.random.default_rng(0)).log_templates
            by_code[code] = {t.template_id for t in tpls}
        rng = self._rng(6)
        banks, providers = sorted(_BANK_VOLUME), sorted(_PROVIDER_VOLUME)
        for s in self.services:
            ids = set().union(*(by_code[c] for c in codes[s]))
            pool = [t for t in NOISE_TEMPLATES if t.template_id in ids]
            for d in self.days:
                for _ in range(int(rng.poisson(NOISE_LOGS_PER_SERVICE_DAY))):
                    tpl = pool[int(rng.integers(len(pool)))]
                    ts = d + timedelta(minutes=int(rng.integers(0, 1440)))
                    bank = banks[int(rng.integers(len(banks)))]
                    provider = providers[int(rng.integers(len(providers)))]
                    self._log(ts, s, tpl, bank, provider)

    def _heartbeat_logs(self) -> None:
        for i in range(0, self.T, 15):
            ts = self.t0 + timedelta(minutes=i)
            for s in self.services:
                self.logs.append((ts, s, "INFO", "health_ok", f"{s} health check OK"))

    # -- frames ---------------------------------------------------------------------------------

    def _segment_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
        S = len(self.seg_keys)
        n_total = np.zeros((S, self.T), dtype=np.int64)
        n_bad = np.zeros((S, self.T), dtype=np.int64)
        thr = np.zeros(S)
        dirs: list[str] = []
        load = self.base * self.mult
        rng = self._rng(5)
        for i, (svc, metric, _seg) in enumerate(self.seg_keys):
            spec = self.topo.services[svc].segment_metrics[metric]
            thr[i] = spec.threshold
            dirs.append(spec.direction)
        # one Poisson volume per segment (bank/provider/login), shared by its metrics
        volume: dict[tuple[str, str], np.ndarray] = {}
        for i, (svc, _metric, seg) in enumerate(self.seg_keys):
            vkey = (svc, seg)
            if vkey not in volume:
                name = seg.split("=")[1] if "=" in seg else ""
                mean = _BANK_VOLUME.get(name) or _PROVIDER_VOLUME.get(name) or _LOGIN_VOLUME
                volume[vkey] = rng.poisson(mean * load)
            n_total[i] = volume[vkey]
        timeouts: dict[str, np.ndarray] = {}
        for i, (svc, metric, seg) in enumerate(self.seg_keys):
            if metric == "issuer_timeout_rate":
                timeouts[seg] = rng.binomial(n_total[i], self.seg_p[(svc, metric, seg)])
                n_bad[i] = timeouts[seg]
        for i, (svc, metric, seg) in enumerate(self.seg_keys):
            if metric == "payment_success_rate":
                to = timeouts.get(seg, np.zeros(self.T, dtype=np.int64))
                other = rng.binomial(n_total[i] - to, _P_HEALTHY["payment_other_fail"])
                n_bad[i] = to + other
            elif metric in ("otp_delivery_rate", "login_failure_rate"):
                n_bad[i] = rng.binomial(n_total[i], self.seg_p[(svc, metric, seg)])
        lower = np.array([d == "lower_bad" for d in dirs])[:, None]
        frac = np.where(n_total > 0, n_bad / np.maximum(n_total, 1), 0.0)
        value = np.where(lower, 1.0 - frac, frac)
        u = np.empty_like(value)
        for i in range(S):  # utilisation() is elementwise for an array value and scalar threshold
            u[i] = utilisation(cast(float, value[i]), float(thr[i]), cast(Direction, dirs[i]))
        u[n_total < MIN_SEGMENT_N] = 0.0  # neutral below the volume floor (MIN_SEGMENT_N)
        return value, n_total, n_bad, u, dirs

    def _metrics_frame(self) -> pd.DataFrame:
        seg_value, seg_nt, seg_nb, seg_u, seg_dirs = self._segment_arrays()
        P, S, T = len(self.ps_keys), len(self.seg_keys), self.T
        n_series = P + S
        services = [s for s, _ in self.ps_keys] + [k[0] for k in self.seg_keys]
        metrics = [m for _, m in self.ps_keys] + [k[1] for k in self.seg_keys]
        segments = ["*"] * P + [k[2] for k in self.seg_keys]
        dirs = ["higher_bad"] * P + seg_dirs
        seg_thr = np.array(
            [self.topo.services[s].segment_metrics[m].threshold for s, m, _ in self.seg_keys]
        )[:, None].repeat(T, axis=1)

        def stack(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            return np.concatenate([a, b]).T.ravel()  # ts-major

        def cat(labels: list[str]) -> pd.Categorical:
            uniq = sorted(set(labels))
            codes = np.array([uniq.index(x) for x in labels], dtype=np.int16)
            return pd.Categorical.from_codes(np.tile(codes, T), categories=uniq)

        zeros = np.zeros((P, T), dtype=np.int64)
        return pd.DataFrame(
            {
                "ts": np.repeat(self.minutes.astype("datetime64[ns]"), n_series),
                "service": cat(services),
                "metric": cat(metrics),
                "segment_key": cat(segments),
                "value": stack(self.value, seg_value),
                "threshold": stack(self.threshold, seg_thr),
                "direction": cat(dirs),
                "n_total": stack(zeros, seg_nt),
                "n_bad": stack(zeros, seg_nb),
                "u": stack(self.u, seg_u),
                "is_anchor": stack(self.is_anchor, np.zeros((S, T), dtype=bool)),
                "anchor_ts": pd.Categorical.from_codes(
                    stack(self.anchor_code, np.zeros((S, T), dtype=np.int16)),
                    categories=self.anchor_ts_cats,
                ),
                "source": pd.Categorical.from_codes(
                    np.zeros(n_series * T, dtype=np.int8), categories=[SOURCE]
                ),
            },
            columns=METRIC_COLUMNS,
        )

    def _logs_frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.logs, columns=LOG_COLUMNS)
        df["ts"] = pd.to_datetime(df["ts"])
        return df.sort_values(["ts", "service", "template_id"], kind="stable").reset_index(
            drop=True
        )

    def _events_frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.events, columns=EVENT_COLUMNS)
        df["ts"] = pd.to_datetime(df["ts"])
        return df.sort_values(["ts", "event_id"], kind="stable").reset_index(drop=True)


def _bank_provider(segment_key: str) -> tuple[str, str]:
    bank, provider = "BANK_A", "P1"
    if segment_key.startswith("bank="):
        bank = segment_key.split("=", 1)[1]
    elif segment_key.startswith("provider="):
        provider = segment_key.split("=", 1)[1]
    return bank, provider
