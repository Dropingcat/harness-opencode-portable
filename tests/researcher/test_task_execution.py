from __future__ import annotations

import random
import tempfile
import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.jobs import job_ctl
from researcher_core.capsules import CapsuleDescriptor, CapsuleObservation, InMemoryCapabilityRegistry, SideEffectClass
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.research_planning import (
    AddCardOperation,
    ResearchCard,
    ResearchCardKind,
    ResearchCardStatus,
    ResearchPatch,
    ResearchRequest,
    apply_research_patch,
    create_initial_dom,
)
from researcher_core.task_execution import (
    DelegationMode,
    ExecutionMode,
    ExecutionOwner,
    JobCtlDelegationAdapter,
    TaskExecutionError,
    TaskExecutionStatus,
    TaskExecutionRepository,
    build_delegation_request,
    compile_task_execution_plan,
    execute_local_task,
    finish_task_execution,
    start_task_execution,
)


class Clock:
    def now_ms(self): return 1789250000000


class SearchCapsule:
    descriptor = CapsuleDescriptor(
        capsule_id="local-corpus-search",
        version="1.0",
        capabilities=("corpus.search",),
        side_effect_class=SideEffectClass.READ_ONLY,
        input_schema_version="search-request/1.0",
        output_schema_version="search-observation/1.0",
    )

    def run(self, request):
        return CapsuleObservation(
            request_id=request.request_id,
            capsule_id=self.descriptor.capsule_id,
            capability=request.capability,
            output_schema_version=self.descriptor.output_schema_version,
            payload={"hits": [{"source": "local", "snippet": "candidate evidence"}]},
            provenance={"provider": "fixture", "query_title": request.payload.get("title")},
        )


