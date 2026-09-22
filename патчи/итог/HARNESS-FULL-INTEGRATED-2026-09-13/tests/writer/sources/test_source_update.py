import tempfile,unittest
from pathlib import Path
from scripts.writer.sources.source_catalog import upsert
from scripts.writer.sources.update import update
class T(unittest.TestCase):
 def test_hash_change_invalidates_dependents(self):
  with tempfile.TemporaryDirectory() as td:
   db=str(Path(td)/'db.sqlite')
   upsert(db,{'source_id':'S1','sha256':'1'*64,'path':'a.pdf','media_type':'pdf'})
   dom={'sources':[{'id':'S1','sha256':'1'*64}],'claims':[{'id':'C1','text':'x','evidence':[{'source_id':'S1'}]}],'structure':{'chapters':[{'sections':[{'paragraphs':[{'id':'PAR-1','claims':['C1']}]}]}]}}
   r=update(db,dom,{'source_id':'S1','sha256':'2'*64,'path':'a.pdf','media_type':'pdf'})
   self.assertTrue(r['requires_revalidation']); self.assertEqual(r['invalidation']['claims_to_revalidate'],['C1']); self.assertEqual(r['invalidation']['paragraphs_to_repair'],['PAR-1'])
