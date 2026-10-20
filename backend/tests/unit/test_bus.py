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
