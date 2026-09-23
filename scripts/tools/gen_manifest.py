#!/usr/bin/env python3
"""Генератор канонических машинных файлов поставки (закрытие TD-D9).

Создаёт в корне репозитория:
  - MANIFEST.json   — инвентарь дерева: относительные пути, размеры, sha256;
  - SHA256SUMS.txt  — чексуммы в формате `sha256  path` (совместим с sha256sum -c);
  - config/decision_aliases.json — стаб-скелет алиасов решений (если отсутствует).

Детерминированность: файлы сортируются по пути; поля времени фиксированы
(`generated` не входит в body хэша манифеста). stdlib-only.

Использование:
  python3 scripts/tools/gen_manifest.py            # генерация
  python3 scripts/tools/gen_manifest.py --check    # верификация без записи (exit 1 при расхождении)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".runs", ".opencode",
    "dist", "build", ".pytest_cache", ".mypy_cache", ".idea", ".vscode",
}
EXCLUDE_FILES = {"MANIFEST.json", "SHA256SUMS.txt"}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect() -> list[dict]:
    entries = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        parts = rel.parts
        # any path component (dir or file name) starting with "." is excluded
        if any(part.startswith(".") for part in parts):
            continue
        if any(part in EXCLUDE_DIRS for part in parts):
            continue
        if rel.name in EXCLUDE_FILES or rel.suffix == ".pyc":
            continue
        entries.append({
            "path": rel.as_posix(),
            "size": p.stat().st_size,
            "sha256": sha256_file(p),
        })
    return entries


DECISION_ALIASES_STUB = {
    "schema": "decision_aliases/1.0",
    "note": "Канонические алиасы решений (README_FIRST). Пополняется вручную/генератором.",
    "aliases": {},
}


def render_manifest(entries: list[dict]) -> str:
    doc = {
        "schema": "harness-manifest/1.0",
        "root": ".",
        "file_count": len(entries),
        "files": entries,
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def render_sums(entries: list[dict]) -> str:
    return "".join(f"{e['sha256']}  {e['path']}\n" for e in entries)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="только верификация существующих файлов")
    args = ap.parse_args()

    entries = collect()
    manifest = render_manifest(entries)
    sums = render_sums(entries)

    mf = ROOT / "MANIFEST.json"
    sf = ROOT / "SHA256SUMS.txt"
    da = ROOT / "config" / "decision_aliases.json"

    if args.check:
        ok = True
        if not mf.exists() or mf.read_text(encoding="utf-8") != manifest:
            print("STALE: MANIFEST.json", file=sys.stderr); ok = False
        if not sf.exists() or sf.read_text(encoding="utf-8") != sums:
            print("STALE: SHA256SUMS.txt", file=sys.stderr); ok = False
        if not da.exists():
            print("MISSING: config/decision_aliases.json", file=sys.stderr); ok = False
        print(json.dumps({"ok": ok, "files": len(entries)}, ensure_ascii=False))
        return 0 if ok else 1

    mf.write_text(manifest, encoding="utf-8")
    sf.write_text(sums, encoding="utf-8")
    if not da.exists():
        da.parent.mkdir(parents=True, exist_ok=True)
        da.write_text(json.dumps(DECISION_ALIASES_STUB, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps({"ok": True, "files": len(entries),
                      "written": [str(mf.relative_to(ROOT)), str(sf.relative_to(ROOT))]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
