import asyncio

import pytest
from pydantic import BaseModel

from sentinel.bus import InMemoryBus, PubSubBus


class Msg(BaseModel):
    n: int


@pytest.mark.unit
async def test_ordering_per_topic():
    bus = InMemoryBus()
    sub = bus.subscribe("a")
    for i in range(5):
        await bus.publish("a", Msg(n=i))
    assert [(await anext(sub)).n for _ in range(5)] == [0, 1, 2, 3, 4]


@pytest.mark.unit
async def test_fan_out_and_topic_isolation():
    bus = InMemoryBus()
    s1, s2, other = bus.subscribe("a"), bus.subscribe("a"), bus.subscribe("b")
    await bus.publish("a", {"x": 1})
    assert await anext(s1) == {"x": 1}
    assert await anext(s2) == {"x": 1}
    await bus.publish("b", {"y": 2})
    assert await anext(other) == {"y": 2}


@pytest.mark.unit
async def test_no_replay_for_late_subscriber_and_aclose():
    bus = InMemoryBus()
    await bus.publish("a", {"old": 1})
    sub = bus.subscribe("a")
    await bus.publish("a", {"new": 1})
    assert await anext(sub) == {"new": 1}
    await sub.aclose()
    await bus.publish("a", {"z": 1})  # no subscribers left; must not block
    with pytest.raises(StopAsyncIteration):
        await anext(sub)


@pytest.mark.unit
async def test_bus_backpressure():
    bus = InMemoryBus(maxsize=2)
    sub = bus.subscribe("a")
    await bus.publish("a", Msg(n=0))
    await bus.publish("a", Msg(n=1))
    third = asyncio.create_task(bus.publish("a", Msg(n=2)))
    await asyncio.sleep(0.01)
    assert not third.done()  # bounded: publisher blocks while the queue is full
    assert (await anext(sub)).n == 0  # consumer drains one slot
    await asyncio.wait_for(third, timeout=1)
    assert [(await anext(sub)).n for _ in range(2)] == [1, 2]


@pytest.mark.unit
async def test_pubsub_bus_is_a_stub():
    bus = PubSubBus()
    with pytest.raises(NotImplementedError):
        await bus.publish("a", {})
    with pytest.raises(NotImplementedError):
        bus.subscribe("a")


@pytest.mark.unit
async def test_closing_subscriber_unblocks_blocked_publisher():
    bus = InMemoryBus(maxsize=1)
    sub = bus.subscribe("a")
    await bus.publish("a", Msg(n=0))
    blocked = asyncio.create_task(bus.publish("a", Msg(n=1)))
    await asyncio.sleep(0.01)
    assert not blocked.done()
    await sub.aclose()
    await asyncio.wait_for(blocked, timeout=1)


@pytest.mark.unit
async def test_closed_subscriber_does_not_block_later_subscribers():
    bus = InMemoryBus(maxsize=1)
    stuck = bus.subscribe("a")
    live = bus.subscribe("a")
    await bus.publish("a", Msg(n=0))
    blocked = asyncio.create_task(bus.publish("a", Msg(n=1)))
    await asyncio.sleep(0.01)
    await stuck.aclose()
    assert (await anext(live)).n == 0
    await asyncio.wait_for(blocked, timeout=1)
    assert (await anext(live)).n == 1


@pytest.mark.unit
async def test_context_manager_unsubscribes_on_break():
    bus = InMemoryBus(maxsize=1)
    async with bus.subscribe("a") as sub:
        await bus.publish("a", Msg(n=0))
        async for msg in sub:
            assert msg.n == 0
            break
    for i in range(3):  # no live subscriber left: must not block
        await asyncio.wait_for(bus.publish("a", Msg(n=i)), timeout=1)


@pytest.mark.unit
async def test_cancelled_consumer_does_not_wedge_publisher():
    bus = InMemoryBus(maxsize=1)
    started = asyncio.Event()

    async def consume() -> None:
        async with bus.subscribe("a") as sub:
            started.set()
            async for _ in sub:
                await asyncio.sleep(10)

    task = asyncio.create_task(consume())
    await started.wait()
    await bus.publish("a", Msg(n=0))
    await asyncio.sleep(0.01)  # consumer took n=0 and is sleeping
    await bus.publish("a", Msg(n=1))  # fills the queue
    blocked = asyncio.create_task(bus.publish("a", Msg(n=2)))
    await asyncio.sleep(0.01)
    assert not blocked.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(blocked, timeout=1)
    await asyncio.wait_for(bus.publish("a", Msg(n=3)), timeout=1)


@pytest.mark.unit
async def test_late_subscriber_gets_no_replay_with_context_manager():
    bus = InMemoryBus()
    await bus.publish("a", {"old": 1})
    async with bus.subscribe("a") as sub:
        await bus.publish("a", {"new": 1})
        assert await anext(sub) == {"new": 1}
