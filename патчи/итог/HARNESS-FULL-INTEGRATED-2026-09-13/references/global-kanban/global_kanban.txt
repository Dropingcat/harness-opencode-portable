#!/usr/bin/env python3
"""
Глобальный канбан — общая доска статусов всех агентов.

Каждый агент (ТРИЗ-кодер, погодный бот, bridge, cron-задача)
пишет сюда свои статусы. Любой может прочитать и узнать «чё там у других».

Использование из Python:
    from global_kanban import GlobalKanban
    gk = GlobalKanban()
    gk.report("triz-coder", "Phase C", "WORKING", "3/8 steps", "рефакторинг core.py")

Использование из шелла:
    kanban-report triz-coder "Phase C" WORKING "3/8" "рефакторинг"
    kanban-board
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


DB_PATH = "/home/orangepi/.hermes/kanban/global.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    group_name  TEXT DEFAULT 'default',
    created_at  TEXT DEFAULT (datetime('now')),
    last_seen   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS statuses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id    TEXT NOT NULL REFERENCES agents(id),
    task_id     TEXT,
    task_name   TEXT,
    status      TEXT NOT NULL DEFAULT 'WORKING',
    phase       TEXT,
    progress    TEXT,
    message     TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_statuses_agent ON statuses(agent_id);
CREATE INDEX IF NOT EXISTS idx_statuses_time  ON statuses(created_at DESC);
"""


class GlobalKanban:
    """Единая доска статусов всех агентов"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)

    def register_agent(
        self,
        agent_id: str,
        name: str,
        group_name: str = "default",
    ) -> bool:
        """
        Зарегистрировать агента на доске.

        Args:
            agent_id: Уникальный ID агента ("triz-coder", "weather-bot")
            name: Человеческое имя ("ТРИЗ-кодер")
            group_name: Группа ("triz-agent", "infra", "tools")

        Returns:
            True если создан, False если уже был
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT id FROM agents WHERE id = ?", (agent_id,)
            )
            if cur.fetchone():
                conn.execute(
                    "UPDATE agents SET last_seen = datetime('now'), name = ? WHERE id = ?",
                    (name, agent_id),
                )
                return False
            conn.execute(
                "INSERT INTO agents (id, name, group_name, last_seen) VALUES (?, ?, ?, datetime('now'))",
                (agent_id, name, group_name),
            )
            return True

    def report(
        self,
        agent_id: str,
        task_name: str,
        status: str = "WORKING",
        progress: str = "",
        message: str = "",
        task_id: Optional[str] = None,
        phase: Optional[str] = None,
    ) -> int:
        """
        Опубликовать статус агента.

        Args:
            agent_id: Кто отчитывается
            task_name: Название задачи ("Phase C — АРИЗ")
            status: QUEUE | WORKING | BLOCKED | REVIEW | DONE | FAILED
            progress: Прогресс ("3/8 steps", "14/20 tests")
            message: Сообщение ("рефакторинг core.py")
            task_id: ID в локальном канбане (опционально)
            phase: Фаза ("C.1", "D.2")

        Returns:
            ID созданной записи
        """
        self.register_agent(agent_id, agent_id)  # гарантируем регистрацию
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                """INSERT INTO statuses
                   (agent_id, task_id, task_name, status, phase, progress, message)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (agent_id, task_id, task_name, status, phase, progress, message),
            )
            # Обновляем last_seen
            conn.execute(
                "UPDATE agents SET last_seen = datetime('now') WHERE id = ?",
                (agent_id,),
            )
            return cur.lastrowid

    def get_board(
        self,
        group_name: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 20,
        hours: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Получить доску — последние статусы.

        Args:
            group_name: Фильтр по группе ("triz-agent")
            agent_id: Фильтр по агенту ("triz-coder")
            limit: Макс записей
            hours: Только за последние N часов

        Returns:
            Список словарей с полями statuses + agent_name
        """
        where_clauses = []
        params = []

        if group_name:
            where_clauses.append("a.group_name = ?")
            params.append(group_name)
        if agent_id:
            where_clauses.append("s.agent_id = ?")
            params.append(agent_id)
        if hours:
            where_clauses.append(
                "s.created_at >= datetime('now', ? || ' hours')"
            )
            params.append(f"-{hours}")

        where = ""
        if where_clauses:
            where = "WHERE " + " AND ".join(where_clauses)

        sql = f"""
            SELECT s.*, a.name as agent_name, a.group_name
            FROM statuses s
            JOIN agents a ON s.agent_id = a.id
            {where}
            ORDER BY s.created_at DESC
            LIMIT ?
        """
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def get_agent_last_status(
        self, agent_id: str
    ) -> Optional[Dict[str, Any]]:
        """Получить последний статус конкретного агента"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT s.*, a.name as agent_name, a.group_name
                   FROM statuses s
                   JOIN agents a ON s.agent_id = a.id
                   WHERE s.agent_id = ?
                   ORDER BY s.created_at DESC LIMIT 1""",
                (agent_id,),
            ).fetchall()
            return dict(rows[0]) if rows else None

    def get_live_agents(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """Кто был на связи за последние N минут"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM agents
                   WHERE last_seen >= datetime('now', ? || ' minutes')
                   ORDER BY last_seen DESC""",
                (f"-{minutes}",),
            ).fetchall()
            return [dict(row) for row in rows]

    def summary(self) -> str:
        """Краткая сводка: кто чем занят"""
        board = self.get_board(limit=10)
        if not board:
            return "📋 Доска пуста. Никто не отчитывался."

        lines = ["📋 **Глобальный канбан:**\n"]
        for row in board:
            icon = {
                "WORKING": "🔧",
                "QUEUE": "📥",
                "BLOCKED": "🚫",
                "REVIEW": "👁",
                "DONE": "✅",
                "FAILED": "❌",
            }.get(row["status"], "📄")

            agent = row.get("agent_name", row["agent_id"])
            task = row["task_name"] or ""
            prog = f" [{row['progress']}]" if row["progress"] else ""
            msg = f" — {row['message']}" if row["message"] else ""

            lines.append(
                f"{icon} **{agent}**: {task}{prog}{msg}"
            )

        return "\n".join(lines)


