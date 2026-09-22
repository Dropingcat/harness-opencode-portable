import unittest
from scripts.writer.research.validation_router import route
class T(unittest.TestCase):
 def test_stages(self):
  self.assertEqual(route({'claim_id':'C','text':'x','evidence':[{'source_id':'S','locator':'pdf_page:2'}]})['entry_stage'],'evidence-validation')
  self.assertEqual(route({'claim_id':'C','text':'x','evidence':[{'source_id':'S'}]})['entry_stage'],'document-analysis')
  self.assertEqual(route({'claim_id':'C','text':'x','doi':'10.1/x'})['entry_stage'],'source-resolution')
  r=route({'claim_id':'C','text':'x'}); self.assertEqual(r['entry_stage'],'local-corpus'); self.assertFalse(r['writer_may_search_web'])
