"""Time source. Replay and tests use SimClock; the live service uses WallClock.

Re-checks (I4), approval expiry, TTLs, post-action verification and cooldowns all schedule through a Clock,
so a 600x replay behaves exactly like real time.
"""

from __future__ import annotations

import heapq
import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def call_later(self, delay: timedelta, fn: Callable[[], None]) -> Handle: ...


@dataclass
class Handle:
    when: datetime
    fn: Callable[[], None]
    cancelled: bool = field(default=False)

    def cancel(self) -> None:
        self.cancelled = True


class SimClock:
    """Deterministic clock: time moves only via `advance`/`set`, firing due callbacks in time order."""

    def __init__(self, start: datetime) -> None:
        self._now = start
        self._heap: list[tuple[datetime, int, Handle]] = []
        self._seq = itertools.count()

    def now(self) -> datetime:
        return self._now

    def call_later(self, delay: timedelta, fn: Callable[[], None]) -> Handle:
        h = Handle(self._now + delay, fn)
        heapq.heappush(self._heap, (h.when, next(self._seq), h))
        return h

    def set(self, t: datetime) -> None:
        while self._heap and self._heap[0][0] <= t:
            when, _, h = heapq.heappop(self._heap)
            self._now = max(self._now, when)
            if not h.cancelled:
                h.fn()
        self._now = max(self._now, t)

    def advance(self, delta: timedelta) -> None:
        self.set(self._now + delta)


class WallClock:
    """Real time. Scheduling is driven by the API's asyncio loop calling `run_due` every second."""

    def __init__(self) -> None:
        self._sim = SimClock(datetime.now(UTC))

    def now(self) -> datetime:
        return datetime.now(UTC)

    def call_later(self, delay: timedelta, fn: Callable[[], None]) -> Handle:
        self._sim.set(self.now())
        return self._sim.call_later(delay, fn)

    def run_due(self) -> None:
        self._sim.set(self.now())
