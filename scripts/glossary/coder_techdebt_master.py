#!/usr/bin/env python3
"""Build the unified tech-debt master document (TD-090).

Reads config/tech_debt.json and emits docs/TRACKERS/TECH_DEBT_MASTER.md —
a single, human-readable ledger where every record is traceable
(source/created_by/created_at when present).

--check: verify that every record in the registry appears in the master
         (exit non-zero if stale).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_master(root: str | Path) -> str:
    root_path = Path(root if isinstance(root, str) else root)
    registry_path = root_path / "config" / "tech_debt.json"
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    debts = data.get("debts", [])

    lines: list[str] = [
        "# Tech Debt Master — единый реестр проекта",
        "",
        f"Дата: {data.get('updated', '2026-09-18')}",
        f"Всего: {len(debts)} | open: {data['counts']['open']} | closed: {data['counts']['closed']}",
        "",
        "Префиксы: CD-* Coder, WR-* Writer, RS-* Researcher, PL-* plugin, TD-* общий.",
        "",
        "## Активные (open)",
        "",
        "| ID | Sevr | Owner | Title | Source/Created |",
        "|---|---|---|---|---|",
    ]
    for x in sorted(debts, key=lambda d: d["id"]):
        if x.get("status") != "open":
            continue
        src = x.get("source") or ""
        cb = x.get("created_by") or ""
        trace = f"{cb}" if cb else (src[:30] if src else "-")
        title = (x.get("title") or "").replace("|", "/")[:70]
        lines.append(f"| {x['id']} | {x.get('severity','-')} | {x.get('owner','-')} | {title} | {trace} |")

    lines += ["", "## Закрытые (closed)", "", "| ID | Title | Закрыт |", "|---|---|---|"]
    for x in sorted(debts, key=lambda d: d["id"]):
        if x.get("status") != "closed":
            continue
        title = (x.get("title") or "").replace("|", "/")[:70]
        closed = x.get("closed_at") or "-"
        lines.append(f"| {x['id']} | {title} | {closed} |")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build/verify the unified tech-debt master.")
    ap.add_argument("--root", default=r"E:\Documents\Документы\doc_Opencode_agern-new")
    ap.add_argument("--check", action="store_true", help="verify master is up-to-date")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    root = Path(args.root)
    out = Path(args.out) if args.out else root / "docs/TRACKERS/TECH_DEBT_MASTER.md"
    text = build_master(root)

    if args.check:
        if out.is_file() and out.read_text(encoding="utf-8") == text:
            print(f"OK {out}: master in sync")
            return 0
        print(f"STALE {out}: run coder_techdebt_master.py --root {root}", file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out}: {len(text.splitlines())} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())