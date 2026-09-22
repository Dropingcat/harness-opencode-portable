#!/usr/bin/env python3
"""sync_tech_debt.py — консолидация двух реестров техдолгов (TD-110).

Проблема: portable (архитектурные долги) и work (исследовательские долги агентов)
имели РАЗНЫЕ записи под одинаковыми ID (TD-103+). Решение (подход 2):
- Канонический реестр — один: config/tech_debt.json в portable (GitHub-версия).
- Записи, существующие в work под ID, который в portable занят ДРУГОЙ записью,
  переименовываются в пространство RS-* (research-space), чтобы не потерять данные.
- После слияния work-реестр синхронизируется с каноническим.

Авто-вызов: после любого изменения tech_debt.json (add/close/update) запускать
этот скрипт, чтобы держать оба дерева в одном состоянии.

Usage:
    python sync_tech_debt.py [--portable <path>] [--work <path>] [--dry-run] [--backup]

Опция --dry-run: показать план без записи.
Опция --backup: бэкап обоих файлов перед записью.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_PORTABLE = Path(r"E:\opencode_harness_portable\config\tech_debt.json")
DEFAULT_WORK = Path(r"E:\Documents\Документы\doc_Opencode_agern-new\config\tech_debt.json")
BACKUP_DIR = Path(r"C:\Temp\opencode\backup_debts")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _next_rs(debts: list[dict]) -> int:
    nums = [int(re.sub(r"\D", "", r["id"])) for r in debts if r["id"].startswith("RS-")]
    return (max(nums) + 1) if nums else 1


def _backup(p: Path, tag: str) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = BACKUP_DIR / f"{p.stem}_{tag}_{ts}{p.suffix}"
    dst.write_bytes(p.read_bytes())
    print(f"  backup: {p.name} -> {dst.name}")


def merge(portable_path: Path, work_path: Path, dry_run: bool, do_backup: bool) -> int:
    """Слияние: portable — канонический (источник правды), work — зеркало.

    Односторонний sync: work-записи, которых нет в portable, добавляются;
    work-записи с ID, занятым другой записью в portable, -> RS-* (без потерь);
    затем work перезаписывается из portable (зеркало).
    """
    print(f"=== Слияние реестров техдолгов ===")
    print(f"portable (канонический): {portable_path}")
    print(f"work (зеркало):          {work_path}")

    dp = _load(portable_path)
    dw = _load(work_path)
    idp = {r["id"]: r for r in dp["debts"]}
    idw = {r["id"]: r for r in dw["debts"]}

    changes = []  # (action, id, detail)
    next_rs = _next_rs(dp["debts"])

    def _norm(s):
        return re.sub(r"\s+", " ", (s or "")).strip().lower()[:70]

    for wid, wrec in sorted(idw.items()):
        if wid.startswith("RS-"):
            continue  # RS-пространство управляется только каноническим (portable)
        if wid not in idp:
            changes.append(("ADD", wid, "нет в portable, добавить как есть"))
            continue
        if idp[wid] == wrec:
            continue  # идентичны
        # Тот же ID и тот же title (нормализованный) -> та же сущность, portable каноничен.
        # CLI правит portable; work-версия устарела. НЕ порождать RS-дубликат.
        if _norm(idp[wid].get("title")) == _norm(wrec.get("title")):
            changes.append(("SKIP", wid, "та же сущность, portable каноничен (work устарел)"))
            continue
        # ID занят ДРУГОЙ записью в каноническом -> сохранить work-версию как RS-*
        new_id = f"RS-{next_rs:03d}"
        next_rs += 1
        changes.append(("RENAME", wid, f"конфликт с portable.{wid} -> {new_id} (исследовательская)"))

    if dry_run:
        print("\n=== ПЛАН (dry-run) ===")
        for action, id_, detail in changes:
            print(f"  {action:8s} {id_:10s} {detail}")
        print(f"\nИтого операций: {len(changes)}")
        return 0

    # Выполняем
    if do_backup:
        print("\nБэкап:")
        _backup(portable_path, "PORTABLE")
        _backup(work_path, "WORK")

    debts = [dict(r) for r in dp["debts"]]
    idp2 = {r["id"]: r for r in debts}
    for wid, wrec in sorted(idw.items()):
        if wid.startswith("RS-"):
            continue  # RS-пространство управляется только каноническим (portable)
        if wid not in idp:
            debts.append(dict(wrec))
            idp2[wid] = debts[-1]
            continue
        if idp[wid] == wrec:
            continue
        # та же сущность (title совпадает) -> portable каноничен, work устарел, не дублировать
        if _norm(idp[wid].get("title")) == _norm(wrec.get("title")):
            continue
        # конфликт: work-версия -> RS-*
        new_id = f"RS-{_next_rs(debts):03d}"
        renamed = dict(wrec)
        renamed["id"] = new_id
        renamed["title"] = (wrec.get("title") or "") + f" [было work {wid}]"
        renamed["notes"] = (wrec.get("notes") or "") + (
            f"\nКонсолидация {datetime.date.today().isoformat()}: "
            f"ID {wid} был занят другой записью в каноническом реестре (portable), "
            f"переименован в {new_id} чтобы не потерять данные.")
        debts.append(renamed)
        idp2[new_id] = renamed

    # сортировка по ID (TD-* затем RS-*)
    def sort_key(r):
        m = re.match(r"^(TD|RS)-(\d+)", r["id"])
        return (0 if r["id"].startswith("TD") else 1, int(m.group(2)) if m else 999999)
    debts.sort(key=sort_key)

    open_c = sum(1 for r in debts if r.get("status") == "open")
    closed_c = sum(1 for r in debts if r.get("status") == "closed")
    dp["debts"] = debts
    dp["counts"] = {"total": len(debts), "open": open_c, "closed": closed_c}
    dp["updated"] = datetime.date.today().isoformat()
    dp["consolidation"] = {
        "merged_from_work": True,
        "date": datetime.date.today().isoformat(),
        "note": "Единый реестр: work-записи с конфликтующими ID сохранены как RS-*",
    }

    portable_path.write_text(json.dumps(dp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nПортable обновлён: total={len(debts)} open={open_c} closed={closed_c}")

    # синхронизация в work
    work_path.write_text(json.dumps(dp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Work синхронизирован: {work_path}")

    print("\n=== Операции ===")
    for action, id_, detail in changes:
        print(f"  {action:8s} {id_:10s} {detail}")

    print("\nOK: консолидация завершена. Канонический реестр = portable (проверь git status).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Консолидация двух реестров техдолгов")
    ap.add_argument("--portable", default=str(DEFAULT_PORTABLE))
    ap.add_argument("--work", default=str(DEFAULT_WORK))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backup", action="store_true")
    args = ap.parse_args()
    return merge(Path(args.portable), Path(args.work), args.dry_run, args.backup)


if __name__ == "__main__":
    raise SystemExit(main())