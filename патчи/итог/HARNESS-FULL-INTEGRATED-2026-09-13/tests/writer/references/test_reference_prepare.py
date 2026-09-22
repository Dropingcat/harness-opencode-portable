import importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
from scripts.writer.references.prepare import prepare

class RefPrepareTest(unittest.TestCase):
    def fixture(self,text):
        return {'ok':True,'schema':'document_inspection.v1','path':'x.pdf','sha256':'a'*64,'kind':'pdf','page_count':2,'segments':[{'locator':'pdf_page:1','text':text}]}
    def test_style_reference_cannot_be_evidence(self):
        r=prepare(self.fixture('Dissertation\n1 Introduction\nThis work may investigate nitriding [1].'),'style')
        self.assertTrue(r['permissions']['style']); self.assertFalse(r['permissions']['evidence'])
        self.assertTrue(r['policy']['style_reference_is_not_evidence'])
    def test_evidence_requires_locator(self):
        r=prepare(self.fixture('Abstract\nKeywords: nitriding\ndoi:10.1/x\nResults'),'evidence')
        self.assertTrue(r['permissions']['evidence']); self.assertTrue(r['policy']['evidence_requires_locator'])
