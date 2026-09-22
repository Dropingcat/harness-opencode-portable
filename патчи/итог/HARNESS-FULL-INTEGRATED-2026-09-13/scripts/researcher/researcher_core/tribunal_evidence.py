"""R4.2 deterministic evidence slicing for Tribunal roles.

R4.1 decides *who* reviews each AssessmentNeed and issues an EvidenceViewPolicy.
R4.2 compiles that policy into bounded, typed per-role evidence slices from
canonical Researcher entities.  It does not run Tribunal dialogue, does not
search for new evidence and does not mutate knowledge state.

The compiler intentionally fails closed on authority/policy mismatches and
reports partial/blocked slices instead of silently widening a role's view.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from researcher_core.r0.entities import Claim, EvidenceSpan, Quantity, Source
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.graph import GraphEdge, GraphEdgeState
from researcher_core.r0.enums import EdgeKind
from researcher_core.r0.ids import EntityId
from researcher_core.tribunal_composition import (
    AssessmentNeedRef,
    EvidenceViewKind,
    RoleBriefContract,
    TribunalCompositionPlan,
    assessment_need_refs_for_work_field,
    validate_tribunal_composition_plan_integrity,
    TribunalCompositionError,
)
from researcher_core.uncertainty_field import AssessmentNeed, ReviewWorkField


class TribunalEvidenceError(RuntimeError):
    pass


class EvidenceSliceStatus(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class EvidencePolarity(StrEnum):
    SUPPORT = "SUPPORT"
    COUNTER = "COUNTER"
    UNLABELED = "UNLABELED"


class EvidenceSelectionReason(StrEnum):
    EXPLICIT_NEED_REF = "EXPLICIT_NEED_REF"
    SUPPORT_RELATION = "SUPPORT_RELATION"
    COUNTER_RELATION = "COUNTER_RELATION"
    TARGET_RELATION_SOURCE = "TARGET_RELATION_SOURCE"
    ASSIGNED_RELEVANCE = "ASSIGNED_RELEVANCE"


RegistryEntity = Claim | Quantity | Source | EvidenceSpan | GraphEdge


@dataclass(frozen=True, slots=True)
class EvidenceItemProjection:
    evidence_id: EntityId
    exact_text: str
    text_hash: str
    polarity: EvidencePolarity
    source_id: EntityId | None = None
    locator: str | None = None
    selection_reasons: tuple[EvidenceSelectionReason, ...] = ()

    def __post_init__(self) -> None:
        if self.evidence_id.namespace != "EVD":
            raise ValueError("evidence_id must use EVD prefix")
        if self.source_id is not None and self.source_id.namespace != "SRC":
            raise ValueError("source_id must use SRC prefix")
        object.__setattr__(self, "selection_reasons", tuple(self.selection_reasons))


@dataclass(frozen=True, slots=True)
class SourceProjection:
    source_id: EntityId
    source_type: str
    title: str
    locator: str
    content_hash: str | None

    def __post_init__(self) -> None:
        if self.source_id.namespace != "SRC":
            raise ValueError("source_id must use SRC prefix")


@dataclass(frozen=True, slots=True)
class TargetProjection:
    target_id: EntityId
    entity_type: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", _deep_freeze(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class PriorReviewArtifact:
    """Non-authoritative prior review context offered to the slicer.

    R4.2 only controls visibility.  A later inquiry layer will replace this
    generic envelope with canonical Argument/InquiryTurn contracts.
    """

    artifact_id: str
    artifact_type: str
    target_refs: tuple[EntityId, ...]
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.artifact_type:
            raise ValueError("prior review artifact requires id and type")
        object.__setattr__(self, "target_refs", tuple(self.target_refs))
        object.__setattr__(self, "payload", _deep_freeze(dict(self.payload)))


@dataclass(frozen=True, slots=True)
class TribunalEvidenceSlice:
    role_id: str
    work_field_id: EntityId
    composition_fingerprint: str
    assigned_need_refs: tuple[AssessmentNeedRef, ...]
    view_kind: EvidenceViewKind
    include_provenance: bool
    include_previous_conclusions: bool
    target_projections: tuple[TargetProjection, ...]
    evidence_items: tuple[EvidenceItemProjection, ...]
    source_projections: tuple[SourceProjection, ...]
    prior_review_artifacts: tuple[PriorReviewArtifact, ...]
    missing_refs: tuple[EntityId, ...]
    status: EvidenceSliceStatus
    truncated: bool
    slice_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.work_field_id.namespace != "RWF":
            raise ValueError("work_field_id must use RWF prefix")
        object.__setattr__(self, "assigned_need_refs", tuple(self.assigned_need_refs))
        object.__setattr__(self, "target_projections", tuple(self.target_projections))
        object.__setattr__(self, "evidence_items", tuple(self.evidence_items))
        object.__setattr__(self, "source_projections", tuple(self.source_projections))
        object.__setattr__(self, "prior_review_artifacts", tuple(self.prior_review_artifacts))
        object.__setattr__(self, "missing_refs", tuple(self.missing_refs))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TribunalEvidenceBundle:
    work_field_id: EntityId
    composition_fingerprint: str
    slices: tuple[TribunalEvidenceSlice, ...]
    bundle_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.work_field_id.namespace != "RWF":
            raise ValueError("work_field_id must use RWF prefix")
        object.__setattr__(self, "slices", tuple(self.slices))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TribunalEvidenceRequest:
    work_field: ReviewWorkField
    composition_plan: TribunalCompositionPlan
    canonical_state: Mapping[EntityId | str, RegistryEntity]
    prior_review_artifacts: tuple[PriorReviewArtifact, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "prior_review_artifacts", tuple(self.prior_review_artifacts))


def compile_tribunal_evidence_bundle(request: TribunalEvidenceRequest) -> TribunalEvidenceBundle:
    field = request.work_field
    plan = request.composition_plan
    try:
        validate_tribunal_composition_plan_integrity(plan)
    except TribunalCompositionError as exc:
        raise TribunalEvidenceError(f"invalid composition plan:{exc}") from exc
    if plan.work_field_id != field.meta.id:
        raise TribunalEvidenceError("composition plan/work field mismatch")

    state = _normalize_state(request.canonical_state)
    _validate_state_run_lineage(state, field.meta.run_id)
    need_index = _need_index(field)

    slices = tuple(
        _compile_role_slice(
            field=field,
            plan=plan,
            brief=brief,
            need_index=need_index,
            state=state,
            prior_review_artifacts=request.prior_review_artifacts,
        )
        for brief in plan.role_briefs
    )
    bundle_payload = {
        "rwf": str(field.meta.id),
        "composition_fingerprint": plan.composition_fingerprint,
        "slices": [(x.role_id, x.slice_fingerprint) for x in slices],
    }
    bundle_fingerprint = _fingerprint(bundle_payload)
    return TribunalEvidenceBundle(
        work_field_id=field.meta.id,
        composition_fingerprint=plan.composition_fingerprint,
        slices=slices,
        bundle_fingerprint=bundle_fingerprint,
        metadata={
            "authority_boundary": "evidence slicing only; no search, Tribunal dialogue or knowledge-state mutation",
            "view_authority": "EvidenceViewPolicy from TribunalCompositionPlan; worker cannot widen slice",
        },
    )


def tribunal_evidence_bundle_to_dict(bundle: TribunalEvidenceBundle) -> dict[str, Any]:
    return {
        "schema_version": "tribunal-evidence-bundle/1.0",
        "work_field_id": str(bundle.work_field_id),
        "composition_fingerprint": bundle.composition_fingerprint,
        "bundle_fingerprint": bundle.bundle_fingerprint,
        "slices": [tribunal_evidence_slice_to_dict(x) for x in bundle.slices],
        "metadata": dict(bundle.metadata),
    }


def tribunal_evidence_slice_to_dict(slice_: TribunalEvidenceSlice) -> dict[str, Any]:
    return {
        "schema_version": "tribunal-evidence-slice/1.0",
        "role_id": slice_.role_id,
        "work_field_id": str(slice_.work_field_id),
        "composition_fingerprint": slice_.composition_fingerprint,
        "assigned_need_refs": [
            {"key": x.key, "ordinal": x.ordinal} for x in slice_.assigned_need_refs
        ],
        "view_kind": slice_.view_kind.value,
        "include_provenance": slice_.include_provenance,
        "include_previous_conclusions": slice_.include_previous_conclusions,
        "target_projections": [
            {"target_id": str(x.target_id), "entity_type": x.entity_type, "payload": dict(x.payload)}
            for x in slice_.target_projections
        ],
        "evidence_items": [
            {
                "evidence_id": str(x.evidence_id),
                "exact_text": x.exact_text,
                "text_hash": x.text_hash,
                "polarity": x.polarity.value,
                "source_id": None if x.source_id is None else str(x.source_id),
                "locator": x.locator,
                "selection_reasons": [r.value for r in x.selection_reasons],
            }
            for x in slice_.evidence_items
        ],
        "source_projections": [
            {
                "source_id": str(x.source_id),
                "source_type": x.source_type,
                "title": x.title,
                "locator": x.locator,
                "content_hash": x.content_hash,
            }
            for x in slice_.source_projections
        ],
        "prior_review_artifacts": [
            {
                "artifact_id": x.artifact_id,
                "artifact_type": x.artifact_type,
                "target_refs": [str(v) for v in x.target_refs],
                "payload": dict(x.payload),
            }
            for x in slice_.prior_review_artifacts
        ],
        "missing_refs": [str(x) for x in slice_.missing_refs],
        "status": slice_.status.value,
        "truncated": slice_.truncated,
        "slice_fingerprint": slice_.slice_fingerprint,
        "metadata": dict(slice_.metadata),
    }


def _compile_role_slice(
    *,
    field: ReviewWorkField,
    plan: TribunalCompositionPlan,
    brief: RoleBriefContract,
    need_index: Mapping[tuple[str, int], AssessmentNeed],
    state: Mapping[EntityId, RegistryEntity],
    prior_review_artifacts: Sequence[PriorReviewArtifact],
) -> TribunalEvidenceSlice:
    needs = tuple(_need_for_ref(ref, need_index) for ref in brief.assigned_need_refs)
    target_refs = _role_target_refs(needs, state)
    explicit_evd, explicit_src = _explicit_refs(needs)
    support_evd, counter_evd, relation_source_evd = _relation_evidence(target_refs, state)

    reasons: dict[EntityId, list[EvidenceSelectionReason]] = {}
    for ref in explicit_evd:
        reasons.setdefault(ref, []).append(EvidenceSelectionReason.EXPLICIT_NEED_REF)
    for ref in support_evd:
        reasons.setdefault(ref, []).append(EvidenceSelectionReason.SUPPORT_RELATION)
    for ref in counter_evd:
        reasons.setdefault(ref, []).append(EvidenceSelectionReason.COUNTER_RELATION)
    for ref in relation_source_evd:
        reasons.setdefault(ref, []).append(EvidenceSelectionReason.TARGET_RELATION_SOURCE)

    selected_order = _select_evidence_order(
        brief.evidence_view.kind,
        explicit_evd=explicit_evd,
        support_evd=support_evd,
        counter_evd=counter_evd,
        relation_source_evd=relation_source_evd,
    )
    max_refs = brief.evidence_view.max_refs
    truncated = max_refs is not None and len(selected_order) > max_refs
    if truncated:
        selected_order = selected_order[:max_refs]

    missing: list[EntityId] = []
    items: list[EvidenceItemProjection] = []
    visible_source_ids: list[EntityId] = []
    for evd_id in selected_order:
        entity = state.get(evd_id)
        if not isinstance(entity, EvidenceSpan):
            missing.append(evd_id)
            continue
        polarity = _polarity_for_view(
            brief.evidence_view.kind,
            evd_id,
            support_evd=support_evd,
            counter_evd=counter_evd,
        )
        include_provenance = brief.evidence_view.include_provenance
        item_reasons = tuple(_dedupe(reasons.get(evd_id, ())))
        if brief.evidence_view.kind is EvidenceViewKind.FRESH_CONTEXT:
            # Do not leak why the control plane selected an excerpt if that
            # reason itself reveals SUPPORT/COUNTER semantics.
            item_reasons = (EvidenceSelectionReason.ASSIGNED_RELEVANCE,)
        items.append(EvidenceItemProjection(
            evidence_id=evd_id,
            exact_text=entity.exact_text,
            text_hash=entity.text_hash,
            polarity=polarity,
            source_id=entity.source_id if include_provenance else None,
            locator=entity.locator if include_provenance else None,
            selection_reasons=item_reasons,
        ))
        if include_provenance:
            visible_source_ids.append(entity.source_id)

    if brief.evidence_view.include_provenance:
        if brief.evidence_view.kind in {EvidenceViewKind.FULL_RELEVANT, EvidenceViewKind.METHOD_ONLY}:
            visible_source_ids.extend(explicit_src)
    source_projections: list[SourceProjection] = []
    for src_id in sorted(set(visible_source_ids), key=str):
        source = state.get(src_id)
        if not isinstance(source, Source):
            missing.append(src_id)
            continue
        source_projections.append(SourceProjection(
            source_id=src_id,
            source_type=source.source_type,
            title=source.title,
            locator=source.locator,
            content_hash=source.content_hash,
        ))

    targets: list[TargetProjection] = []
    for target_id in sorted(target_refs, key=str):
        projection = _target_projection(
            target_id,
            state,
            include_provenance=brief.evidence_view.include_provenance,
            blind_semantics=brief.evidence_view.kind is EvidenceViewKind.FRESH_CONTEXT,
        )
        if projection is None:
            missing.append(target_id)
        else:
            targets.append(projection)

    prior = _visible_prior_review_artifacts(
        prior_review_artifacts,
        target_refs,
        include=brief.evidence_view.include_previous_conclusions,
    )

    blocking_need = any(need.blocking for need in needs)
    missing = _dedupe(missing)
    has_visible_payload = bool(items or targets or source_projections or prior)
    if blocking_need and (missing or not has_visible_payload):
        # BLOCKED is a slice-compilation state: a required canonical ref is
        # unavailable (or nothing executable can be shown).  It is not an
        # epistemic verdict that the AssessmentNeed itself is unresolved.
        status = EvidenceSliceStatus.BLOCKED
    elif missing or truncated:
        status = EvidenceSliceStatus.PARTIAL
    else:
        status = EvidenceSliceStatus.READY

    fp_payload = {
        "role": brief.role_id,
        "rwf": str(field.meta.id),
        "composition": plan.composition_fingerprint,
        "view": brief.evidence_view.kind.value,
        "provenance": brief.evidence_view.include_provenance,
        "previous": brief.evidence_view.include_previous_conclusions,
        "targets": [str(x.target_id) for x in targets],
        "evidence": [
            (str(x.evidence_id), x.polarity.value, None if x.source_id is None else str(x.source_id), x.locator)
            for x in items
        ],
        "sources": [str(x.source_id) for x in source_projections],
        "prior": [x.artifact_id for x in prior],
        "missing": [str(x) for x in missing],
        "truncated": truncated,
    }
    return TribunalEvidenceSlice(
        role_id=brief.role_id,
        work_field_id=field.meta.id,
        composition_fingerprint=plan.composition_fingerprint,
        assigned_need_refs=brief.assigned_need_refs,
        view_kind=brief.evidence_view.kind,
        include_provenance=brief.evidence_view.include_provenance,
        include_previous_conclusions=brief.evidence_view.include_previous_conclusions,
        target_projections=tuple(targets),
        evidence_items=tuple(items),
        source_projections=tuple(source_projections),
        prior_review_artifacts=tuple(prior),
        missing_refs=tuple(sorted(missing, key=str)),
        status=status,
        truncated=truncated,
        slice_fingerprint=_fingerprint(fp_payload),
        metadata={
            "selection_boundary": "canonical refs and typed GraphEdge relations only; no free-text source classification",
            "method_only_semantics": "explicit AssessmentNeed refs plus evidence that is source of an assigned target relation",
            "missing_refs_fail_visible": True,
            "nonprojected_control_refs": [
                str(ref)
                for ref in sorted(
                    {ref for need in needs for ref in need.target_refs if ref.namespace not in _PROJECTABLE_TARGET_NAMESPACES},
                    key=str,
                )
            ],
        },
    )


def _need_index(field: ReviewWorkField) -> Mapping[tuple[str, int], AssessmentNeed]:
    refs = assessment_need_refs_for_work_field(field)
    return MappingProxyType({
        (ref.key, ref.ordinal): need
        for ref, need in zip(refs, field.assessment_needs, strict=True)
    })


def _need_for_ref(
    ref: AssessmentNeedRef, index: Mapping[tuple[str, int], AssessmentNeed]
) -> AssessmentNeed:
    need = index.get((ref.key, ref.ordinal))
    if need is None:
        raise TribunalEvidenceError(
            f"composition plan contains unknown AssessmentNeedRef:{ref.key}:{ref.ordinal}"
        )
    return need


_PROJECTABLE_TARGET_NAMESPACES = frozenset({"CLM", "QTY", "EDG", "EVD", "SRC"})


def _role_target_refs(needs: Sequence[AssessmentNeed], state: Mapping[EntityId, RegistryEntity]) -> set[EntityId]:
    # R3.5 currently folds component.source_refs into AssessmentNeed.target_refs.
    # Consequently control/lineage refs such as RAS/GAP/CNF may occur here.
    # They are not evidence-registry targets and must not be treated as missing
    # evidence merely because R4.2 does not project those control-plane objects.
    refs = {
        ref for need in needs for ref in need.target_refs
        if ref.namespace in _PROJECTABLE_TARGET_NAMESPACES
    }
    # If an uncertainty target is a relation, the judge must also see the
    # relation endpoints.  This is structural expansion, not semantic inference.
    for ref in tuple(refs):
        edge = state.get(ref)
        if isinstance(edge, GraphEdge):
            refs.add(edge.source_id)
            refs.add(edge.target_id)
    return refs


def _explicit_refs(needs: Sequence[AssessmentNeed]) -> tuple[set[EntityId], set[EntityId]]:
    evd: set[EntityId] = set()
    src: set[EntityId] = set()
    for need in needs:
        for ref in need.source_refs:
            if ref.namespace == "EVD":
                evd.add(ref)
            elif ref.namespace == "SRC":
                src.add(ref)
    return evd, src


def _relation_evidence(
    target_refs: set[EntityId], state: Mapping[EntityId, RegistryEntity]
) -> tuple[set[EntityId], set[EntityId], set[EntityId]]:
    target_claims = {x for x in target_refs if x.namespace == "CLM"}
    relation_source_evd: set[EntityId] = set()
    for ref in target_refs:
        edge = state.get(ref)
        if isinstance(edge, GraphEdge) and edge.source_id.namespace == "EVD":
            relation_source_evd.add(edge.source_id)
            if edge.target_id.namespace == "CLM":
                target_claims.add(edge.target_id)

    support: set[EntityId] = set()
    counter: set[EntityId] = set()
    for entity in state.values():
        if not isinstance(entity, GraphEdge) or entity.state is not GraphEdgeState.ACTIVE:
            continue
        if entity.source_id.namespace != "EVD" or entity.target_id not in target_claims:
            continue
        if entity.edge_kind is EdgeKind.SUPPORTS:
            support.add(entity.source_id)
        elif entity.edge_kind is EdgeKind.CONTRADICTS:
            counter.add(entity.source_id)
    return support, counter, relation_source_evd


def _select_evidence_order(
    kind: EvidenceViewKind,
    *,
    explicit_evd: set[EntityId],
    support_evd: set[EntityId],
    counter_evd: set[EntityId],
    relation_source_evd: set[EntityId],
) -> list[EntityId]:
    unclassified_explicit = explicit_evd.difference(support_evd).difference(counter_evd)
    if kind is EvidenceViewKind.CLAIM_PLUS_SUPPORT:
        groups = (support_evd, unclassified_explicit, relation_source_evd.intersection(support_evd))
    elif kind is EvidenceViewKind.CLAIM_PLUS_COUNTEREVIDENCE:
        groups = (counter_evd, unclassified_explicit, relation_source_evd.intersection(counter_evd))
    elif kind is EvidenceViewKind.METHOD_ONLY:
        groups = (explicit_evd, relation_source_evd)
    elif kind in {EvidenceViewKind.FULL_RELEVANT, EvidenceViewKind.FRESH_CONTEXT}:
        groups = (explicit_evd, support_evd, counter_evd, relation_source_evd)
    else:  # defensive for future enum extensions
        raise TribunalEvidenceError(f"unsupported evidence view kind:{kind}")
    result: list[EntityId] = []
    for group in groups:
        for ref in sorted(group, key=str):
            if ref not in result:
                result.append(ref)
    return result


def _polarity_for_view(
    kind: EvidenceViewKind,
    evidence_id: EntityId,
    *,
    support_evd: set[EntityId],
    counter_evd: set[EntityId],
) -> EvidencePolarity:
    if kind in {EvidenceViewKind.FRESH_CONTEXT, EvidenceViewKind.METHOD_ONLY}:
        return EvidencePolarity.UNLABELED
    if evidence_id in counter_evd:
        return EvidencePolarity.COUNTER
    if evidence_id in support_evd:
        return EvidencePolarity.SUPPORT
    return EvidencePolarity.UNLABELED


def _visible_prior_review_artifacts(
    artifacts: Sequence[PriorReviewArtifact],
    target_refs: set[EntityId],
    *,
    include: bool,
) -> tuple[PriorReviewArtifact, ...]:
    if not include:
        return ()
    return tuple(
        artifact
        for artifact in sorted(artifacts, key=lambda x: x.artifact_id)
        if target_refs.intersection(artifact.target_refs)
    )


def _target_projection(
    target_id: EntityId,
    state: Mapping[EntityId, RegistryEntity],
    *,
    include_provenance: bool,
    blind_semantics: bool = False,
) -> TargetProjection | None:
    entity = state.get(target_id)
    if isinstance(entity, Claim):
        return TargetProjection(target_id, "Claim", {
            "proposition": entity.proposition,
            "claim_type": str(entity.claim_type),
            "revision": entity.meta.revision,
        })
    if isinstance(entity, Quantity):
        return TargetProjection(target_id, "Quantity", {
            "value": str(entity.value),
            "unit": entity.unit,
            "measured_property": entity.measured_property,
            "revision": entity.meta.revision,
        })
    if isinstance(entity, GraphEdge):
        if blind_semantics:
            return TargetProjection(target_id, "GraphEdge", {
                "revision": entity.meta.revision,
                "relation_semantics_hidden": True,
            })
        return TargetProjection(target_id, "GraphEdge", {
            "source_id": str(entity.source_id),
            "target_id": str(entity.target_id),
            "edge_kind": entity.edge_kind.value,
            "revision": entity.meta.revision,
        })
    if isinstance(entity, EvidenceSpan):
        payload: dict[str, Any] = {
            "exact_text": entity.exact_text,
            "text_hash": entity.text_hash,
            "revision": entity.meta.revision,
        }
        if include_provenance:
            payload["source_id"] = str(entity.source_id)
            payload["locator"] = entity.locator
        return TargetProjection(target_id, "EvidenceSpan", payload)
    if isinstance(entity, Source):
        if blind_semantics:
            return TargetProjection(target_id, "Source", {
                "revision": entity.meta.revision,
                "provenance_hidden": True,
            })
        payload = {"source_type": entity.source_type, "revision": entity.meta.revision}
        if include_provenance:
            payload.update({"title": entity.title, "locator": entity.locator, "content_hash": entity.content_hash})
        return TargetProjection(target_id, "Source", payload)
    return None


def _normalize_state(state: Mapping[EntityId | str, RegistryEntity]) -> Mapping[EntityId, RegistryEntity]:
    normalized: dict[EntityId, RegistryEntity] = {}
    for key, value in state.items():
        entity_id = key if isinstance(key, EntityId) else EntityId(str(key))
        if getattr(value, "meta", None) is None or value.meta.id != entity_id:
            raise TribunalEvidenceError(f"canonical_state key/entity mismatch:{entity_id}")
        normalized[entity_id] = value
    return MappingProxyType(normalized)


def _validate_state_run_lineage(state: Mapping[EntityId, RegistryEntity], run_id: EntityId) -> None:
    mismatched = sorted(str(entity.meta.id) for entity in state.values() if entity.meta.run_id != run_id)
    if mismatched:
        raise TribunalEvidenceError(f"canonical_state contains cross-run entities:{mismatched[:5]}")


def _fingerprint(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dedupe(values: Sequence[Any]) -> list[Any]:
    return list(dict.fromkeys(values))
