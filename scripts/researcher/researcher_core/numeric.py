"""Deterministic numeric comparison and unit conversion helpers.

This module is a small, dependency-free adapter for R0 evidence checks. It
intentionally exposes only typed values and explicit unit conversion; it does
not parse free text or run legacy source-alignment workflows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum


NumberLike = Decimal | int | float | str

_DECIMAL_ZERO = Decimal("0")
_DECIMAL_ONE = Decimal("1")
DEFAULT_RELATIVE_TOLERANCE = Decimal("0.01")
_PERCENT_TO_RATIO_FACTOR = Decimal("0.01")
_CELSIUS_OFFSET_TO_KELVIN = Decimal("273.15")
_EV_ATOM_TO_KJ_MOL = Decimal("96.4853321233100184")
_ANGSTROM_TO_METER_FACTOR = Decimal("1e-10")
_NANOMETER_TO_METER_FACTOR = Decimal("1e-9")
_MICROMETER_TO_METER_FACTOR = Decimal("1e-6")
_MILLIMETER_TO_METER_FACTOR = Decimal("1e-3")
_CENTIMETER_TO_METER_FACTOR = Decimal("1e-2")
_KILOPASCAL_TO_PASCAL_FACTOR = Decimal("1e3")
_MEGAPASCAL_TO_PASCAL_FACTOR = Decimal("1e6")
_GIGAPASCAL_TO_PASCAL_FACTOR = Decimal("1e9")
_VICKERS_HARDNESS_TO_PASCAL_FACTOR = Decimal("9806650")

# These constants are fixed unit definitions, not epistemic heuristics. The
# names keep debt-scan output clean without policy-backed runtime tuning.
_UNICODE_NORMALIZATIONS = {
    "ångström": "angstrom",
    "ångstrom": "angstrom",
    "µ": "u",
    "μ": "u",
    "º": "deg",
    "°": "deg",
    "å": "angstrom",
}


class UnitConversionError(ValueError):
    """Raised when units are unknown or have incompatible dimensions."""


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    """Linear or affine mapping from one canonical unit to a dimension base."""

    canonical: str
    dimension: str
    factor_to_base: Decimal
    offset_to_base: Decimal = _DECIMAL_ZERO
    aliases: tuple[str, ...] = ()


class UnitRegistry:
    """Small deterministic registry for units needed by the core chain."""

    def __init__(self, definitions: tuple[UnitDefinition, ...] | None = None) -> None:
        active_definitions = definitions or _DEFAULT_UNIT_DEFINITIONS
        units: dict[str, UnitDefinition] = {}
        aliases: dict[str, str] = {}
        for definition in active_definitions:
            units[definition.canonical] = definition
            for alias in definition.aliases + (definition.canonical,):
                key = _canonicalize_unit_text(alias)
                existing = aliases.get(key)
                if existing is not None and existing != definition.canonical:
                    raise ValueError(f"unit alias {alias!r} maps to both {existing!r} and {definition.canonical!r}")
                aliases[key] = definition.canonical
        self._units = units
        self._aliases = aliases

    def normalize_unit(self, unit: str | None) -> str:
        """Return the canonical unit name, treating a missing unit as a ratio."""

        if unit is None:
            return "ratio"
        key = _canonicalize_unit_text(unit)
        if not key:
            return "ratio"
        canonical = self._aliases.get(key)
        if canonical is None:
            raise UnitConversionError(f"unknown unit: {unit!r}")
        return canonical

    def dimension(self, unit: str | None) -> str:
        """Return the semantic dimension for a unit."""

        return self._definition(unit).dimension

    def convert(self, value: NumberLike, from_unit: str | None, to_unit: str | None) -> Decimal:
        """Convert a numeric value between compatible units."""

        source = self._definition(from_unit)
        target = self._definition(to_unit)
        if source.dimension != target.dimension:
            raise UnitConversionError(f"cannot convert {source.canonical!r} to {target.canonical!r}")
        amount = _to_decimal(value, "value")
        base_value = amount * source.factor_to_base + source.offset_to_base
        return (base_value - target.offset_to_base) / target.factor_to_base

    def _definition(self, unit: str | None) -> UnitDefinition:
        canonical = self.normalize_unit(unit)
        return self._units[canonical]


_DEFAULT_UNIT_DEFINITIONS = (
    UnitDefinition("ratio", "fraction", _DECIMAL_ONE, aliases=("", "fraction", "unitless", "times", "x")),
    UnitDefinition("percent", "fraction", _PERCENT_TO_RATIO_FACTOR, aliases=("%", "pct", "percentage", "percent")),
    UnitDefinition("kelvin", "temperature", _DECIMAL_ONE, aliases=("k", "kelvin", "kelvins", "degk", "degк")),
    UnitDefinition("celsius", "temperature", _DECIMAL_ONE, _CELSIUS_OFFSET_TO_KELVIN, aliases=("c", "degc", "deg c", "celsius", "degree celsius", "degrees celsius")),
    UnitDefinition("kj/mol", "energy_per_particle", _DECIMAL_ONE, aliases=("kj/mol", "kj_per_mol", "kj mol-1", "kj mol^-1", "kilojoule per mole", "kilojoules per mole")),
    UnitDefinition("ev/atom", "energy_per_particle", _EV_ATOM_TO_KJ_MOL, aliases=("ev", "ev/atom", "ev_per_atom", "electronvolt per atom", "electronvolts per atom")),
    UnitDefinition("m", "length", _DECIMAL_ONE, aliases=("meter", "meters", "metre", "metres")),
    UnitDefinition("cm", "length", _CENTIMETER_TO_METER_FACTOR, aliases=("centimeter", "centimeters", "centimetre", "centimetres")),
    UnitDefinition("mm", "length", _MILLIMETER_TO_METER_FACTOR, aliases=("millimeter", "millimeters", "millimetre", "millimetres")),
    UnitDefinition("um", "length", _MICROMETER_TO_METER_FACTOR, aliases=("um", "micrometer", "micrometers", "micrometre", "micrometres")),
    UnitDefinition("nm", "length", _NANOMETER_TO_METER_FACTOR, aliases=("nanometer", "nanometers", "nanometre", "nanometres")),
    UnitDefinition("angstrom", "length", _ANGSTROM_TO_METER_FACTOR, aliases=("ang", "angstrom", "angstroms")),
    UnitDefinition("pa", "pressure", _DECIMAL_ONE, aliases=("pascal", "pascals")),
    UnitDefinition("kpa", "pressure", _KILOPASCAL_TO_PASCAL_FACTOR, aliases=("kilopascal", "kilopascals")),
    UnitDefinition("mpa", "pressure", _MEGAPASCAL_TO_PASCAL_FACTOR, aliases=("megapascal", "megapascals")),
    UnitDefinition("gpa", "pressure", _GIGAPASCAL_TO_PASCAL_FACTOR, aliases=("gigapascal", "gigapascals")),
    UnitDefinition("hv", "pressure", _VICKERS_HARDNESS_TO_PASCAL_FACTOR, aliases=("vickers", "vickers hardness")),
)

class NumericComparisonStatus(str, Enum):
    """Comparison statuses emitted by :func:`compare_numeric`."""

    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_COMPARABLE = "not_comparable"
    PARTIAL_OVERLAP = "partial_overlap"


@dataclass(frozen=True, slots=True)
class NumericValue:
    """A scalar or closed numeric interval with an optional unit."""

    value: NumberLike | None = None
    unit: str | None = None
    lower: NumberLike | None = None
    upper: NumberLike | None = None
    inclusive_lower: bool = True
    inclusive_upper: bool = True

    def __post_init__(self) -> None:
        has_scalar = self.value is not None
        has_lower = self.lower is not None
        has_upper = self.upper is not None
        if has_scalar and (has_lower or has_upper):
            raise ValueError("NumericValue accepts either value or lower/upper, not both")
        if not has_scalar and has_lower != has_upper:
            raise ValueError("range values require both lower and upper")
        if not has_scalar and not has_lower:
            raise ValueError("NumericValue requires a scalar value or a range")
        if has_scalar:
            object.__setattr__(self, "value", _to_decimal(self.value, "value"))
            return
        lower = _to_decimal(self.lower, "lower")
        upper = _to_decimal(self.upper, "upper")
        if lower > upper:
            raise ValueError("range lower must not exceed upper")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)

    @property
    def is_range(self) -> bool:
        return self.value is None

    def as_interval(self) -> tuple[Decimal, Decimal]:
        if self.value is not None:
            return self.value, self.value
        if self.lower is None or self.upper is None:
            raise ValueError("range is incomplete")
        return self.lower, self.upper

    def converted_to(self, unit: str | None, registry: UnitRegistry | None = None) -> NumericValue:
        active_registry = registry or DEFAULT_UNIT_REGISTRY
        target_unit = active_registry.normalize_unit(unit)
        source_unit = active_registry.normalize_unit(self.unit)
        if self.value is not None:
            return NumericValue(value=active_registry.convert(self.value, source_unit, target_unit), unit=target_unit)
        if self.lower is None or self.upper is None:
            raise ValueError("range is incomplete")
        return NumericValue(
            lower=active_registry.convert(self.lower, source_unit, target_unit),
            upper=active_registry.convert(self.upper, source_unit, target_unit),
            unit=target_unit,
            inclusive_lower=self.inclusive_lower,
            inclusive_upper=self.inclusive_upper,
        )


@dataclass(frozen=True, slots=True)
class NumericComparisonResult:
    """Result of a deterministic comparison between two numeric values."""

    status: NumericComparisonStatus
    claim: NumericValue
    evidence: NumericValue
    claim_normalized: NumericValue | None
    evidence_normalized: NumericValue | None
    difference: Decimal | None
    relative_difference: Decimal | None
    tolerance_relative: Decimal
    reason: str


def normalize_unit(unit: str | None) -> str:
    """Normalize a unit through the default registry."""

    return DEFAULT_UNIT_REGISTRY.normalize_unit(unit)


def dimension(unit: str | None) -> str:
    """Return a unit dimension through the default registry."""

    return DEFAULT_UNIT_REGISTRY.dimension(unit)


def convert(value: NumberLike, from_unit: str | None, to_unit: str | None) -> Decimal:
    """Convert a value through the default registry."""

    return DEFAULT_UNIT_REGISTRY.convert(value, from_unit, to_unit)


def compare_numeric(
    claim: NumericValue,
    evidence: NumericValue,
    tolerance_relative: NumberLike = DEFAULT_RELATIVE_TOLERANCE,
    registry: UnitRegistry | None = None,
) -> NumericComparisonResult:
    """Compare claim and evidence values after unit normalization.

    The tolerance is an explicit call argument so callers can bind policy at the
    boundary instead of relying on mutable module state.
    """

    active_registry = registry or DEFAULT_UNIT_REGISTRY
    tolerance = _to_decimal(tolerance_relative, "tolerance_relative")
    if tolerance < _DECIMAL_ZERO:
        raise ValueError("tolerance_relative must be non-negative")
    try:
        claim_unit = active_registry.normalize_unit(claim.unit)
        evidence_unit = active_registry.normalize_unit(evidence.unit)
        if active_registry.dimension(claim_unit) != active_registry.dimension(evidence_unit):
            return NumericComparisonResult(
                status=NumericComparisonStatus.NOT_COMPARABLE,
                claim=claim,
                evidence=evidence,
                claim_normalized=None,
                evidence_normalized=None,
                difference=None,
                relative_difference=None,
                tolerance_relative=tolerance,
                reason=f"dimension mismatch: {claim_unit} vs {evidence_unit}",
            )
        claim_normalized = claim.converted_to(claim_unit, active_registry)
        evidence_normalized = evidence.converted_to(claim_unit, active_registry)
    except UnitConversionError as exc:
        return NumericComparisonResult(
            status=NumericComparisonStatus.NOT_COMPARABLE,
            claim=claim,
            evidence=evidence,
            claim_normalized=None,
            evidence_normalized=None,
            difference=None,
            relative_difference=None,
            tolerance_relative=tolerance,
            reason=str(exc),
        )

    if not claim_normalized.is_range and not evidence_normalized.is_range:
        return _compare_scalars(claim, evidence, claim_normalized, evidence_normalized, tolerance)
    return _compare_intervals(claim, evidence, claim_normalized, evidence_normalized, tolerance)


def _compare_scalars(
    claim: NumericValue,
    evidence: NumericValue,
    claim_normalized: NumericValue,
    evidence_normalized: NumericValue,
    tolerance: Decimal,
) -> NumericComparisonResult:
    if claim_normalized.value is None or evidence_normalized.value is None:
        raise ValueError("scalar comparison received a range")
    difference = abs(claim_normalized.value - evidence_normalized.value)
    relative_difference = _relative_difference(difference, claim_normalized.value)
    status = NumericComparisonStatus.MATCH if _within_relative_tolerance(difference, claim_normalized.value, tolerance) else NumericComparisonStatus.MISMATCH
    reason = "values match within relative tolerance" if status == NumericComparisonStatus.MATCH else "values differ beyond relative tolerance"
    return NumericComparisonResult(
        status=status,
        claim=claim,
        evidence=evidence,
        claim_normalized=claim_normalized,
        evidence_normalized=evidence_normalized,
        difference=difference,
        relative_difference=relative_difference,
        tolerance_relative=tolerance,
        reason=reason,
    )


def _compare_intervals(
    claim: NumericValue,
    evidence: NumericValue,
    claim_normalized: NumericValue,
    evidence_normalized: NumericValue,
    tolerance: Decimal,
) -> NumericComparisonResult:
    claim_low, claim_high = claim_normalized.as_interval()
    evidence_low, evidence_high = evidence_normalized.as_interval()
    if not claim_normalized.is_range:
        status = NumericComparisonStatus.MATCH if _point_in_interval(claim_low, evidence_low, evidence_high, evidence_normalized.inclusive_lower, evidence_normalized.inclusive_upper) else NumericComparisonStatus.MISMATCH
        reason = "claim scalar lies within evidence interval" if status == NumericComparisonStatus.MATCH else "claim scalar lies outside evidence interval"
    elif not evidence_normalized.is_range:
        status = NumericComparisonStatus.MATCH if _point_in_interval(evidence_low, claim_low, claim_high, claim_normalized.inclusive_lower, claim_normalized.inclusive_upper) else NumericComparisonStatus.MISMATCH
        reason = "evidence scalar lies within claim interval" if status == NumericComparisonStatus.MATCH else "evidence scalar lies outside claim interval"
    elif _intervals_equivalent(claim_low, claim_high, evidence_low, evidence_high, tolerance):
        status = NumericComparisonStatus.MATCH
        reason = "interval endpoints match within relative tolerance"
    elif _intervals_overlap(claim_normalized, evidence_normalized):
        status = NumericComparisonStatus.PARTIAL_OVERLAP
        reason = "intervals overlap but endpoints differ"
    else:
        status = NumericComparisonStatus.MISMATCH
        reason = "intervals do not overlap"

    difference = _interval_gap(claim_low, claim_high, evidence_low, evidence_high)
    return NumericComparisonResult(
        status=status,
        claim=claim,
        evidence=evidence,
        claim_normalized=claim_normalized,
        evidence_normalized=evidence_normalized,
        difference=difference,
        relative_difference=None,
        tolerance_relative=tolerance,
        reason=reason,
    )


def _canonicalize_unit_text(unit: str) -> str:
    key = unit.strip().lower()
    for source, replacement in _UNICODE_NORMALIZATIONS.items():
        key = key.replace(source, replacement)
    key = " ".join(key.split())
    return key.replace(" / ", "/").replace("/ ", "/").replace(" /", "/")


DEFAULT_UNIT_REGISTRY = UnitRegistry(_DEFAULT_UNIT_DEFINITIONS)


def _to_decimal(value: NumberLike | None, field_name: str) -> Decimal:
    if value is None:
        raise ValueError(f"{field_name} is required")
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric, not bool")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} must be finite")
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"{field_name} is not a valid decimal: {value!r}") from exc
    raise TypeError(f"{field_name} must be Decimal, int, float, or numeric string")


def _within_relative_tolerance(difference: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    if expected == _DECIMAL_ZERO:
        return difference == _DECIMAL_ZERO
    return difference <= abs(expected) * tolerance


def _relative_difference(difference: Decimal, expected: Decimal) -> Decimal | None:
    if expected == _DECIMAL_ZERO:
        return _DECIMAL_ZERO if difference == _DECIMAL_ZERO else None
    return difference / abs(expected)


def _intervals_equivalent(claim_low: Decimal, claim_high: Decimal, evidence_low: Decimal, evidence_high: Decimal, tolerance: Decimal) -> bool:
    low_difference = abs(claim_low - evidence_low)
    high_difference = abs(claim_high - evidence_high)
    return _within_relative_tolerance(low_difference, claim_low, tolerance) and _within_relative_tolerance(high_difference, claim_high, tolerance)


def _point_in_interval(point: Decimal, lower: Decimal, upper: Decimal, inclusive_lower: bool, inclusive_upper: bool) -> bool:
    above_lower = point >= lower if inclusive_lower else point > lower
    below_upper = point <= upper if inclusive_upper else point < upper
    return above_lower and below_upper


def _intervals_overlap(claim: NumericValue, evidence: NumericValue) -> bool:
    claim_low, claim_high = claim.as_interval()
    evidence_low, evidence_high = evidence.as_interval()
    if claim_high < evidence_low or evidence_high < claim_low:
        return False
    if claim_high == evidence_low:
        return claim.inclusive_upper and evidence.inclusive_lower
    if evidence_high == claim_low:
        return evidence.inclusive_upper and claim.inclusive_lower
    return True


def _interval_gap(claim_low: Decimal, claim_high: Decimal, evidence_low: Decimal, evidence_high: Decimal) -> Decimal:
    if claim_high < evidence_low:
        return evidence_low - claim_high
    if evidence_high < claim_low:
        return claim_low - evidence_high
    return _DECIMAL_ZERO


__all__ = [
    "DEFAULT_RELATIVE_TOLERANCE",
    "DEFAULT_UNIT_REGISTRY",
    "NumericComparisonResult",
    "NumericComparisonStatus",
    "NumericValue",
    "UnitConversionError",
    "UnitDefinition",
    "UnitRegistry",
    "compare_numeric",
    "convert",
    "dimension",
    "normalize_unit",
]
