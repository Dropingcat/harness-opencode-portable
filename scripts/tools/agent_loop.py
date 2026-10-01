#!/usr/bin/env python3
"""agent_loop.py — итеративный запуск opencode-агента (TD-173).

Проблема: headless `opencode run` завершает проход, когда модель отвечает без
tool-вызовов (1-3 хода) — не «дожимает» задачу. Решение: opencode как framework,
runner рулит циклом через `--format json` и `--session`:

  1. Запустить: opencode run --format json --agent <a> -m <model> "<контракт>"
  2. Парсить события: step_finish.reason == "tool-calls"  -> модель работает;
     reason == "stop" -> проверить критерий завершения.
  3. Если stop и критерий не выполнен -> продолжить:
     opencode run -s <sessionID> -m <model> "<инструкция продолжить>"
  4. Лимит итераций + честный timeout.

Позволяет opencode запускать ЛЮБЫХ субагентов и рулить ими (внутренний task-цикл
тоже работает, но здесь — для внешних запусков/кросс-контура).

Usage:
  python agent_loop.py --agent claim-parser --model polza/deepseek/deepseek-v4-flash-0731 \
      --contract "<контракт>" [--max-iters 5] [--done-regex "клаймы извлечены"] [--timeout 900]
  python agent_loop.py --agent research-orchestrator --contract "..." --done-file claims.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_MODEL = "polza/deepseek/deepseek-v4-flash-0731"


def opencode_bin() -> str:
    return os.environ.get("OPENCODE_BIN", "opencode")


def run_once(agent: str, model: str, message: str, session: str | None = None,
             timeout: int = 900) -> tuple[int, list[dict], str]:
    """Один проход opencode run --format json. Возвращает (rc, события, session_id)."""
    cmd = [opencode_bin(), "run", "--format", "json", "-m", model, "--agent", agent]
    if session:
        cmd += ["-s", session]
    cmd.append(message)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          env=env, encoding="utf-8", errors="replace")
    events = []
    sid = session
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
            events.append(ev)
            if ev.get("sessionID"):
                sid = ev["sessionID"]
        except json.JSONDecodeError:
            continue
    return proc.returncode, events, sid


def analyze(events: list[dict]) -> dict:
    """Анализ событий: сколько tool_use, последний reason, последний текст."""
    tool_calls = sum(1 for e in events if e.get("type") == "tool_use")
    last_reason = None
    texts = []
    for e in events:
        t = e.get("type")
        if t == "step_finish":
            last_reason = e.get("part", {}).get("reason")
        elif t == "text":
            texts.append(e.get("part", {}).get("text", ""))
    return {"tool_calls": tool_calls, "last_reason": last_reason,
            "last_text": texts[-1] if texts else ""}


def done_condition(args, events: list[dict], session_state: dict) -> tuple[bool, str]:
    """Критерий завершения: done-file / done-regex / done-tool-call."""
    # 1. done-file (артефакт создан)
    if args.done_file:
        p = Path(args.done_file)
        if p.exists() and p.stat().st_size > 0:
            return True, f"артефакт создан: {p}"
    # 2. done-regex (текст модели содержит маркер)
    if args.done_regex:
        last = session_state.get("last_text", "")
        if re.search(args.done_regex, last, re.I):
            return True, f"regex в ответе: {args.done_regex}"
    # 3. done-tool-call (модель сделала целевой tool-вызов в этом проходе)
    if args.done_tool:
        for e in events:
            if e.get("type") == "tool_use":
                tool = e.get("part", {}).get("tool")
                if tool == args.done_tool:
                    return True, f"tool выполнен: {args.done_tool}"
    return False, ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Итеративный запуск opencode-агента (TD-173)")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--contract", required=True, help="промпт-контракт")
    ap.add_argument("--model", default=os.environ.get("OPENCODE_MODEL", DEFAULT_MODEL))
    ap.add_argument("--max-iters", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--done-file", default=None, help="артефакт-маркер завершения")
    ap.add_argument("--done-regex", default=None, help="regex в ответе модели = завершено")
    ap.add_argument("--done-tool", default=None, help="имя tool-вызова = завершено")
    ap.add_argument("--continue-prompt", default="Продолжай выполнение задачи до конца. Не завершай, пока не достигнут критерий завершения.",
                    help="промпт для следующей итерации")
    ap.add_argument("--session", default=None, help="начальный session id (возобновить)")
    args = ap.parse_args()

    session = args.session
    last_state = {}
    for i in range(1, args.max_iters + 1):
        print(f"=== Итерация {i}/{args.max_iters} (session={session or 'new'}) ===", flush=True)
        msg = args.contract if i == 1 else args.continue_prompt
        try:
            rc, events, sid = run_once(args.agent, args.model, msg, session, args.timeout)
        except subprocess.TimeoutExpired:
            print(f"ТАЙМАУТ {args.timeout}с на итерации {i}", file=sys.stderr)
            return 124
        session = sid or session
        st = analyze(events)
        last_state.update(st)
        print(f"  tool_calls={st['tool_calls']} last_reason={st['last_reason']} rc={rc}", flush=True)

        done, why = done_condition(args, events, last_state)
        if done:
            print(f"ГОТОВО: {why} (итог на итерации {i})", flush=True)
            print(f"session={session}", flush=True)
            return 0
        # модель завершила ход, но задача не выполнена -> продолжить
        if st["last_reason"] == "stop":
            print(f"  модель завершила ход (reason=stop), задача не выполнена -> продолжу", flush=True)
            continue
        # reason=tool-calls: модель сама продолжит в следующем проходе? Нет — проход завершён,
        # но она вызвала tools; продолжаем сессию
        continue

    print(f"ЛИМИТ ИТЕРАЦИЙ ({args.max_iters}) достигнут без завершения. session={session}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())