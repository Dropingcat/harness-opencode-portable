"""R3.4 strict reasoning facade.

New R3 callers must not accidentally fall back to the R2 compatibility mode in
which ACTIVE GraphEdge objects can be used without a current RelationAssessment.
"""
from __future__ import annotations

from typing import Sequence

from researcher_core.provenance_dependencies import ProvenanceDependencyBuild, build_knowledge_dependencies
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EvidenceSpan, Source
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.relation_assessment import RelationAssessment
from researcher_core.research_planning_runtime import ResearchTraceLink
from researcher_core.challenge_resolution import ChallengeResolutionAssessment


def build_strict_reasoning_dependencies(
    *,
    sources: Sequence[Source] = (),
    evidence_spans: Sequence[EvidenceSpan] = (),
    graph_edges: Sequence[GraphEdge] = (),
    trace_links: Sequence[ResearchTraceLink] = (),
    resolutions: Sequence[ChallengeResolutionAssessment] = (),
    relation_assessments: Sequence[RelationAssessment] = (),
    id_factory: EntityIdFactory,
    actor: ActorRef,
    run_id: EntityId,
    created_at,
) -> ProvenanceDependencyBuild:
    return build_knowledge_dependencies(
        sources=sources,
        evidence_spans=evidence_spans,
        graph_edges=graph_edges,
        trace_links=trace_links,
        resolutions=resolutions,
        relation_assessments=relation_assessments,
        require_relation_assessment=True,
        id_factory=id_factory,
        actor=actor,
        run_id=run_id,
        created_at=created_at,
    )
