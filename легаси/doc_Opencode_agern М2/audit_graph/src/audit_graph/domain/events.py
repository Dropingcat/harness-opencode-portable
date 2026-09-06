from __future__ import annotations

from dataclasses import dataclass, field

from .entities import Claim
from .enums import ClaimStatus, EventType
from .ids import ClaimId, EventId, require_id
from .value_objects import AuditMetadata, EvidenceRef, Reason, utc_now_iso


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: EventId
    event_type: EventType
    claim_id: ClaimId
    occurred_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", EventId(require_id(str(self.event_id), field_name="event_id")))
        object.__setattr__(self, "claim_id", ClaimId(require_id(str(self.claim_id), field_name="claim_id")))


@dataclass(frozen=True, kw_only=True)
class ClaimRegistered(DomainEvent):
    claim: Claim
    metadata: AuditMetadata


@dataclass(frozen=True, kw_only=True)
class EvidenceAttached(DomainEvent):
    evidence: EvidenceRef
    reason: Reason
    metadata: AuditMetadata


@dataclass(frozen=True, kw_only=True)
class ClaimStatusChanged(DomainEvent):
    from_status: ClaimStatus
    to_status: ClaimStatus
    reason: Reason
    metadata: AuditMetadata
