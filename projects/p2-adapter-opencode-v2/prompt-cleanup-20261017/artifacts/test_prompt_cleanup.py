"""Offline prompt-cleanup checks. No scanner, provider or host invocation."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]
HARNESS = PROJECT.parents[2]
BASELINE = PROJECT / 'artifacts/baseline'
TARGET = Path(os.environ.get('PROMPT_CLEANUP_TARGET', HARNESS))
sys.path.insert(0, str(HARNESS))
from scripts.agent_gen.compile_agents import compile_agents


def load(root, path):
    return json.loads((root / path).read_text(encoding='utf-8'))


def differences(a, b, prefix=()):
    if isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
        return set().union(*(differences(a[k], b[k], prefix + (k,)) for k in a))
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return set().union(*(differences(x, y, prefix + (i,)) for i, (x, y) in enumerate(zip(a, b))))
    return set() if a == b else {prefix}


class PromptCleanupTests(unittest.TestCase):
    def test_no_scanner_instruction_in_agent_or_shared_prompts(self):
        for directory in ('agents', 'shared', '.opencode/agent', '.opencode/agents', '.opencode/shared'):
            for path in (TARGET / directory).glob('*.md'):
                with self.subTest(path=path.relative_to(TARGET)):
                    text = path.read_text(encoding='utf-8').lower()
                    self.assertNotIn('doc_guard', text)
                    self.assertNotIn('doc-guard', text)

    def test_source_and_generated_agents_agree(self):
        self.assertEqual([], compile_agents(TARGET, write=False)['stale'])

    def test_route_hint_changed_without_route_behavior_changes(self):
        path = 'config/routes_authority.json'
        self.assertEqual({('routes', 'web-research', 'agent_hint')},
                         differences(load(BASELINE, path), load(TARGET, path)))

    def test_tool_authority_changes_only_prompt_fields(self):
        path = 'config/tool_contracts_authority.json'
        expected = {('contracts', name, field) for name, field in (
            ('doc_guard', 'guard'), ('coder_run', 'guard'), ('research_web', 'guard'),
            ('research_web', 'safety'), ('research_academic', 'guard'))}
        self.assertEqual(expected, differences(load(BASELINE, path), load(TARGET, path)))

    def test_compiled_views_change_only_matching_prompt_text(self):
        for path in ('config/runtime_snapshot.json', 'config/tool_skill_routes.json'):
            delta = differences(load(BASELINE, path), load(TARGET, path))
            self.assertEqual(5, len(delta))
            self.assertTrue(all(p[-1] in ('agent_hint', 'guard', 'safety') for p in delta))
            contracts = load(TARGET, path)['tool_contracts']
            for value in contracts.values():
                for field in ('guard', 'safety'):
                    self.assertNotIn('doc_guard', value.get(field, '').lower())

    def test_manual_scanner_registration_is_not_removed(self):
        path = 'config/tool_contracts_authority.json'
        before, after = load(BASELINE, path)['contracts']['doc_guard'], load(TARGET, path)['contracts']['doc_guard']
        self.assertEqual(before['commands'], after['commands'])
        self.assertEqual(before['required_stages'], after['required_stages'])
        self.assertIn('Manual invocation only', after['guard'])

    def test_guard_policy_and_unrelated_support_are_unchanged(self):
        manifest = json.loads((PROJECT / 'artifacts/BASELINE.json').read_text(encoding='utf-8'))
        for record in manifest['files']:
            if not record['target']:
                with self.subTest(path=record['path']):
                    self.assertEqual(record['sha256'], hashlib.sha256((TARGET / record['path']).read_bytes()).hexdigest())

    def test_agent_frontmatter_preserved(self):
        for path in ('agents/code-orchestrator.md', '.opencode/agent/code-orchestrator.md',
                     '.opencode/agent/research-orchestrator.md', '.opencode/agents/code-orchestrator.md',
                     '.opencode/agents/research-orchestrator.md'):
            self.assertEqual((BASELINE / path).read_text(encoding='utf-8').split('---', 2)[1],
                             (TARGET / path).read_text(encoding='utf-8').split('---', 2)[1])

    def test_source_audit_is_unmodified(self):
        path = HARNESS / 'docs/audit 17-10-26/audit_1.md'
        self.assertEqual('b5ef3889192c33f5e7a64993aee6bec624c749bd6d557df7393400096a7b2bcb',
                         hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main(verbosity=2)
