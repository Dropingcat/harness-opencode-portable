"""R2 bridge between ResearchDOM planning and the canonical knowledge graph.

The planning tree answers *what are we doing?* while the knowledge layer answers
*what do we know?*.  This module does not duplicate Claim/Gap/Conflict entities.
It only creates typed research challenges from already admitted knowledge nodes
and materializes those challenges back into ResearchDOM as historical cards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import EventEnvelope, _deep_freeze
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r0.sqlite_store import SqliteUnitOfWork
from researcher_core.r1_entities import Conflict, Gap
from researcher_core.research_planning import (
    AddCardOperation,
    ResearchCard,
    ResearchCardKind,
    ResearchCardStatus,
    ResearchDOM,
    ResearchPatch,
    apply_research_patch,
)
from researcher_core.research_planning_runtime import (
    ResearchTraceLink,
    ResearchTraceRelation,
)


class ResearchChallengeKind(StrEnum):
    GAP_RESOLUTION = "GAP_RESOLUTION"
    CONFLICT_RESOLUTION = "CONFLICT_RESOLUTION"


class ResearchChallengeStatus(StrEnum):
    OPEN = "OPEN"
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    REOPENED = "REOPENED"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True, slots=True)
class ResearchChallenge:
    """A planning request created from an admitted knowledge problem.

    The source Gap/Conflict remains canonical.  This entity records only the
    request to investigate it, which may later be decomposed through the same
    PlanningDialectic used for the original objective.
    """

    meta: EntityMeta
    request_id: EntityId
    kind: ResearchChallengeKind
    source_entity_id: EntityId
    target_claim_ids: tuple[EntityId, ...]
    title: str
    resolution_requirements: tuple[str, ...] = ()
    status: ResearchChallengeStatus = ResearchChallengeStatus.OPEN
    dimensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RCH":
            raise ValueError("research challenge id must use RCH prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        if self.source_entity_id.namespace not in {"GAP", "CNF"}:
            raise ValueError("source_entity_id must use GAP or CNF prefix")
        if any(claim_id.namespace != "CLM" for claim_id in self.target_claim_ids):
            raise ValueError("target_claim_ids must use CLM prefix")
        if not self.target_claim_ids:
            raise ValueError("target_claim_ids must not be empty")
        if not self.title.strip():
            raise ValueError("title is required")
        object.__setattr__(self, "target_claim_ids", tuple(self.target_claim_ids))
        object.__setattr__(self, "resolution_requirements", tuple(self.resolution_requirements))
        object.__setattr__(self, "dimensions", _deep_freeze(self.dimensions))


@dataclass(frozen=True, slots=True)
class KnowledgeFeedbackResult:
    challenge: ResearchChallenge
    card: ResearchCard
    dom: ResearchDOM
    events: tuple[EventEnvelope, ...]
    trace_links: tuple[ResearchTraceLink, ...]


def challenge_from_gap(
    gap: Gap,
    request_id: EntityId,
    meta: EntityMeta,
    *,
    dimensions: Mapping[str, Any] | None = None,
) -> ResearchChallenge:
    if meta.id.namespace != "RCH":
        raise ValueError("meta id must use RCH prefix")
    return ResearchChallenge(
        meta=meta,
        request_id=request_id,
        kind=ResearchChallengeKind.GAP_RESOLUTION,
        source_entity_id=gap.id,
        target_claim_ids=gap.target_claim_ids,
        title=f"Resolve knowledge gap: {gap.gap_type}",
        resolution_requirements=gap.resolution_requirements,
        dimensions={
            "source_kind": "GAP",
            "gap_type": gap.gap_type,
            "severity": gap.severity,
            **dict(dimensions or {}),
        },
    )


def challenge_from_conflict(
    conflict: Conflict,
    request_id: EntityId,
    meta: EntityMeta,
    *,
    dimensions: Mapping[str, Any] | None = None,
) -> ResearchChallenge:
    if meta.id.namespace != "RCH":
        raise ValueError("meta id must use RCH prefix")
    requirements = (
        "compare conflicting claims under aligned scope",
        "inspect supporting and contradicting evidence",
        "determine whether the conflict is substantive or scope-dependent",
    )
    return ResearchChallenge(
        meta=meta,
        request_id=request_id,
        kind=ResearchChallengeKind.CONFLICT_RESOLUTION,
        source_entity_id=conflict.id,
        target_claim_ids=conflict.member_claim_ids,
        title=f"Resolve knowledge conflict: {conflict.conflict_type}",
        resolution_requirements=requirements,
        dimensions={
            "source_kind": "CONFLICT",
            "conflict_type": conflict.conflict_type,
            "evidence_ids": tuple(str(x) for x in conflict.member_evidence_ids),
            **dict(dimensions or {}),
        },
    )


def materialize_challenge_card(
    dom: ResearchDOM,
    challenge: ResearchChallenge,
    *,
    parent_card_id: EntityId,
    card_id: EntityId,
    patch_id: EntityId,
    actor: ActorRef,
    id_factory: EntityIdFactory,
    timestamp: datetime,
    causation_id: EntityId,
    correlation_id: EntityId,
) -> KnowledgeFeedbackResult:
    """Insert one historical CHALLENGE card and link it to knowledge entities.

    This deliberately does *not* decompose the challenge into executable tasks.
    The next PlanningDialectic owns that semantic operation.
    """
    if challenge.request_id != dom.request_id:
        raise ValueError("challenge belongs to a different research request")
    if parent_card_id not in dom.cards:
        raise KeyError(str(parent_card_id))
    if card_id.namespace != "RCD":
        raise ValueError("card_id must use RCD prefix")

    inherited: dict[str, Any] = {}
    for ancestor in dom.lineage(parent_card_id):
        inherited.update(dict(ancestor.dimensions))
    challenge_dimensions = {
        **inherited,
        **dict(challenge.dimensions),
        "challenge_id": str(challenge.meta.id),
        "challenge_kind": challenge.kind.value,
        "source_entity_id": str(challenge.source_entity_id),
        "target_claim_ids": tuple(str(x) for x in challenge.target_claim_ids),
        "resolution_requirements": challenge.resolution_requirements,
    }
    card = ResearchCard(
        meta=EntityMeta(
            id=card_id,
            schema_version="research-card/1.1",
            revision=1,
            run_id=dom.meta.run_id,
            created_at=timestamp,
            created_by=actor,
        ),
        request_id=dom.request_id,
        kind=ResearchCardKind.CHALLENGE,
        title=challenge.title,
        parent_id=parent_card_id,
        description="Knowledge-graph feedback requiring further research decomposition.",
        status=ResearchCardStatus.PLANNED,
        dimensions=challenge_dimensions,
        created_from=(challenge.source_entity_id,),
    )
    patch = ResearchPatch(
        id=patch_id,
        request_id=dom.request_id,
        expected_dom_revision=dom.meta.revision,
        operations=(AddCardOperation(card),),
    )
    reduced = apply_research_patch(
        dom,
        patch,
        actor,
        id_factory,
        timestamp,
        causation_id,
        correlation_id,
    )
    links = (
        ResearchTraceLink(
            id=id_factory.new("RTL"),
            research_card_id=parent_card_id,
            target_id=challenge.meta.id,
            relation=ResearchTraceRelation.CREATED_CHALLENGE,
            run_id=dom.meta.run_id,
            created_at=timestamp,
            created_by=actor,
            metadata={"source_entity_id": str(challenge.source_entity_id)},
        ),
        ResearchTraceLink(
            id=id_factory.new("RTL"),
            research_card_id=card.meta.id,
            target_id=challenge.source_entity_id,
            relation=ResearchTraceRelation.ADDRESSES,
            run_id=dom.meta.run_id,
            created_at=timestamp,
            created_by=actor,
            metadata={"challenge_id": str(challenge.meta.id)},
        ),
    )
    return KnowledgeFeedbackResult(
        challenge=challenge,
        card=card,
        dom=reduced.dom,
        events=reduced.events,
        trace_links=links,
    )


@dataclass(frozen=True, slots=True)
class ResearchKnowledgeProjection:
    by_card: Mapping[EntityId, tuple[ResearchTraceLink, ...]]
    by_entity: Mapping[EntityId, tuple[ResearchTraceLink, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_card", MappingProxyType(dict(self.by_card)))
        object.__setattr__(self, "by_entity", MappingProxyType(dict(self.by_entity)))


def build_research_knowledge_projection(links: Sequence[ResearchTraceLink]) -> ResearchKnowledgeProjection:
    by_card: dict[EntityId, list[ResearchTraceLink]] = {}
    by_entity: dict[EntityId, list[ResearchTraceLink]] = {}
    for link in links:
        by_card.setdefault(link.research_card_id, []).append(link)
        by_entity.setdefault(link.target_id, []).append(link)
    return ResearchKnowledgeProjection(
        by_card={key: tuple(value) for key, value in by_card.items()},
        by_entity={key: tuple(value) for key, value in by_entity.items()},
    )


def research_challenge_to_dict(challenge: ResearchChallenge) -> dict[str, Any]:
    return {
        "schema_version": "research-challenge/1.0",
        "meta": {
            "id": str(challenge.meta.id),
            "schema_version": challenge.meta.schema_version,
            "revision": challenge.meta.revision,
            "run_id": str(challenge.meta.run_id),
            "created_at": challenge.meta.created_at.isoformat(),
            "created_by": {
                "actor_type": challenge.meta.created_by.actor_type,
                "actor_id": challenge.meta.created_by.actor_id,
            },
        },
        "request_id": str(challenge.request_id),
        "kind": challenge.kind.value,
        "source_entity_id": str(challenge.source_entity_id),
        "target_claim_ids": [str(x) for x in challenge.target_claim_ids],
        "title": challenge.title,
        "resolution_requirements": list(challenge.resolution_requirements),
        "status": challenge.status.value,
        "dimensions": _plain(challenge.dimensions),
    }


def research_challenge_from_dict(raw: Mapping[str, Any]) -> ResearchChallenge:
    meta_raw = raw["meta"]
    actor_raw = meta_raw["created_by"]
    return ResearchChallenge(
        meta=EntityMeta(
            id=EntityId(str(meta_raw["id"])),
            schema_version=str(meta_raw["schema_version"]),
            revision=int(meta_raw["revision"]),
            run_id=EntityId(str(meta_raw["run_id"])),
            created_at=datetime.fromisoformat(str(meta_raw["created_at"])),
            created_by=ActorRef(str(actor_raw["actor_type"]), str(actor_raw["actor_id"])),
        ),
        request_id=EntityId(str(raw["request_id"])),
        kind=ResearchChallengeKind(str(raw["kind"])),
        source_entity_id=EntityId(str(raw["source_entity_id"])),
        target_claim_ids=tuple(EntityId(str(x)) for x in raw["target_claim_ids"]),
        title=str(raw["title"]),
        resolution_requirements=tuple(str(x) for x in raw.get("resolution_requirements", ())),
        status=ResearchChallengeStatus(str(raw.get("status", ResearchChallengeStatus.OPEN.value))),
        dimensions=dict(raw.get("dimensions", {})),
    )


class ResearchChallengeRepository:
    def __init__(self, conn) -> None:
        self._conn = conn

    def save(self, challenge: ResearchChallenge) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(challenge.meta.id, research_challenge_to_dict(challenge))
            uow.commit()

    def load(self, challenge_id: EntityId) -> ResearchChallenge | None:
        raw = SqliteUnitOfWork(self._conn).state_view().get(str(challenge_id))
        if raw is None or raw.get("schema_version") != "research-challenge/1.0":
            return None
        return research_challenge_from_dict(raw)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [_plain(nested) for nested in value]
    if isinstance(value, EntityId):
        return str(value)
    return value
