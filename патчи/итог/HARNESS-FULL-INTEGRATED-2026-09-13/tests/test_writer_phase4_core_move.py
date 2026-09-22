from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CLI=ROOT/'scripts/writer/cli.py'
def run(*args): return subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,text=True,capture_output=True)
class Phase4Tests(unittest.TestCase):
    def test_public_cli_dispatches_canonical_core(self):
        text=CLI.read_text(encoding='utf-8')
        self.assertIn('scripts.writer.core.cli',text)
    def test_plan_topic_works_through_public_cli(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'plan.json'
            r=run(CLI,'plan','--topic','Фазовые превращения','--out',out)
            self.assertEqual(0,r.returncode,r.stderr+r.stdout)
            payload=json.loads(out.read_text(encoding='utf-8'))
            self.assertIsInstance(payload,dict)
    def test_new_runtime_has_no_sys_path_mutation_or_legacy_import(self):
        roots=[ROOT/'scripts/writer/core',ROOT/'scripts/writer/planning',ROOT/'scripts/writer/extraction',ROOT/'scripts/writer/analysis',ROOT/'scripts/writer/text',ROOT/'scripts/writer/io',ROOT/'scripts/writer/infrastructure',ROOT/'scripts/writer/adapters',ROOT/'scripts/writer/review']
        for base in roots:
            for p in base.rglob('*.py'):
                t=p.read_text(encoding='utf-8')
                self.assertNotIn('sys.path.insert',t,str(p)); self.assertNotIn('from writer_core.',t,str(p))
    def test_shared_paths_remain(self):
        for rel in ['scripts/researcher','scripts/router','scripts/code-factory','scripts/memory','scripts/orchestration','scripts/kanban','shared']:
            self.assertTrue((ROOT/rel).exists(),rel)
if __name__=='__main__': unittest.main()
