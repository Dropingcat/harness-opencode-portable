from __future__ import annotations

import json
import random
import unittest
from datetime import datetime, timezone
from pathlib import Path

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_composition import load_tribunal_composition_policy
from researcher_core.tribunal_provider_binding import (
    ProviderBindingStatus,
    RoleExecutionKind,
    assert_binding_execution_ready,
    compile_role_provider_binding,
    load_provider_binding_policy,
)


class Clock:
    def now_ms(self):
        return 1789280000000


class TribunalProviderBindingTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.ids = EntityIdFactory(Clock(), random.Random(9911))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.contract = self.ids.new("DQC")
        self.t = datetime(2026, 9, 13, 10, 0, tzinfo=timezone.utc)
        self.composition = load_tribunal_composition_policy(self.root / "config" / "tribunal_composition.yaml")
        self.binding_policy = load_provider_binding_policy(self.root / "config" / "tribunal_provider_binding.yaml")
        self.runtime = {
            "tools": {
                "tribunal_a": {"provider": "runtime_a"},
                "tribunal_b": {"provider": "runtime_b"},
                "other_tool": {"provider": "runtime_other"},
            }
        }
        self.providers = {
            "providers": {
                "p.a": {"kind": "process", "tool": "tribunal_a", "provides": ["tribunal.role.execute"], "priority": 100, "live_probe": {"kind": "always"}},
                "p.b": {"kind": "process", "tool": "tribunal_b", "provides": ["tribunal.role.execute"], "priority": 90, "live_probe": {"kind": "always"}},
                "p.wrong": {"kind": "process", "tool": "other_tool", "provides": ["science.numeric"], "priority": 999, "live_probe": {"kind": "always"}},
            }
        }

    def pf(self, *, a=True, b=True):
        def st(ok, prio):
            return {"status": "available" if ok else "degraded", "available": ok, "implemented": True, "detail": "fixture", "kind": "process", "provides": ["tribunal.role.execute"], "priority": prio}
        return {"schema": "capability-preflight/1.0", "network_probes": False, "providers": {"p.a": st(a,100), "p.b": st(b,90), "p.wrong": {"status":"available","available":True,"implemented":True,"detail":"fixture","kind":"process","provides":["science.numeric"],"priority":999}}}

    def bind(self, **kw):
        return compile_role_provider_binding(
            contract_id=self.contract,
            run_id=self.run,
            expected_role_id="xrd_specialist",
            requested_role_id=kw.pop("requested_role_id", None),
            execution_kind=RoleExecutionKind.QUESTION,
            composition_policy=self.composition,
            binding_policy=self.binding_policy,
            providers_authority=self.providers,
            runtime_bindings=self.runtime,
            preflight=kw.pop("preflight", self.pf()),
            capability_policy_hash="sha256:test-capability-policy",
            id_factory=self.ids,
            actor=self.actor,
            created_at=self.t,
            **kw,
        )

    def test_multiple_healthy_selects_exactly_one_by_priority(self):
        b = self.bind()
        self.assertEqual(b.status, ProviderBindingStatus.READY)
        self.assertEqual(b.selected_provider_id, "p.a")
        self.assertEqual(b.candidate_provider_ids, ("p.a", "p.b"))
        self.assertEqual(b.max_executors, 1)

    def test_wrong_role_fails_closed(self):
        b = self.bind(requested_role_id="crystallographer")
        self.assertEqual(b.status, ProviderBindingStatus.ROLE_MISMATCH)
        self.assertIsNone(b.selected_provider_id)

    def test_explicit_wrong_provider_fails_closed(self):
        b = self.bind(requested_provider_id="p.wrong")
        self.assertEqual(b.status, ProviderBindingStatus.WRONG_PROVIDER)
        self.assertIsNone(b.selected_provider_id)

    def test_explicit_provider_with_wrong_role_kind_fails_closed(self):
        providers = json.loads(json.dumps(self.providers))
        providers["providers"]["p.a"]["role_kinds"] = ["META"]
        b = compile_role_provider_binding(
            contract_id=self.contract, run_id=self.run, expected_role_id="xrd_specialist", requested_role_id=None,
            execution_kind=RoleExecutionKind.QUESTION, composition_policy=self.composition, binding_policy=self.binding_policy,
            providers_authority=providers, runtime_bindings=self.runtime, preflight=self.pf(),
            capability_policy_hash="sha256:test-capability-policy", id_factory=self.ids, actor=self.actor, created_at=self.t,
            requested_provider_id="p.a",
        )
        self.assertEqual(b.status, ProviderBindingStatus.WRONG_PROVIDER)
        self.assertIsNone(b.selected_provider_id)

    def test_equal_priority_candidates_use_provider_id_tiebreak(self):
        providers = json.loads(json.dumps(self.providers))
        providers["providers"]["p.b"]["priority"] = 100
        pf = self.pf(); pf["providers"]["p.b"]["priority"] = 100
        b = compile_role_provider_binding(
            contract_id=self.contract, run_id=self.run, expected_role_id="xrd_specialist", requested_role_id=None,
            execution_kind=RoleExecutionKind.QUESTION, composition_policy=self.composition, binding_policy=self.binding_policy,
            providers_authority=providers, runtime_bindings=self.runtime, preflight=pf,
            capability_policy_hash="sha256:test-capability-policy", id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        self.assertEqual(b.candidate_provider_ids, ("p.a", "p.b"))
        self.assertEqual(b.selected_provider_id, "p.a")

    def test_no_healthy_provider_is_not_semantic_open(self):
        b = self.bind(preflight=self.pf(a=False,b=False))
        self.assertEqual(b.status, ProviderBindingStatus.NO_HEALTHY_PROVIDER)
        self.assertIsNone(b.selected_provider_id)

    def test_more_executors_than_policy_allows_fails_closed(self):
        b = self.bind(requested_executor_count=2)
        self.assertEqual(b.status, ProviderBindingStatus.EXECUTOR_CARDINALITY_EXCEEDED)
        self.assertIsNone(b.selected_provider_id)

    def test_health_change_after_binding_invalidates_execution(self):
        b = self.bind()
        assert_binding_execution_ready(b, self.pf())
        with self.assertRaisesRegex(Exception, "no longer execution-ready|health state changed"):
            assert_binding_execution_ready(b, self.pf(a=False,b=True))


    def test_provider_role_kind_filters_wrong_executor_even_if_higher_priority(self):
        providers = json.loads(json.dumps(self.providers))
        providers["providers"]["p.a"]["role_kinds"] = ["META"]
        providers["providers"]["p.b"]["role_kinds"] = ["METHOD"]
        b = compile_role_provider_binding(
            contract_id=self.contract, run_id=self.run, expected_role_id="xrd_specialist", requested_role_id=None,
            execution_kind=RoleExecutionKind.QUESTION, composition_policy=self.composition, binding_policy=self.binding_policy,
            providers_authority=providers, runtime_bindings=self.runtime, preflight=self.pf(),
            capability_policy_hash="sha256:test-capability-policy", id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        self.assertEqual(b.status, ProviderBindingStatus.READY)
        self.assertEqual(b.selected_provider_id, "p.b")
        self.assertIn("PROVIDER_ROLE_KIND_MISMATCH", b.rejected_provider_reasons["p.a"])

    def test_provider_contract_namespace_filters_wrong_executor(self):
        providers = json.loads(json.dumps(self.providers))
        providers["providers"]["p.a"]["execution_contracts"] = ["IQC"]
        providers["providers"]["p.b"]["execution_contracts"] = ["DQC"]
        b = compile_role_provider_binding(
            contract_id=self.contract, run_id=self.run, expected_role_id="xrd_specialist", requested_role_id=None,
            execution_kind=RoleExecutionKind.QUESTION, composition_policy=self.composition, binding_policy=self.binding_policy,
            providers_authority=providers, runtime_bindings=self.runtime, preflight=self.pf(),
            capability_policy_hash="sha256:test-capability-policy", id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        self.assertEqual(b.selected_provider_id, "p.b")
        self.assertIn("PROVIDER_CONTRACT_MISMATCH", b.rejected_provider_reasons["p.a"])

    def test_repository_provider_is_implemented_but_not_live_here(self):
        providers = json.loads((self.root / "config" / "providers_authority.json").read_text())
        runtime = json.loads((self.root / "config" / "tool_runtime_bindings.json").read_text())
        import importlib.util
        spec = importlib.util.spec_from_file_location("cap_preflight", self.root / "scripts" / "router" / "capability_preflight.py")
        mod = importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
        pf = mod.snapshot(network=False)
        b = compile_role_provider_binding(
            contract_id=self.contract, run_id=self.run,
            expected_role_id="xrd_specialist", requested_role_id=None,
            execution_kind=RoleExecutionKind.QUESTION,
            composition_policy=self.composition, binding_policy=self.binding_policy,
            providers_authority=providers, runtime_bindings=runtime, preflight=pf,
            capability_policy_hash=json.loads((self.root / "config" / "capability_runtime_snapshot.json").read_text())["policy_hash"],
            id_factory=self.ids, actor=self.actor, created_at=self.t,
        )
        # In CI/container without opencode, the provider is implemented but not executable.
        state = pf["providers"]["existing.opencode_tribunal_role"]
        if not state["available"]:
            self.assertEqual(b.status, ProviderBindingStatus.NO_HEALTHY_PROVIDER)


if __name__ == "__main__":
    unittest.main()
