#!/usr/bin/env python3
"""One-command acceptance for the integrated Writer + Researcher + Coder harness."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(argv: list[str], *, env: dict[str, str] | None = None) -> int:
    print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, cwd=ROOT, env=env).returncode


def researcher_env() -> dict[str, str]:
    e = dict(os.environ)
    roots = [str(ROOT / "scripts" / "researcher"), str(ROOT)]
    if e.get("PYTHONPATH"):
        roots.append(e["PYTHONPATH"])
    e["PYTHONPATH"] = os.pathsep.join(roots)
    return e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("modules", "gates", "all"), nargs="?", default="all")
    args = ap.parse_args()

    if args.mode in {"modules", "all"}:
        steps = [
            ([sys.executable, "-m", "pytest", "-q", "tests/writer"], None),
            ([sys.executable, "-m", "pytest", "-q", "tests/researcher"], researcher_env()),
            ([sys.executable, "-m", "pytest", "-q", "tests/coder"], None),
        ]
        for command, env in steps:
            rc = run(command, env=env)
            if rc:
                return rc

    if args.mode in {"gates", "all"}:
        steps = [
            [sys.executable, "scripts/router/compile_runtime.py", "--check"],
            [sys.executable, "scripts/router/compile_capability_runtime.py", "--check"],
            [sys.executable, "-m", "compileall", "-q", "scripts/researcher/researcher_core"],
            [sys.executable, "-m", "compileall", "-q", "scripts/code-factory"],
            [sys.executable, "-m", "json.tool", "config/factory_gate_policy.json"],
            [sys.executable, "-m", "json.tool", "config/artifact_provenance_policy.json"],
            [sys.executable, "-m", "compileall", "-q", "scripts/writer"],
            [sys.executable, "-m", "compileall", "-q", "scripts/jobs", "scripts/router", "scripts/orchestration", "scripts/capsules"],
        ]
        for command in steps:
            rc = run(command, env=researcher_env() if "compile_runtime.py" in command or "compile_capability_runtime.py" in command else None)
            if rc:
                return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
