#!/usr/bin/env python3
"""Health check for runtime integration."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


def check_plugin_loaded() -> tuple[bool, str]:
    """Check if plugin is registered in opencode.jsonc."""
    config_path = Path.home() / ".config" / "opencode" / "opencode.jsonc"
    if not config_path.exists():
        return False, f"Config not found: {config_path}"

    try:
        content = config_path.read_text(encoding="utf-8")
        lines = []
        for line in content.splitlines():
            if not line.strip().startswith("//"):
                lines.append(line)
        config = json.loads("\n".join(lines))

        plugins = config.get("plugin", [])
        plugin_path = "E:/Documents/Документы/doc_Opencode_agern/plugins/tool-skill-contract-router.ts"
        plugin_uri = "file:///E:/Documents/%D0%94%D0%BE%D0%BA%D1%83%D0%BC%D0%B5%D0%BD%D1%82%D1%8B/doc_Opencode_agern/plugins/tool-skill-contract-router.ts"
        if plugin_path in plugins or plugin_uri in plugins:
            return True, "Plugin registered"
        return False, "Plugin not registered in opencode.jsonc"
    except Exception as e:
        return False, f"Config parse error: {e}"


def check_mcp_servers() -> tuple[bool, str]:
    """Check if MCP servers are responding."""
    servers = [
        ("coder_router", "http://localhost:8001/health"),
        ("academic_search", "http://localhost:8002/health"),
        ("doc_extract", "http://localhost:8003/health"),
        ("searxng_search", "http://localhost:8004/health"),
    ]

    failed = []
    for name, url in servers:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status != 200:
                    failed.append(f"{name}: HTTP {resp.status}")
        except Exception as e:
            failed.append(f"{name}: {e}")

    if failed:
        return False, "; ".join(failed)
    return True, "All MCP servers healthy"


def check_guard_running() -> tuple[bool, str]:
    """Check if doc_guard can run."""
    guard_path = os.environ.get("DOC_GUARD_ENTRYPOINT", "E:/Documents/Документы/doc_Opencode_agern/guard/src/session_guard.py")
    if not os.path.exists(guard_path):
        return False, f"Guard script not found: {guard_path}"

    try:
        result = subprocess.run(
            ["python", guard_path, "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, "Guard script executable"
        return False, f"Guard failed: {result.stderr}"
    except Exception as e:
        return False, f"Guard error: {e}"


def check_db_accessible() -> tuple[bool, str]:
    """Check if OpenCode session DB is accessible."""
    db_path = os.environ.get("OPENCODE_SESSION_DB")
    if not db_path:
        return False, "OPENCODE_SESSION_DB not set"

    if not os.path.exists(db_path):
        return False, f"DB not found: {db_path}"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        cursor.fetchone()
        conn.close()
        return True, "DB accessible"
    except Exception as e:
        return False, f"DB error: {e}"


def main() -> int:
    checks = [
        ("Plugin Loaded", check_plugin_loaded),
        ("MCP Servers", check_mcp_servers),
        ("Guard Running", check_guard_running),
        ("DB Accessible", check_db_accessible),
    ]

    all_ok = True
    results = []

    for name, check_fn in checks:
        try:
            ok, msg = check_fn()
            status = "OK" if ok else "FAIL"
            results.append(f"  [{status}] {name}: {msg}")
            if not ok:
                all_ok = False
        except Exception as e:
            results.append(f"  [ERROR] {name}: {e}")
            all_ok = False

    for r in results:
        print(r)

    print(f"\nOverall: {'HEALTHY' if all_ok else 'UNHEALTHY'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
