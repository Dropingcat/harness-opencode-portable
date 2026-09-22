"""Canonical R4.4 branching argument relations and graph projection.

ArgumentArtifact remains the semantic node.  This module adds versioned,
historical relations between those nodes.  Relations describe the dialectic
shape only; they do not mutate Claim/GraphEdge truth and are not a vote model.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence

from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId
from researcher_core.tribunal_composition import AssessmentNeedRef
from researcher_core.tribunal_inquiry import ArgumentArtifact, ArgumentPosition


class TribunalArgumentGraphError(RuntimeError):
    pass


class ArgumentRelationKind(StrEnum):
    ATTACKS = "ATTACKS"
    UNDERCUTS = "UNDERCUTS"
    REPLIES_TO = "REPLIES_TO"
    DEFENDS = "DEFENDS"


class ArgumentRelationState(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True, slots=True)
class ArgumentRelation:
    meta: EntityMeta
    kind: ArgumentRelationKind
    source_argument_id: EntityId
    target_argument_id: EntityId
    need_refs: tuple[AssessmentNeedRef, ...]
    material: bool = False
    state: ArgumentRelationState = ArgumentRelationState.ACTIVE
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "ARL":
            raise ValueError("ArgumentRelation id must use ARL prefix")
        if self.source_argument_id.namespace != "ARG" or self.target_argument_id.namespace != "ARG":
            raise ValueError("ArgumentRelation endpoints must use ARG prefix")
        if self.source_argument_id == self.target_argument_id:
            raise ValueError("ArgumentRelation cannot self-reference")
        if not self.need_refs:
            raise ValueError("ArgumentRelation requires AssessmentNeedRef coverage")
        object.__setattr__(self, "need_refs", tuple(dict.fromkeys(self.need_refs)))
        object.__setattr__(self, "reason_codes", tuple(dict.fromkeys(x for x in self.reason_codes if x)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ArgumentGraphProjection:
    meta: EntityMeta
    argument_ids: tuple[EntityId, ...]
    relations: tuple[ArgumentRelation, ...]
    root_argument_ids: tuple[EntityId, ...]
    branch_head_ids: tuple[EntityId, ...]
    graph_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "AGP":
            raise ValueError("ArgumentGraphProjection id must use AGP prefix")
        if not self.argument_ids:
            raise ValueError("ArgumentGraphProjection requires at least one argument")
        object.__setattr__(self, "argument_ids", tuple(dict.fromkeys(self.argument_ids)))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "root_argument_ids", tuple(dict.fromkeys(self.root_argument_ids)))
        object.__setattr__(self, "branch_head_ids", tuple(dict.fromkeys(self.branch_head_ids)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


def build_argument_graph(
    *,
    meta: EntityMeta,
    arguments: Sequence[ArgumentArtifact],
    relations: Sequence[ArgumentRelation],
) -> ArgumentGraphProjection:
    if meta.id.namespace != "AGP":
        raise TribunalArgumentGraphError("graph meta must use AGP prefix")
    argument_map = _argument_map(arguments)
    if any(arg.meta.run_id != meta.run_id for arg in arguments):
        raise TribunalArgumentGraphError("argument graph cannot mix run lineage")

    rels = tuple(relations)
    seen_rel_ids: set[EntityId] = set()
    seen_semantic_edges: set[tuple[str, str, str]] = set()
    for relation in rels:
        if relation.meta.run_id != meta.run_id:
            raise TribunalArgumentGraphError("argument relation run mismatch")
        if relation.meta.id in seen_rel_ids:
            raise TribunalArgumentGraphError("duplicate ArgumentRelation id")
        seen_rel_ids.add(relation.meta.id)
        if relation.source_argument_id not in argument_map or relation.target_argument_id not in argument_map:
            raise TribunalArgumentGraphError("argument relation endpoint missing from graph")
        key = (relation.kind.value, str(relation.source_argument_id), str(relation.target_argument_id))
        if key in seen_semantic_edges and relation.state is ArgumentRelationState.ACTIVE:
            raise TribunalArgumentGraphError("duplicate active semantic argument relation")
        seen_semantic_edges.add(key)
        _validate_relation_semantics(relation, argument_map)

    active = tuple(x for x in rels if x.state is ArgumentRelationState.ACTIVE)
    _assert_acyclic(argument_map, active)
    source_ids = {x.source_argument_id for x in active}
    target_ids = {x.target_argument_id for x in active}
    roots = tuple(x for x in argument_map if x not in source_ids)
    heads = tuple(x for x in argument_map if x not in target_ids)
    if not active:
        roots = tuple(argument_map)
        heads = tuple(argument_map)

    fingerprint = _graph_fingerprint(meta.id, meta.revision, tuple(argument_map), rels)
    return ArgumentGraphProjection(
        meta=meta,
        argument_ids=tuple(argument_map),
        relations=rels,
        root_argument_ids=roots,
        branch_head_ids=heads,
        graph_fingerprint=fingerprint,
        metadata={
            "authority_boundary": "argument topology only; no Claim/GraphEdge truth mutation",
            "orientation": "newer/source argument -> challenged/replied/defended target argument",
        },
    )



def validate_argument_graph_integrity(
    graph: ArgumentGraphProjection,
    arguments: Sequence[ArgumentArtifact],
) -> None:
    rebuilt = build_argument_graph(meta=graph.meta, arguments=arguments, relations=graph.relations)
    if rebuilt.graph_fingerprint != graph.graph_fingerprint:
        raise TribunalArgumentGraphError("ArgumentGraphProjection fingerprint mismatch")
    if rebuilt.argument_ids != graph.argument_ids:
        raise TribunalArgumentGraphError("ArgumentGraphProjection argument set mismatch")
    if rebuilt.root_argument_ids != graph.root_argument_ids or rebuilt.branch_head_ids != graph.branch_head_ids:
        raise TribunalArgumentGraphError("ArgumentGraphProjection topology mismatch")


def append_argument_branch(
    *,
    graph: ArgumentGraphProjection,
    new_meta: EntityMeta,
    arguments: Sequence[ArgumentArtifact],
    new_relations: Sequence[ArgumentRelation],
) -> ArgumentGraphProjection:
    if new_meta.id != graph.meta.id or new_meta.revision != graph.meta.revision + 1:
        raise TribunalArgumentGraphError("graph revision must preserve id and increment exactly once")
    if new_meta.run_id != graph.meta.run_id:
        raise TribunalArgumentGraphError("graph revision run mismatch")
    existing_ids = set(graph.argument_ids)
    merged_arguments = list(arguments)
    provided = {x.meta.id for x in merged_arguments}
    if not existing_ids.issubset(provided):
        raise TribunalArgumentGraphError("graph revision requires all prior argument nodes")
    return build_argument_graph(
        meta=new_meta,
        arguments=merged_arguments,
        relations=(*graph.relations, *tuple(new_relations)),
    )


def relation_targets(graph: ArgumentGraphProjection, argument_id: EntityId) -> tuple[ArgumentRelation, ...]:
    return tuple(
        x for x in graph.relations
        if x.state is ArgumentRelationState.ACTIVE and x.target_argument_id == argument_id
    )


def relation_sources(graph: ArgumentGraphProjection, argument_id: EntityId) -> tuple[ArgumentRelation, ...]:
    return tuple(
        x for x in graph.relations
        if x.state is ArgumentRelationState.ACTIVE and x.source_argument_id == argument_id
    )


def argument_relation_to_dict(relation: ArgumentRelation) -> dict[str, Any]:
    return {
        "schema_version": "argument-relation/1.0",
        "meta": _meta_to_dict(relation.meta),
        "kind": relation.kind.value,
        "source_argument_id": str(relation.source_argument_id),
        "target_argument_id": str(relation.target_argument_id),
        "need_refs": [{"key": x.key, "ordinal": x.ordinal} for x in relation.need_refs],
        "material": relation.material,
        "state": relation.state.value,
        "reason_codes": list(relation.reason_codes),
        "metadata": dict(relation.metadata),
    }


def argument_graph_to_dict(graph: ArgumentGraphProjection) -> dict[str, Any]:
    return {
        "schema_version": "argument-graph-projection/1.0",
        "meta": _meta_to_dict(graph.meta),
        "argument_ids": [str(x) for x in graph.argument_ids],
        "relations": [argument_relation_to_dict(x) for x in graph.relations],
        "root_argument_ids": [str(x) for x in graph.root_argument_ids],
        "branch_head_ids": [str(x) for x in graph.branch_head_ids],
        "graph_fingerprint": graph.graph_fingerprint,
        "metadata": dict(graph.metadata),
    }


def _argument_map(arguments: Sequence[ArgumentArtifact]) -> dict[EntityId, ArgumentArtifact]:
    out: dict[EntityId, ArgumentArtifact] = {}
    for argument in arguments:
        if argument.meta.id in out:
            raise TribunalArgumentGraphError("duplicate ArgumentArtifact id")
        out[argument.meta.id] = argument
    if not out:
        raise TribunalArgumentGraphError("argument graph requires arguments")
    return out


def _validate_relation_semantics(
    relation: ArgumentRelation,
    arguments: Mapping[EntityId, ArgumentArtifact],
) -> None:
    source = arguments[relation.source_argument_id]
    target = arguments[relation.target_argument_id]
    if source.meta.run_id != target.meta.run_id or source.meta.run_id != relation.meta.run_id:
        raise TribunalArgumentGraphError("argument relation crosses run lineage")
    if not set(relation.need_refs).intersection(source.assigned_need_refs):
        raise TribunalArgumentGraphError("argument relation need refs are outside source assignment")
    if not set(relation.need_refs).intersection(target.assigned_need_refs):
        raise TribunalArgumentGraphError("argument relation need refs are outside target assignment")
    if relation.kind in {ArgumentRelationKind.ATTACKS, ArgumentRelationKind.UNDERCUTS}:
        if source.position is not ArgumentPosition.CHALLENGE:
            raise TribunalArgumentGraphError("attack/undercut source must have CHALLENGE position")
    if relation.kind is ArgumentRelationKind.DEFENDS:
        if source.position not in {ArgumentPosition.SUPPORT, ArgumentPosition.QUALIFY}:
            raise TribunalArgumentGraphError("defense source must SUPPORT or QUALIFY")
        if target.position is ArgumentPosition.OPEN:
            raise TribunalArgumentGraphError("cannot DEFEND an OPEN target argument")


def _assert_acyclic(
    arguments: Mapping[EntityId, ArgumentArtifact],
    relations: Sequence[ArgumentRelation],
) -> None:
    adjacency: dict[EntityId, list[EntityId]] = {x: [] for x in arguments}
    for relation in relations:
        adjacency[relation.source_argument_id].append(relation.target_argument_id)
    visiting: set[EntityId] = set()
    visited: set[EntityId] = set()

    def walk(node: EntityId) -> None:
        if node in visiting:
            raise TribunalArgumentGraphError("argument relation cycle detected")
        if node in visited:
            return
        visiting.add(node)
        for target in adjacency[node]:
            walk(target)
        visiting.remove(node)
        visited.add(node)

    for node in arguments:
        walk(node)


def _graph_fingerprint(
    graph_id: EntityId,
    revision: int,
    argument_ids: Sequence[EntityId],
    relations: Sequence[ArgumentRelation],
) -> str:
    payload = {
        "graph_id": str(graph_id),
        "revision": revision,
        "arguments": [str(x) for x in argument_ids],
        "relations": [
            {
                "id": str(x.meta.id),
                "revision": x.meta.revision,
                "kind": x.kind.value,
                "source": str(x.source_argument_id),
                "target": str(x.target_argument_id),
                "needs": [(n.key, n.ordinal) for n in x.need_refs],
                "material": x.material,
                "state": x.state.value,
            }
            for x in relations
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _meta_to_dict(meta: EntityMeta) -> dict[str, Any]:
    return {
        "id": str(meta.id),
        "schema_version": meta.schema_version,
        "revision": meta.revision,
        "run_id": str(meta.run_id),
        "created_at": meta.created_at.isoformat(),
        "created_by": {"kind": meta.created_by.actor_type, "id": meta.created_by.actor_id},
    }
