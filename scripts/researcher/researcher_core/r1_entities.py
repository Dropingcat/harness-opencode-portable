"""R1 entity contracts: knowledge-model nodes above the R0 core.

R1 adds the structured knowledge layer that lets the core describe research
findings without search, an LLM, or a writer: Scope, Derivation, Assumption,
Recommendation, Gap, Conflict and EdgeProposal.  The classes below are frozen,
slot-based records that follow the R0 patterns from ``r0/entities.py``:

* ``frozen=True, slots=True`` dataclasses;
* ``__post_init__`` validates required fields and entity-id namespaces;
* mapping fields are snapshotted with ``_deep_freeze`` so callers cannot mutate
  them after construction.

Only stdlib imports are used (``dataclasses``, ``typing``), plus the existing
R0 contracts (enums, ids, event helpers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from researcher_core.r0.enums import (
    AdmissionStatus,
    ClaimStatus,
    ConflictState,
    DerivationState,
    GapState,
    WriterEligibility,
)
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId

__all__ = [
    "Scope",
    "Derivation",
    "Assumption",
    "Recommendation",
    "Gap",
    "Conflict",
    "EdgeProposal",
]


@dataclass(frozen=True, slots=True)
class Scope:
    """Typed research scope for a domain with its comparison dimensions."""

    id: EntityId
    domain: str
    dimensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id.namespace != "SCP":
            raise ValueError("scope id must use SCP prefix")
        if not self.domain:
            raise ValueError("domain is required")
        object.__setattr__(self, "dimensions", _deep_freeze(self.dimensions))


@dataclass(frozen=True, slots=True)
class Derivation:
    """Arithmetic or logical derivation from input claims to an output claim."""

    id: EntityId
    output_claim_id: EntityId
    input_claim_ids: tuple[EntityId, ...]
    operation: str
    formula: str | None
    status: DerivationState

    def __post_init__(self) -> None:
        if self.id.namespace != "DRV":
            raise ValueError("derivation id must use DRV prefix")
        if self.output_claim_id.namespace != "CLM":
            raise ValueError("output_claim_id must use CLM prefix")
        if not self.input_claim_ids:
            raise ValueError("input_claim_ids must not be empty")
        if any(claim_id.namespace != "CLM" for claim_id in self.input_claim_ids):
            raise ValueError("input_claim_ids must use CLM prefix")
        if not self.operation:
            raise ValueError("operation is required")
        if not isinstance(self.status, DerivationState):
            raise TypeError("status must be DerivationState")
        object.__setattr__(self, "input_claim_ids", tuple(self.input_claim_ids))
        if self.formula is not None and not self.formula:
            raise ValueError("formula must not be empty")


@dataclass(frozen=True, slots=True)
class Assumption:
    """An admitted or candidate assumption that may back a claim."""

    id: EntityId
    proposition: str
    claim_id: EntityId | None
    status: AdmissionStatus

    def __post_init__(self) -> None:
        if self.id.namespace != "ASM":
            raise ValueError("assumption id must use ASM prefix")
        if not self.proposition:
            raise ValueError("proposition is required")
        if self.claim_id is not None and self.claim_id.namespace != "CLM":
            raise ValueError("claim_id must use CLM prefix")
        if not isinstance(self.status, AdmissionStatus):
            raise TypeError("status must be AdmissionStatus")


@dataclass(frozen=True, slots=True)
class Recommendation:
    """A practical recommendation tied to supporting or blocking claims."""

    id: EntityId
    proposition: str
    target_claim_ids: tuple[EntityId, ...]
    status: ClaimStatus | None
    eligibility: WriterEligibility

    def __post_init__(self) -> None:
        if self.id.namespace != "REC":
            raise ValueError("recommendation id must use REC prefix")
        if not self.proposition:
            raise ValueError("proposition is required")
        if any(claim_id.namespace != "CLM" for claim_id in self.target_claim_ids):
            raise ValueError("target_claim_ids must use CLM prefix")
        if self.status is not None and not isinstance(self.status, ClaimStatus):
            raise TypeError("status must be ClaimStatus or None")
        if not isinstance(self.eligibility, WriterEligibility):
            raise TypeError("eligibility must be WriterEligibility")
        object.__setattr__(self, "target_claim_ids", tuple(self.target_claim_ids))


@dataclass(frozen=True, slots=True)
class Gap:
    """A knowledge gap: full graph node, not a validator-output string."""

    id: EntityId
    gap_type: str
    target_claim_ids: tuple[EntityId, ...]
    severity: str
    blocks: tuple[EntityId, ...]
    resolution_requirements: tuple[str, ...]
    status: GapState

    def __post_init__(self) -> None:
        if self.id.namespace != "GAP":
            raise ValueError("gap id must use GAP prefix")
        if not self.gap_type:
            raise ValueError("gap_type is required")
        if not self.target_claim_ids:
            raise ValueError("target_claim_ids must not be empty")
        if any(claim_id.namespace != "CLM" for claim_id in self.target_claim_ids):
            raise ValueError("target_claim_ids must use CLM prefix")
        if not self.severity:
            raise ValueError("severity is required")
        if any(block.namespace not in {"REC", "GAP", "CLM"} for block in self.blocks):
            raise ValueError("blocks must use REC, GAP, or CLM prefix")
        if not isinstance(self.status, GapState):
            raise TypeError("status must be GapState")
        object.__setattr__(self, "target_claim_ids", tuple(self.target_claim_ids))
        object.__setattr__(self, "blocks", tuple(self.blocks))
        object.__setattr__(self, "resolution_requirements", tuple(self.resolution_requirements))


@dataclass(frozen=True, slots=True)
class Conflict:
    """A recorded conflict between claims and their supporting evidence."""

    id: EntityId
    member_claim_ids: tuple[EntityId, ...]
    member_evidence_ids: tuple[EntityId, ...]
    conflict_type: str
    status: ConflictState

    def __post_init__(self) -> None:
        if self.id.namespace != "CNF":
            raise ValueError("conflict id must use CNF prefix")
        if not self.member_claim_ids:
            raise ValueError("member_claim_ids must not be empty")
        if any(claim_id.namespace != "CLM" for claim_id in self.member_claim_ids):
            raise ValueError("member_claim_ids must use CLM prefix")
        if any(evidence_id.namespace != "EVD" for evidence_id in self.member_evidence_ids):
            raise ValueError("member_evidence_ids must use EVD prefix")
        if not self.conflict_type:
            raise ValueError("conflict_type is required")
        if not isinstance(self.status, ConflictState):
            raise TypeError("status must be ConflictState")
        object.__setattr__(self, "member_claim_ids", tuple(self.member_claim_ids))
        object.__setattr__(self, "member_evidence_ids", tuple(self.member_evidence_ids))


@dataclass(frozen=True, slots=True)
class EdgeProposal:
    """Candidate graph edge between two entities, awaiting admission."""

    temp_id: str
    source_entity: EntityId
    target_entity: EntityId
    proposed_relation_type: str
    proposed_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.temp_id:
            raise ValueError("temp_id is required")
        if not isinstance(self.source_entity, EntityId):
            raise TypeError("source_entity must be EntityId")
        if not isinstance(self.target_entity, EntityId):
            raise TypeError("target_entity must be EntityId")
        if not self.proposed_relation_type:
            raise ValueError("proposed_relation_type is required")
        object.__setattr__(self, "proposed_metadata", _deep_freeze(self.proposed_metadata))