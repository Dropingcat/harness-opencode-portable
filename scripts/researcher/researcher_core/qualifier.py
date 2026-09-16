"""Deterministic qualifier extraction and comparison — port of numeric_comparator qualifier.

Pure, dependency-free, Russian/English keywords as in legacy.
"""

from __future__ import annotations

_QUALIFIERS_MAP: tuple[tuple[str, str], ...] = (
    ("для всех", "universal"),
    ("для легированных", "alloyed_only"),
    ("для углеродистых", "carbon_only"),
    ("стандартный режим", "standard_mode"),
    ("стандартном режиме", "standard_mode"),
    ("при стандартном", "standard_mode"),
    ("до ", "up_to"),
    ("не более", "max"),
    ("не менее", "min"),
    ("типично", "typical"),
    ("обычно", "typical"),
    ("в зависимости", "conditional"),
)


def extract_qualifier(text: str) -> tuple[str, ...]:
    qualifiers: list[str] = []
    text_lower = text.lower()
    for keyword, qtype in _QUALIFIERS_MAP:
        if keyword in text_lower:
            qualifiers.append(qtype)
    return tuple(qualifiers) if qualifiers else ("unspecified",)


def compare_qualifiers(claim_quals: tuple[str, ...] | list[str], source_quals: tuple[str, ...] | list[str]) -> str:
    claim_set = set(claim_quals)
    source_set = set(source_quals)
    if "universal" in claim_set and "universal" not in source_set:
        return "qualifier_mismatch"
    if "standard_mode" in claim_set and "standard_mode" not in source_set:
        return "qualifier_mismatch"
    if "up_to" in source_set and "universal" in claim_set:
        return "qualifier_mismatch"
    return "match"
