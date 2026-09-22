#!/usr/bin/env python3
"""Repository-owned Coder/code-factory acceptance entrypoint."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env() -> dict[str, str]:
    out = dict(os.environ)
    roots = [str(ROOT / "scripts" / "code-factory"), str(ROOT)]
    if out.get("PYTHONPATH"):
        roots.append(out["PYTHONPATH"])
    out["PYTHONPATH"] = os.pathsep.join(roots)
    return out


def run(argv: list[str]) -> int:
    print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, cwd=ROOT, env=env()).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("full", "gates", "all"), nargs="?", default="all")
    args = ap.parse_args()
    if args.mode in {"full", "all"}:
        rc = run([sys.executable, "-m", "pytest", "-q", "tests/coder"])
        if rc:
            return rc
    if args.mode in {"gates", "all"}:
        commands = [
            [sys.executable, "-m", "compileall", "-q", "scripts/code-factory"],
            [sys.executable, "-m", "json.tool", "config/factory_gate_policy.json"],
            [sys.executable, "-m", "json.tool", "config/artifact_provenance_policy.json"],
        ]
        for command in commands:
            rc = run(command)
            if rc:
                return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
