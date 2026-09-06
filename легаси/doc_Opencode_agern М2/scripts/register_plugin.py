#!/usr/bin/env python3
"""Register/unregister tool-skill-contract-router plugin in OpenCode config."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def register_plugin() -> int:
    config_path = Path.home() / ".config" / "opencode" / "opencode.jsonc"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return 1

    # Read and parse JSONC (strip comments)
    content = config_path.read_text(encoding="utf-8")
    # Simple comment stripper for JSONC
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        lines.append(line)
    config = json.loads("\n".join(lines))

    # Ensure plugin array exists
    if "plugin" not in config:
        config["plugin"] = []

    plugin_entry = "E:/Documents/Документы/doc_Opencode_agern/plugins/tool-skill-contract-router.ts"

    # Check if already registered
    if plugin_entry in config["plugin"]:
        print("Plugin already registered")
        return 0

    # Add plugin
    config["plugin"].append(plugin_entry)

    # Write back (as JSON, comments will be lost but functional)
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Plugin registered successfully")
    return 0


def unregister_plugin() -> int:
    config_path = Path.home() / ".config" / "opencode" / "opencode.jsonc"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return 1

    content = config_path.read_text(encoding="utf-8")
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        lines.append(line)
    config = json.loads("\n".join(lines))

    plugin_entry = "E:/Documents/Документы/doc_Opencode_agern/plugins/tool-skill-contract-router.ts"

    if "plugin" in config and plugin_entry in config["plugin"]:
        config["plugin"].remove(plugin_entry)
        # Write back
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("Plugin unregistered successfully")
    else:
        print("Plugin not found in config")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: register_plugin.py [register|unregister]")
        return 2

    action = sys.argv[1]
    if action == "register":
        return register_plugin()
    elif action == "unregister":
        return unregister_plugin()
    else:
        print(f"unknown action: {action}")
        return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(main())