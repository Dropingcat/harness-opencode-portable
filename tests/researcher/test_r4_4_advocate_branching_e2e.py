from __future__ import annotations

import random
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.knowledge_reconciliation import challenge_from_gap
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_advocate import (
    AdvocateNextAction,
    AdvocateOutcome,
    AdvocateWorkerDraft,
    TribunalAdvocateError,
    compile_advocate_defense_contract,
    compile_advocate_disclosure,
    decide_advocate_activation,
    materialize_advocate_draft,
    validate_disclosure_contract_integrity,
)
from researcher_core.tribunal_argument_graph import (
    ArgumentRelation,
    ArgumentRelationKind,
    append_argument_branch,
    build_argument_graph,
)
from researcher_core.tribunal_composition import AssessmentNeedRef, load_tribunal_composition_policy
from researcher_core.tribunal_dialectic import (
    DialecticAction,
    DialecticHistory,
    DialecticLevel,
    gap_from_emergent_issue,
    observe_dialectic_step,
)
from researcher_core.tribunal_inquiry import (
    AdditionalEvidenceRequest,
    ArgumentArtifact,
    ArgumentPosition,
    InquiryTurn,
    InquiryTurnKind,
    ResponseGroundingItem,
    ResponseGroundingKind,
)
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self):
        return 1789272000000


