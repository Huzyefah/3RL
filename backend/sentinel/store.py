"""Persistence seam. ``Store`` exposes one ``Collection`` per record type.

``MemoryStore`` is the default adapter; ``BigQueryStore`` is a Phase 12 stub. Objects are
copied on the way in and out, so callers can never mutate stored state by accident.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from threading import RLock
from typing import Any, Protocol

from pydantic import BaseModel

from sentinel.schemas import (
    CES,
    ActionRecord,
    Approval,
    Feedback,
    IncidentResult,
    Ticket,
)


class Collection[T: BaseModel](Protocol):
    def put(self, key: str, item: T) -> None: ...
    def get(self, key: str) -> T | None: ...
    def list(self, where: Callable[[T], bool] | None = None) -> list[T]: ...
    def update(self, key: str, **fields: Any) -> T:
        """Merge fields into the stored item and return it; KeyError if absent."""
        ...


class Store(Protocol):
    @property
    def incidents(self) -> Collection[IncidentResult]: ...
    @property
    def tickets(self) -> Collection[Ticket]: ...
    @property
    def actions(self) -> Collection[ActionRecord]: ...
    @property
    def approvals(self) -> Collection[Approval]: ...
    @property
    def feedback(self) -> Collection[Feedback]: ...
    @property
    def events(self) -> Collection[CES]: ...

    def claim_action(self, record: ActionRecord) -> tuple[ActionRecord, bool]:
        """Idempotent insert keyed on ``record.idempotency_key``.

        Returns ``(stored_record, created)``; a repeat returns the original with ``False``.
        """
        ...


class MemoryCollection[T: BaseModel]:
    def __init__(self, lock: AbstractContextManager[Any] | None = None) -> None:
        self._items: dict[str, T] = {}
        self._lock = lock or RLock()

    def put(self, key: str, item: T) -> None:
        with self._lock:
            self._items[key] = item.model_copy(deep=True)

    def get(self, key: str) -> T | None:
        with self._lock:
            item = self._items.get(key)
            return None if item is None else item.model_copy(deep=True)

    def list(self, where: Callable[[T], bool] | None = None) -> list[T]:
        with self._lock:
            items = [i.model_copy(deep=True) for i in self._items.values()]
        return items if where is None else [i for i in items if where(i)]

    def update(self, key: str, **fields: Any) -> T:
        with self._lock:
            current = self._items[key]
            merged = type(current).model_validate({**current.model_dump(), **fields})
            self._items[key] = merged
            return merged.model_copy(deep=True)


class MemoryStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.incidents: MemoryCollection[IncidentResult] = MemoryCollection(self._lock)
        self.tickets: MemoryCollection[Ticket] = MemoryCollection(self._lock)
        self.actions: MemoryCollection[ActionRecord] = MemoryCollection(self._lock)
        self.approvals: MemoryCollection[Approval] = MemoryCollection(self._lock)
        self.feedback: MemoryCollection[Feedback] = MemoryCollection(self._lock)
        self.events: MemoryCollection[CES] = MemoryCollection(self._lock)
        self._by_key: dict[str, str] = {}

    def claim_action(self, record: ActionRecord) -> tuple[ActionRecord, bool]:
        with self._lock:
            existing_id = self._by_key.get(record.idempotency_key)
            if existing_id is not None:
                existing = self.actions.get(existing_id)
                if existing is not None:
                    return existing, False
            self._by_key[record.idempotency_key] = record.action_id
            self.actions.put(record.action_id, record)
            return record.model_copy(deep=True), True


class BigQueryStore:
    """Phase 12 adapter; not implemented."""

    def __init__(self) -> None:
        raise NotImplementedError("BigQueryStore arrives in Phase 12")
