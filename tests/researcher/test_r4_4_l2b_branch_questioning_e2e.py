from __future__ import annotations

import random
import unittest
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.knowledge_reconciliation import challenge_from_gap
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_argument_graph import ArgumentRelation, ArgumentRelationKind, append_argument_branch, build_argument_graph
from researcher_core.tribunal_composition import AssessmentNeedRef, load_tribunal_composition_policy
from researcher_core.tribunal_dialectic import (
    DialecticAction,
    branch_resume_dimensions,
    compile_research_resume_anchor,
    dialectic_branch_history_to_dict,
    gap_from_emergent_issue,
    new_branch_history,
    observe_branch_dialectic_step,
    restore_dialectic_branch_history,
    validate_branch_resume_dimensions,
    validate_research_resume_anchor,
)
from researcher_core.tribunal_disclosure import (
    DisclosurePurpose,
    QuestionPurpose,
    compile_branch_ref,
    compile_dialectic_disclosure,
    compile_question_contract,
    materialize_question_turn,
    refresh_branch_ref,
    validate_answer_against_question_contract,
)
from researcher_core.tribunal_inquiry import (
    AdditionalEvidenceRequest,
    ArgumentArtifact,
    ArgumentPosition,
    DiscoveryKind,
    InquiryDiscovery,
    InquiryTurn,
    InquiryTurnKind,
)
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self):
        return 1789272000000


