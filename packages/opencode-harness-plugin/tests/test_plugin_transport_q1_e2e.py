"""
P4 deterministic integration: Tribunal Q1/A1/Q2 via the plugin transport adapter.

Runs the real JobCtlLiveDialogueAdapter.execute_question with
PluginBridgeProviderTransport wired to a fake plugin bridge (the plugin returns
the structured question draft in text, as the real model would after a child
session). Exercises Core admission with a fake semantic callback; no real
OpenCode session, model, or stdio bridge is exercised by this test.
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
    admit_live_answer_to_argument_graph,
    compile_execution_envelope,
)
from researcher_core.tribunal_provider_binding import (
    compile_answer_provider_binding,
    compile_question_provider_binding,
    load_provider_binding_policy,
)
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class Clock:
    def now_ms(self) -> int:
        return 1789413000000


class _PluginBridge:
    """Fake plugin bridge: returns the draft matching the request's expected schema."""

    def __init__(self, answer2_mode="repeat") -> None:
        self.requests: list[dict] = []
        self.answer2_mode = answer2_mode

    def handle(self, method: str, params: dict) -> dict:
        assert method == "semantic.execute"
        req = json.loads(params["request"])
        self.requests.append(req)
        bounded = req.get("bounded_input") or {}
        expected = bounded.get("expected_output_schema", "")
        if expected == "tribunal-question-draft/1.0":
            draft = {"schema": "tribunal-question-draft/1.0", "question": "Which disclosed observation discriminates the competing explanation?"}
            if bounded["control_contract"]["purpose"] == "QUESTION_ON_ANSWER":
                draft["question"] = "Which disclosed measurement tests the assumption identified in the previous answer?"
        else:
            draft = {
                "schema": expected,
                "position": "QUALIFY",
                "summary": "The interpretation remains qualified because an alternative explanation is not excluded.",
                "justification": "The disclosed evidence does not independently test the key assumption.",
                "cited_evidence_refs": list(bounded.get("visible_evidence_refs") or []),
                "cited_target_refs": list(bounded.get("visible_target_refs") or []),
                "discoveries": [{"kind": "ASSUMPTION_ISSUE", "statement": "assumes alternative is negligible", "target_refs": list(bounded.get("visible_target_refs") or []), "evidence_refs": list(bounded.get("visible_evidence_refs") or []), "blocking": False}],
                "additional_evidence_requests": [],
                "grounding": [{"kind": "DISCLOSED_EVIDENCE", "statement": "Uses disclosed evidence.", "refs": list(bounded.get("visible_evidence_refs") or [])}],
            }
        if expected == "tribunal-answer-draft/1.1" and bounded["control_contract"]["purpose"] == "QUESTION_ON_ANSWER":
            if self.answer2_mode == "novel":
                draft["discoveries"][0]["statement"] = "Calibration stability is a distinct untested assumption."
            if self.answer2_mode == "research":
                draft["position"] = "OPEN"
                draft["discoveries"] = []
                draft["additional_evidence_requests"] = [{
                    "question": "Obtain an independent stress-sensitive measurement.",
                    "reason": "Disclosed observations cannot distinguish the alternatives.",
                    "target_refs": list(bounded["visible_target_refs"]),
                    "requested_evidence_kinds": ["stress-sensitive XRD"],
                }]
            draft["grounding"].append({
                "kind": "PRIOR_TURN", "statement": "Answers the disclosed Q2.",
                "refs": [bounded["question_turn_id"]],
            })
        return {"tool_result": {"ok": True, "runtime_status": "COMPLETED", "structured_output": {"text": json.dumps(draft, ensure_ascii=False)}}}


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