# ── CLI (если запущен напрямую) ──

if __name__ == "__main__":
    import sys

    gk = GlobalKanban()

    if len(sys.argv) < 2:
        print(gk.summary())
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "report" and len(sys.argv) >= 4:
        agent_id = sys.argv[2]
        task_name = sys.argv[3]
        status = sys.argv[4] if len(sys.argv) > 4 else "WORKING"
        progress = sys.argv[5] if len(sys.argv) > 5 else ""
        message = " ".join(sys.argv[6:]) if len(sys.argv) > 6 else ""
        gk.report(agent_id, task_name, status, progress, message)
        print(f"✅ {agent_id}: [{status}] {task_name} {progress}")

    elif cmd == "board":
        group = sys.argv[2] if len(sys.argv) > 2 else None
        agent = sys.argv[3] if len(sys.argv) > 3 else None
        board = gk.get_board(group_name=group, agent_id=agent)
        for row in board:
            print(
                f"[{row['created_at'][:19]}] "
                f"{row.get('agent_name', row['agent_id']):20s} "
                f"[{row['status']:8s}] "
                f"{row['task_name'] or '':30s} "
                f"{row['progress'] or '':15s} "
                f"{row['message'] or ''}"
            )

    elif cmd == "agents":
        agents = gk.get_live_agents(minutes=60 * 24)
        for a in agents:
            print(
                f"{a['id']:25s} {a.get('name', ''):20s} "
                f"[{a['group_name']}] "
                f"last_seen: {a['last_seen'][:19]}"
            )

    else:
        print("Использование:")
        print("  global_kanban.py                         — сводка")
        print("  global_kanban.py report <agent> <task> [status] [progress] [msg]")
        print("  global_kanban.py board [group] [agent]")
        print("  global_kanban.py agents")