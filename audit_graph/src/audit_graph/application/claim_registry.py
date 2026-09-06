from __future__ import annotations

from dataclasses import asdict
from typing import Iterable
from uuid import uuid4

from audit_graph.domain.commands import AttachEvidence, RegisterClaim, TransitionClaim
from audit_graph.domain.entities import Claim
from audit_graph.domain.enums import ClaimStatus, EventType, EvidenceKind
from audit_graph.domain.events import ClaimRegistered, ClaimStatusChanged, EvidenceAttached
from audit_graph.domain.ids import EventId, TransitionId
from audit_graph.domain.state_machines import require_transition
from audit_graph.domain.value_objects import AuditMetadata, EvidenceRef
from audit_graph.ports.repositories import ClaimRepository, EventRepository


class ClaimRegistry:
    def __init__(self, claim_repository: ClaimRepository, event_repository: EventRepository) -> None:
        self._claim_repository = claim_repository
        self._event_repository = event_repository

    def register(self, command: RegisterClaim) -> Claim:
        claim = Claim(
            claim_id=command.claim_id,
            task_id=command.task_id,
            text=command.text,
            status=ClaimStatus.REGISTERED,
            reasons=(command.reason,),
        )
        metadata = AuditMetadata(actor_id=command.actor_id)
        event = ClaimRegistered(
            event_id=EventId(str(uuid4())),
            event_type=EventType.CLAIM_REGISTERED,
            claim_id=claim.claim_id,
            claim=claim,
            metadata=metadata,
        )
        self._claim_repository.upsert(claim)
        self._event_repository.append(event)
        return claim

    def attach_evidence(self, command: AttachEvidence) -> Claim:
        claim = self._claim_repository.get(command.claim_id)
        evidence = EvidenceRef(
            evidence_id=command.evidence_id,
            kind=EvidenceKind(command.kind),
            uri=command.uri,
        )
        updated = claim.with_evidence(evidence, command.reason)
        event = EvidenceAttached(
            event_id=EventId(str(uuid4())),
            event_type=EventType.EVIDENCE_ATTACHED,
            claim_id=claim.claim_id,
            evidence=evidence,
            reason=command.reason,
            metadata=AuditMetadata(actor_id=command.actor_id),
        )
        self._claim_repository.upsert(updated)
        self._event_repository.append(event)
        return updated

    def transition(self, command: TransitionClaim) -> Claim:
        claim = self._claim_repository.get(command.claim_id)
        require_transition(claim.status, command.target_status, command.reason)
        updated = claim.with_status(command.target_status, command.reason)
        event = ClaimStatusChanged(
            event_id=EventId(str(uuid4())),
            event_type=EventType.CLAIM_STATUS_CHANGED,
            claim_id=claim.claim_id,
            from_status=claim.status,
            to_status=command.target_status,
            reason=command.reason,
            metadata=AuditMetadata(actor_id=command.actor_id),
        )
        self._claim_repository.upsert(updated)
        self._event_repository.append(event)
        return updated

    def list_by_task(self, task_id: str) -> Iterable[Claim]:
        return self._claim_repository.list_by_task(task_id)
