import json,tempfile,unittest
from pathlib import Path
from scripts.writer.references.prepare import prepare
from scripts.writer.references.fragments import build as build_fragments
from scripts.writer.references.select import select
from scripts.writer.references.graph_profile import digest

class T(unittest.TestCase):
 def inspection(self):
  return {'ok':True,'schema':'document_inspection.v1','path':'x.md','sha256':'a'*64,'kind':'text','segments':[{'locator':'lines:1-9','text':'Introduction\n\nNitriding improves surface properties [1]. This paragraph describes motivation and scope in a compact academic form.\n\nResults\n\nThe hardness increased because nitrogen-containing phases formed during treatment [2]. This result is discussed cautiously.'}]}
 def test_graph_digest_and_fragments(self):
  g={'graphs':{'P1':{'graphs':{'G4_argument':{'nodes':[{'type':'ClaimRef'}],'edges':[{'relation':'SUPPORTS'}]}}}}}
  b=prepare(self.inspection(),'style','R1',g)
  self.assertTrue(b['profile']['graph_digest']['available'])
  fs=build_fragments(self.inspection(),b,g)
  self.assertGreaterEqual(fs['count'],2)
  self.assertTrue(all(x['permissions']['style'] for x in fs['fragments']))
 def test_hard_role_filter(self):
  bs=prepare(self.inspection(),'style','RS'); be=prepare(self.inspection(),'evidence','RE')
  fs=build_fragments(self.inspection(),bs)['fragments']+build_fragments(self.inspection(),be)['fragments']
  r=select(fs,role='evidence',target_text='hardness nitrogen phases',section_role='results')
  self.assertTrue(r['selected']); self.assertTrue(all(x['reference_id']=='RE' for x in r['selected']))

class TestReferenceGap(unittest.TestCase):
 def test_no_reference_after_hard_filters_is_typed(self):
  fs=[{'fragment_id':'F1','reference_id':'R1','permissions':{'style':True},'document_kind':'dissertation','language':'ru','section_role':'body','style_features':{},'graph_digest':{},'excerpt':'x'}]
  r=select(fs,role='style',target_kind='article',language='en_or_de')
  self.assertEqual(r['status'],'DEGRADED')
  self.assertEqual(r['reason_code'],'NO_REFERENCE_AFTER_HARD_FILTERS')
