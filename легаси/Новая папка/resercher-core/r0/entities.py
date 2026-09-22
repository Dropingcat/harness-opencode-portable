"""Minimal R0 proposal and entity contracts.

Adapters may create proposals. Authoritative entities are immutable records that
will later be created only by ClaimRegistry factories.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.enums import ClaimStatus
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId


FORBIDDEN_CLAIM_LINK_KEYS = frozenset({"depends_on", "derived_from", "gaps", "conflicts", "children", "parents"})


@dataclass(frozen=True, slots=True)
class EntityMeta:
    id: EntityId
    schema_version: str
    revision: int
    run_id: EntityId
    created_at: datetime
    created_by: ActorRef

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
class ClaimProposal:
    temp_id: str
    proposition: str
    proposed_type: str
    proposed_scope: Mapping[str, Any]
    source_span_ref: str | None
    extraction_run_id: EntityId

    def __post_init__(self) -> None:
        if not self.temp_id:
            raise ValueError("temp_id is required")
        if not self.proposition:
            raise ValueError("proposition is required")
        if not self.proposed_type:
            raise ValueError("proposed_type is required")
        if self.extraction_run_id.namespace != "OPR":
            raise ValueError("extraction_run_id must use OPR prefix")
        object.__setattr__(self, "proposed_scope", _deep_freeze(self.proposed_scope))


@dataclass(frozen=True, slots=True)
class QuantityProposal:
    temp_id: str
    value: Decimal
    unit: str
    measured_property: str
    source_span_ref: str | None
    extraction_run_id: EntityId

    def __post_init__(self) -> None:
        if not self.temp_id:
            raise ValueError("temp_id is required")
        if not isinstance(self.value, Decimal):
            raise TypeError("value must be Decimal")
        if not self.unit:
            raise ValueError("unit is required")
        if not self.measured_property:
            raise ValueError("measured_property is required")
        if self.extraction_run_id.namespace != "OPR":
            raise ValueError("extraction_run_id must use OPR prefix")


@dataclass(frozen=True, slots=True)
class Claim:
    meta: EntityMeta
    proposition: str
    normalized_proposition: str
    claim_type: str
    scope_id: EntityId
    status: ClaimStatus = ClaimStatus.OPEN
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "CLM":
            raise ValueError("claim id must use CLM prefix")
        if not self.proposition:
            raise ValueError("proposition is required")
        if not self.normalized_proposition:
            raise ValueError("normalized_proposition is required")
        if not self.claim_type:
            raise ValueError("claim_type is required")
        forbidden = FORBIDDEN_CLAIM_LINK_KEYS.intersection(self.attributes.keys())
        if forbidden:
            raise ValueError(f"claim attributes contain authoritative link keys: {sorted(forbidden)}")
        object.__setattr__(self, "attributes", _deep_freeze(self.attributes))


@dataclass(frozen=True, slots=True)
class Quantity:
    meta: EntityMeta
    value: Decimal
    unit: str
    measured_property: str
    scope_id: EntityId | None = None

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "QTY":
            raise ValueError("quantity id must use QTY prefix")
        if not isinstance(self.value, Decimal):
            raise TypeError("value must be Decimal")
        if not self.unit:
            raise ValueError("unit is required")
        if not self.measured_property:
            raise ValueError("measured_property is required")


@dataclass(frozen=True, slots=True)
class Source:
    meta: EntityMeta
    source_type: str
    title: str
    locator: str
    content_hash: str | None = None

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "SRC":
            raise ValueError("source id must use SRC prefix")
        if not self.source_type:
            raise ValueError("source_type is required")
        if not self.title:
            raise ValueError("title is required")
        if not self.locator:
            raise ValueError("locator is required")


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    meta: EntityMeta
    source_id: EntityId
    exact_text: str
    locator: str
    text_hash: str

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "EVD":
            raise ValueError("evidence id must use EVD prefix")
        if self.source_id.namespace != "SRC":
            raise ValueError("source_id must use SRC prefix")
        if not self.exact_text:
            raise ValueError("exact_text is required")
        if not self.locator:
            raise ValueError("locator is required")
        if not self.text_hash:
            raise ValueError("text_hash is required")
