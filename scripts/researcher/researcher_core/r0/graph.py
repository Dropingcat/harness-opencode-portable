"""Minimal graph edge contracts for R0."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import EdgeKind
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId


class GraphEdgeState(StrEnum):
    """Lifecycle state of a semantic relation.

    ACTIVE participates in reasoning. STALE is preserved historically but must
    be revalidated before use as current support. SUPERSEDED and INVALIDATED are
    terminal historical states in R2.3.3.
    """

    ACTIVE = "ACTIVE"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """Authoritative relation between graph entities."""

    meta: EntityMeta
    source_id: EntityId
    target_id: EntityId
    edge_kind: EdgeKind
    attributes: Mapping[str, Any] = field(default_factory=dict)
    state: GraphEdgeState = GraphEdgeState.ACTIVE

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "EDG":
            raise ValueError("edge id must use EDG prefix")
        if self.source_id == self.target_id:
            raise ValueError("self edges are not allowed in R0")
        if not isinstance(self.edge_kind, EdgeKind):
            raise TypeError("edge_kind must be EdgeKind")
        if not isinstance(self.state, GraphEdgeState):
            raise TypeError("state must be GraphEdgeState")
        object.__setattr__(self, "attributes", _deep_freeze(self.attributes))


class InMemoryGraphRepository:
    """Tiny edge store used by bubble tests before SQLite repositories exist."""

    def __init__(self) -> None:
        self._edges: dict[EntityId, GraphEdge] = {}

    def add_edge(self, edge: GraphEdge) -> None:
        if edge.meta.id in self._edges:
            raise ValueError(f"duplicate edge id: {edge.meta.id}")
        self._edges[edge.meta.id] = edge

    def replace_edge(self, edge: GraphEdge, *, expected_revision: int) -> None:
        current = self._edges.get(edge.meta.id)
        if current is None:
            raise KeyError(str(edge.meta.id))
        if current.meta.revision != expected_revision:
            raise ValueError("edge revision does not match expected_revision")
        if edge.meta.revision != expected_revision + 1:
            raise ValueError("replacement edge revision must increment by one")
        self._edges[edge.meta.id] = edge

    def edges_for_source(self, source_id: EntityId) -> tuple[GraphEdge, ...]:
        return tuple(edge for edge in self._edges.values() if edge.source_id == source_id)

    def edge_view(self) -> Mapping[EntityId, GraphEdge]:
        return MappingProxyType(self._edges)
