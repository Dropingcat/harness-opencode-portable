import json,tempfile,unittest
from pathlib import Path
from scripts.jobs.job_ctl import create,save
from scripts.writer.provenance.event_bridge import register_change_ledger
class T(unittest.TestCase):
 def test_register(self):
  with tempfile.TemporaryDirectory() as td:
   st=Path(td)/'job.json'; led=Path(td)/'ledger.json'
   save(create('J1',{'x':1},['draft']),st)
   led.write_text(json.dumps({'schema':'writer_change_ledger/1.0','old':{'sha256':'a'},'new':{'sha256':'b'},'touched_claims':['C1'],'touched_sources':['S1']}),encoding='utf8')
   r=register_change_ledger(str(st),str(led),'A1'); self.assertTrue(r['ok'])
   d=json.loads(st.read_text()); self.assertIn('A1',d['artifacts']); self.assertEqual(d['events'][-1]['type'],'WRITER_CHANGE_LEDGER')
