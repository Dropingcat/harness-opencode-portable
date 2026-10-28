"""Offline fixture and mutation checks; no private run receipts required."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/tools/check_stage0_matrix.py'
spec = importlib.util.spec_from_file_location('stage0', SCRIPT)
stage0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage0)


class Stage0Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tracker = {'dev_items': [{'id': f'DEV-{i:02}', 'title': 'fixture',
                         'status': 'not_started', 'evidence': ''} for i in range(1, 14)],
                        'workstreams': [{'id': i, 'title': 'fixture', 'status': 'done',
                                        'evidence': 'historical'} for i in stage0.WS_IDS]}
        self.td = {'debts': [{'id': i, 'title': 'fixture', 'status': 'open',
                             'owner': 'fixture-owner', 'acceptance': 'one positive and one negative trace'}
                            for i in stage0.RELEVANT_TD + stage0.E2E_ORDER + ['TD-999']]}
        self.td['counts'] = {'total': len(self.td['debts']), 'open': len(self.td['debts']), 'closed': 0}
        for path in stage0.SOURCE_DOCS + stage0.EVIDENCE_PATHS:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('{}', encoding='utf-8')
        self.write_sources()
        self.matrix = stage0.build(self.root)

    def write_sources(self):
        (self.root / 'config').mkdir(exist_ok=True)
        for name, data in [('development_tracker', self.tracker), ('tech_debt', self.td)]:
            (self.root / 'config' / (name + '.json')).write_text(json.dumps(data), encoding='utf-8')

    def test_fixture_valid_and_nonmutating(self):
        before = copy.deepcopy(self.matrix)
        self.assertEqual([], stage0.check(self.matrix, self.root))
        self.assertEqual(before, self.matrix)
        self.assertEqual('OUTSIDE_VERIFIED_SCOPE_UNASSESSED', self.matrix['td_inventory'][-1]['assessment'])

    def test_mutations_rejected(self):
        mutations = {
            'duplicate': lambda m: m['items'].append(copy.deepcopy(m['items'][0])),
            'missing_id': lambda m: m['items'].pop(),
            'hash': lambda m: m['sources'][0].update(sha256='0' * 64),
            'status': lambda m: m['items'][0].update(status='done'),
            'dangling': lambda m: m['stages'][1]['depends_on'].append('stage-missing'),
            'cycle': lambda m: m['stages'][0]['depends_on'].append('stage-8'),
            'acceptance': lambda m: m['stages'][1].update(closure_gates=[]),
            'evidence': lambda m: m['items'][0].update(evidence=[]),
            'certification': lambda m: m['items'][0]['readiness'].update(certified='PASS'),
            'unassessed_promotion': lambda m: m['td_inventory'][-1].update(assessment='AUDITED'),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                matrix = copy.deepcopy(self.matrix)
                mutate(matrix)
                self.assertTrue(stage0.check(matrix, self.root))

    def test_source_status_and_bytes_drift_rejected(self):
        self.td['debts'][0]['status'] = 'closed'
        self.write_sources()
        self.assertTrue(stage0.check(self.matrix, self.root))

    def test_duplicate_source_ids_fail_closed(self):
        self.tracker['dev_items'].append(self.tracker['dev_items'][0])
        self.write_sources()
        with self.assertRaises(ValueError):
            stage0.build(self.root)

    def test_missing_source_id_fail_closed(self):
        self.tracker['dev_items'].pop()
        self.write_sources()
        with self.assertRaises(ValueError):
            stage0.build(self.root)

    def test_missing_durable_evidence_fail_closed(self):
        (self.root / stage0.EVIDENCE_PATHS[0]).unlink()
        self.assertTrue(stage0.check(self.matrix, self.root))

    def test_explicit_data_paths_and_separate_evidence_root(self):
        other = self.root / 'other'
        other.mkdir()
        tracker = other / 'tracker.json'
        td = other / 'td.json'
        tracker.write_text(json.dumps(self.tracker), encoding='utf-8')
        td.write_text(json.dumps(self.td), encoding='utf-8')
        matrix = stage0.build(self.root, tracker, td, self.root)
        self.assertEqual([], stage0.check(matrix, self.root, tracker, td, self.root))

    def test_source_declared_inventory_counts_checked(self):
        self.td['counts']['total'] += 1
        self.write_sources()
        with self.assertRaises(ValueError):
            stage0.build(self.root)
