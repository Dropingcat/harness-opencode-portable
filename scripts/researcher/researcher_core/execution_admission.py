"""R3.1 execution-output admission bridge.

Execution providers emit untrusted observations/artifacts. This module compiles
only already-typed proposal objects into an admission proposal, delegates the
canonical write to the existing R0 ClaimRegistry, and projects process
provenance back to the producing ResearchCard.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from researcher_core.r0.commands import ActorRef, CommandEnvelope, CommandResult
from researcher_core.r0.entities import ClaimProposal, EntityMeta, EvidenceSpan, QuantityProposal, Source
from researcher_core.r0.enums import CommitPolicy, ValidationResult
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.r0.registry import InMemoryClaimRegistry, ProposalBatch
from researcher_core.r0.sqlite_store import SqliteUnitOfWork
from researcher_core.research_planning import ResearchCardStatus, ResearchDOM
from researcher_core.research_planning_runtime import ResearchTraceLink, ResearchTraceRelation
from researcher_core.task_execution import TaskExecutionResult, TaskExecutionStatus
from researcher_core.r3_validators import AtomicityValidator, EvidenceAdmissionValidator, NumericValidator, SourceAdmissionValidator


class ExecutionAdmissionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionAdmissionProposal:
    meta: EntityMeta
    execution_result_id: EntityId
    source_card_id: EntityId
    expected_completed_card_revision: int
    batch: ProposalBatch
    adapter_id: str
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "EAP":
            raise ValueError("execution admission proposal id must use EAP prefix")
        if self.execution_result_id.namespace != "TER":
            raise ValueError("execution_result_id must use TER prefix")
        if self.source_card_id.namespace != "RCD":
            raise ValueError("source_card_id must use RCD prefix")
        if self.expected_completed_card_revision < 2:
            raise ValueError("expected completed card revision must be >= 2")
        if not self.adapter_id.strip():
            raise ValueError("adapter_id is required")
        if _batch_size(self.batch) == 0:
            raise ValueError("admission proposal batch must not be empty")
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


@dataclass(frozen=True, slots=True)
class ExecutionAdmissionReceipt:
    meta: EntityMeta
    proposal_id: EntityId
    registry_command_id: EntityId
    source_card_id: EntityId
    admitted_ids: tuple[EntityId, ...]
    trace_link_ids: tuple[EntityId, ...]

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "EAR":
            raise ValueError("execution admission receipt id must use EAR prefix")
        if self.proposal_id.namespace != "EAP":
            raise ValueError("proposal_id must use EAP prefix")
        if self.registry_command_id.namespace != "OPR":
            raise ValueError("registry_command_id must use OPR prefix")
        if self.source_card_id.namespace != "RCD":
            raise ValueError("source_card_id must use RCD prefix")
        if not self.admitted_ids:
            raise ValueError("admitted_ids must not be empty")
        object.__setattr__(self, "admitted_ids", tuple(self.admitted_ids))
        object.__setattr__(self, "trace_link_ids", tuple(self.trace_link_ids))


def compile_local_execution_admission(
    *, result: TaskExecutionResult, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime,
) -> ExecutionAdmissionProposal:
    """Compile a successful structured CapsuleObservation into typed proposals."""
    if result.status != TaskExecutionStatus.SUCCEEDED:
        raise ExecutionAdmissionError("only successful execution results can be proposed for admission")
    if result.observation is None:
        raise ExecutionAdmissionError("local execution result has no observation")
    payload = result.observation.payload
    batch = _typed_batch_from_payload(payload)
    return ExecutionAdmissionProposal(
        meta=EntityMeta(id_factory.new("EAP"), "execution-admission-proposal/1.0", 1, result.meta.run_id, created_at, actor),
        execution_result_id=result.meta.id,
        source_card_id=result.source_card_id,
        expected_completed_card_revision=result.active_card_revision + 1,
        batch=batch,
        adapter_id=f"capsule:{result.observation.capsule_id}:{result.observation.output_schema_version}",
        provenance={
            "execution_plan_id": str(result.execution_plan_id),
            "capability": result.capability,
            "observation_request_id": str(result.observation.request_id),
        },
    )


def compile_peer_execution_admission(
    *, result: TaskExecutionResult, batch: ProposalBatch, adapter_id: str,
    id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime,
    provenance: Mapping[str, Any] | None = None,
) -> ExecutionAdmissionProposal:
    """Compile explicit typed adapter output for a successful peer artifact."""
    if result.status != TaskExecutionStatus.SUCCEEDED:
        raise ExecutionAdmissionError("only successful execution results can be proposed for admission")
    if result.observation is not None:
        raise ExecutionAdmissionError("peer admission expects explicit adapter batch, not a local observation")
    if not result.artifact_refs:
        raise ExecutionAdmissionError("peer admission requires at least one artifact reference")
    if _batch_size(batch) == 0:
        raise ExecutionAdmissionError("peer adapter produced an empty proposal batch")
    return ExecutionAdmissionProposal(
        meta=EntityMeta(id_factory.new("EAP"), "execution-admission-proposal/1.0", 1, result.meta.run_id, created_at, actor),
        execution_result_id=result.meta.id,
        source_card_id=result.source_card_id,
        expected_completed_card_revision=result.active_card_revision + 1,
        batch=batch,
        adapter_id=adapter_id,
        provenance={"artifact_refs": tuple(result.artifact_refs), **dict(provenance or {})},
    )


def preflight_execution_proposal(proposal: ExecutionAdmissionProposal) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Run deterministic admission-shape validators before the registry mutation boundary.

    WARN outcomes are preserved in the audit return but do not block structural
    admission. FAIL outcomes are fail-closed. Scientific support remains a later
    assessment concern.
    """
    findings: list[tuple[str, str, tuple[str, ...]]] = []
    checks = (
        (("claim", x, AtomicityValidator()) for x in proposal.batch.claims),
        (("quantity", x, NumericValidator()) for x in proposal.batch.quantities),
        (("source", x, SourceAdmissionValidator()) for x in proposal.batch.sources),
        (("evidence", x, EvidenceAdmissionValidator()) for x in proposal.batch.evidence_spans),
    )
    failures: list[str] = []
    for group in checks:
        for kind, entity, validator in group:
            outcome = validator.evaluate(entity)
            findings.append((kind, outcome.result.value, tuple(outcome.reason_codes)))
            if outcome.result == ValidationResult.FAIL:
                failures.append(f"{kind}:{','.join(outcome.reason_codes) or 'validation_failed'}")
    if failures:
        raise ExecutionAdmissionError("execution admission preflight failed: " + "; ".join(failures))
    return tuple(findings)


