"""Replay a Dataset onto the bus as CES telemetry, paced by wall time and agent activity.

Interface: ``Replayer(ds, bus, clock, speed, gate).run(window | episode_id)``. Per tick
(one dataset minute) it publishes, on topic ``telemetry``, one message per service: a list of
``CES`` covering every metric/segment of that service in that minute. Log and change rows are
published as their own single-service lists (kind='log'/'change') before the metrics of the
same tick. The ``EventClock`` is advanced to the tick time before anything is published.

Pacing (plan D4): a tick sleeps ``60 / speed`` seconds; ``speed <= 0`` or ``None`` means no
sleeping. While ``gate.busy()`` (an incident is between Planning and AwaitingApproval) the
replayer drops to 1x (60 s per tick) so the agent sees time pass at human speed, then resumes.

Idempotency: event ids are uuid5 of (kind, ts, service, metric, segment), so redelivery dedupes.
Dataset timestamps are naive; they are interpreted as UTC for the clock and CES.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

import pandas as pd

from sentinel.bus import Bus
from sentinel.clock import EventClock
from sentinel.datagen.types import Dataset
from sentinel.schemas import CES

TOPIC = "telemetry"
_NS = uuid.UUID("5e57117e-1000-4000-8000-000000000001")
_REAL_TIME_S = 60.0  # wall seconds per dataset minute at 1x

Sleep = Callable[[float], Awaitable[None]]
Progress = Callable[[datetime, int], None]  # (tick ts, messages published this tick)


class PaceGate(Protocol):
    def busy(self) -> bool:
        """True while any incident is between Planning and AwaitingApproval."""
        ...


def _eid(*parts: object) -> str:
    return str(uuid.uuid5(_NS, "|".join(str(p) for p in parts)))


def _naive(ts: datetime) -> datetime:
    return ts.replace(tzinfo=None) if ts.tzinfo else ts


def _utc(ts: pd.Timestamp) -> datetime:
    return ts.to_pydatetime().replace(tzinfo=UTC)


class Replayer:
    def __init__(
        self,
        ds: Dataset,
        bus: Bus,
        clock: EventClock,
        speed: float | None = 60.0,
        gate: PaceGate | None = None,
        *,
        sleep: Sleep = asyncio.sleep,
        on_progress: Progress | None = None,
    ) -> None:
        self._ds = ds
        self._bus = bus
        self._clock = clock
        self._speed = speed
        self._gate = gate
        self._sleep = sleep
        self.on_progress = on_progress
        self._stopped = False
        self._running = asyncio.Event()
        self._running.set()
        self.current_speed: float = speed or 0.0

    def stop(self) -> None:
        self._stopped = True
        self._running.set()  # release a paused run so it can exit

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    def _window(
        self, window: tuple[datetime, datetime] | None, episode_id: str | None,
        lead_in_min: int, tail_min: int,
    ) -> tuple[datetime, datetime]:  # fmt: skip
        if episode_id is not None:
            ep = self._ds.episode(episode_id)
            return (
                _naive(ep.precursor_start) - timedelta(minutes=lead_in_min),
                _naive(ep.end) + timedelta(minutes=tail_min),
            )
        if window is not None:
            return _naive(window[0]), _naive(window[1])
        return _naive(self._ds.window[0]), _naive(self._ds.window[1])

    def _tick_delay(self) -> float:
        busy = self._gate is not None and self._gate.busy()
        speed = 1.0 if busy else (self._speed or 0.0)
        self.current_speed = speed
        return 0.0 if speed <= 0 else _REAL_TIME_S / speed

    async def run(
        self,
        window: tuple[datetime, datetime] | None = None,
        episode_id: str | None = None,
        lead_in_min: int = 90,
        tail_min: int = 30,
    ) -> None:
        lo, hi = self._window(window, episode_id, lead_in_min, tail_min)
        ds = self._ds
        m = ds.metrics[(ds.metrics["ts"] >= lo) & (ds.metrics["ts"] <= hi)]
        lg = ds.logs[(ds.logs["ts"] >= lo) & (ds.logs["ts"] <= hi)]
        ev = ds.events[(ds.events["ts"] >= lo) & (ds.events["ts"] <= hi)]
        m_by = {k: g for k, g in m.groupby("ts", sort=True)}
        lg_by = {k: g for k, g in lg.groupby("ts", sort=True)}
        ev_by = {k: g for k, g in ev.groupby("ts", sort=True)}
        ticks = sorted(cast(set[pd.Timestamp], set(m_by) | set(lg_by) | set(ev_by)))
        self._stopped = False
        for tick in ticks:
            await self._running.wait()
            if self._stopped:
                return
            ts = _utc(cast(pd.Timestamp, tick))
            self._clock.advance_to(ts)
            batches: list[list[CES]] = []
            if tick in lg_by:
                batches += [[self._log(r)] for r in lg_by[tick].itertuples(index=False)]
            if tick in ev_by:
                batches += [[self._change(r)] for r in ev_by[tick].itertuples(index=False)]
            if tick in m_by:
                for _svc, g in m_by[tick].groupby("service", sort=True):
                    batches.append(
                        [self._metric(r, ts, ds.seed) for r in g.itertuples(index=False)]
                    )
            for b in batches:
                await self._bus.publish(TOPIC, b)  # pyright: ignore[reportArgumentType]
            if self.on_progress:
                self.on_progress(ts, len(batches))
            delay = self._tick_delay()
            if delay > 0:
                await self._sleep(delay)

    def _metric(self, r: Any, ts: datetime, seed: int) -> CES:
        return CES(
            event_id=_eid("metric", ts.isoformat(), r.service, r.metric, r.segment_key),
            ts=ts, source=str(r.source), kind="metric", service=str(r.service),
            segment_key=str(r.segment_key), metric=str(r.metric), value=float(r.value),
            threshold=float(r.threshold), direction=r.direction,
            n_total=int(r.n_total), n_bad=int(r.n_bad), seed=seed,
        )  # fmt: skip

    def _log(self, r: Any) -> CES:
        ts = _utc(r.ts)
        return CES(
            event_id=_eid("log", ts.isoformat(), r.service, r.template_id, r.message),
            ts=ts, source=f"{self._ds.mode}_replay", kind="log", service=str(r.service),
            attributes={"level": str(r.level), "template_id": str(r.template_id),
                        "message": str(r.message)},
            seed=self._ds.seed,
        )  # fmt: skip

    def _change(self, r: Any) -> CES:
        ts = _utc(r.ts)
        return CES(
            event_id=_eid("change", ts.isoformat(), r.service, r.event_id),
            ts=ts, source=f"{self._ds.mode}_replay", kind="change", service=str(r.service),
            attributes={"change_kind": str(r.kind), "text": str(r.text),
                        "event_id": str(r.event_id)},
            seed=self._ds.seed,
        )  # fmt: skip
