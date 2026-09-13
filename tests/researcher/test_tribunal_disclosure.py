from __future__ import annotations

import random
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_argument_graph import ArgumentRelation, ArgumentRelationKind, build_argument_graph
from researcher_core.tribunal_composition import AssessmentNeedRef, load_tribunal_composition_policy
from researcher_core.tribunal_disclosure import (
    DisclosurePurpose,
    QuestionPurpose,
    TribunalDisclosureError,
    compile_branch_ref,
    compile_dialectic_disclosure,
    compile_question_contract,
    disclosure_contract_from_dict,
    disclosure_contract_to_dict,
    materialize_question_turn,
    question_contract_from_dict,
    question_contract_to_dict,
    validate_disclosure_contract_integrity,
    validate_question_contract_integrity,
)
from researcher_core.tribunal_inquiry import ArgumentArtifact, ArgumentPosition, InquiryTurn, InquiryTurnKind
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self):
        return 1789272000000


class TribunalDisclosureTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.policy = load_tribunal_composition_policy(self.root / "config" / "tribunal_composition.yaml")
        self.handbook = load_role_handbook(self.root / "config" / "tribunal_role_handbook.yaml", self.policy)
        self.ids = EntityIdFactory(Clock(), random.Random(5221))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.contract = self.ids.new("IQC")
        self.need = AssessmentNeedRef("ANR-disclosure000001", 0)
        self.claim = self.ids.new("CLM")
        self.e1, self.e2, self.e3 = self.ids.new("EVD"), self.ids.new("EVD"), self.ids.new("EVD")
        self.t = datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)

    def meta(self, ns, schema, *, entity_id=None, revision=1):
        return EntityMeta(entity_id or self.ids.new(ns), schema, revision, self.run, self.t, self.actor)

    def arg(self, role, pos, text, evd, kind):
        turn = InquiryTurn(self.meta("IQT", "inquiry-turn/1.0"), self.contract, role, kind, text, None, (self.claim, evd))
        arg = ArgumentArtifact(
            self.meta("ARG", "argument-artifact/1.0"), self.contract, turn.meta.id, role, pos,
            (self.need,), text, text + " justification", (evd,), (self.claim,), (), (),
        )
        return turn, arg

    def fixture(self):
        root_turn, root = self.arg("xrd_specialist", ArgumentPosition.QUALIFY, "root", self.e1, InquiryTurnKind.FIRST_PASS_ASSESSMENT)
        a_turn, attack_a = self.arg("skeptic", ArgumentPosition.CHALLENGE, "attack a", self.e2, InquiryTurnKind.CHALLENGE)
        b_turn, attack_b = self.arg("methodologist", ArgumentPosition.CHALLENGE, "attack b", self.e3, InquiryTurnKind.CHALLENGE)
        rel_a = ArgumentRelation(self.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.ATTACKS, attack_a.meta.id, root.meta.id, (self.need,), material=True)
        rel_b = ArgumentRelation(self.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.UNDERCUTS, attack_b.meta.id, root.meta.id, (self.need,), material=True)
        graph = build_argument_graph(meta=self.meta("AGP", "argument-graph-projection/1.0"), arguments=(root, attack_a, attack_b), relations=(rel_a, rel_b))
        return (root_turn, root, a_turn, attack_a, b_turn, attack_b, rel_a, rel_b, graph)

    def test_generic_direct_question_disclosure_hides_sibling_branch(self):
        _, root, _, attack_a, _, attack_b, rel_a, _, graph = self.fixture()
        args = {x.meta.id: x for x in (root, attack_a, attack_b)}
        branch = compile_branch_ref(graph=graph, arguments=args, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
        disclosure = compile_dialectic_disclosure(
            role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION,
            branch=branch, graph=graph, arguments=args, assigned_need_refs=(self.need,),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
            focus_argument_id=attack_a.meta.id, focus_relation_id=rel_a.meta.id,
        )
        self.assertEqual(set(disclosure.visible_argument_ids), {root.meta.id, attack_a.meta.id})
        self.assertIn(attack_b.meta.id, disclosure.hidden_argument_ids)
        self.assertNotIn(self.e3, disclosure.visible_evidence_refs)
        validate_disclosure_contract_integrity(disclosure, graph=graph)

    def test_direct_question_contract_is_integrity_checked(self):
        _, root, a_turn, attack_a, _, attack_b, rel_a, _, graph = self.fixture()
        args = {x.meta.id: x for x in (root, attack_a, attack_b)}
        branch = compile_branch_ref(graph=graph, arguments=args, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
        disclosure = compile_dialectic_disclosure(
            role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION,
            branch=branch, graph=graph, arguments=args, assigned_need_refs=(self.need,),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
            focus_argument_id=attack_a.meta.id, focus_relation_id=rel_a.meta.id,
        )
        instruction = compile_role_instruction_pack(role_id="skeptic", variant=RoleVariantKind.CHALLENGER, handbook=self.handbook, policy=self.policy)
        contract = compile_question_contract(
            purpose=QuestionPurpose.DIRECT_QUESTION, role_id="skeptic", answer_role_id="xrd_specialist", disclosure=disclosure,
            instruction=instruction, parent_turn_id=a_turn.meta.id, id_factory=self.ids,
            actor=self.actor, created_at=self.t, policy_version=self.policy.version, policy_hash=self.policy.policy_hash,
            target_argument_id=attack_a.meta.id, expected_closure_surface=("ASSUMPTION_ISSUE",),
        )
        q = materialize_question_turn(contract=contract, disclosure=disclosure, question="Which observation excludes the alternative?", id_factory=self.ids, actor=self.actor, created_at=self.t)
        self.assertEqual(q.kind, InquiryTurnKind.QUESTION)
        self.assertEqual(q.parent_turn_id, a_turn.meta.id)
        validate_question_contract_integrity(contract, disclosure)
        restored_disclosure = disclosure_contract_from_dict(disclosure_contract_to_dict(disclosure))
        restored_contract = question_contract_from_dict(question_contract_to_dict(contract))
        validate_question_contract_integrity(restored_contract, restored_disclosure)
        self.assertEqual(restored_contract, contract)
        self.assertEqual(restored_disclosure, disclosure)
        with self.assertRaisesRegex(TribunalDisclosureError, "fingerprint"):
            validate_question_contract_integrity(replace(contract, contract_fingerprint="sha256:" + "0" * 64), disclosure)

    def test_q2_requires_newly_admitted_issue_surface(self):
        _, root, a_turn, attack_a, _, attack_b, rel_a, _, graph = self.fixture()
        args = {x.meta.id: x for x in (root, attack_a, attack_b)}
        branch = compile_branch_ref(graph=graph, arguments=args, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
        disclosure = compile_dialectic_disclosure(
            role_id="methodologist", purpose=DisclosurePurpose.QUESTION_ON_ANSWER,
            branch=branch, graph=graph, arguments=args, assigned_need_refs=(self.need,),
            id_factory=self.ids, actor=self.actor, created_at=self.t,
            focus_argument_id=attack_a.meta.id, focus_turn_id=a_turn.meta.id,
            focus_issue_signature="ISSUE-new",
        )
        instruction = compile_role_instruction_pack(role_id="methodologist", variant=RoleVariantKind.CROSS_EXAM, handbook=self.handbook, policy=self.policy)
        with self.assertRaisesRegex(TribunalDisclosureError, "newly admitted"):
            compile_question_contract(
                purpose=QuestionPurpose.QUESTION_ON_ANSWER, role_id="methodologist", answer_role_id="xrd_specialist", disclosure=disclosure,
                instruction=instruction, parent_turn_id=a_turn.meta.id, id_factory=self.ids, actor=self.actor,
                created_at=self.t, policy_version=self.policy.version, policy_hash=self.policy.policy_hash,
                target_argument_id=attack_a.meta.id, target_turn_id=a_turn.meta.id,
                target_issue_signature="ISSUE-old", admitted_new_issue_signatures=("ISSUE-new",),
            )

    def test_generic_challenge_disclosure_exposes_only_target_argument(self):
        root_turn, root, _, attack_a, _, attack_b, rel_a, _, graph = self.fixture()
        args = {x.meta.id: x for x in (root, attack_a, attack_b)}
        branch = compile_branch_ref(graph=graph, arguments=args, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
        disclosure = compile_dialectic_disclosure(
            role_id="skeptic", purpose=DisclosurePurpose.CHALLENGE, branch=branch,
            graph=graph, arguments=args, assigned_need_refs=(self.need,), id_factory=self.ids,
            actor=self.actor, created_at=self.t, focus_argument_id=root.meta.id,
        )
        self.assertEqual(disclosure.visible_argument_ids, (root.meta.id,))
        self.assertEqual(disclosure.visible_turn_ids, (root_turn.meta.id,))
        self.assertIn(attack_a.meta.id, disclosure.hidden_argument_ids)
        self.assertIn(attack_b.meta.id, disclosure.hidden_argument_ids)

    def test_answer_turn_cannot_smuggle_hidden_sibling_ref(self):
        _, root, a_turn, attack_a, _, attack_b, rel_a, _, graph = self.fixture()
        args = {x.meta.id: x for x in (root, attack_a, attack_b)}
        branch = compile_branch_ref(graph=graph, arguments=args, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
        disclosure = compile_dialectic_disclosure(
            role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION, branch=branch, graph=graph, arguments=args,
            assigned_need_refs=(self.need,), id_factory=self.ids, actor=self.actor, created_at=self.t,
            focus_argument_id=attack_a.meta.id, focus_relation_id=rel_a.meta.id,
        )
        instruction = compile_role_instruction_pack(role_id="skeptic", variant=RoleVariantKind.CHALLENGER, handbook=self.handbook, policy=self.policy)
        contract = compile_question_contract(
            purpose=QuestionPurpose.DIRECT_QUESTION, role_id="skeptic", answer_role_id="xrd_specialist", disclosure=disclosure, instruction=instruction,
            parent_turn_id=a_turn.meta.id, id_factory=self.ids, actor=self.actor, created_at=self.t,
            policy_version=self.policy.version, policy_hash=self.policy.policy_hash, target_argument_id=attack_a.meta.id,
        )
        question = materialize_question_turn(contract=contract, disclosure=disclosure, question="Test the branch", id_factory=self.ids, actor=self.actor, created_at=self.t)
        answer_turn = InquiryTurn(self.meta("IQT", "inquiry-turn/1.0"), contract.meta.id, "xrd_specialist", InquiryTurnKind.ANSWER, "answer", question.meta.id, (attack_b.meta.id,))
        answer_arg = ArgumentArtifact(self.meta("ARG", "argument-artifact/1.0"), contract.meta.id, answer_turn.meta.id, "xrd_specialist", ArgumentPosition.OPEN, (self.need,), "answer", "justification", (), (self.claim,), (), ())
        from researcher_core.tribunal_disclosure import validate_answer_against_question_contract
        with self.assertRaisesRegex(TribunalDisclosureError, "outside question disclosure"):
            validate_answer_against_question_contract(contract=contract, disclosure=disclosure, question_turn=question, answer_turn=answer_turn, answer_argument=answer_arg)

    def test_questioner_cannot_be_its_own_answer_role(self):
        _, root, a_turn, attack_a, _, attack_b, rel_a, _, graph = self.fixture()
        args = {x.meta.id: x for x in (root, attack_a, attack_b)}
        branch = compile_branch_ref(graph=graph, arguments=args, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
        disclosure = compile_dialectic_disclosure(
            role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION, branch=branch, graph=graph, arguments=args,
            assigned_need_refs=(self.need,), id_factory=self.ids, actor=self.actor, created_at=self.t,
            focus_argument_id=attack_a.meta.id, focus_relation_id=rel_a.meta.id,
        )
        instruction = compile_role_instruction_pack(role_id="skeptic", variant=RoleVariantKind.CHALLENGER, handbook=self.handbook, policy=self.policy)
        with self.assertRaisesRegex(TribunalDisclosureError, "distinct"):
            compile_question_contract(
                purpose=QuestionPurpose.DIRECT_QUESTION, role_id="skeptic", answer_role_id="skeptic", disclosure=disclosure,
                instruction=instruction, parent_turn_id=a_turn.meta.id, id_factory=self.ids, actor=self.actor, created_at=self.t,
                policy_version=self.policy.version, policy_hash=self.policy.policy_hash, target_argument_id=attack_a.meta.id,
            )

    def test_legacy_dqc_1_0_cannot_guess_answer_role_on_restore(self):
        _, root, a_turn, attack_a, _, attack_b, rel_a, _, graph = self.fixture()
        args = {x.meta.id: x for x in (root, attack_a, attack_b)}
        branch = compile_branch_ref(graph=graph, arguments=args, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
        disclosure = compile_dialectic_disclosure(
            role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION, branch=branch, graph=graph, arguments=args,
            assigned_need_refs=(self.need,), id_factory=self.ids, actor=self.actor, created_at=self.t,
            focus_argument_id=attack_a.meta.id, focus_relation_id=rel_a.meta.id,
        )
        instruction = compile_role_instruction_pack(role_id="skeptic", variant=RoleVariantKind.CHALLENGER, handbook=self.handbook, policy=self.policy)
        contract = compile_question_contract(
            purpose=QuestionPurpose.DIRECT_QUESTION, role_id="skeptic", answer_role_id="xrd_specialist", disclosure=disclosure,
            instruction=instruction, parent_turn_id=a_turn.meta.id, id_factory=self.ids, actor=self.actor, created_at=self.t,
            policy_version=self.policy.version, policy_hash=self.policy.policy_hash, target_argument_id=attack_a.meta.id,
        )
        legacy = question_contract_to_dict(contract)
        legacy["schema_version"] = "dialectic-question-contract/1.0"
        legacy.pop("answer_role_id", None)
        with self.assertRaisesRegex(TribunalDisclosureError, "lacks explicit answer_role_id"):
            question_contract_from_dict(legacy)


if __name__ == "__main__":
    unittest.main()
