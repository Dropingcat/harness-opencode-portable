#!/usr/bin/env python3
"""Portable health check for harness integration (TD-D2).

Канонический health-инструмент — plugin-aware doctor:
    packages/opencode-harness-plugin/core/doctor.py

Этот модуль — тонкая совместимая обёртка (исторический путь запуска), которая
делегирует doctor.py и сохраняет контракт выхода (0 = HEALTHY, 1 = UNHEALTHY).
Legacy-проверки («plugin registered + DB accessible») здесь больше не дублируются.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HARNESS_ROOT = Path(
    os.environ.get("OPENCODE_HARNESS_ROOT", Path(__file__).resolve().parents[1])
).resolve()
DOCTOR = HARNESS_ROOT / "packages" / "opencode-harness-plugin" / "core" / "doctor.py"


def main(argv: list[str]) -> int:
    if not DOCTOR.is_file():
        print(f"FAIL: canonical doctor not found: {DOCTOR}")
        return 1
    r = subprocess.run([sys.executable, str(DOCTOR), *argv], cwd=str(HARNESS_ROOT))
    print(f"\nOverall: {'HEALTHY' if r.returncode == 0 else 'UNHEALTHY'}")
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
