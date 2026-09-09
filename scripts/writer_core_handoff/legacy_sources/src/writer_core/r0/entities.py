"""R0 entity contracts for writer-core.

Immutable, frozen dataclasses with __post_init__ validation.
Follows the same pattern as researcher_core.r0.entities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping, Optional

from writer_core.r0.enums import (
    ObjectKind,
    ValidationResult,
    WriterEligibility,
    WriterUnitStatus,
    WriterUnitType,
)
from writer_core.r0.events import _deep_freeze
from writer_core.r0.ids import EntityId


# Keys that must not appear in unit.attributes (reserved for authoritative links)
FORBIDDEN_UNIT_LINK_KEYS = frozenset({
    "depends_on", "derived_from", "supports", "contradicts", "cites"
})


def _validate_namespace(id_obj: EntityId, expected: str) -> None:
    if id_obj.namespace != expected:
        raise ValueError(f"id must use {expected} prefix, got {id_obj.namespace!r}")


def _collapsed_text(value: Any) -> str:
    """Normalize text: strip, collapse whitespace, lowercase."""
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.strip().lower().split())
    return ""


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_hex64(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value)


def _entity_namespace(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value.split("_", maxsplit=1)[0] if "_" in value else None
    if hasattr(value, "namespace"):
        return value.namespace
    return None


def _mapping_get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    if hasattr(value, "__dict__"):
        return getattr(value, key, default)
    return default


def _sequence(value: Any) -> tuple[Any, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(value)
    if value is None:
        return ()
    return (value,)


@dataclass(frozen=True, slots=True)
class EntityMeta:
    id: EntityId
    schema_version: str
    revision: int
    run_id: EntityId
    created_at: datetime
    created_by: str  # ActorRef as string for writer-core

    def __post_init__(self) -> None:
        if not self.schema_version:
            raise ValueError("schema_version is required")
        if self.revision < 1:
            raise ValueError("revision must be positive")
        if self.run_id.namespace != "RUN":
            raise ValueError("run_id must use RUN prefix")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        object.__setattr__(self, "created_at", self.created_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class WriterUnitProposal:
    """Untrusted input from capsule/LLM — never authoritative."""

    temp_id: str
    unit_type: WriterUnitType
    text: str
    object_payload: Mapping[str, Any] | None = None
    extraction_run_id: EntityId | None = None

    def __post_init__(self) -> None:
        if not self.temp_id:
            raise ValueError("temp_id is required")
        if self.unit_type == WriterUnitType.OBJECT and not self.object_payload:
            raise ValueError("object_payload required for OBJECT type")
        if self.unit_type != WriterUnitType.OBJECT and self.object_payload:
            raise ValueError("object_payload only allowed for OBJECT type")
        if self.extraction_run_id and self.extraction_run_id.namespace != "OPR":
            raise ValueError("extraction_run_id must use OPR prefix")


@dataclass(frozen=True, slots=True)
class WriterUnit:
    """Authoritative writer unit: paragraph, assertion, object, or section."""

    meta: EntityMeta
    unit_type: WriterUnitType
    text: str
    object_payload: Mapping[str, Any] = field(default_factory=dict)
    status: WriterUnitStatus = WriterUnitStatus.DRAFT
    provenance: tuple[str, ...] = ()           # claim/evidence refs: CLM_..., EVD_...
    review_checklist: Mapping[str, Any] = field(default_factory=dict)
    review_verdict: str | None = None
    reviewer: str | None = None
    Toulmin_role: str | None = None           # Toulmin role for assertions
    scope: Mapping[str, Any] = field(default_factory=dict)  # scope dimensions
    gaps: tuple[str, ...] = ()                # gap IDs
    conflicts: tuple[str, ...] = ()           # conflict IDs
    vector: tuple[float, ...] = ()            # embedding vector (optional)

    def __post_init__(self) -> None:
        _validate_namespace(self.meta.id, "WUT")
        if not self.text and self.unit_type != WriterUnitType.OBJECT:
            raise ValueError("text is required for non-OBJECT units")
        if self.unit_type == WriterUnitType.OBJECT:
            if "kind" not in self.object_payload:
                raise ValueError("object_payload must contain 'kind'")
            kind = self.object_payload["kind"]
            if isinstance(kind, ObjectKind):
                kind = kind.value
            if kind not in {k.value for k in ObjectKind}:
                raise ValueError(f"unknown object kind: {kind}")
        object.__setattr__(self, "object_payload", MappingProxyType(dict(self.object_payload)))


@dataclass(frozen=True, slots=True)
class WriterDocument:
    """Root document entity: dissertation, article, monograph, etc."""

    meta: EntityMeta
    title: str
    genre: str
    spec_vak: str | None = None
    gost: str | None = None
    language: str = "ru"
    spec_version: str = "1.0"
    author_persona: str | None = None
    budget: Mapping[str, Any] = field(default_factory=dict)
    skeleton: Mapping[str, Any] = field(default_factory=dict)
    parts: tuple[EntityId, ...] = ()          # for book/monograph
    chapters: tuple[EntityId, ...] = ()       # flat list for simple genres
    macro_claims: tuple[dict, ...] = ()       # macro-claims aggregated from units
    vector_state: Mapping[str, Any] = field(default_factory=dict)  # paragraph/chapter/work vectors
    target_vector: tuple[float, ...] = ()     # target vector for convergence
    convergence_criterion: float = 0.85
    writer_context: Mapping[str, Any] = field(default_factory=dict)
    convergence_history: tuple[dict, ...] = ()

    def __post_init__(self) -> None:
        _validate_namespace(self.meta.id, "DOC")
        if not self.title:
            raise ValueError("title is required")
        for uid in self.parts:
            if uid.namespace != "WUT":
                raise ValueError("parts must contain WUT IDs only")
        for uid in self.chapters:
            if uid.namespace != "WUT":
                raise ValueError("chapters must contain WUT IDs only")


@dataclass(frozen=True, slots=True)
class WriterTransaction:
    """Atomic multi-unit change (commit unit)."""

    meta: EntityMeta
    unit_changes: Mapping[EntityId, Mapping[str, Any]]  # id -> new fields
    unit_additions: tuple[WriterUnit, ...] = ()
    unit_deletions: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        _validate_namespace(self.meta.id, "TXN")


@dataclass(frozen=True, slots=True)
class WriterSnapshot:
    """Named document state for rollback/diff."""

    meta: EntityMeta
    document_id: EntityId
    label: str
    unit_states: Mapping[EntityId, Mapping[str, Any]]  # serialized units

    def __post_init__(self) -> None:
        _validate_namespace(self.meta.id, "SNP")
        if not self.label:
            raise ValueError("snapshot label is required")
        if self.document_id.namespace != "DOC":
            raise ValueError("document_id must use DOC prefix")


@dataclass(frozen=True, slots=True)
class WriterEvent:
    """Append-only event log entry."""

    meta: EntityMeta
    event_type: str
    aggregate_id: EntityId
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        _validate_namespace(self.meta.id, "EVT")


@dataclass(frozen=True, slots=True)
class ObjectPayload:
    """Structured payload for OBJECT units."""

    kind: ObjectKind
    value: Any = None
    unit: str | None = None
    dimension: str | None = None
    lower: Decimal | None = None
    upper: Decimal | None = None
    formula: str | None = None
    variables: Mapping[str, Any] = field(default_factory=dict)
    citation: str | None = None
    term: str | None = None

    def __post_init__(self) -> None:
        if self.kind == ObjectKind.NUMBER:
            if self.value is None:
                raise ValueError("NUMBER object requires value")
            if self.unit is None:
                raise ValueError("NUMBER object requires unit")
            if self.dimension is None:
                raise ValueError("NUMBER object requires dimension")
        if self.kind == ObjectKind.FORMULA:
            if self.formula is None:
                raise ValueError("FORMULA object requires formula")
        if self.kind == ObjectKind.CITATION:
            if self.citation is None:
                raise ValueError("CITATION object requires citation")


@dataclass(frozen=True, slots=True)
class UnitRelation:
    """Relation between two writer units."""

    from_id: EntityId
    to_id: EntityId
    relation_type: str  # SUPPORTS, CONTRADICTS, DERIVED_FROM, CITES, PARENT_OF, CHILD_OF
    weight: float = 1.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.from_id == self.to_id:
            raise ValueError("relation cannot be self-referential")