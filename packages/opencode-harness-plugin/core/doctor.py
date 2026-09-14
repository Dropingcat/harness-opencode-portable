#!/usr/bin/env python3
"""Harness native plugin doctor.

Reports plugin-loaded/bridge/core/legacy status without requiring semantic execution.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def harness_root() -> Path:
    env = __import__("os").environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=None)
    args = ap.parse_args()

    root = harness_root()
    status: dict = {
        "schema": "harness-opencode-plugin-doctor/1.0",
        "core_root": str(root),
        "checks": [],
    }

    checks = [
        ("config_dir", (root / "config").is_dir(), "config present"),
        ("runtime_snapshot", (root / "config" / "runtime_snapshot.json").is_file(), "runtime snapshot"),
        ("capability_snapshot", (root / "config" / "capability_runtime_snapshot.json").is_file(), "capability snapshot"),
        ("plugin_package", (root / "packages" / "opencode-harness-plugin" / "package.json").is_file(), "plugin package"),
        ("bridge_peer", (root / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py").is_file(), "bridge peer"),
    ]
    for name, ok, detail in checks:
        status["checks"].append({"check": name, "ok": ok, "detail": detail})

    # Legacy conflict: native and legacy must not both be loaded.
    legacy = root / "plugins" / "tool-skill-contract-router.ts"
    native_auto = root / ".opencode" / "plugins" / "opencode-harness-plugin.ts"
    status["legacy_plugin_present"] = legacy.is_file()
    status["native_plugin_auto_discovered"] = native_auto.is_file()
    if legacy.is_file() and native_auto.is_file():
        status["conflict"] = True
        status["conflict_detail"] = "legacy + native both installed; do not load simultaneously"
    else:
        status["conflict"] = False
        status["conflict_detail"] = "no simultaneous legacy/native auto-discovery"

    status["ok"] = all(c["ok"] for c in status["checks"]) and not status["conflict"]

    text = json.dumps(status, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())