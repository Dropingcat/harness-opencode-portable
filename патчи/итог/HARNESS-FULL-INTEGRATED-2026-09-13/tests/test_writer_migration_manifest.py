from __future__ import annotations
import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'config/writer_migration_manifest.json'
ALLOWED={'ACTIVE_MOVE','ACTIVE_ADAPTER','KEEP_SHARED','ARCHIVE_AFTER_MIGRATION','GENERATED_CLEANUP','DEFERRED'}
def under(path:Path,parent:Path)->bool:
    try: path.relative_to(parent); return True
    except ValueError: return False
def rel(v):
    p=Path(v); assert not p.is_absolute() and '..' not in p.parts, v; return p
class ManifestTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.m=json.loads(P.read_text(encoding='utf-8')); cls.groups=cls.m['groups']; cls.phases=sorted(cls.m['phases'],key=lambda x:x['order'])
 def test_root_contract(self):
  self.assertEqual('writer-migration-manifest/1.1',self.m['schema']); self.assertEqual(2,self.m['version']); self.assertTrue(self.m['fail_closed']); self.assertEqual(ALLOWED,set(self.m['classifications']))
 def test_phase_order_and_gates(self):
  self.assertEqual([p['id'] for p in self.phases],self.m['phase_order']); self.assertEqual(list(range(1,len(self.phases)+1)),[p['order'] for p in self.phases])
  for p in self.phases:
   self.assertTrue(p['gates']['reviewer'],p['id']); self.assertTrue(p['gates']['tester'],p['id']); self.assertTrue(p['acceptance'],p['id']); self.assertTrue(p['rollback'],p['id'])
 def test_unique_group_ids_and_enums(self):
  ids=[]
  for g in self.groups:
   ids.append(g['id']); self.assertIn(g['classification'],ALLOWED); self.assertIn(g['phase'],self.m['phase_order']); self.assertTrue(g['preconditions']); self.assertTrue(g['acceptance']); self.assertTrue(g['rollback']); self.assertIsInstance(g['reference_updates'],list)
  self.assertEqual(len(ids),len(set(ids)))
 def test_sources_are_lists_and_exist_until_archive(self):
  archive_root=ROOT/self.m['legacy_root']
  for g in self.groups:
   self.assertIsInstance(g['source'],list,g['id'])
   for s in g['source']:
    src=ROOT/rel(s)
    if src.exists() or g.get('optional') or g.get('generated'): continue
    if g.get('source_state')=='archived':
      target=ROOT/rel(g.get('archive_target') or g.get('target'))
      self.assertTrue(target.exists(),f"{g['id']} archived source missing archive target")
    elif g['classification']=='ARCHIVE_AFTER_MIGRATION':
      target=ROOT/rel(g['target'])
      self.assertTrue(target.exists(),f"{g['id']} source absent without archive target")
    else: self.fail(f"{g['id']} missing source {s}")
 def test_target_containment(self):
  canonical=Path(self.m['canonical_root']); legacy=Path(self.m['legacy_root'])
  for g in self.groups:
   if g.get('target') is None:
    self.assertEqual('GENERATED_CLEANUP',g['classification']); continue
   target=rel(g['target']); c=g['classification']
   if c in {'ACTIVE_MOVE','ACTIVE_ADAPTER'} and not g.get('external_target'): self.assertTrue(under(target,canonical) or target==canonical,g['id'])
   if c=='ARCHIVE_AFTER_MIGRATION': self.assertTrue(under(target,legacy),g['id'])
   if c=='KEEP_SHARED': self.assertFalse(under(target,legacy),g['id'])
 def test_archive_contract_requires_zero_refs_provenance_rollback(self):
  for g in self.groups:
   if g['classification']!='ARCHIVE_AFTER_MIGRATION': continue
   words=' '.join(g['preconditions']+g['acceptance']+g['rollback']).lower()
   for term in ('zero runtime/config/agent/test references','provenance'): self.assertIn(term,words,g['id'])
   self.assertTrue(any(k in words for k in ('rollback','revert','restore')),g['id'])
 def test_experiment_has_baseline_metrics_stop_rule(self):
  ex=self.m['experiments']; self.assertEqual(1,len(ex)); e=ex[0]; self.assertTrue(e['baseline']); self.assertGreaterEqual(len(e['metrics']),3); self.assertTrue(e['stop_rule'])
 def test_handoff_archive_is_exact_versioned_unit(self):
  g=next(g for g in self.groups if g['id']=='writer-handoff-unit'); self.assertEqual('ARCHIVE_AFTER_MIGRATION',g['classification']); self.assertTrue(g['target'].endswith('v0.3.0'))
if __name__=='__main__': unittest.main()
