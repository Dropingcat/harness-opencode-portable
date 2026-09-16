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

    # Legacy would load ONLY if registered in a config (global/project) or placed in an
    # auto-discovery dir (.opencode/plugins/). A file in root plugins/ without registration
    # is not loaded by OpenCode (auto-discovery is .opencode/plugin(s)/ only).
    legacy_auto = root / ".opencode" / "plugins" / "tool-skill-contract-router.ts"

    # Detect legacy registered in global opencode config.
    global_cfgs = [
        Path.home() / ".config" / "opencode" / "opencode.jsonc",
        Path.home() / ".config" / "opencode" / "opencode.json",
    ]
    legacy_in_global = False
    for gcfg in global_cfgs:
        if not gcfg.is_file():
            continue
        try:
            gdata = json.loads(gcfg.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        plugins = gdata.get("plugin") if isinstance(gdata, dict) else None
        if isinstance(plugins, list):
            if any(isinstance(p, str) and "tool-skill-contract-router" in p for p in plugins):
                legacy_in_global = True

    legacy_would_load = legacy_in_global or legacy_auto.is_file()
    status["legacy_in_global_config"] = legacy_in_global
    status["legacy_would_load"] = legacy_would_load

    # Native enabled via project config (.opencode/opencode.json) or auto-discovery.
    project_cfgs = [
        root / ".opencode" / "opencode.json",
        root / "opencode.json",
        root / "opencode.jsonc",
    ]
    native_enabled = False
    native_auto = root / ".opencode" / "plugins" / "opencode-harness-plugin.ts"
    for pcfg in project_cfgs:
        if not pcfg.is_file():
            continue
        try:
            pdata = json.loads(pcfg.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        plugins = pdata.get("plugin") if isinstance(pdata, dict) else None
        if isinstance(plugins, list) and any(
            isinstance(p, str) and "opencode-harness-plugin" in p for p in plugins
        ):
            native_enabled = True
    status["native_enabled_in_project_config"] = native_enabled
    status["native_plugin_auto_discovered"] = native_auto.is_file()

    if legacy_would_load and (native_enabled or native_auto.is_file()):
        status["conflict"] = True
        status["conflict_detail"] = (
            "legacy + native both load (legacy in global config/plugin dir; native in project config/auto-discovery); "
            "do not load simultaneously"
        )
    else:
        status["conflict"] = False
        status["conflict_detail"] = "no simultaneous legacy/native loading"

    status["ok"] = all(c["ok"] for c in status["checks"]) and not status["conflict"]

    text = json.dumps(status, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())