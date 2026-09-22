import unittest
from scripts.writer.provenance.change_ledger import diff
class LedgerTest(unittest.TestCase):
    def test_claim_change_is_explicit(self):
        a={'claims':[{'claim_id':'C1','text':'a','source_id':'S1'}],'sources':[{'source_id':'S1','x':1}]}
        b={'claims':[{'claim_id':'C1','text':'b','source_id':'S1'}],'sources':[{'source_id':'S1','x':1}]}
        d=diff(a,b); self.assertEqual(d['changes'][0]['change'],'modified'); self.assertIn('text',d['changes'][0]['fields'])
