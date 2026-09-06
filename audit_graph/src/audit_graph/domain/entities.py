from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Tuple

from .enums import ClaimStatus
from .ids import ClaimId, TaskId, TransitionId, require_id
from .value_objects import AuditMetadata, EvidenceRef, Reason


@dataclass(frozen=True)
class Claim:
    claim_id: ClaimId
    task_id: TaskId
    text: str
    status: ClaimStatus = ClaimStatus.DRAFT
    reasons: Tuple[Reason, ...] = ()
    evidence: Tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", ClaimId(require_id(str(self.claim_id), field_name="claim_id")))
        object.__setattr__(self, "task_id", TaskId(require_id(str(self.task_id), field_name="task_id")))
        object.__setattr__(self, "text", require_id(self.text, field_name="text"))

    def with_status(self, status: ClaimStatus, reason: Reason) -> "Claim":
        return replace(self, status=status, reasons=self.reasons + (reason,))

    def with_evidence(self, evidence_ref: EvidenceRef, reason: Reason) -> "Claim":
        return replace(self, evidence=self.evidence + (evidence_ref,), reasons=self.reasons + (reason,))


@dataclass(frozen=True)
class ClaimTransition:
    transition_id: TransitionId
    claim_id: ClaimId
    from_status: ClaimStatus
    to_status: ClaimStatus
    reason: Reason
    metadata: AuditMetadata

    def __post_init__(self) -> None:
        object.__setattr__(self, "transition_id", TransitionId(require_id(str(self.transition_id), field_name="transition_id")))
        object.__setattr__(self, "claim_id", ClaimId(require_id(str(self.claim_id), field_name="claim_id")))


@dataclass(frozen=True)
class TaskAudit:
    task_id: TaskId
    claims: Tuple[Claim, ...] = field(default_factory=tuple)
