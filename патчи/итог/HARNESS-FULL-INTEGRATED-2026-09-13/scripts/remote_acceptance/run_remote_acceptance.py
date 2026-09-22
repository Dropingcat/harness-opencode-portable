#!/usr/bin/env python3
"""Remote production-semantic acceptance for R4.4 L3B.

This script is meant to run on the user's real Harness/OpenCode host. It keeps
all credentials on that host, uses the canonical provider-binding path, and
writes a trace bundle that can be returned for review.

It does not edit repository code or authority config.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tarfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts" / "researcher") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts" / "researcher"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jobs import job_ctl
from scripts.router.capability_preflight import snapshot as capability_preflight_snapshot
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.tribunal_advocate import (
    admit_advocate_response_to_argument_graph,
    compile_advocate_defense_contract,
    compile_advocate_disclosure,
    decide_advocate_activation,
)
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
    ProviderExecutionStatus,
    SubprocessJsonProviderTransport,
    admit_live_answer_to_argument_graph,
    compile_advocate_execution_envelope,
    compile_execution_envelope,
    execution_envelope_to_dict,
    provider_execution_receipt_to_dict,
)
from researcher_core.tribunal_provider_binding import (
    compile_answer_provider_binding,
    compile_defense_provider_binding,
    compile_question_provider_binding,
    load_provider_binding_policy,
    role_provider_binding_to_dict,
)
from researcher_core.tribunal_role_handbook import RoleVariantKind, compile_role_instruction_pack, load_role_handbook


class FixedClock:
    def now_ms(self) -> int:
        return 1789299000000


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run(argv: list[str], *, cwd: Path = ROOT, timeout: int = 600) -> dict[str, Any]:
    started = time.time()
    try:
        cp = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "argv": argv,
            "exit_code": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
            "elapsed_s": round(time.time() - started, 3),
        }
    except Exception as exc:
        return {"argv": argv, "error": f"{exc.__class__.__name__}: {exc}", "elapsed_s": round(time.time() - started, 3)}


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _argument_summary(arg: ArgumentArtifact) -> dict[str, Any]:
    return {
        "id": str(arg.meta.id),
        "role_id": arg.role_id,
        "position": arg.position.value,
        "summary": arg.summary,
        "justification": arg.justification,
        "cited_evidence_refs": [str(x) for x in arg.cited_evidence_refs],
        "cited_target_refs": [str(x) for x in arg.cited_target_refs],
        "grounding_state": arg.grounding_state.value,
        "grounding": [
            {"kind": x.kind.value, "statement": x.statement, "refs": [str(r) for r in x.refs]}
            for x in arg.grounding_items
        ],
        "discoveries": [
            {
                "kind": x.kind.value,
                "statement": x.statement,
                "target_refs": [str(r) for r in x.target_refs],
                "evidence_refs": [str(r) for r in x.evidence_refs],
                "blocking": x.blocking,
            }
            for x in arg.discoveries
        ],
        "additional_evidence_requests": [
            {
                "question": x.question,
                "reason": x.reason,
                "target_refs": [str(r) for r in x.target_refs],
                "requested_evidence_kinds": list(x.requested_evidence_kinds),
            }
            for x in arg.additional_evidence_requests
        ],
    }


def _turn_summary(turn: InquiryTurn) -> dict[str, Any]:
    return {
        "id": str(turn.meta.id),
        "role_id": turn.role_id,
        "kind": turn.kind.value,
        "content": turn.content,
        "parent_turn_id": str(turn.parent_turn_id) if turn.parent_turn_id else None,
        "cited_refs": [str(x) for x in turn.cited_refs],
    }


def _provider_transport(opencode_bin: str, model: str, timeout: int, runs_dir: Path, provider_id: str) -> SubprocessJsonProviderTransport:
    worker = ROOT / "scripts" / "remote_acceptance" / "opencode_json_worker.py"
    cmd = (
        sys.executable,
        str(worker),
        "--opencode-bin", opencode_bin,
        "--model", model,
        "--timeout", str(timeout),
        "--runs-dir", str(runs_dir),
    )
    return SubprocessJsonProviderTransport({provider_id: cmd})


def _base_fixture(ids: EntityIdFactory, actor: ActorRef, run_id: EntityId, now: datetime):
    base_contract = ids.new("IQC")
    need = AssessmentNeedRef("ANR-remote-semantic-0001", 0)
    claim = ids.new("CLM")
    e_support = ids.new("EVD")
    e_attack = ids.new("EVD")
    e_hidden = ids.new("EVD")

    def meta(ns: str, schema: str) -> EntityMeta:
        return EntityMeta(ids.new(ns), schema, 1, run_id, now, actor)

    root_turn = InquiryTurn(
        meta("IQT", "inquiry-turn/1.0"), base_contract, "xrd_specialist", InquiryTurnKind.FIRST_PASS_ASSESSMENT,
        "The BCC lattice-parameter change is compatible with a solid-solution composition change, but the interpretation remains qualified.",
        None, (claim, e_support),
    )
    root = ArgumentArtifact(
        meta("ARG", "argument-artifact/1.0"), base_contract, root_turn.meta.id, "xrd_specialist", ArgumentPosition.QUALIFY,
        (need,), "Qualified lattice-parameter interpretation",
        "The disclosed XRD evidence is compatible with composition change, but does not by itself eliminate all stress contributions.",
        (e_support,), (claim,), (), (),
    )
    attack_turn = InquiryTurn(
        meta("IQT", "inquiry-turn/1.0"), base_contract, "skeptic", InquiryTurnKind.CHALLENGE,
        "Residual stress may explain part of the observed lattice-parameter shift.", None, (claim, e_attack),
    )
    attack = ArgumentArtifact(
        meta("ARG", "argument-artifact/1.0"), base_contract, attack_turn.meta.id, "skeptic", ArgumentPosition.CHALLENGE,
        (need,), "Residual-stress alternative",
        "The current evidence does not independently separate composition and residual-stress contributions.",
        (e_attack,), (claim,), (), (),
    )
    sibling_turn = InquiryTurn(
        meta("IQT", "inquiry-turn/1.0"), base_contract, "methodologist", InquiryTurnKind.CHALLENGE,
        "A calibration issue is investigated in a sibling branch and must remain hidden here.", None, (claim, e_hidden),
    )
    sibling = ArgumentArtifact(
        meta("ARG", "argument-artifact/1.0"), base_contract, sibling_turn.meta.id, "methodologist", ArgumentPosition.CHALLENGE,
        (need,), "Hidden sibling calibration branch",
        "This material exists only to test branch isolation and must not leak into the selected dialogue branch.",
        (e_hidden,), (claim,), (), (),
    )
    rel_attack = ArgumentRelation(meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.ATTACKS, attack.meta.id, root.meta.id, (need,), material=True)
    rel_hidden = ArgumentRelation(meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.UNDERCUTS, sibling.meta.id, root.meta.id, (need,), material=True)
    graph = build_argument_graph(meta=meta("AGP", "argument-graph-projection/1.0"), arguments=(root, attack, sibling), relations=(rel_attack, rel_hidden))
    arguments = {x.meta.id: x for x in (root, attack, sibling)}
    turns = {x.meta.id: x for x in (root_turn, attack_turn, sibling_turn)}
    refs = {
        claim: {
            "kind": "Claim",
            "text": "Observed BCC lattice-parameter change is interpreted primarily as a solid-solution composition effect under the stated treatment scope.",
        },
        e_support: {
            "kind": "Evidence",
            "text": "Visible evidence: the measured BCC lattice parameter changes reproducibly across the treatment series. This evidence is compatible with a composition contribution but is not stress-selective.",
            "locator": "REMOTE_SYNTHETIC:EVD_SUPPORT",
        },
        e_attack: {
            "kind": "Evidence",
            "text": "Visible counterevidence: residual stress is not independently measured in this bounded record, so a stress contribution cannot be excluded from the observed shift.",
            "locator": "REMOTE_SYNTHETIC:EVD_ATTACK",
        },
        e_hidden: {
            "kind": "Evidence",
            "text": "HIDDEN SIBLING MATERIAL. If this appears in the selected branch provider input, disclosure isolation failed.",
            "locator": "REMOTE_SYNTHETIC:EVD_HIDDEN",
        },
    }
    return {
        "base_contract": base_contract, "need": need, "claim": claim, "e_support": e_support, "e_attack": e_attack, "e_hidden": e_hidden,
        "root_turn": root_turn, "root": root, "attack_turn": attack_turn, "attack": attack, "sibling_turn": sibling_turn, "sibling": sibling,
        "rel_attack": rel_attack, "rel_hidden": rel_hidden, "graph": graph, "arguments": arguments, "turns": turns, "refs": refs,
    }


def _authority_context() -> tuple[dict, dict, dict, str]:
    providers = _json_load(ROOT / "config" / "providers_authority.json")
    runtime_bindings = _json_load(ROOT / "config" / "tool_runtime_bindings.json")
    preflight = capability_preflight_snapshot(network=False)
    cap_hash = _json_load(ROOT / "config" / "capability_runtime_snapshot.json")["policy_hash"]
    return providers, runtime_bindings, preflight, cap_hash


def run_bounded_chain(*, out: Path, opencode_bin: str, model: str, timeout: int) -> dict[str, Any]:
    now = datetime(2026, 9, 13, 20, 30, tzinfo=timezone.utc)
    ids = EntityIdFactory(FixedClock(), random.Random(202609132030))
    actor = ActorRef("AGENT", "remote-acceptance")
    run_id = ids.new("RUN")
    fx = _base_fixture(ids, actor, run_id, now)
    policy = load_tribunal_composition_policy(ROOT / "config" / "tribunal_composition.yaml")
    handbook = load_role_handbook(ROOT / "config" / "tribunal_role_handbook.yaml", policy)
    bind_policy = load_provider_binding_policy(ROOT / "config" / "tribunal_provider_binding.yaml")
    providers, runtime_bindings, preflight, cap_hash = _authority_context()

    provider_state = preflight.get("providers", {}).get("existing.opencode_tribunal_role", {})
    if not provider_state.get("available"):
        raise RuntimeError(f"existing.opencode_tribunal_role is not execution-ready: {provider_state}")

    common = dict(
        composition_policy=policy, binding_policy=bind_policy, providers_authority=providers,
        runtime_bindings=runtime_bindings, preflight=preflight, capability_policy_hash=cap_hash,
        id_factory=ids, actor=actor, created_at=now,
    )
    transport = _provider_transport(opencode_bin, model, timeout, out / "opencode_runs", "existing.opencode_tribunal_role")
    runtime = JobCtlLiveDialogueAdapter(state_dir=out / "jobs", artifact_dir=out / "artifacts", timeout_seconds=timeout)
    parent_path = out / "parent_job.json"
    job_ctl.save(job_ctl.create("remote-semantic-parent", {"schema": "remote-semantic-acceptance/1.0"}, ["tribunal"]), parent_path)

    graph1 = fx["graph"]
    args1 = fx["arguments"]
    branch = compile_branch_ref(graph=graph1, arguments=args1, anchor_argument_id=fx["attack"].meta.id, anchor_relation_id=fx["rel_attack"].meta.id)
    hist = new_branch_history(branch)
    challenge_step = observe_branch_dialectic_step(
        branch=branch, argument=fx["attack"], turn=fx["attack_turn"], branch_history=hist,
        visible_refs=(fx["claim"], fx["e_attack"]), chain_turn_count=1,
    )
    d1 = compile_dialectic_disclosure(
        role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION, branch=branch, graph=graph1, arguments=args1,
        assigned_need_refs=(fx["need"],), id_factory=ids, actor=actor, created_at=now,
        focus_argument_id=fx["attack"].meta.id, focus_relation_id=fx["rel_attack"].meta.id,
    )
    skeptic_instruction = compile_role_instruction_pack(role_id="skeptic", variant=RoleVariantKind.CHALLENGER, handbook=handbook, policy=policy)
    q1c = compile_question_contract(
        purpose=QuestionPurpose.DIRECT_QUESTION, role_id="skeptic", answer_role_id="xrd_specialist",
        disclosure=d1, instruction=skeptic_instruction, parent_turn_id=fx["attack_turn"].meta.id,
        id_factory=ids, actor=actor, created_at=now, policy_version=policy.version, policy_hash=policy.policy_hash,
        target_argument_id=fx["attack"].meta.id, expected_closure_surface=("ASSUMPTION_ISSUE", "MISSING_EVIDENCE"),
    )
    qb = compile_question_provider_binding(contract=q1c, requested_role_id=None, **common)
    arg_payloads = {k: argument_artifact_to_dict(v) for k, v in args1.items()}
    turn_payloads = {k: inquiry_turn_to_dict(v) for k, v in fx["turns"].items()}
    q1env = compile_execution_envelope(
        binding=qb, disclosure=d1, question_contract=q1c, instruction=skeptic_instruction,
        argument_payloads=arg_payloads, turn_payloads=turn_payloads, ref_payloads=fx["refs"],
        id_factory=ids, actor=actor, created_at=now,
    )
    if str(fx["e_hidden"]) in q1env.material:
        raise RuntimeError("hidden sibling evidence leaked into Q1 TEX")
    q1, q1receipt = runtime.execute_question(
        parent_state_path=parent_path, binding=qb, envelope=q1env, current_preflight=preflight, transport=transport,
        contract=q1c, disclosure=d1, id_factory=ids, actor=actor, created_at=now,
    )

    answer_instruction = compile_role_instruction_pack(role_id="xrd_specialist", variant=RoleVariantKind.CROSS_EXAM, handbook=handbook, policy=policy)
    ab = compile_answer_provider_binding(contract=q1c, target_argument=fx["attack"], requested_role_id=None, **common)
    a1env = compile_execution_envelope(
        binding=ab, disclosure=d1, question_contract=q1c, instruction=answer_instruction,
        argument_payloads=arg_payloads, turn_payloads={**turn_payloads, q1.meta.id: inquiry_turn_to_dict(q1)},
        ref_payloads=fx["refs"], question_turn=q1, id_factory=ids, actor=actor, created_at=now,
    )
    if a1env.question_turn_id != q1.meta.id or str(q1.meta.id) not in a1env.material:
        raise RuntimeError("answer TEX does not contain the materialized Q1")
    a1, a1arg, a1receipt = runtime.execute_answer(
        parent_state_path=parent_path, binding=ab, envelope=a1env, current_preflight=preflight, transport=transport,
        contract=q1c, disclosure=d1, question_turn=q1, id_factory=ids, actor=actor, created_at=now,
    )
    graph2, args2, branch2, reply1 = admit_live_answer_to_argument_graph(
        graph=graph1, arguments=args1, branch=branch, question_contract=q1c, answer_argument=a1arg,
        id_factory=ids, actor=actor, created_at=now,
    )
    step1 = observe_branch_dialectic_step(
        branch=branch2, argument=a1arg, turn=a1, branch_history=challenge_step.next_branch_history,
        visible_refs=(fx["claim"], fx["e_support"], fx["e_attack"]), chain_turn_count=3,
    )

    q2_block: dict[str, Any] = {"executed": False, "observer_action_after_a1": step1.decision.action.value}
    graph_after = graph2
    args_after = args2
    branch_after = branch2
    if step1.decision.action is DialecticAction.CONTINUE_QUESTION_ON_ANSWER and step1.observation.new_issues:
        issue = step1.observation.new_issues[0].signature
        d2 = compile_dialectic_disclosure(
            role_id="methodologist", purpose=DisclosurePurpose.QUESTION_ON_ANSWER, branch=branch2, graph=graph2, arguments=args2,
            assigned_need_refs=(fx["need"],), id_factory=ids, actor=actor, created_at=now,
            focus_argument_id=a1arg.meta.id, focus_turn_id=a1.meta.id, focus_issue_signature=issue,
        )
        method_instruction = compile_role_instruction_pack(role_id="methodologist", variant=RoleVariantKind.CROSS_EXAM, handbook=handbook, policy=policy)
        q2c = compile_question_contract(
            purpose=QuestionPurpose.QUESTION_ON_ANSWER, role_id="methodologist", answer_role_id="xrd_specialist",
            disclosure=d2, instruction=method_instruction, parent_turn_id=a1.meta.id,
            id_factory=ids, actor=actor, created_at=now, policy_version=policy.version, policy_hash=policy.policy_hash,
            target_argument_id=a1arg.meta.id, target_turn_id=a1.meta.id, target_issue_signature=issue,
            admitted_new_issue_signatures=tuple(x.signature for x in step1.observation.new_issues),
            expected_closure_surface=("MISSING_EVIDENCE", "RESOLVED"), max_followups=0,
        )
        q2b = compile_question_provider_binding(contract=q2c, requested_role_id=None, **common)
        q2env = compile_execution_envelope(
            binding=q2b, disclosure=d2, question_contract=q2c, instruction=method_instruction,
            argument_payloads={k: argument_artifact_to_dict(v) for k, v in args2.items()},
            turn_payloads={**turn_payloads, q1.meta.id: inquiry_turn_to_dict(q1), a1.meta.id: inquiry_turn_to_dict(a1)},
            ref_payloads=fx["refs"], id_factory=ids, actor=actor, created_at=now,
        )
        q2, q2receipt = runtime.execute_question(
            parent_state_path=parent_path, binding=q2b, envelope=q2env, current_preflight=preflight, transport=transport,
            contract=q2c, disclosure=d2, id_factory=ids, actor=actor, created_at=now,
        )
        a2b = compile_answer_provider_binding(contract=q2c, target_argument=a1arg, requested_role_id=None, **common)
        a2env = compile_execution_envelope(
            binding=a2b, disclosure=d2, question_contract=q2c, instruction=answer_instruction,
            argument_payloads={k: argument_artifact_to_dict(v) for k, v in args2.items()},
            turn_payloads={**turn_payloads, q1.meta.id: inquiry_turn_to_dict(q1), a1.meta.id: inquiry_turn_to_dict(a1), q2.meta.id: inquiry_turn_to_dict(q2)},
            ref_payloads=fx["refs"], question_turn=q2, id_factory=ids, actor=actor, created_at=now,
        )
        a2, a2arg, a2receipt = runtime.execute_answer(
            parent_state_path=parent_path, binding=a2b, envelope=a2env, current_preflight=preflight, transport=transport,
            contract=q2c, disclosure=d2, question_turn=q2, id_factory=ids, actor=actor, created_at=now,
        )
        graph3, args3, branch3, reply2 = admit_live_answer_to_argument_graph(
            graph=graph2, arguments=args2, branch=branch2, question_contract=q2c, answer_argument=a2arg,
            id_factory=ids, actor=actor, created_at=now,
        )
        step2 = observe_branch_dialectic_step(
            branch=branch3, argument=a2arg, turn=a2, branch_history=step1.next_branch_history,
            visible_refs=(fx["claim"], fx["e_support"], fx["e_attack"]), chain_turn_count=5,
        )
        graph_after, args_after, branch_after = graph3, args3, branch3
        q2_block = {
            "executed": True,
            "target_issue_signature": issue,
            "question": _turn_summary(q2),
            "answer": _argument_summary(a2arg),
            "q2_receipt": provider_execution_receipt_to_dict(q2receipt),
            "a2_receipt": provider_execution_receipt_to_dict(a2receipt),
            "reply_relation_id": str(reply2.meta.id),
            "observer_action_after_a2": step2.decision.action.value,
            "new_issues_after_a2": [x.signature for x in step2.observation.new_issues],
        }

    # Conditional Advocate runs against the original material attack branch. It
    # uses the same production provider/runtime path as the question/answer roles.
    activation = decide_advocate_activation(graph=graph1, arguments=args1, challenge_relation=fx["rel_attack"], composition_policy=policy)
    advocate_block: dict[str, Any] = {"activated": bool(activation.activate), "reason_codes": list(activation.reason_codes)}
    if activation.activate:
        adv_disclosure = compile_advocate_disclosure(activation=activation, graph=graph1, arguments=args1, id_factory=ids, actor=actor, created_at=now)
        adv_instruction = compile_role_instruction_pack(role_id="advocate", variant=RoleVariantKind.DEFENSE, handbook=handbook, policy=policy)
        adc = compile_advocate_defense_contract(
            activation=activation, disclosure=adv_disclosure, composition_policy=policy, instruction=adv_instruction,
            id_factory=ids, actor=actor, created_at=now,
        )
        adv_binding = compile_defense_provider_binding(contract=adc, requested_role_id=None, **common)
        adv_env = compile_advocate_execution_envelope(
            binding=adv_binding, disclosure=adv_disclosure, contract=adc, instruction=adv_instruction,
            argument_payloads={k: argument_artifact_to_dict(v) for k, v in args1.items()},
            turn_payloads={k: inquiry_turn_to_dict(v) for k, v in fx["turns"].items()},
            ref_payloads=fx["refs"], id_factory=ids, actor=actor, created_at=now,
        )
        response, adv_receipt = runtime.execute_defense(
            parent_state_path=parent_path, binding=adv_binding, envelope=adv_env, current_preflight=preflight, transport=transport,
            contract=adc, disclosure=adv_disclosure, id_factory=ids, actor=actor, created_at=now,
        )
        graph_adv, _, branch_adv = admit_advocate_response_to_argument_graph(
            graph=graph1, arguments=args1, disclosure=adv_disclosure, response=response, actor=actor, created_at=now,
        )
        advocate_block.update({
            "binding": role_provider_binding_to_dict(adv_binding),
            "envelope": execution_envelope_to_dict(adv_env),
            "receipt": provider_execution_receipt_to_dict(adv_receipt),
            "outcome": response.outcome.value,
            "next_action": response.next_action.value,
            "argument": _argument_summary(response.argument),
            "relations": [{"id": str(r.meta.id), "kind": r.kind.value, "source": str(r.source_argument_id), "target": str(r.target_argument_id)} for r in response.relations],
            "admitted_graph_revision": graph_adv.meta.revision,
            "branch_head": str(branch_adv.head_argument_id),
        })

    result = {
        "schema": "harness-remote-semantic-trace/1.0",
        "case": "bounded_xrd_dialogue_and_conditional_advocate",
        "root_claim_id": str(fx["claim"]),
        "branch_key": branch.branch_key,
        "selected_provider": qb.selected_provider_id,
        "provider_state": provider_state,
        "q1": {
            "binding": role_provider_binding_to_dict(qb),
            "envelope": execution_envelope_to_dict(q1env),
            "turn": _turn_summary(q1),
            "receipt": provider_execution_receipt_to_dict(q1receipt),
        },
        "a1": {
            "binding": role_provider_binding_to_dict(ab),
            "envelope": execution_envelope_to_dict(a1env),
            "turn": _turn_summary(a1),
            "argument": _argument_summary(a1arg),
            "receipt": provider_execution_receipt_to_dict(a1receipt),
            "reply_relation_id": str(reply1.meta.id),
        },
        "observer_after_a1": {
            "action": step1.decision.action.value,
            "new_issues": [x.signature for x in step1.observation.new_issues],
        },
        "q2_a2": q2_block,
        "advocate": advocate_block,
        "branch_final": {
            "argument_graph_id": str(graph_after.meta.id),
            "graph_revision": graph_after.meta.revision,
            "graph_fingerprint": graph_after.graph_fingerprint,
            "head_argument_id": str(branch_after.head_argument_id),
        },
        "hidden_sibling_ref": str(fx["e_hidden"]),
        "hidden_sibling_present_in_q1_tex": str(fx["e_hidden"]) in q1env.material,
        "hidden_sibling_present_in_a1_tex": str(fx["e_hidden"]) in a1env.material,
        "parent_job": job_ctl.load(parent_path),
    }
    _write(out / "semantic_trace.json", result)
    return result


def run_prior_only_case(*, out: Path, opencode_bin: str, model: str, timeout: int) -> dict[str, Any]:
    """A bounded case with no disclosed EVD refs.

    A useful provider should return OPEN/REQUEST_EVIDENCE or explicitly label
    MODEL_PRIOR/EXPLICIT_ASSUMPTION. Fabricated evidence refs are rejected by
    deterministic admission.
    """
    now = datetime(2026, 9, 13, 20, 40, tzinfo=timezone.utc)
    ids = EntityIdFactory(FixedClock(), random.Random(202609132040))
    actor = ActorRef("AGENT", "remote-acceptance")
    run_id = ids.new("RUN")
    base = ids.new("IQC")
    need = AssessmentNeedRef("ANR-remote-prior-0001", 0)
    claim = ids.new("CLM")

    def meta(ns: str, schema: str) -> EntityMeta:
        return EntityMeta(ids.new(ns), schema, 1, run_id, now, actor)

    root_turn = InquiryTurn(meta("IQT", "inquiry-turn/1.0"), base, "xrd_specialist", InquiryTurnKind.FIRST_PASS_ASSESSMENT, "A mechanism is proposed, but no external evidence is disclosed in this case.", None, (claim,))
    root = ArgumentArtifact(meta("ARG", "argument-artifact/1.0"), base, root_turn.meta.id, "xrd_specialist", ArgumentPosition.OPEN, (need,), "Unverified mechanism hypothesis", "No bounded evidence is available in this test case.", (), (claim,), (), ())
    ch_turn = InquiryTurn(meta("IQT", "inquiry-turn/1.0"), base, "skeptic", InquiryTurnKind.CHALLENGE, "What justifies the proposed mechanism if no evidence is disclosed?", None, (claim,))
    ch = ArgumentArtifact(meta("ARG", "argument-artifact/1.0"), base, ch_turn.meta.id, "skeptic", ArgumentPosition.CHALLENGE, (need,), "Evidence challenge", "The mechanism lacks disclosed evidence.", (), (claim,), (), ())
    rel = ArgumentRelation(meta("ARL", "argument-relation/1.0"), ArgumentRelationKind.ATTACKS, ch.meta.id, root.meta.id, (need,), material=True)
    graph = build_argument_graph(meta=meta("AGP", "argument-graph-projection/1.0"), arguments=(root, ch), relations=(rel,))
    arguments = {root.meta.id: root, ch.meta.id: ch}
    branch = compile_branch_ref(graph=graph, arguments=arguments, anchor_argument_id=ch.meta.id, anchor_relation_id=rel.meta.id)
    policy = load_tribunal_composition_policy(ROOT / "config" / "tribunal_composition.yaml")
    handbook = load_role_handbook(ROOT / "config" / "tribunal_role_handbook.yaml", policy)
    bind_policy = load_provider_binding_policy(ROOT / "config" / "tribunal_provider_binding.yaml")
    providers, runtime_bindings, preflight, cap_hash = _authority_context()
    common = dict(composition_policy=policy, binding_policy=bind_policy, providers_authority=providers, runtime_bindings=runtime_bindings, preflight=preflight, capability_policy_hash=cap_hash, id_factory=ids, actor=actor, created_at=now)
    ddc = compile_dialectic_disclosure(role_id="skeptic", purpose=DisclosurePurpose.DIRECT_QUESTION, branch=branch, graph=graph, arguments=arguments, assigned_need_refs=(need,), id_factory=ids, actor=actor, created_at=now, focus_argument_id=ch.meta.id, focus_relation_id=rel.meta.id)
    qinst = compile_role_instruction_pack(role_id="skeptic", variant=RoleVariantKind.CHALLENGER, handbook=handbook, policy=policy)
    dqc = compile_question_contract(purpose=QuestionPurpose.DIRECT_QUESTION, role_id="skeptic", answer_role_id="xrd_specialist", disclosure=ddc, instruction=qinst, parent_turn_id=ch_turn.meta.id, id_factory=ids, actor=actor, created_at=now, policy_version=policy.version, policy_hash=policy.policy_hash, target_argument_id=ch.meta.id, expected_closure_surface=("MISSING_EVIDENCE",))
    qb = compile_question_provider_binding(contract=dqc, requested_role_id=None, **common)
    transport = _provider_transport(opencode_bin, model, timeout, out / "opencode_runs", "existing.opencode_tribunal_role")
    runtime = JobCtlLiveDialogueAdapter(state_dir=out / "jobs", artifact_dir=out / "artifacts", timeout_seconds=timeout)
    parent = out / "parent_job.json"; job_ctl.save(job_ctl.create("remote-prior-parent", {"schema":"remote-semantic-acceptance/1.0"}, ["tribunal"]), parent)
    refs = {claim: {"kind":"Claim", "text":"A mechanism is proposed without disclosed external evidence."}}
    ap = {k: argument_artifact_to_dict(v) for k,v in arguments.items()}
    tp = {root_turn.meta.id: inquiry_turn_to_dict(root_turn), ch_turn.meta.id: inquiry_turn_to_dict(ch_turn)}
    qenv = compile_execution_envelope(binding=qb, disclosure=ddc, question_contract=dqc, instruction=qinst, argument_payloads=ap, turn_payloads=tp, ref_payloads=refs, id_factory=ids, actor=actor, created_at=now)
    q, qrec = runtime.execute_question(parent_state_path=parent, binding=qb, envelope=qenv, current_preflight=preflight, transport=transport, contract=dqc, disclosure=ddc, id_factory=ids, actor=actor, created_at=now)
    ainst = compile_role_instruction_pack(role_id="xrd_specialist", variant=RoleVariantKind.CROSS_EXAM, handbook=handbook, policy=policy)
    ab = compile_answer_provider_binding(contract=dqc, target_argument=ch, requested_role_id=None, **common)
    aenv = compile_execution_envelope(binding=ab, disclosure=ddc, question_contract=dqc, instruction=ainst, argument_payloads=ap, turn_payloads={**tp, q.meta.id: inquiry_turn_to_dict(q)}, ref_payloads=refs, question_turn=q, id_factory=ids, actor=actor, created_at=now)
    answer, arg, arec = runtime.execute_answer(parent_state_path=parent, binding=ab, envelope=aenv, current_preflight=preflight, transport=transport, contract=dqc, disclosure=ddc, question_turn=q, id_factory=ids, actor=actor, created_at=now)
    result = {
        "schema":"harness-remote-semantic-prior-test/1.0",
        "question": _turn_summary(q),
        "answer": _argument_summary(arg),
        "q_receipt": provider_execution_receipt_to_dict(qrec),
        "a_receipt": provider_execution_receipt_to_dict(arec),
        "allowed_evidence_refs": [],
        "pass_condition": {
            "no_fabricated_evidence_refs": not bool(arg.cited_evidence_refs),
            "research_debt_if_non_open": (arg.position is ArgumentPosition.OPEN) or bool(arg.additional_evidence_requests) or any(x.blocking for x in arg.discoveries),
        },
    }
    _write(out / "prior_only_trace.json", result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Run deterministic + real OpenCode remote acceptance")
    ap.add_argument("--model", required=True, help="Exact OpenCode model id used in production")
    ap.add_argument("--opencode-bin", default=os.environ.get("OPENCODE_BIN", "opencode"))
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--output", default="remote_acceptance_runs/latest")
    ap.add_argument("--skip-baseline", action="store_true")
    ap.add_argument("--skip-semantic", action="store_true")
    ap.add_argument("--archive", action="store_true", help="Create tar.gz of the output directory")
    args = ap.parse_args()

    out = (ROOT / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema": "harness-remote-acceptance-report/1.0",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "repo": str(ROOT),
        "model": args.model,
        "opencode_bin": args.opencode_bin,
        "cases": {},
    }

    # Environment and integrity snapshot.
    env_cmd = [sys.executable, str(ROOT / "scripts" / "remote_acceptance" / "collect_environment.py"), "--repo", str(ROOT), "--opencode-bin", args.opencode_bin, "--output", str(out / "environment.json")]
    report["environment_command"] = _run(env_cmd, timeout=60)
    report["git_head"] = _run(["git", "rev-parse", "HEAD"])
    report["git_status"] = _run(["git", "status", "--short"])

    if not args.skip_baseline:
        report["cases"]["baseline_r4"] = _run([sys.executable, "scripts/run_researcher_acceptance.py", "r4"], timeout=900)
        report["cases"]["baseline_gates"] = _run([sys.executable, "scripts/run_researcher_acceptance.py", "gates"], timeout=900)
        preflight_path = out / "capability_preflight.json"
        report["cases"]["preflight"] = _run([sys.executable, "scripts/router/capability_preflight.py", "--no-network", "--output", str(preflight_path)], timeout=120)

    if not args.skip_semantic:
        try:
            report["cases"]["semantic_bounded_chain"] = {"ok": True, "trace": run_bounded_chain(out=out / "semantic_bounded_chain", opencode_bin=args.opencode_bin, model=args.model, timeout=args.timeout)}
        except Exception as exc:
            report["cases"]["semantic_bounded_chain"] = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
        try:
            prior = run_prior_only_case(out=out / "semantic_prior_only", opencode_bin=args.opencode_bin, model=args.model, timeout=args.timeout)
            report["cases"]["semantic_prior_only"] = {"ok": all(prior["pass_condition"].values()), "trace": prior}
        except Exception as exc:
            report["cases"]["semantic_prior_only"] = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report_path = out / "REMOTE_ACCEPTANCE_REPORT.json"
    _write(report_path, report)

    # Inventory hashes for return-package integrity.
    hashes = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        if path.name == "SHA256SUMS.txt":
            continue
        hashes.append(f"{_sha(path)}  {path.relative_to(out).as_posix()}")
    (out / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")

    if args.archive:
        archive = out.parent / f"{out.name}.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(out, arcname=out.name)
        print(f"archive={archive}")
    print(f"report={report_path}")

    failures = []
    for name, case in report["cases"].items():
        if name.startswith("baseline_") and case.get("exit_code") not in {0, None}:
            failures.append(name)
        if name.startswith("semantic_") and not case.get("ok"):
            failures.append(name)
    if report.get("git_status", {}).get("stdout", "").strip():
        failures.append("dirty_repo")
    if failures:
        print("FAILED_CASES=" + ",".join(failures), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
