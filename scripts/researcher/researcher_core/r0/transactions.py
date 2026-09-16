"""In-memory UnitOfWork primitives for R0 transaction bubble tests."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from researcher_core.r0.events import EventEnvelope, _deep_freeze
from researcher_core.r0.ids import EntityId


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    message_type: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.message_type:
            raise ValueError("message_type is required")
        object.__setattr__(self, "payload", _deep_freeze(self.payload))


class UnitOfWorkStateError(RuntimeError):
    """Raised when a transaction operation is used outside its lifecycle."""


class InMemoryUnitOfWork:
    """Atomic in-memory stand-in for SQLite-backed UnitOfWork.

    It is deliberately small: enough to test commit/rollback and replay
    invariants before introducing infrastructure code.
    """

    def __init__(self) -> None:
        self.state: dict[EntityId, Mapping[str, Any]] = {}
        self.events: list[EventEnvelope] = []
        self.outbox: list[OutboxMessage] = []
        self.rejections: list[tuple[EntityId, Any]] = []
        self._active = False
        self._closed = False
        self._pending_state: dict[EntityId, Mapping[str, Any]] = {}
        self._pending_events: list[EventEnvelope] = []
        self._pending_outbox: list[OutboxMessage] = []
        self._pending_rejections: list[tuple[EntityId, Any]] = []

    def __enter__(self) -> "InMemoryUnitOfWork":
        if self._active or self._closed:
            raise UnitOfWorkStateError("unit of work cannot be re-entered")
        self._active = True
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        if exc_type is not None:
            self.rollback()
            return False
        if self._active:
            self.rollback()
        return False

    def put_state(self, entity_id: EntityId, row: Mapping[str, Any]) -> None:
        self._require_active()
        self._pending_state[entity_id] = _deep_freeze(row)

    def append_event(self, event: EventEnvelope) -> None:
        self._require_active()
        self._pending_events.append(event)

    def enqueue_outbox(self, message: OutboxMessage) -> None:
        self._require_active()
        self._pending_outbox.append(message)

    def put_rejection(self, command_id: EntityId, report: Any) -> None:
        self._require_active()
        self._pending_rejections.append((command_id, report))

    def commit(self) -> None:
        self._require_active()
        self.state.update(self._pending_state)
        self.events.extend(self._pending_events)
        self.outbox.extend(self._pending_outbox)
        self.rejections.extend(self._pending_rejections)
        self._finish()

    def rollback(self) -> None:
        self._require_active()
        self._finish()

    def state_view(self) -> Mapping[EntityId, Mapping[str, Any]]:
        return MappingProxyType(self.state)

    def _finish(self) -> None:
        self._pending_state = {}
        self._pending_events = []
        self._pending_outbox = []
        self._pending_rejections = []
        self._active = False
        self._closed = True

    def _require_active(self) -> None:
        if not self._active:
            raise UnitOfWorkStateError("unit of work is not active")
