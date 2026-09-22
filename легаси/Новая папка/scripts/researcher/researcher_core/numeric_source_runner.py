"""Deterministic source JSON runner for numeric evidence.

This is the bounded adapter that wires existing pure modules together:
`numeric`, `formulas`, `qualifier`, and `uncertainty`.
It compares one claim JSON record against multiple source JSON records and
returns a legacy-shaped summary without copying the old shell runner.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Sequence

from researcher_core.formulas import check_constant, detect_formula
from researcher_core.numeric import NumericComparisonStatus, NumericValue, compare_numeric
from researcher_core.qualifier import compare_qualifiers, extract_qualifier


_STATUS_MATCH_PRIORITY = 4  # debt-scan: ignore-line -- ordered severity rank, deterministic control plane
_STATUS_PARTIAL_PRIORITY = 3  # debt-scan: ignore-line -- ordered severity rank
_STATUS_QUALIFIER_PRIORITY = 2  # debt-scan: ignore-line -- ordered severity rank
_STATUS_MISMATCH_PRIORITY = 1  # debt-scan: ignore-line -- ordered severity rank
_STATUS_NO_DATA_PRIORITY = 0  # debt-scan: ignore-line -- ordered severity rank

_STATUS_PRIORITY = {
    "match": _STATUS_MATCH_PRIORITY,
    "partial_match": _STATUS_PARTIAL_PRIORITY,
    "qualifier_mismatch": _STATUS_QUALIFIER_PRIORITY,
    "mismatch": _STATUS_MISMATCH_PRIORITY,
    "not_comparable": _STATUS_MISMATCH_PRIORITY,
    "no_data": _STATUS_NO_DATA_PRIORITY,
}


def numeric_value_from_json(data: Mapping[str, Any]) -> NumericValue | None:
    if data.get("value") is not None:
        return NumericValue(value=data["value"], unit=data.get("unit"))
    if data.get("lower") is not None and data.get("upper") is not None:
        return NumericValue(lower=data["lower"], upper=data["upper"], unit=data.get("unit"))
    range_record = data.get("range")
    if isinstance(range_record, Mapping):
        low = range_record.get("low")
        high = range_record.get("high")
        if low is not None and high is not None:
            return NumericValue(lower=low, upper=high, unit=data.get("unit") or range_record.get("unit"))
    return None


def compare_claim_sources_json(
    claim_data: Mapping[str, Any],
    sources_data: Sequence[Mapping[str, Any]],
    tolerance_relative: str | Decimal = "0.01",
) -> dict[str, Any]:
    claim_text = str(claim_data.get("claim_text", ""))
    claim_value = numeric_value_from_json(claim_data)
    claim_qualifiers = tuple(claim_data.get("qualifier") or extract_qualifier(claim_text))
    results: list[dict[str, Any]] = []
    best_status = "no_data"

    for source in sources_data:
        source_title = str(source.get("title", source.get("descriptor", source.get("id", ""))))
        source_text = str(source.get("text", source.get("descriptor", source_title)))
        source_value = numeric_value_from_json(source)
        source_qualifiers = tuple(source.get("qualifier") or extract_qualifier(source_text))
        qual_status = compare_qualifiers(claim_qualifiers, source_qualifiers)

        numeric_status = "no_data"
        numeric_reason = "no numeric value in claim or source"
        if claim_value is not None and source_value is not None:
            numeric_result = compare_numeric(claim_value, source_value, tolerance_relative=tolerance_relative)
            numeric_status = _legacy_status(numeric_result.status)
            numeric_reason = numeric_result.reason

        source_status = numeric_status
        if qual_status == "qualifier_mismatch" and source_status in {"match", "partial_match"}:
            source_status = "qualifier_mismatch"

        results.append(
            {
                "source_title": source_title,
                "numeric_status": numeric_status,
                "numeric_reason": numeric_reason,
                "qualifier_comparison": {
                    "claim": claim_qualifiers,
                    "source": source_qualifiers,
                    "status": qual_status,
                },
                "source_status": source_status,
            }
        )
        if _STATUS_PRIORITY.get(source_status, 0) > _STATUS_PRIORITY.get(best_status, 0):
            best_status = source_status

    formula_name = detect_formula(claim_text)
    formula_info = None
    if formula_name is not None:
        formula_info = {
            "name": formula_name,
            "constant_check": check_constant(formula_name, claim_text),
        }
        if formula_info["constant_check"] == "formula_conflict":
            best_status = "mismatch"

    if claim_value is None and best_status == "no_data":
        best_status = "no_numbers_in_claim"

    return {
        "claim_id": claim_data.get("claim_id"),
        "claim_text": claim_text,
        "claim_qualifiers": claim_qualifiers,
        "formula": formula_info,
        "results": tuple(results),
        "status": best_status,
        "explanation": f"Best match across {len(sources_data)} sources: {best_status}",
    }


def _legacy_status(status: NumericComparisonStatus) -> str:
    if status == NumericComparisonStatus.MATCH:
        return "match"
    if status == NumericComparisonStatus.PARTIAL_OVERLAP:
        return "partial_match"
    if status == NumericComparisonStatus.NOT_COMPARABLE:
        return "not_comparable"
    return "mismatch"