class R44L2BBranchQuestioningE2E(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.policy = load_tribunal_composition_policy(self.root / "config" / "tribunal_composition.yaml")
        self.handbook = load_role_handbook(self.root / "config" / "tribunal_role_handbook.yaml", self.policy)
        self.ids = EntityIdFactory(Clock(), random.Random(88117))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.rrq = self.ids.new("RRQ")
        self.base_contract = self.ids.new("IQC")
        self.need = AssessmentNeedRef("ANR-l2bbranch000001", 0)
        self.claim = self.ids.new("CLM")
        self.e_support = self.ids.new("EVD")
        self.e_attack = self.ids.new("EVD")
        self.e_sibling = self.ids.new("EVD")
        self.t = datetime(2026, 9, 13, 17, 30, tzinfo=timezone.utc)

    def meta(self, ns, schema, *, entity_id=None, revision=1):
        return EntityMeta(entity_id or self.ids.new(ns), schema, revision, self.run, self.t, self.actor)

    def base_arg(self, role, pos, text, evd, kind):
        turn = InquiryTurn(self.meta("IQT", "inquiry-turn/1.0"), self.base_contract, role, kind, text, None, (self.claim, evd))
        arg = ArgumentArtifact(self.meta("ARG", "argument-artifact/1.0"), self.base_contract, turn.meta.id, role, pos, (self.need,), text, text + " justification", (evd,), (self.claim,), (), ())
        return turn, arg

    def test_two_attack_branches_keep_history_and_q2_surface_isolated(self):
        root_turn, root = self.base_arg("xrd_specialist", ArgumentPosition.QUALIFY, "root interpretation", self.e_support, InquiryTurnKind.FIRST_PASS_ASSESSMENT)
        a_turn, attack_a = self.base_arg("skeptic", ArgumentPosition.CHALLENGE, "residual stress alternative", self.e_attack, InquiryTurnKind.CHALLENGE)
        b_turn, attack_b = self.base_arg("methodologist", ArgumentPosition.CHALLENGE, "calibration undercut", self.e_sibling, InquiryTurnKind.CHALLENGE)
        rel_a = ArgumentRelation(self.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.ATTACKS, attack_a.meta.id, root.meta.id, (self.need,), material=True)
        rel_b = ArgumentRelation(self.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.UNDERCUTS, attack_b.meta.id, root.meta.id, (self.need,), material=True)
        graph1 = build_argument_graph(meta=self.meta("AGP", "argument-graph-projection/1.0"), arguments=(root, attack_a, attack_b), relations=(rel_a, rel_b))
        args1 = {x.meta.id: x for x in (root, attack_a, attack_b)}

        branch_a = compile_branch_ref(graph=graph1, arguments=args1, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
        branch_b = compile_branch_ref(graph=graph1, arguments=args1, anchor_argument_id=attack_b.meta.id, anchor_relation_id=rel_b.meta.id)
        self.assertNotEqual(branch_a.branch_key, branch_b.branch_key)
        history_a = new_branch_history(branch_a)
        history_b = new_branch_history(branch_b)

        challenge_step = observe_branch_dialectic_step(
            branch=branch_a, argument=attack_a, turn=a_turn, branch_history=history_a,
            visible_refs=(self.claim, self.e_attack), chain_turn_count=1,
        )
        self.assertEqual(challenge_step.decision.action, DialecticAction.CONTINUE_QA)
        self.assertEqual(history_b.history.turn_ids, ())

        # Persist/restore the selected branch before continuing Q/A.  The
        # sibling history remains independent and empty.
        checkpoint = dialectic_branch_history_to_dict(challenge_step.next_branch_history)
        restored_a = restore_dialectic_branch_history(checkpoint)
        self.assertEqual(restored_a.branch.branch_key, branch_a.branch_key)
        self.assertEqual(restored_a.history.turn_ids, (a_turn.meta.id,))

        d1 = compile_dialectic_disclosure(
            role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION, branch=branch_a,
            graph=graph1, arguments=args1, assigned_need_refs=(self.need,), id_factory=self.ids,
            actor=self.actor, created_at=self.t, focus_argument_id=attack_a.meta.id, focus_relation_id=rel_a.meta.id,
        )
        self.assertIn(attack_b.meta.id, d1.hidden_argument_ids)
        skeptic_instruction = compile_role_instruction_pack(role_id="skeptic", variant=RoleVariantKind.CHALLENGER, handbook=self.handbook, policy=self.policy)
        q1c = compile_question_contract(
            purpose=QuestionPurpose.DIRECT_QUESTION, role_id="skeptic", answer_role_id="xrd_specialist", disclosure=d1,
            instruction=skeptic_instruction, parent_turn_id=a_turn.meta.id, id_factory=self.ids,
            actor=self.actor, created_at=self.t, policy_version=self.policy.version, policy_hash=self.policy.policy_hash,
            target_argument_id=attack_a.meta.id, expected_closure_surface=("ASSUMPTION_ISSUE", "MISSING_EVIDENCE"),
        )
        q1 = materialize_question_turn(contract=q1c, disclosure=d1, question="What measurement excludes residual stress?", id_factory=self.ids, actor=self.actor, created_at=self.t)

        a1_turn = InquiryTurn(self.meta("IQT", "inquiry-turn/1.0"), q1c.meta.id, "xrd_specialist", InquiryTurnKind.ANSWER, "No independent stress-sensitive measurement is present.", q1.meta.id, (self.claim, self.e_support))
        a1_disc = InquiryDiscovery(DiscoveryKind.ASSUMPTION_ISSUE, "The interpretation assumes residual stress is negligible.", (self.need,), target_refs=(self.claim,), evidence_refs=(self.e_support,), blocking=False)
        a1_arg = ArgumentArtifact(self.meta("ARG", "argument-artifact/1.0"), q1c.meta.id, a1_turn.meta.id, "xrd_specialist", ArgumentPosition.QUALIFY, (self.need,), "A1 reveals assumption", "Current data do not directly test residual stress.", (self.e_support,), (self.claim,), (a1_disc,), ())
        validate_answer_against_question_contract(contract=q1c, disclosure=d1, question_turn=q1, answer_turn=a1_turn, answer_argument=a1_arg)
        reply1 = ArgumentRelation(self.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.REPLIES_TO, a1_arg.meta.id, attack_a.meta.id, (self.need,), material=True)
        graph2 = append_argument_branch(graph=graph1, new_meta=self.meta("AGP", "argument-graph-projection/1.0", entity_id=graph1.meta.id, revision=2), arguments=(root, attack_a, attack_b, a1_arg), new_relations=(reply1,))
        args2 = {x.meta.id: x for x in (root, attack_a, attack_b, a1_arg)}
        branch_a2 = refresh_branch_ref(branch=branch_a, graph=graph2, arguments=args2, head_argument_id=a1_arg.meta.id)
        a1_step = observe_branch_dialectic_step(
            branch=branch_a2, argument=a1_arg, turn=a1_turn, branch_history=restored_a,
            visible_refs=(self.claim, self.e_support, self.e_attack), chain_turn_count=3,
        )
        self.assertEqual(a1_step.decision.action, DialecticAction.CONTINUE_QUESTION_ON_ANSWER)
        issue_sig = a1_step.observation.new_issues[0].signature
        self.assertEqual(history_b.history.no_progress_streak, 0)
        self.assertEqual(history_b.history.qa_pair_count, 0)

        d2 = compile_dialectic_disclosure(
            role_id="methodologist", purpose=DisclosurePurpose.QUESTION_ON_ANSWER, branch=branch_a2,
            graph=graph2, arguments=args2, assigned_need_refs=(self.need,), id_factory=self.ids,
            actor=self.actor, created_at=self.t, focus_argument_id=a1_arg.meta.id, focus_turn_id=a1_turn.meta.id,
            focus_issue_signature=issue_sig,
        )
        self.assertIn(attack_b.meta.id, d2.hidden_argument_ids)
        method_instruction = compile_role_instruction_pack(role_id="methodologist", variant=RoleVariantKind.CROSS_EXAM, handbook=self.handbook, policy=self.policy)
        q2c = compile_question_contract(
            purpose=QuestionPurpose.QUESTION_ON_ANSWER, role_id="methodologist", answer_role_id="xrd_specialist", disclosure=d2,
            instruction=method_instruction, parent_turn_id=a1_turn.meta.id, id_factory=self.ids, actor=self.actor,
            created_at=self.t, policy_version=self.policy.version, policy_hash=self.policy.policy_hash,
            target_argument_id=a1_arg.meta.id, target_turn_id=a1_turn.meta.id, target_issue_signature=issue_sig,
            admitted_new_issue_signatures=tuple(x.signature for x in a1_step.observation.new_issues),
            expected_closure_surface=("MISSING_EVIDENCE", "RESOLVED"), max_followups=0,
        )
        q2 = materialize_question_turn(contract=q2c, disclosure=d2, question="Which discriminating measurement closes that assumption?", id_factory=self.ids, actor=self.actor, created_at=self.t)

        req = AdditionalEvidenceRequest("Obtain stress-sensitive XRD or independent composition evidence.", "The Q2 target remains unresolved.", (self.need,), target_refs=(self.claim,), requested_evidence_kinds=("stress-sensitive XRD",))
        a2_turn = InquiryTurn(self.meta("IQT", "inquiry-turn/1.0"), q2c.meta.id, "xrd_specialist", InquiryTurnKind.REBUTTAL, "A discriminating measurement is required.", q2.meta.id, (self.claim, self.e_support))
        a2_arg = ArgumentArtifact(self.meta("ARG", "argument-artifact/1.0"), q2c.meta.id, a2_turn.meta.id, "xrd_specialist", ArgumentPosition.OPEN, (self.need,), "A2 reaches evidence boundary", "No disclosed measurement closes the issue.", (self.e_support,), (self.claim,), (), (req,))
        validate_answer_against_question_contract(contract=q2c, disclosure=d2, question_turn=q2, answer_turn=a2_turn, answer_argument=a2_arg)
        reply2 = ArgumentRelation(self.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.REPLIES_TO, a2_arg.meta.id, a1_arg.meta.id, (self.need,), material=True)
        graph3 = append_argument_branch(graph=graph2, new_meta=self.meta("AGP", "argument-graph-projection/1.0", entity_id=graph2.meta.id, revision=3), arguments=(root, attack_a, attack_b, a1_arg, a2_arg), new_relations=(reply2,))
        args3 = {x.meta.id: x for x in (root, attack_a, attack_b, a1_arg, a2_arg)}
        branch_a3 = refresh_branch_ref(branch=branch_a2, graph=graph3, arguments=args3, head_argument_id=a2_arg.meta.id)
        a2_step = observe_branch_dialectic_step(
            branch=branch_a3, argument=a2_arg, turn=a2_turn, branch_history=a1_step.next_branch_history,
            visible_refs=(self.claim, self.e_support, self.e_attack), chain_turn_count=5,
        )
        self.assertEqual(a2_step.decision.action, DialecticAction.REQUEST_LOCAL_RESEARCH)
        blocking = next(x for x in a2_step.observation.new_issues if x.blocking)
        gap = gap_from_emergent_issue(issue=blocking, target_claim_ids=(self.claim,), gap_id=self.ids.new("GAP"))
        dims = {"origin": "TribunalBranch", **branch_resume_dimensions(branch_a3, blocking.signature)}
        challenge = challenge_from_gap(gap, self.rrq, self.meta("RCH", "research-challenge/1.0"), dimensions=dims)
        validate_branch_resume_dimensions(dimensions=challenge.dimensions, branch=branch_a3, issue_signature=blocking.signature)
        resume_anchor = compile_research_resume_anchor(
            research_challenge_id=challenge.meta.id, source_gap_id=gap.id,
            branch_history=a2_step.next_branch_history, issue_signature=blocking.signature,
            challenge_dimensions=challenge.dimensions,
        )
        validate_research_resume_anchor(
            anchor=resume_anchor, research_challenge_id=challenge.meta.id, source_gap_id=gap.id,
            branch_history=a2_step.next_branch_history, issue_signature=blocking.signature,
        )

        # Sibling branch remains a pristine independent control history.
        self.assertEqual(history_b.history.argument_ids, ())
        self.assertEqual(history_b.history.turn_ids, ())
        self.assertEqual(history_b.history.issue_signatures, ())
        self.assertNotIn(attack_b.meta.id, d2.visible_argument_ids)
        self.assertIn(attack_b.meta.id, d2.hidden_argument_ids)

        # The sibling may start later on the newest graph revision without
        # inheriting branch-A counters or issues.
        branch_b3 = refresh_branch_ref(branch=branch_b, graph=graph3, arguments=args3, head_argument_id=attack_b.meta.id)
        sibling_step = observe_branch_dialectic_step(
            branch=branch_b3, argument=attack_b, turn=b_turn, branch_history=history_b,
            visible_refs=(self.claim, self.e_sibling), chain_turn_count=1,
        )
        self.assertEqual(sibling_step.next_branch_history.history.turn_ids, (b_turn.meta.id,))
        self.assertEqual(sibling_step.next_branch_history.history.qa_pair_count, 0)
        self.assertEqual(a2_step.next_branch_history.history.qa_pair_count, 2)
        self.assertNotEqual(sibling_step.next_branch_history.history_fingerprint, a2_step.next_branch_history.history_fingerprint)


if __name__ == "__main__":
    unittest.main()
