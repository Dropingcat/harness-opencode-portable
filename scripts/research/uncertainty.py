"""uncertainty.py: мост к researcher_core.uncertainty (неопределённость).

Совместимость numeric_comparator.py (top-level import).
Источник истины: scripts/researcher/researcher_core/uncertainty.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "researcher"))

from researcher_core.uncertainty import (  # noqa: E402
    compare_with_uncertainty,
    parse_uncertainty,
    values_in_range,
    values_overlap,
)

__all__ = ["parse_uncertainty", "compare_with_uncertainty", "values_overlap", "values_in_range"]