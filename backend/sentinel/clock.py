"""Clocks and the timer registry (plan D4 and the timer table).

Every time-dependent component takes a ``Clock`` instead of calling ``datetime.now``.
``EventClock`` follows replayed event time, ``WallClock`` follows real time, and
``FrozenClock`` is for tests. ``TIMERS`` records which clock each named timer uses, so
``test_timer_clock_assignment`` can enforce the table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol


class ClockKind(StrEnum):
    EVENT = "event"
    WALL = "wall"


class Clock(Protocol):
    def now(self) -> datetime: ...


def _require_aware(ts: datetime) -> None:
    if ts.tzinfo is None or ts.utcoffset() is None:
        raise ValueError(f"timestamp must be timezone-aware: {ts!r}")


class WallClock:
    """Real time, timezone-aware UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class EventClock:
    """Time that moves only when a replayed event says so.

    Monotonic: ``advance_to`` raises ``ValueError`` for a timestamp earlier than the
    current time (equal is allowed) or a naive (tz-less) timestamp. ``now()`` raises
    ``LookupError`` until the first event, so a timer can never be armed against an unknown time.
    """

    def __init__(self, start: datetime | None = None) -> None:
        if start is not None:
            _require_aware(start)
        self._now = start

    def now(self) -> datetime:
        if self._now is None:
            raise LookupError("EventClock has not seen an event yet")
        return self._now

    def advance_to(self, ts: datetime) -> None:
        _require_aware(ts)
        if self._now is not None and ts < self._now:
            raise ValueError(f"EventClock cannot go backwards: {ts} < {self._now}")
        self._now = ts


class FrozenClock:
    """Test clock: stands still until ``advance`` is called."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now += delta


@dataclass(frozen=True)
class Timer:
    kind: ClockKind
    value: timedelta | None  # duration, or the rate window when ``limit`` is set
    limit: int | None = None  # max count (rechecks, breaker trips, pages per window)


_M = timedelta(minutes=1)
_H = timedelta(hours=1)
_E, _W = ClockKind.EVENT, ClockKind.WALL

TIMERS: dict[str, Timer] = {
    "holt_warmup": Timer(_E, 10 * _M),
    "rising_streak": Timer(_E, 5 * _M),
    "binomial_window": Timer(_E, 5 * _M),
    "corroboration_window": Timer(_E, 5 * _M),
    "grouping_window": Timer(_E, 10 * _M),
    "cooldown": Timer(_E, 15 * _M),
    "recheck": Timer(_E, 3 * _M, limit=2),
    "approval_expiry": Timer(_W, 10 * _M),
    "containment_ttl_throttle": Timer(_W, 15 * _M),
    "containment_ttl_mfa": Timer(_W, 30 * _M),
    "post_action_verification": Timer(_W, timedelta(seconds=60)),
    "circuit_breaker": Timer(_W, _H, limit=5),
    "page_limit": Timer(_W, _H, limit=6),
    "feedback_half_life": Timer(_W, 24 * _H),
    "ui_eta_countdown": Timer(_E, None),
}
