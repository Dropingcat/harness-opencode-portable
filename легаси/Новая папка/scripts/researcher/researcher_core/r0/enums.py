"""Closed vocabularies for R0 research contracts."""

from __future__ import annotations

from enum import Enum


class _StrictStrEnum(str, Enum):
    """String enum base that renders as its wire value."""

    def __str__(self) -> str:
        return self.value


class ClaimKind(_StrictStrEnum):
    OBSERVATIONAL = "observational"
    EXPERIMENTAL_RESULT = "experimental_result"
    QUANTITATIVE = "quantitative"
    CAUSAL = "causal"
    MECHANISTIC = "mechanistic"
    DEFINITIONAL = "definitional"
    TAXONOMIC = "taxonomic"
    COMPUTATIONAL = "computational"
    METHODOLOGICAL = "methodological"
    HISTORICAL_EVENT = "historical_event"
    ATTRIBUTION = "attribution"
    INTERPRETIVE = "interpretive"
    ARGUMENTATIVE = "argumentative"
    NORMATIVE = "normative"
    DIAGNOSTIC_OR_CLINICAL = "diagnostic_or_clinical"
    RECOMMENDATION = "recommendation"


class EdgeKind(_StrictStrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    HAS_GAP = "has_gap"
    IN_CONFLICT = "in_conflict"
    QUANTIFIES = "quantifies"


class ClaimStatus(_StrictStrEnum):
    OPEN = "open"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONTRADICTED = "contradicted"
    REJECTED = "rejected"
    STALE = "stale"
    SUPERSEDED = "superseded"


class Verifiability(_StrictStrEnum):
    VERIFIABLE = "verifiable"
    UNVERIFIABLE_AS_STATED = "unverifiable_as_stated"
    UNDERDEFINED = "underdefined"
    NOT_CHECKWORTHY = "not_checkworthy"


class AdmissionStatus(_StrictStrEnum):
    CANDIDATE = "candidate"
    PROPOSED = "proposed"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"
    QUARANTINED = "quarantined"


class EvidenceState(_StrictStrEnum):
    UNASSESSED = "unassessed"
    INSUFFICIENT = "insufficient"
    SUPPORTED_IN_REPORT = "supported_in_report"
    SUPPORTED_EXTERNAL = "supported_external"
    PARTIALLY_SUPPORTED = "partially_supported"
    MIXED = "mixed"
    CONTRADICTED = "contradicted"


class DerivationState(_StrictStrEnum):
    NOT_DERIVED = "not_derived"
    DERIVED_REPRODUCIBLE = "derived_reproducible"
    DERIVED_NOT_REPRODUCIBLE = "derived_not_reproducible"
    DERIVED_WITH_UNJUSTIFIED_ASSUMPTION = "derived_with_unjustified_assumption"


class ExtrapolationState(_StrictStrEnum):
    NO_EXTRAPOLATION = "no_extrapolation"
    EXPLICIT_EXTRAPOLATION = "explicit_extrapolation"
    HIDDEN_EXTRAPOLATION = "hidden_extrapolation"
    BLOCKING_EXTRAPOLATION = "blocking_extrapolation"


class ConflictState(_StrictStrEnum):
    NO_DIRECT_CONFLICT = "no_direct_conflict"
    CONFLICT_MEMBER = "conflict_member"
    CONFLICT_BLOCKED = "conflict_blocked"
    CONFLICT_UNRESOLVED = "conflict_unresolved"


class GapState(_StrictStrEnum):
    NO_OPEN_GAPS = "no_open_gaps"
    OPEN_NONBLOCKING_GAPS = "open_nonblocking_gaps"
    OPEN_BLOCKING_GAPS = "open_blocking_gaps"


class WriterEligibility(_StrictStrEnum):
    ALLOWED = "allowed"
    QUALIFIED = "qualified"
    FORBIDDEN_AS_FACT = "forbidden_as_fact"
    FORBIDDEN_AS_RECOMMENDATION = "forbidden_as_recommendation"


class ReviewState(_StrictStrEnum):
    AUTOMATED_ONLY = "automated_only"
    HUMAN_REVIEWED = "human_reviewed"
    EXPERT_REVIEWED = "expert_reviewed"


class ValidationResult(_StrictStrEnum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    UNKNOWN = "unknown"


ValidationOutcome = ValidationResult


class CommitPolicy(_StrictStrEnum):
    ALL_OR_NOTHING = "all_or_nothing"
    DEPENDENCY_CLOSED_PARTIAL = "dependency_closed_partial"