class TaskExecutionTests(unittest.TestCase):
    def setUp(self):
        self.ids = EntityIdFactory(Clock(), random.Random(41))
        self.actor = ActorRef("AGENT", "researcher")
        self.created = datetime(2026, 9, 12, 20, 0, tzinfo=timezone.utc)
        self.run_id = self.ids.new("RUN")
        self.request = ResearchRequest(
            EntityMeta(self.ids.new("RRQ"), "research-request/1.0", 1, self.run_id, self.created, self.actor),
            "Investigate BCC lattice parameter changes",
        )
        self.root = ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, ResearchCardKind.OBJECTIVE, self.request.objective,
        )
        self.dom = create_initial_dom(self.request, self.root, self.ids.new("RDM"))
        self.direction = self.card(ResearchCardKind.DIRECTION, "D1", self.root.meta.id, {"disciplines": ["crystallography"]})
        self.local_task = self.card(
            ResearchCardKind.TASK, "Search stress-sensitive XRD evidence", self.direction.meta.id,
            {"capability": "corpus.search", "input_payload": {"title": "residual stress XRD"}},
        )
        self.dom = self.apply_add(self.dom, self.direction, self.local_task)
        self.registry = InMemoryCapabilityRegistry()
        self.registry.register(SearchCapsule())

    def card(self, kind, title, parent, dimensions):
        return ResearchCard(
            EntityMeta(self.ids.new("RCD"), "research-card/1.0", 1, self.run_id, self.created, self.actor),
            self.request.meta.id, kind, title, parent_id=parent, dimensions=dimensions,
        )

    def apply_add(self, dom, *cards):
        return apply_research_patch(
            dom,
            ResearchPatch(self.ids.new("RPT"), self.request.meta.id, dom.meta.revision, tuple(AddCardOperation(x) for x in cards)),
            self.actor, self.ids, self.created, self.ids.new("OPR"), self.ids.new("TXN"),
        ).dom

    def compile_local(self, dom=None):
        return compile_task_execution_plan(
            dom=dom or self.dom, card_id=self.local_task.meta.id, id_factory=self.ids, actor=self.actor,
            created_at=self.created, local_capabilities=tuple(self.registry.capabilities()),
        )

    def test_local_plan_executes_capsule_and_completes_card_without_epistemic_admission(self):
        plan = self.compile_local()
        self.assertEqual(plan.mode, ExecutionMode.LOCAL)
        self.assertEqual(plan.owner, ExecutionOwner.RESEARCHER)
        started = start_task_execution(
            dom=self.dom, plan=plan, id_factory=self.ids, actor=self.actor, timestamp=self.created,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        active = started.dom.cards[self.local_task.meta.id]
        self.assertEqual(active.status, ResearchCardStatus.ACTIVE)
        result = execute_local_task(
            plan=plan, active_card_revision=active.meta.revision, registry=self.registry, id_factory=self.ids,
            actor=self.actor, created_at=self.created,
        )
        self.assertEqual(result.status, TaskExecutionStatus.SUCCEEDED)
        self.assertIsNotNone(result.observation)
        self.assertEqual(result.observation.capability, "corpus.search")
        finished = finish_task_execution(
            dom=started.dom, plan=plan, result=result, id_factory=self.ids, actor=self.actor, timestamp=self.created,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        self.assertEqual(finished.dom.cards[self.local_task.meta.id].status, ResearchCardStatus.COMPLETED)
        # Execution result is observation/provenance only; no canonical Claim/Evidence entity is created here.
        self.assertFalse(hasattr(result, "claim"))
        self.assertFalse(hasattr(result, "evidence"))

    def test_execution_plan_and_local_result_roundtrip_in_existing_sqlite_uow(self):
        plan = self.compile_local()
        started = start_task_execution(
            dom=self.dom, plan=plan, id_factory=self.ids, actor=self.actor, timestamp=self.created,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        active = started.dom.cards[self.local_task.meta.id]
        result = execute_local_task(
            plan=plan, active_card_revision=active.meta.revision, registry=self.registry, id_factory=self.ids,
            actor=self.actor, created_at=self.created,
        )
        conn = sqlite3.connect(":memory:")
        repo = TaskExecutionRepository(conn)
        repo.save_plan(plan); repo.save_result(result)
        self.assertEqual(repo.load_plan(plan.meta.id), plan)
        self.assertEqual(repo.load_result(result.meta.id), result)
        conn.close()

    def test_missing_local_provider_fails_closed_instead_of_silent_delegation(self):
        with self.assertRaisesRegex(TaskExecutionError, "no local provider"):
            compile_task_execution_plan(
                dom=self.dom, card_id=self.local_task.meta.id, id_factory=self.ids, actor=self.actor,
                created_at=self.created, local_capabilities=(),
            )

    def test_non_leaf_task_is_rejected(self):
        child = self.card(ResearchCardKind.TASK, "child", self.local_task.meta.id, {"capability": "corpus.search"})
        dom = self.apply_add(self.dom, child)
        with self.assertRaisesRegex(TaskExecutionError, "only leaf"):
            compile_task_execution_plan(
                dom=dom, card_id=self.local_task.meta.id, id_factory=self.ids, actor=self.actor,
                created_at=self.created, local_capabilities=("corpus.search",),
            )

    def test_stale_plan_revision_rejected(self):
        plan = self.compile_local()
        started = start_task_execution(
            dom=self.dom, plan=plan, id_factory=self.ids, actor=self.actor, timestamp=self.created,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        with self.assertRaisesRegex(TaskExecutionError, "stale execution plan"):
            start_task_execution(
                dom=started.dom, plan=plan, id_factory=self.ids, actor=self.actor, timestamp=self.created,
                causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )

    def make_peer(self, mode="required"):
        peer = self.card(
            ResearchCardKind.DELEGATION, "Run numerical experiment", self.direction.meta.id,
            {"capability": "science.numeric", "execution_owner": "CODER", "route_id": "code-implementation", "delegation_mode": mode},
        )
        dom = self.apply_add(self.dom, peer)
        plan = compile_task_execution_plan(
            dom=dom, card_id=peer.meta.id, id_factory=self.ids, actor=self.actor, created_at=self.created,
            local_capabilities=("corpus.search",),
        )
        return dom, peer, plan

    def test_peer_plan_uses_explicit_owner_and_route_not_text_regex(self):
        dom, peer, plan = self.make_peer()
        self.assertEqual(plan.mode, ExecutionMode.PEER_DELEGATION)
        self.assertEqual(plan.owner, ExecutionOwner.CODER)
        self.assertEqual(plan.route_id, "code-implementation")
        self.assertEqual(plan.delegation_mode, DelegationMode.REQUIRED)

    def test_required_peer_child_success_reconciles_and_completes_source_card(self):
        dom, peer, plan = self.make_peer()
        started = start_task_execution(
            dom=dom, plan=plan, id_factory=self.ids, actor=self.actor, timestamp=self.created,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        with tempfile.TemporaryDirectory() as td:
            parent_path = Path(td) / "parent.json"
            parent = job_ctl.create("research-parent", {"schema": "research-parent/1.0"}, ["research"])
            parent["stages"]["research"]["status"] = "COMPLETED"
            job_ctl.save(parent, parent_path)
            request = build_delegation_request(
                plan=plan, parent_job_id="research-parent", id_factory=self.ids, actor=self.actor, created_at=self.created,
            )
            adapter = JobCtlDelegationAdapter(Path(td) / "children")
            child_path = adapter.start(parent_state_path=parent_path, request=request)
            self.assertTrue(child_path.exists())
            running_parent = job_ctl.load(parent_path)
            self.assertEqual(running_parent["children"][0]["mode"], "required")
            self.assertFalse(job_ctl.reconcile(running_parent)["ok"])
            result = adapter.finish(
                parent_state_path=parent_path, request=request, child_status="COMPLETED",
                active_card_revision=started.dom.cards[peer.meta.id].meta.revision,
                id_factory=self.ids, actor=self.actor, created_at=self.created,
                artifact_refs=("artifact://coder/simulation-1",),
            )
            self.assertTrue(job_ctl.reconcile(job_ctl.load(parent_path))["ok"])
            finished = finish_task_execution(
                dom=started.dom, plan=plan, result=result, id_factory=self.ids, actor=self.actor, timestamp=self.created,
                causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )
            self.assertEqual(finished.dom.cards[peer.meta.id].status, ResearchCardStatus.COMPLETED)
            self.assertEqual(result.artifact_refs, ("artifact://coder/simulation-1",))

    def test_required_peer_failure_blocks_parent_and_source_card(self):
        dom, peer, plan = self.make_peer()
        started = start_task_execution(
            dom=dom, plan=plan, id_factory=self.ids, actor=self.actor, timestamp=self.created,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        with tempfile.TemporaryDirectory() as td:
            parent_path = Path(td) / "parent.json"
            parent = job_ctl.create("research-parent", {"schema": "research-parent/1.0"}, ["research"])
            parent["stages"]["research"]["status"] = "COMPLETED"
            job_ctl.save(parent, parent_path)
            request = build_delegation_request(plan=plan, parent_job_id="research-parent", id_factory=self.ids, actor=self.actor, created_at=self.created)
            adapter = JobCtlDelegationAdapter(Path(td) / "children")
            adapter.start(parent_state_path=parent_path, request=request)
            result = adapter.finish(
                parent_state_path=parent_path, request=request, child_status="FAILED",
                active_card_revision=started.dom.cards[peer.meta.id].meta.revision,
                id_factory=self.ids, actor=self.actor, created_at=self.created,
            )
            rec = job_ctl.reconcile(job_ctl.load(parent_path))
            self.assertFalse(rec["ok"])
            self.assertIn(request.child_job_id, rec["nonterminal_required_children"])
            finished = finish_task_execution(
                dom=started.dom, plan=plan, result=result, id_factory=self.ids, actor=self.actor, timestamp=self.created,
                causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
            )
            self.assertEqual(finished.dom.cards[peer.meta.id].status, ResearchCardStatus.BLOCKED)

    def test_optional_peer_failure_does_not_block_parent_reconciliation(self):
        dom, peer, plan = self.make_peer(mode="optional")
        started = start_task_execution(
            dom=dom, plan=plan, id_factory=self.ids, actor=self.actor, timestamp=self.created,
            causation_id=self.ids.new("OPR"), correlation_id=self.ids.new("TXN"),
        )
        with tempfile.TemporaryDirectory() as td:
            parent_path = Path(td) / "parent.json"
            parent = job_ctl.create("research-parent", {"schema": "research-parent/1.0"}, ["research"])
            parent["stages"]["research"]["status"] = "COMPLETED"
            job_ctl.save(parent, parent_path)
            request = build_delegation_request(plan=plan, parent_job_id="research-parent", id_factory=self.ids, actor=self.actor, created_at=self.created)
            adapter = JobCtlDelegationAdapter(Path(td) / "children")
            adapter.start(parent_state_path=parent_path, request=request)
            adapter.finish(
                parent_state_path=parent_path, request=request, child_status="FAILED",
                active_card_revision=started.dom.cards[peer.meta.id].meta.revision,
                id_factory=self.ids, actor=self.actor, created_at=self.created,
            )
            self.assertTrue(job_ctl.reconcile(job_ctl.load(parent_path))["ok"])

    def test_duplicate_child_start_is_rejected(self):
        dom, peer, plan = self.make_peer()
        with tempfile.TemporaryDirectory() as td:
            parent_path = Path(td) / "parent.json"
            job_ctl.save(job_ctl.create("research-parent", {"schema": "research-parent/1.0"}, ["research"]), parent_path)
            request = build_delegation_request(plan=plan, parent_job_id="research-parent", id_factory=self.ids, actor=self.actor, created_at=self.created)
            adapter = JobCtlDelegationAdapter(Path(td) / "children")
            adapter.start(parent_state_path=parent_path, request=request)
            with self.assertRaisesRegex(TaskExecutionError, "already exists"):
                adapter.start(parent_state_path=parent_path, request=request)


if __name__ == "__main__":
    unittest.main()
