"""Independent stage-0 negative controls; all writes are isolated fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'stage0_independent_subject', ROOT / 'scripts/tools/check_stage0_matrix.py')
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)
WS = ['WS-55A', 'WS-56A', 'WS-56B', 'WS-57A', 'WS-57B', 'WS-58A', 'WS-59A']
REQUIRED_DEBTS = ['TD-004', 'TD-013', 'TD-024', 'TD-053', 'TD-054',
                  'TD-175', 'TD-174', 'TD-176', 'TD-177', 'TD-RESTORE-01',
                  'E2E-06', 'E2E-02', 'E2E-01', 'E2E-04', 'E2E-03', 'E2E-07', 'E2E-05']


class IndependentStage0Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.tracker = {
            'dev_items': [{'id': f'DEV-{i:02}', 'title': 'Independent DEV',
                           'status': 'not_started'} for i in range(1, 14)],
            'workstreams': [{'id': key, 'title': 'Independent WS', 'status': 'done'}
                            for key in WS]}
        ids = REQUIRED_DEBTS + [f'TD-INDEPENDENT-{i}' for i in range(224)]
        self.debts = {'debts': [{'id': key, 'title': 'Independent debt',
                                'owner': 'fixture', 'status': 'open' if i < 182 else 'closed'}
                               for i, key in enumerate(ids)],
                      'counts': {'total': 241, 'open': 182, 'closed': 59}}
        for relative in subject.SOURCE_DOCS + subject.EVIDENCE_PATHS:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'Independent bounded fixture\n')
        self.write_sources()
        self.matrix = subject.build(self.root)

    def write_sources(self):
        (self.root / 'config').mkdir(exist_ok=True)
        for name, value in [('development_tracker', self.tracker), ('tech_debt', self.debts)]:
            (self.root / 'config' / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')

    def reject(self, mutation):
        candidate = copy.deepcopy(self.matrix)
        mutation(candidate)
        self.assertTrue(subject.check(candidate, self.root), 'mutation was accepted')

    def test_valid_projection_and_read_only_check(self):
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob('*') if p.is_file()}
        original = copy.deepcopy(self.matrix)
        self.assertEqual([], subject.check(self.matrix, self.root))
        self.assertEqual(original, self.matrix)
        self.assertEqual(before, {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(241, len(self.matrix['td_inventory']))
        self.assertEqual(20, len(self.matrix['items']))

    def test_stale_hash_and_status(self):
        self.reject(lambda m: m['sources'][0].update(sha256='f' * 64))
        self.reject(lambda m: m['items'][0].update(status='done'))
        self.reject(lambda m: m['td_inventory'][0].update(status='closed'))
        self.reject(lambda m: m['td_inventory'][0].update(source_record_sha256='0' * 64))

    def test_missing_dev_ws_and_td(self):
        for collection, key in [('items', 'DEV-13'), ('items', 'WS-59A'),
                                ('td_inventory', 'TD-RESTORE-01')]:
            with self.subTest(key=key):
                self.reject(lambda m, c=collection, k=key:
                            m.__setitem__(c, [r for r in m[c] if r['id'] != k]))
        for collection in ['dev_items', 'workstreams']:
            original = copy.deepcopy(self.tracker)
            self.tracker[collection].pop()
            self.write_sources()
            self.assertTrue(subject.check(self.matrix, self.root))
            self.tracker = original
        self.debts['debts'].pop(0)
        self.write_sources()
        self.assertTrue(subject.check(self.matrix, self.root))

    def test_duplicate_ids_dangling_edges_and_cycles(self):
        for collection in ['items', 'td_inventory', 'stages']:
            with self.subTest(collection=collection):
                self.reject(lambda m, c=collection: m[c].append(copy.deepcopy(m[c][0])))
        for dependency, expected in [('stage-nonexistent', 'dangling'), ('stage-8', 'cycle')]:
            candidate = copy.deepcopy(self.matrix)
            candidate['stages'][0]['depends_on'].append(dependency)
            self.assertTrue(any(expected in error for error in subject.check(candidate, self.root)))
        self.tracker['dev_items'].append(copy.deepcopy(self.tracker['dev_items'][0]))
        self.write_sources()
        self.assertTrue(subject.check(self.matrix, self.root))

    def test_241_source_versus_230_workspace(self):
        self.assertEqual({'total': 241, 'open': 182, 'closed': 59}, self.matrix['inventory_counts'])
        self.debts['debts'] = self.debts['debts'][:-11]
        self.debts['counts'] = {'total': 230, 'open': 182, 'closed': 48}
        self.write_sources()
        self.assertTrue(subject.check(self.matrix, self.root))
        workspace = subject.build(self.root)
        self.assertEqual(230, workspace['inventory_counts']['total'])
        self.assertNotEqual(workspace, self.matrix)

    def test_missing_evidence_and_closure_gates(self):
        self.reject(lambda m: m['items'][0].update(evidence=[]))
        self.reject(lambda m: m['items'][0].update(closure_gates=[]))
        self.reject(lambda m: m['stages'][1].update(closure_gates=[]))
        self.reject(lambda m: m['stages'][8].update(prerequisites=[]))
        (self.root / subject.EVIDENCE_PATHS[-1]).unlink()
        self.assertTrue(subject.check(self.matrix, self.root))

    def test_fabricated_certifications_rejected(self):
        self.reject(lambda m: m['runtime_limits'].update(semantic_status='CERTIFIED', full_autonomy='PASS'))
        self.reject(lambda m: m['items'][0]['readiness'].update(certified='PASS'))
        self.reject(lambda m: m['items'][0]['evidence'][0].update(current_certification=True))
        self.reject(lambda m: m['td_inventory'][-1].update(assessment='AUDITED'))
        self.reject(lambda m: m['stages'][1].update(execution='PASS'))

    def test_fixture_tracker_bytes_are_packaging_exact(self):
        fixture = ROOT / 'tests/fixtures/development_tracker.original.2026-09-15.json'
        self.assertEqual('9e7303c2801a7cac72fab5718c6eed3b338352c87add7f31a283ae78a04be199',
                         hashlib.sha256(fixture.read_bytes()).hexdigest())