def admit_execution_proposal(
    *, dom: ResearchDOM, proposal: ExecutionAdmissionProposal, registry: InMemoryClaimRegistry,
    id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime,
    causation_id: EntityId, correlation_id: EntityId,
) -> tuple[ExecutionAdmissionReceipt, CommandResult, tuple[ResearchTraceLink, ...]]:
    """Revision-check TASK lineage, admit via R0 registry, and project TASK provenance."""
    card = dom.cards.get(proposal.source_card_id)
    if card is None:
        raise ExecutionAdmissionError("source ResearchCard does not exist")
    if card.status != ResearchCardStatus.COMPLETED:
        raise ExecutionAdmissionError("source ResearchCard must be COMPLETED before admission")
    if card.meta.revision != proposal.expected_completed_card_revision:
        raise ExecutionAdmissionError("stale execution admission proposal card revision")
    if proposal.meta.run_id != dom.meta.run_id:
        raise ExecutionAdmissionError("admission proposal run does not match ResearchDOM run")

    preflight_execution_proposal(proposal)

    command_id = id_factory.new("OPR")
    command = CommandEnvelope(
        command_id=command_id,
        command_type="ADMIT_EXECUTION_OUTPUT",
        run_id=proposal.meta.run_id,
        actor=actor,
        idempotency_key=f"execution-admission:{proposal.meta.id}",
        expected_revisions={proposal.source_card_id: card.meta.revision},
        causation_id=causation_id,
        correlation_id=correlation_id,
        payload={
            "execution_admission_proposal_id": str(proposal.meta.id),
            "execution_result_id": str(proposal.execution_result_id),
            "source_card_id": str(proposal.source_card_id),
            "adapter_id": proposal.adapter_id,
        },
    )
    result = registry.admit(proposal.batch, CommitPolicy.ALL_OR_NOTHING, command)
    links = tuple(
        ResearchTraceLink(
            id=id_factory.new("RTL"),
            research_card_id=proposal.source_card_id,
            target_id=entity_id,
            relation=ResearchTraceRelation.PRODUCED,
            run_id=proposal.meta.run_id,
            created_at=created_at,
            created_by=actor,
            metadata={
                "execution_result_id": str(proposal.execution_result_id),
                "admission_proposal_id": str(proposal.meta.id),
                "registry_command_id": str(command_id),
            },
        )
        for entity_id in result.accepted_ids
    )
    receipt = ExecutionAdmissionReceipt(
        meta=EntityMeta(id_factory.new("EAR"), "execution-admission-receipt/1.0", 1, proposal.meta.run_id, created_at, actor),
        proposal_id=proposal.meta.id,
        registry_command_id=command_id,
        source_card_id=proposal.source_card_id,
        admitted_ids=result.accepted_ids,
        trace_link_ids=tuple(link.id for link in links),
    )
    return receipt, result, links


