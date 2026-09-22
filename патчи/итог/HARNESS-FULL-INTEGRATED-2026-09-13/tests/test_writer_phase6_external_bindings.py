from __future__ import annotations
import importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PUBLIC_CLI='scripts/writer/cli.py'
AR=ROOT/'scripts/writer/migration/archive_readiness.py'
spec=importlib.util.spec_from_file_location('archive_policy',AR); ar=importlib.util.module_from_spec(spec); spec.loader.exec_module(ar)
FORBIDDEN=tuple(ar.LEGACY_NEEDLES) + ('scripts/writer/draft_loop.py','scripts/writer/citation_trace.py')
EXTERNAL_ROOTS=('agents','shared','skills/opencode-current/writer-core','skills/opencode-current/writer-review')
class Phase6ExternalBindingsTests(unittest.TestCase):
    def test_public_cli_exists(self): self.assertTrue((ROOT/PUBLIC_CLI).is_file())
    def test_external_writer_docs_do_not_call_superseded_entrypoints(self):
        offenders=[]
        for rel in EXTERNAL_ROOTS:
            base=ROOT/rel
            if not base.exists(): continue
            files=[base] if base.is_file() else list(base.rglob('*'))
            for p in files:
                if not p.is_file() or p.suffix not in {'.md','.json','.yaml','.yml','.py','.sh','.ps1'}: continue
                text=p.read_text(encoding='utf-8-sig',errors='replace')
                for needle in FORBIDDEN:
                    if needle in text: offenders.append(f'{p.relative_to(ROOT)} -> {needle}')
        self.assertEqual([],offenders)
    def test_provider_authority_uses_canonical_writer(self):
        data=json.loads((ROOT/'config/providers_authority.json').read_text(encoding='utf-8'))
        p=data['providers']['local.writer_core']; self.assertEqual(PUBLIC_CLI,p['entrypoint']); self.assertEqual(PUBLIC_CLI,p['installed_probe']['path'])
        probe=' '.join(p['live_probe']['argv']); self.assertIn('scripts.writer.core.factory_process',probe)
        for needle in ar.LEGACY_NEEDLES: self.assertNotIn(needle,probe)
    def test_generated_snapshot_matches_authority(self):
        data=json.loads((ROOT/'config/capability_runtime_snapshot.json').read_text(encoding='utf-8'))
        p=data['providers']['local.writer_core']; self.assertEqual(PUBLIC_CLI,p['entrypoint']); self.assertEqual(PUBLIC_CLI,p['installed_probe']['path'])
    def test_research_authority_remains_external(self):
        cli=(ROOT/PUBLIC_CLI).read_text(encoding='utf-8'); self.assertIn('scripts" / "researcher" / "verify_claims.py',cli); self.assertTrue((ROOT/'scripts/researcher/verify_claims.py').is_file())
    def test_sync_writer_is_recursive_and_preserves_relative_paths(self):
        path=ROOT/'scripts/sync_to_live.py'; spec=importlib.util.spec_from_file_location('sync_to_live_phase6',path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'src'; dst=Path(td)/'dst'; nested=src/'scripts/writer/core/deep'; nested.mkdir(parents=True); (nested/'probe.py').write_text('x=1\n',encoding='utf-8')
            pairs=mod.plan_copy(src,dst,'scripts/writer','*.py',recursive=True); self.assertEqual(1,len(pairs)); self.assertEqual(dst/'scripts/writer/core/deep/probe.py',pairs[0][1])
if __name__=='__main__': unittest.main()
