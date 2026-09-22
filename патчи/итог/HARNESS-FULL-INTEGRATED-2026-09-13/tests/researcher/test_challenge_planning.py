from __future__ import annotations

import random
import unittest
from datetime import datetime, timezone

from researcher_core.challenge_planning import (
    ChallengePlanningError,
    expand_challenge_with_decomposition,
)
from researcher_core.knowledge_reconciliation import challenge_from_gap, materialize_challenge_card
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import GapState
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r1_entities import Gap
from researcher_core.research_planning import (
    AddCardOperation,
    DecompositionSession,
    PlanningInquiryTurn,
    PlanningRole,
    PlanningTurnKind,
    ResearchCard,
    ResearchCardKind,
    ResearchCardProposal,
    ResearchCardStatus,
    ResearchPatch,
    ResearchRequest,
    apply_research_patch,
    create_initial_dom,
)
from researcher_core.research_planning_runtime import PlanningGateState, evaluate_planning_subtree_gate


class Clock:
    def now_ms(self): return 1789240000000


class ChallengePlanningTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(23))
        self.actor = ActorRef("AGENT", "researcher")
        self.created = datetime(2026, 9, 12, 14, 0, tzinfo=timezone.utc)
        self.run_id = self.ids.new("RUN")
        self.request = ResearchRequest(
            EntityMeta(self.ids.new("RRQ"), "research-request/1.0", 1, self.run_id, self.created, self.actor),
            "Исследовать причины изменения параметра ОЦК решётки",
        )
        self.root = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, ResearchCardKind.OBJECTIVE, self.request.objective,
        )
        dom = create_initial_dom(self.request, self.root, self.ids.new("RDM"))
        self.direction = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, ResearchCardKind.DIRECTION, "D1: peak shift", self.root.meta.id,
            dimensions={"disciplines":["crystallography", "physics_of_metals"], "methods":["xrd"]},
        )
        self.task = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, ResearchCardKind.TASK, "Проверить peak shift", self.direction.meta.id,
            dimensions={"capability":"evidence.verify", "question_types":["measurement"]},
        )
        dom = apply_research_patch(
            dom, ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(self.direction), AddCardOperation(self.task))),
            self.actor, self.ids, self.created, self.ids.new("OPR"), self.ids.new("TXN")
        ).dom
        claim = self.ids.new("CLM")
        gap = Gap(
            id=self.ids.new("GAP"), gap_type="residual_stress_not_excluded", target_claim_ids=(claim,),
            severity="blocking", blocks=(claim,),
            resolution_requirements=("separate composition and residual-stress contributions",),
            status=GapState.OPEN_BLOCKING_GAPS,
        )
        challenge = challenge_from_gap(
            gap, self.request.meta.id,
            EntityMeta(self.ids.new("RCH"), "research-challenge/1.0", 1, self.run_id, self.created, self.actor),
        )
        self.challenge = challenge
        feedback = materialize_challenge_card(
            dom, challenge, parent_card_id=self.task.meta.id, card_id=self.ids.new("RCD"), patch_id=self.ids.new("RPT"),
            actor=self.actor, id_factory=self.ids, timestamp=self.created,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        self.dom = feedback.dom
        self.challenge_card = feedback.card

    def session(self):
        q1 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.DECOMPOSITION_CRITIC, PlanningTurnKind.QUESTION, "Что нужно проверить, чтобы закрыть gap?", target_card_id=self.challenge_card.meta.id)
        a1 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER, "Разделить compositional и stress contributions", parent_turn_id=q1.id, target_card_id=self.challenge_card.meta.id)
        q2 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.METHODOLOGIST, PlanningTurnKind.QUESTION, "Какими наблюдениями это проверить?", parent_turn_id=a1.id, target_card_id=self.challenge_card.meta.id)
        a2 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER, "XRD stress-sensitive evidence + comparison", parent_turn_id=q2.id, target_card_id=self.challenge_card.meta.id)
        return DecompositionSession(
            EntityMeta(self.ids.new("DCS"), "decomposition-session/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, self.challenge_card.meta.id, (q1, a1, q2, a2),
        )

    def good_proposals(self):
        return (
            ResearchCardProposal("q", ResearchCardKind.QUESTION, "Можно ли отделить вклад остаточных напряжений?", self.challenge_card.meta.id),
            ResearchCardProposal("m", ResearchCardKind.METHOD_VIEW, "Stress-sensitive XRD comparison", "q", dimensions={"methods":["xrd"]}),
            ResearchCardProposal("t", ResearchCardKind.TASK, "Найти и сопоставить stress-sensitive XRD evidence", "m", dimensions={"capability":"corpus.search"}),
        )

    def test_challenge_dialectic_expands_to_executable_subtree_and_activates_card(self):
        result = expand_challenge_with_decomposition(
            dom=self.dom, session=self.session(), proposals=self.good_proposals(), id_factory=self.ids,
            actor=self.actor, timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            challenge=self.challenge,
        )
        self.assertEqual(result.local_gate.state, PlanningGateState.PASS)
        self.assertEqual(result.challenge.status.value, "ACTIVE")
        self.assertEqual(result.challenge.meta.revision, self.challenge.meta.revision + 1)
        self.assertEqual(result.local_gate.metrics["executable_leaves"], 1)
        updated = result.dom.cards[self.challenge_card.meta.id]
        self.assertEqual(updated.status, ResearchCardStatus.ACTIVE)
        task = result.compiled.cards[-1]
        self.assertEqual([c.kind for c in result.dom.lineage(task.meta.id)][-4:], [ResearchCardKind.CHALLENGE, ResearchCardKind.QUESTION, ResearchCardKind.METHOD_VIEW, ResearchCardKind.TASK])
        self.assertEqual(task.created_from, (result.session.meta.id,))

    def test_local_research_map_preserves_new_method_dimension(self):
        result = expand_challenge_with_decomposition(
            dom=self.dom, session=self.session(), proposals=self.good_proposals(), id_factory=self.ids,
            actor=self.actor, timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        self.assertIn("xrd", result.compiled.research_map.axes["methods"])

    def test_rejects_non_executable_challenge_expansion(self):
        proposals = (
            ResearchCardProposal("q", ResearchCardKind.QUESTION, "Что влияет на peak shift?", self.challenge_card.meta.id),
        )
        with self.assertRaisesRegex(ChallengePlanningError, "NON_EXECUTABLE_LEAF"):
            expand_challenge_with_decomposition(
                dom=self.dom, session=self.session(), proposals=proposals, id_factory=self.ids,
                actor=self.actor, timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )

    def test_rejects_cross_branch_parent(self):
        proposals = (
            ResearchCardProposal("x", ResearchCardKind.TASK, "Hijack sibling", self.direction.meta.id, dimensions={"capability":"corpus.search"}),
        )
        with self.assertRaisesRegex(ChallengePlanningError, "only to target CHALLENGE"):
            expand_challenge_with_decomposition(
                dom=self.dom, session=self.session(), proposals=proposals, id_factory=self.ids,
                actor=self.actor, timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )

    def test_local_expansion_ignores_unrelated_pending_challenge_branch(self):
        # A second unresolved challenge elsewhere in the same DOM must not block
        # expansion of the current local feedback branch.
        sibling = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.1", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, ResearchCardKind.CHALLENGE, "Unrelated pending gap",
            parent_id=self.task.meta.id, dimensions={"challenge_id": "RCH-unrelated"},
        )
        dom = apply_research_patch(
            self.dom,
            ResearchPatch(self.ids.new("RPT"), self.request.meta.id, self.dom.meta.revision, (AddCardOperation(sibling),)),
            self.actor, self.ids, self.created, self.ids.new("OPR"), self.ids.new("TXN"),
        ).dom
        result = expand_challenge_with_decomposition(
            dom=dom, session=self.session(), proposals=self.good_proposals(), id_factory=self.ids,
            actor=self.actor, timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        self.assertEqual(result.local_gate.state, PlanningGateState.PASS)
        self.assertEqual(result.dom.cards[sibling.meta.id].status, ResearchCardStatus.PLANNED)

    def test_subtree_gate_fails_before_decomposition_and_passes_after(self):
        before = evaluate_planning_subtree_gate(self.dom, self.challenge_card.meta.id)
        self.assertEqual(before.state, PlanningGateState.FAIL)
        result = expand_challenge_with_decomposition(
            dom=self.dom, session=self.session(), proposals=self.good_proposals(), id_factory=self.ids,
            actor=self.actor, timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        after = evaluate_planning_subtree_gate(result.dom, self.challenge_card.meta.id)
        self.assertEqual(after.state, PlanningGateState.PASS)


if __name__ == "__main__":
    unittest.main()
