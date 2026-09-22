from __future__ import annotations

import random, sys, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.jobs import job_ctl
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_argument_graph import ArgumentRelation, ArgumentRelationKind, build_argument_graph
from researcher_core.tribunal_composition import AssessmentNeedRef, load_tribunal_composition_policy
from researcher_core.tribunal_disclosure import DisclosurePurpose, QuestionPurpose, compile_branch_ref, compile_dialectic_disclosure, compile_question_contract
from researcher_core.tribunal_inquiry import ArgumentArtifact, ArgumentPosition, InquiryTurn, InquiryTurnKind, argument_artifact_to_dict, inquiry_turn_to_dict
from researcher_core.tribunal_live_dialogue import JobCtlLiveDialogueAdapter, SubprocessJsonProviderTransport, compile_execution_envelope
from researcher_core.tribunal_provider_binding import compile_answer_provider_binding, compile_question_provider_binding, load_provider_binding_policy
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self): return 1789282000000


class SecondRoleFamilyE2E(unittest.TestCase):
    def setUp(self):
        self.root=Path(__file__).resolve().parents[2]
        self.policy=load_tribunal_composition_policy(self.root/'config/tribunal_composition.yaml')
        self.handbook=load_role_handbook(self.root/'config/tribunal_role_handbook.yaml',self.policy)
        self.bind_policy=load_provider_binding_policy(self.root/'config/tribunal_provider_binding.yaml')
        self.ids=EntityIdFactory(Clock(),random.Random(20260913)); self.actor=ActorRef('AGENT','researcher'); self.run=self.ids.new('RUN'); self.base=self.ids.new('IQC'); self.need=AssessmentNeedRef('ANR-l3domain000001',0)
        self.claim=self.ids.new('CLM'); self.evd=self.ids.new('EVD'); self.t=datetime(2026,9,13,19,15,tzinfo=timezone.utc)
        self.providers={'providers':{
          'p.meta':{'kind':'process','tool':'tribunal_meta','provides':['tribunal.role.execute'],'priority':100,'live_probe':{'kind':'always'},'role_kinds':['META'],'execution_contracts':['DQC']},
          'p.method':{'kind':'process','tool':'tribunal_method','provides':['tribunal.role.execute'],'priority':500,'live_probe':{'kind':'always'},'role_kinds':['METHOD'],'execution_contracts':['DQC']},
          'p.domain':{'kind':'process','tool':'tribunal_domain','provides':['tribunal.role.execute'],'priority':80,'live_probe':{'kind':'always'},'role_kinds':['DOMAIN'],'execution_contracts':['DQC']},
        }}
        self.runtime={'tools':{'tribunal_meta':{'provider':'meta_runtime'},'tribunal_method':{'provider':'method_runtime'},'tribunal_domain':{'provider':'domain_runtime'}}}
        self.preflight={'schema':'capability-preflight/1.0','network_probes':False,'providers':{pid:{'status':'available','available':True,'implemented':True,'detail':'fixture','kind':'process','provides':['tribunal.role.execute'],'priority':spec['priority']} for pid,spec in self.providers['providers'].items()}}
        stub=(sys.executable,str(self.root/'tests/researcher/fixtures/tribunal_live_provider_stub.py'))
        self.transport=SubprocessJsonProviderTransport({pid:stub for pid in self.providers['providers']})

    def meta(self,ns,schema): return EntityMeta(self.ids.new(ns),schema,1,self.run,self.t,self.actor)

    def test_domain_answerer_uses_domain_provider_not_higher_priority_method_provider(self):
        root_t=InquiryTurn(self.meta('IQT','inquiry-turn/1.0'),self.base,'crystallographer',InquiryTurnKind.FIRST_PASS_ASSESSMENT,'structural interpretation',None,(self.claim,self.evd))
        root=ArgumentArtifact(self.meta('ARG','argument-artifact/1.0'),self.base,root_t.meta.id,'crystallographer',ArgumentPosition.QUALIFY,(self.need,),'phase interpretation','phase/lattice interpretation remains qualified',(self.evd,),(self.claim,),(),())
        ch_t=InquiryTurn(self.meta('IQT','inquiry-turn/1.0'),self.base,'skeptic',InquiryTurnKind.CHALLENGE,'alternative phase remains',None,(self.claim,self.evd))
        ch=ArgumentArtifact(self.meta('ARG','argument-artifact/1.0'),self.base,ch_t.meta.id,'skeptic',ArgumentPosition.CHALLENGE,(self.need,),'alternative phase','alternative structural assignment is not excluded',(self.evd,),(self.claim,),(),())
        rel=ArgumentRelation(self.meta('ARL','argument-relation/1.0'),ArgumentRelationKind.ATTACKS,ch.meta.id,root.meta.id,(self.need,),material=True)
        graph=build_argument_graph(meta=self.meta('AGP','argument-graph-projection/1.0'),arguments=(root,ch),relations=(rel,)); args={root.meta.id:root,ch.meta.id:ch}
        branch=compile_branch_ref(graph=graph,arguments=args,anchor_argument_id=ch.meta.id,anchor_relation_id=rel.meta.id)
        ddc=compile_dialectic_disclosure(role_id='skeptic',purpose=DisclosurePurpose.DIRECT_QUESTION,branch=branch,graph=graph,arguments=args,assigned_need_refs=(self.need,),id_factory=self.ids,actor=self.actor,created_at=self.t,focus_argument_id=ch.meta.id,focus_relation_id=rel.meta.id)
        qinst=compile_role_instruction_pack(role_id='skeptic',variant=RoleVariantKind.CHALLENGER,handbook=self.handbook,policy=self.policy)
        dqc=compile_question_contract(purpose=QuestionPurpose.DIRECT_QUESTION,role_id='skeptic',answer_role_id='crystallographer',disclosure=ddc,instruction=qinst,parent_turn_id=ch_t.meta.id,id_factory=self.ids,actor=self.actor,created_at=self.t,policy_version=self.policy.version,policy_hash=self.policy.policy_hash,target_argument_id=ch.meta.id,expected_closure_surface=('SCOPE_ISSUE','METHOD_LIMITATION','MISSING_EVIDENCE'))
        common=dict(composition_policy=self.policy,binding_policy=self.bind_policy,providers_authority=self.providers,runtime_bindings=self.runtime,preflight=self.preflight,capability_policy_hash='sha256:domain-fixture',id_factory=self.ids,actor=self.actor,created_at=self.t)
        qb=compile_question_provider_binding(contract=dqc,requested_role_id=None,**common)
        ab=compile_answer_provider_binding(contract=dqc,target_argument=ch,requested_role_id=None,**common)
        self.assertEqual(qb.selected_provider_id,'p.meta')
        self.assertEqual(ab.selected_provider_id,'p.domain')
        self.assertIn('p.method',ab.rejected_provider_reasons)
        refs={self.claim:{'kind':'Claim','text':'phase interpretation'},self.evd:{'kind':'Evidence','text':'visible diffraction evidence'}}
        ap={x.meta.id:argument_artifact_to_dict(x) for x in (root,ch)}; tp={x.meta.id:inquiry_turn_to_dict(x) for x in (root_t,ch_t)}
        qenv=compile_execution_envelope(binding=qb,disclosure=ddc,question_contract=dqc,instruction=qinst,argument_payloads=ap,turn_payloads=tp,ref_payloads=refs,id_factory=self.ids,actor=self.actor,created_at=self.t)
        ainst=compile_role_instruction_pack(role_id='crystallographer',variant=RoleVariantKind.CROSS_EXAM,handbook=self.handbook,policy=self.policy)
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); parent=td/'parent.json'; job_ctl.save(job_ctl.create('l3-domain-parent',{'schema':'fixture/1.0'},['tribunal']),parent)
            rt=JobCtlLiveDialogueAdapter(state_dir=td/'jobs',artifact_dir=td/'artifacts',timeout_seconds=5)
            q,_=rt.execute_question(parent_state_path=parent,binding=qb,envelope=qenv,current_preflight=self.preflight,transport=self.transport,contract=dqc,disclosure=ddc,id_factory=self.ids,actor=self.actor,created_at=self.t)
            aenv=compile_execution_envelope(binding=ab,disclosure=ddc,question_contract=dqc,instruction=ainst,argument_payloads=ap,turn_payloads={**tp,q.meta.id:inquiry_turn_to_dict(q)},ref_payloads=refs,question_turn=q,id_factory=self.ids,actor=self.actor,created_at=self.t)
            ans,arg,receipt=rt.execute_answer(parent_state_path=parent,binding=ab,envelope=aenv,current_preflight=self.preflight,transport=self.transport,contract=dqc,disclosure=ddc,question_turn=q,id_factory=self.ids,actor=self.actor,created_at=self.t)
            self.assertEqual(arg.role_id,'crystallographer'); self.assertEqual(receipt.provider_id,'p.domain')
            self.assertEqual(len(job_ctl.load(parent)['children']),2)


if __name__=='__main__': unittest.main()
