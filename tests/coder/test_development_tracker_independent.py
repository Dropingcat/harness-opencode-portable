"""Independent Phase A acceptance checks; no production state or network use."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / 'tests/fixtures/development_tracker.original.2026-09-15.json'
SPEC = importlib.util.spec_from_file_location('independent_tracker_gate', ROOT / 'scripts/tools/check_development_tracker.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class IndependentTrackerTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'config/development_tracker.json').read_text(encoding='utf-8'))

    def item(self, identifier):
        return next(x for x in self.data['dev_items'] + self.data['workstreams'] if x['id'] == identifier)

    def test_exact_baseline_and_normalized_snapshot(self):
        raw = BASELINE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '9e7303c2801a7cac72fab5718c6eed3b338352c87add7f31a283ae78a04be199')
        original = json.loads(raw)
        self.assertEqual(self.data['history'][0]['snapshot'], original)
        digest = hashlib.sha256(json.dumps(original, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(digest, '0f5d96969a23e1766dc748f7f833d220e7f85f53cffe8bd5e07b7a201b349647')
        current = {x['id']: x for x in self.data['dev_items'] + self.data['workstreams']}
        historical = original['dev_items'] + original['workstreams']
        self.assertEqual(set(current), {x['id'] for x in historical})
        for old in historical:
            for key in ('title', 'result'):
                if key in old:
                    self.assertEqual(current[old['id']][key], old[key])
            self.assertEqual(self.data['history'][0]['snapshot'][
                'dev_items' if old['id'].startswith('DEV-') else 'workstreams'][
                    next(i for i, x in enumerate(original['dev_items' if old['id'].startswith('DEV-') else 'workstreams']) if x['id'] == old['id'])]['evidence'], old['evidence'])

    def test_counts_and_current_noncertification(self):
        expected = {}
        for group, prefix in (('dev_items', 'dev'), ('workstreams', 'workstream')):
            for status in ('done', 'in_progress', 'not_started'):
                expected[prefix + '_' + status] = sum(x['status'] == status for x in self.data[group])
        self.assertEqual(self.data['counts'], expected)
        self.assertEqual(self.item('DEV-05')['status'], 'in_progress')
        self.assertIs(self.item('DEV-05')['production_ready'], False)
        for identifier in ('DEV-03', 'DEV-04', 'WS-57A'):
            self.assertIn('1.18.30', self.item(identifier)['completion_scope'])
        self.assertEqual(GATE.check(self.data), [])

    def test_missing_historical_completion_scope_rejected(self):
        for identifier in ('DEV-03', 'DEV-04', 'WS-57A'):
            with self.subTest(identifier=identifier):
                changed = copy.deepcopy(self.data)
                next(x for x in changed['dev_items'] + changed['workstreams'] if x['id'] == identifier).pop('completion_scope')
                self.assertTrue(GATE.check(changed), 'historical DONE without version scope admitted')

    def test_v2_scope_substitution_rejected(self):
        self.item('DEV-03')['completion_scope'] = 'OpenCode 2.0.29 fully certified'
        self.assertTrue(GATE.check(self.data), 'historical DONE relabeled as V2 certification admitted')

    def test_certified_with_blocked_connection_rejected(self):
        self.item('DEV-05')['current_readiness']['certified'] = 'PASS'
        self.assertTrue(GATE.check(self.data), 'certified PASS with connected BLOCKED/host NOT_TESTED admitted')

    def test_accidental_semantic_readiness_rejected(self):
        self.data['semantic_ready'] = True
        self.assertTrue(GATE.check(self.data), 'semantic_ready true with blocked transport admitted')

    def test_current_evidence_replacement_cannot_rewrite_history(self):
        self.data['history'][0]['snapshot']['dev_items'][0]['evidence'] = 'replacement'
        self.data['history'][0]['snapshot_sha256'] = hashlib.sha256(json.dumps(self.data['history'][0]['snapshot'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertTrue(GATE.check(self.data))


if __name__ == '__main__':
    unittest.main()
