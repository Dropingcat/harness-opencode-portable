#!/usr/bin/env python3
"""idle_tasks.py — чем агенту заняться в простое (геймификация уровня B).

Детерминированный, без LLM, НИЧЕГО не пишет: только предлагает проверенную
«агенду гигиены». Оркестратор может вызывать его пока ждёт воркеров/ревьюеров
и делать полезное без риска заtheй в токены.

Приоритеты:
  [H] health — здоровье инфраструктуры
  [M] hygn   — гигиена данных (канбан, память, sync)
  [L] meta   — подготовка к следующим шагам

Примеры:
  python idle_tasks.py             # агенда markdown
  python idle_tasks.py --json      # агенда JSON
  python idle_tasks.py --check     # только факты, без действий (безопасно)
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


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


def _ago(hours: float = 1.0) -> str:
    return (datetime.now().astimezone() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


def build(root: Path) -> dict:
    runs = root / ".runs"
    items: list[dict] = []

    # --- H1: health_check ---
    hc = root / "scripts" / "health_check.py"
    items.append({
        "prio": "H",
        "kind": "health",
        "title": "Прогнать health_check",
        "cmd": f"python {hc}",
        "why": "Быстрая проверка плагина/MCP/guard/DB перед длинным циклом.",
        "check": "exists",
        "exists": hc.exists(),
    })

    # --- H2: factory state согласован ---
    fstate = _read_json(runs / "factory_state.json")
    if fstate:
        st = fstate.get("cycle", {}).get("state")
        items.append({
            "prio": "H",
            "kind": "health",
            "title": f"Фабрика в состоянии {st} — проверить stop_reason",
            "cmd": f"python {root / 'scripts' / 'code-factory' / 'factory_ctl.py'} status",
            "why": "Текущий цикл не завершён; полезно знать, ждать ли воркеров.",
            "check": "state",
            "state": st,
        })
    else:
        items.append({
            "prio": "L",
            "kind": "meta",
            "title": "Нет активного factory_state — можно инициализировать новую задачу",
            "cmd": None,
            "why": "runs/factory_state.json отсутствует: предыдущее состояние не сохранилось.",
            "check": "state",
            "state": None,
        })

    # --- M1: канбан старые WORKING ---
    kb = root / ".kanban.db"
    if kb.exists():
        stale = []
        try:
            conn = sqlite3.connect(str(kb))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM statuses WHERE created_at < ? AND status IN ('WORKING','RUNNING','PENDING') ORDER BY created_at DESC",
                (_ago(24),),
            ).fetchall()
            conn.close()
            for r in rows:
                stale.append({
                    "task": r["task_name"], "status": r["status"],
                    "created": r["created_at"], "message": r["message"],
                })
        except sqlite3.Error:
            stale = []
        if stale:
            items.append({
                "prio": "M",
                "kind": "hygn",
                "title": f"Канбан: {len(stale)} статусов более 24ч в рабочем состоянии",
                "cmd": None,
                "why": "Зависшие статусы раздувают доску; стоит отметить DONE/FAILED или спросить пользователя.",
                "check": "kanban_stale",
                "stale": stale[:3],
            })
        else:
            items.append({
                "prio": "L",
                "kind": "hygn",
                "title": "Канбан чистый (нет старых WORKING)",
                "cmd": None,
                "why": "Доска в порядке.",
                "check": "kanban_clean",
            })

    # --- M2: L2->L3 кандидаты ---
    tmp_l2 = root / ".tmp_l2.json"
    l2 = _read_json(tmp_l2)
    candidates = l2.get("candidate_lessons", [])
    if isinstance(candidates, list) and candidates:
        items.append({
            "prio": "M",
            "kind": "hygn",
            "title": f"Есть {len(candidates)} кандидатов L2→L3",
            "cmd": f"python {root / 'scripts' / 'memory' / 'memory_bridge.py'} add-file {tmp_l2}",
            "why": ".tmp_l2.json накоплен; перенос в L3 по политике (promote через add-file).",
            "check": "l2_candidates",
            "count": len(candidates),
        })

    # --- M3: расхождение HARNESS <-> LIVE ---
    sync = root / "scripts" / "sync_to_live.py"
    if sync.exists():
        items.append({
            "prio": "M",
            "kind": "hygn",
            "title": "Проверить расхождение HARNESS→LIVE",
            "cmd": f"python {sync}",
            "why": "Dry-run покажет, не уехали ли агенты/скрипты относительно live.",
            "check": "sync_dryrun",
        })

    # --- L1: поиск в памяти под следующую задачу ---
    mb = root / "scripts" / "memory" / "memory_bridge.py"
    items.append({
        "prio": "L",
        "kind": "meta",
        "title": "Полистать опыт в L3 (search) для будущих задач",
        "cmd": f"python {mb} search --limit 10",
        "why": "Подсветить повторяющиеся грабли перед следующим контрактом.",
        "check": "memory_search",
        "exists": mb.exists(),
    })

    return {"generated": datetime.now().astimezone().isoformat(), "root": str(root), "items": items}


def to_markdown(d: dict) -> str:
    lines = ["", "## 🕹 Idle agenda (чем полезно заняться в простое)", ""]
    for it in sorted(d["items"], key=lambda x: (x["prio"], x["kind"], x["title"])):
        icon = {"H": "🩺", "M": "🧹", "L": "🗂"}.get(it["prio"], "•")
        cmd = f"\n    `{it['cmd']}`" if it.get("cmd") else ""
        lines.append(f"- {icon} **[{it['prio']}]** {it['title']}{cmd}")
        if it.get("why"):
            lines.append(f"    *{it['why']}*")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(prog="idle_tasks", description="Агенда полезного простоя (B)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true", help="только факты без команд")
    args = parser.parse_args()

    d = build(_harness_root())
    if args.check:
        for it in sorted(d["items"], key=lambda x: (x["prio"], x["kind"])):
            print(f"{it['prio']} {it['kind']}: {it['title']}")
        return 0
    if args.json:
        print(json.dumps(d, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    print(to_markdown(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())