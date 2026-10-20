"""Episode shape library for the data generator (FP 3.3, 3.4, 5). Pure, seeded, numpy only.

A :class:`Shape` describes one episode in **normalised utilisation space**: ``u_offset[i]`` is the
fraction of the way from the background ``u`` to the episode's target ``u`` at minute
``start + i``, where ``start = onset - onset_index``. The generator turns it into a series with

    u(t) = u_background(t) + u_offset[i] * (u_target - u_background(onset))

so ``u_offset[onset_index] == 1.0`` means the target (the CSV anchor's ``u``) is reached exactly at
onset. Incident shapes end at onset (``len == lead_minutes + 1``); what happens after onset is the
generator's business. Negative shapes may continue past onset (recovery, plateau) and so can be
longer. RC-CERT is the exception: its metrics stay flat (all zeros) and only its logs move.

Every function takes the ``numpy.random.Generator`` it draws from; nothing reads global state.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

import numpy as np

from sentinel.calendar import CalendarEvent, events_at

INCIDENT_CODES: tuple[str, ...] = (
    "RC-BANK",
    "RC-DBPOOL",
    "RC-OTP-PROVIDER",
    "RC-QUEUE",
    "RC-AUTH-ATTACK",
    "RC-MEMLEAK",
    "RC-CERT",
    "RC-ABRUPT",
)
NEGATIVE_CODES: tuple[str, ...] = ("N1", "N2", "N3", "N4", "N5", "N6")

# Precursor lead windows in minutes, inclusive (FP 3.3). RC-CERT has no metric precursor; its
# window is how far ahead of onset the novel log template first appears.
LEAD_WINDOWS: dict[str, tuple[int, int]] = {
    "RC-BANK": (20, 45),
    "RC-DBPOOL": (10, 40),
    "RC-OTP-PROVIDER": (10, 30),
    "RC-QUEUE": (60, 180),
    "RC-AUTH-ATTACK": (5, 20),
    "RC-MEMLEAK": (40, 120),
    "RC-CERT": (5, 15),
    "RC-ABRUPT": (0, 0),
}

_NOISE_SD = 0.015
_DEPENDANT_LAG = (5, 15)  # FP 5: dependants get a sympathetic ramp 5-15 min later
_DEPLOY_CONFOUNDER_P = 0.25  # FP 3.4: 25% of RC-DBPOOL / RC-MEMLEAK follow a causing deploy
# Anti-leakage (FP 1.4 F4): share of N4/N5 draws with a slow pre-drift, and with a WARN precursor.
_PRE_DRIFT_P = 0.5
_NEG_WARN_P = 0.5


class LogTemplate(NamedTuple):
    """A log line relative to onset. ``message`` may use ``{bank}`` and ``{provider}`` only."""

    offset_min: int  # minutes relative to onset; negative = before onset
    template_id: str
    message: str
    level: str = "ERROR"  # INFO | WARN | ERROR


@dataclass(frozen=True, eq=False)
class Shape:
    """One episode's shape plus the secondary signals the generator must emit around it."""

    code: str
    kind: str  # "incident" | "negative"
    u_offset: np.ndarray  # read-only float64, normalised (see module docstring)
    onset_index: int  # index into u_offset of the onset / CRITICAL minute
    lead_minutes: int  # == onset_index; 0 for RC-ABRUPT
    latency_lag_min: int  # latency_p99 follows the primary metric this many minutes later
    dependant_lag_min: tuple[int, int]  # inclusive range for dependants' sympathetic ramp
    log_templates: tuple[LogTemplate, ...]
    co_metrics: tuple[str, ...] = ()  # metrics that move with the same shape (besides the anchor)
    segment_metric: str | None = None  # segment rate metric that carries the signal, if any
    benign_evidence: tuple[str, ...] = ()  # kinds of benign evidence a tool can find
    event_kinds: tuple[
        str, ...
    ] = ()  # EVENT_COLUMNS kinds to emit (deploy|maintenance|campaign|cron)
    calendar_kinds: tuple[str, ...] = ()  # the episode must be placed inside one of these


def render_log(template: LogTemplate, *, bank: str = "BANK_A", provider: str = "P1") -> str:
    """Fill a template's placeholders. Templates carry masked/fictional identifiers only."""
    return template.message.format(bank=bank, provider=provider)


def deploy_event_id(service: str, ts: datetime) -> str:
    """Opaque, stable id for a deploy event: no episode id or label leaks into it."""
    digest = hashlib.sha1(f"{service}|{ts:%Y-%m-%dT%H:%M}".encode()).hexdigest()
    return f"deploy_{digest[:8]}"


