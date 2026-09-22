"""Parsers and comparators for numeric values with uncertainty."""

import re

_PM_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*[±+-]\s*(\d+\.?\d*)"
)
_RANGE_PATTERN = re.compile(
    r"\[\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*\+\s*(\d+\.?\d*)\s*\]"
)


def parse_uncertainty(text: str) -> tuple[float, float] | None:
    m = _RANGE_PATTERN.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = _PM_PATTERN.search(text)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def values_overlap(a_val, a_unc, b_val, b_unc) -> bool:
    a_lo, a_hi = a_val - a_unc, a_val + a_unc
    b_lo, b_hi = b_val - b_unc, b_val + b_unc
    return a_lo <= b_hi and b_lo <= a_hi


values_in_range = values_overlap


def compare_with_uncertainty(claim_val, claim_unc, source_val, source_unc) -> str:
    if claim_unc is None or source_unc is None:
        return "NO_DATA"
    if values_overlap(claim_val, claim_unc, source_val, source_unc):
        return "MATCH"
    if abs(claim_val - source_val) <= max(claim_unc, source_unc):
        return "PARTIAL_MATCH"
    return "MISMATCH"
