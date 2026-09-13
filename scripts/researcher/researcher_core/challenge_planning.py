"""R2.1 local dialectic expansion of knowledge-generated CHALLENGE cards.

A Gap/Conflict first becomes a canonical ResearchChallenge and then a historical
CHALLENGE card (R2).  This module feeds that card back through the same planning
contracts used for the initial research objective.  The semantic planner proposes
Q/A turns and ResearchCardProposal objects; code validates locality, compiles one
atomic patch, and requires an executable local subtree before activation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Sequence

from researcher_core.knowledge_reconciliation import ResearchChallenge, ResearchChallengeStatus
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.events import EventEnvelope
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.research_planning import (
    DecompositionSession,
    PlanningCompileError,
    PlanningCompileResult,
    ResearchCard,
    ResearchCardKind,
    ResearchCardProposal,
    ResearchCardStatus,
    ResearchDOM,
    ResearchPatch,
    SetCardStatusOperation,
    apply_research_patch,
    compile_decomposition_proposals,
)
from researcher_core.research_planning_runtime import (
    PlanningGateReport,
    PlanningGateState,
    evaluate_planning_subtree_gate,
)


class ChallengePlanningError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ChallengePlanningResult:
    session: DecompositionSession
    target_card: ResearchCard
    compiled: PlanningCompileResult
    dom: ResearchDOM
    events: tuple[EventEnvelope, ...]
    local_gate: PlanningGateReport
    challenge: ResearchChallenge | None = None


def expand_challenge_with_decomposition(
    *,
    dom: ResearchDOM,
    session: DecompositionSession,
    proposals: Sequence[ResearchCardProposal],
    id_factory: EntityIdFactory,
    actor: ActorRef,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
    challenge: ResearchChallenge | None = None,
) -> ChallengePlanningResult:
    """Compile and atomically activate one local CHALLENGE decomposition.

    The session must target an existing CHALLENGE card. Proposal roots may only
    attach to that card; descendants may attach to temp ids from the same batch.
    This prevents a local feedback session from silently editing a sibling branch.

    The resulting challenge subtree must contain at least one executable leaf.
    A failed gate returns no authoritative DOM mutation to the caller.
    """
    if session.request_id != dom.request_id:
        raise ChallengePlanningError("session belongs to a different research request")
    if session.target_card_id is None:
        raise ChallengePlanningError("challenge decomposition requires target_card_id")
    if session.target_card_id not in dom.cards:
        raise ChallengePlanningError("challenge target does not exist in ResearchDOM")

    target = dom.cards[session.target_card_id]
    if target.kind != ResearchCardKind.CHALLENGE:
        raise ChallengePlanningError("target card must be CHALLENGE")
    if target.status not in {ResearchCardStatus.PLANNED, ResearchCardStatus.BLOCKED}:
        raise ChallengePlanningError(
            f"challenge card must be PLANNED or BLOCKED, got {target.status.value}"
        )
    if challenge is not None:
        if target.dimensions.get("challenge_id") != str(challenge.meta.id):
            raise ChallengePlanningError("challenge entity does not match target CHALLENGE card")
        if challenge.status not in {ResearchChallengeStatus.OPEN, ResearchChallengeStatus.PLANNED, ResearchChallengeStatus.BLOCKED, ResearchChallengeStatus.REOPENED}:
            raise ChallengePlanningError(f"challenge entity cannot be activated from {challenge.status.value}")

    _validate_local_proposal_roots(target.meta.id, proposals)

    try:
        compiled = compile_decomposition_proposals(
            session=session,
            dom=dom,
            proposals=proposals,
            id_factory=id_factory,
            actor=actor,
            created_at=timestamp,
        )
    except PlanningCompileError as exc:
        raise ChallengePlanningError(str(exc)) from exc

    # Add activation to the same patch so subtree materialization and challenge
    # lifecycle transition are one optimistic-concurrency boundary.
    patch = ResearchPatch(
        id=compiled.patch.id,
        request_id=compiled.patch.request_id,
        expected_dom_revision=compiled.patch.expected_dom_revision,
        operations=(
            *compiled.patch.operations,
            SetCardStatusOperation(
                card_id=target.meta.id,
                expected_card_revision=target.meta.revision,
                status=ResearchCardStatus.ACTIVE,
            ),
        ),
        source_session_id=compiled.patch.source_session_id,
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
    gate = evaluate_planning_subtree_gate(reduced.dom, target.meta.id)
    if gate.state == PlanningGateState.FAIL:
        codes = ", ".join(issue.code for issue in gate.issues) or "UNKNOWN"
        raise ChallengePlanningError(f"challenge subtree is not executable: {codes}")

    updated_challenge = None
    if challenge is not None:
        updated_challenge = replace(
            challenge,
            meta=replace(challenge.meta, revision=challenge.meta.revision + 1),
            status=ResearchChallengeStatus.ACTIVE,
        )
    return ChallengePlanningResult(
        session=session,
        target_card=target,
        compiled=PlanningCompileResult(
            cards=compiled.cards,
            research_map=compiled.research_map,
            patch=patch,
        ),
        dom=reduced.dom,
        events=reduced.events,
        local_gate=gate,
        challenge=updated_challenge,
    )


def _validate_local_proposal_roots(
    target_card_id: EntityId,
    proposals: Sequence[ResearchCardProposal],
) -> None:
    if not proposals:
        raise ChallengePlanningError("challenge decomposition produced no proposals")
    temp_ids = {proposal.temp_id for proposal in proposals}
    if len(temp_ids) != len(proposals):
        raise ChallengePlanningError("challenge decomposition contains duplicate temp ids")

    has_direct_child = False
    for proposal in proposals:
        parent = proposal.parent_ref
        if isinstance(parent, EntityId):
            if parent != target_card_id:
                raise ChallengePlanningError(
                    "challenge proposal may attach only to target CHALLENGE or batch temp-id"
                )
            has_direct_child = True
        elif parent not in temp_ids:
            raise ChallengePlanningError(
                f"challenge proposal parent temp-id is outside local batch: {parent}"
            )
    if not has_direct_child:
        raise ChallengePlanningError("challenge decomposition must contain a direct child")
