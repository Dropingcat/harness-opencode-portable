#!/usr/bin/env python3
"""baseline_tracker.py — глобальный трекер задач и суб-трекеры веток сна.

Канон гл.26 (чекпоинты): чекпоинт = проверяемое состояние (description + ts +
commit на каждом шаге). Канон гл.28 (ветки сна): пока агент спит, его ветки
идут параллельно (параллельные агенты по cli), каждая ветка имеет собственный
sub_tracker с baseline (HEAD на момент открытия сна) и статусом
pending|running|merged|failed.

Файл прогресса `.runs/progress/<task_id>.json` — страховка от сжатия/обрыва:
любой агент может прочитать его как компактный снапшот состояния трекера.

API (Python):
    register_task(task_id, agent, dispatcher)  -> dict
    open_sleep(task_id, branches)              -> list[dict]
    checkpoint(task_id, branch, description)   -> dict
    mark_branch(task_id, branch, status)       -> dict
    close_sleep(task_id, merged_branches)      -> dict
    progress_file(task_id)                     -> str

CLI:
    python baseline_tracker.py register --task <id> --agent <a> --dispatcher <d>
    python baseline_tracker.py open-sleep --task <id> --branches fix/A,fix/B
    python baseline_tracker.py checkpoint --task <id> --branch fix/A --desc "текст"
    python baseline_tracker.py mark --task <id> --branch fix/A --status merged
    python baseline_tracker.py progress --task <id>
    python baseline_tracker.py status            # печать всего трекера
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

# корень harness (относительно scripts/orchestration)
_HARNESS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRACKER_PATH = os.path.join(_HARNESS_ROOT, ".runs", "progress", "baseline_tracker.json")
PROGRESS_DIR = os.path.join(_HARNESS_ROOT, ".runs", "progress")

VALID_TASK_STATUS = ("active", "sleeping", "done")
VALID_BRANCH_STATUS = ("pending", "running", "merged", "failed")


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_head() -> str:
    """Текущий git HEAD (только чтение, без git-операций)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_HARNESS_ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip()
    except Exception:  # subprocess-ошибка или git недоступен — пустой baseline
        return ""


def _load_tracker() -> dict:
    """Читает .runs/progress/baseline_tracker.json (создаёт пустой каркас, если нет)."""
    if os.path.exists(TRACKER_PATH):
        try:
            with open(TRACKER_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # битый/нечитаемый файл — не перезаписываем его вслепую, но работаем
            # с пустым каркасом (append-only гарантирует, что история не теряется
            # в рамках текущего запуска)
            return {"version": 1, "tasks": []}
    return {"version": 1, "tasks": []}


def _save_tracker(tracker: dict) -> None:
    os.makedirs(os.path.dirname(TRACKER_PATH), exist_ok=True)
    tmp = TRACKER_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tracker, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, TRACKER_PATH)  # атомарная замена, не рвём файл при обрыве


def _find_task(tracker: dict, task_id: str) -> Optional[dict]:
    for task in tracker.get("tasks", []):
        if task.get("task_id") == task_id:
            return task
    return None


def _require_task(task_id: str) -> dict:
    """Находит задачу или падает с понятной ошибкой."""
    tracker = _load_tracker()
    task = _find_task(tracker, task_id)
    if task is None:
        raise ValueError(f"task '{task_id}' не найден в {TRACKER_PATH}. "
                         f"Сначала: register --task {task_id}")
    return task


def _find_branch(task: dict, branch: str) -> Optional[dict]:
    for st in task.get("sub_trackers", []):
        if st.get("branch") == branch:
            return st
    return None


