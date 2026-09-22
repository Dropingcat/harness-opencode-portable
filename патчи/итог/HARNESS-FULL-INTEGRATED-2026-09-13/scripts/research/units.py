"""units.py — мост к единому реестру единиц researcher_core.numeric.

Нужен для совместимости numeric_comparator.py (top-level import).
Перенесено из default project researcher-core (2026-09-06). Источник истины:
scripts/researcher/researcher_core/numeric.py (UnitRegistry + convert/dimension).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "researcher"))

from researcher_core.numeric import (  # noqa: E402
    UnitRegistry,
    convert,
    dimension,
    normalize_unit,
)

__all__ = ["convert", "dimension", "normalize_unit", "UnitRegistry"]