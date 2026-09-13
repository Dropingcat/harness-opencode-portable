"""R2.2 resolution lifecycle for adaptive ResearchChallenge branches.

The knowledge graph remains authoritative for Gap/Conflict entities.  A
resolution assessment records *why* a problem is considered resolved, still
open, blocked or reopened.  Code then projects that assessment onto the
canonical knowledge state, the ResearchChallenge lifecycle and its historical
CHALLENGE card in ResearchDOM.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Mapping, Sequence

from researcher_core.knowledge_reconciliation import (
    ResearchChallenge,
    ResearchChallengeStatus,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import ConflictState, GapState
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r1_entities import Conflict, Gap
from researcher_core.research_planning import (
    ResearchCardKind,
    ResearchCardStatus,
    ResearchDOM,
    ResearchPatch,
    SetCardStatusOperation,
    apply_research_patch,
)
from researcher_core.research_planning_runtime import ResearchTraceLink, ResearchTraceRelation


class ResolutionOutcome(StrEnum):
    RESOLVED = "RESOLVED"
    STILL_OPEN = "STILL_OPEN"
    BLOCKED = "BLOCKED"
    REOPENED = "REOPENED"


class ConflictResolutionMode(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SUBSTANTIVE = "SUBSTANTIVE"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    METHOD_MISMATCH = "METHOD_MISMATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True, slots=True)
class ChallengeResolutionAssessment:
    meta: EntityMeta
    challenge_id: EntityId
    source_entity_id: EntityId
    expected_challenge_revision: int
    outcome: ResolutionOutcome
    rationale: str
    evidence_refs: tuple[EntityId, ...] = ()
    claim_refs: tuple[EntityId, ...] = ()
    remaining_requirements: tuple[str, ...] = ()
    conflict_mode: ConflictResolutionMode = ConflictResolutionMode.NOT_APPLICABLE
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RRS":
            raise ValueError("resolution assessment id must use RRS prefix")
        if self.challenge_id.namespace != "RCH":
            raise ValueError("challenge_id must use RCH prefix")
        if self.source_entity_id.namespace not in {"GAP", "CNF"}:
            raise ValueError("source_entity_id must use GAP or CNF prefix")
        if self.expected_challenge_revision < 1:
            raise ValueError("expected_challenge_revision must be positive")
        if not self.rationale.strip():
            raise ValueError("rationale is required")
        if any(ref.namespace != "EVD" for ref in self.evidence_refs):
            raise ValueError("evidence_refs must use EVD prefix")
        if any(ref.namespace != "CLM" for ref in self.claim_refs):
            raise ValueError("claim_refs must use CLM prefix")
        if self.source_entity_id.namespace == "GAP" and self.conflict_mode != ConflictResolutionMode.NOT_APPLICABLE:
            raise ValueError("conflict_mode is only valid for CNF sources")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "claim_refs", tuple(self.claim_refs))
        object.__setattr__(self, "remaining_requirements", tuple(self.remaining_requirements))
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class ChallengeResolutionResult:
    assessment: ChallengeResolutionAssessment
    source_entity: Gap | Conflict
    challenge: ResearchChallenge
    dom: ResearchDOM
    events: tuple
    trace_links: tuple[ResearchTraceLink, ...]


class ChallengeResolutionError(ValueError):
    pass


def reconcile_challenge_resolution(
    *,
    dom: ResearchDOM,
    challenge: ResearchChallenge,
    source_entity: Gap | Conflict,
    assessment: ChallengeResolutionAssessment,
    challenge_card_id: EntityId,
    patch_id: EntityId,
    actor: ActorRef,
    id_factory: EntityIdFactory,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
) -> ChallengeResolutionResult:
    """Project a typed assessment onto knowledge, challenge and ResearchDOM.

    No assessment may silently resolve a different problem or a different
    historical branch.  The ResearchDOM mutation remains optimistic and atomic.
    """
    _validate_resolution_inputs(dom, challenge, source_entity, assessment, challenge_card_id)

    updated_source = _update_source_entity(source_entity, assessment)
    updated_challenge = replace(
        challenge,
        meta=replace(challenge.meta, revision=challenge.meta.revision + 1),
        status=_challenge_status(assessment.outcome),
    )
    card = dom.cards[challenge_card_id]
    patch = ResearchPatch(
        id=patch_id,
        request_id=dom.request_id,
        expected_dom_revision=dom.meta.revision,
        operations=(
            SetCardStatusOperation(
                card_id=challenge_card_id,
                expected_card_revision=card.meta.revision,
                status=_card_status(assessment.outcome),
            ),
        ),
    )
    reduced = apply_research_patch(
        dom, patch, actor, id_factory, timestamp, causation_id, correlation_id
    )

    links = [
        ResearchTraceLink(
            id=id_factory.new("RTL"),
            research_card_id=challenge_card_id,
            target_id=assessment.meta.id,
            relation=ResearchTraceRelation.VALIDATED,
            run_id=dom.meta.run_id,
            created_at=timestamp,
            created_by=actor,
            metadata={
                "outcome": assessment.outcome.value,
                "challenge_id": str(challenge.meta.id),
                "source_entity_id": str(source_entity.id),
            },
        ),
        ResearchTraceLink(
            id=id_factory.new("RTL"),
            research_card_id=challenge_card_id,
            target_id=source_entity.id,
            relation=(ResearchTraceRelation.RESOLVED_BY if assessment.outcome == ResolutionOutcome.RESOLVED else ResearchTraceRelation.VALIDATED),
            run_id=dom.meta.run_id,
            created_at=timestamp,
            created_by=actor,
            metadata={"assessment_id": str(assessment.meta.id), "outcome": assessment.outcome.value},
        ),
    ]
    for ref in assessment.evidence_refs:
        links.append(
            ResearchTraceLink(
                id=id_factory.new("RTL"),
                research_card_id=challenge_card_id,
                target_id=ref,
                relation=ResearchTraceRelation.VALIDATED,
                run_id=dom.meta.run_id,
                created_at=timestamp,
                created_by=actor,
                metadata={"assessment_id": str(assessment.meta.id)},
            )
        )

    return ChallengeResolutionResult(
        assessment=assessment,
        source_entity=updated_source,
        challenge=updated_challenge,
        dom=reduced.dom,
        events=reduced.events,
        trace_links=tuple(links),
    )


def _validate_resolution_inputs(dom, challenge, source_entity, assessment, challenge_card_id) -> None:
    if challenge.request_id != dom.request_id:
        raise ChallengeResolutionError("challenge belongs to a different research request")
    if assessment.challenge_id != challenge.meta.id:
        raise ChallengeResolutionError("assessment belongs to a different challenge")
    if assessment.expected_challenge_revision != challenge.meta.revision:
        raise ChallengeResolutionError(
            f"challenge revision mismatch: expected {assessment.expected_challenge_revision}, current {challenge.meta.revision}"
        )
    if assessment.source_entity_id != source_entity.id or challenge.source_entity_id != source_entity.id:
        raise ChallengeResolutionError("source entity mismatch")
    if challenge_card_id not in dom.cards:
        raise ChallengeResolutionError("challenge card does not exist")
    card = dom.cards[challenge_card_id]
    if card.kind != ResearchCardKind.CHALLENGE:
        raise ChallengeResolutionError("target card must be CHALLENGE")
    if card.dimensions.get("challenge_id") != str(challenge.meta.id):
        raise ChallengeResolutionError("ResearchDOM card is bound to a different challenge")
    if assessment.outcome == ResolutionOutcome.RESOLVED and assessment.remaining_requirements:
        raise ChallengeResolutionError("resolved assessment cannot contain remaining requirements")
    if isinstance(source_entity, Conflict):
        if assessment.conflict_mode == ConflictResolutionMode.NOT_APPLICABLE:
            raise ChallengeResolutionError("conflict resolution requires conflict_mode")
        if assessment.outcome == ResolutionOutcome.RESOLVED and assessment.conflict_mode == ConflictResolutionMode.INSUFFICIENT_EVIDENCE:
            raise ChallengeResolutionError("insufficient evidence cannot resolve a conflict")
    elif assessment.conflict_mode != ConflictResolutionMode.NOT_APPLICABLE:
        raise ChallengeResolutionError("gap assessment cannot set conflict_mode")


def _update_source_entity(source: Gap | Conflict, assessment: ChallengeResolutionAssessment) -> Gap | Conflict:
    if isinstance(source, Gap):
        if assessment.outcome == ResolutionOutcome.RESOLVED:
            return replace(source, status=GapState.NO_OPEN_GAPS)
        if assessment.outcome == ResolutionOutcome.REOPENED and source.status == GapState.NO_OPEN_GAPS:
            reopened = GapState.OPEN_BLOCKING_GAPS if source.severity.lower() == "blocking" else GapState.OPEN_NONBLOCKING_GAPS
            return replace(source, status=reopened)
        return source

    if assessment.outcome == ResolutionOutcome.RESOLVED:
        return replace(source, status=ConflictState.NO_DIRECT_CONFLICT)
    if assessment.outcome == ResolutionOutcome.REOPENED and source.status == ConflictState.NO_DIRECT_CONFLICT:
        return replace(source, status=ConflictState.CONFLICT_UNRESOLVED)
    if assessment.outcome in {ResolutionOutcome.STILL_OPEN, ResolutionOutcome.BLOCKED}:
        return replace(source, status=ConflictState.CONFLICT_UNRESOLVED)
    return source


def _challenge_status(outcome: ResolutionOutcome) -> ResearchChallengeStatus:
    return {
        ResolutionOutcome.RESOLVED: ResearchChallengeStatus.RESOLVED,
        ResolutionOutcome.STILL_OPEN: ResearchChallengeStatus.ACTIVE,
        ResolutionOutcome.BLOCKED: ResearchChallengeStatus.BLOCKED,
        ResolutionOutcome.REOPENED: ResearchChallengeStatus.REOPENED,
    }[outcome]


def _card_status(outcome: ResolutionOutcome) -> ResearchCardStatus:
    return {
        ResolutionOutcome.RESOLVED: ResearchCardStatus.COMPLETED,
        ResolutionOutcome.STILL_OPEN: ResearchCardStatus.ACTIVE,
        ResolutionOutcome.BLOCKED: ResearchCardStatus.BLOCKED,
        ResolutionOutcome.REOPENED: ResearchCardStatus.ACTIVE,
    }[outcome]


def challenge_resolution_to_dict(value: ChallengeResolutionAssessment) -> dict[str, Any]:
    return {
        "schema_version": "challenge-resolution/1.0",
        "meta": {
            "id": str(value.meta.id),
            "schema_version": value.meta.schema_version,
            "revision": value.meta.revision,
            "run_id": str(value.meta.run_id),
            "created_at": value.meta.created_at.isoformat(),
            "created_by": {
                "actor_type": value.meta.created_by.actor_type,
                "actor_id": value.meta.created_by.actor_id,
            },
        },
        "challenge_id": str(value.challenge_id),
        "source_entity_id": str(value.source_entity_id),
        "expected_challenge_revision": value.expected_challenge_revision,
        "outcome": value.outcome.value,
        "rationale": value.rationale,
        "evidence_refs": [str(x) for x in value.evidence_refs],
        "claim_refs": [str(x) for x in value.claim_refs],
        "remaining_requirements": list(value.remaining_requirements),
        "conflict_mode": value.conflict_mode.value,
        "metadata": _plain_value(value.metadata),
    }


def challenge_resolution_from_dict(raw: Mapping[str, Any]) -> ChallengeResolutionAssessment:
    from datetime import datetime
    meta = raw["meta"]
    actor = meta["created_by"]
    return ChallengeResolutionAssessment(
        meta=EntityMeta(
            id=EntityId(str(meta["id"])),
            schema_version=str(meta["schema_version"]),
            revision=int(meta["revision"]),
            run_id=EntityId(str(meta["run_id"])),
            created_at=datetime.fromisoformat(str(meta["created_at"])),
            created_by=ActorRef(str(actor["actor_type"]), str(actor["actor_id"])),
        ),
        challenge_id=EntityId(str(raw["challenge_id"])),
        source_entity_id=EntityId(str(raw["source_entity_id"])),
        expected_challenge_revision=int(raw["expected_challenge_revision"]),
        outcome=ResolutionOutcome(str(raw["outcome"])),
        rationale=str(raw["rationale"]),
        evidence_refs=tuple(EntityId(str(x)) for x in raw.get("evidence_refs", ())),
        claim_refs=tuple(EntityId(str(x)) for x in raw.get("claim_refs", ())),
        remaining_requirements=tuple(str(x) for x in raw.get("remaining_requirements", ())),
        conflict_mode=ConflictResolutionMode(str(raw.get("conflict_mode", ConflictResolutionMode.NOT_APPLICABLE.value))),
        metadata=dict(raw.get("metadata", {})),
    )


class ChallengeResolutionRepository:
    def __init__(self, conn) -> None:
        self._conn = conn

    def save(self, assessment: ChallengeResolutionAssessment) -> None:
        from researcher_core.r0.sqlite_store import SqliteUnitOfWork
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(assessment.meta.id, challenge_resolution_to_dict(assessment))
            uow.commit()

    def load(self, assessment_id: EntityId) -> ChallengeResolutionAssessment | None:
        from researcher_core.r0.sqlite_store import SqliteUnitOfWork
        raw = SqliteUnitOfWork(self._conn).state_view().get(str(assessment_id))
        if raw is None or raw.get("schema_version") != "challenge-resolution/1.0":
            return None
        return challenge_resolution_from_dict(raw)


def _plain_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _plain_value(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain_value(v) for v in value]
    if isinstance(value, EntityId):
        return str(value)
    return value
