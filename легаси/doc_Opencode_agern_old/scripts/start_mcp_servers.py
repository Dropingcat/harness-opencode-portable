#!/usr/bin/env python3
"""Start/stop/health-check MCP servers from lifecycle config."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_env(value: str) -> str:
    """Resolve ${VAR} patterns in string."""
    import re
    def replace(match):
        var = match.group(1)
        return os.environ.get(var, match.group(0))
    return re.sub(r"\$\{([^}]+)\}", replace, value)


def start_server(server_config: dict) -> Optional[subprocess.Popen]:
    cmd = [resolve_env(part) for part in server_config["command"]]
    cwd = resolve_env(server_config.get("cwd", "."))
    env = os.environ.copy()
    for k, v in server_config.get("env", {}).items():
        env[k] = resolve_env(v)

    print(f"Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc


def wait_health(endpoint: str, timeout: int = 10) -> bool:
    import urllib.request
    import urllib.error
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(endpoint)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, TimeoutError):
            pass
        time.sleep(0.5)
    return False


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: start_mcp_servers.py [start|stop|health]")
        return 2

    action = sys.argv[1]
    config_path = Path(__file__).resolve().parents[1] / "config" / "mcp_lifecycle_config.json"
    config = load_json(config_path)

    servers = config.get("servers", {})
    global_cfg = config.get("global", {})
    max_concurrent = global_cfg.get("max_concurrent_starts", 2)

    if action == "start":
        # Start servers with concurrency limit
        procs: Dict[str, subprocess.Popen] = {}
        running = 0

        for name, cfg in servers.items():
            if not cfg.get("auto_start", True):
                continue
            while running >= max_concurrent:
                # Wait for one to finish starting
                time.sleep(0.5)
            proc = start_server(cfg)
            if proc:
                procs[name] = proc
                running += 1
            else:
                print(f"Failed to start {name}")

        # Wait for health checks
        for name, cfg in servers.items():
            if name in procs and cfg.get("health_check", {}).get("enabled"):
                endpoint = cfg["health_check"]["endpoint"]
                timeout = cfg.get("startup_timeout_sec", 10)
                if wait_health(endpoint, timeout):
                    print(f"{name}: healthy")
                else:
                    print(f"{name}: health check failed")
                    procs[name].terminate()
                    return 1

        print("All servers started")
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            for proc in procs.values():
                proc.terminate()
        return 0

    elif action == "stop":
        # This would need to track PIDs - simplified for now
        print("Stop not implemented in standalone mode")
        return 0

    elif action == "health":
        for name, cfg in servers.items():
            hc = cfg.get("health_check", {})
            if hc.get("enabled"):
                endpoint = hc["endpoint"]
                if wait_health(endpoint, 5):
                    print(f"{name}: OK")
                else:
                    print(f"{name}: FAIL")
        return 0

    return 0


if __name__ == "__main__":
    import re
    import sys
    raise SystemExit(main())
