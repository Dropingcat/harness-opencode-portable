from __future__ import annotations

import random
import unittest
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_argument_graph import ArgumentRelation, ArgumentRelationKind, build_argument_graph
from researcher_core.tribunal_composition import AssessmentNeedRef, load_tribunal_composition_policy
from researcher_core.tribunal_disclosure import DisclosurePurpose, QuestionPurpose, compile_branch_ref, compile_dialectic_disclosure, compile_question_contract
from researcher_core.tribunal_inquiry import ArgumentArtifact, ArgumentPosition, InquiryTurn, InquiryTurnKind, ResponseGroundingState
from researcher_core.tribunal_live_dialogue import materialize_live_answer
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self): return 1789291000000


class ResponseGroundingTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[2]
        self.policy=load_tribunal_composition_policy(self.root/'config/tribunal_composition.yaml')
        self.handbook=load_role_handbook(self.root/'config/tribunal_role_handbook.yaml',self.policy)
        self.ids=EntityIdFactory(Clock(),random.Random(9551)); self.actor=ActorRef('AGENT','researcher')
        self.run=self.ids.new('RUN'); self.base=self.ids.new('IQC'); self.need=AssessmentNeedRef('ANR-grounding0000001',0)
        self.claim=self.ids.new('CLM'); self.evd=self.ids.new('EVD'); self.t=datetime(2026,9,13,20,0,tzinfo=timezone.utc)

    def meta(self,ns,schema,revision=1): return EntityMeta(self.ids.new(ns),schema,revision,self.run,self.t,self.actor)

    def fixture(self):
        rt=InquiryTurn(self.meta('IQT','inquiry-turn/1.0'),self.base,'xrd_specialist',InquiryTurnKind.FIRST_PASS_ASSESSMENT,'root',None,(self.claim,self.evd))
        root=ArgumentArtifact(self.meta('ARG','argument-artifact/1.0'),self.base,rt.meta.id,'xrd_specialist',ArgumentPosition.QUALIFY,(self.need,),'root','root justification',(self.evd,),(self.claim,),(),())
        ct=InquiryTurn(self.meta('IQT','inquiry-turn/1.0'),self.base,'skeptic',InquiryTurnKind.CHALLENGE,'challenge',None,(self.claim,self.evd))
        ch=ArgumentArtifact(self.meta('ARG','argument-artifact/1.0'),self.base,ct.meta.id,'skeptic',ArgumentPosition.CHALLENGE,(self.need,),'challenge','challenge justification',(self.evd,),(self.claim,),(),())
        rel=ArgumentRelation(self.meta('ARL','argument-relation/1.0'),ArgumentRelationKind.ATTACKS,ch.meta.id,root.meta.id,(self.need,),material=True)
        graph=build_argument_graph(meta=self.meta('AGP','argument-graph-projection/1.0'),arguments=(root,ch),relations=(rel,)); args={root.meta.id:root,ch.meta.id:ch}
        branch=compile_branch_ref(graph=graph,arguments=args,anchor_argument_id=ch.meta.id,anchor_relation_id=rel.meta.id)
        ddc=compile_dialectic_disclosure(role_id='skeptic',purpose=DisclosurePurpose.DIRECT_QUESTION,branch=branch,graph=graph,arguments=args,assigned_need_refs=(self.need,),id_factory=self.ids,actor=self.actor,created_at=self.t,focus_argument_id=ch.meta.id,focus_relation_id=rel.meta.id)
        inst=compile_role_instruction_pack(role_id='skeptic',variant=RoleVariantKind.CHALLENGER,handbook=self.handbook,policy=self.policy)
        dqc=compile_question_contract(purpose=QuestionPurpose.DIRECT_QUESTION,role_id='skeptic',answer_role_id='xrd_specialist',disclosure=ddc,instruction=inst,parent_turn_id=ct.meta.id,id_factory=self.ids,actor=self.actor,created_at=self.t,policy_version=self.policy.version,policy_hash=self.policy.policy_hash,target_argument_id=ch.meta.id,expected_closure_surface=('MISSING_EVIDENCE',))
        q=InquiryTurn(self.meta('IQT','inquiry-turn/1.0'),dqc.meta.id,'skeptic',InquiryTurnKind.QUESTION,'Why is that scientifically justified?',ct.meta.id,(ch.meta.id,self.claim,self.evd))
        return ddc,dqc,q

    def test_model_prior_specialist_answer_is_traceable_but_cannot_close_research(self):
        ddc,dqc,q=self.fixture()
        turn,arg=materialize_live_answer(contract=dqc,disclosure=ddc,question_turn=q,answer_role_id='xrd_specialist',provider_payload={
            'schema':'tribunal-answer-draft/1.1','position':'QUALIFY',
            'summary':'A residual-stress explanation is plausible from domain memory.',
            'justification':'This is remembered domain knowledge, not evidence in the disclosed package.',
            'cited_evidence_refs':[], 'cited_target_refs':[str(self.claim)],
            'discoveries':[], 'additional_evidence_requests':[],
            'grounding':[{'kind':'MODEL_PRIOR','statement':'Model prior only; requires external verification.','refs':[]}],
        },id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertEqual(arg.grounding_state,ResponseGroundingState.MODEL_PRIOR_ONLY)
        self.assertTrue(any(d.kind.value=='MISSING_EVIDENCE' and d.blocking for d in arg.discoveries))
        self.assertTrue(arg.additional_evidence_requests)
        self.assertEqual(turn.role_id,'xrd_specialist')

    def test_disclosed_evidence_specialist_answer_is_documented(self):
        ddc,dqc,q=self.fixture()
        _,arg=materialize_live_answer(contract=dqc,disclosure=ddc,question_turn=q,answer_role_id='xrd_specialist',provider_payload={
            'schema':'tribunal-answer-draft/1.1','position':'QUALIFY','summary':'The evidence supports only a narrower interpretation.','justification':'The disclosed measurement is compatible with both explanations.',
            'cited_evidence_refs':[str(self.evd)], 'cited_target_refs':[str(self.claim)],'discoveries':[], 'additional_evidence_requests':[],
            'grounding':[{'kind':'DISCLOSED_EVIDENCE','statement':'Uses the disclosed measurement evidence.','refs':[str(self.evd)]}],
        },id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertEqual(arg.grounding_state,ResponseGroundingState.DOCUMENTED)
        self.assertFalse(any(d.kind.value=='MISSING_EVIDENCE' and d.blocking for d in arg.discoveries))

if __name__=='__main__': unittest.main()
