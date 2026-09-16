"""Runtime composition helpers.

The current runtime is in-memory, but it is wired through ports so future SQLite,
MCP, and schema-backed artifact adapters can replace pieces independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from pathlib import Path

from researcher_core.artifact_builder import build_minimal_service_artifact, render_artifact_yaml, render_minimal_yaml
from researcher_core.capsules import InMemoryCapabilityRegistry
from researcher_core.ports import ArtifactBuilderPort, CapabilityRegistryPort, CommandHandlerPort, EventProjectorPort, IdFactoryPort
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r0.projections import ProjectableEntity, Snapshot, rebuild_state_from_events
from researcher_core.r0.registry import CycleRandom, InMemoryClaimRegistry, SequenceClock
from researcher_core.r0.sqlite_store import SqliteIdempotencyStore, SqliteUnitOfWork, open_sqlite, rebuild_state_from_sqlite


@dataclass(frozen=True, slots=True)
class MinimalArtifactBuilderAdapter:
    def build(self, snapshot: Snapshot, state: Mapping[str, ProjectableEntity], title: str) -> Mapping[str, Any]:
        return build_minimal_service_artifact(snapshot, state, title)

    def render(self, artifact: Mapping[str, Any]) -> str:
        return render_artifact_yaml(dict(artifact))


@dataclass(frozen=True, slots=True)
class SqliteArtifactBuilderAdapter:
    def build(self, snapshot: Snapshot, state: Mapping[str, ProjectableEntity], title: str) -> Mapping[str, Any]:
        return build_minimal_service_artifact(snapshot, state, title)

    def render(self, artifact: Mapping[str, Any]) -> str:
        return render_artifact_yaml(dict(artifact))


@dataclass(frozen=True, slots=True)
class InMemoryEventProjectorAdapter:
    def rebuild_state(self, events):
        return rebuild_state_from_events(events)


@dataclass(frozen=True, slots=True)
class SqliteEventProjectorAdapter:
    conn: object

    def rebuild_state(self, events):
        return rebuild_state_from_sqlite(self.conn)


@dataclass(frozen=True, slots=True)
class RuntimeServices:
    id_factory: IdFactoryPort
    command_handler: CommandHandlerPort
    capability_registry: CapabilityRegistryPort
    artifact_builder: ArtifactBuilderPort
    event_projector: EventProjectorPort


def build_in_memory_runtime() -> RuntimeServices:
    clock = SequenceClock()
    random_source = CycleRandom()
    id_factory = EntityIdFactory(clock=clock, random_source=random_source)
    return RuntimeServices(
        id_factory=id_factory,
        command_handler=InMemoryClaimRegistry(clock, random_source),
        capability_registry=InMemoryCapabilityRegistry(),
        artifact_builder=MinimalArtifactBuilderAdapter(),
        event_projector=InMemoryEventProjectorAdapter(),
    )


def build_sqlite_runtime(db_path: str | Path = ":memory:") -> RuntimeServices:
    clock = SequenceClock()
    random_source = CycleRandom()
    id_factory = EntityIdFactory(clock=clock, random_source=random_source)
    conn = open_sqlite(db_path)
    registry = InMemoryClaimRegistry(
        clock,
        random_source,
        uow_factory=lambda: SqliteUnitOfWork(conn),
        idempotency_store=SqliteIdempotencyStore(conn),
    )
    # Expose connection for test cleanup / inspection (not part of port)
    try:
        object.__setattr__(registry, "_sqlite_conn", conn)  # type: ignore[attr-defined]
    except Exception:
        registry._sqlite_conn = conn  # type: ignore[attr-defined]
    return RuntimeServices(
        id_factory=id_factory,
        command_handler=registry,
        capability_registry=InMemoryCapabilityRegistry(),
        artifact_builder=SqliteArtifactBuilderAdapter(),
        event_projector=SqliteEventProjectorAdapter(conn),
    )
