"""R0 state transitions for claims.

Direct mutation of ``Claim.status`` is impossible because Claim is frozen. This
module is the deterministic transition boundary used before the full registry
and validator stack exist.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import Claim, EntityMeta
from researcher_core.r0.enums import ClaimStatus
from researcher_core.r0.events import EventEnvelope, ReasonCode, ReasonCodeRegistry
from researcher_core.r0.ids import EntityId


ALLOWED_CLAIM_STATUS_TRANSITIONS = frozenset(
    {
        (ClaimStatus.OPEN, ClaimStatus.SUPPORTED),
        (ClaimStatus.OPEN, ClaimStatus.PARTIALLY_SUPPORTED),
        (ClaimStatus.OPEN, ClaimStatus.CONTRADICTED),
        (ClaimStatus.OPEN, ClaimStatus.REJECTED),
        (ClaimStatus.SUPPORTED, ClaimStatus.STALE),
        (ClaimStatus.PARTIALLY_SUPPORTED, ClaimStatus.STALE),
        (ClaimStatus.CONTRADICTED, ClaimStatus.STALE),
        (ClaimStatus.STALE, ClaimStatus.SUPERSEDED),
        (ClaimStatus.STALE, ClaimStatus.SUPPORTED),
        (ClaimStatus.STALE, ClaimStatus.PARTIALLY_SUPPORTED),
        (ClaimStatus.STALE, ClaimStatus.CONTRADICTED),
    }
)


@dataclass(frozen=True, slots=True)
class TransitionRequest:
    target_id: EntityId
    expected_revision: int
    requested_status: ClaimStatus
    reason_codes: tuple[ReasonCode, ...]
    evidence_refs: tuple[EntityId, ...] = ()

    def __post_init__(self) -> None:
        if self.target_id.namespace != "CLM":
            raise ValueError("target_id must use CLM prefix")
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be positive")
        if not isinstance(self.requested_status, ClaimStatus):
            raise TypeError("requested_status must be ClaimStatus")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        if not self.reason_codes:
            raise ValueError("reason_codes are required for status transitions")
        for evidence_ref in self.evidence_refs:
            if evidence_ref.namespace != "EVD":
                raise ValueError("evidence_refs must use EVD prefix")


class RevisionConflict(RuntimeError):
    """Raised when expected revision does not match current entity revision."""


class InvalidTransition(RuntimeError):
    """Raised when a status transition is not allowed by R0 state machine."""


@dataclass(frozen=True, slots=True)
class TransitionResult:
    claim: Claim
    event: EventEnvelope


def transition_claim_status(
    claim: Claim,
    request: TransitionRequest,
    actor: ActorRef,
    event_id: EntityId,
    causation_id: EntityId,
    correlation_id: EntityId,
    timestamp,
    reason_registry: ReasonCodeRegistry | None = None,
) -> TransitionResult:
    if claim.meta.id != request.target_id:
        raise ValueError("transition target does not match claim id")
    if claim.meta.revision != request.expected_revision:
        raise RevisionConflict("claim revision does not match expected_revision")
    if (claim.status, request.requested_status) not in ALLOWED_CLAIM_STATUS_TRANSITIONS:
        raise InvalidTransition(f"cannot transition claim from {claim.status.value} to {request.requested_status.value}")
    if reason_registry is not None:
        reason_registry.validate_all(request.reason_codes)

    next_meta = EntityMeta(
        id=claim.meta.id,
        schema_version=claim.meta.schema_version,
        revision=claim.meta.revision + 1,
        run_id=claim.meta.run_id,
        created_at=claim.meta.created_at,
        created_by=claim.meta.created_by,
    )
    updated_claim = replace(claim, meta=next_meta, status=request.requested_status)
    event = EventEnvelope(
        event_id=event_id,
        event_type="CLAIM_STATUS_CHANGED",
        aggregate_id=claim.meta.id,
        aggregate_revision=next_meta.revision,
        run_id=claim.meta.run_id,
        actor=actor.actor_id,
        timestamp=timestamp,
        causation_id=causation_id,
        correlation_id=correlation_id,
        schema_version="r0-event/0.1",
        reason_codes=request.reason_codes,
        payload={
            "claim": updated_claim,
            "from_status": claim.status.value,
            "to_status": request.requested_status.value,
            "evidence_refs": request.evidence_refs,
        },
        reason_registry=reason_registry,
    )
    return TransitionResult(claim=updated_claim, event=event)
