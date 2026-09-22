from __future__ import annotations

import random
import unittest
from dataclasses import replace
from datetime import datetime, timezone

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_argument_graph import (
    ArgumentRelation,
    ArgumentRelationKind,
    TribunalArgumentGraphError,
    build_argument_graph,
    validate_argument_graph_integrity,
)
from researcher_core.tribunal_composition import AssessmentNeedRef
from researcher_core.tribunal_inquiry import ArgumentArtifact, ArgumentPosition, InquiryTurn, InquiryTurnKind


class Clock:
    def now_ms(self):
        return 1789272000000


class TribunalArgumentGraphTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(8844))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.contract = self.ids.new("IQC")
        self.need = AssessmentNeedRef("ANR-argumentgraph000001", 0)
        self.claim = self.ids.new("CLM")
        self.evd = self.ids.new("EVD")
        self.t = datetime(2026, 9, 13, 16, 0, tzinfo=timezone.utc)

    def meta(self, ns, schema, *, entity_id=None, revision=1):
        return EntityMeta(entity_id or self.ids.new(ns), schema, revision, self.run, self.t, self.actor)

    def argument(self, role, position, text):
        turn = InquiryTurn(
            self.meta("IQT", "inquiry-turn/1.0"), self.contract, role,
            InquiryTurnKind.FIRST_PASS_ASSESSMENT, text, None, (self.claim, self.evd),
        )
        arg = ArgumentArtifact(
            self.meta("ARG", "argument-artifact/1.0"), self.contract, turn.meta.id,
            role, position, (self.need,), text, text + " justification",
            (self.evd,), (self.claim,), (), (),
        )
        return turn, arg

    def relation(self, kind, source, target, *, material=True):
        return ArgumentRelation(
            self.meta("ARL", "argument-relation/1.0"), kind,
            source.meta.id, target.meta.id, (self.need,), material=material,
            reason_codes=("fixture",),
        )

    def test_real_branching_graph_has_one_root_and_two_heads(self):
        _, root = self.argument("xrd_specialist", ArgumentPosition.QUALIFY, "root")
        _, skeptical = self.argument("skeptic", ArgumentPosition.CHALLENGE, "attack")
        _, methodological = self.argument("methodologist", ArgumentPosition.CHALLENGE, "undercut")
        _, defense = self.argument("advocate", ArgumentPosition.SUPPORT, "defense")
        attack = self.relation(ArgumentRelationKind.ATTACKS, skeptical, root)
        undercut = self.relation(ArgumentRelationKind.UNDERCUTS, methodological, root)
        reply = self.relation(ArgumentRelationKind.REPLIES_TO, defense, skeptical)
        defends = self.relation(ArgumentRelationKind.DEFENDS, defense, root)

        graph = build_argument_graph(
            meta=self.meta("AGP", "argument-graph-projection/1.0"),
            arguments=(root, skeptical, methodological, defense),
            relations=(attack, undercut, reply, defends),
        )
        self.assertEqual(graph.root_argument_ids, (root.meta.id,))
        self.assertEqual(set(graph.branch_head_ids), {methodological.meta.id, defense.meta.id})
        self.assertTrue(graph.graph_fingerprint.startswith("sha256:"))

    def test_graph_fingerprint_tamper_fails_integrity(self):
        _, root = self.argument("xrd_specialist", ArgumentPosition.QUALIFY, "root")
        _, skeptical = self.argument("skeptic", ArgumentPosition.CHALLENGE, "attack")
        attack = self.relation(ArgumentRelationKind.ATTACKS, skeptical, root)
        graph = build_argument_graph(
            meta=self.meta("AGP", "argument-graph-projection/1.0"),
            arguments=(root, skeptical), relations=(attack,),
        )
        with self.assertRaisesRegex(TribunalArgumentGraphError, "fingerprint"):
            validate_argument_graph_integrity(replace(graph, graph_fingerprint="sha256:" + "0" * 64), (root, skeptical))


    def test_attack_source_must_be_challenge(self):
        _, root = self.argument("xrd_specialist", ArgumentPosition.QUALIFY, "root")
        _, invalid = self.argument("critic", ArgumentPosition.SUPPORT, "not challenge")
        attack = self.relation(ArgumentRelationKind.ATTACKS, invalid, root)
        with self.assertRaises(TribunalArgumentGraphError):
            build_argument_graph(
                meta=self.meta("AGP", "argument-graph-projection/1.0"),
                arguments=(root, invalid), relations=(attack,),
            )

    def test_argument_cycles_fail_closed(self):
        _, a = self.argument("skeptic", ArgumentPosition.CHALLENGE, "a")
        _, b = self.argument("critic", ArgumentPosition.CHALLENGE, "b")
        ab = self.relation(ArgumentRelationKind.ATTACKS, a, b)
        ba = self.relation(ArgumentRelationKind.UNDERCUTS, b, a)
        with self.assertRaisesRegex(TribunalArgumentGraphError, "cycle"):
            build_argument_graph(
                meta=self.meta("AGP", "argument-graph-projection/1.0"),
                arguments=(a, b), relations=(ab, ba),
            )


if __name__ == "__main__":
    unittest.main()
