"""Message bus port with an in-memory adapter.

Payloads are generic (pydantic models or dicts); the bus knows nothing about schemas.

Backpressure policy: every subscriber has a bounded queue. ``publish`` awaits until
every LIVE subscriber of the topic has room, so a slow consumer slows the publisher
instead of dropping messages or growing memory. A subscriber that closes (``aclose()``
or leaving ``async with``) stops counting immediately, even while the publisher is
blocked on it. Delivery is ordered per topic. A subscriber only sees messages published
after it subscribed (no replay). Use ``async with bus.subscribe(t) as sub`` so a
consumer that breaks out or is cancelled unsubscribes.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from typing import Any, Protocol

from pydantic import BaseModel

Message = BaseModel | Mapping[str, Any]


class Bus(Protocol):
    async def publish(self, topic: str, msg: Message) -> None: ...

    def subscribe(self, topic: str) -> AsyncIterator[Any]: ...


class _Closed:
    pass


_CLOSED = _Closed()


class Subscription:
    """Async iterator over one topic. Call ``aclose()`` to unsubscribe."""

    def __init__(self, bus: InMemoryBus, topic: str, maxsize: int) -> None:
        self._bus = bus
        self._topic = topic
        self.queue: asyncio.Queue[Any] = asyncio.Queue(maxsize)
        self._closed = False
        self._closed_event = asyncio.Event()

    async def __aenter__(self) -> Subscription:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def _deliver(self, msg: Any) -> None:
        """Put ``msg``, blocking while full, but give up as soon as we are closed."""
        if self._closed:
            return
        if not self.queue.full():
            self.queue.put_nowait(msg)
            return
        put = asyncio.ensure_future(self.queue.put(msg))
        closed = asyncio.ensure_future(self._closed_event.wait())
        try:
            await asyncio.wait({put, closed}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            put.cancel()
            closed.cancel()

    def __aiter__(self) -> Subscription:
        return self

    async def __anext__(self) -> Any:
        if self._closed:
            raise StopAsyncIteration
        item = await self.queue.get()
        if item is _CLOSED:
            raise StopAsyncIteration
        return item

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._closed_event.set()
        self._bus._remove(self._topic, self)
        while not self.queue.empty():
            self.queue.get_nowait()
        try:
            self.queue.put_nowait(_CLOSED)  # wake a blocked consumer
        except asyncio.QueueFull:  # a woken putter refilled it; no consumer is waiting
            pass


class InMemoryBus:
    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._subs: dict[str, list[Subscription]] = {}

    async def publish(self, topic: str, msg: Message) -> None:
        for sub in list(self._subs.get(topic, ())):
            await sub._deliver(msg)

    def subscribe(self, topic: str) -> Subscription:
        sub = Subscription(self, topic, self._maxsize)
        self._subs.setdefault(topic, []).append(sub)
        return sub

    def _remove(self, topic: str, sub: Subscription) -> None:
        subs = self._subs.get(topic, [])
        if sub in subs:
            subs.remove(sub)


class PubSubBus:
    """Google Pub/Sub adapter, deferred until the GCP phase."""

    async def publish(self, topic: str, msg: Message) -> None:
        raise NotImplementedError("PubSubBus arrives with the GCP phase")

    def subscribe(self, topic: str) -> AsyncIterator[Any]:
        raise NotImplementedError("PubSubBus arrives with the GCP phase")
