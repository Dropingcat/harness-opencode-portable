from __future__ import annotations

import random
import unittest
from datetime import UTC, datetime

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.research_planning import (
    AddCardOperation,
    DecompositionSession,
    PlanningInquiryTurn,
    PlanningRole,
    PlanningTurnKind,
    ResearchCard,
    ResearchCardKind,
    ResearchCardStatus,
    ResearchCardProposal,
    ResearchDOMRevisionConflict,
    ResearchPatch,
    ResearchPatchConflict,
    ResearchRequest,
    SetCardStatusOperation,
    apply_research_patch,
    build_research_map,
    create_initial_dom,
    compile_decomposition_proposals,
)


class FixedClock:
    def __init__(self) -> None:
        self.value = 1_800_000_000_000

    def now_ms(self) -> int:
        self.value += 1
        return self.value


class ResearchPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FixedClock()
        self.random = random.Random(42)
        self.ids = EntityIdFactory(self.clock, self.random)
        self.actor = ActorRef("AGENT", "researcher")
        self.run_id = self.ids.new("RUN")
        self.created = datetime(2026, 9, 12, tzinfo=UTC)
        self.request = ResearchRequest(
            meta=self.meta("RRQ", "research-request/1.0"),
            objective="Исследовать влияние легирующих элементов на параметр ОЦК-решётки стали",
            constraints={"material_class": "steel"},
        )
        self.root = self.card(
            ResearchCardKind.OBJECTIVE,
            "Влияние легирования на ОЦК-решётку",
            parent=None,
        )
        self.dom = create_initial_dom(self.request, self.root, self.ids.new("RDM"))

    def meta(self, prefix: str, schema: str = "test/1.0") -> EntityMeta:
        return EntityMeta(
            id=self.ids.new(prefix),
            schema_version=schema,
            revision=1,
            run_id=self.run_id,
            created_at=self.created,
            created_by=self.actor,
        )

    def card(self, kind, title, parent, dimensions=None, created_from=()):
        return ResearchCard(
            meta=self.meta("RCD", "research-card/1.0"),
            request_id=self.request.meta.id,
            kind=kind,
            title=title,
            parent_id=parent,
            dimensions=dimensions or {},
            created_from=created_from,
        )

    def apply(self, dom, patch):
        return apply_research_patch(
            dom,
            patch,
            actor=self.actor,
            id_factory=self.ids,
            timestamp=self.created,
            causation_id=self.ids.new("OPR"),
            correlation_id=self.run_id,
        )

    def test_initial_dom_has_objective_root(self):
        self.assertEqual(self.dom.meta.revision, 1)
        self.assertEqual(self.dom.root_card_id, self.root.meta.id)
        self.assertEqual(self.dom.lineage(self.root.meta.id), (self.root,))

    def test_patch_adds_historical_card_tree_atomically(self):
        d1 = self.card(
            ResearchCardKind.DIRECTION,
            "Изменение параметра ОЦК-решётки",
            self.root.meta.id,
            {"disciplines": ["physics_of_metals", "crystallography"], "methods": ["xrd"]},
        )
        xrd = self.card(ResearchCardKind.METHOD_VIEW, "XRD", d1.meta.id, {"methods": ["xrd"]})
        task = self.card(ResearchCardKind.TASK, "Найти зависимости a(c) для Fe-X", xrd.meta.id)
        patch = ResearchPatch(
            id=self.ids.new("RPT"),
            request_id=self.request.meta.id,
            expected_dom_revision=1,
            operations=(AddCardOperation(d1), AddCardOperation(xrd), AddCardOperation(task)),
        )
        result = self.apply(self.dom, patch)
        self.assertEqual(result.dom.meta.revision, 2)
        self.assertEqual([c.meta.id for c in result.dom.lineage(task.meta.id)], [self.root.meta.id, d1.meta.id, xrd.meta.id, task.meta.id])
        self.assertEqual(len(result.events), 4)
        self.assertEqual(result.events[-1].event_type, "RESEARCH_PATCH_APPLIED")

    def test_stale_dom_patch_fails_closed(self):
        d1 = self.card(ResearchCardKind.DIRECTION, "D1", self.root.meta.id)
        p1 = ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(d1),))
        updated = self.apply(self.dom, p1).dom
        d2 = self.card(ResearchCardKind.DIRECTION, "D2", self.root.meta.id)
        stale = ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(d2),))
        with self.assertRaises(ResearchDOMRevisionConflict):
            self.apply(updated, stale)

    def test_missing_parent_fails_atomically(self):
        fake_parent = self.ids.new("RCD")
        orphan = self.card(ResearchCardKind.TASK, "orphan", fake_parent)
        patch = ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(orphan),))
        with self.assertRaises(ResearchPatchConflict):
            self.apply(self.dom, patch)
        self.assertEqual(len(self.dom.cards), 1)

    def test_status_change_is_revision_checked(self):
        d1 = self.card(ResearchCardKind.DIRECTION, "D1", self.root.meta.id)
        p1 = ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(d1),))
        dom2 = self.apply(self.dom, p1).dom
        p2 = ResearchPatch(
            self.ids.new("RPT"), self.request.meta.id, 2,
            (SetCardStatusOperation(d1.meta.id, 1, ResearchCardStatus.ACTIVE),),
        )
        result = self.apply(dom2, p2)
        changed = result.dom.cards[d1.meta.id]
        self.assertEqual(changed.status, ResearchCardStatus.ACTIVE)
        self.assertEqual(changed.meta.revision, 2)
        self.assertEqual(result.events[0].event_type, "RESEARCH_CARD_STATE_CHANGED")

    def test_reapplying_same_patch_fails(self):
        d1 = self.card(ResearchCardKind.DIRECTION, "D1", self.root.meta.id)
        patch = ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(d1),))
        dom2 = self.apply(self.dom, patch).dom
        replay = ResearchPatch(patch.id, self.request.meta.id, 2, (SetCardStatusOperation(d1.meta.id, 1, ResearchCardStatus.ACTIVE),))
        with self.assertRaises(ResearchPatchConflict):
            self.apply(dom2, replay)

    def test_research_map_is_projection_not_dom_mutation(self):
        d1 = self.card(
            ResearchCardKind.DIRECTION,
            "Легирование и параметр решётки",
            self.root.meta.id,
            {"disciplines": ["physics_of_metals", "crystallography"], "methods": ["xrd", "tem"], "question_types": ["mechanistic", "measurement"]},
        )
        research_map = build_research_map(self.meta("RMP", "research-map/1.0"), self.request.meta.id, (d1,))
        self.assertIn("physics_of_metals", research_map.axes["disciplines"])
        self.assertIn("xrd", research_map.axes["methods"])
        self.assertEqual(len(self.dom.cards), 1)

    def test_decomposition_session_keeps_question_answer_history(self):
        q1 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.DECOMPOSITION_CRITIC, PlanningTurnKind.QUESTION, "Что нужно знать для исследования X?")
        a1 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER, "D1: физика металлов; D2: измерительные эффекты", parent_turn_id=q1.id, extracted={"directions": ["D1", "D2"]})
        q2 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.METHODOLOGIST, PlanningTurnKind.QUESTION, "Какие методы нужны для D1?", parent_turn_id=a1.id)
        a2 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER, "XRD, TEM, EDS", parent_turn_id=q2.id, extracted={"methods": ["xrd", "tem", "eds"]})
        session = DecompositionSession(self.meta("DCS", "decomposition-session/1.0"), self.request.meta.id, self.root.meta.id, (q1, a1, q2, a2))
        self.assertEqual(len(session.turns), 4)
        self.assertEqual(session.turns[-1].parent_turn_id, q2.id)

    def test_dialectic_proposals_compile_to_map_and_atomic_patch(self):
        q1 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.DECOMPOSITION_CRITIC, PlanningTurnKind.QUESTION, "Какие направления нужны?")
        a1 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER, "D1: параметр решётки; D2: вторичные фазы", parent_turn_id=q1.id)
        q2 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.METHODOLOGIST, PlanningTurnKind.QUESTION, "Как исследовать D1?", parent_turn_id=a1.id)
        a2 = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER, "Физика металлов + XRD", parent_turn_id=q2.id)
        session = DecompositionSession(self.meta("DCS", "decomposition-session/1.0"), self.request.meta.id, self.root.meta.id, (q1, a1, q2, a2))
        proposals = (
            ResearchCardProposal("d1", ResearchCardKind.DIRECTION, "Изменение параметра ОЦК-решётки", self.root.meta.id, dimensions={"disciplines": ["physics_of_metals", "crystallography"], "question_types": ["mechanistic", "measurement"]}),
            ResearchCardProposal("m1", ResearchCardKind.METHOD_VIEW, "Рентгеновская дифракция", "d1", dimensions={"methods": ["xrd"]}),
            ResearchCardProposal("t1", ResearchCardKind.TASK, "Найти зависимости a(c) и проверить peak-shift alternatives", "m1", dimensions={"capability": "corpus.search"}),
        )
        compiled = compile_decomposition_proposals(session=session, dom=self.dom, proposals=proposals, id_factory=self.ids, actor=self.actor, created_at=self.created)
        self.assertEqual(len(compiled.cards), 3)
        self.assertIn("physics_of_metals", compiled.research_map.axes["disciplines"])
        self.assertIn("xrd", compiled.research_map.axes["methods"])
        result = self.apply(self.dom, compiled.patch)
        task = compiled.cards[-1]
        self.assertEqual([card.kind for card in result.dom.lineage(task.meta.id)], [ResearchCardKind.OBJECTIVE, ResearchCardKind.DIRECTION, ResearchCardKind.METHOD_VIEW, ResearchCardKind.TASK])
        self.assertEqual(task.created_from, (session.meta.id,))

    def test_research_card_state_reason_code_is_registered(self):
        from pathlib import Path
        from researcher_core.policy import load_policy
        policy = load_policy(Path("."))
        self.assertIn("RESEARCH_CARD_STATE_CHANGED", policy.reason_codes)

    def test_compile_rejects_duplicate_sibling_proposals(self):
        q = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.DECOMPOSITION_CRITIC, PlanningTurnKind.QUESTION, "Что исследовать?")
        a = PlanningInquiryTurn(self.ids.new("PIT"), PlanningRole.PLANNER, PlanningTurnKind.ANSWER, "D1", parent_turn_id=q.id)
        session = DecompositionSession(self.meta("DCS", "decomposition-session/1.0"), self.request.meta.id, self.root.meta.id, (q, a))
        proposals = (
            ResearchCardProposal("d1", ResearchCardKind.DIRECTION, "Параметр решётки", self.root.meta.id),
            ResearchCardProposal("d2", ResearchCardKind.DIRECTION, "  параметр   решётки ", self.root.meta.id),
        )
        from researcher_core.research_planning import PlanningCompileError
        with self.assertRaises(PlanningCompileError):
            compile_decomposition_proposals(session=session, dom=self.dom, proposals=proposals, id_factory=self.ids, actor=self.actor, created_at=self.created)


if __name__ == "__main__":
    unittest.main()
