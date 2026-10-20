from datetime import UTC, datetime, timedelta

import pytest

from sentinel.bus import InMemoryBus
from sentinel.clock import EventClock
from sentinel.datagen.replay import Replayer
from sentinel.schemas import CES

from ._replay_fixtures import make_dataset

pytestmark = pytest.mark.unit


class FakeSleep:
    def __init__(self) -> None:
        self.calls: list[float] = []

    async def __call__(self, s: float) -> None:
        self.calls.append(s)


class Gate:
    def __init__(self, busy_fn=lambda: False) -> None:
        self.busy_fn = busy_fn

    def busy(self) -> bool:
        return self.busy_fn()


async def _collect(rp: Replayer, bus: InMemoryBus, **run_kw):
    sub = bus.subscribe("telemetry")
    await rp.run(**run_kw)
    out = []
    while not sub.queue.empty():
        out.append(sub.queue.get_nowait())
    return out


def _metric_msgs(msgs):
    return [m for m in msgs if m and m[0].kind == "metric"]


async def test_replay_by_episode_id():
    bus = InMemoryBus()
    rp = Replayer(make_dataset(), bus, EventClock(), speed=0, sleep=FakeSleep())
    msgs = _metric_msgs(await _collect(rp, bus, episode_id="INC-0001"))
    tss = {c.ts for m in msgs for c in m}
    # [02:00-90m, 02:40+30m] = [00:30, 03:10]
    assert min(tss) == datetime(2026, 1, 1, 0, 30, tzinfo=UTC)
    assert max(tss) == datetime(2026, 1, 1, 3, 10, tzinfo=UTC)


async def test_replay_one_message_per_service_per_tick():
    bus = InMemoryBus()
    w = (datetime(2026, 1, 1, 1, 0), datetime(2026, 1, 1, 1, 1))
    rp = Replayer(make_dataset(), bus, EventClock(), speed=0, sleep=FakeSleep())
    msgs = _metric_msgs(await _collect(rp, bus, window=w))
    keys = [(m[0].ts, m[0].service) for m in msgs]
    assert len(keys) == len(set(keys)) == 4  # 2 ticks x 2 services
    a_even = next(m for m in msgs if m[0].service == "svc-a" and m[0].ts.minute == 0)
    assert {(c.metric, c.segment_key) for c in a_even} == {
        ("latency", "*"), ("errors", "*"), ("fail_rate", "bank=BANK_C")
    }  # fmt: skip
    seg = next(c for c in a_even if c.segment_key != "*")
    assert (seg.n_total, seg.n_bad, seg.direction) == (50, 5, "higher_bad")
    assert all(isinstance(c, CES) for c in a_even)


async def test_logs_and_changes_published_at_their_timestamps():
    bus = InMemoryBus()
    w = (datetime(2026, 1, 1, 1, 40), datetime(2026, 1, 1, 1, 41))
    rp = Replayer(make_dataset(), bus, EventClock(), speed=0, sleep=FakeSleep())
    msgs = await _collect(rp, bus, window=w)
    flat = [c for m in msgs for c in m]
    log = next(c for c in flat if c.kind == "log")
    chg = next(c for c in flat if c.kind == "change")
    assert log.ts == datetime(2026, 1, 1, 1, 40, tzinfo=UTC) and log.service == "svc-a"
    assert chg.ts == datetime(2026, 1, 1, 1, 41, tzinfo=UTC)
    assert chg.event_id.endswith("EV-1") or chg.attributes["event_id"] == "EV-1"


async def test_event_clock_advanced_before_publish():
    seen: list[tuple[datetime, datetime]] = []
    clock = EventClock()

    class SpyBus(InMemoryBus):
        async def publish(self, topic, msg):
            seen.append((clock.now(), msg[0].ts))  # pyright: ignore
            await super().publish(topic, msg)

    rp = Replayer(make_dataset(), SpyBus(), clock, speed=0, sleep=FakeSleep())
    await rp.run(window=(datetime(2026, 1, 1, 1, 0), datetime(2026, 1, 1, 1, 3)))
    assert seen and all(c == ts for c, ts in seen)


async def test_replay_agent_paced():
    sleep = FakeSleep()
    state = {"busy": False}
    rp = Replayer(make_dataset(), InMemoryBus(), EventClock(), speed=60.0,
                  gate=Gate(lambda: state["busy"]), sleep=sleep)  # fmt: skip
    speeds: list[float] = []

    def progress(ts: datetime, n: int) -> None:
        speeds.append(rp.current_speed)
        # busy set after the 01:01 and 01:02 ticks, so those two ticks run at 1x
        state["busy"] = ts.minute in (1, 2)

    rp.on_progress = progress
    await rp.run(window=(datetime(2026, 1, 1, 1, 0), datetime(2026, 1, 1, 1, 5)))
    assert sleep.calls == [1.0, 60.0, 60.0, 1.0, 1.0, 1.0]
    assert rp.current_speed == 60.0


async def test_replay_unbounded_speed_never_sleeps():
    sleep = FakeSleep()
    rp = Replayer(make_dataset(), InMemoryBus(), EventClock(), speed=0, sleep=sleep)
    await rp.run(window=(datetime(2026, 1, 1, 1, 0), datetime(2026, 1, 1, 1, 3)))
    assert sleep.calls == []


async def test_replay_event_ids_deterministic():
    async def ids():
        bus = InMemoryBus()
        rp = Replayer(make_dataset(), bus, EventClock(), speed=0, sleep=FakeSleep())
        msgs = await _collect(rp, bus, window=(datetime(2026, 1, 1, 1, 0),
                                               datetime(2026, 1, 1, 1, 3)))  # fmt: skip
        return [c.event_id for m in msgs for c in m]

    a, b = await ids(), await ids()
    assert a == b and len(set(a)) == len(a)


async def test_replay_stop():
    bus = InMemoryBus()
    rp = Replayer(make_dataset(), bus, EventClock(), speed=0, sleep=FakeSleep())
    n = 0

    def progress(ts: datetime, count: int) -> None:
        nonlocal n
        n += 1
        if n == 3:
            rp.stop()

    rp.on_progress = progress
    await rp.run()
    assert n == 3


async def test_replay_pause_blocks_until_resume():
    import asyncio

    rp = Replayer(make_dataset(), InMemoryBus(), EventClock(), speed=0, sleep=FakeSleep())
    ticks: list[datetime] = []
    rp.on_progress = lambda ts, n: ticks.append(ts)
    rp.pause()
    task = asyncio.create_task(rp.run(window=(datetime(2026, 1, 1, 1, 0),
                                              datetime(2026, 1, 1, 1, 2))))  # fmt: skip
    await asyncio.sleep(0.01)
    assert ticks == []
    rp.resume()
    await task
    assert len(ticks) == 3
    assert ticks[-1] - ticks[0] == timedelta(minutes=2)
