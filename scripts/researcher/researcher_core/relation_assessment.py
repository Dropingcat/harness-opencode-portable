"""R3.3 deterministic assessment of canonical semantic relations.

GraphEdge states describe relation lifecycle. RelationAssessment describes whether
an ACTIVE relation is currently eligible for reasoning. Claim truth remains a
separate downstream concern.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import EdgeKind, ValidationResult
from researcher_core.r0.events import _deep_freeze, ReasonCode
from researcher_core.r0.graph import GraphEdge, GraphEdgeState
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r0.sqlite_store import SqliteUnitOfWork
from researcher_core.r3_validators import EdgeValidator, ScopeValidator
from researcher_core.relation_lifecycle import (
    RelationTransitionRequest,
    RelationTransitionResult,
    transition_relation_state,
)
from researcher_core.research_planning_runtime import ResearchTraceLink, ResearchTraceRelation


class RelationAssessmentError(ValueError):
    pass


class RelationAssessmentVerdict(StrEnum):
    ACCEPTED = "ACCEPTED"
    QUALIFIED = "QUALIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED = "REJECTED"


class RelationUseState(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    QUALIFIED = "QUALIFIED"
    BLOCKED = "BLOCKED"


class MethodMatch(StrEnum):
    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    DISJOINT = "DISJOINT"


class EvidenceQuality(StrEnum):
    STRONG = "STRONG"
    ADEQUATE = "ADEQUATE"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True, slots=True)
class RelationAssessmentProposal:
    meta: EntityMeta
    research_card_id: EntityId
    edge_id: EntityId
    expected_edge_revision: int
    scope_match: str | None
    directness: str | None
    method_match: MethodMatch
    evidence_quality: EvidenceQuality
    rationale: str
    supporting_refs: tuple[EntityId, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RAP":
            raise ValueError("relation assessment proposal id must use RAP prefix")
        if self.research_card_id.namespace != "RCD":
            raise ValueError("research_card_id must use RCD prefix")
        if self.edge_id.namespace != "EDG":
            raise ValueError("edge_id must use EDG prefix")
        if self.expected_edge_revision < 1:
            raise ValueError("expected_edge_revision must be positive")
        if not isinstance(self.method_match, MethodMatch):
            raise TypeError("method_match must be MethodMatch")
        if not isinstance(self.evidence_quality, EvidenceQuality):
            raise TypeError("evidence_quality must be EvidenceQuality")
        if not self.rationale:
            raise ValueError("rationale is required")
        object.__setattr__(self, "supporting_refs", tuple(self.supporting_refs))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RelationAssessment:
    meta: EntityMeta
    proposal_id: EntityId
    research_card_id: EntityId
    edge_id: EntityId
    assessed_edge_revision: int
    edge_kind: EdgeKind
    verdict: RelationAssessmentVerdict
    use_state: RelationUseState
    reason_codes: tuple[str, ...]
    findings: tuple[str, ...]
    supporting_refs: tuple[EntityId, ...]
    validator_versions: Mapping[str, str]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RAS":
            raise ValueError("relation assessment id must use RAS prefix")
        if self.proposal_id.namespace != "RAP":
            raise ValueError("proposal_id must use RAP prefix")
        if self.research_card_id.namespace != "RCD":
            raise ValueError("research_card_id must use RCD prefix")
        if self.edge_id.namespace != "EDG":
            raise ValueError("edge_id must use EDG prefix")
        if self.assessed_edge_revision < 1:
            raise ValueError("assessed_edge_revision must be positive")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "supporting_refs", tuple(self.supporting_refs))
        object.__setattr__(self, "validator_versions", _deep_freeze(dict(self.validator_versions)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))

    @property
    def reasoning_eligible(self) -> bool:
        return self.use_state in {RelationUseState.ELIGIBLE, RelationUseState.QUALIFIED}


def _edge_for_validation(edge: GraphEdge, proposal: RelationAssessmentProposal) -> Mapping[str, Any]:
    attrs = dict(edge.attributes)
    if proposal.scope_match is not None:
        attrs["scope_match"] = proposal.scope_match
    if proposal.directness is not None:
        attrs["directness"] = proposal.directness
    return {
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "edge_kind": edge.edge_kind,
        "attributes": attrs,
    }


def _classify_support_relation(
    edge: GraphEdge,
    proposal: RelationAssessmentProposal,
) -> tuple[RelationAssessmentVerdict, RelationUseState, tuple[str, ...], tuple[str, ...], Mapping[str, str]]:
    view = _edge_for_validation(edge, proposal)
    edge_outcome = EdgeValidator().evaluate(view)
    reasons = list(edge_outcome.reason_codes)
    findings = list(edge_outcome.findings)
    versions = {"edge": EdgeValidator.version, "scope": ScopeValidator.version, "policy": "relation-assessment/1.0"}

    if edge_outcome.result is ValidationResult.FAIL:
        return RelationAssessmentVerdict.REJECTED, RelationUseState.BLOCKED, tuple(reasons), tuple(findings), versions
    if proposal.method_match is MethodMatch.DISJOINT:
        reasons.append("relation:method_disjoint")
        findings.append("method context is disjoint from the relation target")
        return RelationAssessmentVerdict.REJECTED, RelationUseState.BLOCKED, tuple(reasons), tuple(findings), versions
    if proposal.evidence_quality is EvidenceQuality.INSUFFICIENT:
        reasons.append("relation:evidence_insufficient")
        findings.append("evidence quality is insufficient for the declared relation")
        return RelationAssessmentVerdict.REJECTED, RelationUseState.BLOCKED, tuple(reasons), tuple(findings), versions
    if proposal.method_match is MethodMatch.UNKNOWN or proposal.evidence_quality is EvidenceQuality.UNKNOWN:
        reasons.append("relation:assessment_incomplete")
        findings.append("method match or evidence quality is unknown")
        return RelationAssessmentVerdict.INCONCLUSIVE, RelationUseState.BLOCKED, tuple(reasons), tuple(findings), versions

    qualified = (
        edge_outcome.result is ValidationResult.WARN
        or proposal.method_match is MethodMatch.PARTIAL
        or proposal.evidence_quality is EvidenceQuality.WEAK
    )
    if qualified:
        reasons.append("relation:qualified")
        findings.append("relation is usable only with qualification")
        return RelationAssessmentVerdict.QUALIFIED, RelationUseState.QUALIFIED, tuple(reasons), tuple(findings), versions
    return RelationAssessmentVerdict.ACCEPTED, RelationUseState.ELIGIBLE, tuple(reasons), tuple(findings), versions


def _classify_quantifies(
    edge: GraphEdge,
    proposal: RelationAssessmentProposal,
) -> tuple[RelationAssessmentVerdict, RelationUseState, tuple[str, ...], tuple[str, ...], Mapping[str, str]]:
    view = _edge_for_validation(edge, proposal)
    edge_outcome = EdgeValidator().evaluate(view)
    scope_outcome = ScopeValidator().evaluate(view) if proposal.scope_match is not None else None
    reasons = list(edge_outcome.reason_codes)
    findings = list(edge_outcome.findings)
    versions = {"edge": EdgeValidator.version, "scope": ScopeValidator.version, "policy": "relation-assessment/1.0"}
    if edge_outcome.result is ValidationResult.FAIL:
        return RelationAssessmentVerdict.REJECTED, RelationUseState.BLOCKED, tuple(reasons), tuple(findings), versions
    if scope_outcome is None:
        reasons.append("relation:quantifies_scope_unknown")
        findings.append("QUANTIFIES requires explicit scope_match for reasoning eligibility")
        return RelationAssessmentVerdict.INCONCLUSIVE, RelationUseState.BLOCKED, tuple(reasons), tuple(findings), versions
    reasons.extend(x for x in scope_outcome.reason_codes if x not in reasons)
    findings.extend(scope_outcome.findings)
    if scope_outcome.result is ValidationResult.FAIL or proposal.method_match is MethodMatch.DISJOINT or proposal.evidence_quality is EvidenceQuality.INSUFFICIENT:
        reasons.append("relation:quantifies_rejected")
        return RelationAssessmentVerdict.REJECTED, RelationUseState.BLOCKED, tuple(reasons), tuple(findings), versions
    if proposal.method_match is MethodMatch.UNKNOWN or proposal.evidence_quality is EvidenceQuality.UNKNOWN:
        reasons.append("relation:assessment_incomplete")
        return RelationAssessmentVerdict.INCONCLUSIVE, RelationUseState.BLOCKED, tuple(reasons), tuple(findings), versions
    if scope_outcome.result is ValidationResult.WARN or proposal.method_match is MethodMatch.PARTIAL or proposal.evidence_quality is EvidenceQuality.WEAK:
        reasons.append("relation:qualified")
        return RelationAssessmentVerdict.QUALIFIED, RelationUseState.QUALIFIED, tuple(reasons), tuple(findings), versions
    return RelationAssessmentVerdict.ACCEPTED, RelationUseState.ELIGIBLE, tuple(reasons), tuple(findings), versions


def assess_relation(
    *,
    edge: GraphEdge,
    proposal: RelationAssessmentProposal,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> tuple[RelationAssessment, ResearchTraceLink]:
    if edge.meta.id != proposal.edge_id:
        raise RelationAssessmentError("assessment target does not match edge")
    if edge.meta.run_id != proposal.meta.run_id:
        raise RelationAssessmentError("assessment proposal run lineage mismatch")
    if edge.meta.revision != proposal.expected_edge_revision:
        raise RelationAssessmentError("edge revision does not match expected_edge_revision")
    if edge.state is not GraphEdgeState.ACTIVE:
        raise RelationAssessmentError("only ACTIVE relations can be assessed as current")

    if edge.edge_kind in {EdgeKind.SUPPORTS, EdgeKind.CONTRADICTS}:
        verdict, use_state, reasons, findings, versions = _classify_support_relation(edge, proposal)
    elif edge.edge_kind is EdgeKind.QUANTIFIES:
        verdict, use_state, reasons, findings, versions = _classify_quantifies(edge, proposal)
    elif edge.edge_kind is EdgeKind.DERIVED_FROM:
        verdict, use_state = RelationAssessmentVerdict.INCONCLUSIVE, RelationUseState.BLOCKED
        reasons = ("relation:derivation_validator_not_implemented",)
        findings = ("DERIVED_FROM requires reproducibility/assumption validation not implemented in R3.3 L1",)
        versions = {"policy": "relation-assessment/1.0"}
    else:
        raise RelationAssessmentError(f"edge kind {edge.edge_kind.value} is not enabled for R3.3 assessment")

    assessment = RelationAssessment(
        meta=EntityMeta(id_factory.new("RAS"), "relation-assessment/1.0", 1, edge.meta.run_id, created_at, actor),
        proposal_id=proposal.meta.id,
        research_card_id=proposal.research_card_id,
        edge_id=edge.meta.id,
        assessed_edge_revision=edge.meta.revision,
        edge_kind=edge.edge_kind,
        verdict=verdict,
        use_state=use_state,
        reason_codes=reasons,
        findings=findings,
        supporting_refs=proposal.supporting_refs,
        validator_versions=versions,
        metadata={
            "proposal_metadata": dict(proposal.metadata),
            "signals": {
                "scope_match": proposal.scope_match,
                "directness": proposal.directness,
                "method_match": proposal.method_match.value,
                "evidence_quality": proposal.evidence_quality.value,
            },
        },
    )
    link = ResearchTraceLink(
        id=id_factory.new("RTL"),
        research_card_id=proposal.research_card_id,
        target_id=edge.meta.id,
        relation=ResearchTraceRelation.VALIDATED,
        run_id=edge.meta.run_id,
        created_at=created_at,
        created_by=actor,
        metadata={"assessment_id": str(assessment.meta.id), "assessment_verdict": assessment.verdict.value, "relation_assessment": True},
    )
    return assessment, link


def lifecycle_transition_from_assessment(
    *,
    edge: GraphEdge,
    assessment: RelationAssessment,
    actor: ActorRef,
    id_factory: EntityIdFactory,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
) -> RelationTransitionResult | None:
    if assessment.edge_id != edge.meta.id or assessment.assessed_edge_revision != edge.meta.revision:
        raise RelationAssessmentError("assessment does not match current edge revision")
    if assessment.verdict is not RelationAssessmentVerdict.REJECTED:
        return None
    return transition_relation_state(
        edge,
        RelationTransitionRequest(
            edge_id=edge.meta.id,
            expected_revision=edge.meta.revision,
            requested_state=GraphEdgeState.INVALIDATED,
            reason_codes=(ReasonCode("RELATION_ASSESSMENT_REJECTED"),),
        ),
        actor=actor,
        event_id=id_factory.new("EVT"),
        timestamp=timestamp,
        causation_id=causation_id,
        correlation_id=correlation_id,
    )


def latest_assessment_by_edge(
    assessments: Sequence[RelationAssessment],
) -> Mapping[EntityId, RelationAssessment]:
    """Choose one deterministic L1 assessment per edge.

    Later Tribunal aggregation may preserve multiple concurrent opinions. R3.3
    L1 instead uses newest assessed edge revision, then assessment creation time,
    then stable id as a deterministic tie-break.
    """
    latest: dict[EntityId, RelationAssessment] = {}
    for assessment in assessments:
        current = latest.get(assessment.edge_id)
        candidate_key = (assessment.assessed_edge_revision, assessment.meta.created_at, str(assessment.meta.id))
        current_key = None if current is None else (current.assessed_edge_revision, current.meta.created_at, str(current.meta.id))
        if current_key is None or candidate_key > current_key:
            latest[assessment.edge_id] = assessment
    return latest


def relation_assessment_proposal_to_dict(value: RelationAssessmentProposal) -> dict[str, Any]:
    return {
        "schema_version": "relation-assessment-proposal/1.0",
        "id": str(value.meta.id), "run_id": str(value.meta.run_id),
        "research_card_id": str(value.research_card_id), "edge_id": str(value.edge_id),
        "expected_edge_revision": value.expected_edge_revision,
        "scope_match": value.scope_match, "directness": value.directness,
        "method_match": value.method_match.value, "evidence_quality": value.evidence_quality.value,
        "rationale": value.rationale, "supporting_refs": [str(x) for x in value.supporting_refs],
        "metadata": dict(value.metadata),
    }


def relation_assessment_to_dict(value: RelationAssessment) -> dict[str, Any]:
    return {
        "schema_version": "relation-assessment/1.0",
        "id": str(value.meta.id), "run_id": str(value.meta.run_id),
        "proposal_id": str(value.proposal_id), "research_card_id": str(value.research_card_id),
        "edge_id": str(value.edge_id), "assessed_edge_revision": value.assessed_edge_revision,
        "edge_kind": value.edge_kind.value, "verdict": value.verdict.value, "use_state": value.use_state.value,
        "reason_codes": list(value.reason_codes), "findings": list(value.findings),
        "supporting_refs": [str(x) for x in value.supporting_refs],
        "validator_versions": dict(value.validator_versions), "metadata": dict(value.metadata),
    }


class RelationAssessmentAuditRepository:
    def __init__(self, conn) -> None:
        self._conn = conn

    def save_proposal(self, proposal: RelationAssessmentProposal) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(proposal.meta.id, relation_assessment_proposal_to_dict(proposal))
            uow.commit()

    def save_assessment(self, assessment: RelationAssessment) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(assessment.meta.id, relation_assessment_to_dict(assessment))
            uow.commit()
