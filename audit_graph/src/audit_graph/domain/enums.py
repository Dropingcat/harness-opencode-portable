from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ClaimStatus(StrEnum):
    DRAFT = "draft"
    REGISTERED = "registered"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ReasonCode(StrEnum):
    TASK_CREATED = "task_created"
    CLAIM_REGISTERED = "claim_registered"
    EVIDENCE_ATTACHED = "evidence_attached"
    REVIEW_REQUESTED = "review_requested"
    DETERMINISTIC_CHECK_PASSED = "deterministic_check_passed"
    DETERMINISTIC_CHECK_FAILED = "deterministic_check_failed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONTRADICTION_FOUND = "contradiction_found"
    CLAIM_ACCEPTED = "claim_accepted"
    CLAIM_REJECTED = "claim_rejected"
    CLAIM_SUPERSEDED = "claim_superseded"
    STATE_TRANSITION = "state_transition"


class EvidenceKind(StrEnum):
    TEXT = "text"
    CODE = "code"
    FILE = "file"
    COMMAND_OUTPUT = "command_output"
    STRUCTURED = "structured"


class EventType(StrEnum):
    CLAIM_REGISTERED = "claim_registered"
    EVIDENCE_ATTACHED = "evidence_attached"
    CLAIM_STATUS_CHANGED = "claim_status_changed"
