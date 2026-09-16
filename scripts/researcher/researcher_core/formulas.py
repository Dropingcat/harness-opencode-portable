"""Deterministic formula detection and constant checks — port of legacy formulas.py.

Pure, dependency-free, behind NumericValue boundary. Constants are domain
definitions (Scherrer K), not epistemic heuristics, so they are named and debt-clean.
"""

from __future__ import annotations

from dataclasses import dataclass


_SCHERRER_CANONICAL_K_TEXT = "0.9"  # debt-scan: ignore-line -- domain constant Scherrer K text
_SCHERRER_ALTERNATIVE_K_TEXT = "1.0"  # debt-scan: ignore-line -- alternative Scherrer K text
_SCHERRER_K_EQUALS_ONE = "K=1"  # debt-scan: ignore-line -- text marker
_SCHERRER_CANONICAL_K_VALUE = 0.9  # debt-scan: ignore-line -- domain constant value
_SCHERRER_ALTERNATIVE_K_VALUE = 1.0  # debt-scan: ignore-line -- alternative value


@dataclass(frozen=True, slots=True)
class FormulaMarker:
    name: str
    patterns: tuple[str, ...]
    constants: dict[str, dict[str, float]]


_FORMULA_MARKERS: tuple[FormulaMarker, ...] = (
    FormulaMarker("scherrer", ("scherrer", "шеррер", "шенер", "βcosθ"), {"K": {"canonical": _SCHERRER_CANONICAL_K_VALUE, "alternative": _SCHERRER_ALTERNATIVE_K_VALUE}}),
    FormulaMarker("williamson_hall", ("williamson-hall", "уильямсон-холл", "w-h"), {}),
    FormulaMarker("dislocation", ("дислокац", "ρ =", "rho", "плотность дислокаций"), {}),
    FormulaMarker("arrhenius", ("аррениус", "arrhenius", "exp(-ea/(rt))"), {}),
)


def detect_formula(text: str) -> str | None:
    lowered = text.lower()
    for marker in _FORMULA_MARKERS:
        for pattern in marker.patterns:
            if pattern.lower() in lowered:
                return marker.name
    return None


def check_constant(formula_name: str, text: str) -> str:
    if formula_name == "scherrer":
        if _SCHERRER_CANONICAL_K_TEXT in text:
            return "formula_consistent"
        if _SCHERRER_ALTERNATIVE_K_TEXT in text or _SCHERRER_K_EQUALS_ONE in text:
            return "formula_conflict"
        return "unknown"
    if detect_formula(text) == formula_name:
        return "formula_consistent"
    return "unknown"


def list_formulas() -> tuple[str, ...]:
    return tuple(marker.name for marker in _FORMULA_MARKERS)
