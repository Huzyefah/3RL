"""Clock-driven in-process scheduler for rechecks, TTLs, expiry and verification.

``tick()`` fires every job whose time is at or before ``clock.now()`` and is the single
entry point: the wall-mode ``run()`` loop calls it, and so will ``/jobs/tick`` (Phase 6).
With an ``EventClock`` the caller advances the clock and ticks; with a ``WallClock``
``run()`` polls.

Keys are idempotent: scheduling an existing key replaces the old job. A job is removed
before its handler runs, so a handler may reschedule its own key (it fires on a later
tick). A failing handler is recorded in ``errors`` and never stops the tick or the loop. If a
handler is cancelled (``CancelledError``) its job is put back (unless the handler already
rescheduled that key) so the job is not lost, and the cancellation propagates.
Datetimes must be timezone-aware.
"""

from __future__ import annotations

import asyncio
import inspect
import itertools
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from sentinel.clock import Clock

log = logging.getLogger(__name__)

Handler = Callable[[], Awaitable[None] | None]


class Scheduler:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._jobs: dict[str, tuple[datetime, int, Handler]] = {}
        self._seq = itertools.count()
        self.errors: list[tuple[str, Exception]] = []

    def schedule(self, at: datetime, key: str, handler: Handler) -> None:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError(f"schedule time must be timezone-aware: {at!r}")
        self._jobs[key] = (at, next(self._seq), handler)

    def cancel(self, key: str) -> bool:
        return self._jobs.pop(key, None) is not None

    def pending(self) -> list[str]:
        return sorted(self._jobs, key=lambda k: self._jobs[k][:2])

    async def tick(self) -> list[str]:
        """Fire due jobs in (time, insertion) order; return the keys that fired."""
        now = self._clock.now()
        due = sorted(
            ((at, seq, key) for key, (at, seq, _) in self._jobs.items() if at <= now),
        )
        fired: list[str] = []
        for _, seq, key in due:
            job = self._jobs.get(key)
            if job is None or job[1] != seq:  # cancelled or replaced by an earlier handler
                continue
            del self._jobs[key]
            fired.append(key)
            try:
                result = job[2]()
                if inspect.isawaitable(result):
                    await result
            except asyncio.CancelledError:
                self._jobs.setdefault(key, job)  # keep the job; it was never completed
                if key in fired:
                    fired.remove(key)
                raise
            except Exception as exc:
                log.exception("scheduled job %s failed", key)
                self.errors.append((key, exc))
        return fired

    async def run(self, poll_interval: float = 0.5) -> None:
        """Wall-mode loop; cancel the task to stop it."""
        while True:
            await self.tick()
            await asyncio.sleep(poll_interval)
