from __future__ import annotations

import random
import sqlite3
import unittest
from datetime import datetime, timezone
from decimal import Decimal

from researcher_core.capsules import CapsuleObservation
from researcher_core.execution_admission import (
    ExecutionAdmissionAuditRepository,
    ExecutionAdmissionError,
    admit_execution_proposal,
    compile_local_execution_admission,
    compile_peer_execution_admission,
)
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import ClaimProposal, EntityMeta, EvidenceSpan, QuantityProposal, Source
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.r0.registry import CycleRandom, InMemoryClaimRegistry, ProposalBatch, SequenceClock
from researcher_core.research_planning import ResearchCard, ResearchCardKind, ResearchCardStatus, ResearchDOM
from researcher_core.research_planning_runtime import ResearchTraceRelation
from researcher_core.task_execution import ExecutionOwner, TaskExecutionResult, TaskExecutionStatus


class Clock:
    def now_ms(self): return 1789255000000


class ExecutionAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(61))
        self.actor = ActorRef("AGENT", "researcher")
        self.created = datetime(2026, 9, 12, 21, 0, tzinfo=timezone.utc)
        self.run_id = self.ids.new("RUN")
        self.request_id = self.ids.new("RRQ")
        self.dom_id = self.ids.new("RDM")
        self.root = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request_id, ResearchCardKind.OBJECTIVE, "Objective",
        )
        self.task = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 3, self.run_id, self.created, self.actor),
            self.request_id, ResearchCardKind.TASK, "Extract result", parent_id=self.root.meta.id,
            status=ResearchCardStatus.COMPLETED, dimensions={"capability": "text.extract_numeric_claims"},
        )
        self.dom = ResearchDOM(
            meta=EntityMeta(self.dom_id, "research-dom/1.0", 2, self.run_id, self.created, self.actor),
            request_id=self.request_id, root_card_id=self.root.meta.id,
            cards={self.root.meta.id: self.root, self.task.meta.id: self.task}, applied_patch_ids=(),
        )
        self.registry = InMemoryClaimRegistry(SequenceClock(1789255001000), CycleRandom())

    def observation_result(self, payload):
        obs = CapsuleObservation(
            request_id=self.ids.new("OPR"), capsule_id="fixture", capability="text.extract_numeric_claims",
            output_schema_version="proposal-observation/1.0", payload=payload, provenance={"fixture": True},
        )
        return TaskExecutionResult(
            meta=EntityMeta(self.ids.new("TER"), "task-execution-result/1.0", 1, self.run_id, self.created, self.actor),
            execution_plan_id=self.ids.new("TEP"), source_card_id=self.task.meta.id,
            active_card_revision=2, status=TaskExecutionStatus.SUCCEEDED,
            owner=ExecutionOwner.RESEARCHER, capability="text.extract_numeric_claims", observation=obs,
        )

    def claim_qty_payload(self):
        opr = self.ids.new("OPR")
        return {
            "claims": (ClaimProposal("tmp-c1", "Nitride fraction is 12 %.", "quantitative", {"sample": "A"}, None, opr),),
            "quantities": (QuantityProposal("tmp-q1", Decimal("12"), "%", "nitride_fraction", None, opr),),
        }

    def admit(self, proposal):
        return admit_execution_proposal(
            dom=self.dom, proposal=proposal, registry=self.registry, id_factory=self.ids, actor=self.actor,
            created_at=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )

    def test_structured_claim_and_quantity_are_admitted_only_through_registry(self):
        result = self.observation_result(self.claim_qty_payload())
        proposal = compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)
        self.assertEqual(len(proposal.batch.claims), 1)
        self.assertEqual(len(proposal.batch.quantities), 1)
        receipt, command_result, links = self.admit(proposal)
        self.assertEqual(len(command_result.accepted_ids), 2)
        self.assertEqual(receipt.admitted_ids, command_result.accepted_ids)
        self.assertEqual({x.namespace for x in receipt.admitted_ids}, {"CLM", "QTY"})
        self.assertEqual({x.target_id.namespace for x in links}, {"CLM", "QTY"})
        self.assertTrue(all(x.relation == ResearchTraceRelation.PRODUCED for x in links))

    def test_source_and_evidence_batch_preserves_prebuilt_identity(self):
        source = Source(
            EntityMeta(self.ids.new("SRC"), "source/1.0", 1, self.run_id, self.created, self.actor),
            "report", "Report", "file://report", "a" * 64,
        )
        evidence = EvidenceSpan(
            EntityMeta(self.ids.new("EVD"), "evidence/1.0", 1, self.run_id, self.created, self.actor),
            source.meta.id, "Exact evidence text.", "p. 4", "b" * 64,
        )
        result = self.observation_result({"sources": (source,), "evidence_spans": (evidence,)})
        proposal = compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)
        receipt, _, links = self.admit(proposal)
        self.assertEqual(set(receipt.admitted_ids), {source.meta.id, evidence.meta.id})
        self.assertEqual({x.target_id.namespace for x in links}, {"SRC", "EVD"})

    def test_failed_execution_cannot_compile_admission(self):
        result = TaskExecutionResult(
            meta=EntityMeta(self.ids.new("TER"), "task-execution-result/1.0", 1, self.run_id, self.created, self.actor),
            execution_plan_id=self.ids.new("TEP"), source_card_id=self.task.meta.id, active_card_revision=2,
            status=TaskExecutionStatus.FAILED, owner=ExecutionOwner.RESEARCHER, capability="x", reason="boom",
        )
        with self.assertRaisesRegex(ExecutionAdmissionError, "only successful"):
            compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)

    def test_untyped_observation_member_fails_closed(self):
        result = self.observation_result({"claims": ({"proposition": "not typed"},)})
        with self.assertRaisesRegex(ExecutionAdmissionError, "unsupported member type"):
            compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)

    def test_empty_structured_observation_is_rejected(self):
        result = self.observation_result({"claims": (), "quantities": ()})
        with self.assertRaisesRegex(ExecutionAdmissionError, "no admissible proposal"):
            compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)

    def test_stale_completed_card_revision_blocks_registry_admission(self):
        result = self.observation_result(self.claim_qty_payload())
        proposal = compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)
        newer = ResearchCard(
            meta=EntityMeta(self.task.meta.id, self.task.meta.schema_version, 4, self.run_id, self.created, self.actor),
            request_id=self.task.request_id, kind=self.task.kind, title=self.task.title, description=self.task.description,
            parent_id=self.task.parent_id, status=self.task.status, dimensions=self.task.dimensions, created_from=self.task.created_from,
        )
        stale_dom = ResearchDOM(self.dom.meta, self.dom.request_id, self.dom.root_card_id, {**self.dom.cards, newer.meta.id: newer}, self.dom.applied_patch_ids)
        with self.assertRaisesRegex(ExecutionAdmissionError, "stale execution admission"):
            admit_execution_proposal(
                dom=stale_dom, proposal=proposal, registry=self.registry, id_factory=self.ids, actor=self.actor,
                created_at=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )
        self.assertEqual(self.registry.state, {})

    def test_non_completed_card_blocks_admission(self):
        result = self.observation_result(self.claim_qty_payload())
        proposal = compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)
        active = ResearchCard(
            meta=self.task.meta, request_id=self.task.request_id, kind=self.task.kind, title=self.task.title,
            description=self.task.description, parent_id=self.task.parent_id, status=ResearchCardStatus.ACTIVE,
            dimensions=self.task.dimensions, created_from=self.task.created_from,
        )
        dom = ResearchDOM(self.dom.meta, self.dom.request_id, self.dom.root_card_id, {**self.dom.cards, active.meta.id: active}, self.dom.applied_patch_ids)
        with self.assertRaisesRegex(ExecutionAdmissionError, "must be COMPLETED"):
            admit_execution_proposal(
                dom=dom, proposal=proposal, registry=self.registry, id_factory=self.ids, actor=self.actor,
                created_at=self.created, causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )

    def test_peer_artifact_requires_explicit_typed_batch(self):
        result = TaskExecutionResult(
            meta=EntityMeta(self.ids.new("TER"), "task-execution-result/1.0", 1, self.run_id, self.created, self.actor),
            execution_plan_id=self.ids.new("TEP"), source_card_id=self.task.meta.id, active_card_revision=2,
            status=TaskExecutionStatus.SUCCEEDED, owner=ExecutionOwner.CODER, capability="numeric.simulate",
            artifact_refs=("artifact://sim.json",), child_job_id="coder-1",
        )
        opr = self.ids.new("OPR")
        batch = ProposalBatch(
            claims=(ClaimProposal("tmp-sim", "Simulation residual is below tolerance.", "computational", {}, None, opr),),
            quantities=(),
        )
        proposal = compile_peer_execution_admission(
            result=result, batch=batch, adapter_id="coder.simulation-result/1.0", id_factory=self.ids,
            actor=self.actor, created_at=self.created,
        )
        self.assertEqual(proposal.adapter_id, "coder.simulation-result/1.0")
        receipt, _, _ = self.admit(proposal)
        self.assertEqual(len(receipt.admitted_ids), 1)
        with self.assertRaisesRegex(ExecutionAdmissionError, "empty proposal batch"):
            compile_peer_execution_admission(
                result=result, batch=ProposalBatch((), ()), adapter_id="coder.simulation-result/1.0",
                id_factory=self.ids, actor=self.actor, created_at=self.created,
            )

    def test_bad_source_shape_is_rejected_by_deterministic_preflight(self):
        source = Source(
            EntityMeta(self.ids.new("SRC"), "source/1.0", 1, self.run_id, self.created, self.actor),
            "report", "Report", "file://report", "sha256:not-a-validator-hash",
        )
        result = self.observation_result({"sources": (source,)})
        proposal = compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)
        with self.assertRaisesRegex(ExecutionAdmissionError, "preflight failed"):
            self.admit(proposal)
        self.assertEqual(self.registry.state, {})

    def test_registry_validation_failure_leaves_no_canonical_state(self):
        missing_source = self.ids.new("SRC")
        evidence = EvidenceSpan(
            EntityMeta(self.ids.new("EVD"), "evidence/1.0", 1, self.run_id, self.created, self.actor),
            missing_source, "orphan evidence", "p. 1", "c" * 64,
        )
        result = self.observation_result({"evidence_spans": (evidence,)})
        proposal = compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)
        with self.assertRaises(Exception):
            self.admit(proposal)
        self.assertEqual(self.registry.state, {})

    def test_audit_repository_persists_proposal_identity_and_receipt(self):
        result = self.observation_result(self.claim_qty_payload())
        proposal = compile_local_execution_admission(result=result, id_factory=self.ids, actor=self.actor, created_at=self.created)
        receipt, _, _ = self.admit(proposal)
        conn = sqlite3.connect(":memory:")
        repo = ExecutionAdmissionAuditRepository(conn)
        repo.save_proposal(proposal); repo.save_receipt(receipt)
        rows = sqlite3.connect(":memory:") if False else None
        view = __import__("researcher_core.r0.sqlite_store", fromlist=["SqliteUnitOfWork"]).SqliteUnitOfWork(conn).state_view()
        self.assertEqual(view[str(proposal.meta.id)]["schema_version"], "execution-admission-proposal/1.0")
        self.assertEqual(view[str(receipt.meta.id)]["schema_version"], "execution-admission-receipt/1.0")
        conn.close()


if __name__ == "__main__": unittest.main()
