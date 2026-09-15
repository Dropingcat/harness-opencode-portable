"""
P4 live E2E: Tribunal Q1 via the native plugin transport.

Runs the real JobCtlLiveDialogueAdapter.execute_question with
PluginBridgeProviderTransport wired to a fake plugin bridge (the plugin returns
the structured question draft in text, as the real model would after a child
session). Proves Core -> transport -> bridge -> plugin -> Core admission.
Mirrors test_r4_4_l3_live_dialogue_e2e structure.
"""
from __future__ import annotations

import json
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_root / "scripts"))
sys.path.insert(0, str(_root / "scripts" / "researcher"))

from scripts.jobs import job_ctl
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityIdFactory
from researcher_core.tribunal_argument_graph import ArgumentRelation, ArgumentRelationKind, build_argument_graph
from researcher_core.tribunal_composition import AssessmentNeedRef, load_tribunal_composition_policy
from researcher_core.tribunal_dialectic import DialecticAction, new_branch_history, observe_branch_dialectic_step
from researcher_core.tribunal_disclosure import (
    DisclosurePurpose,
    QuestionPurpose,
    compile_branch_ref,
    compile_dialectic_disclosure,
    compile_question_contract,
)
from researcher_core.tribunal_inquiry import (
    ArgumentArtifact,
    ArgumentPosition,
    InquiryTurn,
    InquiryTurnKind,
    argument_artifact_to_dict,
    inquiry_turn_to_dict,
)
from researcher_core.tribunal_live_dialogue import (
    JobCtlLiveDialogueAdapter,
    PluginBridgeProviderTransport,
    compile_execution_envelope,
)
from researcher_core.tribunal_provider_binding import (
    compile_question_provider_binding,
    load_provider_binding_policy,
)
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self) -> int:
        return 1789413000000


class _PluginBridge:
    """Fake plugin bridge: returns a valid tribunal-question-draft/1.0 in text."""

    def __init__(self) -> None:
        self.requests: list[dict] = []

    def handle(self, method: str, params: dict) -> dict:
        assert method == "semantic.execute"
        req = json.loads(params["request"])
        self.requests.append(req)
        draft = json.dumps(
            {"schema": "tribunal-question-draft/1.0", "question": "Which disclosed observation discriminates the competing explanation?"},
            ensure_ascii=False,
        )
        return {"tool_result": {"ok": True, "runtime_status": "COMPLETED", "structured_output": {"text": draft}}}


@pytest.fixture()
def ctx():
    class Ctx:
        pass

    c = Ctx()
    c.root = _root
    c.policy = load_tribunal_composition_policy(_root / "config" / "tribunal_composition.yaml")
    c.handbook = load_role_handbook(_root / "config" / "tribunal_role_handbook.yaml", c.policy)
    c.binding_policy = load_provider_binding_policy(_root / "config" / "tribunal_provider_binding.yaml")
    c.ids = EntityIdFactory(Clock(), random.Random(94431))
    c.actor = ActorRef("AGENT", "researcher")
    c.run = c.ids.new("RUN")
    c.base_contract = c.ids.new("IQC")
    c.need = AssessmentNeedRef("ANR-p4e2e0000001", 0)
    c.claim = c.ids.new("CLM")
    c.e_support = c.ids.new("EVD")
    c.e_attack = c.ids.new("EVD")
    c.t = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    c.providers = {"providers": {"existing.opencode_tribunal_role": {
        "kind": "agent", "tool": "semantic.execute",
        "provides": ["tribunal.role.execute"], "priority": 120,
        "live_probe": {"kind": "always"},
    }}}
    c.runtime_bindings = {"tools": {"semantic.execute": {"provider": "existing.opencode_tribunal_role"}}}
    c.preflight = {"schema": "capability-preflight/1.0", "network_probes": False,
                   "providers": {"existing.opencode_tribunal_role": {
                       "status": "available", "available": True, "implemented": True,
                       "detail": "plugin-bridge", "kind": "agent",
                       "provides": ["tribunal.role.execute"], "priority": 120}}}
    c.cap_hash = "sha256:p4-e2e-capability-policy"

    def meta(ns, schema, *, entity_id=None, revision=1):
        return EntityMeta(entity_id or c.ids.new(ns), schema, revision, c.run, c.t, c.actor)

    c.meta = meta

    def base_arg(role, pos, text, evd, kind):
        turn = InquiryTurn(c.meta("IQT", "inquiry-turn/1.0"), c.base_contract, role, kind, text, None, (c.claim, evd))
        arg = ArgumentArtifact(c.meta("ARG", "argument-artifact/1.0"), c.base_contract, turn.meta.id, role, pos, (c.need,), text, text + " justification", (evd,), (c.claim,), (), ())
        return turn, arg

    c.base_arg = base_arg
    return c


