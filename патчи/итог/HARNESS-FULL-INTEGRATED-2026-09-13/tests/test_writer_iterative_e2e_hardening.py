from __future__ import annotations
import tempfile, unittest
from pathlib import Path
import yaml
from scripts.researcher import verify_claims as vc
from scripts.writer.release.gate import evaluate_release

class IterativeE2EHardeningTests(unittest.TestCase):
    def test_material_grade_and_formula_are_not_numeric_measurements(self):
        self.assertEqual([], vc._extract_numbers('Сталь Р6М5 содержит γ′-Fe4N.'))
        self.assertEqual([], vc._extract_numbers('В фазе Fe4N наблюдается уширение линии.'))

    def test_readonly_effective_verification_preserves_curated_verdict(self):
        computed={'verdict':'OPEN','confidence':0.0,'numeric_comparison':None,'guard':'PASS','formula':None,'qualifier':None}
        existing={'verdict':'SUPPORTED','confidence':0.75,'note':'curated'}
        merged=vc._merge_verification(existing,computed)
        self.assertEqual('SUPPORTED',merged['verdict'])
        self.assertEqual(0.75,merged['confidence'])

    def test_release_checks_only_realized_marker_claims_when_markers_exist(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            dom={
              'product':{'id':'P','kind':'dissertation'},
              'structure':{'chapters':[{'id':'CH','sections':[{'id':'SEC','paragraphs':[]}]}]},
              'claims':[
                {'id':'C-001','text':'Прочность составляет 10 МПа.','evidence':[{'source_id':'S-001','span':'p.1'}]},
                {'id':'C-002','text':'Неподтвержденный будущий клайм.','evidence':[]},
              ],
              'sources':[{'id':'S-001','text':'Прочность составляет 10 МПа.'}], 'graphs':[], 'uncertainty':{}
            }
            dp=td/'dom.yaml'; tp=td/'text.md'
            dp.write_text(yaml.safe_dump(dom,allow_unicode=True,sort_keys=False),encoding='utf8')
            tp.write_text('Прочность составляет 10 МПа. [C-001] [S-001]',encoding='utf8')
            out=evaluate_release(dp,tp)
            self.assertEqual('PASS',out['gates']['evidence']['verdict'])
            self.assertEqual('PASS',out['gates']['semantic_roundtrip']['verdict'])
            self.assertNotIn('C-002',[x.get('claim_id') for x in out['gates']['evidence']['detail'].get('failures',[])])

if __name__=='__main__': unittest.main()
