import tempfile,unittest
from pathlib import Path
from scripts.writer.sources.library_ingest import ingest
from scripts.writer.sources.library_search import search
class T(unittest.TestCase):
 def test_ingest_search_memory(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)/'lib';root.mkdir();(root/'a.md').write_text('Nitriding changes nitrogen diffusion and phase formation.',encoding='utf8')
   db=str(Path(td)/'lib.db');r=ingest(str(root),db);self.assertEqual(r['indexed'],1)
   s=search(db,'nitriding',purpose='test',claim_id='C1');self.assertTrue(s['hits']);self.assertTrue(s['hits'][0]['source_id']);self.assertIsNotNone(s['memory_record'])
