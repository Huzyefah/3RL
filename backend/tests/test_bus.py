import asyncio

import pytest

from sentinel.bus import InMemoryBus


async def test_bus_backpressure():
    bus = InMemoryBus(maxsize=2)
    await bus.publish({"n": 1})
    await bus.publish({"n": 2})
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(bus.publish({"n": 3}), timeout=0.05)


async def test_bus_fifo():
    bus = InMemoryBus(maxsize=10)
    for i in range(3):
        await bus.publish({"n": i})
    assert [(await bus.get())["n"] for _ in range(3)] == [0, 1, 2]
