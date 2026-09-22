from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.jobs import job_ctl
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_argument_graph import ArgumentRelation, ArgumentRelationKind, append_argument_branch, build_argument_graph
from researcher_core.tribunal_composition import AssessmentNeedRef, load_tribunal_composition_policy
from researcher_core.tribunal_dialectic import DialecticAction, new_branch_history, observe_branch_dialectic_step
from researcher_core.tribunal_disclosure import DisclosurePurpose, QuestionPurpose, compile_branch_ref, compile_dialectic_disclosure, compile_question_contract, refresh_branch_ref
from researcher_core.tribunal_inquiry import ArgumentArtifact, ArgumentPosition, InquiryTurn, InquiryTurnKind, argument_artifact_to_dict, inquiry_turn_to_dict
from researcher_core.tribunal_live_dialogue import JobCtlLiveDialogueAdapter, SubprocessJsonProviderTransport, admit_live_answer_to_argument_graph, compile_execution_envelope
from researcher_core.tribunal_provider_binding import compile_answer_provider_binding, compile_question_provider_binding, load_provider_binding_policy
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self): return 1789281000000


class R44L3LiveDialogueE2E(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[2]
        self.policy=load_tribunal_composition_policy(self.root/'config/tribunal_composition.yaml')
        self.handbook=load_role_handbook(self.root/'config/tribunal_role_handbook.yaml',self.policy)
        self.binding_policy=load_provider_binding_policy(self.root/'config/tribunal_provider_binding.yaml')
        self.ids=EntityIdFactory(Clock(),random.Random(94431)); self.actor=ActorRef('AGENT','researcher')
        self.run=self.ids.new('RUN'); self.base_contract=self.ids.new('IQC'); self.need=AssessmentNeedRef('ANR-l3live00000001',0)
        self.claim=self.ids.new('CLM'); self.e_support=self.ids.new('EVD'); self.e_attack=self.ids.new('EVD'); self.e_sibling=self.ids.new('EVD')
        self.t=datetime(2026,9,13,18,30,tzinfo=timezone.utc)
        self.providers={'providers':{'test.live_process':{'kind':'process','tool':'tribunal_live_stub','provides':['tribunal.role.execute'],'priority':100,'live_probe':{'kind':'always'}}}}
        self.runtime_bindings={'tools':{'tribunal_live_stub':{'provider':'test_live_process'}}}
        self.preflight={'schema':'capability-preflight/1.0','network_probes':False,'providers':{'test.live_process':{'status':'available','available':True,'implemented':True,'detail':'fixture-process','kind':'process','provides':['tribunal.role.execute'],'priority':100}}}
        self.cap_hash='sha256:l3-e2e-capability-policy'
        self.transport=SubprocessJsonProviderTransport({'test.live_process':(sys.executable,str(self.root/'tests/researcher/fixtures/tribunal_live_provider_stub.py'))})

    def meta(self,ns,schema,*,entity_id=None,revision=1): return EntityMeta(entity_id or self.ids.new(ns),schema,revision,self.run,self.t,self.actor)
    def base_arg(self,role,pos,text,evd,kind):
        turn=InquiryTurn(self.meta('IQT','inquiry-turn/1.0'),self.base_contract,role,kind,text,None,(self.claim,evd))
        arg=ArgumentArtifact(self.meta('ARG','argument-artifact/1.0'),self.base_contract,turn.meta.id,role,pos,(self.need,),text,text+' justification',(evd,),(self.claim,),(),())
        return turn,arg
    def bindq(self,c,role=None):
        return compile_question_provider_binding(contract=c,requested_role_id=role,composition_policy=self.policy,binding_policy=self.binding_policy,providers_authority=self.providers,runtime_bindings=self.runtime_bindings,preflight=self.preflight,capability_policy_hash=self.cap_hash,id_factory=self.ids,actor=self.actor,created_at=self.t)
    def binda(self,c,target,role=None):
        return compile_answer_provider_binding(contract=c,target_argument=target,requested_role_id=role,composition_policy=self.policy,binding_policy=self.binding_policy,providers_authority=self.providers,runtime_bindings=self.runtime_bindings,preflight=self.preflight,capability_policy_hash=self.cap_hash,id_factory=self.ids,actor=self.actor,created_at=self.t)
    def refs(self):
        return {self.claim:{'kind':'Claim','text':'BCC lattice parameter change interpretation'},self.e_support:{'kind':'Evidence','text':'disclosed support evidence'},self.e_attack:{'kind':'Evidence','text':'residual-stress counterevidence'},self.e_sibling:{'kind':'Evidence','text':'hidden sibling calibration evidence'}}

    def test_live_process_q1_a1_q2_a2_is_branch_bounded(self):
        root_turn,root=self.base_arg('xrd_specialist',ArgumentPosition.QUALIFY,'root interpretation',self.e_support,InquiryTurnKind.FIRST_PASS_ASSESSMENT)
        a_turn,attack_a=self.base_arg('skeptic',ArgumentPosition.CHALLENGE,'residual stress alternative',self.e_attack,InquiryTurnKind.CHALLENGE)
        b_turn,attack_b=self.base_arg('methodologist',ArgumentPosition.CHALLENGE,'calibration undercut',self.e_sibling,InquiryTurnKind.CHALLENGE)
        rel_a=ArgumentRelation(self.meta('ARL','argument-relation/1.0'),ArgumentRelationKind.ATTACKS,attack_a.meta.id,root.meta.id,(self.need,),material=True)
        rel_b=ArgumentRelation(self.meta('ARL','argument-relation/1.0'),ArgumentRelationKind.UNDERCUTS,attack_b.meta.id,root.meta.id,(self.need,),material=True)
        graph1=build_argument_graph(meta=self.meta('AGP','argument-graph-projection/1.0'),arguments=(root,attack_a,attack_b),relations=(rel_a,rel_b)); args1={x.meta.id:x for x in (root,attack_a,attack_b)}
        branch=compile_branch_ref(graph=graph1,arguments=args1,anchor_argument_id=attack_a.meta.id,anchor_relation_id=rel_a.meta.id)
        hist=new_branch_history(branch)
        challenge=observe_branch_dialectic_step(branch=branch,argument=attack_a,turn=a_turn,branch_history=hist,visible_refs=(self.claim,self.e_attack),chain_turn_count=1)
        self.assertEqual(challenge.decision.action,DialecticAction.CONTINUE_QA)
        d1=compile_dialectic_disclosure(role_id='skeptic',purpose=DisclosurePurpose.DIRECT_QUESTION,branch=branch,graph=graph1,arguments=args1,assigned_need_refs=(self.need,),id_factory=self.ids,actor=self.actor,created_at=self.t,focus_argument_id=attack_a.meta.id,focus_relation_id=rel_a.meta.id)
        self.assertIn(attack_b.meta.id,d1.hidden_argument_ids)
        sk=compile_role_instruction_pack(role_id='skeptic',variant=RoleVariantKind.CHALLENGER,handbook=self.handbook,policy=self.policy)
        q1c=compile_question_contract(purpose=QuestionPurpose.DIRECT_QUESTION,role_id='skeptic',disclosure=d1,instruction=sk,answer_role_id='xrd_specialist',parent_turn_id=a_turn.meta.id,id_factory=self.ids,actor=self.actor,created_at=self.t,policy_version=self.policy.version,policy_hash=self.policy.policy_hash,target_argument_id=attack_a.meta.id,expected_closure_surface=('ASSUMPTION_ISSUE','MISSING_EVIDENCE'))
        qb=self.bindq(q1c)
        qp={x.meta.id:argument_artifact_to_dict(x) for x in (root,attack_a,attack_b)}; tp={x.meta.id:inquiry_turn_to_dict(x) for x in (root_turn,a_turn,b_turn)}
        qenv=compile_execution_envelope(binding=qb,disclosure=d1,question_contract=q1c,instruction=sk,argument_payloads=qp,turn_payloads=tp,ref_payloads=self.refs(),id_factory=self.ids,actor=self.actor,created_at=self.t)
        self.assertNotIn(str(attack_b.meta.id),qenv.material); self.assertNotIn(str(self.e_sibling),qenv.material)
        xrd=compile_role_instruction_pack(role_id='xrd_specialist',variant=RoleVariantKind.CROSS_EXAM,handbook=self.handbook,policy=self.policy)
        ab=self.binda(q1c,attack_a,role='skeptic')
        self.assertEqual(ab.status.value,'ROLE_MISMATCH')
        # DQC addresses the answer role explicitly; target argument and answerer are separate semantics.
        answer_instruction=compile_role_instruction_pack(role_id='xrd_specialist',variant=RoleVariantKind.CROSS_EXAM,handbook=self.handbook,policy=self.policy)
        ab=self.binda(q1c,attack_a)
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); parent_path=td/'parent.json'; job_ctl.save(job_ctl.create('r4-l3-parent',{'schema':'fixture/1.0'},['tribunal']),parent_path)
            runtime=JobCtlLiveDialogueAdapter(state_dir=td/'jobs',artifact_dir=td/'artifacts',timeout_seconds=5)
            q1,qrec=runtime.execute_question(parent_state_path=parent_path,binding=qb,envelope=qenv,current_preflight=self.preflight,transport=self.transport,contract=q1c,disclosure=d1,id_factory=self.ids,actor=self.actor,created_at=self.t)
            # Rebuild answer envelope after Q1 so the question turn itself is visible material.
            tp1={**tp,q1.meta.id:inquiry_turn_to_dict(q1)}
            aenv=compile_execution_envelope(binding=ab,disclosure=d1,question_contract=q1c,instruction=answer_instruction,argument_payloads=qp,turn_payloads=tp1,ref_payloads=self.refs(),question_turn=q1,id_factory=self.ids,actor=self.actor,created_at=self.t)
            self.assertEqual(aenv.question_turn_id, q1.meta.id)
            self.assertIn(q1.meta.id, aenv.visible_turn_ids)
            self.assertEqual(aenv.material[str(q1.meta.id)]['content'], q1.content)
            a1,a1arg,arec=runtime.execute_answer(parent_state_path=parent_path,binding=ab,envelope=aenv,current_preflight=self.preflight,transport=self.transport,contract=q1c,disclosure=d1,question_turn=q1,id_factory=self.ids,actor=self.actor,created_at=self.t)
            self.assertEqual(qrec.status.value,'COMPLETED'); self.assertEqual(arec.status.value,'COMPLETED')
            self.assertTrue((td/'artifacts'/f'{qrec.meta.id}.json').exists())
            self.assertTrue((td/'artifacts'/f'{arec.meta.id}.json').exists())
            self.assertEqual(json.loads((td/'artifacts'/f'{qrec.meta.id}.json').read_text())['status'],'COMPLETED')
            self.assertEqual(a1arg.position,ArgumentPosition.QUALIFY); self.assertTrue(a1arg.discoveries)
            graph2,args2,branch2,reply=admit_live_answer_to_argument_graph(graph=graph1,arguments=args1,branch=branch,question_contract=q1c,answer_argument=a1arg,id_factory=self.ids,actor=self.actor,created_at=self.t)
            self.assertEqual(reply.kind,ArgumentRelationKind.REPLIES_TO)
            step1=observe_branch_dialectic_step(branch=branch2,argument=a1arg,turn=a1,branch_history=challenge.next_branch_history,visible_refs=(self.claim,self.e_support,self.e_attack),chain_turn_count=3)
            self.assertEqual(step1.decision.action,DialecticAction.CONTINUE_QUESTION_ON_ANSWER); issue=step1.observation.new_issues[0].signature
            d2=compile_dialectic_disclosure(role_id='methodologist',purpose=DisclosurePurpose.QUESTION_ON_ANSWER,branch=branch2,graph=graph2,arguments=args2,assigned_need_refs=(self.need,),id_factory=self.ids,actor=self.actor,created_at=self.t,focus_argument_id=a1arg.meta.id,focus_turn_id=a1.meta.id,focus_issue_signature=issue)
            mi=compile_role_instruction_pack(role_id='methodologist',variant=RoleVariantKind.CROSS_EXAM,handbook=self.handbook,policy=self.policy)
            q2c=compile_question_contract(purpose=QuestionPurpose.QUESTION_ON_ANSWER,role_id='methodologist',disclosure=d2,instruction=mi,answer_role_id='xrd_specialist',parent_turn_id=a1.meta.id,id_factory=self.ids,actor=self.actor,created_at=self.t,policy_version=self.policy.version,policy_hash=self.policy.policy_hash,target_argument_id=a1arg.meta.id,target_turn_id=a1.meta.id,target_issue_signature=issue,admitted_new_issue_signatures=tuple(x.signature for x in step1.observation.new_issues),expected_closure_surface=('MISSING_EVIDENCE','RESOLVED'),max_followups=0)
            q2b=self.bindq(q2c); q2env=compile_execution_envelope(binding=q2b,disclosure=d2,question_contract=q2c,instruction=mi,argument_payloads={x.meta.id:argument_artifact_to_dict(x) for x in args2.values()},turn_payloads={**tp1,a1.meta.id:inquiry_turn_to_dict(a1)},ref_payloads=self.refs(),id_factory=self.ids,actor=self.actor,created_at=self.t)
            q2,_=runtime.execute_question(parent_state_path=parent_path,binding=q2b,envelope=q2env,current_preflight=self.preflight,transport=self.transport,contract=q2c,disclosure=d2,id_factory=self.ids,actor=self.actor,created_at=self.t)
            xrd_cross=compile_role_instruction_pack(role_id='xrd_specialist',variant=RoleVariantKind.CROSS_EXAM,handbook=self.handbook,policy=self.policy)
            a2b=self.binda(q2c,a1arg)
            a2env=compile_execution_envelope(binding=a2b,disclosure=d2,question_contract=q2c,instruction=xrd_cross,argument_payloads={x.meta.id:argument_artifact_to_dict(x) for x in args2.values()},turn_payloads={**tp1,a1.meta.id:inquiry_turn_to_dict(a1),q2.meta.id:inquiry_turn_to_dict(q2)},ref_payloads=self.refs(),question_turn=q2,id_factory=self.ids,actor=self.actor,created_at=self.t)
            a2,a2arg,_=runtime.execute_answer(parent_state_path=parent_path,binding=a2b,envelope=a2env,current_preflight=self.preflight,transport=self.transport,contract=q2c,disclosure=d2,question_turn=q2,id_factory=self.ids,actor=self.actor,created_at=self.t)
            self.assertEqual(a2arg.position,ArgumentPosition.OPEN); self.assertTrue(a2arg.additional_evidence_requests)
            graph3,args3,branch3,_=admit_live_answer_to_argument_graph(graph=graph2,arguments=args2,branch=branch2,question_contract=q2c,answer_argument=a2arg,id_factory=self.ids,actor=self.actor,created_at=self.t)
            step2=observe_branch_dialectic_step(branch=branch3,argument=a2arg,turn=a2,branch_history=step1.next_branch_history,visible_refs=(self.claim,self.e_support,self.e_attack),chain_turn_count=5)
            self.assertEqual(step2.decision.action,DialecticAction.REQUEST_LOCAL_RESEARCH)
            parent=job_ctl.load(parent_path); self.assertEqual(len(parent['children']),4); self.assertTrue(all(c['status']=='COMPLETED' for c in parent['children']))
            self.assertNotIn(str(self.e_sibling),q2env.material)

if __name__=='__main__': unittest.main()
