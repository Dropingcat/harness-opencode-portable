from __future__ import annotations

import random
import unittest
from datetime import datetime, timezone

from researcher_core.knowledge_reconciliation import challenge_from_gap
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_composition import AssessmentNeedRef
from researcher_core.tribunal_dialectic import (
    DialecticAction,
    DialecticHistory,
    DialecticLevel,
    DialecticPolicy,
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


class R44DialecticObserverE2E(unittest.TestCase):
    def test_first_pass_through_q_a_q_on_a_to_local_research_challenge(self):
        ids = EntityIdFactory(Clock(), random.Random(4401))
        actor = ActorRef("AGENT", "researcher")
        run = ids.new("RUN")
        req = ids.new("RRQ")
        contract = ids.new("IQC")
        claim = ids.new("CLM")
        evidence = ids.new("EVD")
        need = AssessmentNeedRef("ANR-fedcba9876543210", 0)
        t = datetime(2026, 9, 13, 15, 0, tzinfo=timezone.utc)

        def meta(ns, schema):
            return EntityMeta(ids.new(ns), schema, 1, run, t, actor)

        def argument(turn, *, role, position, discoveries=(), requests=(), text):
            return ArgumentArtifact(
                meta=meta("ARG", "argument-artifact/1.0"),
                contract_id=contract,
                source_turn_id=turn.meta.id,
                role_id=role,
                position=position,
                assigned_need_refs=(need,),
                summary=text,
                justification=text + " / justification",
                cited_evidence_refs=(evidence,),
                cited_target_refs=(claim,),
                discoveries=tuple(discoveries),
                additional_evidence_requests=tuple(requests),
            )

        # L0: independent specialist exposes a methodological ambiguity.
        first_turn = InquiryTurn(
            meta("IQT", "inquiry-turn/1.0"), contract, "xrd_specialist",
            InquiryTurnKind.FIRST_PASS_ASSESSMENT,
            "Stress/composition ambiguity remains.", None, (evidence, claim),
        )
        first_arg = argument(
            first_turn,
            role="xrd_specialist",
            position=ArgumentPosition.QUALIFY,
            discoveries=(InquiryDiscovery(
                DiscoveryKind.METHOD_LIMITATION,
                "Peak shift alone does not separate stress from composition.",
                (need,), target_refs=(claim,), evidence_refs=(evidence,), blocking=False,
            ),),
            text="Method ambiguity remains",
        )
        s0 = observe_dialectic_step(
            level=DialecticLevel.L0_INDEPENDENT,
            argument=first_arg,
            turn=first_turn,
            history=DialecticHistory(),
            visible_refs=(evidence, claim),
            chain_turn_count=1,
        )
        self.assertEqual(s0.decision.action, DialecticAction.CONTINUE_CHALLENGE)

        # L1: a challenger adds an alternative interpretation before direct Q/A.
        challenge_turn = InquiryTurn(
            meta("IQT", "inquiry-turn/1.0"), contract, "skeptic", InquiryTurnKind.CHALLENGE,
            "Residual stress remains a competing explanation.", first_turn.meta.id, (claim,),
        )
        challenge_arg = argument(
            challenge_turn,
            role="skeptic",
            position=ArgumentPosition.CHALLENGE,
            discoveries=(InquiryDiscovery(
                DiscoveryKind.POSSIBLE_COUNTEREXAMPLE,
                "Residual stress remains compatible with the observed shift.",
                (need,), target_refs=(claim,), evidence_refs=(evidence,), blocking=False,
            ),),
            text="Challenger identifies a competing explanation",
        )
        s_challenge = observe_dialectic_step(
            level=DialecticLevel.L1_CHALLENGE,
            argument=challenge_arg,
            turn=challenge_turn,
            history=s0.next_history,
            visible_refs=(evidence, claim),
            chain_turn_count=2,
        )
        self.assertEqual(s_challenge.decision.action, DialecticAction.CONTINUE_QA)

        q1 = InquiryTurn(
            meta("IQT", "inquiry-turn/1.0"), contract, "skeptic", InquiryTurnKind.QUESTION,
            "What observation excludes residual stress?", challenge_turn.meta.id, (claim,),
        )
        a1_turn = InquiryTurn(
            meta("IQT", "inquiry-turn/1.0"), contract, "xrd_specialist", InquiryTurnKind.ANSWER,
            "The current experiment has no independent stress-sensitive measurement.", q1.meta.id, (evidence,),
        )
        a1_arg = argument(
            a1_turn,
            role="xrd_specialist",
            position=ArgumentPosition.QUALIFY,
            discoveries=(InquiryDiscovery(
                DiscoveryKind.ASSUMPTION_ISSUE,
                "The interpretation assumes residual stress is negligible without direct measurement.",
                (need,), target_refs=(claim,), evidence_refs=(evidence,), blocking=False,
            ),),
            text="Answer reveals an untested assumption",
        )
        s1 = observe_dialectic_step(
            level=DialecticLevel.L2_DIRECT_QA,
            argument=a1_arg,
            turn=a1_turn,
            history=s_challenge.next_history,
            visible_refs=(evidence, claim),
            chain_turn_count=4,
        )
        self.assertEqual(s1.decision.action, DialecticAction.CONTINUE_QUESTION_ON_ANSWER)

        # L3: Q-on-answer forces the unresolved assumption into a concrete evidence request.
        q2 = InquiryTurn(
            meta("IQT", "inquiry-turn/1.0"), contract, "methodologist", InquiryTurnKind.QUESTION_ON_ANSWER,
            "Which discriminating measurement would close that assumption?", a1_turn.meta.id, (claim,),
        )
        a2_turn = InquiryTurn(
            meta("IQT", "inquiry-turn/1.0"), contract, "xrd_specialist", InquiryTurnKind.REBUTTAL,
            "A stress-sensitive XRD measurement or independent phase/composition measurement is required.", q2.meta.id, (evidence,),
        )
        a2_arg = argument(
            a2_turn,
            role="xrd_specialist",
            position=ArgumentPosition.OPEN,
            requests=(AdditionalEvidenceRequest(
                "Obtain stress-sensitive XRD or independent composition/phase evidence.",
                "The Q-on-answer exposed a blocking discriminating-evidence gap.",
                (need,), target_refs=(claim,), requested_evidence_kinds=("stress-sensitive XRD", "independent composition"),
            ),),
            text="Cross-exam reaches an actionable evidence boundary",
        )
        s2 = observe_dialectic_step(
            level=DialecticLevel.L3_QUESTION_ON_ANSWER,
            argument=a2_arg,
            turn=a2_turn,
            history=s1.next_history,
            visible_refs=(evidence, claim),
            chain_turn_count=6,
            policy=DialecticPolicy(max_level=DialecticLevel.L3_QUESTION_ON_ANSWER),
        )
        self.assertEqual(s2.decision.action, DialecticAction.REQUEST_LOCAL_RESEARCH)
        self.assertEqual(s2.decision.next_level, DialecticLevel.L4_LOCAL_RESEARCH_ESCALATION)

        validate_dialectic_turn_chain((first_turn, challenge_turn, q1, a1_turn, q2, a2_turn))

        blocking_issue = next(x for x in s2.observation.new_issues if x.blocking)
        gap = gap_from_emergent_issue(issue=blocking_issue, target_claim_ids=(claim,), gap_id=ids.new("GAP"))
        challenge = challenge_from_gap(
            gap,
            req,
            EntityMeta(ids.new("RCH"), "research-challenge/1.0", 1, run, t, actor),
            dimensions={
                "origin": "TribunalDialectic",
                "issue_signature": blocking_issue.signature,
                "dialectic_level": int(s2.observation.level),
            },
        )
        self.assertEqual(challenge.source_entity_id, gap.id)
        self.assertEqual(challenge.target_claim_ids, (claim,))
        self.assertEqual(challenge.dimensions["origin"], "TribunalDialectic")
        self.assertEqual(first_arg.position, ArgumentPosition.QUALIFY)
        self.assertEqual(a2_arg.position, ArgumentPosition.OPEN)


if __name__ == "__main__":
    unittest.main()
