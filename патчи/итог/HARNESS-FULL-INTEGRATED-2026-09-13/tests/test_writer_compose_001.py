import copy, json, sqlite3, tempfile, unittest
from pathlib import Path
from scripts.writer.references.language import detect
from scripts.writer.references.fragment_graph import build as graph_build
from scripts.writer.library.document_card import build as card_build
from scripts.writer.composition.writing_policy import build as policy_build
from scripts.writer.composition.style_instruction import build as style_build
from scripts.writer.drafting.artifact import build as draft_build
from scripts.writer.drafting.dom_patch import build_patch, apply as patch_apply
from scripts.writer.drafting.repair import build as repair_build
from scripts.writer.provenance.state_policy import apply_invalidation
from scripts.writer.sources.source_catalog import upsert
from scripts.writer.references.select import select as reference_select
from scripts.writer.provenance.change_ledger import build as ledger_build

class Compose001(unittest.TestCase):
    def test_language_en_de_ru(self):
        self.assertEqual(detect('The results show that nitriding increases hardness in the diffusion zone.')['language'],'en')
        self.assertEqual(detect('Die Ergebnisse zeigen, dass die Nitrierung der Werkstoffe untersucht wurde.')['language'],'de')
        self.assertEqual(detect('Результаты исследования показывают влияние азотирования на структуру материала.')['language'],'ru')

    def test_fragment_graph_has_source_locator(self):
        f={'fragment_id':'RF-1','source_id':'S1','source_sha256':'a'*64,'locator':'pdf_page:3','span':{'start':0,'end':110},'normalized_text_hash':'b'*64,'excerpt':'The measured hardness was 900 MPa. Therefore, the treatment increased the measured hardness.'}
        out=graph_build(f)
        self.assertTrue(out['fingerprint']['available'])
        nodes=[n for g in out['graphs']['graphs'].values() for n in g.get('nodes',[])]
        self.assertTrue(nodes)
        self.assertTrue(all((n.get('props') or {}).get('source_span',{}).get('locator')=='pdf_page:3' for n in nodes))

    def test_document_card(self):
        ins={'ok':True,'schema':'document_inspection.v1','sha256':'a'*64,'kind':'pdf','size_bytes':10,'page_count':2,'warnings':[]}
        src={'source_id':'S1','title':'T','language':'en','document_kind':'dissertation','media_type':'pdf'}
        c=card_build(inspection=ins,source_record=src,fragment_set={'schema':'reference_fragment_set/1.0','count':2},derived={'fragment_index_artifact':'ART-1'})
        self.assertEqual(c['profile_state'],'enriched');self.assertEqual(c['fragments']['count'],2)

    def _selection(self):
        return {'schema':'reference_selection/1.0','role':'style','selected':[{'fragment_id':'F1','components':{'style':.8}}]}
    def test_policy_and_style_instruction(self):
        obj={'schema':'writing_object_decision/1.0','kind':'dissertation','language':'ru'}
        pol=policy_build(obj,'discussion',self._selection(),target_language='ru')
        self.assertIn('UNQUALIFIED_CAUSALITY',pol['forbidden_claim_classes'])
        fr={'F1':{'fragment_id':'F1','section_role':'discussion','style_features':{'words':120,'citation_density_per_1000':8,'hedge_density_per_1000':2,'causal_density_per_1000':3},'graph_digest':{'edge_relations':{'SUPPORTS':2,'INTERPRETS':1}}}}
        si=style_build(self._selection(),fr,pol)
        self.assertEqual(si['instructions']['paragraph_words_target'],120.0)
        self.assertIn('do not import reference claims as facts',si['instructions']['prohibitions'])

    def test_draft_artifact_rejects_unauthorized_claim(self):
        req={'schema':'draft_request/1.0','request_id':'DR1','authorized_claims':[{'id':'C-1'}]}
        d=draft_build(req,[{'text':'x','realizes_claims':['C-1','C-X']}])
        self.assertFalse(d['ok']);self.assertEqual(d['unauthorized_claim_ids'],['C-X'])

    def _dom(self):
        return {'claims':[{'id':'C-1','text':'x','evidence':['S1'],'verification':{'verdict':'SUPPORTED'}},{'id':'C-2','text':'y','evidence':['S1','S2'],'verification':{'verdict':'SUPPORTED'}}], 'sources':[{'id':'S1','sha256':'a'*64},{'id':'S2','sha256':'b'*64}], 'structure':{'chapters':[{'sections':[{'paragraphs':[{'id':'PAR-1','text':'old','claims':['C-1']},{'id':'PAR-2','text':'keep','claims':['C-2']}]}]}]}}
    def test_dom_patch_and_conflict(self):
        dom=self._dom();draft={'paragraphs':[{'target_paragraph_id':'PAR-1','text':'new','realizes_claims':['C-1'],'evidence_refs':['E1']}]} ;patch=build_patch(dom,draft);res=patch_apply(dom,patch);self.assertTrue(res['ok']);self.assertEqual(res['dom']['structure']['chapters'][0]['sections'][0]['paragraphs'][0]['text'],'new')
        changed=copy.deepcopy(dom);changed['structure']['chapters'][0]['sections'][0]['paragraphs'][0]['text']='other';self.assertFalse(patch_apply(changed,patch)['ok'])

    def test_invalidation_state_and_repair(self):
        dom=self._dom();inv={'changed_sources':['S1'],'claims_to_revalidate':['C-1','C-2'],'paragraphs_to_repair':['PAR-1','PAR-2']}
        st=apply_invalidation(dom,inv);tr={x['claim_id']:x['to'] for x in st['transitions']}
        self.assertEqual(tr['C-1'],'PENDING_REVALIDATION');self.assertEqual(tr['C-2'],'SUPPORTED_WITH_STALE_EVIDENCE')
        rr=repair_build(st['dom'],inv);self.assertEqual(len(rr['paragraphs']),2);self.assertTrue(rr['constraints']['repair_only_affected_paragraphs'])


    def test_evidence_selection_crosses_genre_and_language(self):
        fr=[{'fragment_id':'F','reference_id':'R','document_kind':'article','language':'en','section_role':'results','permissions':{'evidence':True},'style_features':{},'graph_digest':{},'excerpt':'plastic deformation nitriding nitride phase','locator':'pdf_page:1'}]
        r=reference_select(fr,role='evidence',target_kind='dissertation',language='ru',section_role='discussion',target_text='plastic deformation nitriding nitride phase',limit=2)
        self.assertEqual(r['status'],'READY');self.assertEqual(r['selected'][0]['reference_id'],'R')

    def test_change_ledger_sees_nested_dom_paragraph(self):
        old=self._dom();new=copy.deepcopy(old);new['structure']['chapters'][0]['sections'][0]['paragraphs'][0]['text']='changed'
        led=ledger_build(old,new);self.assertIn('PAR-1',led['touched_paragraphs']);self.assertIn('C-1',led['touched_claims'])

    def test_source_catalog_byte_only_vs_semantic(self):
        with tempfile.TemporaryDirectory() as td:
            db=str(Path(td)/'c.db')
            a=upsert(db,{'source_id':'S','sha256':'a'*64,'metadata':{'normalized_text_hash':'n1'}});self.assertFalse(a['semantic_changed'])
            b=upsert(db,{'source_id':'S','sha256':'b'*64,'metadata':{'normalized_text_hash':'n1'}});self.assertEqual(b['change_class'],'BYTE_ONLY');self.assertFalse(b['semantic_changed'])
            c=upsert(db,{'source_id':'S','sha256':'c'*64,'metadata':{'normalized_text_hash':'n2'}});self.assertEqual(c['change_class'],'SEMANTIC');self.assertTrue(c['semantic_changed'])

if __name__=='__main__':unittest.main()
