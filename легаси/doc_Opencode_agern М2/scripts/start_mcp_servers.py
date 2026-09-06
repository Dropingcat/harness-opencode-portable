#!/usr/bin/env python3
"""Validate MCP lifecycle configuration.

All bundled MCP servers currently use stdio transport. Their lifecycle belongs to the
MCP host (OpenCode), not to a detached daemon manager. This script intentionally does
not pretend that stdio servers expose HTTP /health endpoints.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_env(value: str) -> str:
    import re
    def replace(match):
        var = match.group(1)
        if var == "PYTHON_BIN":
            return os.environ.get(var, sys.executable)
        if var == "OPENCODE_HARNESS_ROOT":
            return os.environ.get(var, str(Path(__file__).resolve().parents[1]))
        return os.environ.get(var, match.group(0))
    return re.sub(r"\$\{([^}]+)\}", replace, value)


def _resolved_command(cfg: dict) -> tuple[list[str], str]:
    cmd = [resolve_env(str(part)) for part in cfg["command"]]
    cwd = resolve_env(str(cfg.get("cwd", ".")))
    return cmd, cwd


def validate_server(name: str, cfg: dict) -> tuple[bool, str]:
    transport = cfg.get("transport", "stdio")
    if transport != "stdio":
        return False, f"unsupported transport in this manager: {transport}"
    cmd, cwd = _resolved_command(cfg)
    if not cmd:
        return False, "empty command"
    exe = shutil.which(cmd[0]) or (cmd[0] if Path(cmd[0]).exists() else None)
    if not exe:
        return False, f"executable not found: {cmd[0]}"
    if not Path(cwd).exists():
        return False, f"cwd not found: {cwd}"
    if len(cmd) > 1 and cmd[0].lower().startswith("python"):
        script = Path(cmd[1])
        if not script.exists():
            return False, f"server script not found: {script}"
        r = subprocess.run([sys.executable, "-m", "py_compile", str(script)], capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return False, f"py_compile failed: {r.stderr.strip()}"
    return True, "stdio config valid; lifecycle is host-managed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate host-managed stdio MCP server definitions")
    parser.add_argument("action", choices=["validate", "health", "start", "stop"])
    args = parser.parse_args()
    config_path = Path(__file__).resolve().parents[1] / "config" / "mcp_lifecycle_config.json"
    config = load_json(config_path)
    servers = config.get("servers", {})

    if args.action in {"start", "stop"}:
        print("Bundled MCP servers use stdio transport; OpenCode/MCP host must start and stop them. Use 'validate' to check definitions.")
        return 2

    ok_all = True
    for name, cfg in servers.items():
        ok, msg = validate_server(name, cfg)
        print(f"{name}: {'OK' if ok else 'FAIL'} - {msg}")
        ok_all &= ok
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