def deploy_text(service: str, ts: datetime) -> str:
    """Uniform text for every deploy (causing, N4 and background alike)."""
    return f"Rolling deploy of {service} build {ts:%Y.%m.%d-%H%M}"


# --- curve primitives (x runs 0..1 over the precursor) ---------------------------------------


def _x(n: int) -> np.ndarray:
    return np.linspace(0.0, 1.0, n + 1)


def _finish(rng: np.random.Generator, curve: np.ndarray, onset_index: int) -> np.ndarray:
    """Add seeded noise, clip to [0, 1.05], pin the onset to exactly 1.0, freeze."""
    out = curve + rng.normal(0.0, _NOISE_SD, curve.shape)
    if onset_index > 0:
        out[0] = max(0.0, curve[0])
    out = np.clip(out, 0.0, 1.0)
    out[onset_index] = 1.0
    out.setflags(write=False)
    return out


def _ramp(code: str, rng: np.random.Generator, lead: int) -> np.ndarray:
    x = _x(lead)
    if code == "RC-BANK":  # step then creep
        step = rng.uniform(0.25, 0.4)
        y = step + (1.0 - step) * x ** rng.uniform(1.2, 1.8)
        y[0] = 0.0
        return y
    if code == "RC-DBPOOL":  # convex rise
        return x ** rng.uniform(1.8, 2.6)
    if code == "RC-OTP-PROVIDER":  # delivery rate falls (u of a lower_bad metric rises)
        return x ** rng.uniform(1.0, 1.5)
    if code == "RC-QUEUE":  # accelerating lag
        k = rng.uniform(2.0, 4.0)
        return np.expm1(k * x) / math.expm1(k)
    if code == "RC-AUTH-ATTACK":  # burst
        mid, steep = rng.uniform(0.45, 0.7), rng.uniform(10.0, 16.0)
        s = 1.0 / (1.0 + np.exp(-steep * (x - mid)))
        return (s - s[0]) / (s[-1] - s[0])
    if code == "RC-MEMLEAK":  # linear ramp
        return x.copy()
    raise AssertionError(code)


_INCIDENT_SIGNALS: dict[str, dict[str, object]] = {
    "RC-BANK": {
        "lag": (0, 3),
        "segment": "issuer_timeout_rate",
        "co": ("latency_p99", "error_rate"),
    },
    "RC-DBPOOL": {"lag": (3, 10), "co": ("connection_pool", "latency_p99", "error_rate")},
    "RC-OTP-PROVIDER": {"lag": (0, 3), "segment": "otp_delivery_rate", "co": ("latency_p99",)},
    "RC-QUEUE": {"lag": (5, 15), "co": ("queue_depth", "latency_p99")},
    "RC-AUTH-ATTACK": {
        "lag": (1, 3),
        "segment": "login_failure_rate",
        "co": ("error_rate", "cpu_usage"),
    },
    "RC-MEMLEAK": {"lag": (10, 20), "co": ("memory_usage", "latency_p99")},
    "RC-CERT": {"lag": (0, 0), "co": ()},
    "RC-ABRUPT": {"lag": (0, 0), "co": ()},
}


