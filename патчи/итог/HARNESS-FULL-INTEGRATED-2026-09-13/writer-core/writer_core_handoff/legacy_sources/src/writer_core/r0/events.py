"""Events and serialization helpers for writer-core R0."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Mapping

from writer_core.r0.ids import EntityId


def _deep_freeze(value: Any) -> Any:
    """Recursively freeze mappings and sequences for immutability."""
    if isinstance(value, Mapping):
        return MappingProxyType({k: _deep_freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(v) for v in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


@dataclass(frozen=True, slots=True)
class ReasonCode:
    code: str
    description: str

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("reason code is required")


class ReasonCodeRegistry:
    """Central registry of reason codes (immutable after init)."""

    def __init__(self) -> None:
        self._codes: dict[str, ReasonCode] = {}

    def register(self, code: str, description: str) -> None:
        if code in self._codes:
            raise ValueError(f"duplicate reason code: {code}")
        self._codes[code] = ReasonCode(code=code, description=description)

    def get(self, code: str) -> ReasonCode | None:
        return self._codes.get(code)

    def all(self) -> Mapping[str, ReasonCode]:
        from types import MappingProxyType
        return MappingProxyType(self._codes)


# Pre-populated writer-core reason codes
WRITER_REASON_CODES = ReasonCodeRegistry()
for code, desc in [
    ("writer:empty_text", "unit text is empty"),
    ("writer:no_provenance", "assertion lacks provenance"),
    ("writer:forbidden_claim", "unit contains forbidden claim"),
    ("writer:citation_missing", "citation required but missing"),
    ("writer:citation_bad_gost", "citation does not match ГОСТ Р 7.0.5"),
    ("writer:object_bad_number", "object NUMBER: value/unit/dimension invalid"),
    ("writer:object_bad_formula", "object FORMULA: LaTeX/variables invalid"),
    ("writer:object_bad_citation", "object CITATION: ГОСТ Р 7.0.5 mismatch"),
    ("writer:atomicity", "unit contains multiple assertions"),
    ("writer:style_kantselyarit", "канцелярит/пассив/читаемость"),
    ("writer:consistency_conflict", "unit contradicts another unit"),
    ("writer:forbidden_claim_in_unit", "unit contains forbidden claim"),
    ("writer:object_bad_formula_syntax", "formula LaTeX syntax error"),
    ("writer:object_bad_citation_gost", "citation ГОСТ Р 7.0.5 mismatch"),
] * 1:
    WRITER_REASON_CODES.register(code, desc)


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: EntityId
    event_type: str
    aggregate_id: EntityId
    aggregate_revision: int
    run_id: EntityId
    actor: str
    timestamp: datetime
    causation_id: EntityId
    correlation_id: EntityId
    schema_version: str
    reason_codes: tuple[str, ...]
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(UTC))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "payload", _deep_freeze(self.payload))