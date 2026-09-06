"""
SQLite-хранилище для канбан-доски.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from .models import Task, TaskStatus


# Константа: порядок колонок в таблице (синхронизировать с CREATE TABLE и _row_to_task)
_COLUMNS = [
    "id", "query", "context", "status", "created_at", "updated_at",
    "current_iteration", "max_iterations", "mode", "iterations", "result", "error",
    "fact_pack",
]


class KanbanStorage:
    """SQLite-хранилище канбан-доски"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = "/home/orangepi/.hermes/profiles/triz-agent/kanban.db"
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS kanban_tasks (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    context TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    current_iteration INTEGER NOT NULL,
                    max_iterations INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    iterations TEXT NOT NULL DEFAULT '[]',
                    result TEXT,
                    error TEXT,
                    fact_pack TEXT
                )
            """)
            conn.commit()
            # Backward compatibility: add fact_pack column if missing (старые БД)
            cursor = conn.execute("PRAGMA table_info(kanban_tasks)")
            existing = {row[1] for row in cursor.fetchall()}
            if "fact_pack" not in existing:
                conn.execute("ALTER TABLE kanban_tasks ADD COLUMN fact_pack TEXT")
                conn.commit()

    def save_task(self, task: Task):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"""
                INSERT OR REPLACE INTO kanban_tasks
                ({', '.join(_COLUMNS)})
                VALUES ({', '.join(['?'] * len(_COLUMNS))})
            """, (
                task.id,
                task.query,
                json.dumps(task.context, ensure_ascii=False),
                task.status.value,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
                task.current_iteration,
                task.max_iterations,
                task.mode,
                json.dumps(task.iterations, ensure_ascii=False),
                json.dumps(task.result, ensure_ascii=False) if task.result else None,
                task.error,
                json.dumps(task.fact_pack, ensure_ascii=False) if task.fact_pack else None
            ))
            conn.commit()

    def load_task(self, task_id: str) -> Optional[Task]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM kanban_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            return self._row_to_task(row) if row else None

    def load_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"SELECT {', '.join(_COLUMNS)} FROM kanban_tasks WHERE status = ? ORDER BY created_at DESC",
                (status.value,)
            )
            return [self._row_to_task(row) for row in cursor.fetchall()]

    def delete_task(self, task_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM kanban_tasks WHERE id = ?", (task_id,))
            conn.commit()

    def _row_to_task(self, row: Tuple) -> Task:
        return Task(
            id=row[0],
            query=row[1],
            context=json.loads(row[2]),
            status=TaskStatus(row[3]),
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
            current_iteration=row[6],
            max_iterations=row[7],
            mode=row[8],
            iterations=json.loads(row[9]),
            result=json.loads(row[10]) if row[10] else None,
            error=row[11],
            fact_pack=json.loads(row[12]) if len(row) > 12 and row[12] else None,
        )