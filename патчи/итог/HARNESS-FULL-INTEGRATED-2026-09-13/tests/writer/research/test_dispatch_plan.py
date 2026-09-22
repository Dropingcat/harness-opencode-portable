import unittest
from scripts.writer.research.dispatch_plan import dispatch
class T(unittest.TestCase):
 def test_evidence_stage_resolves_without_backend_names(self):
  plan={'schema':'validation_plan/1.0','entry_stage':'evidence-validation'}
  claim={'claim_id':'C1','text':'900 MPa'}
  r=dispatch(plan,claim)
  self.assertEqual(r['research_stage'],'evidence-validation'); self.assertFalse(r['backend_names_exposed_to_writer']); self.assertFalse(r['writer_may_execute_web_discovery'])
