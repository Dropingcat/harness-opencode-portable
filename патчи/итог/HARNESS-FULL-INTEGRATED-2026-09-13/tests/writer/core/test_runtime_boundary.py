from __future__ import annotations
import shutil, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import yaml
from scripts.writer.infrastructure.registry_loader import Registries
from scripts.writer.review.rtt_compare import compare, compare_contract
from scripts.writer.core.factory_process import run_writer_cycle
ROOT = Path(__file__).resolve().parent
class RoundTripFixtureTests(unittest.TestCase):
    def test_four_handoff_fixtures(self):
        for path in sorted((ROOT/'fixtures'/'roundtrip').glob('*.yaml')):
            data=yaml.safe_load(path.read_text(encoding='utf-8'))
            result=compare_contract(data['contract_claim'],data['realization'])
            self.assertEqual(data['expected']['verdict'],result.verdict)
            self.assertEqual(data['expected']['reason_codes'],[r.value for r in result.reason_codes])
    def test_selected_golden_traps_have_stable_codes(self):
        fixtures=yaml.safe_load((ROOT/'fixtures'/'linguistics'/'golden_traps.yaml').read_text(encoding='utf-8'))['fixtures']
        for case in [c for c in fixtures if c.get('mutation')]:
            codes={r.value for r in compare(case['source'],case['mutation']).reason_codes}
            self.assertIn(case['expected_issue'],codes)
class RegistryBoundaryTests(unittest.TestCase):
    def test_all_six_runtime_registries_load(self):
        r=Registries(); self.assertTrue(r.lexicon and r.connectives and r.frames and r.patterns and r.actions and r.valency)
    def test_duplicate_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'assets'; shutil.copytree(Path('scripts/writer/assets/linguistic'),target)
            path=target/'connective_registry.yaml'; data=yaml.safe_load(path.read_text(encoding='utf-8')); data['entries'].append(dict(data['entries'][0])); path.write_text(yaml.safe_dump(data,allow_unicode=True),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'duplicate form'): Registries(str(target))
    def test_missing_required_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'assets'; shutil.copytree(Path('scripts/writer/assets/linguistic'),target)
            path=target/'valency_registry.yaml'; data=yaml.safe_load(path.read_text(encoding='utf-8')); del data['entries'][0]['case']; path.write_text(yaml.safe_dump(data,allow_unicode=True),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'missing'): Registries(str(target))
class BoundedRepairTests(unittest.TestCase):
    @patch('scripts.writer.core.factory_process.apply_constrained_repair')
    @patch('scripts.writer.core.factory_process.draftcheck')
    def test_no_progress_stops_without_retry_loop(self,draftcheck,repair):
        draftcheck.return_value={'verdict':'FAIL','defects':[{'claim_id':'C1','defect_type':'claim_omission','span':None}]}; repair.return_value={'text':'draft','applied':[],'skipped':[]}
        r=run_writer_cycle('draft',[],max_iterations=5); self.assertEqual('REJECTED',r['verdict']); self.assertEqual('no_progress',r['stopped_reason']); self.assertEqual(1,draftcheck.call_count)
    @patch('scripts.writer.core.factory_process.draftcheck')
    def test_iteration_limit_is_bounded(self,draftcheck):
        draftcheck.return_value={'verdict':'FAIL','defects':[]}; r=run_writer_cycle('draft',[],max_iterations=0); self.assertEqual('iteration_limit',r['stopped_reason']); self.assertEqual(1,draftcheck.call_count)
if __name__=='__main__': unittest.main()
