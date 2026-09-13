"""R3.2 explicit post-admission semantic linking.

Execution admission proves that typed entities may enter the canonical registry.
This module is a separate control-plane step that resolves adapter-declared
relations onto canonical ids and admits GraphEdge entities. Co-occurrence never
creates a semantic relation implicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence

from researcher_core.execution_admission import ExecutionAdmissionProposal, ExecutionAdmissionReceipt
from researcher_core.r0.commands import ActorRef, CommandEnvelope, CommandResult
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.enums import CommitPolicy, EdgeKind
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.graph import GraphEdge
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r0.registry import InMemoryClaimRegistry, ProposalBatch
from researcher_core.r0.sqlite_store import SqliteUnitOfWork
from researcher_core.research_planning_runtime import ResearchTraceLink, ResearchTraceRelation


class ExecutionLinkingError(ValueError):
    pass


class EndpointRefKind(StrEnum):
    TEMP = "TEMP"
    CANONICAL = "CANONICAL"


@dataclass(frozen=True, slots=True)
class RelationEndpointRef:
    kind: EndpointRefKind
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("relation endpoint value is required")


@dataclass(frozen=True, slots=True)
class AdmissionIdentityMap:
    meta: EntityMeta
    admission_proposal_id: EntityId
    admission_receipt_id: EntityId
    temp_to_canonical: Mapping[str, EntityId]
    canonical_ids: tuple[EntityId, ...]

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "AIM":
            raise ValueError("identity map id must use AIM prefix")
        if self.admission_proposal_id.namespace != "EAP" or self.admission_receipt_id.namespace != "EAR":
            raise ValueError("identity map must reference EAP/EAR")
        if len(set(self.temp_to_canonical)) != len(self.temp_to_canonical):
            raise ValueError("duplicate temp ids are not allowed")
        object.__setattr__(self, "temp_to_canonical", _deep_freeze(dict(self.temp_to_canonical)))
        object.__setattr__(self, "canonical_ids", tuple(self.canonical_ids))


@dataclass(frozen=True, slots=True)
class SemanticRelationProposal:
    meta: EntityMeta
    admission_proposal_id: EntityId
    source: RelationEndpointRef
    target: RelationEndpointRef
    edge_kind: EdgeKind
    rationale: str
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "SRP":
            raise ValueError("semantic relation proposal id must use SRP prefix")
        if self.admission_proposal_id.namespace != "EAP":
            raise ValueError("semantic relation proposal must reference EAP")
        if not isinstance(self.edge_kind, EdgeKind):
            raise TypeError("edge_kind must be EdgeKind")
        if not self.rationale:
            raise ValueError("semantic relation rationale is required")
        object.__setattr__(self, "provenance", _deep_freeze(dict(self.provenance)))


@dataclass(frozen=True, slots=True)
class SemanticLinkReceipt:
    meta: EntityMeta
    admission_proposal_id: EntityId
    identity_map_id: EntityId
    relation_proposal_ids: tuple[EntityId, ...]
    admitted_edge_ids: tuple[EntityId, ...]
    trace_link_ids: tuple[EntityId, ...]

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "SLR":
            raise ValueError("semantic link receipt id must use SLR prefix")
        object.__setattr__(self, "relation_proposal_ids", tuple(self.relation_proposal_ids))
        object.__setattr__(self, "admitted_edge_ids", tuple(self.admitted_edge_ids))
        object.__setattr__(self, "trace_link_ids", tuple(self.trace_link_ids))


def build_admission_identity_map(*, proposal: ExecutionAdmissionProposal, receipt: ExecutionAdmissionReceipt,
                                 registry: InMemoryClaimRegistry, id_factory: EntityIdFactory,
                                 actor: ActorRef, created_at: datetime) -> AdmissionIdentityMap:
    if receipt.proposal_id != proposal.meta.id:
        raise ExecutionLinkingError("receipt does not belong to admission proposal")
    if tuple(receipt.admitted_ids) != tuple(x for x in receipt.admitted_ids):
        raise ExecutionLinkingError("invalid admitted id sequence")
    state_ids = set(registry.state)
    if any(x not in state_ids for x in receipt.admitted_ids):
        raise ExecutionLinkingError("receipt references entities absent from canonical registry")

    claims = [x for x in receipt.admitted_ids if x.namespace == "CLM"]
    quantities = [x for x in receipt.admitted_ids if x.namespace == "QTY"]
    if len(claims) != len(proposal.batch.claims) or len(quantities) != len(proposal.batch.quantities):
        raise ExecutionLinkingError("admission identity cardinality mismatch")
    temp_map: dict[str, EntityId] = {}
    for p, entity_id in zip(proposal.batch.claims, claims, strict=True):
        if p.temp_id in temp_map:
            raise ExecutionLinkingError("duplicate proposal temp id")
        temp_map[p.temp_id] = entity_id
    for p, entity_id in zip(proposal.batch.quantities, quantities, strict=True):
        if p.temp_id in temp_map:
            raise ExecutionLinkingError("duplicate proposal temp id")
        temp_map[p.temp_id] = entity_id
    return AdmissionIdentityMap(
        meta=EntityMeta(id_factory.new("AIM"), "admission-identity-map/1.0", 1, proposal.meta.run_id, created_at, actor),
        admission_proposal_id=proposal.meta.id,
        admission_receipt_id=receipt.meta.id,
        temp_to_canonical=temp_map,
        canonical_ids=receipt.admitted_ids,
    )


def _resolve(ref: RelationEndpointRef, identity: AdmissionIdentityMap) -> EntityId:
    if ref.kind == EndpointRefKind.TEMP:
        entity_id = identity.temp_to_canonical.get(ref.value)
        if entity_id is None:
            raise ExecutionLinkingError(f"unknown temp endpoint: {ref.value}")
        return entity_id
    try:
        entity_id = EntityId(ref.value)
    except ValueError as exc:
        raise ExecutionLinkingError("invalid canonical endpoint id") from exc
    if entity_id not in identity.canonical_ids:
        raise ExecutionLinkingError("canonical endpoint is outside this admission receipt")
    return entity_id


def _validate_relation_shape(kind: EdgeKind, source_id: EntityId, target_id: EntityId) -> None:
    allowed = {
        EdgeKind.SUPPORTS: {("EVD", "CLM")},
        EdgeKind.CONTRADICTS: {("EVD", "CLM")},
        EdgeKind.QUANTIFIES: {("QTY", "CLM")},
        EdgeKind.DERIVED_FROM: {("CLM", "CLM")},
    }
    if kind not in allowed:
        raise ExecutionLinkingError(f"edge kind {kind.value} is not enabled for R3.2 execution linking")
    if (source_id.namespace, target_id.namespace) not in allowed[kind]:
        raise ExecutionLinkingError(f"invalid endpoint namespaces for {kind.value}: {source_id.namespace}->{target_id.namespace}")


def admit_semantic_relations(*, proposal: ExecutionAdmissionProposal, identity: AdmissionIdentityMap,
                             relation_proposals: Sequence[SemanticRelationProposal], registry: InMemoryClaimRegistry,
                             id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime,
                             causation_id: EntityId, correlation_id: EntityId) -> tuple[SemanticLinkReceipt, CommandResult, tuple[ResearchTraceLink, ...]]:
    if identity.admission_proposal_id != proposal.meta.id:
        raise ExecutionLinkingError("identity map belongs to another admission proposal")
    if not relation_proposals:
        raise ExecutionLinkingError("semantic linking requires at least one explicit relation proposal")
    edges: list[GraphEdge] = []
    seen: set[tuple[EntityId, EntityId, EdgeKind]] = set()
    existing = {(x.source_id, x.target_id, x.edge_kind) for x in registry.state.values() if isinstance(x, GraphEdge)}
    for rp in relation_proposals:
        if rp.admission_proposal_id != proposal.meta.id or rp.meta.run_id != proposal.meta.run_id:
            raise ExecutionLinkingError("relation proposal lineage mismatch")
        source_id, target_id = _resolve(rp.source, identity), _resolve(rp.target, identity)
        _validate_relation_shape(rp.edge_kind, source_id, target_id)
        key = (source_id, target_id, rp.edge_kind)
        if key in seen:
            raise ExecutionLinkingError("duplicate semantic relation proposal")
        if key in existing:
            raise ExecutionLinkingError("semantic relation already exists in canonical registry")
        seen.add(key)
        edges.append(GraphEdge(
            meta=EntityMeta(id_factory.new("EDG"), "graph-edge/1.0", 1, proposal.meta.run_id, created_at, actor),
            source_id=source_id, target_id=target_id, edge_kind=rp.edge_kind,
            attributes={"relation_proposal_id": str(rp.meta.id), "rationale": rp.rationale,
                        "admission_proposal_id": str(proposal.meta.id), **dict(rp.provenance)},
        ))
    command_id = id_factory.new("OPR")
    command = CommandEnvelope(
        command_id=command_id, command_type="ADMIT_EXECUTION_RELATIONS", run_id=proposal.meta.run_id, actor=actor,
        idempotency_key="execution-linking:" + str(proposal.meta.id) + ":" + str(identity.meta.id) + ":" + ",".join(str(x.meta.id) for x in relation_proposals), expected_revisions={},
        causation_id=causation_id, correlation_id=correlation_id,
        payload={"admission_proposal_id": str(proposal.meta.id), "identity_map_id": str(identity.meta.id)},
    )
    result = registry.admit(ProposalBatch((), (), edges=tuple(edges)), CommitPolicy.ALL_OR_NOTHING, command)
    links = tuple(ResearchTraceLink(
        id=id_factory.new("RTL"), research_card_id=proposal.source_card_id, target_id=edge_id,
        relation=ResearchTraceRelation.PRODUCED, run_id=proposal.meta.run_id, created_at=created_at, created_by=actor,
        metadata={"admission_proposal_id": str(proposal.meta.id), "identity_map_id": str(identity.meta.id), "semantic_link": True},
    ) for edge_id in result.accepted_ids)
    receipt = SemanticLinkReceipt(
        meta=EntityMeta(id_factory.new("SLR"), "semantic-link-receipt/1.0", 1, proposal.meta.run_id, created_at, actor),
        admission_proposal_id=proposal.meta.id, identity_map_id=identity.meta.id,
        relation_proposal_ids=tuple(x.meta.id for x in relation_proposals), admitted_edge_ids=result.accepted_ids,
        trace_link_ids=tuple(x.id for x in links),
    )
    return receipt, result, links


def admission_identity_map_to_dict(identity: AdmissionIdentityMap) -> dict[str, Any]:
    return {
        "schema_version": "admission-identity-map/1.0",
        "id": str(identity.meta.id), "run_id": str(identity.meta.run_id),
        "admission_proposal_id": str(identity.admission_proposal_id),
        "admission_receipt_id": str(identity.admission_receipt_id),
        "temp_to_canonical": {k: str(v) for k, v in identity.temp_to_canonical.items()},
        "canonical_ids": [str(x) for x in identity.canonical_ids],
    }

def semantic_relation_proposal_to_dict(proposal: SemanticRelationProposal) -> dict[str, Any]:
    return {
        "schema_version": "semantic-relation-proposal/1.0",
        "id": str(proposal.meta.id), "run_id": str(proposal.meta.run_id),
        "admission_proposal_id": str(proposal.admission_proposal_id),
        "source": {"kind": proposal.source.kind.value, "value": proposal.source.value},
        "target": {"kind": proposal.target.kind.value, "value": proposal.target.value},
        "edge_kind": proposal.edge_kind.value, "rationale": proposal.rationale,
        "provenance": dict(proposal.provenance),
    }

def semantic_link_receipt_to_dict(receipt: SemanticLinkReceipt) -> dict[str, Any]:
    return {
        "schema_version": "semantic-link-receipt/1.0",
        "id": str(receipt.meta.id), "run_id": str(receipt.meta.run_id),
        "admission_proposal_id": str(receipt.admission_proposal_id),
        "identity_map_id": str(receipt.identity_map_id),
        "relation_proposal_ids": [str(x) for x in receipt.relation_proposal_ids],
        "admitted_edge_ids": [str(x) for x in receipt.admitted_edge_ids],
        "trace_link_ids": [str(x) for x in receipt.trace_link_ids],
    }

class ExecutionLinkingAuditRepository:
    """Audit projection for R3.2 linking artifacts; GraphEdge authority remains ClaimRegistry."""
    def __init__(self, conn) -> None:
        self._conn = conn
    def save_identity_map(self, identity: AdmissionIdentityMap) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(identity.meta.id, admission_identity_map_to_dict(identity)); uow.commit()
    def save_relation_proposals(self, proposals: Sequence[SemanticRelationProposal]) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            for proposal in proposals:
                uow.put_state(proposal.meta.id, semantic_relation_proposal_to_dict(proposal))
            uow.commit()
    def save_receipt(self, receipt: SemanticLinkReceipt) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(receipt.meta.id, semantic_link_receipt_to_dict(receipt)); uow.commit()