def _write_progress(task_id: str, task: dict) -> str:
    """Страховка (канон гл.26): компактный снапшот задачи в файл прогресса."""
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    path = os.path.join(PROGRESS_DIR, f"{task_id}.json")
    snapshot = {
        "task_id": task.get("task_id"),
        "agent": task.get("agent"),
        "dispatcher": task.get("dispatcher"),
        "baseline_commit": task.get("baseline_commit"),
        "baseline_ts": task.get("baseline_ts"),
        "status": task.get("status"),
        "updated_ts": _now(),
        "sub_trackers": task.get("sub_trackers", []),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def register_task(task_id: str, agent: str, dispatcher: str) -> dict:
    """Создаёт задачу с baseline_commit = текущий git HEAD, baseline_ts = now.

    Если task_id уже существует — возвращает существующую запись без изменений
    (не перезаписываем прошлый baseline, история append-only).
    """
    tracker = _load_tracker()
    existing = _find_task(tracker, task_id)
    if existing is not None:
        return existing

    task = {
        "task_id": task_id,
        "agent": agent,
        "dispatcher": dispatcher,
        "baseline_commit": _git_head(),
        "baseline_ts": _now(),
        "status": "active",
        "sub_trackers": [],
    }
    tracker["tasks"].append(task)
    _save_tracker(tracker)
    _write_progress(task_id, task)
    return task


def open_sleep(task_id: str, branches: list[str]) -> list[dict]:
    """Открывает сон: для каждой ветки создаёт sub_tracker.

    {branch, baseline=HEAD на момент сна, checkpoints: [], status: pending}.
    Существующая ветка не пересоздаётся (append-only, сохраняем чекпоинты).
    Статус задачи -> 'sleeping'.
    """
    task = _require_task(task_id)
    tracker = _load_tracker()
    task = _find_task(tracker, task_id)  # свежая ссылка из файла

    head = _git_head()
    now = _now()
    for branch in branches:
        if _find_branch(task, branch) is None:
            task["sub_trackers"].append({
                "branch": branch,
                "baseline": head,
                "checkpoints": [],
                "status": "pending",
                "agent_pid": None,
            })

    # статус задачи: active -> sleeping (сон открыт), done не трогаем
    if task.get("status") not in ("done",):
        task["status"] = "sleeping"

    _save_tracker(tracker)
    _write_progress(task_id, task)
    return list(task["sub_trackers"])


def checkpoint(task_id: str, branch: str, description: str) -> dict:
    """Добавляет чекпоинт {description, ts, commit} в ветку (append-only).

    Канон гл.26: чекпоинт = проверяемое состояние на каждом шаге.
    """
    task = _require_task(task_id)
    tracker = _load_tracker()
    task = _find_task(tracker, task_id)
    st = _find_branch(task, branch)
    if st is None:
        raise ValueError(f"ветка '{branch}' не найдена в задаче '{task_id}'. "
                         f"Сначала: open-sleep --task {task_id} --branches {branch}")

    entry = {
        "description": description,
        "ts": _now(),
        "commit": _git_head(),
    }
    st["checkpoints"].append(entry)  # append-only, прошлые чекпоинты не трогаем
    _save_tracker(tracker)
    _write_progress(task_id, task)
    return entry


def mark_branch(task_id: str, branch: str, status: str) -> dict:
    """Меняет статус ветки: pending|running|merged|failed."""
    if status not in VALID_BRANCH_STATUS:
        raise ValueError(f"неверный статус ветки '{status}'. "
                         f"Допустимо: {', '.join(VALID_BRANCH_STATUS)}")

    task = _require_task(task_id)
    tracker = _load_tracker()
    task = _find_task(tracker, task_id)
    st = _find_branch(task, branch)
    if st is None:
        raise ValueError(f"ветка '{branch}' не найдена в задаче '{task_id}'.")

    st["status"] = status
    _save_tracker(tracker)
    _write_progress(task_id, task)
    return st


def close_sleep(task_id: str, merged_branches: Optional[list[str]] = None) -> dict:
    """Закрывает сон. Если переданы merged_branches — проставляет им merged.

    task.status = done, только если все ветки merged (или веток нет).
    Возвращает итоговую задачу.
    """
    task = _require_task(task_id)
    tracker = _load_tracker()
    task = _find_task(tracker, task_id)

    if merged_branches:
        for branch in merged_branches:
            st = _find_branch(task, branch)
            if st is not None:
                st["status"] = "merged"

    sts = [st.get("status") for st in task.get("sub_trackers", [])]
    if all(s == "merged" for s in sts):
        task["status"] = "done"
    elif task.get("status") == "sleeping":
        # ещё не все merged — сон закрыт, но задача остаётся спящей/активной
        pass

    _save_tracker(tracker)
    _write_progress(task_id, task)
    return task


def progress_file(task_id: str) -> str:
    """Возвращает путь к файлу прогресса `.runs/progress/<task_id>.json`."""
    return os.path.join(PROGRESS_DIR, f"{task_id}.json")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_branches(raw: str) -> list[str]:
    return [b.strip() for b in raw.split(",") if b.strip()]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="baseline_tracker.py",
        description="Глобальный трекер задач и суб-трекеры веток сна (канон гл.26/28).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_register = sub.add_parser("register", help="создать задачу с baseline=HEAD")
    p_register.add_argument("--task", required=True, help="task_id")
    p_register.add_argument("--agent", required=True, help="агент-исполнитель")
    p_register.add_argument("--dispatcher", required=True, help="агент-диспетчер")

    p_open = sub.add_parser("open-sleep", help="открыть сон с ветками")
    p_open.add_argument("--task", required=True, help="task_id")
    p_open.add_argument("--branches", required=True, help="ветки через запятую: fix/A,fix/B")

    p_chk = sub.add_parser("checkpoint", help="добавить чекпоинт в ветку")
    p_chk.add_argument("--task", required=True, help="task_id")
    p_chk.add_argument("--branch", required=True, help="имя ветки")
    p_chk.add_argument("--desc", required=True, help="описание чекпоинта")

    p_mark = sub.add_parser("mark", help="сменить статус ветки")
    p_mark.add_argument("--task", required=True, help="task_id")
    p_mark.add_argument("--branch", required=True, help="имя ветки")
    p_mark.add_argument("--status", required=True, choices=VALID_BRANCH_STATUS)

    p_close = sub.add_parser("close-sleep", help="закрыть сон (merged-ветки)")
    p_close.add_argument("--task", required=True, help="task_id")
    p_close.add_argument("--branches", help="merged-ветки через запятую (опционально)")

    p_prog = sub.add_parser("progress", help="путь к файлу прогресса")
    p_prog.add_argument("--task", required=True, help="task_id")

    sub.add_parser("status", help="показать весь трекер")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "register":
            task = register_task(args.task, args.agent, args.dispatcher)
            print(json.dumps(task, ensure_ascii=False, indent=2))
        elif args.cmd == "open-sleep":
            sts = open_sleep(args.task, _parse_branches(args.branches))
            print(json.dumps(sts, ensure_ascii=False, indent=2))
        elif args.cmd == "checkpoint":
            entry = checkpoint(args.task, args.branch, args.desc)
            print(json.dumps(entry, ensure_ascii=False, indent=2))
        elif args.cmd == "mark":
            st = mark_branch(args.task, args.branch, args.status)
            print(json.dumps(st, ensure_ascii=False, indent=2))
        elif args.cmd == "close-sleep":
            merged = _parse_branches(args.branches) if args.branches else None
            task = close_sleep(args.task, merged)
            print(json.dumps(task, ensure_ascii=False, indent=2))
        elif args.cmd == "progress":
            print(progress_file(args.task))
        elif args.cmd == "status":
            print(json.dumps(_load_tracker(), ensure_ascii=False, indent=2))
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())