class AdvocateBranchingE2E(unittest.TestCase):
    def setUp(self):
        self.root_dir = Path(__file__).resolve().parents[2]
        self.policy = load_tribunal_composition_policy(self.root_dir / "config" / "tribunal_composition.yaml")
        self.handbook = load_role_handbook(self.root_dir / "config" / "tribunal_role_handbook.yaml", self.policy)
        self.ids = EntityIdFactory(Clock(), random.Random(9944))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.rrq = self.ids.new("RRQ")
        self.contract = self.ids.new("IQC")
        self.need = AssessmentNeedRef("ANR-advocatebranch00001", 0)
        self.claim = self.ids.new("CLM")
        self.evd_support = self.ids.new("EVD")
        self.evd_attack = self.ids.new("EVD")
        self.evd_hidden = self.ids.new("EVD")
        self.t = datetime(2026, 9, 13, 16, 30, tzinfo=timezone.utc)

    def meta(self, ns, schema, *, entity_id=None, revision=1):
        return EntityMeta(entity_id or self.ids.new(ns), schema, revision, self.run, self.t, self.actor)

    def arg(self, role, position, text, evd, kind=InquiryTurnKind.FIRST_PASS_ASSESSMENT):
        turn = InquiryTurn(
            self.meta("IQT", "inquiry-turn/1.0"), self.contract, role, kind,
            text, None, (self.claim, evd),
        )
        arg = ArgumentArtifact(
            self.meta("ARG", "argument-artifact/1.0"), self.contract, turn.meta.id,
            role, position, (self.need,), text, text + " justification",
            (evd,), (self.claim,), (), (),
        )
        return turn, arg

    def relation(self, kind, source, target, *, material=True):
        return ArgumentRelation(
            self.meta("ARL", "argument-relation/1.0"), kind,
            source.meta.id, target.meta.id, (self.need,), material=material,
            reason_codes=("fixture",),
        )

    def fixture_graph(self):
        root_turn, root = self.arg("xrd_specialist", ArgumentPosition.QUALIFY, "XRD interpretation remains qualified", self.evd_support)
        challenge_turn, challenge = self.arg("skeptic", ArgumentPosition.CHALLENGE, "Residual stress remains alternative", self.evd_attack, InquiryTurnKind.CHALLENGE)
        sibling_turn, sibling = self.arg("methodologist", ArgumentPosition.CHALLENGE, "Calibration undercuts uniqueness", self.evd_hidden, InquiryTurnKind.CHALLENGE)
        attack = self.relation(ArgumentRelationKind.ATTACKS, challenge, root, material=True)
        undercut = self.relation(ArgumentRelationKind.UNDERCUTS, sibling, root, material=True)
        graph = build_argument_graph(
            meta=self.meta("AGP", "argument-graph-projection/1.0"),
            arguments=(root, challenge, sibling), relations=(attack, undercut),
        )
        return root_turn, root, challenge_turn, challenge, sibling_turn, sibling, attack, undercut, graph

    def test_conditional_advocate_isolated_branch_defense_and_downstream_research(self):
        root_turn, root, challenge_turn, challenge, _, sibling, attack, undercut, graph = self.fixture_graph()
        args = {x.meta.id: x for x in (root, challenge, sibling)}

        activation = decide_advocate_activation(
            graph=graph, arguments=args, challenge_relation=attack, composition_policy=self.policy,
        )
        self.assertTrue(activation.activate)
        self.assertNotIn("advocate", graph.branch_head_ids)

        disclosure = compile_advocate_disclosure(
            activation=activation, graph=graph, arguments=args,
            id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        self.assertEqual(set(disclosure.visible_argument_ids), {root.meta.id, challenge.meta.id})
        self.assertIn(sibling.meta.id, disclosure.hidden_argument_ids)
        self.assertNotIn(self.evd_hidden, disclosure.visible_evidence_refs)
        self.assertEqual(disclosure.visible_relation_ids, (attack.meta.id,))

        instruction = compile_role_instruction_pack(
            role_id="advocate", variant=RoleVariantKind.DEFENSE,
            handbook=self.handbook, policy=self.policy,
        )
        contract = compile_advocate_defense_contract(
            activation=activation, disclosure=disclosure, composition_policy=self.policy,
            instruction=instruction, id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        self.assertEqual(contract.challenge_turn_id, challenge_turn.meta.id)
        self.assertEqual(contract.defended_turn_id, root_turn.meta.id)

        request = AdditionalEvidenceRequest(
            "Obtain a stress-sensitive measurement before defending uniqueness.",
            "The disclosed support does not discriminate residual stress.",
            (self.need,), target_refs=(self.claim,), requested_evidence_kinds=("stress-sensitive XRD",),
        )
        response = materialize_advocate_draft(
            contract=contract, disclosure=disclosure,
            draft=AdvocateWorkerDraft(
                outcome=AdvocateOutcome.REQUEST_EVIDENCE,
                summary="The challenged interpretation cannot yet be defended uniquely.",
                justification="Visible support is compatible with the attack; discriminating evidence is required.",
                cited_evidence_refs=(self.evd_support,), cited_target_refs=(self.claim,),
                additional_evidence_requests=(request,),
            ),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        self.assertEqual(response.next_action, AdvocateNextAction.REQUEST_LOCAL_RESEARCH)
        self.assertEqual([x.kind for x in response.relations], [ArgumentRelationKind.REPLIES_TO])
        self.assertEqual(response.turn.parent_turn_id, challenge_turn.meta.id)
        self.assertEqual(response.argument.position, ArgumentPosition.OPEN)

        graph2 = append_argument_branch(
            graph=graph,
            new_meta=self.meta("AGP", "argument-graph-projection/1.0", entity_id=graph.meta.id, revision=2),
            arguments=(root, challenge, sibling, response.argument),
            new_relations=response.relations,
        )
        self.assertEqual(set(graph2.branch_head_ids), {sibling.meta.id, response.argument.meta.id})
        self.assertEqual(graph2.root_argument_ids, (root.meta.id,))

        observed = observe_dialectic_step(
            level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            argument=response.argument, turn=response.turn,
            history=DialecticHistory(),
            visible_refs=(*contract.allowed_evidence_refs, *contract.allowed_target_refs),
            chain_turn_count=1,
        )
        self.assertEqual(observed.decision.action, DialecticAction.REQUEST_LOCAL_RESEARCH)
        issue = next(x for x in observed.observation.new_issues if x.blocking)
        gap = gap_from_emergent_issue(issue=issue, target_claim_ids=(self.claim,), gap_id=self.ids.new("GAP"))
        research_challenge = challenge_from_gap(
            gap, self.rrq,
            EntityMeta(self.ids.new("RCH"), "research-challenge/1.0", 1, self.run, self.t, self.actor),
            dimensions={"origin": "AdvocateDefense", "argument_id": str(response.argument.meta.id)},
        )
        self.assertEqual(research_challenge.target_claim_ids, (self.claim,))
        self.assertEqual(research_challenge.dimensions["origin"], "AdvocateDefense")

    def test_defense_outcome_adds_defends_and_reply_edges(self):
        _, root, _, challenge, _, sibling, attack, _, graph = self.fixture_graph()
        args = {x.meta.id: x for x in (root, challenge, sibling)}
        activation = decide_advocate_activation(graph=graph, arguments=args, challenge_relation=attack, composition_policy=self.policy)
        disclosure = compile_advocate_disclosure(activation=activation, graph=graph, arguments=args, id_factory=self.ids, actor=self.actor, created_at=self.t)
        instruction = compile_role_instruction_pack(role_id="advocate", variant=RoleVariantKind.DEFENSE, handbook=self.handbook, policy=self.policy)
        contract = compile_advocate_defense_contract(activation=activation, disclosure=disclosure, composition_policy=self.policy, instruction=instruction, id_factory=self.ids, actor=self.actor, created_at=self.t)
        response = materialize_advocate_draft(
            contract=contract, disclosure=disclosure,
            draft=AdvocateWorkerDraft(
                outcome=AdvocateOutcome.DEFEND,
                summary="The limited claim remains defensible.",
                justification="The visible support survives the specific attack when the scope is narrowed.",
                cited_evidence_refs=(self.evd_support,), cited_target_refs=(self.claim,),
                grounding_items=(ResponseGroundingItem(ResponseGroundingKind.DISCLOSED_EVIDENCE, "Uses disclosed support.", (self.evd_support,)),),
            ),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        self.assertEqual(response.next_action, AdvocateNextAction.CONTINUE_CROSS_EXAM)
        self.assertEqual({x.kind for x in response.relations}, {ArgumentRelationKind.REPLIES_TO, ArgumentRelationKind.DEFENDS})

    def test_advocate_cannot_cite_hidden_sibling_evidence(self):
        _, root, _, challenge, _, sibling, attack, _, graph = self.fixture_graph()
        args = {x.meta.id: x for x in (root, challenge, sibling)}
        activation = decide_advocate_activation(graph=graph, arguments=args, challenge_relation=attack, composition_policy=self.policy)
        disclosure = compile_advocate_disclosure(activation=activation, graph=graph, arguments=args, id_factory=self.ids, actor=self.actor, created_at=self.t)
        instruction = compile_role_instruction_pack(role_id="advocate", variant=RoleVariantKind.DEFENSE, handbook=self.handbook, policy=self.policy)
        contract = compile_advocate_defense_contract(activation=activation, disclosure=disclosure, composition_policy=self.policy, instruction=instruction, id_factory=self.ids, actor=self.actor, created_at=self.t)
        with self.assertRaisesRegex(TribunalAdvocateError, "outside disclosure"):
            materialize_advocate_draft(
                contract=contract, disclosure=disclosure,
                draft=AdvocateWorkerDraft(
                    outcome=AdvocateOutcome.DEFEND, summary="bad", justification="bad hidden citation",
                    cited_evidence_refs=(self.evd_hidden,), cited_target_refs=(self.claim,),
                ),
                id_factory=self.ids, actor=self.actor, created_at=self.t,
            )

    def test_advocate_derivation_cannot_reference_hidden_sibling_evidence(self):
        _, root, _, challenge, _, sibling, attack, _, graph = self.fixture_graph()
        args = {x.meta.id: x for x in (root, challenge, sibling)}
        activation = decide_advocate_activation(graph=graph, arguments=args, challenge_relation=attack, composition_policy=self.policy)
        disclosure = compile_advocate_disclosure(activation=activation, graph=graph, arguments=args, id_factory=self.ids, actor=self.actor, created_at=self.t)
        instruction = compile_role_instruction_pack(role_id="advocate", variant=RoleVariantKind.DEFENSE, handbook=self.handbook, policy=self.policy)
        contract = compile_advocate_defense_contract(activation=activation, disclosure=disclosure, composition_policy=self.policy, instruction=instruction, id_factory=self.ids, actor=self.actor, created_at=self.t)
        with self.assertRaisesRegex(TribunalAdvocateError, "hidden material"):
            materialize_advocate_draft(
                contract=contract,
                disclosure=disclosure,
                draft=AdvocateWorkerDraft(
                    outcome=AdvocateOutcome.QUALIFY,
                    summary="hidden derivation",
                    justification="derived from a hidden sibling",
                    cited_evidence_refs=(self.evd_support,),
                    cited_target_refs=(self.claim,),
                    grounding_items=(ResponseGroundingItem(ResponseGroundingKind.DERIVATION_FROM_VISIBLE, "Hidden derivation.", (self.evd_hidden,)),),
                ),
                id_factory=self.ids,
                actor=self.actor,
                created_at=self.t,
            )

    def test_disclosure_fingerprint_tamper_fails_closed(self):
        _, root, _, challenge, _, sibling, attack, _, graph = self.fixture_graph()
        args = {x.meta.id: x for x in (root, challenge, sibling)}
        activation = decide_advocate_activation(graph=graph, arguments=args, challenge_relation=attack, composition_policy=self.policy)
        disclosure = compile_advocate_disclosure(activation=activation, graph=graph, arguments=args, id_factory=self.ids, actor=self.actor, created_at=self.t)
        with self.assertRaisesRegex(TribunalAdvocateError, "fingerprint"):
            validate_disclosure_contract_integrity(replace(disclosure, disclosure_fingerprint="sha256:" + "0" * 64))


    def test_nonmaterial_attack_does_not_activate_advocate(self):
        _, root, _, challenge, _, sibling, _, undercut, _ = self.fixture_graph()
        nonmaterial = self.relation(ArgumentRelationKind.ATTACKS, challenge, root, material=False)
        graph = build_argument_graph(
            meta=self.meta("AGP", "argument-graph-projection/1.0"),
            arguments=(root, challenge, sibling), relations=(nonmaterial, undercut),
        )
        args = {x.meta.id: x for x in (root, challenge, sibling)}
        decision = decide_advocate_activation(graph=graph, arguments=args, challenge_relation=nonmaterial, composition_policy=self.policy)
        self.assertFalse(decision.activate)
        self.assertEqual(decision.reason_codes, ("CHALLENGE_NOT_MATERIAL",))


if __name__ == "__main__":
    unittest.main()
