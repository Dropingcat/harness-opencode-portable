from __future__ import annotations

from typing import NewType


TaskId = NewType("TaskId", str)
ClaimId = NewType("ClaimId", str)
EvidenceId = NewType("EvidenceId", str)
EventId = NewType("EventId", str)
ActorId = NewType("ActorId", str)
TransitionId = NewType("TransitionId", str)


def require_id(value: str, *, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    return value
