#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run(argv: list[str], cwd: Path) -> dict:
    try:
        cp = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=30, check=False)
        return {"argv": argv, "exit_code": cp.returncode, "stdout": cp.stdout.strip(), "stderr": cp.stderr.strip()}
    except Exception as exc:
        return {"argv": argv, "error": f"{exc.__class__.__name__}: {exc}"}


def sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--opencode-bin", default=os.environ.get("OPENCODE_BIN", "opencode"))
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    root = Path(args.repo).resolve()
    opencode_path = Path(args.opencode_bin)
    if not opencode_path.is_absolute():
        resolved = shutil.which(args.opencode_bin)
        opencode_path = Path(resolved) if resolved else opencode_path
    payload = {
        "schema": "harness-remote-environment/1.0",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "node": run(["node", "--version"], root),
        "git": run(["git", "--version"], root),
        "repo_head": run(["git", "rev-parse", "HEAD"], root),
        "repo_status": run(["git", "status", "--short"], root),
        "opencode": {
            "requested": args.opencode_bin,
            "resolved": str(opencode_path),
            "exists": opencode_path.is_file(),
            "sha256": sha256(opencode_path),
            "version": run([args.opencode_bin, "--version"], root),
        },
        "env_presence": {
            # Presence only. Never serialize values of secrets.
            key: bool(os.environ.get(key))
            for key in ["OPENCODE_BIN", "OPENCODE_RUNS_DIR", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY"]
        },
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
