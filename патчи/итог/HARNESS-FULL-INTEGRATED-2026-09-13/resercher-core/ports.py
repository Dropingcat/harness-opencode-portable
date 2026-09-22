"""Scalable architecture ports for Researcher Core.

Ports are stable seams. Domain/application code depends on these shapes; SQLite,
MCP, real YAML writers, and other infrastructure can be added as adapters.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from researcher_core.capsules import Capsule, CapsuleObservation, CapsuleRequest
from researcher_core.r0.commands import CommandEnvelope, CommandResult
from researcher_core.r0.events import EventEnvelope
from researcher_core.r0.ids import EntityId
from researcher_core.r0.projections import ProjectableEntity, Snapshot
from researcher_core.r0.transactions import OutboxMessage


@runtime_checkable
class ClockPort(Protocol):
    def now_ms(self) -> int: ...


@runtime_checkable
class IdFactoryPort(Protocol):
    def new(self, prefix: str) -> EntityId: ...


@runtime_checkable
class CommandHandlerPort(Protocol):
    def execute(self, command: CommandEnvelope) -> CommandResult: ...


@runtime_checkable
class UnitOfWorkPort(Protocol):
    def __enter__(self) -> "UnitOfWorkPort": ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool: ...
    def put_state(self, entity_id: EntityId, row: Mapping[str, Any]) -> None: ...
    def append_event(self, event: EventEnvelope) -> None: ...
    def enqueue_outbox(self, message: OutboxMessage) -> None: ...
    def put_rejection(self, command_id: EntityId, report: Any) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


@runtime_checkable
class EventProjectorPort(Protocol):
    def rebuild_state(self, events: Sequence[EventEnvelope]) -> Mapping[str, ProjectableEntity]: ...


@runtime_checkable
class CapabilityRegistryPort(Protocol):
    def register(self, capsule: Capsule) -> None: ...
    def provider_for(self, capability: str) -> Capsule: ...
    def capabilities(self) -> Mapping[str, str]: ...


@runtime_checkable
class CapsuleRunnerPort(Protocol):
    def run(self, request: CapsuleRequest) -> CapsuleObservation: ...


@runtime_checkable
class ArtifactBuilderPort(Protocol):
    def build(self, snapshot: Snapshot, state: Mapping[str, ProjectableEntity], title: str) -> Mapping[str, Any]: ...
    def render(self, artifact: Mapping[str, Any]) -> str: ...
