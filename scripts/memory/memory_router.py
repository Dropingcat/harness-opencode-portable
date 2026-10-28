#!/usr/bin/env python3
"""memory_router.py — per-agent namespace + session tracker + switch routing (TD-175).

Детерминированный роутер памяти поверх L3 registry (memory_registry.json) и
моста memory_bridge.py. Решает технический долг TD-175:
- память была глобальной (один flat levels.L3.lessons), не было per-agent namespace;
- не было session tracker / task_hash;
- не было light-memory из прошлой сессии;
- не было роутинга при переключении агента.

Схема (сохраняет обратную совместимость с memory_bridge):
  config/memory_registry.json
    levels.L3.lessons                       # flat L3 уроки (существующий формат, НЕ трогаем)
    namespaces.<agent>.lesson_keys[]        # sha256 ключи уроков агента (подмножество lessons)
    namespaces.global.lesson_keys[]         # ключи глобального слоя (видят все агенты)
  config/session_tracker.json
    sessions[] = {session_id, agent, task_hash, created, light_summary, tech_debts_created[]}

Роутинг при переключении switch(agent):
  загружает ровно 3 слоя: global namespace + agent namespace + light_memory прошлой
  сессии того же агента. Чужие namespace НЕ подтягиваются.

Безопасность: селекторы namespaces берутся ТОЛЬКО из фиксированного списка
(Namespace хранится как {agent: [ключи]}, а не из untrusted текста). Секреты и
untrusted текст (логи, README, web) — только data, никогда не instructions.

Примеры:
  python memory_router.py register --session s1 --agent source-fetcher --task "fetch NKR"
  python memory_router.py switch --agent source-fetcher
  python memory_router.py add --agent source-fetcher --lesson "..." --reason R1 --evidence e1
  python memory_router.py light --agent source-fetcher
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Paths (module-owned). Env override: OPENCODE_HARNESS_ROOT
# ---------------------------------------------------------------------------
DEFAULT_HARNESS = Path(__file__).resolve().parents[2]
REGISTRY_REL = Path("config") / "memory_registry.json"
TRACKER_REL = Path("config") / "session_tracker.json"

# Фиксированный реестр агентов (запрещено динамически брать ключи из аргументов).
KNOWN_AGENTS: List[str] = [
    "global",
    "research-orchestrator",
    "source-fetcher",
    "fact-checker",
    "claim-parser",
    "code-worker",
    "code-reviewer",
    "writing-orchestrator",
]


def _harness_root() -> Path:
    import os

    env = os.environ.get("OPENCODE_HARNESS_ROOT")
    return Path(env) if env else DEFAULT_HARNESS


def _registry_path() -> Path:
    return _harness_root() / REGISTRY_REL


def _tracker_path() -> Path:
    return _harness_root() / TRACKER_REL


def _load_json(path: Path, fallback: Any) -> Any:
    # utf-8-sig transparently strips UTF-8 BOM (PowerShell Set-Content/Out-File пишет BOM)
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _task_hash(task_title: str, agent: str, date: str) -> str:
    raw = json.dumps(
        {"task": task_title, "agent": agent, "date": date},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _check_agent(agent: str) -> None:
    if agent not in KNOWN_AGENTS:
        raise ValueError(
            f"unknown agent {agent!r}; allowed: {', '.join(KNOWN_AGENTS)}"
        )


# ---------------------------------------------------------------------------
# Registry helpers (namespaces, обратно-совместимы с levels.L3.lessons)
# ---------------------------------------------------------------------------
def _registry() -> Dict[str, Any]:
    return _load_json(_registry_path(), {"version": 1, "kind": "memory_registry", "levels": {}})


def _save_registry(reg: Dict[str, Any]) -> None:
    _save_json(_registry_path(), reg)


def _ensure_namespaces(reg: Dict[str, Any]) -> Dict[str, Any]:
    """Возвращает namespaces-словарь; создаёт пустые для всех KNOWN_AGENTS, сохраняя остальные."""
    ns = reg.get("namespaces")
    if not isinstance(ns, dict):
        ns = {}
    for agent in KNOWN_AGENTS:
        entry = ns.get(agent)
        if not isinstance(entry, dict):
            entry = {"lesson_keys": []}
        if not isinstance(entry.get("lesson_keys"), list):
            entry["lesson_keys"] = []
        # дедупликация, сохраняя порядок
        seen, uniq = set(), []
        for k in entry["lesson_keys"]:
            if isinstance(k, str) and k not in seen:
                seen.add(k)
                uniq.append(k)
        entry["lesson_keys"] = uniq
        ns[agent] = entry
    reg["namespaces"] = ns
    return ns


# ---------------------------------------------------------------------------
# Session tracker
# ---------------------------------------------------------------------------
def _tracker() -> Dict[str, Any]:
    return _load_json(_tracker_path(), {"version": 1, "sessions": []})


def _save_tracker(tracker: Dict[str, Any]) -> None:
    _save_json(_tracker_path(), tracker)


def register(session_id: str, agent: str, task: str, light_summary: Optional[str] = None) -> Dict[str, Any]:
    """Создаёт запись сессии; task_hash = sha256(task_title + agent + date)."""
    _check_agent(agent)
    if not session_id or not isinstance(session_id, str):
        raise ValueError("session_id: required non-empty string")
    if not task or not isinstance(task, str):
        raise ValueError("task: required non-empty string")

    date = _now_iso().split("T")[0]
    session = {
        "session_id": session_id,
        "agent": agent,
        "task_hash": _task_hash(task, agent, date),
        "created": _now_iso(),
        "light_summary": light_summary or "",
        "tech_debts_created": [],
    }
    tracker = _tracker()
    sessions = tracker.setdefault("sessions", [])
    # апдейт по session_id+agent, если уже существует (idempotent)
    for existing in sessions:
        if existing.get("session_id") == session_id and existing.get("agent") == agent:
            existing.update(session)
            _save_tracker(tracker)
            return {"ok": True, "updated": True, **session}
    sessions.append(session)
    _save_tracker(tracker)
    return {"ok": True, "updated": False, **session}


def light_memory(agent: str, limit: int = 1) -> Dict[str, Any]:
    """Последняя light_summary прошлой сессии агента (по created desc)."""
    _check_agent(agent)
    tracker = _tracker()
    sessions = [s for s in tracker.get("sessions", [])
                if isinstance(s, dict) and s.get("agent") == agent]
    if not sessions:
        return {"ok": True, "agent": agent, "light_summary": None, "session": None}
    ordered = sorted(sessions, key=lambda s: str(s.get("created", "")), reverse=True)
    found = None
    for s in ordered:
        summary = s.get("light_summary")
        if summary and str(summary).strip():
            found = s
            break
    if found is None:
        return {"ok": True, "agent": agent, "light_summary": None, "session": None}
    return {
        "ok": True,
        "agent": agent,
        "light_summary": str(found.get("light_summary", "")),
        "session": {
            "session_id": found.get("session_id"),
            "created": found.get("created"),
            "task_hash": found.get("task_hash"),
            "tech_debts_created": found.get("tech_debts_created", []),
        },
    }


# ---------------------------------------------------------------------------
# Switch routing: global + agent + light_memory. Чужие namespace НЕ грузятся.
# ---------------------------------------------------------------------------
def _namespace_lessons(reg: Dict[str, Any], agent: str) -> List[Dict[str, Any]]:
    lessons = reg.get("levels", {}).get("L3", {}).get("lessons", {})
    if not isinstance(lessons, dict):
        return []
    ns = reg.get("namespaces", {})
    entry = ns.get(agent) if isinstance(ns, dict) else None
    keys = entry.get("lesson_keys", []) if isinstance(entry, dict) else []
    out = []
    for key in keys:
        lesson = lessons.get(key)
        if isinstance(lesson, dict):
            out.append({"key": key, **lesson})
    return out


def switch(agent: str) -> Dict[str, Any]:
    """Загружает ровно global + agent + light_memory(agent). Read-only: не пишет в registry."""
    _check_agent(agent)
    if agent == "global":
        raise ValueError("switch: 'global' is a shared layer, not a routable agent")
    reg = _registry()
    _ensure_namespaces(reg)  # только in-memory нормализация, без сохранения на диск
    loaded = {
        "agent": agent,
        "loaded_slices": ["global", agent],
        "global": _namespace_lessons(reg, "global"),
        agent: _namespace_lessons(reg, agent),
        "light_memory": light_memory(agent),
        "ok": True,
    }
    return loaded


# ---------------------------------------------------------------------------
# add: per-agent namespace поверх существующего bridge-формата
# ---------------------------------------------------------------------------
def add_lesson(agent: str, lesson_text: str, reason_codes: List[str],
               evidence_refs: List[str], task_id: Optional[str] = None,
               snapshot_id: Optional[str] = None) -> Dict[str, Any]:
    """Добавляет урок в flat L3 и привязывает его ключ к namespace агента."""
    _check_agent(agent)
    if agent == "global":
        raise ValueError("add: 'global' is a shared layer; use bridge.add directly or add --agent <real>")
    if not lesson_text or not isinstance(lesson_text, str) or not lesson_text.strip():
        raise ValueError("lesson: required non-empty string")
    if not isinstance(reason_codes, list) or not reason_codes or not all(isinstance(x, str) and x for x in reason_codes):
        raise ValueError("reason_codes: required non-empty list of strings")
    if not isinstance(evidence_refs, list) or not evidence_refs or not all(isinstance(x, str) and x for x in evidence_refs):
        raise ValueError("evidence_refs: required non-empty list of strings")

    # используем тот же stable_key, что и memory_bridge (совместимость дедупликации)
    payload = {
        "lesson_text": lesson_text,
        "reason_codes": sorted(set(reason_codes)),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    key = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    reg = _registry()
    l3 = reg.setdefault("levels", {}).setdefault("L3", {})
    lessons = l3.setdefault("lessons", {})
    entry = lessons.get(key, {
        "lesson_text": lesson_text,
        "reason_codes": sorted(set(reason_codes)),
        "evidence_refs": [],
        "sources": [],
        "admissions": 0,
    })
    entry["evidence_refs"] = sorted(set(entry.get("evidence_refs", []) + evidence_refs))
    src = {"task_id": task_id, "snapshot_id": snapshot_id, "added_via": "memory_router.add"}
    if src not in entry.get("sources", []):
        entry.setdefault("sources", []).append(src)
    entry["admissions"] = int(entry.get("admissions", 0)) + 1
    lessons[key] = entry

    ns = _ensure_namespaces(reg)
    # idempotent: повторный add того же stable_key не дублирует ссылку в namespace
    if key not in ns[agent]["lesson_keys"]:
        ns[agent]["lesson_keys"].append(key)
    _save_registry(reg)
    return {"ok": True, "key": key, "admissions": entry["admissions"], "agent": agent}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_register(args: argparse.Namespace) -> int:
    try:
        out = register(args.session, args.agent, args.task, light_summary=args.summary)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_switch(args: argparse.Namespace) -> int:
    try:
        out = switch(args.agent)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    try:
        out = add_lesson(args.agent, args.lesson, args.reason, args.evidence,
                         task_id=args.task_id, snapshot_id=args.snapshot_id)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0


def cmd_light(args: argparse.Namespace) -> int:
    try:
        out = light_memory(args.agent)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0


def main() -> int:
    # Windows-консоль (cp1251) не кодирует кириллицу/юникод из lesson-текстов; stdout -> UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass  # не-файловые stdout или старая версия Python — оставляем как есть

    parser = argparse.ArgumentParser(prog="memory_router", description="Per-agent memory namespaces + session tracker + switch routing (TD-175)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_reg = sub.add_parser("register")
    p_reg.add_argument("--session", required=True, help="session id")
    p_reg.add_argument("--agent", required=True, choices=KNOWN_AGENTS, help="agent name")
    p_reg.add_argument("--task", required=True, help="task title (для task_hash)")
    p_reg.add_argument("--summary", default=None, help="light_summary (опционально)")
    p_reg.set_defaults(fn=cmd_register)

    p_sw = sub.add_parser("switch")
    p_sw.add_argument("--agent", required=True, choices=KNOWN_AGENTS, help="agent to switch to")
    p_sw.set_defaults(fn=cmd_switch)

    p_add = sub.add_parser("add")
    p_add.add_argument("--agent", required=True, choices=KNOWN_AGENTS, help="agent namespace")
    p_add.add_argument("--lesson", required=True, help="lesson text")
    p_add.add_argument("--reason", action="append", required=True, help="reason code (repeatable)")
    p_add.add_argument("--evidence", action="append", required=True, help="evidence ref (repeatable)")
    p_add.add_argument("--task-id", default=None, help="optional task id")
    p_add.add_argument("--snapshot-id", default=None, help="optional snapshot id")
    p_add.set_defaults(fn=cmd_add)

    p_lt = sub.add_parser("light")
    p_lt.add_argument("--agent", required=True, choices=KNOWN_AGENTS, help="agent name")
    p_lt.set_defaults(fn=cmd_light)

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())