"""R2.3.1 provenance-to-dependency adapter and SourceCatalog trigger.

This module converts already-authoritative provenance structures into the
``KnowledgeDependency`` records consumed by R2.3.  It is intentionally an
adapter, not another knowledge graph and not a second invalidation reducer.

Current canonical inputs:
* researcher ``Source`` / ``EvidenceSpan``;
* admitted ``GraphEdge`` relations;
* ``ResearchTraceLink`` records emitted by planning/challenge workflows;
* ``ChallengeResolutionAssessment`` evidence/claim references;
* Writer ``SourceCatalog`` update results through an explicit identity binding.

The adapter is deterministic and conservative.  Unknown or ambiguous source
identity fails closed instead of guessing from titles, paths or hashes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from researcher_core.challenge_resolution import ChallengeResolutionAssessment
from researcher_core.invalidation import (
    DependencyImpactAssessment,
    DependencyState,
    DependencyStrength,
    KnowledgeDependency,
    assess_dependency_impact,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta, EvidenceSpan, Source
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.graph import GraphEdge, GraphEdgeState
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.research_planning_runtime import ResearchTraceLink, ResearchTraceRelation
from researcher_core.relation_assessment import RelationAssessment, latest_assessment_by_edge


@dataclass(frozen=True, slots=True)
class SourceIdentityBinding:
    """Explicit bridge between shared-library/catalog identity and Researcher Source."""

    catalog_source_id: str
    researcher_source_id: EntityId
    catalog_sha256: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.catalog_source_id.strip():
            raise ValueError("catalog_source_id is required")
        if self.researcher_source_id.namespace != "SRC":
            raise ValueError("researcher_source_id must use SRC prefix")
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class SourceCatalogSemanticChange:
    """Normalized semantic change emitted by SourceCatalog-facing adapters."""

    catalog_source_id: str
    change_class: str
    semantic_changed: bool
    old_sha256: str | None
    new_sha256: str | None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.catalog_source_id.strip():
            raise ValueError("catalog_source_id is required")
        if self.change_class not in {"UNCHANGED", "BYTE_ONLY", "SEMANTIC", "ADDED"}:
            raise ValueError("unsupported SourceCatalog change_class")
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class ProvenanceDependencyBuild:
    dependencies: tuple[KnowledgeDependency, ...]
    diagnostics: tuple[str, ...]
    source_bindings_used: tuple[SourceIdentityBinding, ...] = ()


class ProvenanceDependencyError(ValueError):
    pass


def source_catalog_change_from_writer(result: Mapping[str, Any]) -> SourceCatalogSemanticChange:
    """Normalize the public ``source_catalog.upsert`` result without importing Writer."""
    if result.get("ok") is not True:
        raise ProvenanceDependencyError("SourceCatalog update is not successful")
    if result.get("schema") != "source_catalog/1.1":
        raise ProvenanceDependencyError("unsupported SourceCatalog result schema")
    if not isinstance(result.get("source_id"), str) or not result["source_id"].strip():
        raise ProvenanceDependencyError("SourceCatalog result requires source_id")
    if not isinstance(result.get("semantic_changed"), bool):
        raise ProvenanceDependencyError("SourceCatalog semantic_changed must be boolean")
    for key in ("old_sha256", "sha256"):
        value = result.get(key)
        if value is not None and (not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{64}", value) is None):
            raise ProvenanceDependencyError(f"SourceCatalog {key} must be a SHA-256 hex digest")
    if result.get("sha256") is None:
        raise ProvenanceDependencyError("SourceCatalog result requires sha256")
    raw_class = str(result.get("change_class") or "").upper()
    # Writer uses change='added' with semantic_changed=False on first admission.
    if str(result.get("change") or "").lower() == "added":
        raw_class = "ADDED"
    semantic_changed = result["semantic_changed"]
    if semantic_changed != (raw_class == "SEMANTIC"):
        raise ProvenanceDependencyError("SourceCatalog change_class/semantic_changed mismatch")
    return SourceCatalogSemanticChange(
        catalog_source_id=result["source_id"],
        change_class=raw_class,
        semantic_changed=semantic_changed,
        old_sha256=result.get("old_sha256"),
        new_sha256=result.get("sha256"),
        metadata={"schema": result.get("schema")},
    )


def resolve_catalog_change(
    change: SourceCatalogSemanticChange,
    bindings: Sequence[SourceIdentityBinding],
) -> tuple[EntityId, ...]:
    """Return changed canonical Source ids for semantic changes only."""
    if not change.semantic_changed or change.change_class != "SEMANTIC":
        return ()
    matches = tuple(x for x in bindings if x.catalog_source_id == change.catalog_source_id)
    if not matches:
        raise ProvenanceDependencyError(
            f"no SourceIdentityBinding for catalog source {change.catalog_source_id!r}"
        )
    researcher_ids = {x.researcher_source_id for x in matches}
    if len(researcher_ids) != 1:
        raise ProvenanceDependencyError(
            f"ambiguous SourceIdentityBinding for catalog source {change.catalog_source_id!r}"
        )
    # A stale binding hash is diagnostic-worthy and unsafe when an old catalog
    # version is accidentally replayed as a current change.
    bound_hashes = {x.catalog_sha256 for x in matches if x.catalog_sha256}
    if bound_hashes and change.old_sha256 and change.old_sha256 not in bound_hashes:
        raise ProvenanceDependencyError("catalog old_sha256 does not match bound Source version")
    return tuple(researcher_ids)


def build_knowledge_dependencies(
    *,
    sources: Sequence[Source] = (),
    evidence_spans: Sequence[EvidenceSpan] = (),
    graph_edges: Sequence[GraphEdge] = (),
    trace_links: Sequence[ResearchTraceLink] = (),
    resolutions: Sequence[ChallengeResolutionAssessment] = (),
    relation_assessments: Sequence[RelationAssessment] = (),
    require_relation_assessment: bool = False,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    run_id: EntityId,
    created_at,
) -> ProvenanceDependencyBuild:
    """Compile canonical provenance into R2.3 dependency records.

    Rules are deliberately small and explainable:
    * Source -> EvidenceSpan is HARD containment.
    * GraphEdge source -> EDG is HARD relation provenance.
    * SUPPORTS/CONTRADICTS EDG -> target is HARD unless edge attributes say
      otherwise; support alternatives share an explicit quorum group.
    * Resolution evidence/claim refs -> RRS are HARD justification links.
    * VALIDATED trace links carrying assessment_id can reconstruct EVD/CLM ->
      RRS justification when a serialized assessment object is unavailable.
    """
    if run_id.namespace != "RUN":
        raise ValueError("run_id must use RUN prefix")
    source_ids = {x.meta.id for x in sources}
    evidence_by_id = {x.meta.id: x for x in evidence_spans}
    diagnostics: list[str] = []
    specs: list[tuple[EntityId, EntityId, str, DependencyStrength, str | None, int, Mapping[str, Any]]] = []

    for evd in evidence_spans:
        if source_ids and evd.source_id not in source_ids:
            diagnostics.append(f"EVIDENCE_SOURCE_NOT_SUPPLIED:{evd.meta.id}:{evd.source_id}")
        specs.append((
            evd.source_id, evd.meta.id, "contains_evidence", DependencyStrength.HARD,
            f"source-evidence:{evd.meta.id}", 1,
            {"provenance_complete": True, "origin": "EvidenceSpan.source_id"},
        ))

    edge_states: dict[tuple[EntityId, EntityId, str], object] = {}
    assessment_by_edge = latest_assessment_by_edge(relation_assessments)
    for edge in graph_edges:
        if edge.state in {GraphEdgeState.SUPERSEDED, GraphEdgeState.INVALIDATED}:
            diagnostics.append(f"TERMINAL_EDGE_EXCLUDED:{edge.meta.id}:{edge.state.value}")
            continue
        assessment = assessment_by_edge.get(edge.meta.id)
        assessment_current = assessment is not None and assessment.assessed_edge_revision == edge.meta.revision
        if require_relation_assessment:
            if not assessment_current:
                diagnostics.append(f"UNASSESSED_EDGE_SEMANTIC_USE_EXCLUDED:{edge.meta.id}")
            elif not assessment.reasoning_eligible:
                diagnostics.append(f"BLOCKED_EDGE_SEMANTIC_USE_EXCLUDED:{edge.meta.id}:{assessment.verdict.value}")
        strength = _edge_strength(edge)
        group_key = _edge_group_key(edge)
        min_active = int(edge.attributes.get("min_active_in_group", 1) or 1)
        complete = edge.attributes.get("provenance_complete", True) is not False
        dep_state = DependencyState.ACTIVE if edge.state == GraphEdgeState.ACTIVE else DependencyState.STALE
        edge_states[(edge.source_id, edge.meta.id, f"edge-source:{edge.edge_kind.value}")] = dep_state
        edge_states[(edge.meta.id, edge.target_id, edge.edge_kind.value)] = dep_state
        specs.append((
            edge.source_id, edge.meta.id, f"edge-source:{edge.edge_kind.value}",
            DependencyStrength.HARD, f"edge:{edge.meta.id}", 1,
            {"provenance_complete": complete, "origin": "GraphEdge.source_id", "edge_state": edge.state.value},
        ))
        semantic_use_allowed = (not require_relation_assessment) or (assessment_current and assessment.reasoning_eligible)
        if semantic_use_allowed:
            specs.append((
                edge.meta.id, edge.target_id, edge.edge_kind.value, strength,
                group_key, min_active,
                {
                    "provenance_complete": complete,
                    "origin": "GraphEdge",
                    "edge_id": str(edge.meta.id),
                    "edge_state": edge.state.value,
                    "relation_assessment_id": str(assessment.meta.id) if assessment_current else None,
                    "relation_assessment_verdict": assessment.verdict.value if assessment_current else None,
                    "critical": bool(edge.attributes.get("critical", False)),
                    "scope_overlap": edge.attributes.get("scope_overlap", True),
                },
            ))

    known_resolution_ids = {x.meta.id for x in resolutions}
    for resolution in resolutions:
        quorum = int(resolution.metadata.get("evidence_quorum", 1) or 1)
        group = f"resolution-evidence:{resolution.meta.id}"
        for evd in resolution.evidence_refs:
            specs.append((
                evd, resolution.meta.id, "justifies_resolution", DependencyStrength.HARD,
                group, quorum,
                {"provenance_complete": True, "origin": "ChallengeResolutionAssessment.evidence_refs"},
            ))
        for claim in resolution.claim_refs:
            specs.append((
                claim, resolution.meta.id, "claim_context_for_resolution", DependencyStrength.CONTEXTUAL,
                f"resolution-claims:{resolution.meta.id}", 1,
                {
                    "provenance_complete": True,
                    "origin": "ChallengeResolutionAssessment.claim_refs",
                    "scope_overlap": resolution.metadata.get("scope_overlap", True),
                },
            ))

    for link in trace_links:
        assessment_raw = link.metadata.get("assessment_id")
        if not assessment_raw or link.relation != ResearchTraceRelation.VALIDATED:
            continue
        try:
            assessment_id = EntityId(str(assessment_raw))
        except Exception:
            diagnostics.append(f"INVALID_TRACE_ASSESSMENT_ID:{link.id}")
            continue
        if assessment_id.namespace != "RRS":
            diagnostics.append(f"TRACE_ASSESSMENT_NOT_RRS:{link.id}")
            continue
        if assessment_id in known_resolution_ids:
            continue
        if link.target_id.namespace not in {"EVD", "CLM"}:
            continue
        specs.append((
            link.target_id, assessment_id,
            "trace_validates_resolution",
            DependencyStrength.HARD if link.target_id.namespace == "EVD" else DependencyStrength.CONTEXTUAL,
            f"resolution-trace:{assessment_id}", 1,
            {
                "provenance_complete": True,
                "origin": "ResearchTraceLink",
                "trace_link_id": str(link.id),
                "scope_overlap": link.metadata.get("scope_overlap", True),
            },
        ))

    # Deterministic de-duplication by semantic dependency identity.  The first
    # canonical observation wins; duplicate provenance is recorded as a
    # diagnostic instead of creating parallel KDP records that alter quorum.
    seen: set[tuple[Any, ...]] = set()
    dependencies: list[KnowledgeDependency] = []
    for source_id, target_id, relation, strength, group_key, min_active, metadata in specs:
        key = (source_id, target_id, relation, strength, group_key, min_active)
        if key in seen:
            diagnostics.append(f"DUPLICATE_DEPENDENCY_COLLAPSED:{source_id}:{target_id}:{relation}")
            continue
        seen.add(key)
        dependencies.append(KnowledgeDependency(
            meta=EntityMeta(
                id=id_factory.new("KDP"), schema_version="knowledge-dependency/1.0",
                revision=1, run_id=run_id, created_at=created_at, created_by=actor,
            ),
            source_id=source_id, target_id=target_id, relation=relation,
            strength=strength, group_key=group_key, min_active_in_group=min_active,
            state=edge_states.get((source_id, target_id, relation), DependencyState.ACTIVE),
            metadata=metadata,
        ))
    return ProvenanceDependencyBuild(tuple(dependencies), tuple(diagnostics))


def assess_source_catalog_change(
    *,
    catalog_result: Mapping[str, Any],
    bindings: Sequence[SourceIdentityBinding],
    dependencies: Sequence[KnowledgeDependency],
    target_resolution_id: EntityId | None,
    impact_meta: EntityMeta,
    max_nodes: int = 128,
) -> DependencyImpactAssessment:
    """SourceCatalog result -> canonical changed Source -> R2.3 impact."""
    change = source_catalog_change_from_writer(catalog_result)
    changed = resolve_catalog_change(change, bindings)
    return assess_dependency_impact(
        changed_entity_ids=changed,
        dependencies=dependencies,
        target_resolution_id=target_resolution_id,
        meta=impact_meta,
        max_nodes=max_nodes,
    )


def _edge_strength(edge: GraphEdge) -> DependencyStrength:
    raw = str(edge.attributes.get("dependency_strength") or "").upper()
    if raw in {x.value for x in DependencyStrength}:
        return DependencyStrength(raw)
    # Evidence/derivation relations are structural; contextual relations remain
    # non-destructive unless explicit scope overlap exists.
    if edge.edge_kind.value in {"supports", "contradicts", "depends_on", "derived_from", "quantifies"}:
        return DependencyStrength.HARD
    return DependencyStrength.SOFT


def _edge_group_key(edge: GraphEdge) -> str:
    custom = edge.attributes.get("group_key")
    if custom:
        return str(custom)
    if edge.edge_kind.value in {"supports", "contradicts"}:
        return f"claim-evidence:{edge.target_id}:{edge.edge_kind.value}"
    return f"edge-target:{edge.target_id}:{edge.edge_kind.value}"


def reopen_from_source_catalog_change(
    *,
    catalog_result: Mapping[str, Any],
    bindings: Sequence[SourceIdentityBinding],
    dependencies: Sequence[KnowledgeDependency],
    dom,
    challenge,
    source_entity,
    resolution: ChallengeResolutionAssessment,
    challenge_card_id: EntityId,
    prior_iterations,
    patch_id: EntityId,
    impact_meta: EntityMeta,
    actor: ActorRef,
    id_factory: EntityIdFactory,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
    max_nodes: int = 128,
):
    """End-to-end shared SourceCatalog change -> selective historical reopen.

    The function remains orchestration glue: provenance compilation/identity,
    impact computation and the R2.3 reducer keep their separate authorities.
    """
    from researcher_core.invalidation import reopen_from_impact

    impact = assess_source_catalog_change(
        catalog_result=catalog_result,
        bindings=bindings,
        dependencies=dependencies,
        target_resolution_id=resolution.meta.id,
        impact_meta=impact_meta,
        max_nodes=max_nodes,
    )
    return reopen_from_impact(
        dom=dom,
        challenge=challenge,
        source_entity=source_entity,
        resolution=resolution,
        impact=impact,
        challenge_card_id=challenge_card_id,
        prior_iterations=prior_iterations,
        patch_id=patch_id,
        actor=actor,
        id_factory=id_factory,
        timestamp=timestamp,
        causation_id=causation_id,
        correlation_id=correlation_id,
    )
