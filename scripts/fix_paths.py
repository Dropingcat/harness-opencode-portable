#!/usr/bin/env python3
"""Fix hardcoded paths in config/agent files using path_resolution_map.json."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_env(value: str) -> str:
    """Resolve ${VAR} patterns."""
    def replace(match):
        var = match.group(1)
        return os.environ.get(var, match.group(0))
    return re.sub(r"\$\{([^}]+)\}", replace, value)


def scan_files(root: Path, extensions: list, exclude_dirs: list) -> list[Path]:
    files = []
    for ext in extensions:
        for f in root.rglob(f"*{ext}"):
            if any(excl in f.parts for excl in exclude_dirs):
                continue
            files.append(f)
    return files


def fix_file(filepath: Path, mappings: list, dry_run: bool = True, backup: bool = True) -> tuple[bool, int]:
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, 0

    original = content
    replacements = 0

    for mapping in mappings:
        pattern = mapping["pattern"]
        replacement = resolve_env(mapping["replacement"])
        if pattern in content:
            content = content.replace(pattern, replacement)
            replacements += content.count(pattern)  # approximate

    if content != original:
        if not dry_run:
            if backup:
                backup_path = filepath.with_suffix(filepath.suffix + ".bak")
                backup_path.write_text(original, encoding="utf-8")
            filepath.write_text(content, encoding="utf-8")
        return True, replacements
    return False, 0


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Fix hardcoded paths in project files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be changed")
    parser.add_argument("--no-backup", action="store_true", help="Don't create backup files")
    parser.add_argument("--root", default=None, help="Project root (default: repo root)")
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parents[1]
    maps_path = Path(__file__).resolve().parents[1] / "config" / "path_resolution_map.json"
    config = load_json(maps_path)

    mappings = config.get("mappings", [])
    scan_cfg = config.get("scan", {})
    replace_cfg = config.get("replacement", {})

    extensions = scan_cfg.get("include_extensions", [".md", ".py", ".json", ".jsonc", ".ts", ".js", ".yaml", ".yml", ".txt"])
    exclude_dirs = scan_cfg.get("exclude_dirs", [".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"])
    dry_run = args.dry_run or replace_cfg.get("dry_run_default", True)
    backup = not args.no_backup and replace_cfg.get("backup_original", True)

    files = scan_files(root, extensions, exclude_dirs)
    print(f"Scanning {len(files)} files...")

    total_changed = 0
    total_replacements = 0

    for f in files:
        changed, reps = fix_file(f, mappings, dry_run=dry_run, backup=backup)
        if changed:
            total_changed += 1
            total_replacements += reps
            print(f"  {'[DRY RUN] ' if dry_run else ''}Fixed: {f.relative_to(root)} ({reps} replacements)")

    print(f"\nTotal files changed: {total_changed}")
    print(f"Total replacements: {total_replacements}")
    print(f"Mode: {'DRY RUN' if dry_run else 'APPLIED'}")
    return 0
if __name__ == "__main__":
    import sys
    raise SystemExit(main())
