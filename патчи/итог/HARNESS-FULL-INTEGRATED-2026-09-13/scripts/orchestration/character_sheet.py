#!/usr/bin/env python3
"""character_sheet.py — нарезка фактов в «персонаж» оркестратора (геймификация уровня A).

Детерминированный, без LLM. Читает ТОЛЬКО существующие артефакты:
  - .runs/delegation_ledger.db   — события делегирования (если есть)
  - .kanban.db                   — глобальный канбан (статусы code-factory)
  - config/memory_registry.json  — L3 уроки (admissions, reason_codes)
  - .runs/factory_state.json     — текущее состояние фабрики (если есть)

Никаких секретов, никаких прогнозов. Выводит компактный чаршит для вставки
в контекст (markdown) или сырой JSON (флаг --json).

Примеры:
  python character_sheet.py
  python character_sheet.py --json
  python character_sheet.py --min   # однострочная сводка для report
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

# XP за факты (политика в коде, консервативная)
XP_FINALIZE = 50          # задача доведена до DONE (из канбана)
XP_LESSON = 15            # урок в L3
XP_LESSON_ADMISSION = 5   # доп. подтверждение урока
XP_DELEGATE = 2           # событие делегирования в ledger
XP_SELF_EDIT = -30        # штраф за само-кодинг мимо фабрики (сигнал, не бан)
XP_TRIBUNAL = 25          # конфликт решён трибуналом (ledger)


def _harness_root() -> Path:
    env = os.environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def _read_json(p: Path) -> dict:
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _kb(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


def _level_for(xp: int) -> tuple[int, int, int]:
    """Level = floor(sqrt(xp/100)) + 1. Возврат (level, xp_need_next, xp_into_level)."""
    if xp <= 0:
        return (1, 100, max(0, xp))
    level = int((xp / 100) ** 0.5) + 1
    prev = 100 * (level - 1) ** 2
    nxt = 100 * level ** 2
    return (level, nxt - prev, max(0, xp - prev))


def build(root: Path) -> dict:
    runs = root / ".runs"
    ledger_db = runs / "delegation_ledger.db"
    kb_db = root / ".kanban.db"
    reg_path = root / "config" / "memory_registry.json"
    state_path = runs / "factory_state.json"

    xp = 0
    counters = {
        "tasks_finalized": 0,
        "lessons": 0,
        "lesson_admissions": 0,
        "delegated_events": 0,
        "tribunals": 0,
        "self_edits": 0,
    }
    achievements: list[str] = []

    # --- kanban (статусы code-factory) ---
    if kb_db.exists():
        try:
            with _kb(kb_db) as conn:
                rows = conn.execute(
                    "SELECT status, COUNT(*) AS n FROM statuses WHERE agent_id='code-factory' AND status='DONE' GROUP BY status"
                ).fetchall()
            done_count = sum(r["n"] for r in rows)
            xp += XP_FINALIZE * done_count
            counters["tasks_finalized"] += done_count
        except sqlite3.Error as exc:
            counters["kanban_error"] = str(exc)

    # --- memory registry (L3) ---
    reg = _read_json(reg_path)
    lessons = reg.get("levels", {}).get("L3", {}).get("lessons", {})
    if isinstance(lessons, dict):
        counters["lessons"] = len(lessons)
        xp += XP_LESSON * len(lessons)
        total_adm = sum(int(e.get("admissions", 0)) for e in lessons.values() if isinstance(e, dict))
        counters["lesson_admissions"] = total_adm
        xp += XP_LESSON_ADMISSION * total_adm
        if len(lessons) >= 1:
            achievements.append("Память: первый L3 урок записан")
        if len(lessons) >= 3:
            achievements.append("Чтиво: 3+ уроков в реестре")

    # --- delegation ledger ---
    if ledger_db.exists():
        try:
            conn = _kb(ledger_db)
            rows = conn.execute(
                "SELECT action, COUNT(*) AS n, SUM(score) AS sc FROM events GROUP BY action"
            ).fetchall()
            trend = conn.execute(
                "SELECT COALESCE(SUM(score),0) FROM events WHERE ts >= date('now','-7 days')"
            ).fetchone()
            trend_xp = int(trend[0] if trend and trend[0] is not None else 0)
            conn.close()
            for r in rows:
                act = r["action"]
                if act.startswith("submit_"):
                    counters["delegated_events"] += r["n"]
                    xp += XP_DELEGATE * r["n"]
                elif act == "tribunal":
                    counters["tribunals"] += r["n"]
                    xp += XP_TRIBUNAL * r["n"]
                elif act == "finalize":
                    counters["tasks_finalized"] += r["n"]
                elif act == "self_edit":
                    counters["self_edits"] += r["n"]
                    xp += XP_SELF_EDIT * r["n"]
        except sqlite3.Error:
            pass
    else:
        trend_xp = 0

    # --- factory state (текущий цикл) ---
    fstate = _read_json(state_path)
    cycle = fstate.get("cycle", {})
    factory_running = bool(cycle)
    factory_attempt = cycle.get("attempt")
    factory_rework = cycle.get("rework_rounds")
    factory_limit = cycle.get("attempt_limit")

    # Achievements по наработанным фактам
    if counters["delegated_events"] >= 5:
        achievements.append("Оркестрация: 5+ событий делегирования")
    if counters["delegated_events"] >= 20:
        achievements.append("Палка-погонялка: 20+ модулей делегировано")
    if counters["tribunals"] >= 1:
        achievements.append("Трибунал: конфликт решён процессом")
    if counters["self_edits"] == 0 and counters["delegated_events"] >= 3 and counters["tasks_finalized"] >= 1:
        achievements.append("Чистый контур: 0 само-правок на фоне делегирования")
    if counters["tasks_finalized"] >= 1:
        achievements.append("Отчёт: задача доведена до DONE")
    if factory_running:
        achievements.append("В процессе: фабрика работает прямо сейчас")

    level, xp_to_next, xp_into = _level_for(xp)

    # Baseline-нормализация: собственный темп, а не чужой бенчмарк (как token-tamers).
    # Сравниваем XP за последние 7 дней с кумулятивным темпом: >baseline = прогресс.
    baseline_xp = xp  # полный капитал как «база»
    trend_label = ""
    if baseline_xp > 0 and trend_xp:
        share = trend_xp / baseline_xp
        if share >= 0.4:
            trend_label = "темп высокий"
        elif share >= 0.2:
            trend_label = "средний темп"
        elif share > 0:
            trend_label = "темп ниже обычного"
    elif trend_xp == 0:
        trend_label = "нет активности за 7 дней"
    else:
        trend_label = "стартуем"

    return {
        "level": level,
        "xp": xp,
        "xp_to_next_level": xp_to_next,
        "xp_into_level": xp_into,
        "trend_xp_7d": trend_xp,
        "trend_label": trend_label,
        "counters": counters,
        "achievements": achievements,
        "factory_running": factory_running,
        "factory_cycle": {
            "attempt": factory_attempt,
            "rework_rounds": factory_rework,
            "attempt_limit": factory_limit,
        },
        "sources": {
            "ledger_db": str(ledger_db) if ledger_db.exists() else None,
            "kanban_db": str(kb_db) if kb_db.exists() else None,
            "memory_registry": str(reg_path) if reg_path.exists() else None,
            "factory_state": str(state_path) if state_path.exists() else None,
        },
    }


def to_markdown(cs: dict) -> str:
    lines = [
        "",
        "## 🎮 Character Sheet (оркестратор)",
        f"- **Уровень {cs['level']}** | XP {cs['xp']} (до {int(cs['xp_into_level'])}/{cs['xp_to_next_level']})",
        f"- Фабрика: {'работает' if cs['factory_running'] else 'простаивает'} | задач DONE: {cs['counters']['tasks_finalized']} | "
        f"уроков L3: {cs['counters']['lessons']} | делегировано: {cs['counters']['delegated_events']} | "
        f"трибуналов: {cs['counters']['tribunals']} | само-правок: {cs['counters']['self_edits']}",
    ]
    fc = cs.get("factory_cycle") or {}
    if fc.get("attempt") is not None:
        lines.append(f"- Фабрика сейчас: attempt {fc['attempt']}, переработок {fc['rework_rounds']}/{fc['attempt_limit']}")
    lines.append(f"- Тренд (XP за 7 дней): {cs.get('trend_xp_7d', 0)} — {cs.get('trend_label', '')}")
    if cs["achievements"]:
        lines.append("- Ачивки: " + "; ".join(cs["achievements"]))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(prog="character_sheet", description="Факты -> персонаж (геймификация A)")
    parser.add_argument("--json", action="store_true", help="выводить JSON")
    parser.add_argument("--min", action="store_true", help="однострочная сводка")
    args = parser.parse_args()

    cs = build(_harness_root())

    if args.json:
        print(json.dumps(cs, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if args.min:
        a = cs["achievements"]
        print(
            f"L{cs['level']} XP{cs['xp']} done={cs['counters']['tasks_finalized']} "
            f"lessons={cs['counters']['lessons']} delegated={cs['counters']['delegated_events']} "
            f"tribunals={cs['counters']['tribunals']} self_edits={cs['counters']['self_edits']}"
            f"{'; ' + a[0] if a else ''}"
        )
        return 0
    print(to_markdown(cs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())