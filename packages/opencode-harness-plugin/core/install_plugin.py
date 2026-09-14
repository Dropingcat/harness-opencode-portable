#!/usr/bin/env python3
"""Install the Harness native OpenCode plugin into a project/global plugin directory.

Standard OpenCode mechanism: a .ts file in .opencode/plugins/ is auto-discovered,
or the plugin package is registered via config. This installer writes the plugin
entry and reports the exact registration, without touching API keys.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def harness_root() -> Path:
    env = __import__("os").environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def _plugin_dir(target: str, root: Path) -> Path:
    if target == "project":
        return root / ".opencode" / "plugins"
    if target == "global":
        return Path.home() / ".config" / "opencode" / "plugins"
    raise ValueError(f"unknown target: {target}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["project", "global"], default="project")
    ap.add_argument("--entry", default=None, help="source entry .ts to copy (default packages/opencode-harness-plugin/src/index.ts)")
    ap.add_argument("--report", default=None, help="path to write install report JSON")
    args = ap.parse_args()

    root = harness_root()
    src = Path(args.entry) if args.entry else root / "packages" / "opencode-harness-plugin" / "src" / "index.ts"
    if not src.is_file():
        print(f"ERROR: plugin entry not found: {src}", file=sys.stderr)
        return 2

    dest_dir = _plugin_dir(args.target, root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "opencode-harness-plugin.ts"
    shutil.copy2(src, dest)

    report = {
        "schema": "harness-opencode-plugin-install/1.0",
        "target": args.target,
        "source": str(src),
        "installed": str(dest),
        "mechanism": "opencode plugin auto-discovery (.opencode/plugins) or config plugin entry",
        "no_api_keys_touched": True,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())