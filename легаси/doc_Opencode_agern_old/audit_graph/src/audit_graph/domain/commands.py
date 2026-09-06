from __future__ import annotations

from dataclasses import dataclass

from .enums import ClaimStatus
from .ids import ActorId, ClaimId, EvidenceId, TaskId
from .value_objects import Reason


@dataclass(frozen=True)
class RegisterClaim:
    claim_id: ClaimId
    task_id: TaskId
    text: str
    actor_id: ActorId
    reason: Reason


@dataclass(frozen=True)
class AttachEvidence:
    claim_id: ClaimId
    evidence_id: EvidenceId
    kind: str
    uri: str
    actor_id: ActorId
    reason: Reason


@dataclass(frozen=True)
class TransitionClaim:
    claim_id: ClaimId
    target_status: ClaimStatus
    actor_id: ActorId
    reason: Reason
