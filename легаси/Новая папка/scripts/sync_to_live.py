#!/usr/bin/env python3
"""
sync_to_live.py — односторонняя синхронизация HARNESS -> LIVE OpenCode config.

Принцип: HARNESS = source of truth; LIVE = runtime mirror.
Скрипт копирует только управляемые подмножества (не весь HARNESS):
- scripts/ -> ~/.config/opencode/scripts
- agents/*.md -> ~/.config/opencode/agent
- shared/*.md -> ~/.config/opencode/shared

Безопасность: dry-run по умолчанию; --apply для реальной записи.

Примеры:
  python scripts/sync_to_live.py                # dry-run: что бы скопировалось
  python scripts/sync_to_live.py --apply        # реально синхронизировать
  python scripts/sync_to_live.py --only scripts # только scripts
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def live_root() -> Path:
    return Path.home() / ".config" / "opencode"


def plan_copy(src_root: Path, dst_root: Path, rel: str, pattern: str, dst_rel: str | None = None) -> list[tuple[Path, Path]]:
    pairs = []
    src_dir = src_root / rel
    if not src_dir.exists():
        return pairs
    target_rel = dst_rel if dst_rel is not None else rel
    files = sorted(src_dir.glob(pattern))
    for f in files:
        pairs.append((f, dst_root / target_rel / f.name))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync HARNESS -> LIVE (one-way)")
    parser.add_argument("--apply", action="store_true", help="actually copy (default dry-run)")
    parser.add_argument("--only", choices=["scripts", "agents", "shared", "plugins"], default=None, help="subset only")
    args = parser.parse_args()

    src = repo_root()
    dst = live_root()
    if not dst.exists():
        print(f"live root not found: {dst}")
        return 2

    plan: list[tuple[Path, Path]] = []
    if args.only in (None, "scripts"):
        plan += plan_copy(src, dst, "scripts", "*.py")
        plan += plan_copy(src, dst, "scripts", "*.ps1")
        plan += plan_copy(src, dst, "scripts", "*.sh")
        # also nested subdirs of scripts
        for sub in ["code-factory", "router", "memory", "research", "orchestration", "writer"]:
            plan += plan_copy(src, dst, f"scripts/{sub}", "*.py")
            plan += plan_copy(src, dst, f"scripts/{sub}", "*.sh")
            plan += plan_copy(src, dst, f"scripts/{sub}", "*.yaml")
    if args.only in (None, "agents"):
        # LIVE использует единственное число 'agent' (не 'agents')
        plan += plan_copy(src, dst, "agents", "*.md", dst_rel="agent")
    if args.only in (None, "shared"):
        plan += plan_copy(src, dst, "shared", "*.md")
    if args.only in (None, "plugins"):
        plan += plan_copy(src, dst, "plugins", "*.ts")
        plan += plan_copy(src, dst, "plugins", "*.js")

    if not plan:
        print("nothing to sync")
        return 0

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"== {mode}: {len(plan)} files ==")
    for s, d in plan:
        if d.parent and not d.parent.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
        if args.apply:
            shutil.copy2(s, d)
            print("  wrote", d.relative_to(dst))
        else:
            print("  would-write", d.relative_to(dst))

    if not args.apply:
        print("\n(dry-run; re-run with --apply to actually sync)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())