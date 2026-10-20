"""Window aggregation → CES envelopes, plus the sinks they are delivered to.

CES is one metric per object, so each 5 s tick yields one *envelope* per service:
``{"service": ..., "ts": ..., "events": [CES, ...]}`` (FINAL_PLAN §4.3).
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from .banks import BANKS
from .otp import PROVIDERS

log = logging.getLogger("finpay_sim.emitter")

SOURCE = "finpay-sim"
TICK_S = 5.0

# (threshold, direction) per metric
PAYMENT_SUCCESS = (0.97, "lower_bad")
ISSUER_TIMEOUT = (0.02, "higher_bad")
PG_LATENCY_P99 = (1200.0, "higher_bad")
PG_ERROR_RATE = (0.01, "higher_bad")
PG_CONNECTION_POOL = (100.0, "higher_bad")
OTP_DELIVERY = (0.95, "lower_bad")
OTP_LATENCY_P99 = (6000.0, "higher_bad")
LOGIN_FAILURE = (0.08, "higher_bad")
QUEUE_DEPTH = (50000.0, "higher_bad")
DISK_IO = (100.0, "higher_bad")


@dataclass
class Window:
    """Raw counts for one 5 s window (also kept as history for rate queries)."""

    end_t: float = 0.0
    pay_total: dict[str, int] = field(default_factory=lambda: dict.fromkeys(BANKS, 0))
    pay_success: dict[str, int] = field(default_factory=lambda: dict.fromkeys(BANKS, 0))
    pay_timeout: dict[str, int] = field(default_factory=lambda: dict.fromkeys(BANKS, 0))
    pay_latency: list[float] = field(default_factory=list)
    otp_total: dict[str, int] = field(default_factory=lambda: dict.fromkeys(PROVIDERS, 0))
    otp_delivered: dict[str, int] = field(default_factory=lambda: dict.fromkeys(PROVIDERS, 0))
    otp_latency: list[float] = field(default_factory=list)
    otp_customer_total: int = 0  # sends on the active provider (excludes standby probes)
    otp_customer_delivered: int = 0
    login_total: int = 0
    login_failed: int = 0
    pool_util_samples: list[float] = field(default_factory=list)
    queue_depth_samples: list[float] = field(default_factory=list)
    disk_io_samples: list[float] = field(default_factory=list)

    def summary(self) -> Window:
        """Drop per-call latency lists once emitted (history keeps counts only)."""
        self.pay_latency = []
        self.otp_latency = []
        return self


def p99(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return float(s[min(len(s) - 1, int(0.99 * len(s)))])


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


class EnvelopeBuilder:
    def __init__(self, seed: int, id_rng: random.Random) -> None:
        self.seed = seed
        self._id_rng = id_rng

    def _ces(
        self,
        ts: str,
        service: str,
        metric: str,
        value: float,
        spec: tuple[float, str],
        segment_key: str = "*",
        n_total: int | None = None,
        n_bad: int | None = None,
    ) -> dict:
        threshold, direction = spec
        return {
            "event_id": uuid.UUID(int=self._id_rng.getrandbits(128), version=4).hex,
            "ts": ts,
            "source": SOURCE,
            "kind": "metric",
            "service": service,
            "segment_key": segment_key,
            "metric": metric,
            "value": float(value),
            "threshold": float(threshold),
            "direction": direction,
            "n_total": n_total,
            "n_bad": n_bad,
            "attributes": {},
            "redacted": True,
            "seed": self.seed,
        }

    def _rate(self, ts, service, metric, spec, total, bad, segment_key="*") -> dict:
        frac = bad / total if total else 0.0
        value = 1.0 - frac if spec[1] == "lower_bad" else frac
        return self._ces(ts, service, metric, value, spec, segment_key, n_total=total, n_bad=bad)

    def build(self, w: Window, when: datetime) -> list[dict]:
        ts = when.isoformat()
        pg: list[dict] = []
        for b in BANKS:
            total, ok, to = w.pay_total[b], w.pay_success[b], w.pay_timeout[b]
            seg = f"bank={b}"
            pg.append(
                self._rate(
                    ts, "PaymentGateway", "payment_success_rate", PAYMENT_SUCCESS, total, total - ok, seg
                )
            )
            pg.append(self._rate(ts, "PaymentGateway", "issuer_timeout_rate", ISSUER_TIMEOUT, total, to, seg))
        all_total = sum(w.pay_total.values())
        all_bad = all_total - sum(w.pay_success.values())
        pg.append(self._ces(ts, "PaymentGateway", "latency_p99", p99(w.pay_latency), PG_LATENCY_P99))
        pg.append(self._rate(ts, "PaymentGateway", "error_rate", PG_ERROR_RATE, all_total, all_bad))
        pg.append(
            self._ces(
                ts,
                "PaymentGateway",
                "connection_pool",
                100.0 * _mean(w.pool_util_samples),
                PG_CONNECTION_POOL,
            )
        )

        nh: list[dict] = []
        for p in PROVIDERS:
            total, ok = w.otp_total[p], w.otp_delivered[p]
            nh.append(
                self._rate(
                    ts,
                    "NotificationHub",
                    "otp_delivery_rate",
                    OTP_DELIVERY,
                    total,
                    total - ok,
                    f"provider={p}",
                )
            )
        nh.append(self._ces(ts, "NotificationHub", "latency_p99", p99(w.otp_latency), OTP_LATENCY_P99))

        auth = [
            self._rate(ts, "AuthService", "login_failure_rate", LOGIN_FAILURE, w.login_total, w.login_failed)
        ]

        dp = [
            self._ces(ts, "DataPipeline", "queue_depth", round(_mean(w.queue_depth_samples)), QUEUE_DEPTH),
            self._ces(ts, "DataPipeline", "disk_io", _mean(w.disk_io_samples), DISK_IO),
        ]
        return [
            {"service": svc, "ts": ts, "events": evs}
            for svc, evs in (
                ("PaymentGateway", pg),
                ("NotificationHub", nh),
                ("AuthService", auth),
                ("DataPipeline", dp),
            )
        ]


# ---------------------------------------------------------------- sinks


class Sink(Protocol):
    """Anything that accepts envelopes. Pub/Sub (Phase 3) implements this too."""

    async def publish(self, envelope: dict) -> None: ...


class RingBufferSink:
    """Last ``maxlen`` envelopes, served by ``GET /emitted`` in local mode."""

    def __init__(self, maxlen: int = 2000) -> None:
        self.buffer: deque[dict] = deque(maxlen=maxlen)

    async def publish(self, envelope: dict) -> None:
        self.buffer.append(envelope)

    def since(self, since: datetime | None, limit: int) -> list[dict]:
        items = [e for e in self.buffer if since is None or datetime.fromisoformat(e["ts"]) > since]
        return items[:limit]


class HttpSink:
    """POSTs each envelope to ``SENTINEL_INGEST_URL``; fire-and-forget, errors logged not raised."""

    def __init__(self, url: str, timeout_s: float = 3.0) -> None:
        import httpx

        self.url = url
        self._client = httpx.AsyncClient(timeout=timeout_s)
        self._tasks: set[asyncio.Task] = set()

    async def _post(self, envelope: dict) -> None:
        try:
            r = await self._client.post(self.url, json=envelope)
            if r.status_code >= 400:
                log.warning("ingest POST %s → %s", self.url, r.status_code)
        except Exception as exc:  # noqa: BLE001 - never let the sink break the loop
            log.warning("ingest POST %s failed: %s", self.url, exc)

    async def publish(self, envelope: dict) -> None:
        task = asyncio.create_task(self._post(envelope))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def aclose(self) -> None:
        await self._client.aclose()
