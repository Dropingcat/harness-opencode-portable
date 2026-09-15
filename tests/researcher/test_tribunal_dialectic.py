from __future__ import annotations

import random
import unittest
from datetime import datetime, timezone

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_composition import AssessmentNeedRef
from researcher_core.tribunal_dialectic import (
    DialecticAction,
    DialecticHistory,
    DialecticIssueDisposition,
    DialecticIssueProposal,
    DialecticIssueResolutionProposal,
    DialecticLevel,
    DialecticPolicy,
    EmergentIssueKind,
    TribunalDialecticError,
    gap_from_emergent_issue,
    observe_dialectic_step,
    validate_dialectic_turn_chain,
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


class Clock:
    def now_ms(self):
        return 1789272000000


class TribunalDialecticTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(991))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.contract = self.ids.new("IQC")
        self.need = AssessmentNeedRef("ANR-0123456789abcdef", 0)
        self.t = datetime(2026, 9, 13, 14, 0, tzinfo=timezone.utc)

    def meta(self, ns, schema):
        return EntityMeta(self.ids.new(ns), schema, 1, self.run, self.t, self.actor)

    def pair(self, *, kind=InquiryTurnKind.FIRST_PASS_ASSESSMENT, position=ArgumentPosition.QUALIFY,
             discoveries=(), requests=(), content="assessment", parent=None):
        turn = InquiryTurn(
            meta=self.meta("IQT", "inquiry-turn/1.0"),
            contract_id=self.contract,
            role_id="xrd_specialist",
            kind=kind,
            content=content,
            parent_turn_id=parent,
            cited_refs=(),
        )
        arg = ArgumentArtifact(
            meta=self.meta("ARG", "argument-artifact/1.0"),
            contract_id=self.contract,
            source_turn_id=turn.meta.id,
            role_id="xrd_specialist",
            position=position,
            assigned_need_refs=(self.need,),
            summary=content,
            justification="bounded typed justification",
            cited_evidence_refs=(),
            cited_target_refs=(),
            discoveries=tuple(discoveries),
            additional_evidence_requests=tuple(requests),
        )
        return turn, arg

    def test_first_pass_new_nonblocking_issue_advances_to_challenge(self):
        discovery = InquiryDiscovery(
            DiscoveryKind.POSSIBLE_COUNTEREXAMPLE,
            "A structural alternative remains compatible with the observed peak shift.",
            (self.need,),
            blocking=False,
        )
        turn, arg = self.pair(discoveries=(discovery,))
        result = observe_dialectic_step(
            level=DialecticLevel.L0_INDEPENDENT,
            argument=arg,
            turn=turn,
            history=DialecticHistory(),
        )
        self.assertEqual(result.decision.action, DialecticAction.CONTINUE_CHALLENGE)
        self.assertEqual(result.decision.next_level, DialecticLevel.L1_CHALLENGE)
        self.assertEqual(len(result.observation.new_issues), 1)

    def test_blocking_evidence_request_escalates_to_local_research(self):
        request = AdditionalEvidenceRequest(
            "Obtain stress-sensitive XRD evidence.",
            "Current slice cannot separate stress from composition.",
            (self.need,),
            requested_evidence_kinds=("stress-sensitive XRD",),
        )
        turn, arg = self.pair(requests=(request,), position=ArgumentPosition.OPEN)
        result = observe_dialectic_step(
            level=DialecticLevel.L1_CHALLENGE,
            argument=arg,
            turn=turn,
            history=DialecticHistory(),
        )
        self.assertEqual(result.decision.action, DialecticAction.REQUEST_LOCAL_RESEARCH)
        self.assertEqual(result.decision.next_level, DialecticLevel.L4_LOCAL_RESEARCH_ESCALATION)
        self.assertTrue(result.observation.new_issues[0].blocking)

    def test_repeated_issue_without_new_refs_hits_no_progress_boundary(self):
        discovery = InquiryDiscovery(
            DiscoveryKind.METHOD_LIMITATION,
            "Stress and composition remain confounded.",
            (self.need,),
            blocking=False,
        )
        t1, a1 = self.pair(discoveries=(discovery,))
        first = observe_dialectic_step(
            level=DialecticLevel.L0_INDEPENDENT,
            argument=a1,
            turn=t1,
            history=DialecticHistory(),
            policy=DialecticPolicy(max_no_progress_streak=0),
        )
        t2, a2 = self.pair(kind=InquiryTurnKind.ANSWER, discoveries=(discovery,), content="same issue again")
        second = observe_dialectic_step(
            level=DialecticLevel.L2_DIRECT_QA,
            argument=a2,
            turn=t2,
            history=first.next_history,
            policy=DialecticPolicy(max_no_progress_streak=0),
        )
        self.assertEqual(second.decision.action, DialecticAction.STOP_NO_PROGRESS)
        self.assertIn("NO_SEMANTIC_PROGRESS", second.observation.reason_codes)

    def test_direct_answer_with_novel_issue_advances_to_question_on_answer(self):
        discovery = InquiryDiscovery(
            DiscoveryKind.ASSUMPTION_ISSUE,
            "The answer introduces an untested assumption of negligible residual stress.",
            (self.need,),
            blocking=False,
        )
        turn, arg = self.pair(kind=InquiryTurnKind.ANSWER, discoveries=(discovery,), content="answer adds assumption")
        result = observe_dialectic_step(
            level=DialecticLevel.L2_DIRECT_QA,
            argument=arg,
            turn=turn,
            history=DialecticHistory(),
        )
        self.assertEqual(result.decision.action, DialecticAction.CONTINUE_QUESTION_ON_ANSWER)
        self.assertEqual(result.decision.next_level, DialecticLevel.L3_QUESTION_ON_ANSWER)

    def test_depth_boundary_stops_cross_exam_growth(self):
        discovery = InquiryDiscovery(
            DiscoveryKind.SCOPE_ISSUE,
            "The reply broadens the claim beyond the measured condition.",
            (self.need,),
            blocking=False,
        )
        turn, arg = self.pair(kind=InquiryTurnKind.REBUTTAL, discoveries=(discovery,), content="cross-exam reply")
        result = observe_dialectic_step(
            level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            argument=arg,
            turn=turn,
            history=DialecticHistory(),
            policy=DialecticPolicy(max_level=DialecticLevel.L3_QUESTION_ON_ANSWER),
        )
        self.assertEqual(result.decision.action, DialecticAction.STOP_DEPTH_LIMIT)


    def test_q3_followup_is_denied_by_default_after_bounded_cross_exam(self):
        # Default policy: L3/2 Q/A pairs, no bounded follow-up. After A2 on L3
        # with a fresh non-blocking issue, the observer must NOT admit Q3 and
        # stops at the configured depth (canonical L3 behaviour).
        discovery = InquiryDiscovery(
            DiscoveryKind.SCOPE_ISSUE,
            "A distinct calibration assumption remains untested.",
            (self.need,),
            blocking=False,
        )
        turn, arg = self.pair(kind=InquiryTurnKind.REBUTTAL, discoveries=(discovery,), content="A2 reply")
        history = DialecticHistory(qa_pair_count=2, issue_signatures=("old-sig",))
        result = observe_dialectic_step(
            level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            argument=arg,
            turn=turn,
            history=history,
        )
        self.assertEqual(result.decision.action, DialecticAction.STOP_DEPTH_LIMIT)


    def test_q3_followup_is_admitted_when_policy_permits_and_issue_is_new(self):
        # Opt-in bounded follow-up: a NEW non-blocking issue on A2 admits Q3,
        # but only when Core raised max_question_answer_pairs to 3.
        discovery = InquiryDiscovery(
            DiscoveryKind.SCOPE_ISSUE,
            "A distinct calibration assumption remains untested.",
            (self.need,),
            blocking=False,
        )
        turn, arg = self.pair(kind=InquiryTurnKind.REBUTTAL, discoveries=(discovery,), content="A2 reply")
        history = DialecticHistory(qa_pair_count=2, issue_signatures=("old-sig",))
        policy = DialecticPolicy(
            max_level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            max_question_answer_pairs=3,
            allow_bounded_followup=True,
        )
        result = observe_dialectic_step(
            level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            argument=arg,
            turn=turn,
            history=history,
            policy=policy,
        )
        self.assertEqual(result.decision.action, DialecticAction.CONTINUE_QUESTION_ON_ANSWER)
        self.assertEqual(result.decision.reason_codes, ("BOUNDED_FOLLOWUP_QA_EXTENSION",))
        self.assertEqual(result.decision.next_level, DialecticLevel.L3_QUESTION_ON_ANSWER)


    def test_q3_followup_denied_for_repeated_issue(self):
        # Novelty is enforced before the L3 branch: a repeated issue must not
        # unlock Q3 even when the policy flag is on.
        repeated = InquiryDiscovery(
            DiscoveryKind.SCOPE_ISSUE,
            "Calibration assumption remains untested.",
            (self.need,),
            blocking=False,
        )
        turn, arg = self.pair(kind=InquiryTurnKind.REBUTTAL, discoveries=(repeated,), content="A2 reply")
        # Compute the repeated issue signature by observing once against an empty
        # history, then replay with that signature already active.
        probe = observe_dialectic_step(
            level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            argument=arg,
            turn=turn,
            history=DialecticHistory(qa_pair_count=2),
        )
        sig = probe.observation.new_issues[0].signature
        policy = DialecticPolicy(
            max_level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            max_question_answer_pairs=3,
            allow_bounded_followup=True,
        )
        result = observe_dialectic_step(
            level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            argument=arg,
            turn=turn,
            history=DialecticHistory(qa_pair_count=2, issue_signatures=(sig,)),
            policy=policy,
        )
        self.assertEqual(result.decision.action, DialecticAction.STOP_NO_PROGRESS)


    def test_typed_turn_observer_can_propose_answer_evasion_without_parsing_prose_in_control_code(self):
        turn, arg = self.pair(kind=InquiryTurnKind.ANSWER, content="bounded answer")
        proposal = DialecticIssueProposal(
            EmergentIssueKind.ANSWER_EVASION,
            "The answer does not address the discriminating measurement requested by the question.",
            (self.need,),
            blocking=False,
        )
        result = observe_dialectic_step(
            level=DialecticLevel.L2_DIRECT_QA,
            argument=arg,
            turn=turn,
            history=DialecticHistory(),
            issue_proposals=(proposal,),
        )
        self.assertEqual(result.observation.new_issues[0].kind, EmergentIssueKind.ANSWER_EVASION)
        self.assertEqual(result.decision.action, DialecticAction.CONTINUE_QUESTION_ON_ANSWER)



    def test_answer_can_close_prior_dialectic_issue_without_mutating_claim_truth(self):
        discovery = InquiryDiscovery(
            DiscoveryKind.METHOD_LIMITATION,
            "Stress and composition are initially confounded.",
            (self.need,),
            blocking=False,
        )
        t1, a1 = self.pair(discoveries=(discovery,))
        first = observe_dialectic_step(
            level=DialecticLevel.L0_INDEPENDENT,
            argument=a1, turn=t1, history=DialecticHistory(),
        )
        sig = first.observation.new_issues[0].signature
        t2, a2 = self.pair(kind=InquiryTurnKind.ANSWER, position=ArgumentPosition.QUALIFY, content="control measurement supplied")
        second = observe_dialectic_step(
            level=DialecticLevel.L2_DIRECT_QA,
            argument=a2, turn=t2, history=first.next_history,
            issue_resolutions=(DialecticIssueResolutionProposal(
                sig, DialecticIssueDisposition.RESOLVED,
                "A newly disclosed control measurement addresses this specific method ambiguity.",
            ),),
        )
        self.assertEqual(second.decision.action, DialecticAction.STOP_CONVERGED)
        self.assertEqual(second.observation.resolved_issue_signatures, (sig,))
        self.assertEqual(second.observation.all_active_issue_signatures, ())

    def test_issue_resolution_cannot_close_unknown_problem(self):
        turn, arg = self.pair(kind=InquiryTurnKind.ANSWER, content="answer")
        with self.assertRaises(TribunalDialecticError):
            observe_dialectic_step(
                level=DialecticLevel.L2_DIRECT_QA, argument=arg, turn=turn, history=DialecticHistory(),
                issue_resolutions=(DialecticIssueResolutionProposal(
                    "sha256:" + "0" * 64, DialecticIssueDisposition.RESOLVED, "not in history"
                ),),
            )


    def test_resolved_issue_reappearing_later_is_marked_reopened(self):
        discovery = InquiryDiscovery(
            DiscoveryKind.METHOD_LIMITATION,
            "Stress and composition are confounded.",
            (self.need,), blocking=False,
        )
        t1, a1 = self.pair(discoveries=(discovery,))
        first = observe_dialectic_step(level=DialecticLevel.L0_INDEPENDENT, argument=a1, turn=t1, history=DialecticHistory())
        sig = first.observation.new_issues[0].signature
        t2, a2 = self.pair(kind=InquiryTurnKind.ANSWER, content="temporary closure")
        closed = observe_dialectic_step(
            level=DialecticLevel.L2_DIRECT_QA, argument=a2, turn=t2, history=first.next_history,
            issue_resolutions=(DialecticIssueResolutionProposal(sig, DialecticIssueDisposition.RESOLVED, "control supplied"),),
        )
        self.assertIn(sig, closed.next_history.resolved_issue_signatures)
        t3, a3 = self.pair(kind=InquiryTurnKind.ANSWER, discoveries=(discovery,), content="later evidence reopens ambiguity")
        reopened = observe_dialectic_step(
            level=DialecticLevel.L2_DIRECT_QA, argument=a3, turn=t3, history=closed.next_history,
        )
        self.assertEqual(reopened.observation.reopened_issues[0].signature, sig)
        self.assertIn("ISSUE_REOPENED", reopened.observation.reason_codes)
        self.assertIn(sig, reopened.next_history.issue_signatures)
        self.assertNotIn(sig, reopened.next_history.resolved_issue_signatures)

    def test_issue_fanout_is_observed_without_silent_truncation_and_stops_open(self):
        turn, arg = self.pair(kind=InquiryTurnKind.ANSWER, content="many independent concerns")
        proposals = tuple(
            DialecticIssueProposal(
                EmergentIssueKind.ASSUMPTION_ISSUE,
                f"Independent assumption concern {i}",
                (self.need,),
            )
            for i in range(7)
        )
        result = observe_dialectic_step(
            level=DialecticLevel.L2_DIRECT_QA, argument=arg, turn=turn, history=DialecticHistory(),
            issue_proposals=proposals, policy=DialecticPolicy(max_new_issues_per_turn=6),
        )
        self.assertEqual(len(result.observation.new_issues), 7)
        self.assertIn("ISSUE_FANOUT_LIMIT_EXCEEDED", result.observation.reason_codes)
        self.assertEqual(result.decision.action, DialecticAction.STOP_OPEN)

    def test_response_cannot_resolve_and_reassert_same_issue(self):
        discovery = InquiryDiscovery(DiscoveryKind.METHOD_LIMITATION, "Same issue", (self.need,), blocking=False)
        t1, a1 = self.pair(discoveries=(discovery,))
        first = observe_dialectic_step(level=DialecticLevel.L0_INDEPENDENT, argument=a1, turn=t1, history=DialecticHistory())
        sig = first.observation.new_issues[0].signature
        t2, a2 = self.pair(kind=InquiryTurnKind.ANSWER, discoveries=(discovery,), content="contradictory lifecycle")
        with self.assertRaises(TribunalDialecticError):
            observe_dialectic_step(
                level=DialecticLevel.L2_DIRECT_QA, argument=a2, turn=t2, history=first.next_history,
                issue_resolutions=(DialecticIssueResolutionProposal(sig, DialecticIssueDisposition.RESOLVED, "claims resolved"),),
            )

    def test_issue_proposal_cannot_reference_hidden_material(self):
        turn, arg = self.pair(kind=InquiryTurnKind.ANSWER, content="bounded answer")
        proposal = DialecticIssueProposal(
            EmergentIssueKind.CONTRADICTION,
            "Hidden evidence would contradict the answer.",
            (self.need,),
            evidence_refs=(self.ids.new("EVD"),),
        )
        with self.assertRaises(TribunalDialecticError):
            observe_dialectic_step(
                level=DialecticLevel.L2_DIRECT_QA,
                argument=arg,
                turn=turn,
                history=DialecticHistory(),
                issue_proposals=(proposal,),
            )

    def test_turn_chain_rejects_skipping_answer_parentage(self):
        first, _ = self.pair(content="first")
        q = InquiryTurn(
            meta=self.meta("IQT", "inquiry-turn/1.0"),
            contract_id=self.contract, role_id="skeptic", kind=InquiryTurnKind.QUESTION,
            content="question", parent_turn_id=first.meta.id, cited_refs=(),
        )
        q2 = InquiryTurn(
            meta=self.meta("IQT", "inquiry-turn/1.0"),
            contract_id=self.contract, role_id="skeptic", kind=InquiryTurnKind.QUESTION_ON_ANSWER,
            content="premature follow-up", parent_turn_id=q.meta.id, cited_refs=(),
        )
        with self.assertRaises(TribunalDialecticError):
            validate_dialectic_turn_chain((first, q, q2))

    def test_actionable_issue_projects_to_existing_gap_contract_only_on_explicit_call(self):
        request = AdditionalEvidenceRequest(
            "Obtain independent phase evidence.",
            "The visible evidence cannot close the method ambiguity.",
            (self.need,),
        )
        turn, arg = self.pair(requests=(request,), position=ArgumentPosition.OPEN)
        observed = observe_dialectic_step(
            level=DialecticLevel.L1_CHALLENGE,
            argument=arg,
            turn=turn,
            history=DialecticHistory(),
        )
        claim_id = self.ids.new("CLM")
        gap = gap_from_emergent_issue(
            issue=observed.observation.new_issues[0],
            target_claim_ids=(claim_id,),
            gap_id=self.ids.new("GAP"),
        )
        self.assertEqual(gap.target_claim_ids, (claim_id,))
        self.assertEqual(gap.severity, "blocking")
        self.assertTrue(gap.gap_type.startswith("TRIBUNAL_"))


if __name__ == "__main__":
    unittest.main()
