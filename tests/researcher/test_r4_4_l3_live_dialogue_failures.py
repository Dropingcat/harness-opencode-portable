from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from scripts.jobs import job_ctl
from tests.researcher.test_r4_4_l3_live_dialogue_e2e import R44L3LiveDialogueE2E as _BaseL3
from researcher_core.tribunal_argument_graph import ArgumentRelation, ArgumentRelationKind, build_argument_graph
from researcher_core.tribunal_dialectic import new_branch_history, observe_branch_dialectic_step
from researcher_core.tribunal_disclosure import DisclosurePurpose, QuestionPurpose, compile_branch_ref, compile_dialectic_disclosure, compile_question_contract
from researcher_core.tribunal_inquiry import ArgumentPosition, InquiryTurnKind, argument_artifact_to_dict, inquiry_turn_to_dict
from researcher_core.tribunal_live_dialogue import (
    JobCtlLiveDialogueAdapter,
    LogicalToolProviderTransport,
    SubprocessJsonProviderTransport,
    TribunalLiveDialogueError,
    TribunalLiveDialogueTimeout,
    compile_execution_envelope,
    execution_envelope_from_dict, execution_envelope_to_dict,
    provider_execution_receipt_from_dict, provider_execution_receipt_to_dict,
)
from researcher_core.tribunal_provider_binding import TribunalProviderBindingError, role_provider_binding_from_dict, role_provider_binding_to_dict
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack


class R44L3LiveDialogueFailureTests(_BaseL3):
    # Parent E2E is collected separately; suppress the inherited test here.
    test_live_process_q1_a1_q2_a2_is_branch_bounded = None

    def q1_fixture(self):
        root_turn, root = self.base_arg('xrd_specialist', ArgumentPosition.QUALIFY, 'root interpretation', self.e_support, InquiryTurnKind.FIRST_PASS_ASSESSMENT)
        a_turn, attack = self.base_arg('skeptic', ArgumentPosition.CHALLENGE, 'residual stress alternative', self.e_attack, InquiryTurnKind.CHALLENGE)
        b_turn, sibling = self.base_arg('methodologist', ArgumentPosition.CHALLENGE, 'hidden calibration branch', self.e_sibling, InquiryTurnKind.CHALLENGE)
        rel_a = ArgumentRelation(self.meta('ARL','argument-relation/1.0'), ArgumentRelationKind.ATTACKS, attack.meta.id, root.meta.id, (self.need,), material=True)
        rel_b = ArgumentRelation(self.meta('ARL','argument-relation/1.0'), ArgumentRelationKind.UNDERCUTS, sibling.meta.id, root.meta.id, (self.need,), material=True)
        graph = build_argument_graph(meta=self.meta('AGP','argument-graph-projection/1.0'), arguments=(root,attack,sibling), relations=(rel_a,rel_b))
        args = {x.meta.id:x for x in (root,attack,sibling)}
        branch = compile_branch_ref(graph=graph, arguments=args, anchor_argument_id=attack.meta.id, anchor_relation_id=rel_a.meta.id)
        observe_branch_dialectic_step(branch=branch, argument=attack, turn=a_turn, branch_history=new_branch_history(branch), visible_refs=(self.claim,self.e_attack), chain_turn_count=1)
        disclosure = compile_dialectic_disclosure(role_id='skeptic', purpose=DisclosurePurpose.DIRECT_QUESTION, branch=branch, graph=graph, arguments=args, assigned_need_refs=(self.need,), id_factory=self.ids, actor=self.actor, created_at=self.t, focus_argument_id=attack.meta.id, focus_relation_id=rel_a.meta.id)
        instruction = compile_role_instruction_pack(role_id='skeptic', variant=RoleVariantKind.CHALLENGER, handbook=self.handbook, policy=self.policy)
        contract = compile_question_contract(purpose=QuestionPurpose.DIRECT_QUESTION, role_id='skeptic', answer_role_id='xrd_specialist', disclosure=disclosure, instruction=instruction, parent_turn_id=a_turn.meta.id, id_factory=self.ids, actor=self.actor, created_at=self.t, policy_version=self.policy.version, policy_hash=self.policy.policy_hash, target_argument_id=attack.meta.id, expected_closure_surface=('ASSUMPTION_ISSUE','MISSING_EVIDENCE'))
        binding = self.bindq(contract)
        argument_payloads = {x.meta.id: argument_artifact_to_dict(x) for x in args.values()}
        turn_payloads = {x.meta.id: inquiry_turn_to_dict(x) for x in (root_turn,a_turn,b_turn)}
        envelope = compile_execution_envelope(binding=binding, disclosure=disclosure, question_contract=contract, instruction=instruction, argument_payloads=argument_payloads, turn_payloads=turn_payloads, ref_payloads=self.refs(), id_factory=self.ids, actor=self.actor, created_at=self.t)
        return root, attack, sibling, disclosure, instruction, contract, binding, envelope, argument_payloads, turn_payloads

    def parent_runtime(self, td: Path, *, timeout=1.0):
        parent_path = td/'parent.json'
        job_ctl.save(job_ctl.create('r4-l3-failure-parent', {'schema':'fixture/1.0'}, ['tribunal']), parent_path)
        return parent_path, JobCtlLiveDialogueAdapter(state_dir=td/'jobs', artifact_dir=td/'artifacts', timeout_seconds=timeout)


    def test_binding_and_execution_envelope_roundtrip_preserve_fingerprints(self):
        _,_,_,_,_,_,binding,envelope,_,_ = self.q1_fixture()
        restored_binding = role_provider_binding_from_dict(role_provider_binding_to_dict(binding))
        restored_envelope = execution_envelope_from_dict(execution_envelope_to_dict(envelope))
        self.assertEqual(restored_binding, binding)
        self.assertEqual(restored_envelope, envelope)

    def test_stale_provider_after_binding_stops_before_child_job(self):
        _,_,_,d,_,c,b,e,_,_ = self.q1_fixture()
        stale = {'schema':'capability-preflight/1.0','network_probes':False,'providers':{'test.live_process':{'status':'degraded','available':False,'implemented':True,'detail':'provider disappeared','kind':'process','provides':['tribunal.role.execute'],'priority':100}}}
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); parent,runtime=self.parent_runtime(td)
            with self.assertRaises(TribunalProviderBindingError):
                runtime.execute_question(parent_state_path=parent,binding=b,envelope=e,current_preflight=stale,transport=self.transport,contract=c,disclosure=d,id_factory=self.ids,actor=self.actor,created_at=self.t)
            self.assertEqual(job_ctl.load(parent)['children'], [])

    def test_provider_timeout_is_runtime_failure_not_semantic_open(self):
        _,_,_,d,_,c,b,e,_,_ = self.q1_fixture()
        transport=SubprocessJsonProviderTransport({'test.live_process':(sys.executable,str(self.root/'tests/researcher/fixtures/tribunal_live_provider_stub.py'),'sleep')})
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); parent,runtime=self.parent_runtime(td,timeout=0.05)
            with self.assertRaises(TribunalLiveDialogueTimeout):
                runtime.execute_question(parent_state_path=parent,binding=b,envelope=e,current_preflight=self.preflight,transport=transport,contract=c,disclosure=d,id_factory=self.ids,actor=self.actor,created_at=self.t)
            p=job_ctl.load(parent); self.assertEqual(p['children'][0]['status'],'TIMED_OUT')
            child=job_ctl.load(next((td/'jobs').glob('*.json'))); self.assertEqual(child['status'],'FAILED_NO_OUTPUT')
            self.assertEqual(child['attempts'][0]['status'],'TIMED_OUT')
            per_files=list((td/'artifacts').glob('PER_*.json')); self.assertEqual(len(per_files),1)
            raw_receipt=json.loads(per_files[0].read_text()); self.assertEqual(raw_receipt['status'],'TIMED_OUT')
            restored_receipt=provider_execution_receipt_from_dict(raw_receipt)
            self.assertEqual(provider_execution_receipt_to_dict(restored_receipt),raw_receipt)

    def test_invalid_json_provider_output_fails_attempt(self):
        _,_,_,d,_,c,b,e,_,_ = self.q1_fixture()
        transport=SubprocessJsonProviderTransport({'test.live_process':(sys.executable,str(self.root/'tests/researcher/fixtures/tribunal_live_provider_stub.py'),'invalid-json')})
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); parent,runtime=self.parent_runtime(td)
            with self.assertRaisesRegex(TribunalLiveDialogueError,'invalid JSON'):
                runtime.execute_question(parent_state_path=parent,binding=b,envelope=e,current_preflight=self.preflight,transport=transport,contract=c,disclosure=d,id_factory=self.ids,actor=self.actor,created_at=self.t)
            child=job_ctl.load(next((td/'jobs').glob('*.json'))); self.assertEqual(child['status'],'FAILED_NO_OUTPUT')
            self.assertEqual(child['attempts'][0]['status'],'FAILED')
            per_files=list((td/'artifacts').glob('PER_*.json')); self.assertEqual(len(per_files),1)
            self.assertEqual(json.loads(per_files[0].read_text())['status'],'FAILED')

    def test_answer_cannot_smuggle_hidden_sibling_evidence(self):
        _,attack,_,d,_,c,qbind,qenv,arg_payloads,turn_payloads = self.q1_fixture()
        answer_instruction=compile_role_instruction_pack(role_id='xrd_specialist',variant=RoleVariantKind.CROSS_EXAM,handbook=self.handbook,policy=self.policy)
        abind=self.binda(c,attack)
        with tempfile.TemporaryDirectory() as raw:
            td=Path(raw); parent,runtime=self.parent_runtime(td)
            q1,_=runtime.execute_question(parent_state_path=parent,binding=qbind,envelope=qenv,current_preflight=self.preflight,transport=self.transport,contract=c,disclosure=d,id_factory=self.ids,actor=self.actor,created_at=self.t)
            turns={**turn_payloads,q1.meta.id:inquiry_turn_to_dict(q1)}
            aenv=compile_execution_envelope(binding=abind,disclosure=d,question_contract=c,instruction=answer_instruction,argument_payloads=arg_payloads,turn_payloads=turns,ref_payloads=self.refs(),question_turn=q1,id_factory=self.ids,actor=self.actor,created_at=self.t)
            bad=SubprocessJsonProviderTransport({'test.live_process':(sys.executable,str(self.root/'tests/researcher/fixtures/tribunal_live_provider_stub.py'),'hidden-answer',str(self.e_sibling))})
            with self.assertRaisesRegex(TribunalLiveDialogueError,'outside question disclosure|hidden evidence|hidden material'):
                runtime.execute_answer(parent_state_path=parent,binding=abind,envelope=aenv,current_preflight=self.preflight,transport=bad,contract=c,disclosure=d,question_turn=q1,id_factory=self.ids,actor=self.actor,created_at=self.t)
            children=job_ctl.load(parent)['children']; self.assertEqual(len(children),2); self.assertEqual(children[-1]['status'],'FAILED')
            receipts=[json.loads(x.read_text()) for x in (td/'artifacts').glob('PER_*.json')]
            self.assertIn('REJECTED',{x['status'] for x in receipts})

    def test_logical_tool_transport_uses_binding_selected_tool_only(self):
        _,_,_,_,_,_,b,e,_,_ = self.q1_fixture()
        calls=[]
        def invoke_tool(**kw):
            calls.append(kw)
            return {'schema':'tribunal-question-draft/1.0','question':'bounded question'}
        out=LogicalToolProviderTransport(invoke_tool).invoke(binding=b,envelope=e,timeout_seconds=3)
        self.assertEqual(out['schema'],'tribunal-question-draft/1.0')
        self.assertEqual(calls[0]['tool_name'],b.selected_runtime_tool)
        self.assertEqual(calls[0]['provider_id'],b.selected_provider_id)
        self.assertEqual(calls[0]['arguments']['execution_envelope']['id'],str(e.meta.id))


if __name__ == '__main__':
    import unittest
    unittest.main()