def _incident_logs(code: str, lead: int) -> tuple[LogTemplate, ...]:
    half = -max(1, lead // 2)
    if code == "RC-BANK":
        return (
            LogTemplate(
                half,
                "ibft_slow_response",
                "IBFT {bank}: ISO8583 0210 response time above SLA",
                "WARN",
            ),
            LogTemplate(
                -max(1, lead // 4),
                "ibft_rc91",
                "IBFT {bank}: ISO8583 0210 RC=91 issuer unavailable",
            ),
            LogTemplate(0, "ibft_rc91", "IBFT {bank}: ISO8583 0210 RC=91 issuer unavailable"),
        )
    if code == "RC-DBPOOL":
        return (
            LogTemplate(
                half,
                "hikari_pool_stats",
                "HikariPool-1 - Pool stats (active=48, idle=2, waiting=17)",
                "WARN",
            ),
            LogTemplate(
                0,
                "hikari_timeout",
                "HikariPool-1 - Connection is not available, request timed out after 30000ms",
            ),
        )
    if code == "RC-OTP-PROVIDER":
        return (
            LogTemplate(half, "sms_dlr_delayed", "SMS {provider} delivery receipt delayed", "WARN"),
            LogTemplate(0, "sms_dlr_timeout", "SMS {provider} DLR timeout"),
        )
    if code == "RC-QUEUE":
        return (
            LogTemplate(
                half, "settlement_lag_rising", "settlement-consumer group lag increasing", "WARN"
            ),
            LogTemplate(
                0, "settlement_cutoff_risk", "settlement-consumer lag threatens 16:00 cut-off"
            ),
        )
    if code == "RC-AUTH-ATTACK":
        return (
            LogTemplate(
                half,
                "login_fail_burst",
                "Login failed: invalid credentials (masked user), source burst",
                "WARN",
            ),
            LogTemplate(
                0, "login_fail_many_accounts", "Failed logins across many accounts from few sources"
            ),
        )
    if code == "RC-MEMLEAK":
        return (
            LogTemplate(
                half, "gc_overhead", "GC overhead high: old gen not reclaimed after full GC", "WARN"
            ),
            LogTemplate(0, "oom_heap", "java.lang.OutOfMemoryError: Java heap space"),
        )
    if code == "RC-CERT":
        return (
            LogTemplate(
                -lead, "ssl_handshake_cert_expired", "SSL handshake failed: certificate expired"
            ),
            LogTemplate(
                0, "ssl_handshake_cert_expired", "SSL handshake failed: certificate expired"
            ),
        )
    return (LogTemplate(0, "upstream_reset", "Upstream connection reset by peer"),)  # RC-ABRUPT


def precursor_shape(code: str, rng: np.random.Generator, duration_min: int | None = None) -> Shape:
    """The precursor of an incident with root cause ``code`` (FP 3.3).

    ``duration_min`` overrides the drawn lead (ignored for RC-ABRUPT, which always has lead 0).
    For RC-DBPOOL and RC-MEMLEAK, 25% of draws carry ``event_kinds=("deploy",)``: the generator
    must place a causing deploy event before the precursor (FP 3.4 confounder).
    """
    if code not in LEAD_WINDOWS:
        raise ValueError(f"unknown incident code {code!r}")
    lo, hi = LEAD_WINDOWS[code]
    lead = (
        0
        if code == "RC-ABRUPT"
        else int(duration_min)
        if duration_min
        else int(rng.integers(lo, hi + 1))
    )
    if lead < 0:
        raise ValueError("duration_min must be positive")

    if code == "RC-ABRUPT":
        u = np.array([1.0])
        u.setflags(write=False)
    elif code == "RC-CERT":
        u = np.zeros(lead + 1)
        u.setflags(write=False)
    else:
        u = _finish(rng, _ramp(code, rng, lead), lead)

    sig = _INCIDENT_SIGNALS[code]
    lag_lo, lag_hi = sig["lag"]  # type: ignore[misc]
    latency_lag = int(rng.integers(lag_lo, lag_hi + 1))
    events: tuple[str, ...] = ()
    if code in ("RC-DBPOOL", "RC-MEMLEAK") and rng.random() < _DEPLOY_CONFOUNDER_P:
        events = ("deploy",)
    return Shape(
        code=code,
        kind="incident",
        u_offset=u,
        onset_index=lead,
        lead_minutes=lead,
        latency_lag_min=latency_lag,
        dependant_lag_min=_DEPENDANT_LAG,
        log_templates=_incident_logs(code, lead),
        co_metrics=sig["co"],  # type: ignore[arg-type]
        segment_metric=sig.get("segment"),  # type: ignore[arg-type]
        event_kinds=events,
    )


# --- hard negatives (FP 3.4) -----------------------------------------------------------------


def _segments(*parts: np.ndarray) -> np.ndarray:
    return np.concatenate(parts)


def negative_shape(code: str, rng: np.random.Generator) -> Shape:
    """A hard negative ``N1``..``N6`` (FP 3.4). ``u_offset`` peaks at 1.0 at ``onset_index``.

    ``calendar_kinds`` names the calendar entries (``sentinel.calendar`` kinds) the generator must
    place the episode inside; ``event_kinds`` names the change events to emit. N6 has neither and
    ``benign_evidence == ()``: no tool can explain it.
    """
    if code == "N1":  # salary/campaign surge: TPS, latency, queue and CPU ramp together, 20-40 min
        lead = int(rng.integers(20, 41))
        ramp = _x(lead) ** rng.uniform(1.0, 1.8)
        hold = rng.uniform(0.9, 0.98, int(rng.integers(5, 16)))
        fade = np.linspace(0.85, 0.4, int(rng.integers(8, 16)))
        u = _finish(rng, _segments(ramp, hold, fade), lead)
        return Shape(
            code,
            "negative",
            u,
            lead,
            lead,
            int(rng.integers(0, 3)),
            (0, 0),
            (
                LogTemplate(
                    -lead // 2, "traffic_surge", "Traffic surge: TPS above daily baseline", "INFO"
                ),
                _HIKARI_WARN._replace(offset_min=-max(1, lead // 3)),
            ),
            co_metrics=("tps", "latency_p99", "queue_depth", "cpu_usage"),
            benign_evidence=("calendar",),
            calendar_kinds=("salary_day", "campaign"),
        )
    if code == "N2":  # scheduled bank maintenance: one bank's timeouts for the window
        rise = int(rng.integers(1, 4))
        body = rng.uniform(0.85, 0.97, int(rng.integers(40, 56)))
        lead = rise + int(rng.integers(5, 20))
        u = _finish(
            rng, _segments(np.linspace(0.0, 0.85, rise + 1), body, np.array([0.3, 0.0])), lead
        )
        return Shape(
            code,
            "negative",
            u,
            lead,
            lead,
            0,
            (0, 0),
            (
                LogTemplate(
                    -lead,
                    "ibft_maintenance",
                    "IBFT {bank}: scheduled switch maintenance window",
                    "INFO",
                ),
                LogTemplate(
                    0, "ibft_rc91", "IBFT {bank}: ISO8583 0210 RC=91 issuer unavailable", "WARN"
                ),
            ),
            segment_metric="issuer_timeout_rate",
            benign_evidence=("maintenance_calendar",),
            event_kinds=("maintenance",),
            calendar_kinds=("maintenance",),
        )
    if code == "N3":  # EOD settlement batch: disk_io + queue plateau at a known hour
        rise = int(rng.integers(5, 11))
        plateau = rng.uniform(0.92, 0.99, int(rng.integers(30, 61)))
        lead = rise + int(rng.integers(5, 25))
        u = _finish(
            rng,
            _segments(np.linspace(0.0, 0.92, rise + 1), plateau, np.linspace(0.6, 0.1, 5)),
            lead,
        )
        return Shape(
            code,
            "negative",
            u,
            lead,
            lead,
            0,
            (0, 0),
            (
                LogTemplate(-lead, "eod_batch_start", "EOD settlement batch started", "INFO"),
                LogTemplate(
                    len(u) - lead - 1, "eod_batch_done", "EOD settlement batch completed", "INFO"
                ),
            ),
            co_metrics=("disk_io", "queue_depth"),
            benign_evidence=("cron_schedule",),
            event_kinds=("cron",),
            calendar_kinds=("eod_settlement",),
        )
    if code == "N4":  # deploy blip: p99 bump for 5-10 min, then recovery (some with a pre-drift)
        total = int(rng.integers(5, 11))
        lead = int(rng.integers(1, 3))
        decay = np.linspace(1.0, rng.uniform(0.1, 0.3), total - lead)
        u = _finish(rng, _segments(np.linspace(0.0, 1.0, lead + 1)[:-1], decay), lead)
        u, lead = _pre_drift(rng, u, lead)
        return Shape(
            code,
            "negative",
            u,
            lead,
            lead,
            0,
            (0, 0),
            (
                LogTemplate(
                    -min(lead, 2),
                    "deploy_warmup",
                    "Deployment rollout complete; warming caches",
                    "INFO",
                ),
                *_maybe_warn(rng, lead),
            ),
            co_metrics=("latency_p99",),
            benign_evidence=("deploy_log", "recovering_trend"),
            event_kinds=("deploy",),
        )
    if code == "N5":  # transient spike: 1-3 min touch of CRITICAL, already recovering
        lead = int(rng.integers(1, 4))
        touch = int(rng.integers(1, 4))
        u = _x(lead)[:-1]
        u = _segments(u * 0.8, np.ones(touch), np.linspace(0.7, 0.1, int(rng.integers(2, 6))))
        u = _finish(rng, u, lead)
        u = u.copy()
        u[lead : lead + touch] = 1.0
        u[:lead] = np.minimum(u[:lead], 0.9)
        u[lead + touch :] = np.minimum(u[lead + touch :], 0.9)
        u.setflags(write=False)
        u, lead = _pre_drift(rng, u, lead)
        return Shape(
            code,
            "negative",
            u,
            lead,
            lead,
            0,
            (0, 0),
            _maybe_warn(rng, lead),
            benign_evidence=("recovering_trend",),
        )
    if code == "N6":  # unexplained CRITICAL excursion; no benign evidence anywhere
        lead = int(rng.integers(10, 61))  # overlaps incident leads (FP 1.4 F4)
        touch = int(rng.integers(1, 5))
        rise = _x(lead) ** rng.uniform(1.0, 2.0)
        u = _finish(
            rng,
            _segments(
                rise, np.full(touch - 1, 0.98), np.linspace(0.9, 0.3, int(rng.integers(10, 21)))
            ),
            lead,
        )
        warn = _GENERIC_WARN[int(rng.integers(len(_GENERIC_WARN)))]
        logs = (warn._replace(offset_min=-max(1, lead // 2)),)
        return Shape(code, "negative", u, lead, lead, int(rng.integers(0, 4)), (0, 0), logs)
    raise ValueError(f"unknown negative code {code!r}")


def _pre_drift(rng: np.random.Generator, u: np.ndarray, onset: int) -> tuple[np.ndarray, int]:
    """With probability ``_PRE_DRIFT_P``, prepend a slow 20-60 min drift up to 0.35-0.6.

    So a long rising precursor is not an incident-only feature (FP 1.4 F4). The pre-onset part
    of ``u`` is lifted to the drift level so the series does not drop back before the blip.
    Draws the same number of variates either way.
    """
    hit = rng.random() < _PRE_DRIFT_P
    n = int(rng.integers(20, 61))
    level, power = rng.uniform(0.35, 0.6), rng.uniform(1.0, 1.6)
    noise = rng.normal(0.0, _NOISE_SD, n)
    if not hit:
        return u, onset
    drift = np.clip(level * _x(n)[:-1] ** power + noise, 0.0, 0.9)
    drift[0] = 0.0
    body = u.copy()
    body[:onset] = np.maximum(body[:onset], level)
    out = np.concatenate([drift, body])
    out.setflags(write=False)
    return out, onset + n


def _maybe_warn(rng: np.random.Generator, lead: int) -> tuple[LogTemplate, ...]:
    """With probability ``_NEG_WARN_P``, one incident-looking WARN line before onset."""
    hit = rng.random() < _NEG_WARN_P
    tpl = _GENERIC_WARN[int(rng.integers(len(_GENERIC_WARN)))]
    return (tpl._replace(offset_min=-max(1, lead // 2)),) if hit else ()


_HIKARI_WARN = LogTemplate(
    0, "hikari_pool_stats", "HikariPool-1 - Pool stats (active=48, idle=2, waiting=17)", "WARN"
)
_GENERIC_WARN: tuple[LogTemplate, ...] = (
    _HIKARI_WARN,
    LogTemplate(0, "gc_overhead", "GC overhead high: old gen not reclaimed after full GC", "WARN"),
)


def _noise_templates() -> tuple[LogTemplate, ...]:
    seen: dict[str, LogTemplate] = {}
    for code in INCIDENT_CODES:
        if code == "RC-CERT":  # D7: RC-CERT's novel template must stay novel
            continue
        for t in _incident_logs(code, 10):
            if t.level in ("WARN", "ERROR") and t.template_id not in seen:
                seen[t.template_id] = t._replace(offset_min=0)
    return tuple(seen.values())


# WARN/ERROR incident templates the generator scatters as background noise (FP 1.4 F4): the same
# template ids appear outside episodes, so "a WARN/ERROR line nearby" is never a free label.
NOISE_TEMPLATES: tuple[LogTemplate, ...] = _noise_templates()


# --- counts and seasonality ------------------------------------------------------------------


def rate_counts(p: float, n_total: int, rng: np.random.Generator) -> tuple[int, int]:
    """``(n_total, n_bad)`` with ``n_bad ~ Binomial(n_total, p)`` (FP 5)."""
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be in [0, 1], got {p}")
    if n_total < 0:
        raise ValueError("n_total must be >= 0")
    return int(n_total), int(rng.binomial(n_total, p)) if n_total else 0


def _bump(h: float, centre: float, width: float) -> float:
    d = min(abs(h - centre), 24.0 - abs(h - centre))
    return math.exp(-0.5 * (d / width) ** 2)


def daily_tps_factor(ts: datetime, calendar: list[CalendarEvent] | None = None) -> float:
    """TPS multiplier at ``ts`` (PKT): daily curve x the largest active calendar multiplier.

    Daily curve (FP 5): trough 02:00-06:00, peaks 12:00-14:00 and 20:00-23:00, mean about 1.
    Calendar multipliers come from ``data/calendar.yaml`` (salary days 1.6, campaigns per entry).
    Pass ``calendar`` (from ``load_calendar()``) in hot loops to avoid re-reading the YAML.
    """
    h = ts.hour + ts.minute / 60.0
    base = 0.2 + 0.35 * _bump(h, 9.5, 2.5) + 0.85 * _bump(h, 13.0, 1.3) + 1.0 * _bump(h, 21.5, 1.4)
    mult = max([e.tps_multiplier for e in events_at(ts, calendar)], default=1.0)
    return base * max(mult, 1.0)
