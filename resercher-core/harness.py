"""Lightweight harness-based testing primitives.

This module gives R0 a cheap alternative to repeated agent review: deterministic
black-box traces plus small invariant checks. The SUT does not need to know about
the checker; tests feed recorded events to the harness.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from researcher_core.r0.events import _deep_freeze


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    correlation_id: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.event_type:
            raise ValueError("event_type is required")
        if not self.correlation_id:
            raise ValueError("correlation_id is required")
        object.__setattr__(self, "payload", _deep_freeze(self.payload))


@dataclass(frozen=True, slots=True)
class InvariantViolation:
    invariant: str
    correlation_id: str
    message: str


class TraceAuditor:
    """Passive sidecar-style observer over an immutable event trace."""

    def __init__(self, events: Iterable[AuditEvent] = ()) -> None:
        self._events = tuple(events)

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return self._events

    def record(self, event_type: str, correlation_id: str, payload: Mapping[str, Any] | None = None) -> "TraceAuditor":
        event = AuditEvent(event_type=event_type, correlation_id=correlation_id, payload=payload or {})
        return TraceAuditor((*self._events, event))

    def require_input_output_pairs(
        self,
        input_event: str = "input",
        output_event: str = "output",
    ) -> list[InvariantViolation]:
        outputs = {event.correlation_id for event in self._events if event.event_type == output_event}
        violations: list[InvariantViolation] = []
        for event in self._events:
            if event.event_type == input_event and event.correlation_id not in outputs:
                violations.append(
                    InvariantViolation(
                        invariant="input_output_pair",
                        correlation_id=event.correlation_id,
                        message="input event has no matching output event",
                    )
                )
        return violations


def compare_trace_event_types(audit_events: Sequence[AuditEvent], reference_event_types: Sequence[str]) -> set[str]:
    """Return reference event types missing from the audit trace."""

    observed = {event.event_type for event in audit_events}
    return set(reference_event_types) - observed
