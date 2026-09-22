import unittest
from scripts.writer.provenance.dependency_graph import build,invalidate
class T(unittest.TestCase):
 def test_invalidation(self):
  dom={'sources':[{'source_id':'S1','sha256':'x'}],'claims':[{'claim_id':'C1','text':'a','evidence':[{'source_id':'S1'}]}],'paragraphs':[{'paragraph_id':'P1','claim_ids':['C1']}]}
  g=build(dom); r=invalidate(g,['S1'])
  self.assertEqual(r['claims_to_revalidate'],['C1']); self.assertEqual(r['paragraphs_to_repair'],['P1'])

class TestRealDomShape(unittest.TestCase):
 def test_nested_structure_and_id_aliases(self):
  dom={'sources':[{'id':'S1','sha256':'x'}],'claims':[{'id':'C1','text':'a','evidence':[{'source_id':'S1'}]}], 'structure':{'chapters':[{'sections':[{'paragraphs':[{'id':'PAR-1','claims':['C1']}]}]}]}}
  r=invalidate(build(dom),['S1'])
  self.assertEqual(r['claims_to_revalidate'],['C1']); self.assertEqual(r['paragraphs_to_repair'],['PAR-1'])
