"""Event envelope contracts for R0 state transitions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Mapping

from researcher_core.r0.ids import EntityId


_REASON_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*(?:\.[A-Z][A-Z0-9_]*)*$")
_REASON_REQUIRED_MARKERS = ("VALIDATION", "STATUS_CHANGED", "STATE_CHANGED")
EVENT_TYPES = frozenset(
    {
        "RUN_CREATED",
        "QUESTION_CREATED",
        "PROPOSAL_RECEIVED",
        "CLAIM_ADMITTED",
        "CLAIM_REJECTED",
        "SOURCE_ADMITTED",
        "EVIDENCE_ADMITTED",
        "EDGE_ADMITTED",
        "EDGE_STATE_CHANGED",
        "VALIDATION_RECORDED",
        "CLAIM_STATE_CHANGED",
        "CLAIM_STATUS_CHANGED",
        "SNAPSHOT_CREATED",
        "REJECTION_RECORDED",
        "RESEARCH_CARD_ADDED",
        "RESEARCH_CARD_STATE_CHANGED",
        "RESEARCH_PATCH_APPLIED",
    }
)


@dataclass(frozen=True, slots=True)
class ReasonCode:
    """Machine-readable reason, for example ``DEPENDS_ON_UNSUPPORTED_ASSUMPTION``."""

    value: str

    def __post_init__(self) -> None:
        if not _REASON_CODE_RE.match(self.value):
            raise ValueError(f"invalid reason code: {self.value!r}")

    @property
    def namespace(self) -> str:
        return self.value.split(".", maxsplit=1)[0]

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ReasonCodeRegistry:
    """Config-backed allowlist for stable reason codes."""

    known_codes: frozenset[str]

    def validate(self, reason_code: ReasonCode) -> None:
        if reason_code.value not in self.known_codes:
            raise ValueError(f"unknown reason code: {reason_code.value!r}")

    def validate_all(self, reason_codes: tuple[ReasonCode, ...]) -> None:
        for reason_code in reason_codes:
            self.validate(reason_code)


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Audit event wrapper used by validation and state-change records."""

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
    reason_codes: tuple[ReasonCode, ...]
    payload: Mapping[str, Any] = field(default_factory=dict)
    reason_registry: ReasonCodeRegistry | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.event_type not in EVENT_TYPES:
            raise ValueError("event_type is required")
        if not self.actor:
            raise ValueError("actor is required")
        if self.aggregate_revision < 1:
            raise ValueError("aggregate_revision must be positive")
        if not isinstance(self.causation_id, EntityId):
            raise TypeError("causation_id is required")
        if not self.schema_version:
            raise ValueError("schema_version is required")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

        normalized_reasons = tuple(self.reason_codes)
        if any(not isinstance(reason, ReasonCode) for reason in normalized_reasons):
            raise TypeError("reason_codes must contain ReasonCode values")
        if self._requires_reason_code() and not normalized_reasons:
            raise ValueError("reason_codes are required for validation/state-change events")
        if self.reason_registry is not None:
            self.reason_registry.validate_all(normalized_reasons)

        object.__setattr__(self, "reason_codes", normalized_reasons)
        object.__setattr__(self, "payload", _deep_freeze(self.payload))
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(UTC))

    def _requires_reason_code(self) -> bool:
        event_type = self.event_type.upper()
        return any(marker in event_type for marker in _REASON_REQUIRED_MARKERS)


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _deep_freeze(nested) for key, nested in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_deep_freeze(nested) for nested in value)
    return value
