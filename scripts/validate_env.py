#!/usr/bin/env python3
"""Validate required environment variables for runtime integration."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def validate_env() -> int:
    config_path = Path(__file__).resolve().parents[1] / "config" / "runtime_integration_policy.json"
    policy = load_json(config_path)
    
    env_cfg = policy.get("environment", {})
    required = env_cfg.get("required_vars", [])
    optional = env_cfg.get("optional_vars", [])
    validation = env_cfg.get("validation", "strict")

    missing = []
    for var in required:
        val = os.environ.get(var)
        if not val:
            missing.append(var)
        else:
            print(f"OK: {var} = {val}")

    for var in optional:
        val = os.environ.get(var)
        if val:
            print(f"OK (optional): {var} = {val}")
        else:
            print(f"MISSING (optional): {var}")

    if missing:
        print(f"MISSING REQUIRED: {missing}")
        if validation == "strict":
            return 1
    else:
        print("All required environment variables set")
        return 0


def main() -> int:
    return validate_env()


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
