#!/usr/bin/env python3
"""Validate required environment variables for runtime integration."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def load_json(path: Path) -> dict:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def _same_path(actual: Path, expected: Path) -> bool:
    """Compare paths after resolving junctions and normalizing platform case."""
    return os.path.normcase(str(actual.resolve())) == os.path.normcase(str(expected.resolve()))


def validate_writer_core(repo_root: Path) -> list[str]:
    """Validate native Writer Core locations without importing optional packages."""
    errors: list[str] = []
    expected_root = repo_root / "scripts" / "writer-core"
    expected_registry = expected_root / "linguistic_assets"

    configured: dict[str, Path] = {}
    for name in (
        "WRITER_CORE_ROOT",
        "WRITER_RUNS_DIR",
        "WRITER_LINGUISTICS_REGISTRY_DIR",
    ):
        value = os.environ.get(name)
        if not value:
            errors.append(f"{name} is not set")
            continue
        configured[name] = Path(value).expanduser()
        print(f"OK: {name} = {value}")

    writer_root = configured.get("WRITER_CORE_ROOT")
    if writer_root is not None and not _same_path(writer_root, expected_root):
        errors.append(
            f"WRITER_CORE_ROOT must point to canonical root {expected_root}, got {writer_root}"
        )

    cli_path = expected_root / "wc_cli.py"
    if not cli_path.is_file():
        errors.append(f"canonical Writer Core CLI not found: {cli_path}")
    else:
        print(f"OK: canonical Writer Core CLI = {cli_path}")

    registry_dir = configured.get("WRITER_LINGUISTICS_REGISTRY_DIR")
    if registry_dir is not None:
        if not _same_path(registry_dir, expected_registry):
            errors.append(
                "WRITER_LINGUISTICS_REGISTRY_DIR must point to "
                f"{expected_registry}, got {registry_dir}"
            )
        elif not registry_dir.is_dir():
            errors.append(f"linguistics registry directory not found: {registry_dir}")

    runs_dir = configured.get("WRITER_RUNS_DIR")
    if runs_dir is not None and not runs_dir.is_absolute():
        errors.append(f"WRITER_RUNS_DIR must be absolute, got {runs_dir}")

    writer_python = os.environ.get("WRITER_PYTHON")
    if not writer_python:
        errors.append("WRITER_PYTHON is not set")
    else:
        resolved_python = shutil.which(writer_python)
        if resolved_python is None:
            errors.append(f"WRITER_PYTHON is not executable or was not found: {writer_python}")
        else:
            print(f"OK: WRITER_PYTHON = {resolved_python}")

    return errors


def validate_env() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "config" / "runtime_integration_policy.json"
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

    writer_errors = validate_writer_core(repo_root)

    if missing:
        print(f"MISSING REQUIRED: {missing}")
        if validation == "strict":
            return 1
    else:
        print("All policy-required environment variables set")

    if writer_errors:
        for error in writer_errors:
            print(f"WRITER CORE ERROR: {error}")
        return 1

    print("Writer Core environment valid")
    return 0


def main() -> int:
    return validate_env()


if __name__ == "__main__":
    raise SystemExit(main())
