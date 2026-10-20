"""Pure, deterministic NovaPay traffic model.

All logic lives here: a seeded ``random.Random`` and an injectable start time. ``step(dt)`` advances
simulated time and returns any CES envelopes closed during that interval (one per service per 5 s).
The FastAPI app only calls ``step`` with wall-clock deltas; tests call it directly.
"""

from __future__ import annotations

import bisect
import itertools
import math
import random
from collections import deque
from datetime import UTC, datetime, timedelta

from . import chaos
from .banks import BANK_WEIGHTS, BANKS, DEFAULT_RAIL, HEALTHY, RAILS, RailProfile, rail_outcome
from .emitter import TICK_S, EnvelopeBuilder, Window
from .otp import DEFAULT_PROVIDER, HEALTHY_DELIVERY, PROVIDERS, send_otp

POOL_SIZE = 20
LEDGER_HOLD_S = 0.08  # each payment holds a ledger connection ~80 ms
LEDGER_BASE_MS = 15.0
FRAUD_MS = 5.0
DEFAULT_WORKERS = 4
TPS_PER_WORKER = 10.0
MIN_TPS, MAX_TPS = 20.0, 80.0
LOGIN_RATE = 10.0
LOGIN_FAILURE_P = 0.03
OTP_RATE = 5.0
OTP_PROBE_RATE = 0.5  # health-check sends on the standby provider (evidence for "target healthy")
MAX_SUBSTEP_S = 1.0
HISTORY_WINDOWS = 720  # 1 hour of 5 s windows
QUEUE_BASE, QUEUE_BATCH = 1500.0, 40000.0
DISK_BASE, DISK_BATCH = 25.0, 85.0


def _floor_to_tick(ts: datetime) -> datetime:
    epoch = ts.timestamp()
    return datetime.fromtimestamp(epoch - (epoch % TICK_S), tz=UTC)


