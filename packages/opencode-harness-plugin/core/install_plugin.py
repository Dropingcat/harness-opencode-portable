#!/usr/bin/env python3
"""Install the Harness native OpenCode plugin into a project/global config.

Standard OpenCode mechanism: explicit `plugin: [ "file:///.../dist/index.js" ]`
entry in the project (or global) opencode config. This is the canonical path
that works in both CLI and Desktop and avoids double-loading with auto-discovery.

Requires the compiled package entry: run `npm run build` in the package first.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def harness_root() -> Path:
    env = os.environ.get("OPENCODE_HARNESS_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3]


def _config_path(target: str, root: Path) -> Path:
    if target == "project":
        return root / ".opencode" / "opencode.json"
    if target == "global":
        return Path.home() / ".config" / "opencode" / "opencode.json"
    raise ValueError(f"unknown target: {target}")


def _dist_entry(root: Path) -> Path:
    dist_entry = root / "packages" / "opencode-harness-plugin" / "dist" / "index.js"
    if not dist_entry.is_file():
        print(f"ERROR: compiled entry not found: {dist_entry}; run `npm run build` first", file=sys.stderr)
        sys.exit(2)
    return dist_entry


def _plugin_file_uri(entry: Path) -> str:
    # file:// URL form used by opencode plugin config.
    path_str = str(entry.resolve()).replace("\\", "/")
    return f"file:///{path_str}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["project", "global"], default="project")
    ap.add_argument("--report", default=None, help="path to write install report JSON")
    args = ap.parse_args()

    root = harness_root()
    config = _config_path(args.target, root)
    dist = _dist_entry(root)
    uri = _plugin_file_uri(dist)

    # Load existing config (if any), preserving unrelated fields.
    if config.is_file():
        try:
            cfg = json.loads(config.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"ERROR: existing config is invalid JSON: {config}: {exc}", file=sys.stderr)
            sys.exit(2)
        if not isinstance(cfg, dict):
            print(f"ERROR: existing config root is not an object: {config}", file=sys.stderr)
            sys.exit(2)
    else:
        cfg = {"$schema": "https://opencode.ai/config.json"}

    plugins = cfg.setdefault("plugin", [])
    if not isinstance(plugins, list):
        print(f"ERROR: plugin key in {config} is not an array", file=sys.stderr)
        sys.exit(2)

    # Remove any prior harness entries to keep exactly one registration.
    cfg["plugin"] = [p for p in plugins if not (isinstance(p, str) and "opencode-harness-plugin" in p)]
    cfg["plugin"].append(uri)

    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = {
        "schema": "harness-opencode-plugin-install/1.0",
        "target": args.target,
        "config": str(config),
        "plugin_entry": uri,
        "mechanism": "opencode explicit plugin: entry (project/global config)",
        "deduplicated": True,
        "no_api_keys_touched": True,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())