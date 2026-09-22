#!/usr/bin/env python3
"""Delegation scoreboard — детерминированный счётчик «игры делегирования» фабрики кода.

Правило игры (закреплено в agents/code-orchestrator.md):
  - Единственный способ набрать очки — прогнать модуль через фабрику:
      worker -> reviewer -> tester -> finalize.
  - Оркестратор НЕ пишет код сам (edit/write у него запрещены permission-конфигом).
  - Само-кодинг в обход (bash-запись) фиксируется как self_edit и штрафуется.

Хранилище: HARNESS/.runs/delegation_ledger.db (вне git).
API детерминирован: любой фикс («забыл учесть») — через этот же скрипт, не в тексте.

Примеры:
  python delegation_score.py record submit --task TD-001 --module m1 --actor worker --note "ok"
  python delegation_score.py record finalize --task TD-001
  python delegation_score.py record self_edit --task TD-001 --note "попытка кодить сам"
  python delegation_score.py board
  python delegation_score.py stats --task TD-001
  python delegation_score.py reset
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Actions и их вклад в счёт (политика — в коде, не в данных)
ACTION_SCORE = {
    "submit_worker": 1,
    "submit_reviewer": 1,   # ревьюер PASS = модуль прошёл гейт
    "submit_tester": 1,
    "tribunal": 5,           # разрешил конфликт процессом, а не самовольным правком
    "finalize": 5,           # задача доведена до DONE через фабрику
    "self_edit": -10,        # оркестратор полез кодить сам (нарушение контракта)
    "assist_read": 0,        # чтение кода/отчётов — норм, не штрафуется
}
VALID_ACTIONS = sorted(ACTION_SCORE)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT DEFAULT (datetime('now')),
    action      TEXT NOT NULL,
    task_id     TEXT NOT NULL,
    module      TEXT,
    actor       TEXT,
    note        TEXT,
    score       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_task ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);
"""


def _harness_root() -> Path:
    env = os.environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def _db_path() -> Path:
    return (_harness_root() / ".runs" / "delegation_ledger.db")


def _connect() -> sqlite3.Connection:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    conn.executescript(SCHEMA)
    return conn


def _emit(obj: dict) -> None:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))


def cmd_record(args: argparse.Namespace) -> int:
    action = args.action
    if action not in ACTION_SCORE:
        _emit({"ok": False, "error": f"unknown action {action!r}; allowed: {VALID_ACTIONS}"})
        return 2
    score = ACTION_SCORE[action]
    task_id = args.task
    if not task_id:
        _emit({"ok": False, "error": "task is required"})
        return 2
    try:
        conn = _connect()
        cur = conn.execute(
            """INSERT INTO events (action, task_id, module, actor, note, score)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (action, task_id, args.module, args.actor, args.note, score),
        )
        conn.commit()
        row = conn.execute(
            "SELECT SUM(score) FROM events WHERE task_id = ?", (task_id,)
        ).fetchone()
        total = row[0] if row[0] is not None else 0
        _emit({
            "ok": True,
            "event_id": cur.lastrowid,
            "action": action,
            "score": score,
            "task_id": task_id,
            "task_total": total,
            "db": str(_db_path()),
        })
        return 0
    except sqlite3.Error as exc:
        _emit({"ok": False, "error": str(exc)})
        return 2


def cmd_board(args: argparse.Namespace) -> int:
    rows = _connect().execute(
        """SELECT task_id,
                  COUNT(*) FILTER (WHERE action = 'self_edit') AS self_edits,
                  COUNT(*) FILTER (WHERE action = 'finalize')  AS finalized,
                  SUM(score) AS total
           FROM events
           GROUP BY task_id
           ORDER BY total DESC, task_id"""
    ).fetchall()
    table = []
    for task_id, self_edits, finalized, total in rows:
        table.append({
            "task_id": task_id,
            "self_edits": self_edits,
            "finalized": finalized,
            "score": total if total is not None else 0,
        })
    _emit({"ok": True, "db": str(_db_path()), "leaderboard": table})
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    conn = _connect()
    if args.task:
        rows = conn.execute(
            "SELECT action, COUNT(*) AS n, SUM(score) AS sc FROM events WHERE task_id = ? GROUP BY action ORDER BY action",
            (args.task,),
        ).fetchall()
        by_action = {r[0]: {"count": r[1], "sum": r[2]} for r in rows}
        total = conn.execute("SELECT SUM(score) FROM events WHERE task_id = ?", (args.task,)).fetchone()
        _emit({
            "ok": True,
            "task_id": args.task,
            "total_score": total[0] if total[0] is not None else 0,
            "by_action": by_action,
            "db": str(_db_path()),
        })
        return 0
    rows = conn.execute(
        "SELECT action, COUNT(*) AS n, SUM(score) AS sc FROM events GROUP BY action ORDER BY action"
    ).fetchall()
    _emit({
        "ok": True,
        "by_action": {r[0]: {"count": r[1], "sum": r[2]} for r in rows},
        "db": str(_db_path()),
    })
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    db = _db_path()
    if db.exists():
        db.unlink()
    _emit({"ok": True, "db": str(db), "reset": True})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="delegation_score", description="Delegation game scoreboard")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rec = sub.add_parser("record", help="record an event")
    p_rec.add_argument("action", choices=sorted(ACTION_SCORE), help="submit_worker|submit_reviewer|submit_tester|tribunal|finalize|self_edit|assist_read")
    p_rec.add_argument("--task", required=True, help="task id")
    p_rec.add_argument("--module", default=None)
    p_rec.add_argument("--actor", default=None, help="worker|reviewer|tester|orchestrator|auditor")
    p_rec.add_argument("--note", default=None)
    p_rec.set_defaults(fn=cmd_record)

    p_brd = sub.add_parser("board", help="leaderboard by task")
    p_brd.set_defaults(fn=cmd_board)

    p_st = sub.add_parser("stats", help="stats, optionally by task")
    p_st.add_argument("--task", default=None)
    p_st.set_defaults(fn=cmd_stats)

    p_rs = sub.add_parser("reset", help="wipe ledger (dev/test only)")
    p_rs.set_defaults(fn=cmd_reset)

    args = parser.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())