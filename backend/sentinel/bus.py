"""Event bus. InMemoryBus for local mode and demo replay; Pub/Sub mirroring is added in Phase 3."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol


class Bus(Protocol):
    async def publish(self, message: dict[str, Any]) -> None: ...

    async def get(self) -> dict[str, Any]: ...


class InMemoryBus:
    """Bounded FIFO. `publish` blocks when full, which gives natural backpressure to the replayer."""

    def __init__(self, maxsize: int = 10_000) -> None:
        self._q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)

    async def publish(self, message: dict[str, Any]) -> None:
        await self._q.put(message)

    async def get(self) -> dict[str, Any]:
        return await self._q.get()

    def qsize(self) -> int:
        return self._q.qsize()
