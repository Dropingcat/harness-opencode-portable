from __future__ import annotations

import random
import sqlite3
import unittest
from datetime import datetime, timezone

from researcher_core.knowledge_reconciliation import (
    ResearchChallengeKind,
    ResearchChallengeRepository,
    ResearchChallengeStatus,
    build_research_knowledge_projection,
    challenge_from_conflict,
    challenge_from_gap,
    materialize_challenge_card,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import ConflictState, GapState
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r1_entities import Conflict, Gap
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
    ResearchTraceRelation,
    ResearchTraceRepository,
)


class Clock:
    def now_ms(self):
        return 1789235000000


class KnowledgeReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(17))
        self.actor = ActorRef("AGENT", "researcher")
        self.created = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)
        self.run_id = self.ids.new("RUN")
        self.request = ResearchRequest(
            EntityMeta(self.ids.new("RRQ"), "research-request/1.0", 1, self.run_id, self.created, self.actor),
            "Исследовать влияние легирования на параметр ОЦК решётки",
        )
        self.root = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id,
            ResearchCardKind.OBJECTIVE,
            self.request.objective,
        )
        self.dom = create_initial_dom(self.request, self.root, self.ids.new("RDM"))
        self.direction = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id,
            ResearchCardKind.DIRECTION,
            "D1: состав матрицы и параметр решётки",
            parent_id=self.root.meta.id,
            dimensions={"disciplines": ["crystallography", "physics_of_metals"], "methods": ["xrd"]},
        )
        self.task = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id,
            ResearchCardKind.TASK,
            "Проверить альтернативное объяснение сдвига линии",
            parent_id=self.direction.meta.id,
            dimensions={"capability": "evidence.verify", "question_types": ["measurement"]},
        )
        patch = ResearchPatch(
            self.ids.new("RPT"), self.request.meta.id, 1,
            (AddCardOperation(self.direction), AddCardOperation(self.task)),
        )
        self.dom = apply_research_patch(
            self.dom, patch, self.actor, self.ids, self.created, self.ids.new("OPR"), self.ids.new("TXN")
        ).dom
        self.claim_1 = self.ids.new("CLM")
        self.claim_2 = self.ids.new("CLM")

    def meta(self, namespace: str, version: str):
        return EntityMeta(self.ids.new(namespace), version, 1, self.run_id, self.created, self.actor)

    def test_gap_becomes_typed_research_challenge_without_duplication(self):
        gap = Gap(
            id=self.ids.new("GAP"),
            gap_type="residual_stress_not_excluded",
            target_claim_ids=(self.claim_1,),
            severity="blocking",
            blocks=(self.claim_1,),
            resolution_requirements=("find stress-sensitive XRD evidence",),
            status=GapState.OPEN_BLOCKING_GAPS,
        )
        challenge = challenge_from_gap(
            gap, self.request.meta.id, self.meta("RCH", "research-challenge/1.0"),
            dimensions={"question_type": "measurement"},
        )
        self.assertEqual(challenge.source_entity_id, gap.id)
        self.assertEqual(challenge.kind, ResearchChallengeKind.GAP_RESOLUTION)
        self.assertEqual(challenge.target_claim_ids, (self.claim_1,))
        self.assertEqual(challenge.resolution_requirements, gap.resolution_requirements)
        self.assertEqual(challenge.status, ResearchChallengeStatus.OPEN)

    def test_conflict_becomes_typed_research_challenge(self):
        conflict = Conflict(
            id=self.ids.new("CNF"),
            member_claim_ids=(self.claim_1, self.claim_2),
            member_evidence_ids=(self.ids.new("EVD"), self.ids.new("EVD")),
            conflict_type="scope_mismatch_or_real_contradiction",
            status=ConflictState.CONFLICT_UNRESOLVED,
        )
        challenge = challenge_from_conflict(
            conflict, self.request.meta.id, self.meta("RCH", "research-challenge/1.0")
        )
        self.assertEqual(challenge.kind, ResearchChallengeKind.CONFLICT_RESOLUTION)
        self.assertEqual(challenge.source_entity_id, conflict.id)
        self.assertEqual(set(challenge.target_claim_ids), {self.claim_1, self.claim_2})
        self.assertIn("aligned scope", challenge.resolution_requirements[0])

    def test_materialize_feedback_creates_historical_challenge_card_and_links(self):
        gap = Gap(
            id=self.ids.new("GAP"), gap_type="residual_stress_not_excluded",
            target_claim_ids=(self.claim_1,), severity="blocking", blocks=(self.claim_1,),
            resolution_requirements=("separate composition and stress effects",),
            status=GapState.OPEN_BLOCKING_GAPS,
        )
        challenge = challenge_from_gap(gap, self.request.meta.id, self.meta("RCH", "research-challenge/1.0"))
        result = materialize_challenge_card(
            self.dom, challenge, parent_card_id=self.task.meta.id, card_id=self.ids.new("RCD"),
            patch_id=self.ids.new("RPT"), actor=self.actor, id_factory=self.ids,
            timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        card = result.card
        self.assertEqual(card.kind, ResearchCardKind.CHALLENGE)
        self.assertEqual(card.parent_id, self.task.meta.id)
        self.assertEqual(card.created_from, (gap.id,))
        self.assertEqual(card.dimensions["disciplines"], ("crystallography", "physics_of_metals"))
        self.assertEqual(card.dimensions["methods"], ("xrd",))
        self.assertEqual(card.dimensions["challenge_id"], str(challenge.meta.id))
        self.assertIn(card.meta.id, result.dom.cards)
        self.assertEqual(
            {link.relation for link in result.trace_links},
            {ResearchTraceRelation.CREATED_CHALLENGE, ResearchTraceRelation.ADDRESSES},
        )

    def test_projection_supports_forward_and_reverse_trace(self):
        gap = Gap(
            id=self.ids.new("GAP"), gap_type="missing_evidence", target_claim_ids=(self.claim_1,),
            severity="blocking", blocks=(self.claim_1,), resolution_requirements=("find evidence",),
            status=GapState.OPEN_BLOCKING_GAPS,
        )
        challenge = challenge_from_gap(gap, self.request.meta.id, self.meta("RCH", "research-challenge/1.0"))
        result = materialize_challenge_card(
            self.dom, challenge, parent_card_id=self.task.meta.id, card_id=self.ids.new("RCD"),
            patch_id=self.ids.new("RPT"), actor=self.actor, id_factory=self.ids,
            timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        projection = build_research_knowledge_projection(result.trace_links)
        self.assertIn(self.task.meta.id, projection.by_card)
        self.assertIn(result.card.meta.id, projection.by_card)
        self.assertIn(challenge.meta.id, projection.by_entity)
        self.assertIn(gap.id, projection.by_entity)

    def test_challenge_and_trace_links_persist_in_existing_sqlite_substrate(self):
        gap = Gap(
            id=self.ids.new("GAP"), gap_type="missing_evidence", target_claim_ids=(self.claim_1,),
            severity="blocking", blocks=(self.claim_1,), resolution_requirements=("find evidence",),
            status=GapState.OPEN_BLOCKING_GAPS,
        )
        challenge = challenge_from_gap(gap, self.request.meta.id, self.meta("RCH", "research-challenge/1.0"))
        result = materialize_challenge_card(
            self.dom, challenge, parent_card_id=self.task.meta.id, card_id=self.ids.new("RCD"),
            patch_id=self.ids.new("RPT"), actor=self.actor, id_factory=self.ids,
            timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        conn = sqlite3.connect(":memory:")
        challenge_repo = ResearchChallengeRepository(conn)
        trace_repo = ResearchTraceRepository(conn)
        challenge_repo.save(challenge)
        trace_repo.save(result.trace_links)
        self.assertEqual(challenge_repo.load(challenge.meta.id), challenge)
        self.assertEqual(len(trace_repo.for_card(result.card.meta.id)), 1)
        conn.close()

    def test_feedback_fails_closed_for_wrong_request(self):
        gap = Gap(
            id=self.ids.new("GAP"), gap_type="missing_evidence", target_claim_ids=(self.claim_1,),
            severity="blocking", blocks=(self.claim_1,), resolution_requirements=(),
            status=GapState.OPEN_BLOCKING_GAPS,
        )
        foreign_request = self.ids.new("RRQ")
        challenge = challenge_from_gap(gap, foreign_request, self.meta("RCH", "research-challenge/1.0"))
        with self.assertRaises(ValueError):
            materialize_challenge_card(
                self.dom, challenge, parent_card_id=self.task.meta.id, card_id=self.ids.new("RCD"),
                patch_id=self.ids.new("RPT"), actor=self.actor, id_factory=self.ids,
                timestamp=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )


if __name__ == "__main__":
    unittest.main()
