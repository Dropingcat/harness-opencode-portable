import random
import sqlite3
import unittest
from datetime import datetime, timezone

from researcher_core.knowledge_reconciliation import ResearchChallenge
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import EdgeKind
from researcher_core.r0.graph import GraphEdge, GraphEdgeState
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r0.registry import InMemoryClaimRegistry, SequenceClock, CycleRandom
from researcher_core.relation_assessment import (
    EvidenceQuality,
    MethodMatch,
    RelationAssessmentProposal,
    RelationAssessmentVerdict,
    assess_relation,
    lifecycle_transition_from_assessment,
)
from researcher_core.relation_feedback import (
    RelationFeedbackError,
    RelationFeedbackRepository,
    gap_from_inconclusive_relation,
    materialize_relation_assessment_feedback,
)
from researcher_core.research_planning import (
    DecompositionSession,
    PlanningInquiryTurn,
    PlanningRole,
    PlanningTurnKind,
    ResearchCard,
    ResearchCardKind,
    ResearchCardProposal,
    ResearchCardStatus,
    ResearchDOM,
)
from researcher_core.challenge_planning import expand_challenge_with_decomposition
from researcher_core.research_planning_runtime import PlanningGateState
from researcher_core.strict_reasoning import build_strict_reasoning_dependencies


class Clock:
    def now_ms(self):
        return 1789260000000