class SimEngine:
    def __init__(self, seed: int = 7, start: datetime | None = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.start = start or _floor_to_tick(datetime.now(UTC))
        self.t = 0.0
        self._builder = EnvelopeBuilder(seed, random.Random(seed ^ 0x5EED))
        self._cum_weights = list(itertools.accumulate(BANK_WEIGHTS))
        self._carry = {"pay": 0.0, "login": 0.0, "otp": 0.0, "probe": 0.0}
        self._window = Window()
        self.history: deque[Window] = deque(maxlen=HISTORY_WINDOWS)
        self._in_use = 0.0
        self._reset_controls()

    # ------------------------------------------------------------ controls

    def _reset_controls(self) -> None:
        self.routing: dict[str, str] = dict.fromkeys(BANKS, DEFAULT_RAIL)
        self.otp_provider = DEFAULT_PROVIDER
        self.workers = DEFAULT_WORKERS
        self.chaos: dict[str, float] = {}  # fault → sim-t it started

    @property
    def now(self) -> datetime:
        return self.start + timedelta(seconds=self.t)

    @property
    def tps(self) -> float:
        return max(MIN_TPS, min(MAX_TPS, self.workers * TPS_PER_WORKER))

    def trigger(self, fault: str) -> list[str]:
        """Start a fault (idempotent) or ``reset``. Unknown fault → KeyError. Returns active faults."""
        if fault == chaos.RESET:
            self._reset_controls()
        elif fault in chaos.FAULTS:
            self.chaos.setdefault(fault, self.t)
        else:
            raise KeyError(fault)
        return sorted(self.chaos)

    def set_routing(self, bank: str, rail: str) -> dict[str, str]:
        if bank not in BANKS or rail not in RAILS:
            raise ValueError(f"bad routing {bank}->{rail}")
        self.routing[bank] = rail
        return dict(self.routing)

    def set_otp_provider(self, provider: str) -> str:
        if provider not in PROVIDERS:
            raise ValueError(provider)
        self.otp_provider = provider
        return provider

    def set_workers(self, workers: int) -> int:
        if not 1 <= workers <= 8:
            raise ValueError(workers)
        self.workers = workers
        return workers

    def _elapsed(self, fault: str) -> float | None:
        started = self.chaos.get(fault)
        return None if started is None else self.t - started

    # ------------------------------------------------------------ model pieces

    def leaked(self) -> float:
        e = self._elapsed("ledger_pool_leak")
        return 0.0 if e is None else chaos.leaked_connections(e, POOL_SIZE)

    def _pool(self) -> tuple[float, float, float]:
        """→ (in-use connections, extra ledger wait ms, pool-exhaustion error probability)."""
        leaked = self.leaked()
        free = max(0.0, POOL_SIZE - leaked)
        demand = self.tps * LEDGER_HOLD_S
        if free <= 0:
            return float(POOL_SIZE), 2000.0, 0.95
        rho = demand / free
        in_use = min(float(POOL_SIZE), leaked + demand)
        if rho >= 1.0:
            return float(POOL_SIZE), 1000.0 * min(2.0, rho), 1.0 - 1.0 / rho
        # queueing wait grows like 1/(1-rho); errors appear as the pool nears saturation
        wait = LEDGER_BASE_MS * (rho / (1.0 - rho))
        err = 0.0 if rho < 0.6 else 0.05 * ((rho - 0.6) / 0.4) ** 2
        return in_use, min(wait, 1000.0), err

    def _rail_profile(self, bank: str, rail: str) -> RailProfile:
        p = HEALTHY[rail]
        e = self._elapsed("bank_c_slow")
        if bank == "BANK_C" and rail == "IBFT" and e is not None:
            mult, timeout_p = chaos.bank_c_ibft(e)
            return RailProfile(p.median_ms * mult, p.sigma, timeout_p, p.error_p)
        return p

    def _otp_params(self, provider: str) -> tuple[float, float]:
        e = self._elapsed("otp_p1_down")
        if provider == "P1" and e is not None:
            return chaos.otp_p1(e, HEALTHY_DELIVERY)
        return HEALTHY_DELIVERY, 1.0

    def _pick_bank(self) -> str:
        r = self.rng.random() * self._cum_weights[-1]
        return BANKS[bisect.bisect_right(self._cum_weights, r)]

    def _count(self, key: str, rate: float, dt: float) -> int:
        self._carry[key] += rate * dt
        n = int(self._carry[key])
        self._carry[key] -= n
        return n

    # ------------------------------------------------------------ single calls

    def pay(self, bank: str | None = None) -> dict:
        """One synthetic payment: fraud → ledger pool → rail. Recorded into the current window."""
        bank = bank or self._pick_bank()
        rail = self.routing[bank]
        _, wait_ms, pool_err = self._pool()
        latency = FRAUD_MS + LEDGER_BASE_MS + wait_ms
        if self.rng.random() < pool_err:
            outcome, rail_ms = "error", 0.0
        else:
            outcome, rail_ms = rail_outcome(self.rng, self._rail_profile(bank, rail))
        latency += rail_ms
        w = self._window
        w.pay_total[bank] += 1
        w.pay_latency.append(latency)
        if outcome == "success":
            w.pay_success[bank] += 1
        elif outcome == "timeout":
            w.pay_timeout[bank] += 1
        return {"bank": bank, "rail": rail, "outcome": outcome, "latency_ms": round(latency, 1)}

    def login(self) -> dict:
        ok = self.rng.random() >= LOGIN_FAILURE_P
        self._window.login_total += 1
        self._window.login_failed += 0 if ok else 1
        return {"ok": ok, "latency_ms": round(self.rng.lognormvariate(math.log(120.0), 0.3), 1)}

    def send_otp(self, provider: str | None = None) -> dict:
        provider = provider or self.otp_provider
        delivery_p, mult = self._otp_params(provider)
        delivered, latency = send_otp(self.rng, delivery_p, mult)
        w = self._window
        if provider == self.otp_provider:
            w.otp_customer_total += 1
            w.otp_customer_delivered += int(delivered)
        w.otp_total[provider] += 1
        w.otp_delivered[provider] += int(delivered)
        w.otp_latency.append(latency)
        return {"provider": provider, "delivered": delivered, "latency_ms": round(latency, 1)}

    # ------------------------------------------------------------ time

    def _substep(self, dt: float) -> None:
        for _ in range(self._count("pay", self.tps, dt)):
            self.pay()
        for _ in range(self._count("login", LOGIN_RATE, dt)):
            self.login()
        for _ in range(self._count("otp", OTP_RATE, dt)):
            self.send_otp()
        standby = next(p for p in PROVIDERS if p != self.otp_provider)
        for _ in range(self._count("probe", OTP_PROBE_RATE, dt)):
            self.send_otp(standby)
        in_use, _, _ = self._pool()
        self._in_use = in_use
        w = self._window
        w.pool_util_samples.append(in_use / POOL_SIZE)
        e = self._elapsed("report_batch")
        level = 0.0 if e is None else chaos.report_batch_level(e)
        w.queue_depth_samples.append(
            max(0.0, QUEUE_BASE + (QUEUE_BATCH - QUEUE_BASE) * level + self.rng.gauss(0, 150))
        )
        w.disk_io_samples.append(
            max(0.0, DISK_BASE + (DISK_BATCH - DISK_BASE) * level + self.rng.gauss(0, 3))
        )

    def step(self, dt: float) -> list[dict]:
        """Advance ``dt`` sim-seconds; return CES envelopes for every 5 s window closed meanwhile."""
        out: list[dict] = []
        remaining = float(dt)
        while remaining > 1e-9:
            next_tick = (math.floor(self.t / TICK_S + 1e-9) + 1) * TICK_S
            d = min(remaining, MAX_SUBSTEP_S, next_tick - self.t)
            self._substep(d)
            self.t += d
            remaining -= d
            if abs(self.t - next_tick) < 1e-9:
                self.t = next_tick
                out.extend(self._close_window())
        return out

    def _close_window(self) -> list[dict]:
        w = self._window
        w.end_t = self.t
        envelopes = self._builder.build(w, self.now)
        self.history.append(w.summary())
        self._window = Window()
        return envelopes

    # ------------------------------------------------------------ queries

    def _recent(self, last_s: float) -> list[Window]:
        return [w for w in self.history if w.end_t > self.t - last_s - 1e-9]

    def payment_success_rate(self, bank: str, last_s: float = 30.0) -> float:
        ws = self._recent(last_s)
        total = sum(w.pay_total[bank] for w in ws)
        return sum(w.pay_success[bank] for w in ws) / total if total else 1.0

    def payment_error_rate(self, last_s: float = 30.0) -> float:
        ws = self._recent(last_s)
        total = sum(sum(w.pay_total.values()) for w in ws)
        ok = sum(sum(w.pay_success.values()) for w in ws)
        return (total - ok) / total if total else 0.0

    def otp_delivery_rate(self, provider: str | None = None, last_s: float = 30.0) -> float:
        ws = self._recent(last_s)
        provs = PROVIDERS if provider is None else (provider,)
        total = sum(w.otp_total[p] for w in ws for p in provs)
        return sum(w.otp_delivered[p] for w in ws for p in provs) / total if total else 1.0

    def otp_customer_delivery_rate(self, last_s: float = 30.0) -> float:
        """Delivery rate of real (active-provider) OTP sends, i.e. what customers experience."""
        ws = self._recent(last_s)
        total = sum(w.otp_customer_total for w in ws)
        return sum(w.otp_customer_delivered for w in ws) / total if total else 1.0

    def login_failure_rate(self, last_s: float = 30.0) -> float:
        ws = self._recent(last_s)
        total = sum(w.login_total for w in ws)
        return sum(w.login_failed for w in ws) / total if total else 0.0

    def pool_utilisation(self) -> float:
        return self._in_use / POOL_SIZE

    def state(self) -> dict:
        last = self.history[-1] if self.history else None
        return {
            "sim_t": round(self.t, 3),
            "sim_time": self.now.isoformat(),
            "seed": self.seed,
            "routing": dict(self.routing),
            "otp_provider": self.otp_provider,
            "workers": self.workers,
            "tps": self.tps,
            "chaos": {f: round(self.t - s, 3) for f, s in sorted(self.chaos.items())},
            "ledger_pool": {
                "size": POOL_SIZE,
                "in_use": round(self._in_use, 2),
                "leaked": round(self.leaked(), 2),
                "utilisation": round(self.pool_utilisation(), 4),
            },
            "last_window": None
            if last is None
            else {
                "end_t": last.end_t,
                "payment_success_rate": {b: round(self.payment_success_rate(b, TICK_S), 4) for b in BANKS},
                "otp_delivery_rate": {p: round(self.otp_delivery_rate(p, TICK_S), 4) for p in PROVIDERS},
                "otp_customer_delivery_rate": round(self.otp_customer_delivery_rate(TICK_S), 4),
                "login_failure_rate": round(self.login_failure_rate(TICK_S), 4),
            },
        }
