"""Independent synthetic contract tests and durable, exact subprocess receipts."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CORE = Path(os.environ.get('WRITER_CORE_ROOT', ROOT / 'scripts/writer-core'))
WRITER = CORE.parent / 'writer'
REPORTS = ROOT / 'projects/writer-gates-restore/reports'
ARTIFACT = ROOT / 'projects/writer-gates-restore/artifacts/tester_writer_gates.json'
REPORTS.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(WRITER))
import citation_trace as trace


def fixture():
    proposition = 'Установлено, что синтетический образец имеет синий цвет'
    text = proposition + ' [C-A] [S-A].'
    dom = {'product': {'id': 'SYNTHETIC'},
           'claims': [{'id': 'C-A', 'text': proposition, 'kind': 'factual',
                       'evidence': [{'source_id': 'S-A', 'span': {'locator': 'p.7', 'quote': proposition}}],
                       'verification': {'verdict': 'SUPPORTED', 'confidence': .91,
                                        'verified_at': 'synthetic-time', 'provenance': {'curator': 'test-only'}}}],
           'sources': [{'id': 'S-A', 'ref': 'Synthetic source', 'text': proposition}],
           'uncertainty': {'C-A': {'level': 'established', 'note': 'Curated synthetic note'}},
           'structure': {'chapters': [{'id': 'CH-A', 'sections': [{'id': 'SEC-A', 'paragraphs': [
               {'id': 'P-A', 'claims': ['C-A'], 'text': '', 'curated': {'keep': True}},
               {'id': 'P-B', 'claims': [], 'text': 'Protected other paragraph'}]}]}]}}
    return text, dom


COMMANDS = []


def command(argv, label):
    env = dict(os.environ, WRITER_CORE_ROOT=str(CORE), PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    p = subprocess.run(list(map(str, argv)), cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    path = REPORTS / ('tester-recheck-' + os.environ.get('TESTER_SUITE', 'combined') + '-' + label + '.json')
    record = {'command': list(map(str, argv)), 'cwd': str(ROOT), 'exit_code': p.returncode,
              'stdout': p.stdout, 'stderr': p.stderr}
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    COMMANDS.append({'command': record['command'], 'exit_code': p.returncode, 'receipt': str(path.relative_to(ROOT))})
    return p


class Independent(unittest.TestCase):
    def assert_trace(self, text, dom, verdict, strict=False):
        before = copy.deepcopy(dom)
        report = trace.run(text, dom, strict=strict)
        self.assertEqual(before, dom, 'Trace mutated curated metadata')
        self.assertEqual(report['verdict'], verdict, report)
        self.assertTrue(report['scope'])
        self.assertTrue(report['limitations'])
        return report

    def test_grounded(self):
        self.assert_trace(*fixture(), 'PASS')

    def test_local_uncertainty(self):
        for verdict in ('OPEN', 'UNSUPPORTED', 'AMBIGUOUS', 'CONTRADICTED'):
            for level in ('established', 'assumed', 'disputed'):
                text, dom = fixture()
                dom['claims'][0]['verification']['verdict'] = verdict
                dom['uncertainty']['C-A']['level'] = level
                self.assert_trace(text, dom, 'FAIL')
                self.assert_trace('Possibly, ' + text, dom, 'PASS')
                self.assert_trace('Possibly, unrelated synthetic thought. ' + text, dom, 'FAIL')

    def test_curated_hedge_must_not_license_unhedged_prose(self):
        text, dom = fixture()
        dom['claims'][0]['text'] = 'Possibly, ' + dom['claims'][0]['text']
        dom['claims'][0]['verification']['verdict'] = 'OPEN'
        dom['uncertainty']['C-A']['level'] = 'assumed'
        for strict in (False, True):
            self.assert_trace(text, dom, 'FAIL', strict)
            self.assert_trace('Possibly, ' + text, dom, 'PASS', strict)

    def test_supported_curated_qualification_is_preserved(self):
        text, dom = fixture()
        dom['claims'][0]['text'] = 'Possibly, ' + dom['claims'][0]['text']
        for strict in (False, True):
            self.assert_trace(text, dom, 'FAIL', strict)
            self.assert_trace('Possibly, ' + text, dom, 'PASS', strict)

    def test_curated_qualification_real_apply(self):
        import yaml
        for verdict, level in (('OPEN', 'assumed'), ('SUPPORTED', 'established')):
            for suffix in ('json', 'yaml'):
                with self.subTest(verdict=verdict, suffix=suffix):
                    text, dom = fixture()
                    dom['claims'][0]['text'] = 'Possibly, ' + dom['claims'][0]['text']
                    dom['claims'][0]['verification']['verdict'] = verdict
                    dom['uncertainty']['C-A']['level'] = level
                    with tempfile.TemporaryDirectory(dir=REPORTS) as td:
                        td = Path(td); dp = td/('dom.'+suffix); draft = td/'draft.md'
                        dp.write_text(json.dumps(dom) if suffix == 'json' else yaml.safe_dump(dom, allow_unicode=True), encoding='utf-8')
                        original = dp.read_bytes()
                        args = [sys.executable, WRITER/'draft_loop.py', '--text', draft,
                                '--dom', dp, '--paragraph-id', 'P-A', '--apply']
                        for qualified in (False, True):
                            candidate = ('Possibly, ' if qualified else '') + text
                            draft.write_text(candidate, encoding='utf-8'); before_text = draft.read_bytes()
                            p = command(args, 'qualification-'+verdict+'-'+suffix+'-'+str(qualified))
                            r = json.loads(p.stdout)
                            self.assertEqual(draft.read_bytes(), before_text)
                            if qualified:
                                self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
                                self.assertEqual(r['verdict'], 'PASS', r)
                                self.assertTrue(r['applied'])
                                expected = copy.deepcopy(dom)
                                expected['structure']['chapters'][0]['sections'][0]['paragraphs'][0]['text'] = candidate
                                self.assertEqual(trace.load_dom(dp), expected)
                            else:
                                self.assertNotEqual(p.returncode, 0, p.stdout+p.stderr)
                                self.assertEqual(r['verdict'], 'FAIL', r)
                                self.assertFalse(r.get('applied', False))
                                self.assertEqual(dp.read_bytes(), original)

    def test_malformed_file_cli(self):
        with tempfile.TemporaryDirectory(dir=REPORTS) as td:
            td = Path(td)
            draft = td/'draft.md'; draft.write_text(fixture()[0], encoding='utf-8')
            for n, (suffix, raw) in enumerate((('.json', '{broken'), ('.yaml', 'claims: [\n'),
                    ('.json', '{"claims": [], "claims": []}'), ('.yaml', 'claims: []\nclaims: []\n'))):
                dp = td/('bad'+suffix); dp.write_text(raw, encoding='utf-8')
                p = command([sys.executable, WRITER/'citation_trace.py', '--text', draft, '--dom', dp], 'malformed-'+str(n))
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(json.loads(p.stdout)['verdict'], 'FAIL')

    def test_draft_dry_apply_and_provenance(self):
        import yaml
        for suffix in ('json', 'yaml'):
            with tempfile.TemporaryDirectory(dir=REPORTS) as td:
                text, dom = fixture(); td = Path(td)
                dp = td/('dom.'+suffix); draft = td/'draft.md'
                dp.write_text(json.dumps(dom) if suffix == 'json' else yaml.safe_dump(dom, allow_unicode=True), encoding='utf-8')
                draft.write_text(text, encoding='utf-8')
                before = dp.read_bytes(); text_before = draft.read_bytes()
                args = [sys.executable, WRITER/'draft_loop.py', '--text', draft, '--dom', dp, '--paragraph-id', 'P-A']
                p = command(args, 'dry-'+suffix)
                self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
                self.assertFalse(json.loads(p.stdout)['applied'])
                self.assertEqual(before, dp.read_bytes())
                p = command(args+['--apply'], 'apply-'+suffix)
                self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
                self.assertTrue(json.loads(p.stdout)['applied'])
                expected = copy.deepcopy(dom)
                expected['structure']['chapters'][0]['sections'][0]['paragraphs'][0]['text'] = text
                self.assertEqual(trace.load_dom(dp), expected)
                self.assertEqual(draft.read_bytes(), text_before)
                before = dp.read_bytes()
                for label, candidate, pid in (('orphan', text+' A new mechanism exists.', 'P-A'),
                                               ('wrong-selection', text, 'P-B'),
                                               ('unknown-selection', text, 'P-NO'),
                                               ('multiple-blocks', text+'\n\n'+text, 'P-A')):
                    draft.write_text(candidate, encoding='utf-8'); text_before = draft.read_bytes()
                    bad_args = args[:-1]+[pid, '--apply']
                    p = command(bad_args, label+'-'+suffix)
                    self.assertNotEqual(p.returncode, 0, p.stdout+p.stderr)
                    self.assertEqual(json.loads(p.stdout)['verdict'], 'FAIL')
                    self.assertEqual(dp.read_bytes(), before)
                    self.assertEqual(draft.read_bytes(), text_before)

    def test_actual_wc_cli_dom(self):
        with tempfile.TemporaryDirectory(dir=REPORTS) as td:
            text, dom = fixture(); td = Path(td)
            draft = td/'draft.md'; dp = td/'dom.json'; cp = td/'contract.json'
            draft.write_text(text, encoding='utf-8')
            cp.write_text(json.dumps({'claims': [{'claim_id': 'C-A', 'proposition': dom['claims'][0]['text']}]}), encoding='utf-8')
            for good in (True, False):
                if not good: dom['claims'][0]['evidence'] = []
                dp.write_text(json.dumps(dom), encoding='utf-8'); out = td/('good.json' if good else 'bad.json')
                p = command([sys.executable, CORE/'wc_cli.py', 'review', '--draft', draft, '--contract', cp,
                             '--dom', dp, '--max-iterations', '0', '--out', out], 'wc-good' if good else 'wc-bad')
                self.assertTrue(out.exists(), p.stdout+p.stderr)
                r = json.loads(out.read_text(encoding='utf-8'))
                (REPORTS / ('tester-recheck-' + os.environ.get('TESTER_SUITE', 'combined') + ('-wc-good-report.json' if good else '-wc-bad-report.json'))).write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
                expected = 'PASS' if good else 'FAIL'
                self.assertEqual(r['trace_checks_final']['verdict'], expected, r)
                self.assertEqual(r['final_verdict'], expected, r)
                self.assertEqual(json.loads(p.stdout)['final_verdict'], expected)
                if good:
                    self.assertEqual(p.returncode, 0, p.stdout+p.stderr)
                else:
                    self.assertNotEqual(p.returncode, 0, p.stdout+p.stderr)


def make_case(name):
    def test(self):
        text, dom = fixture(); c = dom['claims'][0]; v = c['verification']
        if name == 'unknown_claim': text = text.replace('C-A', 'C-NO')
        elif name == 'unknown_citation': text = text.replace('S-A', 'S-NO')
        elif name == 'unknown_evidence_source': c['evidence'][0]['source_id'] = 'S-NO'
        elif name == 'unrelated_source':
            dom['sources'].append({'id': 'S-B', 'ref': 'Unrelated synthetic source'})
            text = text.replace('S-A', 'S-B')
        elif name == 'missing_locator': del c['evidence'][0]['span']['locator']
        elif name == 'quote_conflict': c['evidence'][0]['span']['quote'] = 'Not present in source'
        elif name == 'orphan_sentence': text += ' A new mechanism exists.'
        elif name == 'orphan_marker_laundering': text += ' A new mechanism exists [C-A] [S-A].'
        elif name == 'duplicate_id': dom['sources'][0]['id'] = 'C-A'
        elif name == 'duplicate_paragraph': dom['structure']['chapters'][0]['sections'][0]['paragraphs'][1]['id'] = 'P-A'
        elif name == 'bad_container': dom['claims'] = {'C-A': c}
        elif name == 'bad_evidence': c['evidence'] = [None]
        elif name == 'bad_verdict': v['verdict'] = 'TRUE'
        elif name == 'bad_confidence': v['confidence'] = float('nan')
        elif name == 'bad_uncertainty': dom['uncertainty']['C-A']['level'] = 'certain'
        elif name == 'unknown_section': text = text[:-1]+' [§SEC-NO].'
        elif name == 'guard_conflict': v['guard'] = 'FAIL'
        elif name == 'formula_conflict': v['formula'] = {'constant_check': 'formula_conflict'}
        elif name.startswith('numeric_'):
            c['text'] += ' 12 mm'; text = c['text']+' [C-A] [S-A].'
            if name != 'numeric_missing': v['numeric_comparison'] = {'status': 'MATCH' if name == 'numeric_good' else 'MISMATCH'}
        self.assert_trace(text, dom, 'PASS' if name == 'numeric_good' else 'FAIL')
    return test


for _name in ('unknown_claim unknown_citation unknown_evidence_source unrelated_source missing_locator quote_conflict orphan_sentence orphan_marker_laundering duplicate_id duplicate_paragraph bad_container bad_evidence bad_verdict bad_confidence bad_uncertainty unknown_section guard_conflict formula_conflict numeric_missing numeric_conflict numeric_good').split():
    setattr(Independent, 'test_'+_name, make_case(_name))


def load_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return unittest.defaultTestLoader.loadTestsFromModule(module)


class RecordedResult(unittest.TextTestResult):
    records = []
    def addSuccess(self, test):
        super().addSuccess(test); self.records.append({'name': test.id(), 'result': 'PASS'})
    def addFailure(self, test, err):
        super().addFailure(test, err); self.records.append({'name': test.id(), 'result': 'FAIL', 'detail': self._exc_info_to_string(err, test)})
    def addError(self, test, err):
        super().addError(test, err); self.records.append({'name': test.id(), 'result': 'FAIL', 'detail': self._exc_info_to_string(err, test)})
    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.records.append({'name': test.id(), 'result': 'NOT_TESTED', 'detail': reason})


if __name__ == '__main__':
    if '--suite' not in sys.argv:
        # Preserve prior fixed-path results before regenerating the canonical report.
        import shutil
        history = REPORTS / 'tester-recheck-prior-history'
        history.mkdir(exist_ok=True)
        if ARTIFACT.exists() and not (history / ARTIFACT.name).exists():
            shutil.copy2(ARTIFACT, history / ARTIFACT.name)
        for old in REPORTS.glob('tester-*.json'):
            if not old.name.startswith('tester-recheck-') and not (history/old.name).exists():
                shutil.copy2(old, history/old.name)
        suite_exits = {}
        for label in ('focused', 'combined', 'standalone-graphs'):
            os.environ['TESTER_SUITE'] = label
            receipt_dir = REPORTS / ('tester-recheck-worker-' + label)
            receipt_dir.mkdir(exist_ok=True)
            os.environ['WRITER_REWORK_RECEIPTS'] = str(receipt_dir)
            p = command([sys.executable, Path(__file__), '--suite', label], 'suite')
            suite_exits[label] = p.returncode
            print(label + ': ' + str(p.returncode)); print(p.stdout); print(p.stderr, file=sys.stderr)
        report = json.loads(ARTIFACT.read_text(encoding='utf-8'))
        report['commands'] += COMMANDS
        report['suite_exit_codes'] = suite_exits
        report['notes'].append('Standalone original graph failures predate restoration and are out of scope; preserved separately, never counted as PASS. Focused and combined results are separate receipts.')
        if suite_exits['focused'] or suite_exits['combined']:
            report['result'] = 'FAIL'
        ARTIFACT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        raise SystemExit(0 if report['result'] == 'PASS' else 1)
    label = sys.argv[sys.argv.index('--suite')+1]
    suite = unittest.TestSuite()
    if label != 'standalone-graphs':
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(Independent))
        suite.addTests(load_file(WRITER/'tests/test_writer_gates.py', 'worker_tests'))
    if label != 'focused':
        suite.addTests(load_file(CORE/'tests/test_citations_graphs.py', 'existing_citation_tests'))
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(suite)
    records = result.records
    failed = sum(r['result'] == 'FAIL' for r in records)
    passed = sum(r['result'] == 'PASS' for r in records)
    report = {'module': 'writer_gates', 'written_by': 'tester', 'result': 'FAIL' if failed or result.skipped else 'PASS',
              'passed': passed, 'failed': failed, 'coverage': 0, 'tests': records,
              'problems': [r for r in records if r['result'] != 'PASS'], 'commands': COMMANDS,
              'notes': ['Coverage is unmeasured; numeric 0 is schema-required placeholder, not measured line coverage.',
                        'Only synthetic fixtures; no network, providers, installation, curated implementation edits or scientific computations.',
                        'Independent tests plus worker suite and existing narrowly relevant writer-core citations/graphs suite.']}
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    (REPORTS / ('tester-recheck-'+label+'-results.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if label == 'combined':
        ARTIFACT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    raise SystemExit(0 if report['result'] == 'PASS' else 1)
