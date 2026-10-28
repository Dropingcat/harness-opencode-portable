"""Synthetic gates; WRITER_CORE_ROOT may select another installed source tree."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


def recorded_subprocess(argv, label, **kwargs):
    result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', **kwargs)
    if os.environ.get('WRITER_REWORK_RECEIPTS'):
        path = Path(os.environ['WRITER_REWORK_RECEIPTS']) / ('worker-rework-' + label + '.json')
        path.write_text(json.dumps({'command': list(map(str, argv)), 'cwd': os.getcwd(),
                                   'stdout': result.stdout, 'stderr': result.stderr,
                                   'exit_code': result.returncode}, ensure_ascii=False, indent=2), encoding='utf-8')
    return result

CORE = Path(os.environ.get('WRITER_CORE_ROOT', Path(__file__).resolve().parents[2] / 'writer-core'))
WRITER = CORE.parent / 'writer'
sys.path.insert(0, str(WRITER))


def fixture():
    text = 'The synthetic sample is blue [C-001] [S-001].'
    return text, {
        'claims': [{'id': 'C-001', 'text': 'The synthetic sample is blue',
                    'kind': 'factual', 'evidence': [{'source_id': 'S-001',
                    'span': 'p.1: «The synthetic sample is blue»'}],
                    'verification': {'verdict': 'SUPPORTED', 'confidence': .8,
                                     'provenance': {'curator': 'synthetic'}}}],
        'sources': [{'id': 'S-001', 'ref': 'Synthetic fixture',
                     'text': 'The synthetic sample is blue'}],
        'uncertainty': {'C-001': {'level': 'established', 'note': ''}},
        'structure': {'chapters': [{'id': 'CH-01', 'sections': [{'id': 'SEC-01',
            'paragraphs': [{'id': 'PAR-01', 'claims': ['C-001'], 'text': ''},
                           {'id': 'PAR-02', 'claims': [], 'text': ''}]}]}]}}


class Gates(unittest.TestCase):
    def trace(self, text, dom):
        from citation_trace import run
        before = copy.deepcopy(dom)
        result = run(text, dom)
        self.assertEqual(before, dom)
        return result

    def test_positive(self):
        self.assertEqual(self.trace(*fixture())['verdict'], 'PASS')

    def test_negative_matrix(self):
        for change in ('claim', 'source', 'citation', 'mismatch', 'locator', 'orphan',
                       'verdict', 'confidence', 'uncertainty', 'evidence', 'duplicate',
                       'numeric', 'numeric_conflict', 'formula', 'guard', 'quote', 'section'):
            with self.subTest(change=change):
                text, dom = fixture()
                c = dom['claims'][0]
                if change == 'claim': text = text.replace('C-001', 'C-999')
                if change == 'source': dom['sources'] = []
                if change == 'citation': text = text.replace('S-001', 'S-999')
                if change == 'mismatch':
                    dom['sources'].append({'id': 'S-002', 'ref': 'unrelated'})
                    text = text.replace('S-001', 'S-002')
                if change == 'locator': c['evidence'][0]['span'] = 'The synthetic sample is blue'
                if change == 'orphan': text += ' This proves a new cause.'
                if change == 'verdict': c['verification']['verdict'] = 'OK'
                if change == 'confidence': c['verification']['confidence'] = True
                if change == 'uncertainty': dom['uncertainty']['C-001']['level'] = 'magic'
                if change == 'evidence': c['evidence'] = 'bad'
                if change == 'duplicate': dom['claims'].append(copy.deepcopy(c))
                if change in ('numeric', 'numeric_conflict'):
                    c['text'] = c['text'].replace('blue', '12 mm wide')
                    text = text.replace('blue', '12 mm wide')
                    if change == 'numeric_conflict': c['verification']['numeric_comparison'] = {'status': 'MISMATCH'}
                if change == 'formula': c['verification']['formula'] = {'name': 'synthetic', 'constant_check': 'formula_conflict'}
                if change == 'guard': c['verification']['guard'] = 'FAIL'
                if change == 'quote': c['evidence'][0]['span'] = 'p.1: «invented quote»'
                if change == 'section': text += ' [§SEC-99]'
                self.assertEqual(self.trace(text, dom)['verdict'], 'FAIL')

    def test_uncertainty_is_local(self):
        for verdict in ('OPEN', 'UNSUPPORTED', 'AMBIGUOUS', 'CONTRADICTED'):
            text, dom = fixture()
            dom['claims'][0]['verification']['verdict'] = verdict
            self.assertEqual(self.trace(text, dom)['verdict'], 'FAIL')
            self.assertEqual(self.trace('Possibly, ' + text, dom)['verdict'], 'PASS')
            self.assertEqual(self.trace('Possibly another sample exists. ' + text, dom)['verdict'], 'FAIL')

    def test_curated_qualifier_requires_draft_qualification(self):
        from citation_trace import run
        for uncertain in (True, False):
            text, dom = fixture()
            dom['claims'][0]['text'] = 'Possibly, ' + dom['claims'][0]['text']
            dom['sources'][0]['text'] = dom['claims'][0]['text']
            dom['claims'][0]['evidence'][0]['span'] = 'p.1: «' + dom['claims'][0]['text'] + '»'
            if uncertain:
                dom['claims'][0]['verification']['verdict'] = 'OPEN'
                dom['uncertainty']['C-001']['level'] = 'assumed'
            before = copy.deepcopy(dom)
            for strict in (False, True):
                with self.subTest(uncertain=uncertain, strict=strict):
                    report = run(text, dom, strict=strict)
                    self.assertEqual(report['verdict'], 'FAIL', report)
                    self.assertIn('masked_uncertainty', [i['type'] for i in report['issues']])
                    self.assertEqual(run('Possibly, ' + text, dom, strict=strict)['verdict'], 'PASS')
                    self.assertEqual(run('Perhaps, ' + text, dom, strict=strict)['verdict'], 'FAIL')
            self.assertEqual(dom, before)

    def test_curated_qualifier_apply_rejection_and_control(self):
        import yaml
        for suffix in ('json', 'yaml'):
            text, dom = fixture()
            dom['claims'][0]['text'] = 'Possibly, ' + dom['claims'][0]['text']
            dom['sources'][0]['text'] = dom['claims'][0]['text']
            dom['claims'][0]['evidence'][0]['span'] = 'p.1: «' + dom['claims'][0]['text'] + '»'
            dom['claims'][0]['verification']['verdict'] = 'OPEN'
            dom['uncertainty']['C-001']['level'] = 'assumed'
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3]) as td:
                draft = Path(td)/'draft.md'; dp = Path(td)/('dom.' + suffix)
                dp.write_text(json.dumps(dom) if suffix == 'json' else yaml.safe_dump(dom), encoding='utf-8')
                original = dp.read_bytes()
                args = [sys.executable, str(WRITER/'draft_loop.py'), '--text', str(draft),
                        '--dom', str(dp), '--paragraph-id', 'PAR-01', '--apply']
                for qualified in (False, True):
                    candidate = ('Possibly, ' if qualified else '') + text
                    draft.write_text(candidate, encoding='utf-8'); draft_before = draft.read_bytes()
                    p = recorded_subprocess(args, 'hedge-apply-' + suffix + '-' + str(qualified))
                    report = json.loads(p.stdout)
                    self.assertEqual(draft.read_bytes(), draft_before)
                    if not qualified:
                        self.assertNotEqual(p.returncode, 0, report)
                        self.assertEqual(report['verdict'], 'FAIL', report)
                        self.assertFalse(report.get('applied', False))
                        self.assertEqual(dp.read_bytes(), original)
                    else:
                        self.assertEqual(p.returncode, 0, report)
                        self.assertTrue(report['applied'])
                        expected = copy.deepcopy(dom)
                        expected['structure']['chapters'][0]['sections'][0]['paragraphs'][0]['text'] = candidate
                        from citation_trace import load_dom
                        self.assertEqual(load_dom(dp), expected)

    def test_malformed(self):
        for dom in (None, [], {}, {'claims': [None]}, {'claims': {}}):
            self.assertEqual(self.trace('Synthetic.', dom)['verdict'], 'FAIL')

    def test_numeric_match(self):
        text, dom = fixture()
        dom['claims'][0]['text'] += ' 12 mm'
        text = 'The synthetic sample is blue 12 mm [C-001] [S-001].'
        dom['claims'][0]['verification']['numeric_comparison'] = {'status': 'MATCH'}
        self.assertEqual(self.trace(text, dom)['verdict'], 'PASS')

    def test_typed_containers_and_duplicate_ids(self):
        for key in ('claims', 'sources', 'uncertainty', 'structure'):
            for malformed in (None, True, 'bad', 42):
                with self.subTest(key=key, value=malformed):
                    text, dom = fixture(); dom[key] = malformed
                    self.assertEqual(self.trace(text, dom)['verdict'], 'FAIL')
        for field in ('sections', 'paragraphs'):
            text, dom = fixture()
            ch = dom['structure']['chapters'][0]
            target = ch if field == 'sections' else ch['sections'][0]
            target[field] = {}
            self.assertEqual(self.trace(text, dom)['verdict'], 'FAIL')
        text, dom = fixture()
        dom['structure']['chapters'][0]['sections'][0]['paragraphs'][1]['id'] = 'PAR-01'
        self.assertEqual(self.trace(text, dom)['verdict'], 'FAIL')

    def test_inferred_assumed_and_disputed(self):
        for level in ('inferred', 'assumed', 'disputed'):
            text, dom = fixture(); dom['uncertainty']['C-001']['level'] = level
            self.assertEqual(self.trace(text, dom)['verdict'], 'FAIL')
            self.assertEqual(self.trace('Possibly, ' + text, dom)['verdict'], 'PASS')

    def test_ingest_selection_blocks(self):
        from draft_loop import ingest
        from citation_trace import InputError
        text, dom = fixture()
        for pid, candidate in (('missing', text), ('PAR-02', text), ('PAR-01', text + '\n \n' + text)):
            with self.subTest(pid=pid, candidate=candidate):
                before = copy.deepcopy(dom)
                with self.assertRaises(InputError): ingest(candidate, dom, pid)
                self.assertEqual(dom, before)

    def test_derived_warning_policy_and_formula_metadata(self):
        text, dom = fixture()
        c = copy.deepcopy(dom['claims'][0]); c['id'] = 'C-002'
        dom['claims'].append(c)
        dom['uncertainty']['C-002'] = {'level': 'established'}
        dom['claims'][0]['derived_from'] = ['C-002']
        from citation_trace import run
        self.assertEqual(run(text, dom)['verdict'], 'PASS')
        self.assertEqual(run(text, dom, strict=True)['verdict'], 'FAIL')
        dom['claims'][0]['verification']['formula'] = {'name': 'synthetic', 'constant_check': 'formula_consistent'}
        self.assertEqual(run(text, dom)['verdict'], 'PASS')

    def test_duplicate_mapping_loader(self):
        from citation_trace import load_dom, InputError
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3]) as td:
            for suffix, content in (('.json', '{"claims": [], "claims": []}'), ('.yaml', 'claims: []\nclaims: []\n')):
                p = Path(td)/('duplicate' + suffix); p.write_text(content, encoding='utf-8')
                with self.assertRaises(InputError): load_dom(p)

    def test_cli_and_ingestion(self):
        text, dom = fixture()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3]) as td:
            d = Path(td); draft = d/'draft.txt'; dp = d/'dom.json'
            draft.write_text(text, encoding='utf-8'); dp.write_text(json.dumps(dom), encoding='utf-8')
            def call(script, *args):
                p = subprocess.run([sys.executable, str(WRITER/script), *map(str, args)], capture_output=True, text=True)
                return p, json.loads(p.stdout)
            p, r = call('citation_trace.py', '--text', draft, '--dom', dp)
            self.assertEqual(p.returncode, 0, r)
            args = ('--text', draft, '--dom', dp, '--paragraph-id', 'PAR-01')
            original = dp.read_bytes()
            p, r = call('draft_loop.py', *args)
            self.assertEqual(p.returncode, 0, r); self.assertEqual(dp.read_bytes(), original)
            p, r = call('draft_loop.py', *args, '--apply')
            self.assertEqual(p.returncode, 0, r)
            expected = copy.deepcopy(dom)
            expected['structure']['chapters'][0]['sections'][0]['paragraphs'][0]['text'] = text
            self.assertEqual(json.loads(dp.read_text(encoding='utf-8')), expected)
            original = dp.read_bytes(); draft.write_text(text + ' New causal claim.', encoding='utf-8')
            p, r = call('draft_loop.py', *args, '--apply')
            self.assertNotEqual(p.returncode, 0); self.assertEqual(dp.read_bytes(), original)
            p, r = call('citation_trace.py', '--text', draft, '--dom', d/'missing')
            self.assertNotEqual(p.returncode, 0); self.assertEqual(r['verdict'], 'FAIL')
            import yaml
            draft.write_text(text, encoding='utf-8'); yp = d/'dom.yaml'
            yp.write_text(yaml.safe_dump(dom, allow_unicode=True), encoding='utf-8')
            p, r = call('draft_loop.py', '--text', draft, '--dom', yp, '--paragraph-id', 'PAR-01', '--apply')
            self.assertEqual(p.returncode, 0, r)
            self.assertEqual(yaml.safe_load(yp.read_text(encoding='utf-8')), expected)
            p, r = call('citation_trace.py')
            self.assertNotEqual(p.returncode, 0); self.assertEqual(r['verdict'], 'FAIL')

    def test_real_review_subprocess(self):
        text, dom = fixture()
        proposition = 'Установлено, что синтетический образец имеет синий цвет'
        dom['claims'][0]['text'] = proposition
        dom['sources'][0]['text'] = proposition
        dom['claims'][0]['evidence'][0]['span'] = 'p.1: «' + proposition + '»'
        text = proposition + ' [C-001] [S-001].'
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[3]) as td:
            d = Path(td); draft = d/'draft.md'; dp = d/'dom.json'; contract = d/'contract.json'; out = d/'report.json'
            draft.write_text(text, encoding='utf-8')
            contract.write_text(json.dumps({'claims': [{'claim_id': 'C-001', 'proposition': dom['claims'][0]['text']}]}), encoding='utf-8')
            for positive in (True, False):
                if not positive: dom['claims'][0]['evidence'] = []
                dp.write_text(json.dumps(dom), encoding='utf-8')
                env = dict(os.environ, WRITER_CORE_ROOT=str(CORE))
                p = recorded_subprocess([sys.executable, str(CORE/'wc_cli.py'), 'review', '--draft', str(draft), '--contract', str(contract), '--dom', str(dp), '--max-iterations', '0', '--out', str(out)], 'review-' + str(positive), env=env)
                self.assertTrue(out.exists(), p.stdout + p.stderr)
                report = json.loads(out.read_text(encoding='utf-8'))
                self.assertEqual(report['trace_checks_final']['verdict'], 'PASS' if positive else 'FAIL', report)
                self.assertEqual(report['final_verdict'], 'PASS' if positive else 'FAIL', report)
                self.assertEqual(json.loads(p.stdout)['final_verdict'], report['final_verdict'])
                if positive:
                    self.assertFalse(report.get('escalation'), report)
                    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                else:
                    self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == '__main__':
    unittest.main()
