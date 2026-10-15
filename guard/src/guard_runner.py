#!/usr/bin/env python3
"""
guard_runner.py — единая точка вызова trust-boundary guard для runtime.

Flow:
  P0 (session_guard.py) — детерминированный сигнатурный скан (без сети).
     PASS → продолжает на P2 (если настроен)
     FAIL → BLOCK (fail-closed, no network needed)
  P2 (semantic_layer.py) — семантический классификатор (cloud polza / local ollama).
     Активен только если:
       - ENV POLZA_API_KEY задан  (для cloud), или
       - local ollama доступен    (для local provider)
     P2 недоступен/без ключа → DEGRADED (по strictness policy), НЕ тихий PASS.

Вход: opencode session DB (или путь к любому json/sqlite для теста).
Выбор provider: --provider local|cloud (default cloud).
Ключ: env POLZA_API_KEY (НЕ в конфиге, никогда не светить).

Примеры:
  python guard_runner.py <opencode.db> --json
  python guard_runner.py <db> --provider local --json
  python guard_runner.py --list-models
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows/mixed consoles print UTF-8 (✅, кириллица). Force UTF-8 on stdio
# to avoid UnicodeEncodeError in cp1251 when emitting guard verdicts.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def harness_root() -> Path:
    return Path(__file__).resolve().parents[2]


def p0_path() -> Path:
    p = os.environ.get("DOC_GUARD_ENTRYPOINT")
    if p:
        return Path(p)
    return harness_root() / "guard" / "src" / "session_guard.py"


def p2_path() -> Path:
    return harness_root() / "guard" / "src" / "semantic_layer.py"


def default_config() -> Path:
    cfg = os.environ.get("DOC_GUARD_CONFIG")
    if cfg:
        return Path(cfg)
    return Path.home() / ".config" / "opencode" / "guard_config.json"


def run_p0(db: str, session: str | None) -> dict:
    cmd = [sys.executable, str(p0_path()), db, "--json"]
    if session:
        cmd += ["--session", session]
    return _run_stage(cmd, 120)


def _run_stage(cmd, timeout):
    """Never echo child output, exception text, or credentials."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        parsed = json.loads(r.stdout)
        if not isinstance(parsed, dict) or parsed.get("verdict") not in ("PASS", "FAIL", "ERROR", "DEGRADED"):
            return {"verdict": "ERROR", "reason": "invalid_stage_output", "exit": r.returncode}
        # Only carry protocol fields; raw findings may contain secrets.
        result = {"verdict": parsed["verdict"], "exit": r.returncode}
        if isinstance(parsed.get("coverage"), dict):
            result["coverage"] = {k: parsed["coverage"].get(k) for k in
                                  ("complete", "total_parts", "covered_parts", "required_parts", "classified_parts")}
        if r.returncode != 0 and result["verdict"] == "PASS":
            result.update(verdict="ERROR", reason="nonzero_exit")
        return result
    except subprocess.TimeoutExpired:
        return {"verdict": "ERROR", "reason": "timeout"}
    except Exception:
        return {"verdict": "ERROR", "reason": "stage_execution_error"}


def run_p2(db: str, provider: str, session: str | None, config: str | None) -> dict:
    key = os.environ.get("POLZA_API_KEY")
    cfg = config or str(default_config())
    if not Path(cfg).exists():
        return {"verdict": "DEGRADED", "reason": "no_config"}
    if provider == "cloud" and not key:
        return {"verdict": "DEGRADED", "reason": "no_polza_key", "detail": "POLZA_API_KEY not set in env (cloud provider)"}
    if provider == "cloud" and key:
        # api-key приоритет над конфигом
        cmd = [sys.executable, str(p2_path()), db, "--provider", "cloud", "--json",
               "--config", cfg]
    else:
        cmd = [sys.executable, str(p2_path()), db, "--provider", "local", "--json",
               "--config", cfg]
    if session:
        cmd += ["--session", session]
    try:
        timeout = max(1.0, int(os.environ.get("DOC_GUARD_TIMEOUT_MS", "180000")) / 1000.0)
        return _run_stage(cmd, timeout)
    except Exception:
        return {"verdict": "ERROR", "reason": "stage_configuration_error"}


def _passed(result):
    return (isinstance(result, dict) and result.get("verdict") == "PASS"
            and type(result.get("exit")) is int and result["exit"] == 0)


def _complete(result):
    c = result.get("coverage") if isinstance(result, dict) else None
    return (isinstance(c, dict) and c.get("complete") is True
            and all(type(c.get(k)) is int and c[k] >= 0 for k in
                    ("total_parts", "covered_parts", "required_parts", "classified_parts"))
            and c["total_parts"] > 0 and c["covered_parts"] == c["total_parts"]
            and c["required_parts"] == c["classified_parts"]
            and c["required_parts"] <= c["total_parts"])


def guard(db: str, provider: str = "cloud", session: str | None = None, config: str | None = None) -> dict:
    """Run P0 then P2; compose verdict. Fail-closed."""
    try:
        p0 = run_p0(db, session)
    except Exception:
        p0 = {"verdict": "ERROR", "reason": "stage_execution_error"}

    if not _passed(p0):
        return {"ok": False, "verdict": "BLOCK", "stage": "P0", "reason": "P0 not successful"}

    try:
        p2 = run_p2(db, provider, session, config)
    except Exception:
        p2 = {"verdict": "ERROR", "reason": "stage_execution_error"}

    if not _passed(p2) or not _complete(p2):
        return {"ok": False, "verdict": "BLOCK", "stage": "P2", "reason": "P2 not successful and complete"}

    return {"ok": True, "verdict": "PASS", "stage": "P0+P2", "p0": p0, "p2": p2}


def main() -> int:
    parser = argparse.ArgumentParser(description="Trust-boundary guard runner (P0 + P2)")
    parser.add_argument("db", nargs="?", help="opencode.db path")
    parser.add_argument("--provider", choices=["local", "cloud"], default="cloud")
    parser.add_argument("--session", default=None)
    parser.add_argument("--config", default=None, help="override guard config path")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--list-models", action="store_true", help="list providers/models from config")
    args = parser.parse_args()

    if args.list_models:
        r = subprocess.run([sys.executable, str(p2_path()), "--config", args.config or str(default_config()), "--list-models"],
                           capture_output=True, text=True, timeout=30)
        print(r.stdout or r.stderr)
        return r.returncode

    if not args.db:
        print("ERROR: missing positional 'db'", file=sys.stderr)
        return 2

    result = guard(args.db, provider=args.provider, session=args.session, config=args.config)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if result.get("ok") else result.get("verdict")
        print(f"GUARD {status} (stage={result.get('stage')}) reason={result.get('reason', '')}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
