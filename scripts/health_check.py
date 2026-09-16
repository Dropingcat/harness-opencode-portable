#!/usr/bin/env python3
"""Portable health check for harness integration."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def harness_root() -> Path:
    return Path(os.environ.get("OPENCODE_HARNESS_ROOT", Path(__file__).resolve().parents[1])).resolve()


def _strip_jsonc_comments(text: str) -> str:
    # Conservative line-comment stripping. Does not try to be a full JSONC parser.
    lines = []
    for line in text.splitlines():
        if not line.lstrip().startswith("//"):
            lines.append(line)
    return "\n".join(lines)


def _plugin_to_path(entry: str) -> Path:
    if entry.startswith("file://"):
        from urllib.parse import urlparse
        from urllib.request import url2pathname
        return Path(url2pathname(urlparse(entry).path))
    return Path(entry)


def check_plugin_loaded() -> tuple[bool, str]:
    config_path = Path(os.environ.get("OPENCODE_CONFIG_FILE", Path.home() / ".config" / "opencode" / "opencode.jsonc"))
    # Project-scoped native plugin config (.opencode/opencode.json) is the
    # canonical registration for the portable module; fall back to global.
    hroot = harness_root()
    project_cfg = hroot / ".opencode" / "opencode.json"
    if project_cfg.is_file():
        config_path = project_cfg
    if not config_path.exists():
        return False, f"Config not found: {config_path}"
    try:
        config = json.loads(_strip_jsonc_comments(config_path.read_text(encoding="utf-8-sig")))
    except Exception as exc:
        return False, f"Config parse error: {exc}"
    plugins = config.get("plugin", [])
    # Native plugin registration is a file:// URI into packages/opencode-harness-plugin/dist.
    for entry in plugins:
        if not isinstance(entry, str):
            continue
        if "opencode-harness-plugin" in entry:
            return True, f"Native plugin registered: {entry}"
    expected = (hroot / "packages" / "opencode-harness-plugin" / "dist" / "index.js").resolve()
    normalized = {str(_plugin_to_path(x).resolve()).replace("\\", "/") for x in plugins if isinstance(x, str)}
    if str(expected).replace("\\", "/") in normalized:
        return True, "Native plugin registered"
    return False, f"Plugin not registered: expected {expected}"


def check_mcp_definitions() -> tuple[bool, str]:
    script = harness_root() / "scripts" / "start_mcp_servers.py"
    if not script.exists():
        return False, f"validator missing: {script}"
    r = subprocess.run([sys.executable, str(script), "validate"], capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        return True, "stdio MCP definitions valid"
    return False, (r.stdout + "\n" + r.stderr).strip()


def check_guard_running() -> tuple[bool, str]:
    guard_path = Path(os.environ.get("DOC_GUARD_RUNNER", harness_root() / "guard" / "src" / "guard_runner.py"))
    if not guard_path.exists():
        return False, f"Guard script not found: {guard_path}"
    try:
        result = subprocess.run([sys.executable, str(guard_path), "--help"], capture_output=True, text=True, timeout=10)
        return (result.returncode == 0, "Guard runner executable" if result.returncode == 0 else result.stderr.strip())
    except Exception as exc:
        return False, f"Guard error: {exc}"


def check_db_accessible() -> tuple[bool, str]:
    db_path = os.environ.get("OPENCODE_SESSION_DB")
    if not db_path:
        return False, "OPENCODE_SESSION_DB not set"
    p = Path(db_path)
    if not p.exists():
        return False, f"DB not found: {p}"
    try:
        with sqlite3.connect(p) as conn:
            conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchone()
        return True, "DB accessible"
    except Exception as exc:
        return False, f"DB error: {exc}"


def main() -> int:
    checks = [
        ("Plugin Loaded", check_plugin_loaded),
        ("MCP Definitions", check_mcp_definitions),
        ("Guard Runner", check_guard_running),
        ("DB Accessible", check_db_accessible),
    ]
    all_ok = True
    for name, fn in checks:
        try:
            ok, msg = fn()
        except Exception as exc:
            ok, msg = False, f"unexpected error: {exc}"
        print(f"  [{'OK' if ok else 'FAIL'}] {name}: {msg}")
        all_ok &= ok
    print(f"\nOverall: {'HEALTHY' if all_ok else 'UNHEALTHY'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
