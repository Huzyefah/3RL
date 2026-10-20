from datetime import UTC, datetime, timedelta

import pytest

from sentinel.clock import EventClock, FrozenClock
from sentinel.scheduler import Scheduler

T0 = datetime(2026, 8, 1, 3, 0, tzinfo=UTC)
M = timedelta(minutes=1)


@pytest.mark.unit
async def test_scheduler_fires_in_event_time():
    clock = EventClock()
    clock.advance_to(T0)
    sched = Scheduler(clock)
    fired: list[str] = []

    async def h(name: str) -> None:
        fired.append(name)

    sched.schedule(T0 + 3 * M, "b", lambda: h("b"))
    sched.schedule(T0 + 1 * M, "a", lambda: h("a"))
    assert await sched.tick() == []
    clock.advance_to(T0 + 2 * M)
    assert await sched.tick() == ["a"]
    clock.advance_to(T0 + 10 * M)
    assert await sched.tick() == ["b"]
    assert await sched.tick() == []  # fired jobs are removed
    assert fired == ["a", "b"]


@pytest.mark.unit
async def test_scheduler_frozen_clock_sync_handler_and_order():
    clock = FrozenClock(T0)
    sched = Scheduler(clock)
    fired: list[str] = []
    sched.schedule(T0 + 2 * M, "late", lambda: fired.append("late"))
    sched.schedule(T0 + 1 * M, "early", lambda: fired.append("early"))
    clock.advance(5 * M)
    assert await sched.tick() == ["early", "late"]
    assert fired == ["early", "late"]


@pytest.mark.unit
async def test_scheduler_cancel():
    clock = FrozenClock(T0)
    sched = Scheduler(clock)
    fired: list[str] = []
    sched.schedule(T0 + M, "k", lambda: fired.append("k"))
    assert sched.cancel("k") is True
    assert sched.cancel("k") is False
    clock.advance(2 * M)
    assert await sched.tick() == []
    assert fired == []


@pytest.mark.unit
async def test_scheduler_duplicate_key_replaces():
    clock = FrozenClock(T0)
    sched = Scheduler(clock)
    fired: list[str] = []
    sched.schedule(T0 + M, "k", lambda: fired.append("old"))
    sched.schedule(T0 + 5 * M, "k", lambda: fired.append("new"))
    assert sched.pending() == ["k"]
    clock.advance(2 * M)
    assert await sched.tick() == []  # replaced: the earlier time no longer applies
    clock.advance(4 * M)
    assert await sched.tick() == ["k"]
    assert fired == ["new"]


@pytest.mark.unit
async def test_scheduler_handler_error_does_not_kill_tick():
    clock = FrozenClock(T0)
    sched = Scheduler(clock)
    fired: list[str] = []

    def boom() -> None:
        raise RuntimeError("boom")

    sched.schedule(T0 + M, "bad", boom)
    sched.schedule(T0 + 2 * M, "good", lambda: fired.append("good"))
    clock.advance(3 * M)
    assert await sched.tick() == ["bad", "good"]
    assert fired == ["good"]
    assert sched.errors and sched.errors[0][0] == "bad"


@pytest.mark.unit
async def test_scheduler_handler_may_reschedule_itself():
    clock = FrozenClock(T0)
    sched = Scheduler(clock)
    count = 0

    def again() -> None:
        nonlocal count
        count += 1
        if count < 2:
            sched.schedule(T0 + M, "r", again)  # already due, fires next tick

    sched.schedule(T0 + M, "r", again)
    clock.advance(2 * M)
    await sched.tick()
    await sched.tick()
    assert count == 2


@pytest.mark.unit
async def test_scheduler_run_loop_wall_mode():
    import asyncio

    clock = FrozenClock(T0)
    sched = Scheduler(clock)
    done = asyncio.Event()
    sched.schedule(T0 + M, "k", done.set)
    task = asyncio.create_task(sched.run(poll_interval=0.001))
    clock.advance(2 * M)
    await asyncio.wait_for(done.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