def _typed_batch_from_payload(payload: Mapping[str, Any]) -> ProposalBatch:
    claims = payload.get("claims", ())
    quantities = payload.get("quantities", ())
    sources = payload.get("sources", ())
    evidence_spans = payload.get("evidence_spans", ())
    values = {
        "claims": (claims, ClaimProposal),
        "quantities": (quantities, QuantityProposal),
        "sources": (sources, Source),
        "evidence_spans": (evidence_spans, EvidenceSpan),
    }
    normalized: dict[str, tuple[Any, ...]] = {}
    for name, (items, expected) in values.items():
        if not isinstance(items, tuple):
            raise ExecutionAdmissionError(f"observation payload {name} must be a tuple")
        if not all(isinstance(item, expected) for item in items):
            raise ExecutionAdmissionError(f"observation payload {name} contains unsupported member type")
        normalized[name] = items
    batch = ProposalBatch(
        claims=normalized["claims"], quantities=normalized["quantities"],
        sources=normalized["sources"], evidence_spans=normalized["evidence_spans"], edges=(),
    )
    if _batch_size(batch) == 0:
        raise ExecutionAdmissionError("structured observation contains no admissible proposal objects")
    return batch


def _batch_size(batch: ProposalBatch) -> int:
    return len(batch.claims) + len(batch.quantities) + len(batch.sources) + len(batch.evidence_spans) + len(batch.edges)


def execution_admission_proposal_to_dict(proposal: ExecutionAdmissionProposal) -> dict[str, Any]:
    # ProposalBatch contains Python entities; repository persistence intentionally stores audit identity/provenance only.
    return {
        "schema_version": "execution-admission-proposal/1.0",
        "id": str(proposal.meta.id),
        "run_id": str(proposal.meta.run_id),
        "execution_result_id": str(proposal.execution_result_id),
        "source_card_id": str(proposal.source_card_id),
        "expected_completed_card_revision": proposal.expected_completed_card_revision,
        "adapter_id": proposal.adapter_id,
        "batch_counts": {
            "claims": len(proposal.batch.claims), "quantities": len(proposal.batch.quantities),
            "sources": len(proposal.batch.sources), "evidence_spans": len(proposal.batch.evidence_spans), "edges": len(proposal.batch.edges),
        },
        "provenance": dict(proposal.provenance),
    }


def execution_admission_receipt_to_dict(receipt: ExecutionAdmissionReceipt) -> dict[str, Any]:
    return {
        "schema_version": "execution-admission-receipt/1.0",
        "id": str(receipt.meta.id), "run_id": str(receipt.meta.run_id),
        "proposal_id": str(receipt.proposal_id), "registry_command_id": str(receipt.registry_command_id),
        "source_card_id": str(receipt.source_card_id),
        "admitted_ids": [str(x) for x in receipt.admitted_ids],
        "trace_link_ids": [str(x) for x in receipt.trace_link_ids],
    }


class ExecutionAdmissionAuditRepository:
    """Audit projection for proposals/receipts; canonical KG remains in ClaimRegistry."""
    def __init__(self, conn) -> None:
        self._conn = conn

    def save_proposal(self, proposal: ExecutionAdmissionProposal) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(proposal.meta.id, execution_admission_proposal_to_dict(proposal)); uow.commit()

    def save_receipt(self, receipt: ExecutionAdmissionReceipt) -> None:
        with SqliteUnitOfWork(self._conn) as uow:
            uow.put_state(receipt.meta.id, execution_admission_receipt_to_dict(receipt)); uow.commit()
