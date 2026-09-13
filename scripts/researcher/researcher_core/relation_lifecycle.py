"""R2.3.3 lifecycle for versioned graph relations.

GraphEdge is an information object in its own right.  Invalidation changes the
relation state, not the truth state of its endpoint entities.  All transitions
are optimistic-concurrency checked and emit replayable state-change events.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from researcher_core.invalidation import DependencyImpactAssessment
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import EventEnvelope, ReasonCode
from researcher_core.r0.graph import GraphEdge, GraphEdgeState
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r0.projections import entity_to_event_record


_ALLOWED_TRANSITIONS = frozenset({
    (GraphEdgeState.ACTIVE, GraphEdgeState.STALE),
    (GraphEdgeState.STALE, GraphEdgeState.ACTIVE),
    (GraphEdgeState.STALE, GraphEdgeState.SUPERSEDED),
    (GraphEdgeState.ACTIVE, GraphEdgeState.INVALIDATED),
    (GraphEdgeState.STALE, GraphEdgeState.INVALIDATED),
})


class RelationLifecycleError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RelationTransitionRequest:
    edge_id: EntityId
    expected_revision: int
    requested_state: GraphEdgeState
    reason_codes: tuple[ReasonCode, ...]

    def __post_init__(self) -> None:
        if self.edge_id.namespace != "EDG":
            raise ValueError("edge_id must use EDG prefix")
        if self.expected_revision < 1:
            raise ValueError("expected_revision must be positive")
        if not self.reason_codes:
            raise ValueError("reason_codes are required")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))


@dataclass(frozen=True, slots=True)
class RelationTransitionResult:
    edge: GraphEdge
    event: EventEnvelope


@dataclass(frozen=True, slots=True)
class RelationImpactProjection:
    updated_edges: tuple[GraphEdge, ...]
    unchanged_edge_ids: tuple[EntityId, ...]
    missing_edge_ids: tuple[EntityId, ...]
    events: tuple[EventEnvelope, ...]


def transition_relation_state(
    edge: GraphEdge,
    request: RelationTransitionRequest,
    *,
    actor: ActorRef,
    event_id: EntityId,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
) -> RelationTransitionResult:
    if edge.meta.id != request.edge_id:
        raise RelationLifecycleError("transition target does not match edge id")
    if edge.meta.revision != request.expected_revision:
        raise RelationLifecycleError("edge revision does not match expected_revision")
    if (edge.state, request.requested_state) not in _ALLOWED_TRANSITIONS:
        raise RelationLifecycleError(
            f"cannot transition edge from {edge.state.value} to {request.requested_state.value}"
        )
    next_meta = EntityMeta(
        id=edge.meta.id,
        schema_version=edge.meta.schema_version,
        revision=edge.meta.revision + 1,
        run_id=edge.meta.run_id,
        created_at=edge.meta.created_at,
        created_by=edge.meta.created_by,
    )
    updated = replace(edge, meta=next_meta, state=request.requested_state)
    event = EventEnvelope(
        event_id=event_id,
        event_type="EDGE_STATE_CHANGED",
        aggregate_id=edge.meta.id,
        aggregate_revision=next_meta.revision,
        run_id=edge.meta.run_id,
        actor=actor.actor_id,
        timestamp=timestamp,
        causation_id=causation_id,
        correlation_id=correlation_id,
        schema_version="graph-edge-event/1.0",
        reason_codes=request.reason_codes,
        payload={
            **entity_to_event_record(updated),
            "from_state": edge.state.value,
            "to_state": updated.state.value,
        },
    )
    return RelationTransitionResult(updated, event)


def project_stale_relations_from_impact(
    *,
    impact: DependencyImpactAssessment,
    graph_edges: Sequence[GraphEdge],
    expected_revisions: Mapping[EntityId, int],
    actor: ActorRef,
    id_factory: EntityIdFactory,
    timestamp,
    causation_id: EntityId,
    correlation_id: EntityId,
    fail_on_missing: bool = True,
) -> RelationImpactProjection:
    """Project DIA.stale_relation_ids onto canonical GraphEdge lifecycle.

    Endpoint entities are intentionally untouched.  A stale relation is a stale
    assertion about how two entities are connected, not proof that either
    endpoint is false.
    """
    by_id = {edge.meta.id: edge for edge in graph_edges}
    updated: list[GraphEdge] = []
    unchanged: list[EntityId] = []
    missing: list[EntityId] = []
    events: list[EventEnvelope] = []
    for edge_id in impact.stale_relation_ids:
        edge = by_id.get(edge_id)
        if edge is None:
            missing.append(edge_id)
            continue
        expected = expected_revisions.get(edge_id)
        if expected is None:
            raise RelationLifecycleError(f"missing expected revision for {edge_id}")
        if edge.state == GraphEdgeState.STALE:
            if edge.meta.revision != expected:
                raise RelationLifecycleError("edge revision does not match expected_revision")
            unchanged.append(edge_id)
            continue
        if edge.state != GraphEdgeState.ACTIVE:
            unchanged.append(edge_id)
            continue
        result = transition_relation_state(
            edge,
            RelationTransitionRequest(
                edge_id=edge_id,
                expected_revision=expected,
                requested_state=GraphEdgeState.STALE,
                reason_codes=(ReasonCode("RELATION_PROVENANCE_STALE"),),
            ),
            actor=actor,
            event_id=id_factory.new("EVT"),
            timestamp=timestamp,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        updated.append(result.edge)
        events.append(result.event)
    if missing and fail_on_missing:
        raise RelationLifecycleError(
            "impact references relation ids not present in canonical graph: " + ",".join(map(str, missing))
        )
    return RelationImpactProjection(tuple(updated), tuple(unchanged), tuple(missing), tuple(events))