@pytest.mark.parametrize("answer2_mode, expected_action", [
    ("repeat", DialecticAction.STOP_NO_PROGRESS),
    ("research", DialecticAction.REQUEST_LOCAL_RESEARCH),
    ("novel", DialecticAction.STOP_DEPTH_LIMIT),
])
def test_q1_a1_q2_a2_and_observer_decision(ctx, answer2_mode, expected_action) -> None:
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

    plugin = _PluginBridge(answer2_mode)
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

        # ---- A1: answer via the same plugin transport ----
        answer_instruction = compile_role_instruction_pack(role_id="xrd_specialist", variant=RoleVariantKind.CROSS_EXAM, handbook=ctx.handbook, policy=ctx.policy)
        ab = compile_answer_provider_binding(
            contract=q1c, target_argument=attack_a, requested_role_id=None,
            composition_policy=ctx.policy, binding_policy=ctx.binding_policy,
            providers_authority=ctx.providers, runtime_bindings=ctx.runtime_bindings,
            preflight=ctx.preflight, capability_policy_hash=ctx.cap_hash,
            id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        assert ab.status.value == "READY"
        assert ab.selected_runtime_tool == "semantic.execute"

        tp1 = {**tp, q1.meta.id: inquiry_turn_to_dict(q1)}
        aenv = compile_execution_envelope(
            binding=ab, disclosure=d1, question_contract=q1c, instruction=answer_instruction,
            argument_payloads=qp, turn_payloads=tp1, ref_payloads=refs,
            question_turn=q1, id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        a1, a1arg, arec = runtime.execute_answer(
            parent_state_path=parent_path, binding=ab, envelope=aenv,
            current_preflight=ctx.preflight, transport=transport,
            contract=q1c, disclosure=d1, question_turn=q1,
            id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        assert arec.status.value == "COMPLETED", arec.failure_reason
        assert a1arg.position == ArgumentPosition.QUALIFY

        # ---- graph admission ----
        graph2, args2, branch2, reply = admit_live_answer_to_argument_graph(
            graph=graph1, arguments=args1, branch=branch, question_contract=q1c,
            answer_argument=a1arg, id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        assert reply.kind == ArgumentRelationKind.REPLIES_TO

        # Q2 is authorized by the observer's admitted issue, not by the transport.
        step1 = observe_branch_dialectic_step(
            branch=branch2, argument=a1arg, turn=a1,
            branch_history=challenge.next_branch_history,
            visible_refs=(ctx.claim, ctx.e_support, ctx.e_attack), chain_turn_count=3,
        )
        assert step1.decision.action == DialecticAction.CONTINUE_QUESTION_ON_ANSWER
        issue = step1.observation.new_issues[0].signature
        d2 = compile_dialectic_disclosure(
            role_id="methodologist", purpose=DisclosurePurpose.QUESTION_ON_ANSWER,
            branch=branch2, graph=graph2, arguments=args2,
            assigned_need_refs=(ctx.need,), id_factory=ctx.ids, actor=ctx.actor,
            created_at=ctx.t, focus_argument_id=a1arg.meta.id,
            focus_turn_id=a1.meta.id, focus_issue_signature=issue,
        )
        instruction2 = compile_role_instruction_pack(
            role_id="methodologist", variant=RoleVariantKind.CROSS_EXAM,
            handbook=ctx.handbook, policy=ctx.policy,
        )
        q2c = compile_question_contract(
            purpose=QuestionPurpose.QUESTION_ON_ANSWER, role_id="methodologist",
            disclosure=d2, instruction=instruction2, answer_role_id="xrd_specialist",
            parent_turn_id=a1.meta.id, id_factory=ctx.ids, actor=ctx.actor,
            created_at=ctx.t, policy_version=ctx.policy.version,
            policy_hash=ctx.policy.policy_hash, target_argument_id=a1arg.meta.id,
            target_turn_id=a1.meta.id, target_issue_signature=issue,
            admitted_new_issue_signatures=tuple(x.signature for x in step1.observation.new_issues),
            expected_closure_surface=("MISSING_EVIDENCE", "RESOLVED"), max_followups=0,
        )
        q2b = compile_question_provider_binding(
            contract=q2c, requested_role_id=None, composition_policy=ctx.policy,
            binding_policy=ctx.binding_policy, providers_authority=ctx.providers,
            runtime_bindings=ctx.runtime_bindings, preflight=ctx.preflight,
            capability_policy_hash=ctx.cap_hash, id_factory=ctx.ids,
            actor=ctx.actor, created_at=ctx.t,
        )
        assert q2b.status.value == "READY"
        assert q2b.meta.id != qb.meta.id
        q2env = compile_execution_envelope(
            binding=q2b, disclosure=d2, question_contract=q2c, instruction=instruction2,
            argument_payloads={k: argument_artifact_to_dict(v) for k, v in args2.items()},
            turn_payloads={**tp1, a1.meta.id: inquiry_turn_to_dict(a1)},
            ref_payloads=refs, id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        assert str(a1arg.meta.id) in q2env.material
        assert str(a1.meta.id) in q2env.material
        q2, q2rec = runtime.execute_question(
            parent_state_path=parent_path, binding=q2b, envelope=q2env,
            current_preflight=ctx.preflight, transport=transport,
            contract=q2c, disclosure=d2, id_factory=ctx.ids, actor=ctx.actor,
            created_at=ctx.t,
        )
        assert q2rec.status.value == "COMPLETED"
        assert q2.kind == InquiryTurnKind.QUESTION_ON_ANSWER
        assert q2.parent_turn_id == a1.meta.id
        assert q2.contract_id == q2c.meta.id
        assert q2.role_id == "methodologist"
        assert q2rec.binding_id == q2b.meta.id
        assert q2rec.envelope_id == q2env.meta.id
        assert (td / "artifacts" / f"{q2rec.meta.id}.json").is_file()
        sent = plugin.requests[2]["bounded_input"]
        assert sent["control_contract"]["target_issue_signature"] == issue
        assert sent["control_contract"]["target_turn_id"] == str(a1.meta.id)
        assert set(sent["material"]) == set(q2env.material)

        a2b = compile_answer_provider_binding(
            contract=q2c, target_argument=a1arg, requested_role_id=None,
            composition_policy=ctx.policy, binding_policy=ctx.binding_policy,
            providers_authority=ctx.providers, runtime_bindings=ctx.runtime_bindings,
            preflight=ctx.preflight, capability_policy_hash=ctx.cap_hash,
            id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        a2env = compile_execution_envelope(
            binding=a2b, disclosure=d2, question_contract=q2c,
            instruction=answer_instruction,
            argument_payloads={k: argument_artifact_to_dict(v) for k, v in args2.items()},
            turn_payloads={**tp1, a1.meta.id: inquiry_turn_to_dict(a1), q2.meta.id: inquiry_turn_to_dict(q2)},
            ref_payloads=refs, question_turn=q2,
            id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        assert a2env.question_turn_id == q2.meta.id
        assert a2env.material[str(q2.meta.id)]["content"] == q2.content
        a2, a2arg, a2rec = runtime.execute_answer(
            parent_state_path=parent_path, binding=a2b, envelope=a2env,
            current_preflight=ctx.preflight, transport=transport,
            contract=q2c, disclosure=d2, question_turn=q2,
            id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        assert a2rec.status.value == "COMPLETED"
        assert a2.parent_turn_id == q2.meta.id
        assert a2.kind == InquiryTurnKind.REBUTTAL
        graph3, args3, branch3, reply2 = admit_live_answer_to_argument_graph(
            graph=graph2, arguments=args2, branch=branch2, question_contract=q2c,
            answer_argument=a2arg, id_factory=ctx.ids, actor=ctx.actor, created_at=ctx.t,
        )
        assert reply2.kind == ArgumentRelationKind.REPLIES_TO
        assert a2arg.meta.id in args3
        step2 = observe_branch_dialectic_step(
            branch=branch3, argument=a2arg, turn=a2,
            branch_history=step1.next_branch_history,
            visible_refs=(ctx.claim, ctx.e_support, ctx.e_attack), chain_turn_count=5,
        )
        assert step2.decision.action == expected_action
        if answer2_mode == "novel":
            assert step2.observation.new_issues
            assert all(x.signature != issue for x in step2.observation.new_issues)
        if answer2_mode == "repeat":
            assert not step2.observation.new_issues
            assert step2.observation.repeated_issue_signatures
        assert (td / "artifacts" / f"{a2rec.meta.id}.json").is_file()

    # No Q3 is executed automatically after a stop/research decision.
    assert len(plugin.requests) == 4
    assert plugin.requests[0]["role_ref"] == "skeptic"
    assert plugin.requests[1]["role_ref"] == "xrd_specialist"
    assert plugin.requests[2]["role_ref"] == "methodologist"
    assert plugin.requests[3]["role_ref"] == "xrd_specialist"
