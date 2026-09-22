from __future__ import annotations

import random
import sqlite3
import unittest
from pathlib import Path
from datetime import datetime, timezone

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.research_planning import (
    AddCardOperation,
    ResearchCard,
    ResearchCardKind,
    ResearchPatch,
    ResearchRequest,
    apply_research_patch,
    create_initial_dom,
)
from researcher_core.research_planning_runtime import (
    PlanningGatePolicy,
    PlanningGateState,
    ResearchDOMRepository,
    ResearchTraceLink,
    ResearchTraceRelation,
    ResearchTraceRepository,
    evaluate_planning_gate,
    replay_research_dom,
    planning_gate_policy_from_policy,
)


class Clock:
    def now_ms(self): return 1789230000000


class PlanningRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(7))
        self.actor = ActorRef("AGENT", "researcher")
        self.created = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)
        self.run_id = self.ids.new("RUN")
        self.request = ResearchRequest(
            EntityMeta(self.ids.new("RRQ"), "research-request/1.0", 1, self.run_id, self.created, self.actor),
            "Исследовать изменение параметра ОЦК решётки",
        )
        self.root = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, ResearchCardKind.OBJECTIVE, self.request.objective,
        )
        self.dom = create_initial_dom(self.request, self.root, self.ids.new("RDM"))

    def card(self, kind, title, parent, dimensions=None):
        return ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, kind, title, parent_id=parent, dimensions=dimensions or {},
        )

    def apply(self, dom, patch):
        return apply_research_patch(dom, patch, self.actor, self.ids, self.created, self.ids.new("OPR"), self.ids.new("TXN"))

    def test_gate_passes_executable_tree(self):
        d = self.card(ResearchCardKind.DIRECTION, "D1", self.root.meta.id)
        t = self.card(ResearchCardKind.TASK, "Найти зависимости a(c)", d.meta.id, {"capability":"corpus.search"})
        result = self.apply(self.dom, ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(d), AddCardOperation(t))))
        report = evaluate_planning_gate(result.dom)
        self.assertEqual(report.state, PlanningGateState.PASS)
        self.assertEqual(report.metrics["executable_leaves"], 1)

    def test_gate_rejects_non_executable_leaf_and_budget(self):
        d = self.card(ResearchCardKind.DIRECTION, "D1", self.root.meta.id)
        q = self.card(ResearchCardKind.QUESTION, "Почему меняется a?", d.meta.id)
        result = self.apply(self.dom, ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(d), AddCardOperation(q))))
        report = evaluate_planning_gate(result.dom, PlanningGatePolicy(max_cards=2))
        self.assertEqual(report.state, PlanningGateState.FAIL)
        self.assertIn("NON_EXECUTABLE_LEAF", {x.code for x in report.issues})
        self.assertIn("CARD_BUDGET_EXCEEDED", {x.code for x in report.issues})

    def test_sqlite_roundtrip_restores_full_dom(self):
        d = self.card(ResearchCardKind.DIRECTION, "D1", self.root.meta.id, {"disciplines":["crystallography"]})
        result = self.apply(self.dom, ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(d),)))
        conn = sqlite3.connect(":memory:")
        repo = ResearchDOMRepository(conn)
        repo.save(result.dom, result.events)
        loaded = repo.load(result.dom.meta.id)
        self.assertEqual(loaded, result.dom)
        self.assertEqual(loaded.cards[d.meta.id].dimensions["disciplines"], ("crystallography",))
        conn.close()

    def test_event_replay_rebuilds_dom(self):
        d = self.card(ResearchCardKind.DIRECTION, "D1", self.root.meta.id)
        t = self.card(ResearchCardKind.TASK, "Search", d.meta.id, {"capability":"corpus.search"})
        result = self.apply(self.dom, ResearchPatch(self.ids.new("RPT"), self.request.meta.id, 1, (AddCardOperation(d), AddCardOperation(t))))
        replayed = replay_research_dom(self.dom, result.events)
        self.assertEqual(replayed, result.dom)

    def test_planning_gate_reads_limits_from_policy(self):
        from researcher_core.policy import load_policy
        policy = planning_gate_policy_from_policy(load_policy(Path(".")))
        self.assertEqual(policy.max_cards, 80)
        self.assertEqual(policy.max_depth, 8)

    def test_trace_repository_persists_card_knowledge_links(self):
        conn = sqlite3.connect(":memory:")
        claim = self.ids.new("CLM")
        gap = self.ids.new("GAP")
        links = (
            ResearchTraceLink(self.ids.new("RTL"), self.root.meta.id, claim, ResearchTraceRelation.PRODUCED, self.run_id, self.created, self.actor, {"task":"extract"}),
            ResearchTraceLink(self.ids.new("RTL"), self.root.meta.id, gap, ResearchTraceRelation.DISCOVERED, self.run_id, self.created, self.actor, {"from_claim":str(claim)}),
        )
        repo = ResearchTraceRepository(conn)
        repo.save(links)
        loaded = repo.for_card(self.root.meta.id)
        self.assertEqual({x.target_id.namespace for x in loaded}, {"CLM", "GAP"})
        conn.close()

    def test_trace_link_connects_card_to_claim(self):
        link = ResearchTraceLink(
            id=self.ids.new("RTL"), research_card_id=self.root.meta.id, target_id=self.ids.new("CLM"),
            relation=ResearchTraceRelation.PRODUCED, run_id=self.run_id, created_at=self.created,
            created_by=self.actor, metadata={"reason":"task-output"},
        )
        self.assertEqual(link.target_id.namespace, "CLM")
        self.assertEqual(link.relation, ResearchTraceRelation.PRODUCED)


if __name__ == "__main__":
    unittest.main()
