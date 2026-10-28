#!/usr/bin/env python3
"""Paper Review System - Dependency Checker (OpenCode portable port of check-deps.sh).

Checks that all required Python packages are installed and reports the optional
marker-pdf status. Windows/portable friendly: no bash dependency (the original
Claude hook used bash; in OpenCode the equivalent runs from the plugin's
setup via the harness .venv interpreter).
"""
from __future__ import annotations

import importlib
import json
import sys

REQUIRED = [
    ("mcp", "mcp>=1.0.0"),
    ("pymupdf", "pymupdf4llm>=0.2.9"),
    ("pydantic", "pydantic>=2.0"),
    ("httpx", "httpx>=0.27.0"),
    ("PIL", "Pillow>=10.0"),
]
OPTIONAL = [("marker", "marker-pdf (ML LaTeX recovery)")]


def check() -> dict:
    missing: list[str] = []
    for mod, req in REQUIRED:
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(req)
    optional_ok: list[str] = []
    for mod, label in OPTIONAL:
        try:
            importlib.import_module(mod)
            optional_ok.append(label)
        except Exception:
            pass
    all_ok = not missing
    return {
        "all_required_ok": all_ok,
        "missing": missing,
        "optional_installed": optional_ok,
        "exit_code": 0 if all_ok else 1,
    }


def main() -> int:
    report = check()
    if report["all_required_ok"]:
        print("OK: all required dependencies are installed.")
        if report["optional_installed"]:
            print(f"INFO: optional installed: {', '.join(report['optional_installed'])}")
        else:
            print("INFO: optional marker-pdf not installed (pymupdf fallback will be used)")
        return 0
    print("MISSING dependencies detected:")
    for req in report["missing"]:
        print(f"  - {req}")
    print("install: see requirements in harness scripts/paper-review/requirements.txt")
    return 1


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(check(), ensure_ascii=False))
        sys.exit(check()["exit_code"])
    sys.exit(main())