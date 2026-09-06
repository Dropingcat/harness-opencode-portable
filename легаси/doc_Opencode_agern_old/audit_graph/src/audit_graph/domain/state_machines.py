from __future__ import annotations

from typing import Mapping, FrozenSet

from .enums import ClaimStatus
from .value_objects import Reason


ALLOWED_CLAIM_TRANSITIONS: Mapping[ClaimStatus, FrozenSet[ClaimStatus]] = {
    ClaimStatus.DRAFT: frozenset({ClaimStatus.REGISTERED}),
    ClaimStatus.REGISTERED: frozenset({ClaimStatus.IN_REVIEW, ClaimStatus.SUPERSEDED}),
    ClaimStatus.IN_REVIEW: frozenset({ClaimStatus.ACCEPTED, ClaimStatus.REJECTED, ClaimStatus.SUPERSEDED}),
    ClaimStatus.ACCEPTED: frozenset({ClaimStatus.SUPERSEDED}),
    ClaimStatus.REJECTED: frozenset({ClaimStatus.SUPERSEDED}),
    ClaimStatus.SUPERSEDED: frozenset(),
}


def can_transition(from_status: ClaimStatus, to_status: ClaimStatus) -> bool:
    return to_status in ALLOWED_CLAIM_TRANSITIONS.get(from_status, frozenset())


def require_transition(from_status: ClaimStatus, to_status: ClaimStatus, reason: Reason) -> None:
    if not can_transition(from_status, to_status):
        raise ValueError(
            f"invalid claim transition: {from_status} -> {to_status} for reason {reason.code}"
        )
