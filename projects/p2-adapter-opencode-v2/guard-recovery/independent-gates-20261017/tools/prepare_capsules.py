"""Compile exact local paths/commands into the three approved role contracts."""
import json
import os
from pathlib import Path
import subprocess
import sys

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[3]
WT = ROOT / 'projects/p2-adapter-opencode-v2/guard-recovery/runs/worktree'
SOURCES = ['guard/src/semantic_layer.py', 'guard/src/artifact_guard.py',
           'guard/src/opencode_transport.py', 'guard/src/native_semantic_transport.py',
           'scripts/tools/doc_guard.py', 'tests/coder/test_guard_recovery.py',
           'tests/coder/test_native_classifier_recovery.py']


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def variants(file, cwd):
    return sorted({str(file), file.as_posix(), os.path.relpath(file, cwd).replace('\\', '/')})


def main():
    q, scratch = P / 'artifacts/quarantine', P / 'runs/tmp'
    q.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    diff = P / 'artifacts/recovery-scope.patch'
    value = subprocess.run(['git', '-C', str(WT), 'diff', 'ac037f3', '892ecc3', '--', *SOURCES],
                           check=True, capture_output=True, text=True, encoding='utf-8')
    diff.write_text(value.stdout, encoding='utf-8')
    helper = P / 'tools/coverage_existing.py'
    command = '& ' + ' '.join(quote(v) for v in [sys.executable, helper, WT, q, scratch])
    metadata = P / 'artifacts/process-metadata.json'
    facts = {'task_id': 'guard-independent-gates-20261017', 'candidate_commit': '892ecc3',
             'implementation_author': 'code-orchestrator under explicit local recovery authorization',
             'prior_offline_tests': 53, 'prior_offline_subtests': 37, 'independent_gates': 'PENDING',
             'implementation_files': 5, 'focused_test_files': 2, 'guard_admission': 'NOT_GRANTED',
             'user_authorization': {'initial_specialized_jobs': 3, 'additional_reviewer_retry': 1,
                                    'maximum_jobs': 4, 'seconds_per_job': 120,
                                    'observed_tokens': 100000, 'inflight_overshoot_accepted': True,
                                    'canary': False, 'merge': False, 'restart': False},
             'worker_role_impersonated': False, 'reviewer_tester_content': 'not supplied; unadmitted',
             'rework_rounds': 0, 'attempt_limit': 2,
             'native_bridge': 'last_observed_deterministic_alive; semantic_ready=false',
             'cli_transport': 'explicit registered primary runners; no general fallback'}
    metadata.write_text(json.dumps(facts, indent=2), encoding='utf-8')
    process = [WT / 'shared/code-factory-process.md', WT / '.opencode/shared/code-factory-process.md',
               ROOT / 'shared/code-factory-process.md']
    for role, child in [('reviewer', 'code-reviewer'), ('tester', 'code-tester'), ('auditor', 'code-auditor')]:
        output, cwd = q / (role + '.json'), P if role == 'auditor' else WT
        inputs = process + ([metadata] if role == 'auditor' else [WT / n for n in SOURCES] + [diff])
        extras = [q / 'tester-coverage.json', q / 'tester-junit.xml'] if role == 'tester' else []
        inputs += ([helper] + extras) if role == 'tester' else []
        rules = [{'action': '*', 'resource': '*', 'effect': 'deny'}]
        for action, files in [('read', inputs), ('edit', [output] + extras),
                              ('external_directory', {q, *[f.parent for f in inputs]})]:
            for file in files:
                rules += [{'action': action, 'resource': v, 'effect': 'allow'} for v in variants(file, cwd)]
        rules.append({'action': 'subagent', 'resource': child, 'effect': 'allow'})
        if role == 'reviewer':
            rules += [{'action': 'skill', 'resource': name, 'effect': 'allow'}
                      for name in ['adversarial-critic-checklist', 'code-review-and-quality']]
        if role == 'tester':
            rules.append({'action': 'shell', 'resource': command, 'effect': 'allow'})
        prompt = (P / ('contracts/' + role + '.md')).read_text(encoding='utf-8')
        replacements = {'%CANDIDATE_ROOT%': WT, '%OUTPUT_JSON%': output, '%DIFF_FILE%': diff,
                        '%TEST_COMMAND%': command, '%PROCESS_METADATA%': metadata}
        for key, value in replacements.items():
            prompt = prompt.replace(key, str(value))
        capsule = {'role': role, 'primary': child + '-runner', 'specialized': child,
                   'candidate_commit': '892ecc3', 'workdir': str(cwd), 'output': str(output),
                   'prompt': prompt, 'permissions': rules, 'guard_admission': 'NOT_GRANTED'}
        (P / ('contracts/' + role + '.json')).write_text(
            json.dumps(capsule, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'roles_prepared': 3, 'budget': 100000, 'budget_mode': 'observational',
                      'model_calls_made': 0, 'coverage': 'stdlib trace, current process only'}))


if __name__ == '__main__':
    main()
