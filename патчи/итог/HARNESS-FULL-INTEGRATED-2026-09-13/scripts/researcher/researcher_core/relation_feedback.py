"""R3.4 feedback from blocked relation assessments into ResearchDOM.

An inconclusive relation assessment is not terminal knowledge.  It becomes a
canonical Gap and ResearchChallenge, then reuses the existing R2 challenge-card
materialization path.  Rejected relations are handled by relation lifecycle and
do not automatically create a research challenge at this layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from researcher_core.knowledge_reconciliation import (
    KnowledgeFeedbackResult,
    ResearchChallenge,
    challenge_from_gap,
    materialize_challenge_card,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import GapState
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r1_entities import Gap
from researcher_core.relation_assessment import (
    RelationAssessment,
    RelationAssessmentVerdict,
    RelationUseState,
)
from researcher_core.research_planning import ResearchDOM


class RelationFeedbackError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RelationGapFeedbackResult:
    gap: Gap
    challenge: ResearchChallenge
    feedback: KnowledgeFeedbackResult


def gap_from_inconclusive_relation(
    *,
    edge: GraphEdge,
    assessment: RelationAssessment,
    gap_id: EntityId,
) -> Gap:
    """Convert one current INCONCLUSIVE/BLOCKED relation into a typed Gap."""
    if gap_id.namespace != "GAP":
        raise ValueError("gap_id must use GAP prefix")
    if assessment.edge_id != edge.meta.id:
        raise RelationFeedbackError("assessment does not target edge")
    if assessment.assessed_edge_revision != edge.meta.revision:
        raise RelationFeedbackError("assessment does not target current edge revision")
    if assessment.verdict is not RelationAssessmentVerdict.INCONCLUSIVE:
        raise RelationFeedbackError("only INCONCLUSIVE relation assessment creates a research gap")
    if assessment.use_state is not RelationUseState.BLOCKED:
        raise RelationFeedbackError("relation gap requires BLOCKED use state")

    target_claim_ids = tuple(
        entity_id for entity_id in (edge.source_id, edge.target_id)
        if entity_id.namespace == "CLM"
    )
    if not target_claim_ids:
        raise RelationFeedbackError("relation gap requires at least one Claim endpoint")

    requirements = tuple(dict.fromkeys((
        *assessment.findings,
        *(
            "obtain missing method/scope/evidence information required to reassess the relation",
            f"reassess relation {edge.meta.id} at a new evidence revision",
        ),
    )))
    return Gap(
        id=gap_id,
        gap_type="RELATION_ASSESSMENT_INCONCLUSIVE",
        target_claim_ids=target_claim_ids,
        severity="blocking",
        blocks=target_claim_ids,
        resolution_requirements=requirements,
        status=GapState.OPEN_BLOCKING_GAPS,
    )


def materialize_relation_assessment_feedback(
    *,
    dom: ResearchDOM,
    edge: GraphEdge,
    assessment: RelationAssessment,
    existing_challenges: Sequence[ResearchChallenge],
    id_factory: EntityIdFactory,
    actor: ActorRef,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
) -> RelationGapFeedbackResult:
    """Create one Gap→ResearchChallenge→CHALLENGE card feedback branch.

    The assessment's originating ResearchCard is the historical parent.  The
    assessment id is an idempotency key at this layer: the same assessment may
    not create a second feedback branch.
    """
    if assessment.research_card_id not in dom.cards:
        raise RelationFeedbackError("assessment research card does not exist in ResearchDOM")
    duplicate = next(
        (
            challenge for challenge in existing_challenges
            if challenge.dimensions.get("relation_assessment_id") == str(assessment.meta.id)
        ),
        None,
    )
    if duplicate is not None:
        raise RelationFeedbackError(
            f"relation assessment already has research challenge {duplicate.meta.id}"
        )

    gap = gap_from_inconclusive_relation(
        edge=edge,
        assessment=assessment,
        gap_id=id_factory.new("GAP"),
    )
    challenge_meta = EntityMeta(
        id=id_factory.new("RCH"),
        schema_version="research-challenge/1.0",
        revision=1,
        run_id=dom.meta.run_id,
        created_at=timestamp,
        created_by=actor,
    )
    challenge = challenge_from_gap(
        gap,
        dom.request_id,
        challenge_meta,
        dimensions={
            "origin": "RelationAssessment",
            "relation_assessment_id": str(assessment.meta.id),
            "edge_id": str(edge.meta.id),
            "edge_revision": edge.meta.revision,
            "edge_kind": edge.edge_kind.value,
            "assessment_verdict": assessment.verdict.value,
            "assessment_reason_codes": tuple(assessment.reason_codes),
        },
    )
    feedback = materialize_challenge_card(
        dom,
        challenge,
        parent_card_id=assessment.research_card_id,
        card_id=id_factory.new("RCD"),
        patch_id=id_factory.new("RPT"),
        actor=actor,
        id_factory=id_factory,
        timestamp=timestamp,
        causation_id=causation_id,
        correlation_id=correlation_id,
    )
    return RelationGapFeedbackResult(gap=gap, challenge=challenge, feedback=feedback)


def relation_gap_to_dict(gap: Gap) -> dict[str, object]:
    return {
        "schema_version": "knowledge-gap/1.0",
        "id": str(gap.id),
        "gap_type": gap.gap_type,
        "target_claim_ids": [str(x) for x in gap.target_claim_ids],
        "severity": gap.severity,
        "blocks": [str(x) for x in gap.blocks],
        "resolution_requirements": list(gap.resolution_requirements),
        "status": gap.status.value,
    }


def relation_gap_from_dict(raw) -> Gap:
    return Gap(
        id=EntityId(str(raw["id"])),
        gap_type=str(raw["gap_type"]),
        target_claim_ids=tuple(EntityId(str(x)) for x in raw.get("target_claim_ids", ())),
        severity=str(raw["severity"]),
        blocks=tuple(EntityId(str(x)) for x in raw.get("blocks", ())),
        resolution_requirements=tuple(str(x) for x in raw.get("resolution_requirements", ())),
        status=GapState(str(raw["status"])),
    )


class RelationFeedbackRepository:
    """Atomic durable projection for relation-generated Gap + Challenge."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def save(self, gap: Gap, challenge: ResearchChallenge) -> None:
        from researcher_core.knowledge_reconciliation import research_challenge_to_dict
        from researcher_core.r0.sqlite_store import SqliteUnitOfWork

        if challenge.source_entity_id != gap.id:
            raise RelationFeedbackError("challenge source_entity_id does not match gap")
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(gap.id, relation_gap_to_dict(gap))
            uow.put_state(challenge.meta.id, research_challenge_to_dict(challenge))
            uow.commit()

    def load_gap(self, gap_id: EntityId) -> Gap | None:
        from researcher_core.r0.sqlite_store import SqliteUnitOfWork

        raw = SqliteUnitOfWork(self._conn).state_view().get(str(gap_id))
        if raw is None or raw.get("schema_version") != "knowledge-gap/1.0":
            return None
        return relation_gap_from_dict(raw)
