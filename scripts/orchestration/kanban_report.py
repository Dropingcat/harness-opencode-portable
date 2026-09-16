#!/usr/bin/env python3
"""kanban_report.py — универсальный отчёт в глобальный канбан harness.

Проблема: писатель (writing-orchestrator) не знал, какой agent_id ставить
(code-factory или свой). Решение: РЕЕСТР контуров — каждый агент отчитывается
своим agent_id + group_name (секция). Хелпер сам резолвит group по agent_id,
регистрирует агента с правильной группой и пишет статус.

Секции (group_name):
  code-factory  — код-контур (code-orchestrator, coder-worker, reviewers...)
  writing       — писатель (writing-orchestrator, article-writer)
  research      — ресёрчер (research-orchestrator, claim-parser, fact-checker...)
  infra         — инфраструктура harness

Использование (Python):
  from kanban_report import report
  report(agent_id="writing-orchestrator", task_id="NKR-CH1-001",
         task_name="DOM главы 1", status="DONE", phase="DOM",
         progress="10/10", message="...")

Использование (CLI):
  python kanban_report.py <agent_id> <task_id> <status> [phase] [progress] [message]
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from typing import Optional

# корень harness (относительно scripts/orchestration)
_HARNESS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(_HARNESS_ROOT, ".kanban.db")

# реестр контуров: agent_id -> (name, group_name)
AGENT_REGISTRY: dict[str, tuple[str, str]] = {
    # --- код-контур (group: code-factory) ---
    "code-factory": ("Code Factory", "code-factory"),
    "code-orchestrator": ("Code Orchestrator", "code-factory"),
    "coder-worker": ("Coder Worker", "code-factory"),
    "code-reviewer": ("Code Reviewer", "code-factory"),
    "code-tester": ("Code Tester", "code-factory"),
    "code-auditor": ("Code Auditor", "code-factory"),
    # --- писатель (group: writing) ---
    "writing-orchestrator": ("Writing Orchestrator", "writing"),
    "article-writer": ("Article Writer", "writing"),
    "writer-review": ("Writer Review", "writing"),
    # --- ресёрчер (group: research) ---
    "research-orchestrator": ("Research Orchestrator", "research"),
    "researcher": ("Researcher", "research"),
    "claim-parser": ("Claim Parser", "research"),
    "fact-checker": ("Fact Checker", "research"),
    "source-fetcher": ("Source Fetcher", "research"),
    "synthesizer": ("Synthesizer", "research"),
    "tribunal-judge": ("Tribunal Judge", "research"),
    # --- инфраструктура ---
    "harness": ("Harness Infra", "infra"),
}


def _resolve(agent_id: str) -> tuple[str, str]:
    """agent_id -> (name, group_name). Неизвестный агент -> свой id + 'default'."""
    name, group = AGENT_REGISTRY.get(agent_id, (agent_id, "default"))
    return name, group


def _init_db(db_path: str = DB_PATH) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY, name TEXT NOT NULL,
                group_name TEXT DEFAULT 'default',
                created_at TEXT DEFAULT (datetime('now')),
                last_seen TEXT DEFAULT (datetime('now')))"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS statuses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL REFERENCES agents(id),
                task_id TEXT, task_name TEXT, status TEXT NOT NULL DEFAULT 'WORKING',
                phase TEXT, progress TEXT, message TEXT,
                created_at TEXT DEFAULT (datetime('now')))"""
        )


def register_agent(agent_id: str, db_path: str = DB_PATH) -> None:
    name, group = _resolve(agent_id)
    _init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute("SELECT id FROM agents WHERE id = ?", (agent_id,))
        if cur.fetchone():
            conn.execute(
                "UPDATE agents SET name = ?, group_name = ?, last_seen = datetime('now') WHERE id = ?",
                (name, group, agent_id),
            )
        else:
            conn.execute(
                "INSERT INTO agents (id, name, group_name) VALUES (?, ?, ?)",
                (agent_id, name, group),
            )


