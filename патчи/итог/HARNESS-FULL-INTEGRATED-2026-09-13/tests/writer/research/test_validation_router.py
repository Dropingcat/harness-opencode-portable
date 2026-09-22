import unittest
from scripts.writer.research.validation_router import route
class ValidationRouterTest(unittest.TestCase):
    def test_missing_numeric_source_routes_research(self):
        r=route({'claim_id':'C1','text':'Твердость составляет 900 МПа.','evidence':[]})
        self.assertIn('deterministic_numeric',r['methods']); self.assertIn('evidence_acquisition',r['methods'])
        self.assertIn('corpus.search',r['tools']); self.assertFalse(r['writer_may_search_web'])
    def test_text_claim_with_locator_uses_entailment(self):
        r=route({'claim_id':'C2','text':'Азотирование изменяет фазовый состав.','evidence':[{'source_id':'S1','locator':'pdf_page:2'}]})
        self.assertIn('textual_entailment',r['methods']); self.assertNotIn('search.discovery',r['tools'])
