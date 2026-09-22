#!/usr/bin/env python3
"""start_searxng.py — авто-запуск локального SearXNG (mini-searxng).

TD-128: поднимает mini-searxng (mcp/mini_searxng.py) на 127.0.0.1:8888,
если он не запущен. Даёт JSON-интерфейс /search?q=&format=json для
searxng_search_server.py (MCP) и webfetch-fallback.

Usage:
  python start_searxng.py          # запустить, если не работает
  python start_searxng.py --check  # только проверить статус
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
MINI = (HERE.parent / "mcp" / "mini_searxng.py").resolve()  # scripts/tools/../mcp
URL = "http://127.0.0.1:8888/healthz"
PYTHON = sys.executable


def is_up(timeout: int = 3) -> bool:
    try:
        with urllib.request.urlopen(URL, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def start() -> int:
    if is_up():
        print("SearXNG (mini-searxng) уже работает: 127.0.0.1:8888")
        return 0
    if not MINI.exists():
        print(f"ERROR: mini-searxng не найден: {MINI}", file=sys.stderr)
        return 2
    # запуск в фоне (detached), лог в C:\Temp\opencode
    import os
    log_dir = Path(os.environ.get("TEMP", "C:/Temp/opencode"))
    log_dir.mkdir(parents=True, exist_ok=True)
    err = log_dir / "mini_searxng_err.log"
    out = log_dir / "mini_searxng_out.log"
    with open(out, "ab") as fo, open(err, "ab") as fe:
        proc = subprocess.Popen([PYTHON, str(MINI), "--port", "8888"],
                                stdout=fo, stderr=fe,
                                creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
                                cwd=str(MINI.parent))
    # ждём поднятия
    for _ in range(20):
        time.sleep(0.5)
        if is_up():
            print(f"OK: mini-searxng запущен (pid {proc.pid}) на 127.0.0.1:8888")
            return 0
    print("WARN: сервер не ответил за 10s, проверь лог", file=sys.stderr)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="только проверить статус")
    args = ap.parse_args()
    if args.check:
        print("up" if is_up() else "down")
        return 0 if is_up() else 1
    return start()


if __name__ == "__main__":
    raise SystemExit(main())