def test_q1_via_plugin_transport_completes(ctx) -> None:
    root_turn, root = ctx.base_arg("xrd_specialist", ArgumentPosition.QUALIFY, "root interpretation", ctx.e_support, InquiryTurnKind.FIRST_PASS_ASSESSMENT)
    a_turn, attack_a = ctx.base_arg("skeptic", ArgumentPosition.CHALLENGE, "residual stress alternative", ctx.e_attack, InquiryTurnKind.CHALLENGE)
    rel_a = ArgumentRelation(ctx.meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.ATTACKS, attack_a.meta.id, root.meta.id, (ctx.need,), material=True)
    graph1 = build_argument_graph(meta=ctx.meta("AGP", "argument-graph-projection/1.0"), arguments=(root, attack_a), relations=(rel_a,))
    args1 = {x.meta.id: x for x in (root, attack_a)}
    branch = compile_branch_ref(graph=graph1, arguments=args1, anchor_argument_id=attack_a.meta.id, anchor_relation_id=rel_a.meta.id)
    hist = new_branch_history(branch)
    challenge = observe_branch_dialectic_step(branch=branch, argument=attack_a, turn=a_turn, branch_history=hist, visible_refs=(ctx.claim, ctx.e_attack), chain_turn_count=1)
    assert challenge.decision.action == DialecticAction.CONTINUE_QA

    d1 = compile_dialectic_disclosure(
        role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION, branch=branch,
        graph=graph1, arguments=args1, assigned_need_refs=(ctx.need,),
        id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        focus_argument_id=attack_a.meta.id, focus_relation_id=rel_a.meta.id,
    )
    sk = compile_role_instruction_pack(role_id="skeptic", variant=RoleVariantKind.CHALLENGER, handbook=ctx.handbook, policy=ctx.policy)
    q1c = compile_question_contract(
        purpose=QuestionPurpose.DIRECT_QUESTION, role_id="skeptic", disclosure=d1, instruction=sk,
        answer_role_id="xrd_specialist", parent_turn_id=a_turn.meta.id,
        id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        policy_version=ctx.policy.version, policy_hash=ctx.policy.policy_hash,
        target_argument_id=attack_a.meta.id,
    )
    qb = compile_question_provider_binding(
        contract=q1c, requested_role_id=None, composition_policy=ctx.policy,
        binding_policy=ctx.binding_policy, providers_authority=ctx.providers,
        runtime_bindings=ctx.runtime_bindings, preflight=ctx.preflight,
        capability_policy_hash=ctx.cap_hash, id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
    )
    assert qb.status.value == "READY"
    assert qb.selected_runtime_tool == "semantic.execute"

    qp = {x.meta.id: argument_artifact_to_dict(x) for x in (root, attack_a)}
    tp = {x.meta.id: inquiry_turn_to_dict(x) for x in (root_turn, a_turn)}
    refs = {str(ctx.claim): {"kind": "Claim", "text": "BCC interpretation"}, str(ctx.e_support): {"kind": "Evidence", "text": "support"}, str(ctx.e_attack): {"kind": "Evidence", "text": "attack"}}
    qenv = compile_execution_envelope(
        binding=qb, disclosure=d1, question_contract=q1c, instruction=sk,
        argument_payloads=qp, turn_payloads=tp, ref_payloads=refs,
        id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
    )

    plugin = _PluginBridge()
    transport = PluginBridgeProviderTransport(plugin.handle)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        parent_path = td / "parent.json"
        job_ctl.save(job_ctl.create("p4-e2e-parent", {"schema": "fixture/1.0"}, ["tribunal"]), parent_path)
        runtime = JobCtlLiveDialogueAdapter(state_dir=td / "jobs", artifact_dir=td / "artifacts", timeout_seconds=10)
        q1, qrec = runtime.execute_question(
            parent_state_path=parent_path, binding=qb, envelope=qenv,
            current_preflight=ctx.preflight, transport=transport,
            contract=q1c, disclosure=d1, id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )

    assert qrec.status.value == "COMPLETED", qrec.failure_reason
    assert q1.content.strip()
    assert plugin.requests[0]["schema"] == "semantic-execution-request/1.0"
    assert plugin.requests[0]["role_ref"] == "skeptic"