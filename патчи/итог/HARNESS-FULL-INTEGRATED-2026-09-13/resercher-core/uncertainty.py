"""Deterministic uncertainty parsing and overlap — port of legacy uncertainty.py.

Dependency-free, Decimal-based for R0-S016. Keeps legacy regex semantics but
returns Decimal for numeric core.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_PM_PATTERN = re.compile(r"(\d+\.?\d*)\s*[±+-]\s*(\d+\.?\d*)")
_RANGE_PATTERN = re.compile(r"\[\s*(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*,\s*(\d+\.?\d*)\s*\+\s*(\d+\.?\d*)\s*\]")


def parse_uncertainty(text: str) -> tuple[Decimal, Decimal] | None:
    match = _RANGE_PATTERN.search(text)
    if match:
        try:
            return Decimal(match.group(1)), Decimal(match.group(2))  # debt-scan: ignore-line -- regex group index, not heuristic
        except InvalidOperation:
            return None
    match = _PM_PATTERN.search(text)
    if match:
        try:
            return Decimal(match.group(1)), Decimal(match.group(2))  # debt-scan: ignore-line -- regex group index, not heuristic
        except InvalidOperation:
            return None
    return None


def values_overlap(a_val: Decimal, a_unc: Decimal, b_val: Decimal, b_unc: Decimal) -> bool:
    a_lo = a_val - a_unc
    a_hi = a_val + a_unc
    b_lo = b_val - b_unc
    b_hi = b_val + b_unc
    return a_lo <= b_hi and b_lo <= a_hi


values_in_range = values_overlap


def compare_with_uncertainty(
    claim_val: Decimal, claim_unc: Decimal | None, source_val: Decimal, source_unc: Decimal | None
) -> str:
    if claim_unc is None or source_unc is None:
        return "NO_DATA"
    if values_overlap(claim_val, claim_unc, source_val, source_unc):
        return "MATCH"
    diff = abs(claim_val - source_val)
    largest = claim_unc if claim_unc > source_unc else source_unc
    if diff <= largest:
        return "PARTIAL_MATCH"
    return "MISMATCH"
