from __future__ import annotations
import importlib.util, json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'scripts/writer/migration/archive_readiness.py'
spec=importlib.util.spec_from_file_location('ar',P); ar=importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
class ArchiveReadinessTests(unittest.TestCase):
    def test_external_refs_are_clean(self): self.assertEqual([],ar.scan(ar.LEGACY_NEEDLES)); self.assertEqual([],ar.scan(ar.HANDOFF_NEEDLES))
    def test_handoff_marker_is_valid(self):
        r=ar.evaluate(); self.assertEqual('PASS',r['handoff_integration'])
    def test_archive_readiness_is_machine_readable(self):
        r=ar.evaluate(); self.assertEqual('writer-archive-readiness/1.1',r['schema']); self.assertIn(r['archive_status'],{'READY','ARCHIVED','BLOCKED'})
class ArchiveInventoryTests(unittest.TestCase):
    def test_archived_units_match_pre_move_inventory(self):
        import hashlib
        inv=json.loads((ROOT/'scripts/writer/migration/archive_inventory.json').read_text(encoding='utf-8'))
        for unit in inv['units']:
            base=ROOT/unit['archive_target']
            self.assertTrue(base.is_dir(),unit['id'])
            agg=hashlib.sha256()
            for item in sorted(unit['files'],key=lambda x:x['path']):
                rel=item['path'].split('/',2)[-1] if item['path'].startswith('scripts/') else item['path']
                # strip the original unit root exactly, not a generic component count
                src_prefix=unit['source'].rstrip('/')+'/'
                rel=item['path'][len(src_prefix):] if item['path'].startswith(src_prefix) else item['path']
                p=base/rel
                self.assertTrue(p.is_file(),f"{unit['id']} missing {rel}")
                digest=hashlib.sha256(p.read_bytes()).hexdigest()
                self.assertEqual(item['sha256'],digest,f"{unit['id']} {rel}")
                agg.update(item['path'].encode()); agg.update(b'\0'); agg.update(digest.encode()); agg.update(b'\n')
            self.assertEqual(unit['tree_sha256'],agg.hexdigest(),unit['id'])

if __name__=='__main__': unittest.main()
