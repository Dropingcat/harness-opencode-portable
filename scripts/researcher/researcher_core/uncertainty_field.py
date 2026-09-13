"""R3.5 multidimensional uncertainty field for pre-Tribunal review.

This module deliberately avoids a scalar confidence score.  It projects typed,
traceable uncertainty components from existing canonical knowledge objects and
packages unresolved assessment needs into a ReviewWorkField.  R3.5 defines
*what* remains uncertain and *how* it may be assessed; R4 decides *which
specialists* should perform that assessment.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any, Mapping, Sequence

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r0.sqlite_store import SqliteUnitOfWork
from researcher_core.r1_entities import Conflict, Gap
from researcher_core.uncertainty import compare_with_uncertainty
from researcher_core.relation_assessment import (
    EvidenceQuality,
    MethodMatch,
    RelationAssessment,
    RelationAssessmentVerdict,
    RelationUseState,
)


class UncertaintyFieldError(ValueError):
    pass


class UncertaintyAxis(StrEnum):
    NUMERIC_MEASUREMENT = "NUMERIC_MEASUREMENT"
    EVIDENCE_SUFFICIENCY = "EVIDENCE_SUFFICIENCY"
    SOURCE_PROVENANCE = "SOURCE_PROVENANCE"
    SCOPE = "SCOPE"
    METHOD = "METHOD"
    CONFLICT = "CONFLICT"
    DERIVATION = "DERIVATION"
    ASSUMPTION = "ASSUMPTION"
    CAUSALITY = "CAUSALITY"
    EXTRAPOLATION = "EXTRAPOLATION"
    FRESHNESS = "FRESHNESS"


class UncertaintyLevel(StrEnum):
    RESOLVED = "RESOLVED"
    QUALIFIED = "QUALIFIED"
    MATERIAL = "MATERIAL"
    BLOCKING = "BLOCKING"
    UNCHARACTERIZED = "UNCHARACTERIZED"


class UncertaintyOrigin(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    ADMITTED_OBJECT = "ADMITTED_OBJECT"
    SPECIALIST_SIGNAL = "SPECIALIST_SIGNAL"
    HUMAN_SIGNAL = "HUMAN_SIGNAL"


class AssessmentMethod(StrEnum):
    INTERVAL_OVERLAP = "INTERVAL_OVERLAP"
    CROSS_SOURCE_COMPARISON = "CROSS_SOURCE_COMPARISON"
    PROVENANCE_CHECK = "PROVENANCE_CHECK"
    SCOPE_ALIGNMENT = "SCOPE_ALIGNMENT"
    METHOD_COMPATIBILITY = "METHOD_COMPATIBILITY"
    EVIDENCE_QUALITY = "EVIDENCE_QUALITY"
    CONFLICT_ANALYSIS = "CONFLICT_ANALYSIS"
    DERIVATION_REPRODUCIBILITY = "DERIVATION_REPRODUCIBILITY"
    ASSUMPTION_AUDIT = "ASSUMPTION_AUDIT"
    CAUSAL_ALTERNATIVES = "CAUSAL_ALTERNATIVES"
    EXTRAPOLATION_CHECK = "EXTRAPOLATION_CHECK"
    FRESHNESS_CHECK = "FRESHNESS_CHECK"
    SPECIALIST_REVIEW = "SPECIALIST_REVIEW"
    EXPERIMENTAL_RETEST = "EXPERIMENTAL_RETEST"


class ReviewReadiness(StrEnum):
    CLEAR = "CLEAR"
    QUALIFIED = "QUALIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class UncertaintyComponent:
    axis: UncertaintyAxis
    level: UncertaintyLevel
    origin: UncertaintyOrigin
    blocking: bool
    reason_codes: tuple[str, ...] = ()
    source_refs: tuple[EntityId, ...] = ()
    assessment_methods: tuple[AssessmentMethod, ...] = ()
    required_checks: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.axis, UncertaintyAxis):
            raise TypeError("axis must be UncertaintyAxis")
        if not isinstance(self.level, UncertaintyLevel):
            raise TypeError("level must be UncertaintyLevel")
        if not isinstance(self.origin, UncertaintyOrigin):
            raise TypeError("origin must be UncertaintyOrigin")
        if self.level is UncertaintyLevel.BLOCKING and not self.blocking:
            raise ValueError("BLOCKING uncertainty must set blocking=True")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "source_refs", tuple(self.source_refs))
        object.__setattr__(self, "assessment_methods", tuple(self.assessment_methods))
        object.__setattr__(self, "required_checks", tuple(self.required_checks))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class UncertaintyProfile:
    meta: EntityMeta
    target_id: EntityId
    target_revision: int | None
    components: tuple[UncertaintyComponent, ...]
    readiness: ReviewReadiness
    dominant_axes: tuple[UncertaintyAxis, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "UPR":
            raise ValueError("uncertainty profile id must use UPR prefix")
        if self.target_revision is not None and self.target_revision < 1:
            raise ValueError("target_revision must be positive")
        if not isinstance(self.readiness, ReviewReadiness):
            raise TypeError("readiness must be ReviewReadiness")
        object.__setattr__(self, "components", tuple(self.components))
        object.__setattr__(self, "dominant_axes", tuple(self.dominant_axes))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssessmentNeed:
    axis: UncertaintyAxis
    level: UncertaintyLevel
    blocking: bool
    target_refs: tuple[EntityId, ...]
    source_refs: tuple[EntityId, ...]
    question: str
    assessment_methods: tuple[AssessmentMethod, ...]
    completion_criteria: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.target_refs:
            raise ValueError("assessment need requires target_refs")
        if not self.question.strip():
            raise ValueError("assessment need requires question")
        if not self.assessment_methods:
            raise ValueError("assessment need requires at least one assessment method")
        object.__setattr__(self, "target_refs", tuple(self.target_refs))
        object.__setattr__(self, "source_refs", tuple(self.source_refs))
        object.__setattr__(self, "assessment_methods", tuple(self.assessment_methods))
        object.__setattr__(self, "completion_criteria", tuple(self.completion_criteria))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


@dataclass(frozen=True, slots=True)
class ReviewWorkField:
    meta: EntityMeta
    request_id: EntityId
    target_refs: tuple[EntityId, ...]
    uncertainty_profile_ids: tuple[EntityId, ...]
    assessment_needs: tuple[AssessmentNeed, ...]
    open_gap_ids: tuple[EntityId, ...]
    conflict_ids: tuple[EntityId, ...]
    relation_assessment_ids: tuple[EntityId, ...]
    evidence_refs: tuple[EntityId, ...]
    readiness: ReviewReadiness
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RWF":
            raise ValueError("review work field id must use RWF prefix")
        if self.request_id.namespace != "RRQ":
            raise ValueError("request_id must use RRQ prefix")
        if any(x.namespace != "UPR" for x in self.uncertainty_profile_ids):
            raise ValueError("uncertainty_profile_ids must use UPR prefix")
        object.__setattr__(self, "target_refs", tuple(self.target_refs))
        object.__setattr__(self, "uncertainty_profile_ids", tuple(self.uncertainty_profile_ids))
        object.__setattr__(self, "assessment_needs", tuple(self.assessment_needs))
        object.__setattr__(self, "open_gap_ids", tuple(self.open_gap_ids))
        object.__setattr__(self, "conflict_ids", tuple(self.conflict_ids))
        object.__setattr__(self, "relation_assessment_ids", tuple(self.relation_assessment_ids))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


_LEVEL_RANK = {
    UncertaintyLevel.RESOLVED: 0,
    UncertaintyLevel.QUALIFIED: 1,
    UncertaintyLevel.MATERIAL: 2,
    UncertaintyLevel.UNCHARACTERIZED: 3,
    UncertaintyLevel.BLOCKING: 4,
}


def _readiness(components: Sequence[UncertaintyComponent]) -> ReviewReadiness:
    unresolved = [x for x in components if x.level is not UncertaintyLevel.RESOLVED]
    if not unresolved:
        return ReviewReadiness.CLEAR
    if any(x.blocking or x.level is UncertaintyLevel.BLOCKING for x in unresolved):
        return ReviewReadiness.BLOCKED
    if any(x.level in {UncertaintyLevel.MATERIAL, UncertaintyLevel.UNCHARACTERIZED} for x in unresolved):
        return ReviewReadiness.NEEDS_REVIEW
    return ReviewReadiness.QUALIFIED


def _dominant_axes(components: Sequence[UncertaintyComponent]) -> tuple[UncertaintyAxis, ...]:
    unresolved = [x for x in components if x.level is not UncertaintyLevel.RESOLVED]
    if not unresolved:
        return ()
    max_rank = max(_LEVEL_RANK[x.level] for x in unresolved)
    return tuple(dict.fromkeys(x.axis for x in unresolved if _LEVEL_RANK[x.level] == max_rank))


def _signal(assessment: RelationAssessment, key: str) -> Any:
    return dict(assessment.metadata).get("signals", {}).get(key)


def components_from_relation_assessment(assessment: RelationAssessment) -> tuple[UncertaintyComponent, ...]:
    """Project typed uncertainty axes from one canonical relation assessment."""
    components: list[UncertaintyComponent] = []
    method_match = _signal(assessment, "method_match")
    evidence_quality = _signal(assessment, "evidence_quality")
    scope_match = _signal(assessment, "scope_match")

    if method_match in {MethodMatch.UNKNOWN.value, None} and assessment.verdict is RelationAssessmentVerdict.INCONCLUSIVE:
        components.append(UncertaintyComponent(
            axis=UncertaintyAxis.METHOD,
            level=UncertaintyLevel.BLOCKING,
            origin=UncertaintyOrigin.DETERMINISTIC,
            blocking=True,
            reason_codes=("uncertainty:method_unknown",),
            source_refs=(assessment.meta.id, assessment.edge_id),
            assessment_methods=(AssessmentMethod.METHOD_COMPATIBILITY, AssessmentMethod.SPECIALIST_REVIEW),
            required_checks=("establish whether the evidence-generating method is applicable to the relation target",),
        ))
    elif method_match == MethodMatch.PARTIAL.value:
        components.append(UncertaintyComponent(
            axis=UncertaintyAxis.METHOD,
            level=UncertaintyLevel.QUALIFIED,
            origin=UncertaintyOrigin.DETERMINISTIC,
            blocking=False,
            reason_codes=("uncertainty:method_partial",),
            source_refs=(assessment.meta.id, assessment.edge_id),
            assessment_methods=(AssessmentMethod.METHOD_COMPATIBILITY,),
            required_checks=("state the method limitations and their effect on the relation",),
        ))

    if evidence_quality in {EvidenceQuality.UNKNOWN.value, None} and assessment.verdict is RelationAssessmentVerdict.INCONCLUSIVE:
        components.append(UncertaintyComponent(
            axis=UncertaintyAxis.EVIDENCE_SUFFICIENCY,
            level=UncertaintyLevel.BLOCKING,
            origin=UncertaintyOrigin.DETERMINISTIC,
            blocking=True,
            reason_codes=("uncertainty:evidence_quality_unknown",),
            source_refs=(assessment.meta.id, *assessment.supporting_refs),
            assessment_methods=(AssessmentMethod.EVIDENCE_QUALITY, AssessmentMethod.CROSS_SOURCE_COMPARISON),
            required_checks=("characterize evidence quality and whether independent support is required",),
        ))
    elif evidence_quality == EvidenceQuality.WEAK.value:
        components.append(UncertaintyComponent(
            axis=UncertaintyAxis.EVIDENCE_SUFFICIENCY,
            level=UncertaintyLevel.QUALIFIED,
            origin=UncertaintyOrigin.DETERMINISTIC,
            blocking=False,
            reason_codes=("uncertainty:evidence_weak",),
            source_refs=(assessment.meta.id, *assessment.supporting_refs),
            assessment_methods=(AssessmentMethod.EVIDENCE_QUALITY, AssessmentMethod.CROSS_SOURCE_COMPARISON),
            required_checks=("preserve qualification or obtain stronger independent evidence",),
        ))

    if scope_match is None and any("scope" in code for code in assessment.reason_codes):
        components.append(UncertaintyComponent(
            axis=UncertaintyAxis.SCOPE,
            level=UncertaintyLevel.UNCHARACTERIZED,
            origin=UncertaintyOrigin.DETERMINISTIC,
            blocking=assessment.use_state is RelationUseState.BLOCKED,
            reason_codes=("uncertainty:scope_uncharacterized",),
            source_refs=(assessment.meta.id, assessment.edge_id),
            assessment_methods=(AssessmentMethod.SCOPE_ALIGNMENT,),
            required_checks=("align population/material/conditions/time/method scope before using the relation",),
        ))
    elif scope_match and str(scope_match).upper() in {"PARTIAL", "OVERLAP", "PARTIAL_MATCH"}:
        components.append(UncertaintyComponent(
            axis=UncertaintyAxis.SCOPE,
            level=UncertaintyLevel.QUALIFIED,
            origin=UncertaintyOrigin.DETERMINISTIC,
            blocking=False,
            reason_codes=("uncertainty:scope_partial",),
            source_refs=(assessment.meta.id, assessment.edge_id),
            assessment_methods=(AssessmentMethod.SCOPE_ALIGNMENT,),
            required_checks=("state the scope mismatch explicitly",),
        ))

    if assessment.verdict is RelationAssessmentVerdict.INCONCLUSIVE and not components:
        components.append(UncertaintyComponent(
            axis=UncertaintyAxis.EVIDENCE_SUFFICIENCY,
            level=UncertaintyLevel.UNCHARACTERIZED,
            origin=UncertaintyOrigin.DETERMINISTIC,
            blocking=True,
            reason_codes=("uncertainty:relation_inconclusive_unclassified",),
            source_refs=(assessment.meta.id, assessment.edge_id),
            assessment_methods=(AssessmentMethod.SPECIALIST_REVIEW,),
            required_checks=("classify the unresolved relation uncertainty before reasoning",),
        ))
    return tuple(components)


def component_from_numeric_uncertainty(
    *,
    target_id: EntityId,
    value: Decimal,
    uncertainty: Decimal | None,
    reference_value: Decimal | None = None,
    reference_uncertainty: Decimal | None = None,
    required_for_decision: bool = False,
) -> UncertaintyComponent:
    """Project numeric uncertainty without inventing universal percentage thresholds.

    Severity is based on the available comparison contract, not on a hard-coded
    relative-error percentage.  If no reference interval is supplied, the
    numeric uncertainty remains uncharacterized for the intended decision.
    """
    if uncertainty is not None and uncertainty < 0:
        raise ValueError("uncertainty must be non-negative")
    status = "NO_REFERENCE"
    if reference_value is not None:
        status = compare_with_uncertainty(value, uncertainty, reference_value, reference_uncertainty)

    if status == "MATCH":
        level = UncertaintyLevel.QUALIFIED
        blocking = False
        reasons = ("uncertainty:numeric_intervals_overlap",)
    elif status == "PARTIAL_MATCH":
        level = UncertaintyLevel.MATERIAL
        blocking = required_for_decision
        reasons = ("uncertainty:numeric_partial_overlap",)
    elif status == "MISMATCH":
        level = UncertaintyLevel.MATERIAL
        blocking = required_for_decision
        reasons = ("uncertainty:numeric_intervals_mismatch",)
    else:
        level = UncertaintyLevel.BLOCKING if required_for_decision else UncertaintyLevel.UNCHARACTERIZED
        blocking = required_for_decision
        reasons = ("uncertainty:numeric_reference_or_uncertainty_missing",)

    return UncertaintyComponent(
        axis=UncertaintyAxis.NUMERIC_MEASUREMENT,
        level=level,
        origin=UncertaintyOrigin.DETERMINISTIC,
        blocking=blocking,
        reason_codes=reasons,
        source_refs=(target_id,),
        assessment_methods=(AssessmentMethod.INTERVAL_OVERLAP, AssessmentMethod.EXPERIMENTAL_RETEST),
        required_checks=(
            "compare explicit uncertainty intervals under aligned units and measurement conditions",
            "if the decision remains sensitive, obtain an independent measurement or retest",
        ),
        metadata={
            "comparison_status": status,
            "value": str(value),
            "uncertainty": None if uncertainty is None else str(uncertainty),
            "reference_value": None if reference_value is None else str(reference_value),
            "reference_uncertainty": None if reference_uncertainty is None else str(reference_uncertainty),
        },
    )


def component_from_gap(gap: Gap) -> UncertaintyComponent:
    gap_type = gap.gap_type.upper()
    if "METHOD" in gap_type:
        axis = UncertaintyAxis.METHOD
        methods = (AssessmentMethod.METHOD_COMPATIBILITY, AssessmentMethod.SPECIALIST_REVIEW)
    elif "SCOPE" in gap_type:
        axis = UncertaintyAxis.SCOPE
        methods = (AssessmentMethod.SCOPE_ALIGNMENT,)
    elif "DERIV" in gap_type:
        axis = UncertaintyAxis.DERIVATION
        methods = (AssessmentMethod.DERIVATION_REPRODUCIBILITY, AssessmentMethod.ASSUMPTION_AUDIT)
    elif "NUM" in gap_type or "MEASURE" in gap_type or "UNCERTAINTY" in gap_type:
        axis = UncertaintyAxis.NUMERIC_MEASUREMENT
        methods = (AssessmentMethod.INTERVAL_OVERLAP, AssessmentMethod.EXPERIMENTAL_RETEST)
    else:
        axis = UncertaintyAxis.EVIDENCE_SUFFICIENCY
        methods = (AssessmentMethod.EVIDENCE_QUALITY, AssessmentMethod.CROSS_SOURCE_COMPARISON)
    blocking = gap.status.value == "open_blocking_gaps" or gap.severity.lower() == "blocking"
    return UncertaintyComponent(
        axis=axis,
        level=UncertaintyLevel.BLOCKING if blocking else UncertaintyLevel.MATERIAL,
        origin=UncertaintyOrigin.ADMITTED_OBJECT,
        blocking=blocking,
        reason_codes=(f"gap:{gap.gap_type}",),
        source_refs=(gap.id,),
        assessment_methods=methods,
        required_checks=gap.resolution_requirements or ("resolve admitted knowledge gap",),
    )


def component_from_conflict(conflict: Conflict) -> UncertaintyComponent:
    blocking = conflict.status.value in {"conflict_blocked", "conflict_unresolved", "conflict_member"}
    return UncertaintyComponent(
        axis=UncertaintyAxis.CONFLICT,
        level=UncertaintyLevel.BLOCKING if blocking else UncertaintyLevel.MATERIAL,
        origin=UncertaintyOrigin.ADMITTED_OBJECT,
        blocking=blocking,
        reason_codes=(f"conflict:{conflict.conflict_type}",),
        source_refs=(conflict.id, *conflict.member_claim_ids, *conflict.member_evidence_ids),
        assessment_methods=(AssessmentMethod.CONFLICT_ANALYSIS, AssessmentMethod.SCOPE_ALIGNMENT, AssessmentMethod.CROSS_SOURCE_COMPARISON),
        required_checks=(
            "determine whether the conflict is substantive, scope-dependent, method-dependent, or evidence-limited",
        ),
    )


def build_uncertainty_profile(
    *,
    target_id: EntityId,
    target_revision: int | None,
    components: Sequence[UncertaintyComponent],
    id_factory: EntityIdFactory,
    actor: ActorRef,
    run_id: EntityId,
    created_at,
    metadata: Mapping[str, Any] | None = None,
) -> UncertaintyProfile:
    deduped: dict[tuple[str, str, tuple[str, ...]], UncertaintyComponent] = {}
    for component in components:
        key = (
            component.axis.value,
            component.level.value,
            tuple(str(x) for x in component.source_refs),
        )
        deduped.setdefault(key, component)
    ordered = tuple(deduped.values())
    return UncertaintyProfile(
        meta=EntityMeta(id_factory.new("UPR"), "uncertainty-profile/1.0", 1, run_id, created_at, actor),
        target_id=target_id,
        target_revision=target_revision,
        components=ordered,
        readiness=_readiness(ordered),
        dominant_axes=_dominant_axes(ordered),
        metadata=dict(metadata or {}),
    )


def _question_for(component: UncertaintyComponent, target_id: EntityId) -> str:
    return {
        UncertaintyAxis.NUMERIC_MEASUREMENT: f"What measurement uncertainty or interval is decision-relevant for {target_id}?",
        UncertaintyAxis.EVIDENCE_SUFFICIENCY: f"Is the evidence for {target_id} sufficient and independent enough for the intended conclusion?",
        UncertaintyAxis.SOURCE_PROVENANCE: f"Is the provenance and source chain for {target_id} trustworthy and complete?",
        UncertaintyAxis.SCOPE: f"Are the compared scopes aligned enough to use {target_id} without overgeneralization?",
        UncertaintyAxis.METHOD: f"Are the methods behind {target_id} compatible with the inference being made?",
        UncertaintyAxis.CONFLICT: f"What explains the unresolved conflict involving {target_id}?",
        UncertaintyAxis.DERIVATION: f"Is the derivation involving {target_id} reproducible under explicit assumptions?",
        UncertaintyAxis.ASSUMPTION: f"Which assumptions materially control {target_id}, and are they justified?",
        UncertaintyAxis.CAUSALITY: f"Are plausible alternative causes excluded for {target_id}?",
        UncertaintyAxis.EXTRAPOLATION: f"Does {target_id} exceed the evidence scope, and with what consequence?",
        UncertaintyAxis.FRESHNESS: f"Is the evidence supporting {target_id} still current?",
    }[component.axis]


def build_review_work_field(
    *,
    request_id: EntityId,
    profiles: Sequence[UncertaintyProfile],
    gaps: Sequence[Gap] = (),
    conflicts: Sequence[Conflict] = (),
    relation_assessments: Sequence[RelationAssessment] = (),
    id_factory: EntityIdFactory,
    actor: ActorRef,
    run_id: EntityId,
    created_at,
    metadata: Mapping[str, Any] | None = None,
) -> ReviewWorkField:
    if any(profile.meta.run_id != run_id for profile in profiles):
        raise UncertaintyFieldError("uncertainty profile run lineage mismatch")
    needs: list[AssessmentNeed] = []
    evidence_refs: list[EntityId] = []
    for profile in profiles:
        for component in profile.components:
            if component.level is UncertaintyLevel.RESOLVED:
                continue
            refs = tuple(dict.fromkeys((profile.target_id, *component.source_refs)))
            evidence_refs.extend(x for x in component.source_refs if x.namespace in {"EVD", "SRC", "EDG", "RAS"})
            needs.append(AssessmentNeed(
                axis=component.axis,
                level=component.level,
                blocking=component.blocking,
                target_refs=refs,
                source_refs=component.source_refs,
                question=_question_for(component, profile.target_id),
                assessment_methods=component.assessment_methods or (AssessmentMethod.SPECIALIST_REVIEW,),
                completion_criteria=component.required_checks or ("produce a typed disposition with supporting references",),
                reason_codes=component.reason_codes,
            ))
    readiness = ReviewReadiness.CLEAR
    if any(need.blocking for need in needs):
        readiness = ReviewReadiness.BLOCKED
    elif any(need.level in {UncertaintyLevel.MATERIAL, UncertaintyLevel.UNCHARACTERIZED} for need in needs):
        readiness = ReviewReadiness.NEEDS_REVIEW
    elif needs:
        readiness = ReviewReadiness.QUALIFIED
    return ReviewWorkField(
        meta=EntityMeta(id_factory.new("RWF"), "review-work-field/1.0", 1, run_id, created_at, actor),
        request_id=request_id,
        target_refs=tuple(dict.fromkeys(profile.target_id for profile in profiles)),
        uncertainty_profile_ids=tuple(profile.meta.id for profile in profiles),
        assessment_needs=tuple(needs),
        open_gap_ids=tuple(gap.id for gap in gaps),
        conflict_ids=tuple(conflict.id for conflict in conflicts),
        relation_assessment_ids=tuple(x.meta.id for x in relation_assessments),
        evidence_refs=tuple(dict.fromkeys(evidence_refs)),
        readiness=readiness,
        metadata={
            "composition_boundary": "R3 defines what must be assessed; R4 selects who assesses it",
            **dict(metadata or {}),
        },
    )


def _meta_to_dict(meta: EntityMeta) -> dict[str, Any]:
    return {
        "id": str(meta.id),
        "schema_version": meta.schema_version,
        "revision": meta.revision,
        "run_id": str(meta.run_id),
        "created_at": meta.created_at.isoformat(),
        "created_by": {"actor_type": meta.created_by.actor_type, "actor_id": meta.created_by.actor_id},
    }


def _meta_from_dict(raw: Mapping[str, Any]) -> EntityMeta:
    from datetime import datetime
    return EntityMeta(
        id=EntityId(str(raw["id"])),
        schema_version=str(raw["schema_version"]),
        revision=int(raw["revision"]),
        run_id=EntityId(str(raw["run_id"])),
        created_at=datetime.fromisoformat(str(raw["created_at"])),
        created_by=ActorRef(str(raw["created_by"]["actor_type"]), str(raw["created_by"]["actor_id"])),
    )


def uncertainty_profile_to_dict(profile: UncertaintyProfile) -> dict[str, Any]:
    return {
        "schema_version": profile.meta.schema_version,
        "meta": _meta_to_dict(profile.meta),
        "target_id": str(profile.target_id),
        "target_revision": profile.target_revision,
        "readiness": profile.readiness.value,
        "dominant_axes": [x.value for x in profile.dominant_axes],
        "components": [
            {
                "axis": x.axis.value,
                "level": x.level.value,
                "origin": x.origin.value,
                "blocking": x.blocking,
                "reason_codes": list(x.reason_codes),
                "source_refs": [str(ref) for ref in x.source_refs],
                "assessment_methods": [method.value for method in x.assessment_methods],
                "required_checks": list(x.required_checks),
                "metadata": dict(x.metadata),
            }
            for x in profile.components
        ],
        "metadata": dict(profile.metadata),
    }


def uncertainty_profile_from_dict(raw: Mapping[str, Any]) -> UncertaintyProfile:
    return UncertaintyProfile(
        meta=_meta_from_dict(raw["meta"]),
        target_id=EntityId(str(raw["target_id"])),
        target_revision=None if raw.get("target_revision") is None else int(raw["target_revision"]),
        components=tuple(
            UncertaintyComponent(
                axis=UncertaintyAxis(str(x["axis"])),
                level=UncertaintyLevel(str(x["level"])),
                origin=UncertaintyOrigin(str(x["origin"])),
                blocking=bool(x["blocking"]),
                reason_codes=tuple(str(v) for v in x.get("reason_codes", ())),
                source_refs=tuple(EntityId(str(v)) for v in x.get("source_refs", ())),
                assessment_methods=tuple(AssessmentMethod(str(v)) for v in x.get("assessment_methods", ())),
                required_checks=tuple(str(v) for v in x.get("required_checks", ())),
                metadata=dict(x.get("metadata", {})),
            )
            for x in raw.get("components", ())
        ),
        readiness=ReviewReadiness(str(raw["readiness"])),
        dominant_axes=tuple(UncertaintyAxis(str(x)) for x in raw.get("dominant_axes", ())),
        metadata=dict(raw.get("metadata", {})),
    )


def review_work_field_to_dict(field: ReviewWorkField) -> dict[str, Any]:
    return {
        "schema_version": field.meta.schema_version,
        "meta": _meta_to_dict(field.meta),
        "request_id": str(field.request_id),
        "target_refs": [str(x) for x in field.target_refs],
        "uncertainty_profile_ids": [str(x) for x in field.uncertainty_profile_ids],
        "readiness": field.readiness.value,
        "assessment_needs": [
            {
                "axis": x.axis.value,
                "level": x.level.value,
                "blocking": x.blocking,
                "target_refs": [str(ref) for ref in x.target_refs],
                "source_refs": [str(ref) for ref in x.source_refs],
                "question": x.question,
                "assessment_methods": [method.value for method in x.assessment_methods],
                "completion_criteria": list(x.completion_criteria),
                "reason_codes": list(x.reason_codes),
            }
            for x in field.assessment_needs
        ],
        "open_gap_ids": [str(x) for x in field.open_gap_ids],
        "conflict_ids": [str(x) for x in field.conflict_ids],
        "relation_assessment_ids": [str(x) for x in field.relation_assessment_ids],
        "evidence_refs": [str(x) for x in field.evidence_refs],
        "metadata": dict(field.metadata),
    }


def review_work_field_from_dict(raw: Mapping[str, Any]) -> ReviewWorkField:
    return ReviewWorkField(
        meta=_meta_from_dict(raw["meta"]),
        request_id=EntityId(str(raw["request_id"])),
        target_refs=tuple(EntityId(str(x)) for x in raw.get("target_refs", ())),
        uncertainty_profile_ids=tuple(EntityId(str(x)) for x in raw.get("uncertainty_profile_ids", ())),
        assessment_needs=tuple(
            AssessmentNeed(
                axis=UncertaintyAxis(str(x["axis"])),
                level=UncertaintyLevel(str(x["level"])),
                blocking=bool(x["blocking"]),
                target_refs=tuple(EntityId(str(v)) for v in x.get("target_refs", ())),
                source_refs=tuple(EntityId(str(v)) for v in x.get("source_refs", ())),
                question=str(x["question"]),
                assessment_methods=tuple(AssessmentMethod(str(v)) for v in x.get("assessment_methods", ())),
                completion_criteria=tuple(str(v) for v in x.get("completion_criteria", ())),
                reason_codes=tuple(str(v) for v in x.get("reason_codes", ())),
            )
            for x in raw.get("assessment_needs", ())
        ),
        open_gap_ids=tuple(EntityId(str(x)) for x in raw.get("open_gap_ids", ())),
        conflict_ids=tuple(EntityId(str(x)) for x in raw.get("conflict_ids", ())),
        relation_assessment_ids=tuple(EntityId(str(x)) for x in raw.get("relation_assessment_ids", ())),
        evidence_refs=tuple(EntityId(str(x)) for x in raw.get("evidence_refs", ())),
        readiness=ReviewReadiness(str(raw["readiness"])),
        metadata=dict(raw.get("metadata", {})),
    )


class UncertaintyFieldRepository:
    """Durable audit projection for profiles and review work fields."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def save_profile(self, profile: UncertaintyProfile) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(profile.meta.id, uncertainty_profile_to_dict(profile))
            uow.commit()

    def save_work_field(self, field: ReviewWorkField) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(field.meta.id, review_work_field_to_dict(field))
            uow.commit()

    def load_profile(self, profile_id: EntityId) -> UncertaintyProfile | None:
        raw = SqliteUnitOfWork(self._conn).state_view().get(str(profile_id))
        if raw is None or raw.get("schema_version") != "uncertainty-profile/1.0":
            return None
        return uncertainty_profile_from_dict(raw)

    def load_work_field(self, field_id: EntityId) -> ReviewWorkField | None:
        raw = SqliteUnitOfWork(self._conn).state_view().get(str(field_id))
        if raw is None or raw.get("schema_version") != "review-work-field/1.0":
            return None
        return review_work_field_from_dict(raw)
