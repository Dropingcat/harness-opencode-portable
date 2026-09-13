#!/usr/bin/env python3
"""Repository-owned Researcher acceptance entrypoint.

It bootstraps the canonical Researcher import root so E2E/regression commands do
not depend on session-specific PYTHONPATH shell state (TD-040).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R4_TESTS = [
    "tests/researcher/test_uncertainty_field.py",
    "tests/researcher/test_tribunal_composition.py",
    "tests/researcher/test_tribunal_evidence.py",
    "tests/researcher/test_r4_2_evidence_slicing_e2e.py",
    "tests/researcher/test_tribunal_role_handbook.py",
    "tests/researcher/test_tribunal_inquiry.py",
    "tests/researcher/test_r4_3_role_execution_e2e.py",
    "tests/researcher/test_r4_3_multi_role_first_pass_e2e.py",
    "tests/researcher/test_tribunal_dialectic.py",
    "tests/researcher/test_r4_4_dialectic_observer_e2e.py",
    "tests/researcher/test_tribunal_argument_graph.py",
    "tests/researcher/test_r4_4_advocate_branching_e2e.py",
    "tests/researcher/test_tribunal_disclosure.py",
    "tests/researcher/test_r4_4_l2b_branch_questioning_e2e.py",
    "tests/researcher/test_tribunal_provider_binding.py",
    "tests/researcher/test_r4_4_l3_live_dialogue_e2e.py",
    "tests/researcher/test_r4_4_l3_live_dialogue_failures.py",
    "tests/researcher/test_r4_4_l3_second_role_family_e2e.py",
    "tests/researcher/test_r4_4_l3b_response_grounding.py",
    "tests/researcher/test_r4_4_l3b_live_advocate_grounding_e2e.py",
    "tests/researcher/test_opencode_tribunal_launcher.py",
]


def env() -> dict[str, str]:
    out = dict(os.environ)
    roots = [str(ROOT / "scripts" / "researcher"), str(ROOT)]
    old = out.get("PYTHONPATH")
    if old:
        roots.append(old)
    out["PYTHONPATH"] = os.pathsep.join(roots)
    return out


def run(argv: list[str]) -> int:
    print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, cwd=ROOT, env=env()).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("r4", "full", "gates", "all"), nargs="?", default="r4")
    args = ap.parse_args()

    if args.mode in {"r4", "all"}:
        rc = run([sys.executable, "-m", "pytest", "-q", *R4_TESTS])
        if rc:
            return rc
    if args.mode in {"full", "all"}:
        rc = run([sys.executable, "-m", "pytest", "-q", "tests/researcher"])
        if rc:
            return rc
    if args.mode in {"gates", "all"}:
        commands = [
            [sys.executable, "scripts/router/compile_runtime.py", "--check"],
            [sys.executable, "scripts/router/compile_capability_runtime.py", "--check"],
            [sys.executable, "-m", "compileall", "-q", "scripts/researcher/researcher_core"],
        ]
        for command in commands:
            rc = run(command)
            if rc:
                return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
