#!/usr/bin/env python3
"""Register/unregister the native Harness OpenCode plugin in the project config.

TD-D3 (issue #16): TEMPORARY transitional helper. In v1 this project-scoped helper is
the operational way to (un)register the plugin for development/bootstrap convenience.
The canonical production path is bootstrap + `.opencode/opencode.json` (project-scoped
file:// registration of packages/opencode-harness-plugin/dist/index.js); the eventual
target architecture replaces this helper with installer/package registration
(INTERFACE_CONTROL.md §12: REPLACE by installer). Do NOT add new runtime consumers of
config/opencode_plugin_config.json — it is a status declaration, not a source of truth.
Gate: scripts/tools/check_plugin_registration_status.py (I1-I5, fail-closed).

Portable module uses project-scoped registration (.opencode/opencode.json) with a
file:// URI to the compiled dist/index.js. Nothing is written to the global config.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def harness_root() -> Path:
    import os
    return Path(os.environ.get("OPENCODE_HARNESS_ROOT", Path(__file__).resolve().parents[1]))


def _cfg_path(root: Path) -> Path:
    return root / ".opencode" / "opencode.json"


def _plugin_uri(root: Path) -> str:
    entry = root / "packages" / "opencode-harness-plugin" / "dist" / "index.js"
    if not entry.is_file():
        print(f"ERROR: compiled entry not found: {entry}; run `npm run build` in the package first", file=sys.stderr)
        sys.exit(2)
    return "file:///" + str(entry.resolve()).replace("\\", "/")


def _load(root: Path) -> dict:
    cfg_path = _cfg_path(root)
    if cfg_path.is_file():
        return json.loads(cfg_path.read_text(encoding="utf-8-sig"))
    return {"$schema": "https://opencode.ai/config.json"}


def _save(root: Path, cfg: dict) -> None:
    cfg_path = _cfg_path(root)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def register() -> int:
    root = harness_root()
    uri = _plugin_uri(root)
    cfg = _load(root)
    plugins = [p for p in cfg.get("plugin", []) if not (isinstance(p, str) and "opencode-harness-plugin" in p)]
    if uri not in plugins:
        plugins.append(uri)
    cfg["plugin"] = plugins
    _save(root, cfg)
    print(f"Native plugin registered (project-scoped): {uri}")
    return 0


def unregister() -> int:
    root = harness_root()
    cfg = _load(root)
    plugins = [p for p in cfg.get("plugin", []) if not (isinstance(p, str) and "opencode-harness-plugin" in p)]
    cfg["plugin"] = plugins
    _save(root, cfg)
    print("Native plugin removed from project config")
    return 0


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("register", "unregister"):
        print("usage: register_plugin.py [register|unregister]")
        return 2
    return register() if sys.argv[1] == "register" else unregister()


if __name__ == "__main__":
    raise SystemExit(main())