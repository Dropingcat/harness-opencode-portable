"""Existing offline suites with stdlib trace; subprocess coverage is excluded."""
import json
import os
from pathlib import Path
import sys
import sysconfig
import trace

import pytest


def coverage_report(root, counts):
    files = {}
    for source in (root / 'guard/src').glob('*.py'):
        executable = {line for line in trace._find_executable_linenos(str(source)) if line > 0}
        covered = {line for (name, line), hits in counts.items()
                   if hits > 0 and Path(name).resolve() == source.resolve()} & executable
        files[str(source.relative_to(root))] = {
            'covered_lines': len(covered), 'num_statements': len(executable)}
    covered = sum(value['covered_lines'] for value in files.values())
    total = sum(value['num_statements'] for value in files.values())
    return {'measurement': 'stdlib_trace_current_process_only',
            'subprocess_coverage': 'NOT_MEASURED', 'files': files,
            'totals': {'covered_lines': covered, 'num_statements': total,
                       'percent_covered': round(100 * covered / total, 2) if total else 0.0}}


def main():
    root, output, scratch = (Path(value).resolve() for value in sys.argv[1:4])
    scratch.mkdir(parents=True, exist_ok=True)
    os.environ.update(OPENCODE_HARNESS_ROOT=str(root),
                      DOC_GUARD_CONFIG=str(root / 'guard/src/guard_config.json'),
                      TEMP=str(scratch), TMP=str(scratch))
    os.chdir(root)
    names = ['test_guard_artifact_stage1.py', 'test_guard_core_stage1.py',
             'test_guard_discovery_contract_stage1.py', 'test_guard_recovery.py',
             'test_native_classifier_recovery.py']
    arguments = ['-q'] + ['tests/coder/' + name for name in names]
    arguments += ['--junitxml=' + str(output / 'tester-junit.xml')]
    tracer = trace.Trace(count=True, trace=False,
                         ignoredirs=[sysconfig.get_path('stdlib'), sysconfig.get_path('purelib')])
    result = tracer.runfunc(pytest.main, arguments)
    report = coverage_report(root, tracer.results().counts)
    (output / 'tester-coverage.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'pytest_exit': int(result), 'coverage': report['totals']}))
    return int(result)


if __name__ == '__main__':
    raise SystemExit(main())
