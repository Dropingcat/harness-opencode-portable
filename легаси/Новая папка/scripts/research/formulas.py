"""formulas.py: мост у researcher_core.formulas (детект формул/констант).

Совместимость numeric_comparator.py (top-level import).
Источник истины: scripts/researcher/researcher_core/formulas.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "researcher"))

from researcher_core.formulas import (  # noqa: E402
    check_constant,
    detect_formula,
    list_formulas,
)

__all__ = ["detect_formula", "check_constant", "list_formulas"]