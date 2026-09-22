import json,tempfile,unittest
from pathlib import Path
from scripts.writer.sources.evidence_span import build_span
from scripts.writer.sources.source_catalog import upsert,get
from scripts.writer.sources.search_memory import remember,recall

class T(unittest.TestCase):
 def test_evidence_span(self):
  ins={'ok':True,'schema':'document_inspection.v1','path':'x.md','sha256':'b'*64,'kind':'text','segments':[{'locator':'lines:1-2','text':'Alpha  nitrogen\n diffusion is accelerated.'}]}
  r=build_span(ins,'S1','nitrogen diffusion')
  self.assertTrue(r['ok']); self.assertEqual(r['source_sha256'],'b'*64); self.assertEqual(r['locator'],'lines:1-2')
 def test_catalog_and_memory(self):
  with tempfile.TemporaryDirectory() as td:
   db=str(Path(td)/'x.db')
   upsert(db,{'source_id':'S1','sha256':'c'*64,'path':'a.pdf','media_type':'pdf','document_kind':'dissertation'})
   self.assertEqual(get(db,'S1')['document_kind'],'dissertation')
   remember(db,'Fe4N nitriding','claim-evidence','C1','local-corpus',[{'source_id':'S1','locator':'pdf_page:7','score':1.0,'disposition':'useful'}])
   rr=recall(db,'  fe4n   NITRIDING ')
   self.assertEqual(rr['matches'][0]['source_id'],'S1')

class TestSourceVersions(unittest.TestCase):
 def test_source_version_history(self):
  from scripts.writer.sources.source_catalog import versions
  with tempfile.TemporaryDirectory() as td:
   db=str(Path(td)/'x.db')
   r1=upsert(db,{'source_id':'S1','sha256':'1'*64,'path':'a.md','media_type':'text'})
   r2=upsert(db,{'source_id':'S1','sha256':'2'*64,'path':'a.md','media_type':'text'})
   self.assertTrue(r2['content_changed'])
   self.assertEqual(len(versions(db,'S1')),2)

class TestArtifactLocator(unittest.TestCase):
 def test_xlsx_cell_locator(self):
  from scripts.writer.sources.evidence_span import build_locator
  ins={'ok':True,'schema':'document_inspection.v1','path':'x.xlsx','sha256':'d'*64,'kind':'xlsx','sheets':[{'sheet':'Data','cells':[{'cell':'B2','value':42}]}]}
  r=build_locator(ins,'S-XLSX','sheet:Data/cell:B2','measured value')
  self.assertTrue(r['ok']); self.assertEqual(r['mode'],'artifact_locator'); self.assertEqual(r['locator'],'sheet:Data/cell:B2')
