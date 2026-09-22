#!/usr/bin/env python3
"""tech_debt_cli.py — канонический CLI для управления реестром техдолгов.

Заменяет десятки ad-hoc скриптов (add_td*.py, close_td*.py, update_td*.py),
которые агенты плодили в C:\\Temp\\opencode. Единая точка правки
config/tech_debt.json + регенерация docs/TRACKERS/TECH_DEBT_MASTER.md.

Usage:
    python tech_debt_cli.py add   --id TD-XXX [--owner code-orchestrator] [--severity high] \\
                                  --title "..." [--notes "..."] [--acceptance "..."]
    python tech_debt_cli.py close --id TD-XXX [--progress "..."]
    python tech_debt_cli.py update --id TD-XXX [--title "..."] [--severity ...] [--notes ...] [--progress ...]
    python tech_debt_cli.py get   --id TD-XXX            # показать запись (без секретов)
    python tech_debt_cli.py list  [--owner research-orchestrator] [--status open] [--severity high]
    python tech_debt_cli.py next  [--owner code-orchestrator]    # следующий свободный ID (TD-XXX+1)
    python tech_debt_cli.py master [--root <harness-root>]       # перегенерировать TECH_DEBT_MASTER.md

Поля записи (схема, как в существующих): id, owner, presentation_category,
sunset_at, title, status_detail, kind, status, severity, acceptance, area,
source_status, notes, progress.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent          # scripts/tools
HARNESS_ROOT = HERE.parent.parent               # scripts/tools/../.. = harness root
# Канонический реестр — portable (GitHub-версия). Work — зеркало через sync_tech_debt.py.
DEFAULT_DEBT = Path(os.environ.get("TECH_DEBT_PATH", r"E:\opencode_harness_portable\config\tech_debt.json"))
DEFAULT_MASTER = HARNESS_ROOT / "docs" / "TRACKERS" / "TECH_DEBT_MASTER.md"
DEFAULT_GEN = HARNESS_ROOT / "scripts" / "glossary" / "coder_techdebt_master.py"

VALID_SEVERITY = ("critical", "high", "medium", "low")
VALID_STATUS = ("open", "closed")


def _load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(path, data: dict) -> None:
    path = Path(path)
    open_c = sum(1 for r in data["debts"] if r.get("status") == "open")
    closed_c = sum(1 for r in data["debts"] if r.get("status") == "closed")
    data["counts"] = {"total": len(data["debts"]), "open": open_c, "closed": closed_c}
    data["updated"] = datetime.date.today().isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _next_id(debts: list[dict]) -> str:
    nums = [int(re.sub(r"\D", "", r["id"])) for r in debts if re.match(r"^TD-\d+", r["id"])]
    return f"TD-{max(nums) + 1}" if nums else "TD-001"


def _find(debts: list[dict], id_: str) -> dict | None:
    return next((r for r in debts if r["id"] == id_), None)


def cmd_add(args) -> int:
    data = _load(args.debt)
    if _find(data["debts"], args.id):
        print(f"ERROR: {args.id} уже существует (use update)", file=sys.stderr)
        return 1
    if not args.title:
        print("ERROR: --title обязателен", file=sys.stderr)
        return 1
    record = {
        "id": args.id,
        "owner": args.owner or "code-orchestrator",
        "presentation_category": "ACTIVE",
        "sunset_at": args.sunset_at or (datetime.date.today().replace(year=datetime.date.today().year + 1).isoformat()),
        "title": args.title,
        "status_detail": "OPEN_CURRENT",
        "kind": args.kind or "tooling",
        "status": "open",
        "severity": args.severity or "medium",
        "acceptance": args.acceptance or "",
        "area": args.area or "",
        "source_status": "open",
        "notes": args.notes or "",
        "progress": args.progress or f"{datetime.date.today().isoformat()}: создано через tech_debt_cli.py",
    }
    data["debts"].append(record)
    _save(args.debt, data)
    print(f"OK: {args.id} добавлен (total={len(data['debts'])})")
    return 0


def cmd_close(args) -> int:
    data = _load(args.debt)
    r = _find(data["debts"], args.id)
    if not r:
        print(f"ERROR: {args.id} не найден", file=sys.stderr)
        return 1
    r["status"] = "closed"
    r["status_detail"] = "CLOSED"
    r["presentation_category"] = "RESOLVED"
    if args.progress:
        r["progress"] = args.progress
    _save(args.debt, data)
    print(f"OK: {args.id} закрыт")
    return 0


def cmd_update(args) -> int:
    data = _load(args.debt)
    r = _find(data["debts"], args.id)
    if not r:
        print(f"ERROR: {args.id} не найден", file=sys.stderr)
        return 1
    for field in ("title", "owner", "severity", "kind", "acceptance", "area", "notes", "progress", "source_status", "status_detail", "sunset_at", "presentation_category"):
        val = getattr(args, field, None)
        if val is not None:
            r[field] = val
    if args.status:
        r["status"] = args.status
        if args.status == "closed":
            r["status_detail"] = "CLOSED"
            r["presentation_category"] = "RESOLVED"
    _save(args.debt, data)
    print(f"OK: {args.id} обновлён")
    return 0


def cmd_get(args) -> int:
    data = _load(args.debt)
    r = _find(data["debts"], args.id)
    if not r:
        print(f"ERROR: {args.id} не найден", file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args) -> int:
    data = _load(args.debt)
    rows = data["debts"]
    if args.owner:
        rows = [r for r in rows if r.get("owner") == args.owner]
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if args.severity:
        rows = [r for r in rows if r.get("severity") == args.severity]
    rows.sort(key=lambda r: r["id"])
    for r in rows:
        print(f"{r['id']:8s} [{r.get('severity','?'):8s}] {r.get('owner','?'):24s} {(r['title'] or '')[:80]}")
    print(f"-- total: {len(rows)}")
    return 0


def cmd_next(args) -> int:
    data = _load(args.debt)
    print(_next_id(data["debts"]))
    return 0


def cmd_master(args) -> int:
    root = Path(args.root) if args.root else HARNESS_ROOT
    gen = root / "scripts" / "glossary" / "coder_techdebt_master.py"
    if not gen.exists():
        print(f"ERROR: генератор не найден: {gen}", file=sys.stderr)
        return 1
    r = subprocess.run([sys.executable, str(gen), "--root", str(root)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout, file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        return r.returncode
    print(r.stdout.strip())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Канонический CLI техдолгов")
    ap.add_argument("--debt", default=str(DEFAULT_DEBT), help="путь к tech_debt.json")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="добавить долг")
    p.add_argument("--id", required=True)
    p.add_argument("--owner", default=None)
    p.add_argument("--severity", choices=VALID_SEVERITY, default="medium")
    p.add_argument("--kind", default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--notes", default=None)
    p.add_argument("--acceptance", default=None)
    p.add_argument("--area", default=None)
    p.add_argument("--progress", default=None)
    p.add_argument("--sunset-at", dest="sunset_at", default=None)
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("close", help="закрыть долг")
    p.add_argument("--id", required=True)
    p.add_argument("--progress", default=None)
    p.set_defaults(fn=cmd_close)

    p = sub.add_parser("update", help="обновить долг")
    p.add_argument("--id", required=True)
    p.add_argument("--title", default=None)
    p.add_argument("--owner", default=None)
    p.add_argument("--severity", choices=VALID_SEVERITY, default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--status", choices=VALID_STATUS, default=None)
    p.add_argument("--notes", default=None)
    p.add_argument("--acceptance", default=None)
    p.add_argument("--area", default=None)
    p.add_argument("--progress", default=None)
    p.add_argument("--source-status", dest="source_status", default=None)
    p.add_argument("--status-detail", dest="status_detail", default=None)
    p.add_argument("--sunset-at", dest="sunset_at", default=None)
    p.set_defaults(fn=cmd_update)

    p = sub.add_parser("get", help="показать долг")
    p.add_argument("--id", required=True)
    p.set_defaults(fn=cmd_get)

    p = sub.add_parser("list", help="список долгов")
    p.add_argument("--owner", default=None)
    p.add_argument("--status", choices=VALID_STATUS, default=None)
    p.add_argument("--severity", choices=VALID_SEVERITY, default=None)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("next", help="следующий свободный ID")
    p.set_defaults(fn=cmd_next)

    p = sub.add_parser("master", help="перегенерировать TECH_DEBT_MASTER.md")
    p.add_argument("--root", default=None)
    p.set_defaults(fn=cmd_master)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())