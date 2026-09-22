from __future__ import annotations
import copy,tempfile,unittest
from pathlib import Path
import yaml
from scripts.writer.references.select import select
from scripts.writer.references.evidence_select import select_for_claims
from scripts.writer.composition.style_instruction import build as build_style
from scripts.writer.composition.writing_policy import build as build_policy
from scripts.writer.drafting.artifact import build as build_draft
from scripts.writer.drafting.request import build as build_request
from scripts.writer.authority.realization import resolve as resolve_authority
from scripts.writer.release.gate import evaluate_release
from scripts.writer.provenance.state_policy import apply_invalidation
from scripts.writer.review import citation_trace
from scripts.researcher.verify_claims import verify_claim,_merge_verification

class WriterV1FreezeTests(unittest.TestCase):
    def _frag(self,fid,lang='ru',kind='dissertation',role='discussion',style=True,evidence=False,excerpt='азотирование фазовые превращения Fe4N',graph=True):
        return {'fragment_id':fid,'reference_id':'R-'+fid,'document_kind':kind,'language':lang,'section_role':role,'permissions':{'style':style,'evidence':evidence},'locator':'pdf_page:1','excerpt':excerpt,'style_features':{'words':120,'citation_density_per_1000':8,'hedge_density_per_1000':2,'causal_density_per_1000':3},'graph_digest':{'available':graph,'graph_ids':['G5','G13'],'node_types':{'CLAIM':2},'edge_relations':{'SUPPORTS':2,'INTERPRETS':1}}}

    def test_cross_language_style_is_structure_only(self):
        fr=[self._frag('RU','ru'),self._frag('EN','en')]
        target_graph={'available':True,'graph_ids':['G5','G13'],'node_types':{'CLAIM':1},'edge_relations':{'SUPPORTS':1,'INTERPRETS':1}}
        r=select(fr,role='style',target_kind='dissertation',language='ru',section_role='discussion',target_style={'words':120,'citation_density_per_1000':8,'hedge_density_per_1000':2,'causal_density_per_1000':3},target_graph=target_graph,limit=2)
        by={x['fragment_id']:x for x in r['selected']}
        self.assertEqual('FULL',by['RU']['style_authority'])
        self.assertEqual('STRUCTURE_ONLY',by['EN']['style_authority'])
        self.assertIn('argument_structure',by['EN']['allowed_take'])
        self.assertNotIn('surface_rhetoric',by['EN']['allowed_take'])

    def test_style_instruction_does_not_take_cross_language_hedging(self):
        sel={'schema':'reference_selection/1.1','role':'style','selected':[
          {'fragment_id':'RU','style_authority':'FULL','components':{'style':1}},
          {'fragment_id':'EN','style_authority':'STRUCTURE_ONLY','components':{'graph':1}},]}
        obj={'schema':'writing_object_decision/1.0','kind':'dissertation','language':'ru'}
        pol=build_policy(obj,'discussion',sel,target_language='ru')
        fmap={'RU':self._frag('RU','ru'),'EN':self._frag('EN','en')}
        fmap['EN']['style_features']['hedge_density_per_1000']=99
        art=build_style(sel,fmap,pol)
        self.assertEqual(2.0,art['instructions']['hedging_target'])
        self.assertEqual(['EN'],art['structure_only_source_fragment_ids'])

    def test_per_claim_evidence_selection_keeps_mapping(self):
        fr=[self._frag('A',style=False,evidence=True,excerpt='Fe4N нитрид обнаружен рентгеновской дифракцией'),self._frag('B',style=False,evidence=True,excerpt='микротвердость увеличилась в два раза')]
        claims=[{'id':'C-1','text':'Обнаружена фаза Fe4N.'},{'id':'C-2','text':'Микротвердость увеличилась в два раза.'}]
        out=select_for_claims(fr,claims,limit_per_claim=1)
        self.assertEqual('claim_evidence_selection/1.0',out['schema'])
        self.assertEqual({'C-1','C-2'},{x['claim_id'] for x in out['claims']})
        req=build_request({'schema':'writing_object_decision/1.0','kind':'dissertation','language':'ru'}, {'schema':'reference_selection/1.0','role':'style','selected':[]}, out, claims,'discussion')
        self.assertEqual({'C-1','C-2'},set(req['evidence_by_claim']))

    def test_draft_artifact_emits_typed_proposed_claim(self):
        req={'schema':'draft_request/1.0','request_id':'DR1','authorized_claims':[{'id':'C-1'}]}
        d=build_draft(req,[{'temp_id':'P1','text':'Наблюдение позволяет предположить причинную связь.','realizes_claims':['C-1'],'proposed_claims':[{'text':'Дефекты ускоряют диффузию азота.','claim_type':'CAUSAL_HYPOTHESIS','span':{'start':0,'end':33}}]}])
        self.assertFalse(d['ok']);self.assertTrue(d['requires_claim_registration'])
        pc=d['proposed_claims'][0]
        self.assertEqual('proposed_claim/1.0',pc['schema']);self.assertEqual('CAUSAL_HYPOTHESIS',pc['claim_type'])

    def test_verification_and_epistemic_states_are_separate(self):
        r=verify_claim({'text':'Прочность составляет 10 МПа.'},'Прочность составляет 10 МПа.')
        self.assertEqual('VERIFIED',r['verification_state']);self.assertEqual('SUPPORTED',r['evidence_verdict']);self.assertIn(r['epistemic_state'],{'ESTABLISHED','QUALIFIED'})
        t=verify_claim({'text':'Фаза Fe4N наблюдается после обработки.'},'В источнике упомянута фаза Fe4N.')
        self.assertEqual('UNCHECKED',t['verification_state']);self.assertEqual('UNKNOWN',t['epistemic_state']);self.assertEqual('OPEN',t['evidence_verdict'])
        curated=_merge_verification({'verdict':'SUPPORTED','confidence':.7},{'verdict':'OPEN','confidence':.3})
        self.assertEqual('VERIFIED',curated['verification_state']);self.assertEqual('SUPPORTED',curated['evidence_verdict'])

    def test_dom_claim_binding_is_authority_and_marker_is_projection(self):
        dom={'claims':[{'id':'C-1','text':'Прочность составляет 10 МПа.','evidence':[{'source_id':'S1'}],'verification':{'verdict':'SUPPORTED','confidence':.8}}], 'sources':[{'id':'S1','text':'Прочность составляет 10 МПа.'}], 'structure':{'chapters':[{'sections':[{'paragraphs':[{'id':'P1','text':'Прочность составляет 10 МПа.','claims':['C-1']}]}]}]}}
        ok=resolve_authority(dom,'Прочность составляет 10 МПа. [C-1] [S1]')
        self.assertEqual('PASS',ok['verdict']);self.assertEqual('DOM_PARAGRAPH_CLAIMS',ok['authority_source'])
        bad=resolve_authority(dom,'Прочность составляет 10 МПа. [C-2] [S1]')
        self.assertEqual('FAIL',bad['verdict']);self.assertEqual(['C-1'],bad['missing_markers'])

    def test_release_fails_on_authority_binding_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            dom={'product':{'id':'P','kind':'article'},'claims':[{'id':'C-1','text':'Прочность составляет 10 МПа.','evidence':[{'source_id':'S1'}]}],'sources':[{'id':'S1','text':'Прочность составляет 10 МПа.'}],'structure':{'chapters':[{'sections':[{'paragraphs':[{'id':'P1','text':'x','claims':['C-1']}]}]}]},'uncertainty':{}}
            dp=td/'d.yaml';tp=td/'t.md';dp.write_text(yaml.safe_dump(dom,allow_unicode=True,sort_keys=False),encoding='utf8');tp.write_text('Прочность составляет 10 МПа. [C-X] [S1]',encoding='utf8')
            out=evaluate_release(dp,tp)
            self.assertEqual('FAIL',out['gates']['traceability']['verdict'])
            self.assertEqual('FAIL',out['gates']['traceability']['detail']['authority_binding']['verdict'])

    def test_unchecked_is_not_epistemic_uncertainty(self):
        dom={'claims':[{'id':'C-1','text':'После обработки обнаружена фаза нитрида.','evidence':[{'source_id':'S1'}],'verification':{'verdict':'OPEN','evidence_verdict':'OPEN','verification_state':'UNCHECKED','epistemic_state':'UNKNOWN'}}],'sources':[{'id':'S1','text':'После обработки обнаружена фаза нитрида.'}],'uncertainty':{}}
        out=citation_trace.run('После обработки обнаружена фаза нитрида. [C-1] [S1]',dom,strict=True,fail_on='high')
        self.assertEqual([],out.get('masked_uncertainty') or [])

    def test_invalidation_separates_claim_state_from_evidence_verdict(self):
        dom={'claims':[{'id':'C-1','text':'x','evidence':[{'source_id':'S1'}],'verification':{'verdict':'SUPPORTED','evidence_verdict':'SUPPORTED','verification_state':'VERIFIED','epistemic_state':'ESTABLISHED'}}]}
        out=apply_invalidation(dom,{'claims_to_revalidate':['C-1'],'changed_sources':['S1']})
        c=out['dom']['claims'][0]
        self.assertEqual('PENDING_REVALIDATION',c['state'])
        self.assertEqual('SUPPORTED',c['verification']['evidence_verdict'])
        self.assertEqual('UNCHECKED',c['verification']['verification_state'])
        self.assertEqual('UNKNOWN',c['verification']['epistemic_state'])

    def test_frozen_contract_manifest(self):
        import json
        from pathlib import Path
        d=json.loads(Path('config/writer_v1_contracts.json').read_text(encoding='utf8'))
        self.assertEqual('FROZEN_FOR_RESEARCHER_INTEGRATION',d['status'])
        self.assertEqual('reference_selection/1.1',d['contracts']['reference_selection'])
        self.assertEqual('STRUCTURE_ONLY',d['style_authority']['cross_language'])
        self.assertIn('web.discovery',d['writer_forbidden_capabilities'])

if __name__=='__main__':unittest.main()
