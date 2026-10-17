#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""relocate_paths.py — сканер абсолютных путей HARNESS_ROOT (TD-AUD-3/TD-DEV-38).

Детерминированный помощник развёртывания harness на НОВОМ сервере:
ищет вхождения абсолютного пути `E:\\opencode_harness_portable` /
`E:/opencode_harness_portable` по дереву и предлагает замену на
переменную окружения `$HARNESS_ROOT` (или относительный корень).

Режимы:
  --check  (по умолчанию) — только отчёт: файл -> число вхождений ->
           предлагаемая замена. Exit 1, если вхождения найдены,
           exit 0, если дерево чистое.
  --apply  — замена на `$HARNESS_ROOT` с бэкапом оригинала
           (<файл>.relocate.bak в той же директории).

ВАЖНО: --apply НЕ предназначен для текущего (LIVE) дерева E:\\opencode_harness_portable —
его запускают на НОВОМ сервере после клонирования, либо вендорят копию.
На LIVE допустим только --check (отчёт).

Исключаемые каталоги: .venv, .git, node_modules, dist, __pycache__,
.pytest_cache, .runs, .kanban.db (файл-исключение тоже учитывается).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# То, что ищем. Два варианта разделителей + escape-вариант перевода строки.
PATTERNS = (
    "E:\\opencode_harness_portable",   # двойной backslash (как в исходниках .py/.json)
    "E:/opencode_harness_portable",    # forward slash
)
# Одиночный backslash (реальный путь в текстовых файлах) — покрывается через
# нормализацию: сначала ищем double-backslash, затем single. Т.к. double-backslash
# это литерал из двух символов '\\', а single — из одного '\\', достаточно
# искать оба; порядок не важен, замена одинаковая.

REPLACEMENT = "$HARNESS_ROOT"

EXCLUDE_DIRS = {
    ".venv", "venv", "env",
    ".git",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".runs",
    ".mypy_cache",
    "htmlcov",
    ".coverage",
}
EXCLUDE_FILES = {".kanban.db", ".relocate.bak"}

# Расширения, которые стоит проверить (текстовые/настраиваемые).
_TRAILING_BYTE = None  # placeholder (для будущих бинарных фильтров)


def _should_skip_file(path: Path) -> bool:
    if path.name in EXCLUDE_FILES:
        return True
    try:
        # Пропускаем очевидно бинарные файлы (быстрая эвристика).
        with path.open("rb") as fh:
            head = fh.read(8192)
        return b"\x00" in head
    except OSError:
        return True


def scan(root: Path) -> list[tuple[Path, int]]:
    """Возвращает [(path, count), ...] для файлов с вхождениями путей."""
    hits: list[tuple[Path, int]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        rel = dp.relative_to(root)
        # Пропускаем исключаемые каталоги на любом уровне.
        dirnames[:] = [
            d for d in dirnames
            if d not in EXCLUDE_DIRS and not (rel / d).name.startswith(".relocate")
        ]
        for fname in filenames:
            if fname in EXCLUDE_FILES:
                continue
            fp = dp / fname
            if _should_skip_file(fp):
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            count = 0
            for pat in PATTERNS:
                count += text.count(pat)
            if count:
                hits.append((fp, count))
    return hits


def apply_replacements(hits: list[tuple[Path, int]]) -> tuple[int, int]:
    """Заменяет вхождения на REPLACEMENT; бэкап рядом. Возвращает (файлов, вхождений)."""
    replaced_files = 0
    replaced_occurrences = 0
    for fp, count in hits:
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        new_text = text
        for pat in PATTERNS:
            new_text = new_text.replace(pat, REPLACEMENT)
        if new_text == text:
            continue
        backup = fp.with_name(fp.name + ".relocate.bak")
        if not backup.exists():
            backup.write_text(text, encoding="utf-8")
        fp.write_text(new_text, encoding="utf-8")
        replaced_files += 1
        replaced_occurrences += count
    return replaced_files, replaced_occurrences


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="relocate_paths.py",
        description="Сканер абсолютных путей E:\\opencode_harness_portable (TD-AUD-3/TD-DEV-38).",
    )
    ap.add_argument("--root", default=".", help="Корень дерева для сканирования (по умолчанию: текущий каталог).")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Только отчёт; exit 1, если найдено.")
    group.add_argument("--apply", action="store_true", help="Замена на $HARNESS_ROOT с бэкапом (.relocate.bak).")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: root не является каталогом: {root}", file=sys.stderr)
        return 2

    hits = scan(root)
    if not hits:
        print(f"OK: абсолютных путей {next(iter(PATTERNS))}* не найдено в {root} (исключённые каталоги пропущены).")
        return 0

    total = sum(c for _, c in hits)
    print(f"Найдено {len(hits)} файлов, {total} вхождений абсолютного пути (E:\\opencode_harness_portable / E:/opencode_harness_portable):")
    print("=" * 100)
    for fp, count in sorted(hits):
        rel = fp.relative_to(root)
        print(f"{rel} -> {count} вхождений -> замена на {REPLACEMENT}")
    print("=" * 100)

    if args.apply:
        n_files, n_occ = apply_replacements(hits)
        print(f"[apply] Заменено: {n_files} файлов, {n_occ} вхождений. Бэкапы: <файл>.relocate.bak.")
        return 1  # после замены дерево "грязное" относительно исходного — exit 1 как сигнал
    # --check (по умолчанию)
    print("[check] НЕ применено. На новом сервере запустите: python scripts/tools/relocate_paths.py --apply --root <клонированный_harnes>")
    return 1


if __name__ == "__main__":
    sys.exit(main())