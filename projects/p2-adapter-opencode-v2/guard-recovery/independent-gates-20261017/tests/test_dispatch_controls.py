"""Offline checks for the task-local orchestration helper; no host/API calls."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / 'tools/dispatch_once.py'
spec = importlib.util.spec_from_file_location('task_dispatch', path)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class DispatchControls(unittest.TestCase):
    def test_capsules_use_native_v2_names_for_exact_delegated_role(self):
        root = path.parents[1]
        for role in ('reviewer', 'tester', 'auditor'):
            with self.subTest(role=role):
                capsule = json.loads((root / ('contracts/' + role + '.json')).read_text(encoding='utf-8'))
                rules = capsule['permissions']
                self.assertIn({'action': 'subagent', 'resource': 'code-' + role, 'effect': 'allow'}, rules)
                self.assertFalse(any(rule['action'] in ('task', 'bash') for rule in rules))
                self.assertFalse(any(rule['action'] == '*' and rule['effect'] == 'allow' for rule in rules))

    def test_only_one_additional_reviewer_launch_is_authorized(self):
        ledger = {'jobs': [{'role': 'reviewer', 'launched': False},
                           {'role': 'reviewer', 'launched': True}]}
        control.check_launch_authorization(ledger, 'reviewer')
        ledger['jobs'].append({'role': 'reviewer', 'launched': True})
        with self.assertRaises(control.Block):
            control.check_launch_authorization(ledger, 'reviewer')
        control.check_launch_authorization(ledger, 'tester')
        ledger['jobs'].extend([{'role': 'tester', 'launched': True},
                               {'role': 'auditor', 'launched': True}])
        with self.assertRaises(control.Block):
            control.check_launch_authorization(ledger, 'tester')

    def test_stdlib_coverage_counts_actual_source_lines(self):
        coverage_path = path.with_name('coverage_existing.py')
        coverage_spec = importlib.util.spec_from_file_location('coverage_existing', coverage_path)
        coverage = importlib.util.module_from_spec(coverage_spec)
        coverage_spec.loader.exec_module(coverage)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'guard/src/synthetic.py'
            source.parent.mkdir(parents=True)
            source.write_text('a = 1\nb = 2\n', encoding='utf-8')
            report = coverage.coverage_report(root, {(str(source), 1): 1})
        self.assertEqual(50.0, report['totals']['percent_covered'])
        self.assertEqual('NOT_MEASURED', report['subprocess_coverage'])

    def test_budget_count_is_conservative_and_includes_cache_reasoning(self):
        info = {'tokens': {'input': 10, 'output': 2, 'reasoning': 3,
                           'cache': {'read': 5, 'write': 7}}}
        self.assertEqual(27, control.counted_tokens(info))

    def test_missing_or_invalid_usage_is_never_zero(self):
        for info in ({}, {'tokens': {}},
                     {'tokens': {'input': -1, 'output': 0, 'reasoning': 0, 'cache': {'read': 0, 'write': 0}}},
                     {'tokens': {'input': float('nan'), 'output': 0, 'reasoning': 0, 'cache': {'read': 0, 'write': 0}}}):
            with self.subTest(info=info), self.assertRaises(control.Block):
                control.counted_tokens(info)

    def test_model_variant_is_part_of_binding(self):
        model = {'providerID': 'component', 'id': 'model', 'variant': 'max'}
        self.assertTrue(control.model_equal(model, dict(model)))
        self.assertFalse(control.model_equal(model, {**model, 'variant': 'default'}))
        self.assertFalse(control.model_equal(model, None))

    def test_wrong_model_child_is_recorded_for_owned_cleanup(self):
        model = {'providerID': 'component', 'id': 'model'}
        usage = {'input': 0, 'output': 0, 'reasoning': 0, 'cache': {'read': 0, 'write': 0}}
        class Fake(control.API):
            def info(self, sid):
                return {'id': sid, 'agent': 'code-reviewer-runner', 'model': model, 'tokens': usage}
            def call(self, operation, params=None, body=None):
                return {'data': [{'id': 'ses_owned_child', 'parentID': 'ses_owned_root',
                                  'agent': 'code-reviewer', 'model': {**model, 'id': 'wrong'}, 'tokens': usage}],
                        'cursor': {'previous': None, 'next': None}}
        api = Fake('not-executed')
        with self.assertRaises(control.Block):
            api.graph('ses_owned_root', model, 'code-reviewer')
        self.assertEqual({'ses_owned_root', 'ses_owned_child'}, api.owned_ids)

    def test_v2_cursor_container_does_not_imply_another_page(self):
        model = {'providerID': 'component', 'id': 'model'}
        usage = {'input': 0, 'output': 0, 'reasoning': 0, 'cache': {'read': 0, 'write': 0}}
        class Fake(control.API):
            def info(self, sid):
                return {'id': sid, 'agent': 'code-reviewer-runner', 'model': model, 'tokens': usage}
            def call(self, operation, params=None, body=None):
                return {'data': [], 'cursor': {'previous': None, 'next': None}}
        nodes = Fake('not-executed').graph('ses_owned_root', model, 'code-reviewer')
        self.assertEqual(['ses_owned_root'], list(nodes))

    def test_no_model_default_and_no_auto_permission_flag(self):
        text = path.read_text(encoding='utf-8')
        self.assertNotIn('DEFAULT_MODEL', text)
        self.assertNotIn('--auto', text)
        self.assertIn('module.run_once', text)
        self.assertIn('native_permission_requires_user', text)


if __name__ == '__main__':
    unittest.main()