def report(
    agent_id: str,
    task_id: Optional[str] = None,
    task_name: str = "",
    status: str = "WORKING",
    phase: Optional[str] = None,
    progress: str = "",
    message: str = "",
    db_path: str = DB_PATH,
) -> int:
    """Опубликовать статус агента в глобальный канбан (с резолвом секции)."""
    register_agent(agent_id, db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO statuses
               (agent_id, task_id, task_name, status, phase, progress, message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (agent_id, task_id, task_name, status, phase, progress, message),
        )
        conn.execute(
            "UPDATE agents SET last_seen = datetime('now') WHERE id = ?", (agent_id,)
        )
        return cur.lastrowid


def board(group_name: Optional[str] = None, agent_id: Optional[str] = None,
          limit: int = 20, db_path: str = DB_PATH) -> list[dict]:
    """Доска с секциями: JOIN agents -> group_name; фильтр по группе/агенту."""
    where, params = [], []
    if group_name:
        where.append("a.group_name = ?")
        params.append(group_name)
    if agent_id:
        where.append("s.agent_id = ?")
        params.append(agent_id)
    sql = """SELECT s.*, a.name as agent_name, a.group_name
             FROM statuses s JOIN agents a ON s.agent_id = a.id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.created_at DESC LIMIT ?"
    params.append(limit)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def summary(groups: Optional[list[str]] = None, db_path: str = DB_PATH) -> str:
    """Сводка по секциям (group_name) — разведённые секции канбана."""
    _init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        all_rows = conn.execute(
            "SELECT s.*, a.group_name, a.name as agent_name FROM statuses s "
            "JOIN agents a ON s.agent_id = a.id "
            "ORDER BY s.created_at DESC LIMIT 50"
        ).fetchall()
    # группируем по секциям
    by_group: dict[str, list] = {}
    for r in all_rows:
        d = dict(r)
        g = d.get("group_name") or "default"
        by_group.setdefault(g, []).append(d)
    icon = {"WORKING": "🔧", "QUEUE": "📥", "BLOCKED": "🚫",
            "REVIEW": "👁", "DONE": "✅", "FAILED": "❌"}
    lines = ["📋 **Глобальный канбан (по секциям):**\n"]
    for g in sorted(by_group):
        if groups and g not in groups:
            continue
        lines.append(f"### [{g}]")
        for row in by_group[g][:8]:
            ic = icon.get(row["status"], "📄")
            agent = row.get("agent_name") or row["agent_id"]
            task = row["task_name"] or ""
            prog = f" [{row['progress']}]" if row.get("progress") else ""
            msg = f" — {row['message']}" if row.get("message") else ""
            lines.append(f"  {ic} **{agent}**: {task}{prog}{msg}")
        lines.append("")
    return "\n".join(lines) if len(lines) > 1 else "📋 Доска пуста."


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(summary())
    elif args[0] == "board":
        g = args[1] if len(args) > 1 else None
        a = args[2] if len(args) > 2 else None
        for row in board(group_name=g, agent_id=a):
            print(f"[{row['created_at'][:19]}] [{row.get('group_name','')}] "
                  f"{row.get('agent_name', row['agent_id']):22s} [{row['status']}] "
                  f"{(row['task_name'] or ''):30s} {row['progress'] or ''}")
    elif args[0] == "report" and len(args) >= 3:
        agent, task_id, status = args[1], args[2], args[3] if len(args) > 3 else "WORKING"
        phase = args[4] if len(args) > 4 else None
        progress = args[5] if len(args) > 5 else ""
        message = " ".join(args[6:]) if len(args) > 6 else ""
        rid = report(agent, task_id=task_id, status=status, phase=phase,
                     progress=progress, message=message)
        name, group = _resolve(agent)
        print(f"✅ [{group}] {name}: [{status}] {task_id} {progress} {message} (id={rid})")
    else:
        print(__doc__)