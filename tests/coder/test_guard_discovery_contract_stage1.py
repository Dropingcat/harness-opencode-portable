"""Static discovery contracts only; no provider or host enforcement certification."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    return json.loads((ROOT / 'config' / name).read_text(encoding='utf-8'))


class DiscoveryContracts(unittest.TestCase):
    def test_canonical_and_legacy_bindings_are_distinct_existing_paths(self):
        tools = load('tool_runtime_bindings.json')['tools']
        for name, path, provider in [
            ('doc_guard', 'scripts/tools/doc_guard.py', 'doc_guard'),
            ('session_guard', 'guard/src/session_guard.py', 'session_guard'),
            ('guard_runner', 'guard/src/guard_runner.py', 'guard_runner'),
        ]:
            self.assertEqual(path, tools[name]['entrypoint'])
            self.assertEqual(provider, tools[name]['provider'])
            self.assertTrue((ROOT / path).is_file(), path)

    def test_policy_requires_combined_artifact_scan_without_db_fallback(self):
        policy = load('guard_policy.json')
        impl = policy['guard_impl']
        self.assertEqual('scripts/tools/doc_guard.py', impl['entrypoint'])
        self.assertEqual(['P0', 'P2'], impl['required_stages'])
        self.assertFalse(impl['artifact_requires_session_db'])
        self.assertEqual(['P0'], impl['legacy_session_guard']['stages'])
        self.assertFalse(impl['legacy_session_guard']['combined_admission'])
        self.assertEqual(['P0', 'P2'], impl['legacy_guard_runner']['stages'])
        self.assertEqual('BLOCK', policy['fail_closed']['guard_missing'])
        self.assertEqual('BLOCK', policy['fail_closed']['timeout'])
        self.assertEqual('BLOCK for orchestrators; WARN only for isolated local-only tasks with no untrusted input', policy['fail_closed']['config_missing'])
        self.assertEqual('p0_or_warn', policy['profile_binding']['soft'])
        self.assertNotIn('otherwise label', json.dumps(policy['guard_points']))

    def test_tool_contract_covers_readiness_scan_root_and_failures(self):
        contract = load('tool_contracts_authority.json')['contracts']['doc_guard']
        self.assertEqual(['command'], contract['required_input'])
        self.assertEqual(['artifact', 'config'], contract['commands']['scan']['required_input'])
        self.assertFalse(contract['commands']['preflight']['admission'])
        self.assertEqual(['--harness-root', 'OPENCODE_HARNESS_ROOT', 'owned_root'], contract['root_precedence'])
        self.assertEqual(['P0', 'P2'], contract['required_stages'])
        self.assertIn('sha256', contract['output_expectation'])
        self.assertIn('nonzero', contract['failures'])
        self.assertFalse(contract['host_enforcement_implemented'])

    def test_prompt_and_dispatch_have_explicit_discovery_and_admission_limits(self):
        for path in ['agents/code-orchestrator.md', 'shared/harness-dispatch-map.md']:
            text = (ROOT / path).read_text(encoding='utf-8')
            for phrase in ['scripts/tools/doc_guard.py', 'preflight --json',
                           'scan --artifact FILE --config CONFIG --json',
                           '--harness-root', 'OPENCODE_HARNESS_ROOT',
                           'never PASS', 'hash-bound receipt', 'P0-only',
                           'Native host binding/enforcement remains outstanding']:
                self.assertIn(phrase, text, path)
            self.assertNotIn('scripts/tools/session_guard.py', text)


if __name__ == '__main__':
    unittest.main()
