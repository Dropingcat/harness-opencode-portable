import tempfile, unittest
from pathlib import Path
from scripts.capsules import corpus_fts
try:
 import fitz
except ImportError:
 fitz=None
class CorpusPdfTest(unittest.TestCase):
 @unittest.skipIf(fitz is None,'fitz unavailable')
 def test_pdf_page_locator_is_indexed(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'docs'; root.mkdir(); pdf=root/'a.pdf'; db=Path(td)/'x.sqlite'
   d=fitz.open(); p=d.new_page(); p.insert_text((72,72),'nitriding diffusion phase formation'); d.save(pdf); d.close()
   r=corpus_fts.index(db,root); self.assertEqual(r['added'],1); self.assertGreater(r['segments_written'],0)
   hits=corpus_fts.search(db,'nitriding',10); self.assertTrue(hits); self.assertEqual(hits[0]['locator'],'pdf_page:1')