class R34ControlLoopTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(97))
        self.actor = ActorRef("AGENT", "researcher")
        self.t = datetime(2026, 9, 13, 3, 0, tzinfo=timezone.utc)
        self.run = self.ids.new("RUN")
        self.req = self.ids.new("RRQ")
        self.root = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run, self.t, self.actor),
            self.req, ResearchCardKind.OBJECTIVE, "Objective",
        )
        self.task = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 2, self.run, self.t, self.actor),
            self.req, ResearchCardKind.TASK, "Task", parent_id=self.root.meta.id,
            status=ResearchCardStatus.COMPLETED, dimensions={"capability": "fixture"},
        )
        self.dom = ResearchDOM(
            EntityMeta(self.ids.new("RDM"), "research-dom/1.0", 1, self.run, self.t, self.actor),
            self.req, self.root.meta.id,
            {self.root.meta.id: self.root, self.task.meta.id: self.task}, (),
        )
        self.evd = self.ids.new("EVD")
        self.clm = self.ids.new("CLM")
        self.edge = GraphEdge(
            EntityMeta(self.ids.new("EDG"), "graph-edge/1.0", 1, self.run, self.t, self.actor),
            self.evd, self.clm, EdgeKind.SUPPORTS, {"scope_overlap": True}, GraphEdgeState.ACTIVE,
        )

    def proposal(self, *, quality=EvidenceQuality.UNKNOWN, scope="MATCH"):
        return RelationAssessmentProposal(
            EntityMeta(self.ids.new("RAP"), "relation-assessment-proposal/1.0", 1, self.run, self.t, self.actor),
            self.task.meta.id, self.edge.meta.id, self.edge.meta.revision,
            scope, "DIRECT", MethodMatch.MATCH, quality,
            "relation assessment", supporting_refs=(self.evd,),
        )

    def test_inconclusive_relation_becomes_blocking_gap(self):
        assessment, _ = assess_relation(
            edge=self.edge, proposal=self.proposal(), id_factory=self.ids,
            actor=self.actor, created_at=self.t,
        )
        gap = gap_from_inconclusive_relation(edge=self.edge, assessment=assessment, gap_id=self.ids.new("GAP"))
        self.assertEqual(gap.gap_type, "RELATION_ASSESSMENT_INCONCLUSIVE")
        self.assertEqual(gap.target_claim_ids, (self.clm,))
        self.assertIn("reassess relation", " ".join(gap.resolution_requirements))

    def test_inconclusive_relation_materializes_challenge_under_origin_task(self):
        assessment, _ = assess_relation(
            edge=self.edge, proposal=self.proposal(), id_factory=self.ids,
            actor=self.actor, created_at=self.t,
        )
        result = materialize_relation_assessment_feedback(
            dom=self.dom, edge=self.edge, assessment=assessment, existing_challenges=(),
            id_factory=self.ids, actor=self.actor, timestamp=self.t,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        self.assertEqual(result.feedback.card.parent_id, self.task.meta.id)
        self.assertEqual(result.feedback.card.kind, ResearchCardKind.CHALLENGE)
        self.assertEqual(result.challenge.dimensions["relation_assessment_id"], str(assessment.meta.id))
        self.assertEqual(result.challenge.dimensions["edge_id"], str(self.edge.meta.id))
        self.assertEqual(result.feedback.dom.cards[result.feedback.card.meta.id].status, ResearchCardStatus.PLANNED)

    def test_same_assessment_cannot_create_duplicate_challenge(self):
        assessment, _ = assess_relation(
            edge=self.edge, proposal=self.proposal(), id_factory=self.ids,
            actor=self.actor, created_at=self.t,
        )
        first = materialize_relation_assessment_feedback(
            dom=self.dom, edge=self.edge, assessment=assessment, existing_challenges=(),
            id_factory=self.ids, actor=self.actor, timestamp=self.t,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        with self.assertRaisesRegex(RelationFeedbackError, "already has research challenge"):
            materialize_relation_assessment_feedback(
                dom=first.feedback.dom, edge=self.edge, assessment=assessment,
                existing_challenges=(first.challenge,), id_factory=self.ids, actor=self.actor,
                timestamp=self.t, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )

    def test_rejected_relation_does_not_use_gap_feedback_path(self):
        assessment, _ = assess_relation(
            edge=self.edge, proposal=self.proposal(scope="DISJOINT", quality=EvidenceQuality.ADEQUATE),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        self.assertEqual(assessment.verdict, RelationAssessmentVerdict.REJECTED)
        with self.assertRaisesRegex(RelationFeedbackError, "only INCONCLUSIVE"):
            gap_from_inconclusive_relation(edge=self.edge, assessment=assessment, gap_id=self.ids.new("GAP"))

    def test_strict_reasoning_facade_never_uses_unassessed_edge_semantics(self):
        build = build_strict_reasoning_dependencies(
            graph_edges=(self.edge,), relation_assessments=(), id_factory=self.ids,
            actor=self.actor, run_id=self.run, created_at=self.t,
        )
        semantic = [d for d in build.dependencies if d.source_id.namespace == "EDG"]
        self.assertFalse(semantic)
        self.assertTrue(any(x.startswith("UNASSESSED_EDGE_SEMANTIC_USE_EXCLUDED") for x in build.diagnostics))

    def test_strict_reasoning_facade_uses_accepted_edge_semantics(self):
        assessment, _ = assess_relation(
            edge=self.edge,
            proposal=self.proposal(quality=EvidenceQuality.ADEQUATE),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        build = build_strict_reasoning_dependencies(
            graph_edges=(self.edge,), relation_assessments=(assessment,), id_factory=self.ids,
            actor=self.actor, run_id=self.run, created_at=self.t,
        )
        semantic = [d for d in build.dependencies if d.source_id.namespace == "EDG"]
        self.assertEqual(len(semantic), 1)
        self.assertEqual(semantic[0].metadata["relation_assessment_id"], str(assessment.meta.id))

    def test_registry_canonical_edge_update_persists_lifecycle_revision(self):
        registry = InMemoryClaimRegistry(SequenceClock(1789260001000), CycleRandom())
        registry.state[self.edge.meta.id] = self.edge
        assessment, _ = assess_relation(
            edge=self.edge, proposal=self.proposal(scope="DISJOINT", quality=EvidenceQuality.ADEQUATE),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        transition = lifecycle_transition_from_assessment(
            edge=self.edge, assessment=assessment, actor=self.actor, id_factory=self.ids,
            timestamp=self.t, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        updated = registry.update_graph_edge(transition.edge, transition.event, expected_revision=1)
        self.assertEqual(updated.state, GraphEdgeState.INVALIDATED)
        self.assertEqual(registry.state[self.edge.meta.id].meta.revision, 2)
        self.assertEqual(registry.events[-1].event_type, "EDGE_STATE_CHANGED")

    def test_registry_edge_update_is_optimistic_concurrency_checked(self):
        registry = InMemoryClaimRegistry(SequenceClock(1789260002000), CycleRandom())
        registry.state[self.edge.meta.id] = self.edge
        assessment, _ = assess_relation(
            edge=self.edge, proposal=self.proposal(scope="DISJOINT", quality=EvidenceQuality.ADEQUATE),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        transition = lifecycle_transition_from_assessment(
            edge=self.edge, assessment=assessment, actor=self.actor, id_factory=self.ids,
            timestamp=self.t, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        with self.assertRaisesRegex(ValueError, "expected_revision"):
            registry.update_graph_edge(transition.edge, transition.event, expected_revision=2)

    def test_relation_feedback_gap_and_challenge_persist_atomically(self):
        assessment, _ = assess_relation(
            edge=self.edge, proposal=self.proposal(), id_factory=self.ids,
            actor=self.actor, created_at=self.t,
        )
        feedback = materialize_relation_assessment_feedback(
            dom=self.dom, edge=self.edge, assessment=assessment, existing_challenges=(),
            id_factory=self.ids, actor=self.actor, timestamp=self.t,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        conn = sqlite3.connect(":memory:")
        repo = RelationFeedbackRepository(conn)
        repo.save(feedback.gap, feedback.challenge)
        loaded = repo.load_gap(feedback.gap.id)
        self.assertEqual(loaded, feedback.gap)
        from researcher_core.r0.sqlite_store import SqliteUnitOfWork
        state = SqliteUnitOfWork(conn).state_view()
        self.assertIn(str(feedback.challenge.meta.id), state)
        conn.close()

    def test_full_relation_feedback_loop_reaches_executable_task(self):
        assessment, _ = assess_relation(
            edge=self.edge, proposal=self.proposal(), id_factory=self.ids,
            actor=self.actor, created_at=self.t,
        )
        feedback = materialize_relation_assessment_feedback(
            dom=self.dom, edge=self.edge, assessment=assessment, existing_challenges=(),
            id_factory=self.ids, actor=self.actor, timestamp=self.t,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        challenge_card = feedback.feedback.card
        q1 = PlanningInquiryTurn(
            self.ids.new("PIT"), PlanningRole.DECOMPOSITION_CRITIC, PlanningTurnKind.QUESTION,
            "Что отсутствует для разрешения relation assessment?", target_card_id=challenge_card.meta.id,
        )
        a1 = PlanningInquiryTurn(
            self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER,
            "Нужны данные о качестве evidence и применимости метода", parent_turn_id=q1.id, target_card_id=challenge_card.meta.id,
        )
        q2 = PlanningInquiryTurn(
            self.ids.new("PIT"), PlanningRole.METHODOLOGIST, PlanningTurnKind.QUESTION,
            "Как получить недостающие данные?", parent_turn_id=a1.id, target_card_id=challenge_card.meta.id,
        )
        a2 = PlanningInquiryTurn(
            self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER,
            "Проверить первичный источник и методическую применимость", parent_turn_id=q2.id, target_card_id=challenge_card.meta.id,
        )
        session = DecompositionSession(
            EntityMeta(self.ids.new("DCS"), "decomposition-session/1.0", 1, self.run, self.t, self.actor),
            self.req, challenge_card.meta.id, (q1, a1, q2, a2),
        )
        proposals = (
            ResearchCardProposal("q", ResearchCardKind.QUESTION, "Достаточно ли evidence?", challenge_card.meta.id),
            ResearchCardProposal("m", ResearchCardKind.METHOD_VIEW, "Primary-source verification", "q", dimensions={"methods": ["source_verification"]}),
            ResearchCardProposal("t", ResearchCardKind.TASK, "Проверить источник и метод", "m", dimensions={"capability": "evidence.verify"}),
        )
        expanded = expand_challenge_with_decomposition(
            dom=feedback.feedback.dom, session=session, proposals=proposals, id_factory=self.ids,
            actor=self.actor, timestamp=self.t, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            challenge=feedback.challenge,
        )
        self.assertEqual(expanded.local_gate.state, PlanningGateState.PASS)
        self.assertEqual(expanded.challenge.status.value, "ACTIVE")
        self.assertEqual(expanded.compiled.cards[-1].kind, ResearchCardKind.TASK)
        self.assertEqual(expanded.compiled.cards[-1].dimensions["capability"], "evidence.verify")


if __name__ == "__main__":
    unittest.main()
