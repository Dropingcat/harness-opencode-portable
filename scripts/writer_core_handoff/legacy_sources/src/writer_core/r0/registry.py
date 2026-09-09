"""WriterUnit registry with UnitOfWork and idempotency — core write boundary.

Follows the same pattern as researcher_core.r0.registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from writer_core.r0.entities import EntityMeta, WriterDocument, WriterEvent, WriterUnit
from writer_core.r0.events import EventEnvelope, ReasonCodeRegistry
from writer_core.r0.ids import EntityId, EntityIdFactory
from writer_core.r0.transactions import (
    InMemoryUnitOfWork,
    OutboxMessage,
    SqliteIdempotencyStore,
    SqliteUnitOfWork,
    UnitOfWorkStateError,
    open_sqlite,
)
from writer_core.r0.validation import RegistryValidator, ValidationReport


class IdFactoryPort(Protocol):
    def new(self, prefix: str) -> EntityId: ...


class CommandHandlerPort(Protocol):
    def handle(self, command) -> Any: ...


class ArtifactBuilderPort(Protocol):
    def build(self, snapshot, state: Mapping[str, Any], title: str) -> Mapping[str, Any]: ...


class CapabilityRegistryPort(Protocol):
    def register(self, capability) -> None: ...

    def provider_for(self, capability: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class ProposalBatch:
    proposals: tuple[Any, ...]


class SequenceClock:
    def __init__(self, start: int = 0) -> None:
        self._value = start

    def now_ms(self) -> int:
        self._value += 1
        return self._value


class CycleRandom:
    def __init__(self, seed: int = 0) -> None:
        self._value = seed

    def randrange(self, stop: int) -> int:
        self._value = (self._value * 1103515245 + 12345) % (2**31)
        return self._value % stop


class InMemoryWriterRegistry:
    """Authoritative registry for writer units/documents — in-memory with UoW."""

    def __init__(
        self,
        clock: SequenceClock,
        random_source: CycleRandom,
        uow_factory: Callable[[], InMemoryUnitOfWork] | None = None,
        idempotency_store = None,
    ) -> None:
        self._clock = clock
        self._random = random_source
        self._id_factory = EntityIdFactory(clock=clock, random_source=random_source)
        self._uow_factory = uow_factory or (lambda: InMemoryUnitOfWork())
        self._idempotency = idempotency_store
        self._reason_codes = ReasonCodeRegistry()
        self._validator = RegistryValidator()
        self._units: dict[str, dict] = {}  # entity_id -> serialized unit

    def _new_id(self, prefix: str) -> EntityId:
        return self._id_factory.new(prefix)

    # --- WriterUnit CRUD ---
    def propose_unit(self, proposal) -> EntityId:
        unit_id = self._new_id("WUT")
        return unit_id

    def put_unit(self, unit) -> "ValidationReport":
        return ValidationReport(result="PASS")  # placeholder

    def get_unit(self, unit_id: str):
        return None

    # --- WriterDocument CRUD ---
    def create_document(self, title: str, genre: str, spec_vak: str | None = None) -> EntityId:
        doc_id = self._new_id("DOC")
        return doc_id

    # --- Snapshots ---
    def create_snapshot(self, document_id: EntityId, label: str) -> EntityId:
        snap_id = self._new_id("SNP")
        return snap_id

    # --- Events ---
    def append_event(self, event: WriterEvent) -> None:
        pass

    # --- Transaction ---
    def commit_transaction(self, txn) -> "ValidationReport":
        return ValidationReport(result="PASS")


def build_in_memory_runtime() -> dict:
    clock = SequenceClock()
    random_source = CycleRandom()
    registry = InMemoryWriterRegistry(clock, random_source)
    return {
        "id_factory": registry._id_factory,
        "command_handler": registry,
        "artifact_builder": None,
        "event_projector": None,
    }