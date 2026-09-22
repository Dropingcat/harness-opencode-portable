from __future__ import annotations

import random
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.jobs import job_ctl
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_advocate import (
    AdvocateNextAction,
    AdvocateOutcome,
    admit_advocate_response_to_argument_graph,
    compile_advocate_defense_contract,
    compile_advocate_disclosure,
    decide_advocate_activation,
)
from researcher_core.tribunal_argument_graph import ArgumentRelation, ArgumentRelationKind, build_argument_graph
from researcher_core.tribunal_composition import AssessmentNeedRef, load_tribunal_composition_policy
from researcher_core.tribunal_inquiry import (
    ArgumentArtifact,
    ArgumentPosition,
    InquiryTurn,
    InquiryTurnKind,
    ResponseGroundingState,
    argument_artifact_to_dict,
    inquiry_turn_to_dict,
)
from researcher_core.tribunal_live_dialogue import (
    JobCtlLiveDialogueAdapter,
    ProviderExecutionStatus,
    SubprocessJsonProviderTransport,
    TribunalLiveDialogueError,
    compile_advocate_execution_envelope,
)
from researcher_core.tribunal_provider_binding import compile_defense_provider_binding, load_provider_binding_policy
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self):
        return 1789290000000


class R44L3BLiveAdvocateGroundingE2E(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[2]
        self.policy = load_tribunal_composition_policy(self.root / "config/tribunal_composition.yaml")
        self.handbook = load_role_handbook(self.root / "config/tribunal_role_handbook.yaml", self.policy)
        self.binding_policy = load_provider_binding_policy(self.root / "config/tribunal_provider_binding.yaml")
        self.ids = EntityIdFactory(Clock(), random.Random(94442))
        self.actor = ActorRef("AGENT", "researcher")
        self.run = self.ids.new("RUN")
        self.base_contract = self.ids.new("IQC")
        self.need = AssessmentNeedRef("ANR-l3badvocate0001", 0)
        self.claim = self.ids.new("CLM")
        self.e_support = self.ids.new("EVD")
        self.e_attack = self.ids.new("EVD")
        self.e_hidden = self.ids.new("EVD")
        self.t = datetime(2026, 9, 13, 19, 30, tzinfo=timezone.utc)
        self.providers = {
            "providers": {
                "test.advocate": {
                    "kind": "process",
                    "tool": "tribunal_live_stub",
                    "provides": ["tribunal.role.execute"],
                    "priority": 100,
                    "live_probe": {"kind": "always"},
                    "role_kinds": ["META"],
                    "execution_contracts": ["ADC"],
                    "max_executors_per_contract": 1,
                }
            }
        }
        self.runtime_bindings = {"tools": {"tribunal_live_stub": {"provider": "test_advocate"}}}
        self.preflight = {
            "schema": "capability-preflight/1.0",
            "network_probes": False,
            "providers": {
                "test.advocate": {
                    "status": "available",
                    "available": True,
                    "implemented": True,
                    "detail": "fixture-process",
                    "kind": "process",
                    "provides": ["tribunal.role.execute"],
                    "priority": 100,
                }
            },
        }
        self.cap_hash = "sha256:l3b-live-advocate"

    def meta(self, ns, schema, *, entity_id=None, revision=1):
        return EntityMeta(entity_id or self.ids.new(ns), schema, revision, self.run, self.t, self.actor)

    def arg(self, role, position, text, evd, kind):
        turn = InquiryTurn(self.meta("IQT", "inquiry-turn/1.0"), self.base_contract, role, kind, text, None, (self.claim, evd))
        arg = ArgumentArtifact(
            self.meta("ARG", "argument-artifact/1.0"), self.base_contract, turn.meta.id,
            role, position, (self.need,), text, text + " justification", (evd,), (self.claim,), (), (),
        )
        return turn, arg

    def fixture(self):
        root_t, root = self.arg("xrd_specialist", ArgumentPosition.QUALIFY, "qualified XRD interpretation", self.e_support, InquiryTurnKind.FIRST_PASS_ASSESSMENT)
        ch_t, challenge = self.arg("skeptic", ArgumentPosition.CHALLENGE, "residual stress alternative", self.e_attack, InquiryTurnKind.CHALLENGE)
        sibling_t, sibling = self.arg("methodologist", ArgumentPosition.CHALLENGE, "hidden calibration branch", self.e_hidden, InquiryTurnKind.CHALLENGE)
        attack = ArgumentRelation(self.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.ATTACKS, challenge.meta.id, root.meta.id, (self.need,), material=True)
        sibling_rel = ArgumentRelation(self.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.UNDERCUTS, sibling.meta.id, root.meta.id, (self.need,), material=True)
        graph = build_argument_graph(meta=self.meta("AGP", "argument-graph-projection/1.0"), arguments=(root, challenge, sibling), relations=(attack, sibling_rel))
        args = {x.meta.id: x for x in (root, challenge, sibling)}
        turns = {x.meta.id: x for x in (root_t, ch_t, sibling_t)}
        activation = decide_advocate_activation(graph=graph, arguments=args, challenge_relation=attack, composition_policy=self.policy)
        disclosure = compile_advocate_disclosure(activation=activation, graph=graph, arguments=args, id_factory=self.ids, actor=self.actor, created_at=self.t)
        instruction = compile_role_instruction_pack(role_id="advocate", variant=RoleVariantKind.DEFENSE, handbook=self.handbook, policy=self.policy)
        contract = compile_advocate_defense_contract(activation=activation, disclosure=disclosure, composition_policy=self.policy, instruction=instruction, id_factory=self.ids, actor=self.actor, created_at=self.t)
        binding = compile_defense_provider_binding(
            contract=contract,
            requested_role_id=None,
            composition_policy=self.policy,
            binding_policy=self.binding_policy,
            providers_authority=self.providers,
            runtime_bindings=self.runtime_bindings,
            preflight=self.preflight,
            capability_policy_hash=self.cap_hash,
            id_factory=self.ids,
            actor=self.actor,
            created_at=self.t,
        )
        refs = {
            self.claim: {"kind": "Claim", "text": "BCC lattice interpretation"},
            self.e_support: {"kind": "Evidence", "text": "supporting XRD evidence"},
            self.e_attack: {"kind": "Evidence", "text": "attack evidence"},
            self.e_hidden: {"kind": "Evidence", "text": "hidden sibling evidence"},
        }
        envelope = compile_advocate_execution_envelope(
            binding=binding,
            disclosure=disclosure,
            contract=contract,
            instruction=instruction,
            argument_payloads={k: argument_artifact_to_dict(v) for k, v in args.items()},
            turn_payloads={k: inquiry_turn_to_dict(v) for k, v in turns.items()},
            ref_payloads=refs,
            id_factory=self.ids,
            actor=self.actor,
            created_at=self.t,
        )
        return graph, args, disclosure, contract, binding, envelope

    def execute(self, mode="default", extra=()):
        graph, args, disclosure, contract, binding, envelope = self.fixture()
        command = (sys.executable, str(self.root / "tests/researcher/fixtures/tribunal_live_provider_stub.py"), mode, *extra)
        transport = SubprocessJsonProviderTransport({"test.advocate": command})
        with tempfile.TemporaryDirectory() as raw:
            td = Path(raw)
            parent = td / "parent.json"
            job_ctl.save(job_ctl.create("l3b-advocate-parent", {"schema": "fixture/1.0"}, ["tribunal"]), parent)
            runtime = JobCtlLiveDialogueAdapter(state_dir=td / "jobs", artifact_dir=td / "artifacts", timeout_seconds=5)
            response, receipt = runtime.execute_defense(
                parent_state_path=parent,
                binding=binding,
                envelope=envelope,
                current_preflight=self.preflight,
                transport=transport,
                contract=contract,
                disclosure=disclosure,
                id_factory=self.ids,
                actor=self.actor,
                created_at=self.t,
            )
            return response, receipt, job_ctl.load(parent), graph, args, disclosure

    def test_live_qualified_defense_is_documented_and_keeps_reply_plus_defends(self):
        response, receipt, parent, graph, args, disclosure = self.execute()
        self.assertEqual(receipt.status, ProviderExecutionStatus.COMPLETED)
        self.assertEqual(response.outcome, AdvocateOutcome.QUALIFY)
        self.assertEqual(response.argument.grounding_state, ResponseGroundingState.DOCUMENTED)
        self.assertEqual(response.argument.metadata['grounding_state'], 'DOCUMENTED')
        self.assertEqual({r.kind for r in response.relations}, {ArgumentRelationKind.REPLIES_TO, ArgumentRelationKind.DEFENDS})
        self.assertEqual(response.next_action, AdvocateNextAction.CONTINUE_CROSS_EXAM)
        graph2,args2,branch2=admit_advocate_response_to_argument_graph(graph=graph,arguments=args,disclosure=disclosure,response=response,actor=self.actor,created_at=self.t)
        self.assertIn(response.argument.meta.id,graph2.argument_ids)
        self.assertEqual(branch2.head_argument_id,response.argument.meta.id)
        self.assertEqual(len(parent["children"]), 1)

    def test_model_prior_cannot_materialize_defend_and_routes_to_research(self):
        response, receipt, _, graph, args, disclosure = self.execute("advocate-prior-only")
        self.assertEqual(receipt.status, ProviderExecutionStatus.COMPLETED)
        self.assertEqual(response.outcome, AdvocateOutcome.REQUEST_EVIDENCE)
        self.assertEqual(response.argument.grounding_state, ResponseGroundingState.MODEL_PRIOR_ONLY)
        self.assertEqual([r.kind for r in response.relations], [ArgumentRelationKind.REPLIES_TO])
        self.assertEqual(response.next_action, AdvocateNextAction.REQUEST_LOCAL_RESEARCH)
        self.assertTrue(response.argument.additional_evidence_requests)
        graph2,_,_=admit_advocate_response_to_argument_graph(graph=graph,arguments=args,disclosure=disclosure,response=response,actor=self.actor,created_at=self.t)
        self.assertIn(response.argument.meta.id,graph2.argument_ids)
        self.assertFalse(any(r.kind is ArgumentRelationKind.DEFENDS for r in response.relations))

    def test_live_advocate_hidden_sibling_grounding_is_rejected(self):
        graph, args, disclosure, contract, binding, envelope = self.fixture()
        transport = SubprocessJsonProviderTransport({
            "test.advocate": (sys.executable, str(self.root / "tests/researcher/fixtures/tribunal_live_provider_stub.py"), "advocate-hidden", str(self.e_hidden))
        })
        with tempfile.TemporaryDirectory() as raw:
            td = Path(raw); parent = td / "parent.json"
            job_ctl.save(job_ctl.create("l3b-hidden-parent", {"schema": "fixture/1.0"}, ["tribunal"]), parent)
            runtime = JobCtlLiveDialogueAdapter(state_dir=td / "jobs", artifact_dir=td / "artifacts", timeout_seconds=5)
            with self.assertRaises(TribunalLiveDialogueError):
                runtime.execute_defense(parent_state_path=parent, binding=binding, envelope=envelope, current_preflight=self.preflight, transport=transport, contract=contract, disclosure=disclosure, id_factory=self.ids, actor=self.actor, created_at=self.t)
            p = job_ctl.load(parent)
            self.assertEqual(p["children"][0]["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
