#!/usr/bin/env python3
"""CI smoke-test: интеграционный прогон run_research.py (dry-run).

Запускается из GitHub Actions (ci.yml -> integration-test job).
Работает ТОЛЬКО если LOCAL_TEST_DATA=true и есть testdata (в CI нет
локального корпуса -> SKIP с кодом 0).
"""
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if os.environ.get("LOCAL_TEST_DATA") != "true":
        print("LOCAL_TEST_DATA != true -> SKIP")
        return 0
    harness = Path(__file__).resolve().parents[2]
    runner = harness / "scripts" / "research" / "run_research.py"
    testdata = harness / "scripts" / "research" / "testdata" / "exp1" / "input.txt"
    if not runner.exists() or not testdata.exists():
        print("runner/testdata отсутствует -> SKIP")
        return 0
    tmp = os.environ.get("TEMP_DIR", "/tmp/opencode/ci_test")
    cmd = [sys.executable, str(runner), str(testdata), "--dry-run",
           "--workspace", tmp, "--max-iterations", "1", "--max-cost-rub", "5"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    print(r.stdout[-2000:])
    if r.returncode != 0:
        print("STDERR:", r.stderr[-1000:], file=sys.stderr)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())