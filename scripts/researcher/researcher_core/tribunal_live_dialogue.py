"""R4.4 L3 bounded live dialogue execution.

This module executes one QUESTION or ANSWER through an already admitted
RoleProviderBinding.  It owns no role selection, evidence selection, provider
policy, or epistemic state transition.  Provider output is untrusted until it
passes deterministic DDC/DQC admission.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from scripts.jobs import job_ctl
from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.tribunal_disclosure import (
    DialecticBranchRef,
    DialecticDisclosureContract,
    DialecticQuestionContract,
    materialize_question_turn,
    refresh_branch_ref,
    validate_answer_against_question_contract,
    validate_disclosure_contract_integrity,
    validate_question_contract_integrity,
)
from researcher_core.tribunal_argument_graph import (
    ArgumentGraphProjection,
    ArgumentRelation,
    ArgumentRelationKind,
    append_argument_branch,
)
from researcher_core.tribunal_inquiry import (
    AdditionalEvidenceRequest,
    ArgumentArtifact,
    ArgumentPosition,
    DiscoveryKind,
    InquiryDiscovery,
    InquiryTurn,
    InquiryTurnKind,
    ResponseGroundingItem,
    ResponseGroundingKind,
    ResponseGroundingState,
    characterize_response_grounding,
    argument_artifact_to_dict,
    inquiry_turn_to_dict,
)
from researcher_core.tribunal_advocate import (
    AdvocateDefenseContract,
    AdvocateOutcome,
    AdvocateResponse,
    AdvocateWorkerDraft,
    advocate_defense_contract_to_dict,
    advocate_response_to_dict,
    materialize_advocate_draft,
    validate_advocate_contract_integrity,
)
from researcher_core.tribunal_provider_binding import (
    ProviderBindingStatus,
    RoleExecutionKind,
    RoleProviderBinding,
    assert_binding_execution_ready,
    role_provider_binding_to_dict,
    validate_role_provider_binding_integrity,
)
from researcher_core.tribunal_role_handbook import RoleInstructionPack, role_instruction_pack_to_dict, validate_role_instruction_pack_integrity


class TribunalLiveDialogueError(RuntimeError):
    pass


class TribunalLiveDialogueTimeout(TribunalLiveDialogueError):
    pass


class ProviderExecutionStatus(StrEnum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class TribunalExecutionEnvelope:
    meta: EntityMeta
    binding_id: EntityId
    binding_fingerprint: str
    contract_id: EntityId
    role_id: str
    execution_kind: RoleExecutionKind
    branch_key: str
    disclosure_contract_id: EntityId
    disclosure_fingerprint: str
    instruction_id: str
    instruction_fingerprint: str
    visible_argument_ids: tuple[EntityId, ...]
    visible_turn_ids: tuple[EntityId, ...]
    visible_evidence_refs: tuple[EntityId, ...]
    visible_target_refs: tuple[EntityId, ...]
    control_contract: Mapping[str, Any]
    material: Mapping[str, Mapping[str, Any]]
    question_turn_id: EntityId | None
    max_response_tokens: int
    expected_output_schema: str
    output_contract: Mapping[str, Any]
    envelope_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "TEX":
            raise ValueError("TribunalExecutionEnvelope id must use TEX prefix")
        if self.binding_id.namespace != "RPB":
            raise ValueError("binding_id must use RPB prefix")
        if self.contract_id.namespace not in {"DQC", "IQC", "ADC"}:
            raise ValueError("execution envelope contract must be DQC/IQC/ADC")
        if self.disclosure_contract_id.namespace != "DDC":
            raise ValueError("disclosure_contract_id must use DDC prefix")
        if self.max_response_tokens < 1:
            raise ValueError("max_response_tokens must be positive")
        object.__setattr__(self, "visible_argument_ids", tuple(self.visible_argument_ids))
        object.__setattr__(self, "visible_turn_ids", tuple(self.visible_turn_ids))
        object.__setattr__(self, "visible_evidence_refs", tuple(self.visible_evidence_refs))
        object.__setattr__(self, "visible_target_refs", tuple(self.visible_target_refs))
        object.__setattr__(self, "control_contract", _deep_freeze(dict(self.control_contract)))
        object.__setattr__(self, "material", _deep_freeze({k: dict(v) for k, v in self.material.items()}))
        object.__setattr__(self, "output_contract", _deep_freeze(dict(self.output_contract)))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProviderExecutionReceipt:
    meta: EntityMeta
    binding_id: EntityId
    envelope_id: EntityId
    provider_id: str
    runtime_tool: str
    execution_kind: RoleExecutionKind
    status: ProviderExecutionStatus
    child_job_id: str
    attempt_id: str
    provider_output_hash: str | None
    output_turn_id: EntityId | None
    output_argument_id: EntityId | None
    receipt_fingerprint: str
    failure_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "PER":
            raise ValueError("ProviderExecutionReceipt id must use PER prefix")
        if self.binding_id.namespace != "RPB" or self.envelope_id.namespace != "TEX":
            raise ValueError("receipt binding/envelope ids invalid")
        if not self.receipt_fingerprint.startswith("sha256:"):
            raise ValueError("receipt fingerprint is invalid")
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


class TribunalProviderTransport(Protocol):
    def invoke(self, *, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, timeout_seconds: float) -> Mapping[str, Any]: ...


class LogicalToolProviderTransport:
    """Adapter from RoleProviderBinding to the harness logical-tool runtime.

    The caller supplies the actual logical-tool invoker.  This layer does not
    discover tools or bypass router authority; it forwards only the selected
    runtime tool and the already bounded TEX payload.
    """

    def __init__(self, invoke_tool: Callable[..., Mapping[str, Any]]):
        self._invoke_tool = invoke_tool

    def invoke(self, *, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, timeout_seconds: float) -> Mapping[str, Any]:
        if binding.status is not ProviderBindingStatus.READY or not binding.selected_runtime_tool:
            raise TribunalLiveDialogueError("logical-tool transport requires READY binding/runtime tool")
        result = self._invoke_tool(
            tool_name=binding.selected_runtime_tool,
            provider_id=binding.selected_provider_id,
            arguments={"execution_envelope": execution_envelope_to_dict(envelope)},
            timeout_seconds=timeout_seconds,
        )
        if not isinstance(result, Mapping):
            raise TribunalLiveDialogueError("logical-tool runtime returned non-object result")
        return result


class SubprocessJsonProviderTransport:
    """Real process boundary used by E2E and local adapters.

    Commands receive the execution envelope JSON on stdin and must emit exactly
    one JSON object on stdout.  This is intentionally transport-only; commands
    are not granted role/evidence authority by this class.
    """

    def __init__(self, commands: Mapping[str, Sequence[str]]):
        self.commands = {k: tuple(v) for k, v in commands.items()}

    def invoke(self, *, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, timeout_seconds: float) -> Mapping[str, Any]:
        provider_id = binding.selected_provider_id or ""
        cmd = self.commands.get(provider_id)
        if not cmd:
            raise TribunalLiveDialogueError(f"no transport command for provider:{provider_id}")
        try:
            cp = subprocess.run(
                list(cmd),
                input=json.dumps(execution_envelope_to_dict(envelope), ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TribunalLiveDialogueTimeout(f"provider timed out:{provider_id}") from exc
        if cp.returncode != 0:
            raise TribunalLiveDialogueError(f"provider failed:{provider_id}:exit={cp.returncode}:{cp.stderr.strip()[:500]}")
        try:
            out = json.loads(cp.stdout)
        except json.JSONDecodeError as exc:
            raise TribunalLiveDialogueError(f"provider returned invalid JSON:{provider_id}") from exc
        if not isinstance(out, Mapping):
            raise TribunalLiveDialogueError("provider output must be a JSON object")
        return out


class PluginBridgeProviderTransport:
    """Native OpenCode plugin transport for Tribunal.

    Invokes a model through the plugin's `semantic.execute` (read-only child
    session) instead of a subprocess CLI.  `reverse_call(method, params)` is the
    bridge peer's full-duplex channel to the plugin; it must be wired by the
    caller.  Transport-only: no role/evidence authority here.
    """

    def __init__(self, reverse_call: Callable[[str, dict[str, Any]], Any]):
        self._reverse_call = reverse_call

    def invoke(self, *, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, timeout_seconds: float) -> Mapping[str, Any]:
        if binding.status is not ProviderBindingStatus.READY:
            raise TribunalLiveDialogueError("plugin-bridge transport requires READY binding")
        envelope_dict = execution_envelope_to_dict(envelope)
        request = {
            "schema": "semantic-execution-request/1.0",
            "execution_id": str(envelope_dict["id"]),
            "purpose": _role_execution_kind_to_purpose(envelope.execution_kind),
            "contract_schema": "tribunal-execution-envelope/1.1",
            "role_ref": str(envelope_dict["role_id"]),
            "parent_host_session_id": str(envelope_dict["meta"]["run_id"]),
            "bounded_input": dict(envelope_dict),
            "expected_output": {"output_contract": dict(envelope_dict.get("output_contract") or {})},
            "model_policy": {},
            "permission_profile": "readonly",
            "timeout_ms": int(timeout_seconds * 1000),
            "trace": {"binding_id": str(envelope_dict["binding_id"]), "envelope_id": str(envelope_dict["id"])},
        }
        try:
            raw = self._reverse_call("semantic.execute", {"request": json.dumps(request, ensure_ascii=False)})
        except Exception as exc:  # noqa: BLE001
            raise TribunalLiveDialogueTimeout(f"plugin-bridge semantic failed:{exc}") from exc
        tool_result = raw.get("tool_result") if isinstance(raw, Mapping) else raw
        if not isinstance(tool_result, Mapping):
            raise TribunalLiveDialogueError("plugin-bridge returned non-object tool_result")
        runtime_status = tool_result.get("runtime_status")
        if runtime_status != "COMPLETED":
            raise TribunalLiveDialogueError(f"plugin-bridge semantic not completed:{runtime_status}")
        structured = tool_result.get("structured_output") or {}
        text = structured.get("text") if isinstance(structured, Mapping) else None
        if not isinstance(text, str) or not text.strip():
            raise TribunalLiveDialogueError("plugin-bridge returned empty structured text")
        try:
            out = json.loads(text)
        except json.JSONDecodeError as exc:
            raise TribunalLiveDialogueError(f"plugin-bridge structured text is not JSON:{exc}") from exc
        if not isinstance(out, Mapping):
            raise TribunalLiveDialogueError("plugin-bridge structured output must be a JSON object")
        # Provider output exactly as Core validates it (same contract as the
        # subprocess transport). Diagnostics live in the bridge/plugin logs.
        return dict(out)


def _role_execution_kind_to_purpose(kind: RoleExecutionKind) -> str:
    mapping = {
        RoleExecutionKind.FIRST_PASS: "TRIBUNAL_ROLE",
        RoleExecutionKind.QUESTION: "TRIBUNAL_ROLE",
        RoleExecutionKind.ANSWER: "TRIBUNAL_ROLE",
        RoleExecutionKind.DEFENSE: "TRIBUNAL_ROLE",
    }
    return mapping.get(kind, "TRIBUNAL_ROLE")


def _meta_to_dict(meta: EntityMeta) -> dict[str, Any]:
    return {
        "id": str(meta.id), "schema_version": meta.schema_version, "revision": meta.revision,
        "run_id": str(meta.run_id), "created_at": meta.created_at.isoformat(),
        "created_by": {"kind": meta.created_by.actor_type, "id": meta.created_by.actor_id},
    }


def _meta_from_dict(payload: Mapping[str, Any]) -> EntityMeta:
    actor=payload.get("created_by") or {}
    return EntityMeta(
        EntityId(str(payload["id"])), str(payload["schema_version"]), int(payload["revision"]),
        EntityId(str(payload["run_id"])), datetime.fromisoformat(str(payload["created_at"])),
        ActorRef(str(actor["kind"]),str(actor["id"])),
    )


def _jsonable(obj: Any) -> Any:
    """Return a canonical JSON-compatible projection of frozen runtime values."""
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (tuple, list)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, EntityId):
        return str(obj)
    if isinstance(obj, StrEnum):
        return obj.value
    return obj


def _canon(obj: Any) -> bytes:
    return json.dumps(_jsonable(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fp(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(_canon(obj)).hexdigest()


def _output_contract(schema: str) -> dict[str, Any]:
    grounding_kinds = [
        "DISCLOSED_EVIDENCE", "DISCLOSED_TARGET", "PRIOR_ARGUMENT", "PRIOR_TURN",
        "DERIVATION_FROM_VISIBLE", "EXPLICIT_ASSUMPTION", "MODEL_PRIOR",
    ]
    discovery_kinds = [
        "MISSING_EVIDENCE", "METHOD_LIMITATION", "POSSIBLE_COUNTEREXAMPLE", "SCOPE_ISSUE",
        "CAUSALITY_PROBLEM", "NUMERIC_DISCREPANCY", "ASSUMPTION_ISSUE",
        "SOURCE_PROVENANCE_ISSUE", "FRESHNESS_ISSUE",
    ]
    grounding = {
        "type": "object",
        "required": ["kind", "statement", "refs"],
        "properties": {
            "kind": {"enum": grounding_kinds},
            "statement": {"type": "string"},
            "refs": {"type": "array", "items": {"type": "string"}},
        },
    }
    discovery = {
        "type": "object",
        "required": ["kind", "statement", "target_refs", "evidence_refs", "blocking"],
        "properties": {
            "kind": {"enum": discovery_kinds},
            "statement": {"type": "string"},
            "target_refs": {"type": "array", "items": {"type": "string"}},
            "evidence_refs": {"type": "array", "items": {"type": "string"}},
            "blocking": {"type": "boolean"},
        },
    }
    evidence_request = {
        "type": "object",
        "required": ["question", "reason", "target_refs", "requested_evidence_kinds"],
        "properties": {
            "question": {"type": "string"},
            "reason": {"type": "string"},
            "target_refs": {"type": "array", "items": {"type": "string"}},
            "requested_evidence_kinds": {"type": "array", "items": {"type": "string"}},
        },
    }
    if schema == "tribunal-question-draft/1.0":
        return {
            "type": "object",
            "required": ["schema", "question"],
            "properties": {
                "schema": {"const": schema},
                "question": {"type": "string"},
            },
            "additionalProperties": False,
        }
    if schema == "tribunal-answer-draft/1.1":
        return {
            "type": "object",
            "required": [
                "schema", "position", "summary", "justification", "cited_evidence_refs",
                "cited_target_refs", "discoveries", "additional_evidence_requests", "grounding",
            ],
            "properties": {
                "schema": {"const": schema},
                "position": {"enum": ["SUPPORT", "CHALLENGE", "QUALIFY", "OPEN"]},
                "summary": {"type": "string"},
                "justification": {"type": "string"},
                "cited_evidence_refs": {"type": "array", "items": {"type": "string"}},
                "cited_target_refs": {"type": "array", "items": {"type": "string"}},
                "discoveries": {"type": "array", "items": discovery},
                "additional_evidence_requests": {"type": "array", "items": evidence_request},
                "grounding": {"type": "array", "items": grounding},
            },
            "additionalProperties": False,
        }
    if schema == "tribunal-advocate-draft/1.1":
        return {
            "type": "object",
            "required": [
                "schema", "outcome", "summary", "justification", "cited_evidence_refs",
                "cited_target_refs", "discoveries", "additional_evidence_requests", "grounding",
            ],
            "properties": {
                "schema": {"const": schema},
                "outcome": {"enum": ["DEFEND", "QUALIFY", "CONCEDE_LOCAL_POINT", "REQUEST_EVIDENCE", "OPEN"]},
                "summary": {"type": "string"},
                "justification": {"type": "string"},
                "cited_evidence_refs": {"type": "array", "items": {"type": "string"}},
                "cited_target_refs": {"type": "array", "items": {"type": "string"}},
                "discoveries": {"type": "array", "items": discovery},
                "additional_evidence_requests": {"type": "array", "items": evidence_request},
                "grounding": {"type": "array", "items": grounding},
            },
            "additionalProperties": False,
        }
    raise TribunalLiveDialogueError(f"unknown expected output schema:{schema}")


def _id_map(items: Mapping[EntityId | str, Any]) -> dict[str, Any]:
    return {str(k): v for k, v in items.items()}


def compile_execution_envelope(
    *,
    binding: RoleProviderBinding,
    disclosure: DialecticDisclosureContract,
    question_contract: DialecticQuestionContract,
    instruction: RoleInstructionPack,
    argument_payloads: Mapping[EntityId | str, Mapping[str, Any]],
    turn_payloads: Mapping[EntityId | str, Mapping[str, Any]],
    ref_payloads: Mapping[EntityId | str, Mapping[str, Any]],
    question_turn: InquiryTurn | None = None,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> TribunalExecutionEnvelope:
    validate_role_provider_binding_integrity(binding)
    validate_disclosure_contract_integrity(disclosure)
    validate_question_contract_integrity(question_contract, disclosure)
    validate_role_instruction_pack_integrity(instruction)
    if binding.status is not ProviderBindingStatus.READY:
        raise TribunalLiveDialogueError(f"binding is not READY:{binding.status.value}")
    if binding.contract_id != question_contract.meta.id:
        raise TribunalLiveDialogueError("binding/question contract mismatch")
    if instruction.role_id != binding.role_id:
        raise TribunalLiveDialogueError("instruction role does not match provider binding")
    addressed_question_turn_id: EntityId | None = None
    if binding.execution_kind is RoleExecutionKind.QUESTION:
        if binding.role_id != question_contract.role_id:
            raise TribunalLiveDialogueError("question binding role must own DQC")
        if instruction.instruction_id != question_contract.role_instruction_id or instruction.instruction_fingerprint != question_contract.role_instruction_fingerprint:
            raise TribunalLiveDialogueError("question instruction does not match DQC")
        if question_turn is not None:
            raise TribunalLiveDialogueError("question execution envelope cannot contain a materialized answer-target question")
        expected_schema = "tribunal-question-draft/1.0"
    elif binding.execution_kind is RoleExecutionKind.ANSWER:
        if question_contract.answer_role_id and binding.role_id != question_contract.answer_role_id:
            raise TribunalLiveDialogueError("answer binding role does not match DQC addressed role")
        if question_turn is None:
            raise TribunalLiveDialogueError("answer execution envelope requires the materialized question turn")
        if question_turn.contract_id != question_contract.meta.id or question_turn.role_id != question_contract.role_id:
            raise TribunalLiveDialogueError("materialized question turn does not belong to DQC/questioner")
        if question_turn.kind not in {InquiryTurnKind.QUESTION, InquiryTurnKind.QUESTION_ON_ANSWER}:
            raise TribunalLiveDialogueError("answer execution envelope requires QUESTION/QUESTION_ON_ANSWER turn")
        if question_turn.parent_turn_id != question_contract.parent_turn_id:
            raise TribunalLiveDialogueError("materialized question turn parent does not match DQC")
        addressed_question_turn_id = question_turn.meta.id
        expected_schema = "tribunal-answer-draft/1.1"
    else:
        raise TribunalLiveDialogueError("L3 bounded dialogue envelope currently supports QUESTION/ANSWER only")

    args = _id_map(argument_payloads); turns = _id_map(turn_payloads); refs = _id_map(ref_payloads)
    material: dict[str, Mapping[str, Any]] = {}
    for eid in disclosure.visible_argument_ids:
        key = str(eid)
        if key not in args:
            raise TribunalLiveDialogueError(f"missing disclosed argument payload:{key}")
        material[key] = args[key]
    for tid in disclosure.visible_turn_ids:
        key = str(tid)
        if key not in turns:
            raise TribunalLiveDialogueError(f"missing disclosed turn payload:{key}")
        material[key] = turns[key]
    if question_turn is not None:
        material[str(question_turn.meta.id)] = inquiry_turn_to_dict(question_turn)
    for ref in (*question_contract.allowed_evidence_refs, *question_contract.allowed_target_refs):
        key = str(ref)
        if key not in refs:
            raise TribunalLiveDialogueError(f"missing disclosed canonical ref payload:{key}")
        material[key] = refs[key]

    allowed_turn_ids = tuple((*disclosure.visible_turn_ids, *((question_turn.meta.id,) if question_turn is not None else ())))
    allowed = {str(x) for x in (*disclosure.visible_argument_ids, *allowed_turn_ids, *question_contract.allowed_evidence_refs, *question_contract.allowed_target_refs)}
    if not set(material).issubset(allowed):
        raise TribunalLiveDialogueError("execution envelope widened disclosure material")

    from researcher_core.tribunal_disclosure import question_contract_to_dict
    control_contract = question_contract_to_dict(question_contract)
    output_contract = _output_contract(expected_schema)
    payload = {
        "binding_id": str(binding.meta.id),
        "binding_fingerprint": binding.binding_fingerprint,
        "contract_id": str(question_contract.meta.id),
        "role_id": binding.role_id,
        "execution_kind": binding.execution_kind.value,
        "branch_key": disclosure.branch.branch_key,
        "disclosure_contract_id": str(disclosure.meta.id),
        "disclosure_fingerprint": disclosure.disclosure_fingerprint,
        "instruction_id": instruction.instruction_id,
        "instruction_fingerprint": instruction.instruction_fingerprint,
        "visible_argument_ids": [str(x) for x in disclosure.visible_argument_ids],
        "visible_turn_ids": [str(x) for x in allowed_turn_ids],
        "question_turn_id": str(addressed_question_turn_id) if addressed_question_turn_id else None,
        "visible_evidence_refs": [str(x) for x in question_contract.allowed_evidence_refs],
        "visible_target_refs": [str(x) for x in question_contract.allowed_target_refs],
        "control_contract_hash": _fp(control_contract),
        "material_hash": _fp(material),
        "max_response_tokens": question_contract.max_response_tokens,
        "expected_output_schema": expected_schema,
        "output_contract_hash": _fp(output_contract),
    }
    return TribunalExecutionEnvelope(
        meta=EntityMeta(id_factory.new("TEX"), "tribunal-execution-envelope/1.1", 1, question_contract.meta.run_id, created_at, actor),
        binding_id=binding.meta.id,
        binding_fingerprint=binding.binding_fingerprint,
        contract_id=question_contract.meta.id,
        role_id=binding.role_id,
        execution_kind=binding.execution_kind,
        branch_key=disclosure.branch.branch_key,
        disclosure_contract_id=disclosure.meta.id,
        disclosure_fingerprint=disclosure.disclosure_fingerprint,
        instruction_id=instruction.instruction_id,
        instruction_fingerprint=instruction.instruction_fingerprint,
        visible_argument_ids=disclosure.visible_argument_ids,
        visible_turn_ids=allowed_turn_ids,
        visible_evidence_refs=question_contract.allowed_evidence_refs,
        visible_target_refs=question_contract.allowed_target_refs,
        control_contract=control_contract,
        material=material,
        question_turn_id=addressed_question_turn_id,
        max_response_tokens=question_contract.max_response_tokens,
        expected_output_schema=expected_schema,
        output_contract=output_contract,
        envelope_fingerprint=_fp(payload),
        metadata={"authority_boundary": "bounded provider input only; no hidden refs/tools/provider authority"},
    )


def _execution_envelope_integrity_payload(envelope: TribunalExecutionEnvelope) -> dict[str, Any]:
    return {
        "binding_id": str(envelope.binding_id),
        "binding_fingerprint": envelope.binding_fingerprint,
        "contract_id": str(envelope.contract_id),
        "role_id": envelope.role_id,
        "execution_kind": envelope.execution_kind.value,
        "branch_key": envelope.branch_key,
        "disclosure_contract_id": str(envelope.disclosure_contract_id),
        "disclosure_fingerprint": envelope.disclosure_fingerprint,
        "instruction_id": envelope.instruction_id,
        "instruction_fingerprint": envelope.instruction_fingerprint,
        "visible_argument_ids": [str(x) for x in envelope.visible_argument_ids],
        "visible_turn_ids": [str(x) for x in envelope.visible_turn_ids],
        "question_turn_id": str(envelope.question_turn_id) if envelope.question_turn_id else None,
        "visible_evidence_refs": [str(x) for x in envelope.visible_evidence_refs],
        "visible_target_refs": [str(x) for x in envelope.visible_target_refs],
        "control_contract_hash": _fp(envelope.control_contract),
        "material_hash": _fp(envelope.material),
        "max_response_tokens": envelope.max_response_tokens,
        "expected_output_schema": envelope.expected_output_schema,
        "output_contract_hash": _fp(envelope.output_contract),
    }


def validate_execution_envelope_integrity(envelope: TribunalExecutionEnvelope) -> None:
    if _fp(_execution_envelope_integrity_payload(envelope)) != envelope.envelope_fingerprint:
        raise TribunalLiveDialogueError("TribunalExecutionEnvelope fingerprint mismatch")


def execution_envelope_to_dict(envelope: TribunalExecutionEnvelope) -> dict[str, Any]:
    validate_execution_envelope_integrity(envelope)
    return {
        "schema_version": "tribunal-execution-envelope/1.1",
        "meta": _meta_to_dict(envelope.meta),
        "id": str(envelope.meta.id),
        "binding_id": str(envelope.binding_id),
        "binding_fingerprint": envelope.binding_fingerprint,
        "contract_id": str(envelope.contract_id),
        "role_id": envelope.role_id,
        "execution_kind": envelope.execution_kind.value,
        "branch_key": envelope.branch_key,
        "disclosure_contract_id": str(envelope.disclosure_contract_id),
        "disclosure_fingerprint": envelope.disclosure_fingerprint,
        "instruction_id": envelope.instruction_id,
        "instruction_fingerprint": envelope.instruction_fingerprint,
        "visible_argument_ids": [str(x) for x in envelope.visible_argument_ids],
        "visible_turn_ids": [str(x) for x in envelope.visible_turn_ids],
        "question_turn_id": str(envelope.question_turn_id) if envelope.question_turn_id else None,
        "visible_evidence_refs": [str(x) for x in envelope.visible_evidence_refs],
        "visible_target_refs": [str(x) for x in envelope.visible_target_refs],
        "control_contract": _jsonable(envelope.control_contract),
        "material": _jsonable(envelope.material),
        "max_response_tokens": envelope.max_response_tokens,
        "expected_output_schema": envelope.expected_output_schema,
        "output_contract": _jsonable(envelope.output_contract),
        "envelope_fingerprint": envelope.envelope_fingerprint,
        "metadata": _jsonable(envelope.metadata),
    }


def execution_envelope_from_dict(payload: Mapping[str, Any]) -> TribunalExecutionEnvelope:
    if payload.get("schema_version") == "tribunal-execution-envelope/1.0":
        raise TribunalLiveDialogueError("legacy TribunalExecutionEnvelope/1.0 may omit the materialized answer question; recompile from DQC/IQT context")
    if payload.get("schema_version") != "tribunal-execution-envelope/1.1":
        raise TribunalLiveDialogueError("unsupported TribunalExecutionEnvelope schema")
    try:
        envelope=TribunalExecutionEnvelope(
            meta=_meta_from_dict(payload["meta"]),
            binding_id=EntityId(str(payload["binding_id"])), binding_fingerprint=str(payload["binding_fingerprint"]),
            contract_id=EntityId(str(payload["contract_id"])), role_id=str(payload["role_id"]), execution_kind=RoleExecutionKind(str(payload["execution_kind"])),
            branch_key=str(payload["branch_key"]), disclosure_contract_id=EntityId(str(payload["disclosure_contract_id"])), disclosure_fingerprint=str(payload["disclosure_fingerprint"]),
            instruction_id=str(payload["instruction_id"]), instruction_fingerprint=str(payload["instruction_fingerprint"]),
            visible_argument_ids=tuple(EntityId(str(x)) for x in payload.get("visible_argument_ids", ())),
            visible_turn_ids=tuple(EntityId(str(x)) for x in payload.get("visible_turn_ids", ())),
            visible_evidence_refs=tuple(EntityId(str(x)) for x in payload.get("visible_evidence_refs", ())),
            visible_target_refs=tuple(EntityId(str(x)) for x in payload.get("visible_target_refs", ())),
            control_contract=dict(payload.get("control_contract") or {}),
            material={str(k):dict(v) for k,v in (payload.get("material") or {}).items()},
            question_turn_id=(EntityId(str(payload["question_turn_id"])) if payload.get("question_turn_id") else None),
            max_response_tokens=int(payload["max_response_tokens"]), expected_output_schema=str(payload["expected_output_schema"]),
            output_contract=dict(payload.get("output_contract") or {}),
            envelope_fingerprint=str(payload["envelope_fingerprint"]), metadata=dict(payload.get("metadata") or {}),
        )
    except (KeyError,TypeError,ValueError) as exc:
        raise TribunalLiveDialogueError("invalid serialized TribunalExecutionEnvelope") from exc
    validate_execution_envelope_integrity(envelope)
    return envelope


def compile_advocate_execution_envelope(
    *,
    binding: RoleProviderBinding,
    disclosure: DialecticDisclosureContract,
    contract: AdvocateDefenseContract,
    instruction: RoleInstructionPack,
    argument_payloads: Mapping[EntityId | str, Mapping[str, Any]],
    turn_payloads: Mapping[EntityId | str, Mapping[str, Any]],
    ref_payloads: Mapping[EntityId | str, Mapping[str, Any]],
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> TribunalExecutionEnvelope:
    validate_role_provider_binding_integrity(binding)
    validate_advocate_contract_integrity(contract, disclosure)
    validate_role_instruction_pack_integrity(instruction)
    if binding.status is not ProviderBindingStatus.READY or binding.execution_kind is not RoleExecutionKind.DEFENSE:
        raise TribunalLiveDialogueError("Advocate execution requires READY DEFENSE binding")
    if binding.contract_id != contract.meta.id or binding.role_id != contract.role_id:
        raise TribunalLiveDialogueError("Advocate binding/contract mismatch")
    if instruction.role_id != contract.role_id or instruction.instruction_id != contract.role_instruction_id or instruction.instruction_fingerprint != contract.role_instruction_fingerprint:
        raise TribunalLiveDialogueError("Advocate instruction does not match ADC")
    args=_id_map(argument_payloads); turns=_id_map(turn_payloads); refs=_id_map(ref_payloads)
    material: dict[str, Mapping[str, Any]]={}
    for eid in disclosure.visible_argument_ids:
        key=str(eid)
        if key not in args: raise TribunalLiveDialogueError(f"missing disclosed Advocate argument payload:{key}")
        material[key]=args[key]
    for tid in disclosure.visible_turn_ids:
        key=str(tid)
        if key not in turns: raise TribunalLiveDialogueError(f"missing disclosed Advocate turn payload:{key}")
        material[key]=turns[key]
    for ref in (*contract.allowed_evidence_refs,*contract.allowed_target_refs):
        key=str(ref)
        if key not in refs: raise TribunalLiveDialogueError(f"missing disclosed Advocate ref payload:{key}")
        material[key]=refs[key]
    allowed={str(x) for x in (*disclosure.visible_argument_ids,*disclosure.visible_turn_ids,*contract.allowed_evidence_refs,*contract.allowed_target_refs)}
    if not set(material).issubset(allowed): raise TribunalLiveDialogueError("Advocate execution envelope widened disclosure")
    control=advocate_defense_contract_to_dict(contract)
    output_contract=_output_contract("tribunal-advocate-draft/1.1")
    payload={
        "binding_id":str(binding.meta.id),"binding_fingerprint":binding.binding_fingerprint,"contract_id":str(contract.meta.id),
        "role_id":binding.role_id,"execution_kind":binding.execution_kind.value,"branch_key":disclosure.branch.branch_key,
        "disclosure_contract_id":str(disclosure.meta.id),"disclosure_fingerprint":disclosure.disclosure_fingerprint,
        "instruction_id":instruction.instruction_id,"instruction_fingerprint":instruction.instruction_fingerprint,
        "visible_argument_ids":[str(x) for x in disclosure.visible_argument_ids],"visible_turn_ids":[str(x) for x in disclosure.visible_turn_ids],
        "question_turn_id":None,
        "visible_evidence_refs":[str(x) for x in contract.allowed_evidence_refs],"visible_target_refs":[str(x) for x in contract.allowed_target_refs],
        "control_contract_hash":_fp(control),"material_hash":_fp(material),"max_response_tokens":contract.token_budget,
        "expected_output_schema":"tribunal-advocate-draft/1.1","output_contract_hash":_fp(output_contract),
    }
    return TribunalExecutionEnvelope(
        meta=EntityMeta(id_factory.new("TEX"),"tribunal-execution-envelope/1.1",1,contract.meta.run_id,created_at,actor),
        binding_id=binding.meta.id,binding_fingerprint=binding.binding_fingerprint,contract_id=contract.meta.id,role_id=binding.role_id,execution_kind=binding.execution_kind,
        branch_key=disclosure.branch.branch_key,disclosure_contract_id=disclosure.meta.id,disclosure_fingerprint=disclosure.disclosure_fingerprint,
        instruction_id=instruction.instruction_id,instruction_fingerprint=instruction.instruction_fingerprint,visible_argument_ids=disclosure.visible_argument_ids,
        visible_turn_ids=disclosure.visible_turn_ids,visible_evidence_refs=contract.allowed_evidence_refs,visible_target_refs=contract.allowed_target_refs,
        control_contract=control,material=material,question_turn_id=None,max_response_tokens=contract.token_budget,expected_output_schema="tribunal-advocate-draft/1.1",
        output_contract=output_contract,envelope_fingerprint=_fp(payload),metadata={"authority_boundary":"bounded conditional Advocate input only; no hidden refs or authority widening"},
    )


def _parse_advocate_payload(payload: Mapping[str, Any], contract: AdvocateDefenseContract, disclosure: DialecticDisclosureContract) -> AdvocateWorkerDraft:
    required = {"schema", "outcome", "summary", "justification", "cited_evidence_refs", "cited_target_refs", "discoveries", "additional_evidence_requests", "grounding"}
    if set(payload) != required:
        raise TribunalLiveDialogueError("Advocate provider output does not match the exact output contract")
    if payload.get("schema") != "tribunal-advocate-draft/1.1":
        raise TribunalLiveDialogueError("Advocate provider returned wrong schema")
    _validate_typed_response_payload(payload)
    try:
        outcome=AdvocateOutcome(payload["outcome"])
    except Exception as exc:
        raise TribunalLiveDialogueError("invalid Advocate outcome") from exc
    summary=payload["summary"].strip(); justification=payload["justification"].strip()
    if not summary or not justification: raise TribunalLiveDialogueError("Advocate summary/justification are required")
    evidence=_entity_ids(payload.get("cited_evidence_refs",())); targets=_entity_ids(payload.get("cited_target_refs",()))
    discoveries=[]
    for item in payload.get("discoveries",()):
        discoveries.append(InquiryDiscovery(kind=DiscoveryKind(item["kind"]),statement=item["statement"],need_refs=contract.assigned_need_refs,target_refs=_entity_ids(item["target_refs"]),evidence_refs=_entity_ids(item["evidence_refs"]),blocking=item["blocking"]))
    requests=[]
    for item in payload.get("additional_evidence_requests",()):
        requests.append(AdditionalEvidenceRequest(question=item["question"],reason=item["reason"],need_refs=contract.assigned_need_refs,target_refs=_entity_ids(item["target_refs"]),requested_evidence_kinds=tuple(item["requested_evidence_kinds"])))
    grounding=[]
    for item in payload.get("grounding",()):
        grounding.append(ResponseGroundingItem(kind=ResponseGroundingKind(item["kind"]),statement=item["statement"],refs=_entity_ids(item["refs"])))
    for item in grounding:
        if item.kind is ResponseGroundingKind.DISCLOSED_EVIDENCE and not set(item.refs).issubset(contract.allowed_evidence_refs):
            raise TribunalLiveDialogueError("Advocate evidence grounding references hidden or non-evidence material")
        if item.kind is ResponseGroundingKind.DISCLOSED_TARGET and not set(item.refs).issubset(contract.allowed_target_refs):
            raise TribunalLiveDialogueError("Advocate target grounding references hidden or non-target material")
        if item.kind is ResponseGroundingKind.PRIOR_ARGUMENT and not set(item.refs).issubset(disclosure.visible_argument_ids):
            raise TribunalLiveDialogueError("Advocate grounding references hidden argument")
        if item.kind is ResponseGroundingKind.PRIOR_TURN and not set(item.refs).issubset(disclosure.visible_turn_ids):
            raise TribunalLiveDialogueError("Advocate grounding references hidden turn")
    state=characterize_response_grounding(grounding)
    if outcome is AdvocateOutcome.DEFEND and state in {ResponseGroundingState.MODEL_PRIOR_ONLY,ResponseGroundingState.UNGROUNDED,ResponseGroundingState.VISIBLE_CONTEXT_ONLY}:
        # A defense without disclosed evidence may remain a hypothesis, but cannot materialize DEFENDS authority.
        outcome=AdvocateOutcome.REQUEST_EVIDENCE
        requests.append(AdditionalEvidenceRequest(question="What disclosed or newly researched evidence supports this defense?",reason="Conditional Advocate cannot defend from model prior/context alone.",need_refs=contract.assigned_need_refs,target_refs=targets,requested_evidence_kinds=("external_source","measurement","reproducible_derivation")))
    return AdvocateWorkerDraft(outcome=outcome,summary=summary,justification=justification,cited_evidence_refs=evidence,cited_target_refs=targets,discoveries=tuple(discoveries),additional_evidence_requests=tuple(requests),metadata={"provider_materialized":True,"grounding_state":state.value},grounding_items=tuple(grounding))


def _provider_execution_receipt_payload(receipt: ProviderExecutionReceipt) -> dict[str, Any]:
    return {
        "binding_id": str(receipt.binding_id), "envelope_id": str(receipt.envelope_id),
        "provider_id": receipt.provider_id, "runtime_tool": receipt.runtime_tool,
        "execution_kind": receipt.execution_kind.value, "status": receipt.status.value,
        "child_job_id": receipt.child_job_id, "attempt_id": receipt.attempt_id,
        "provider_output_hash": receipt.provider_output_hash,
        "output_turn_id": str(receipt.output_turn_id) if receipt.output_turn_id else None,
        "output_argument_id": str(receipt.output_argument_id) if receipt.output_argument_id else None,
        "failure_reason": receipt.failure_reason, "metadata": _jsonable(receipt.metadata),
    }


def validate_provider_execution_receipt_integrity(receipt: ProviderExecutionReceipt) -> None:
    if _fp(_provider_execution_receipt_payload(receipt)) != receipt.receipt_fingerprint:
        raise TribunalLiveDialogueError("ProviderExecutionReceipt fingerprint mismatch")


def provider_execution_receipt_to_dict(receipt: ProviderExecutionReceipt) -> dict[str, Any]:
    validate_provider_execution_receipt_integrity(receipt)
    return {
        "schema_version": "provider-execution-receipt/1.0",
        "meta": _meta_to_dict(receipt.meta),
        "id": str(receipt.meta.id),
        **_provider_execution_receipt_payload(receipt),
        "receipt_fingerprint": receipt.receipt_fingerprint,
    }


def provider_execution_receipt_from_dict(payload: Mapping[str, Any]) -> ProviderExecutionReceipt:
    if payload.get("schema_version") != "provider-execution-receipt/1.0":
        raise TribunalLiveDialogueError("unsupported ProviderExecutionReceipt schema")
    try:
        receipt=ProviderExecutionReceipt(
            meta=_meta_from_dict(payload["meta"]), binding_id=EntityId(str(payload["binding_id"])), envelope_id=EntityId(str(payload["envelope_id"])),
            provider_id=str(payload["provider_id"]), runtime_tool=str(payload["runtime_tool"]), execution_kind=RoleExecutionKind(str(payload["execution_kind"])),
            status=ProviderExecutionStatus(str(payload["status"])), child_job_id=str(payload["child_job_id"]), attempt_id=str(payload["attempt_id"]),
            provider_output_hash=(str(payload["provider_output_hash"]) if payload.get("provider_output_hash") else None),
            output_turn_id=(EntityId(str(payload["output_turn_id"])) if payload.get("output_turn_id") else None),
            output_argument_id=(EntityId(str(payload["output_argument_id"])) if payload.get("output_argument_id") else None),
            receipt_fingerprint=str(payload["receipt_fingerprint"]), failure_reason=(str(payload["failure_reason"]) if payload.get("failure_reason") else None),
            metadata=dict(payload.get("metadata") or {}),
        )
    except (KeyError,TypeError,ValueError) as exc:
        raise TribunalLiveDialogueError("invalid serialized ProviderExecutionReceipt") from exc
    validate_provider_execution_receipt_integrity(receipt)
    return receipt


def _entity_ids(values: Sequence[str]) -> tuple[EntityId, ...]:
    return tuple(EntityId(str(x)) for x in values)


def _validate_typed_response_payload(payload: Mapping[str, Any]) -> None:
    for key in ("summary", "justification"):
        if not isinstance(payload[key], str):
            raise TribunalLiveDialogueError(f"provider {key} must be a string")
    for key in ("cited_evidence_refs", "cited_target_refs"):
        _validate_string_array(payload[key], key)
    _validate_object_array(
        payload["discoveries"],
        "discoveries",
        {"kind", "statement", "target_refs", "evidence_refs", "blocking"},
    )
    for item in payload["discoveries"]:
        if not isinstance(item["kind"], str) or not isinstance(item["statement"], str) or not isinstance(item["blocking"], bool):
            raise TribunalLiveDialogueError("provider discovery fields have invalid types")
        _validate_string_array(item["target_refs"], "discovery target_refs")
        _validate_string_array(item["evidence_refs"], "discovery evidence_refs")
    _validate_object_array(
        payload["additional_evidence_requests"],
        "additional_evidence_requests",
        {"question", "reason", "target_refs", "requested_evidence_kinds"},
    )
    for item in payload["additional_evidence_requests"]:
        if not isinstance(item["question"], str) or not isinstance(item["reason"], str):
            raise TribunalLiveDialogueError("provider evidence request fields have invalid types")
        _validate_string_array(item["target_refs"], "evidence request target_refs")
        _validate_string_array(item["requested_evidence_kinds"], "requested_evidence_kinds")
    _validate_object_array(payload["grounding"], "grounding", {"kind", "statement", "refs"})
    for item in payload["grounding"]:
        if not isinstance(item["kind"], str) or not isinstance(item["statement"], str):
            raise TribunalLiveDialogueError("provider grounding fields have invalid types")
        _validate_string_array(item["refs"], "grounding refs")


def _validate_object_array(value: Any, label: str, keys: set[str]) -> None:
    if not isinstance(value, list):
        raise TribunalLiveDialogueError(f"provider {label} must be an array")
    if any(not isinstance(item, Mapping) or set(item) != keys for item in value):
        raise TribunalLiveDialogueError(f"provider {label} items do not match the exact output contract")


def _validate_string_array(value: Any, label: str) -> None:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TribunalLiveDialogueError(f"provider {label} must be an array of strings")


def _parse_answer_payload(payload: Mapping[str, Any], contract: DialecticQuestionContract) -> tuple[ArgumentPosition, str, str, tuple[EntityId, ...], tuple[EntityId, ...], tuple[InquiryDiscovery, ...], tuple[AdditionalEvidenceRequest, ...], tuple[ResponseGroundingItem, ...]]:
    required = {"schema", "position", "summary", "justification", "cited_evidence_refs", "cited_target_refs", "discoveries", "additional_evidence_requests", "grounding"}
    if set(payload) != required:
        raise TribunalLiveDialogueError("answer provider output does not match the exact output contract")
    if payload.get("schema") != "tribunal-answer-draft/1.1":
        raise TribunalLiveDialogueError("answer provider returned wrong schema")
    _validate_typed_response_payload(payload)
    try:
        position = ArgumentPosition(payload["position"])
    except Exception as exc:
        raise TribunalLiveDialogueError("invalid answer position") from exc
    summary = payload["summary"].strip(); justification = payload["justification"].strip()
    if not summary or not justification:
        raise TribunalLiveDialogueError("answer summary/justification are required")
    evidence = _entity_ids(payload.get("cited_evidence_refs", ()))
    targets = _entity_ids(payload.get("cited_target_refs", ()))
    discoveries: list[InquiryDiscovery] = []
    for item in payload.get("discoveries", ()):
        discoveries.append(InquiryDiscovery(
            kind=DiscoveryKind(item["kind"]), statement=item["statement"], need_refs=contract.assigned_need_refs,
            target_refs=_entity_ids(item["target_refs"]), evidence_refs=_entity_ids(item["evidence_refs"]), blocking=item["blocking"],
        ))
    requests: list[AdditionalEvidenceRequest] = []
    for item in payload.get("additional_evidence_requests", ()):
        requests.append(AdditionalEvidenceRequest(
            question=item["question"], reason=item["reason"], need_refs=contract.assigned_need_refs,
            target_refs=_entity_ids(item["target_refs"]), requested_evidence_kinds=tuple(item["requested_evidence_kinds"]),
        ))
    grounding: list[ResponseGroundingItem] = []
    for item in payload.get("grounding", ()):
        grounding.append(ResponseGroundingItem(
            kind=ResponseGroundingKind(item["kind"]),
            statement=item["statement"],
            refs=_entity_ids(item["refs"]),
        ))
    return position, summary, justification, evidence, targets, tuple(discoveries), tuple(requests), tuple(grounding)


def materialize_live_answer(
    *,
    contract: DialecticQuestionContract,
    disclosure: DialecticDisclosureContract,
    question_turn: InquiryTurn,
    answer_role_id: str,
    provider_payload: Mapping[str, Any],
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> tuple[InquiryTurn, ArgumentArtifact]:
    position, summary, justification, evidence, targets, discoveries, requests, grounding = _parse_answer_payload(provider_payload, contract)
    allowed_grounding_refs = set(disclosure.visible_argument_ids) | set(disclosure.visible_turn_ids) | {question_turn.meta.id} | set(contract.allowed_evidence_refs) | set(contract.allowed_target_refs)
    for item in grounding:
        if not set(item.refs).issubset(allowed_grounding_refs):
            raise TribunalLiveDialogueError("answer grounding references hidden material")
        if item.kind is ResponseGroundingKind.DISCLOSED_EVIDENCE and not set(item.refs).issubset(contract.allowed_evidence_refs):
            raise TribunalLiveDialogueError("evidence grounding references non-evidence disclosure")
        if item.kind is ResponseGroundingKind.DISCLOSED_TARGET and not set(item.refs).issubset(contract.allowed_target_refs):
            raise TribunalLiveDialogueError("target grounding references hidden target")
        if item.kind is ResponseGroundingKind.PRIOR_ARGUMENT and not set(item.refs).issubset(disclosure.visible_argument_ids):
            raise TribunalLiveDialogueError("prior-argument grounding references hidden argument")
        if item.kind is ResponseGroundingKind.PRIOR_TURN and not set(item.refs).issubset(set(disclosure.visible_turn_ids) | {question_turn.meta.id}):
            raise TribunalLiveDialogueError("prior-turn grounding references hidden turn")
    grounding_state = characterize_response_grounding(grounding)
    if grounding_state in {ResponseGroundingState.MODEL_PRIOR_ONLY, ResponseGroundingState.UNGROUNDED} and position is not ArgumentPosition.OPEN:
        discoveries = tuple((*discoveries, InquiryDiscovery(
            kind=DiscoveryKind.MISSING_EVIDENCE,
            statement="Response relies on model prior/unsupported reasoning and cannot close the scientific branch without external evidence.",
            need_refs=contract.assigned_need_refs,
            target_refs=targets,
            evidence_refs=(),
            blocking=True,
        )))
        requests = tuple((*requests, AdditionalEvidenceRequest(
            question="What external evidence or reproducible derivation supports this response?",
            reason="Live semantic response is not grounded in disclosed evidence.",
            need_refs=contract.assigned_need_refs,
            target_refs=targets,
            requested_evidence_kinds=("external_source", "measurement", "reproducible_derivation"),
        )))
    kind = InquiryTurnKind.REBUTTAL if question_turn.kind is InquiryTurnKind.QUESTION_ON_ANSWER else InquiryTurnKind.ANSWER
    cited = tuple(dict.fromkeys((*targets, *evidence)))
    turn = InquiryTurn(
        meta=EntityMeta(id_factory.new("IQT"), "inquiry-turn/1.0", 1, contract.meta.run_id, created_at, actor),
        contract_id=contract.meta.id, role_id=answer_role_id, kind=kind, content=summary,
        parent_turn_id=question_turn.meta.id, cited_refs=cited,
        metadata={"branch_key": contract.branch.branch_key, "provider_materialized": True},
    )
    argument = ArgumentArtifact(
        meta=EntityMeta(id_factory.new("ARG"), "argument-artifact/1.0", 1, contract.meta.run_id, created_at, actor),
        contract_id=contract.meta.id, source_turn_id=turn.meta.id, role_id=answer_role_id, position=position,
        assigned_need_refs=contract.assigned_need_refs, summary=summary, justification=justification,
        cited_evidence_refs=evidence, cited_target_refs=targets, discoveries=discoveries, additional_evidence_requests=requests,
        metadata={"branch_key": contract.branch.branch_key, "provider_materialized": True, "grounding_state": grounding_state.value},
        grounding_items=grounding, grounding_state=grounding_state,
    )
    validate_answer_against_question_contract(contract=contract, disclosure=disclosure, question_turn=question_turn, answer_turn=turn, answer_argument=argument)
    return turn, argument


def admit_live_answer_to_argument_graph(
    *,
    graph: ArgumentGraphProjection,
    arguments: Mapping[EntityId, ArgumentArtifact],
    branch: DialecticBranchRef,
    question_contract: DialecticQuestionContract,
    answer_argument: ArgumentArtifact,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
) -> tuple[ArgumentGraphProjection, dict[EntityId, ArgumentArtifact], DialecticBranchRef, ArgumentRelation]:
    """Admit one already validated live answer into the historical argument graph.

    Provider output cannot be observed by the dialectic controller until it is a
    graph member.  Admission creates only a REPLIES_TO review relation; it does
    not create KnowledgeGraph edges or mutate claim truth.
    """
    if graph.meta.id != branch.argument_graph_id:
        raise TribunalLiveDialogueError("answer admission branch/graph identity mismatch")
    if graph.meta.revision != branch.graph_revision or graph.graph_fingerprint != branch.graph_fingerprint:
        raise TribunalLiveDialogueError("answer admission requires current branch graph snapshot")
    if answer_argument.meta.id in arguments or answer_argument.meta.id in graph.argument_ids:
        raise TribunalLiveDialogueError("answer argument is already admitted to argument graph")
    if question_contract.target_argument_id not in arguments:
        raise TribunalLiveDialogueError("question target argument is absent from argument graph")
    if answer_argument.meta.run_id != graph.meta.run_id or question_contract.meta.run_id != graph.meta.run_id:
        raise TribunalLiveDialogueError("answer admission cannot cross run lineage")
    relation = ArgumentRelation(
        meta=EntityMeta(id_factory.new("ARL"), "argument-relation/1.0", 1, graph.meta.run_id, created_at, actor),
        kind=ArgumentRelationKind.REPLIES_TO,
        source_argument_id=answer_argument.meta.id,
        target_argument_id=question_contract.target_argument_id,
        need_refs=question_contract.assigned_need_refs,
        material=True,
        reason_codes=("LIVE_DIALECTIC_REPLY_ADMITTED",),
        metadata={"question_contract_id": str(question_contract.meta.id), "branch_key": branch.branch_key},
    )
    merged = dict(arguments)
    merged[answer_argument.meta.id] = answer_argument
    new_graph = append_argument_branch(
        graph=graph,
        new_meta=EntityMeta(graph.meta.id, graph.meta.schema_version, graph.meta.revision + 1, graph.meta.run_id, created_at, actor),
        arguments=tuple(merged.values()),
        new_relations=(relation,),
    )
    new_branch = refresh_branch_ref(
        branch=branch, graph=new_graph, arguments=merged, head_argument_id=answer_argument.meta.id
    )
    return new_graph, merged, new_branch, relation


class JobCtlLiveDialogueAdapter:
    def __init__(self, *, state_dir: str | Path, artifact_dir: str | Path, timeout_seconds: float = 30.0):
        self.state_dir = Path(state_dir); self.artifact_dir = Path(artifact_dir); self.timeout_seconds = float(timeout_seconds)
        self.state_dir.mkdir(parents=True, exist_ok=True); self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def _child_path(self, child_id: str) -> Path:
        return self.state_dir / f"{child_id.replace('/', '_')}.json"

    def _start(self, *, parent_state_path: Path, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope) -> tuple[str, str, Path]:
        parent = job_ctl.load(parent_state_path)
        if parent.get("status") not in {"RUNNING", "DEGRADED", "WAITING_RETRY"}:
            raise TribunalLiveDialogueError("parent Job is not executable")
        suffix = binding.execution_kind.value.lower()
        child_id = f"tribunal-live-{suffix}-{str(envelope.contract_id)}-{binding.role_id}"
        external_id = f"{envelope.contract_id}:{binding.execution_kind.value}:{binding.role_id}"
        if any(c.get("external_task_id") == external_id for c in parent.get("children", ())):
            raise TribunalLiveDialogueError("live execution already exists in parent")
        child_path = self._child_path(child_id)
        if child_path.exists():
            raise TribunalLiveDialogueError("live child Job state already exists")
        contract = {"schema":"tribunal-live-role-job/1.0","binding":role_provider_binding_to_dict(binding),"envelope":execution_envelope_to_dict(envelope)}
        child = job_ctl.create(child_id, contract, [suffix]); job_ctl.save(child, child_path)
        rec = {"child_id":child_id,"mode":"required","external_task_id":external_id,"status":"RUNNING","created_at":job_ctl.now()}
        parent.setdefault("children", []).append(rec); job_ctl.event(parent,"CHILD_ADDED",rec); job_ctl.save(parent,parent_state_path)
        child = job_ctl.load(child_path)
        attempt_id = "ATT-" + envelope.envelope_fingerprint.split(":",1)[-1][:12]
        arec = {"attempt_id":attempt_id,"agent":binding.selected_provider_id,"stage":suffix,"external_task_id":external_id,"status":"RUNNING","started_at":job_ctl.now(),"heartbeat":None,"artifacts":[]}
        child["attempts"].append(arec); child["stages"][suffix]["status"]="RUNNING"; child["stages"][suffix]["updated_at"]=job_ctl.now(); job_ctl.event(child,"ATTEMPT_STARTED",arec); job_ctl.save(child,child_path)
        return child_id, attempt_id, child_path

    def _finish(self, *, child_path: Path, parent_path: Path, child_id: str, attempt_id: str, status: ProviderExecutionStatus, artifacts: Sequence[tuple[str, Path]] = (), reason: str | None) -> None:
        child=job_ctl.load(child_path); attempt=next(x for x in child["attempts"] if x["attempt_id"]==attempt_id)
        attempt["finished_at"]=job_ctl.now(); attempt["status"]="COMPLETED" if status is ProviderExecutionStatus.COMPLETED else ("TIMED_OUT" if status is ProviderExecutionStatus.TIMED_OUT else "FAILED")
        stage=attempt["stage"]
        artifact_ids=[]
        for artifact_id, artifact_path in artifacts:
            artifact_ids.append(artifact_id)
            child["artifacts"][artifact_id]={"path":str(artifact_path),"sha256":hashlib.sha256(artifact_path.read_bytes()).hexdigest(),"registered_at":job_ctl.now()}
        if artifact_ids:
            attempt["artifacts"]=artifact_ids; child["stages"][stage]["artifacts"]=artifact_ids
        child["stages"][stage]["status"]="COMPLETED" if status is ProviderExecutionStatus.COMPLETED else "FAILED"; child["stages"][stage]["updated_at"]=job_ctl.now(); child["status"]="COMPLETED" if status is ProviderExecutionStatus.COMPLETED else "FAILED_NO_OUTPUT"
        job_ctl.event(child,"ATTEMPT_FINISHED",{"attempt_id":attempt_id,"status":attempt["status"],"reason":reason,"artifacts":attempt.get("artifacts",[])}); job_ctl.save(child,child_path)
        parent=job_ctl.load(parent_path); crec=next(x for x in parent["children"] if x["child_id"]==child_id); crec["status"]="COMPLETED" if status is ProviderExecutionStatus.COMPLETED else attempt["status"]; crec["finished_at"]=job_ctl.now(); job_ctl.event(parent,"CHILD_FINISHED",{"child_id":child_id,"status":crec["status"],"reason":reason}); job_ctl.save(parent,parent_path)

    def _receipt(self, *, id_factory: EntityIdFactory, contract: Any, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, child_id: str, attempt_id: str, status: ProviderExecutionStatus, created_at: datetime, actor: ActorRef, provider_output: Mapping[str, Any] | None = None, output_turn_id: EntityId | None = None, output_argument_id: EntityId | None = None, failure_reason: str | None = None, elapsed_ms: float | None = None) -> ProviderExecutionReceipt:
        meta=EntityMeta(id_factory.new("PER"),"provider-execution-receipt/1.0",1,contract.meta.run_id,created_at,actor)
        metadata={"elapsed_ms":elapsed_ms} if elapsed_ms is not None else {}
        values={
            "binding_id":str(binding.meta.id),"envelope_id":str(envelope.meta.id),"provider_id":binding.selected_provider_id or "",
            "runtime_tool":binding.selected_runtime_tool or "","execution_kind":binding.execution_kind.value,"status":status.value,
            "child_job_id":child_id,"attempt_id":attempt_id,"provider_output_hash":(_fp(provider_output) if provider_output is not None else None),
            "output_turn_id":str(output_turn_id) if output_turn_id else None,"output_argument_id":str(output_argument_id) if output_argument_id else None,
            "failure_reason":failure_reason,"metadata":metadata,
        }
        return ProviderExecutionReceipt(
            meta=meta,binding_id=binding.meta.id,envelope_id=envelope.meta.id,provider_id=binding.selected_provider_id or "",runtime_tool=binding.selected_runtime_tool or "",
            execution_kind=binding.execution_kind,status=status,child_job_id=child_id,attempt_id=attempt_id,provider_output_hash=values["provider_output_hash"],
            output_turn_id=output_turn_id,output_argument_id=output_argument_id,receipt_fingerprint=_fp(values),failure_reason=failure_reason,metadata=metadata,
        )

    def _write_receipt(self, receipt: ProviderExecutionReceipt) -> Path:
        path=self.artifact_dir/f"{receipt.meta.id}.json"
        job_ctl.atomic_write(path,provider_execution_receipt_to_dict(receipt))
        return path

    @staticmethod
    def _validate_execution_lineage(
        *,
        binding: RoleProviderBinding,
        envelope: TribunalExecutionEnvelope,
        contract: Any,
        disclosure: DialecticDisclosureContract,
        question_turn: InquiryTurn | None = None,
    ) -> None:
        validate_execution_envelope_integrity(envelope)
        if envelope.binding_id != binding.meta.id or envelope.binding_fingerprint != binding.binding_fingerprint:
            raise TribunalLiveDialogueError("execution envelope/binding lineage mismatch")
        if envelope.contract_id != contract.meta.id or binding.contract_id != contract.meta.id:
            raise TribunalLiveDialogueError("execution envelope/contract lineage mismatch")
        if envelope.role_id != binding.role_id:
            raise TribunalLiveDialogueError("execution envelope/binding role mismatch")
        if envelope.disclosure_contract_id != disclosure.meta.id or envelope.disclosure_fingerprint != disclosure.disclosure_fingerprint:
            raise TribunalLiveDialogueError("execution envelope/disclosure lineage mismatch")
        expected_question_id = question_turn.meta.id if question_turn is not None else None
        if envelope.question_turn_id != expected_question_id:
            raise TribunalLiveDialogueError("execution envelope/question turn lineage mismatch")

    def execute_question(self, *, parent_state_path: str | Path, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, current_preflight: Mapping[str, Any], transport: TribunalProviderTransport, contract: DialecticQuestionContract, disclosure: DialecticDisclosureContract, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[InquiryTurn, ProviderExecutionReceipt]:
        assert_binding_execution_ready(binding,current_preflight)
        if binding.execution_kind is not RoleExecutionKind.QUESTION or envelope.execution_kind is not RoleExecutionKind.QUESTION:
            raise TribunalLiveDialogueError("question execution requires QUESTION binding/envelope")
        self._validate_execution_lineage(binding=binding, envelope=envelope, contract=contract, disclosure=disclosure)
        parent_path=Path(parent_state_path); child_id,attempt_id,child_path=self._start(parent_state_path=parent_path,binding=binding,envelope=envelope)
        started=time.monotonic(); out: Mapping[str, Any] | None=None
        try:
            out=transport.invoke(binding=binding,envelope=envelope,timeout_seconds=self.timeout_seconds)
        except TribunalLiveDialogueTimeout as exc:
            elapsed=round((time.monotonic()-started)*1000,3); receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.TIMED_OUT,created_at=created_at,actor=actor,failure_reason=str(exc),elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.TIMED_OUT,artifacts=((str(receipt.meta.id),rp),),reason=str(exc)); raise
        except Exception as exc:
            elapsed=round((time.monotonic()-started)*1000,3); reason=f"{exc.__class__.__name__}: {exc}"; receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.FAILED,created_at=created_at,actor=actor,failure_reason=reason,elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.FAILED,artifacts=((str(receipt.meta.id),rp),),reason=reason)
            if isinstance(exc,TribunalLiveDialogueError): raise
            raise TribunalLiveDialogueError(str(exc)) from exc
        try:
            if set(out) != {"schema", "question"} or out.get("schema")!="tribunal-question-draft/1.0" or not isinstance(out.get("question"), str) or not out["question"].strip():
                raise TribunalLiveDialogueError("question provider returned invalid typed output")
            turn=materialize_question_turn(contract=contract,disclosure=disclosure,question=out["question"],id_factory=id_factory,actor=actor,created_at=created_at)
        except Exception as exc:
            elapsed=round((time.monotonic()-started)*1000,3); reason=f"{exc.__class__.__name__}: {exc}"; receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.REJECTED,created_at=created_at,actor=actor,provider_output=out,failure_reason=reason,elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.REJECTED,artifacts=((str(receipt.meta.id),rp),),reason=reason)
            if isinstance(exc,TribunalLiveDialogueError): raise
            raise TribunalLiveDialogueError(str(exc)) from exc
        elapsed=round((time.monotonic()-started)*1000,3); receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.COMPLETED,created_at=created_at,actor=actor,provider_output=out,output_turn_id=turn.meta.id,elapsed_ms=elapsed)
        payload={"schema":"tribunal-live-question-output/1.0","binding":role_provider_binding_to_dict(binding),"envelope":execution_envelope_to_dict(envelope),"provider_output":out,"turn":inquiry_turn_to_dict(turn),"receipt":provider_execution_receipt_to_dict(receipt)}
        path=self.artifact_dir/f"{turn.meta.id}.json"; job_ctl.atomic_write(path,payload); rp=self._write_receipt(receipt)
        self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.COMPLETED,artifacts=((str(turn.meta.id),path),(str(receipt.meta.id),rp)),reason=None)
        return turn,receipt

    def execute_answer(self, *, parent_state_path: str | Path, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, current_preflight: Mapping[str, Any], transport: TribunalProviderTransport, contract: DialecticQuestionContract, disclosure: DialecticDisclosureContract, question_turn: InquiryTurn, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[InquiryTurn, ArgumentArtifact, ProviderExecutionReceipt]:
        assert_binding_execution_ready(binding,current_preflight)
        if binding.execution_kind is not RoleExecutionKind.ANSWER or envelope.execution_kind is not RoleExecutionKind.ANSWER:
            raise TribunalLiveDialogueError("answer execution requires ANSWER binding/envelope")
        self._validate_execution_lineage(binding=binding, envelope=envelope, contract=contract, disclosure=disclosure, question_turn=question_turn)
        parent_path=Path(parent_state_path); child_id,attempt_id,child_path=self._start(parent_state_path=parent_path,binding=binding,envelope=envelope)
        started=time.monotonic(); out: Mapping[str, Any] | None=None
        try:
            out=transport.invoke(binding=binding,envelope=envelope,timeout_seconds=self.timeout_seconds)
        except TribunalLiveDialogueTimeout as exc:
            elapsed=round((time.monotonic()-started)*1000,3); receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.TIMED_OUT,created_at=created_at,actor=actor,failure_reason=str(exc),elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.TIMED_OUT,artifacts=((str(receipt.meta.id),rp),),reason=str(exc)); raise
        except Exception as exc:
            elapsed=round((time.monotonic()-started)*1000,3); reason=f"{exc.__class__.__name__}: {exc}"; receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.FAILED,created_at=created_at,actor=actor,failure_reason=reason,elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.FAILED,artifacts=((str(receipt.meta.id),rp),),reason=reason)
            if isinstance(exc,TribunalLiveDialogueError): raise
            raise TribunalLiveDialogueError(str(exc)) from exc
        try:
            turn,arg=materialize_live_answer(contract=contract,disclosure=disclosure,question_turn=question_turn,answer_role_id=binding.role_id,provider_payload=out,id_factory=id_factory,actor=actor,created_at=created_at)
        except Exception as exc:
            elapsed=round((time.monotonic()-started)*1000,3); reason=f"{exc.__class__.__name__}: {exc}"; receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.REJECTED,created_at=created_at,actor=actor,provider_output=out,failure_reason=reason,elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.REJECTED,artifacts=((str(receipt.meta.id),rp),),reason=reason)
            if isinstance(exc,TribunalLiveDialogueError): raise
            raise TribunalLiveDialogueError(str(exc)) from exc
        elapsed=round((time.monotonic()-started)*1000,3); receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.COMPLETED,created_at=created_at,actor=actor,provider_output=out,output_turn_id=turn.meta.id,output_argument_id=arg.meta.id,elapsed_ms=elapsed)
        payload={"schema":"tribunal-live-answer-output/1.0","binding":role_provider_binding_to_dict(binding),"envelope":execution_envelope_to_dict(envelope),"provider_output":out,"turn":inquiry_turn_to_dict(turn),"argument":argument_artifact_to_dict(arg),"receipt":provider_execution_receipt_to_dict(receipt)}
        path=self.artifact_dir/f"{arg.meta.id}.json"; job_ctl.atomic_write(path,payload); rp=self._write_receipt(receipt)
        self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.COMPLETED,artifacts=((str(arg.meta.id),path),(str(receipt.meta.id),rp)),reason=None)
        return turn,arg,receipt

    def execute_defense(self, *, parent_state_path: str | Path, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, current_preflight: Mapping[str, Any], transport: TribunalProviderTransport, contract: AdvocateDefenseContract, disclosure: DialecticDisclosureContract, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[AdvocateResponse, ProviderExecutionReceipt]:
        assert_binding_execution_ready(binding,current_preflight)
        if binding.execution_kind is not RoleExecutionKind.DEFENSE or envelope.execution_kind is not RoleExecutionKind.DEFENSE:
            raise TribunalLiveDialogueError("defense execution requires DEFENSE binding/envelope")
        self._validate_execution_lineage(binding=binding, envelope=envelope, contract=contract, disclosure=disclosure)
        parent_path=Path(parent_state_path); child_id,attempt_id,child_path=self._start(parent_state_path=parent_path,binding=binding,envelope=envelope)
        started=time.monotonic(); out: Mapping[str, Any] | None=None
        try:
            out=transport.invoke(binding=binding,envelope=envelope,timeout_seconds=self.timeout_seconds)
        except TribunalLiveDialogueTimeout as exc:
            elapsed=round((time.monotonic()-started)*1000,3); receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.TIMED_OUT,created_at=created_at,actor=actor,failure_reason=str(exc),elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.TIMED_OUT,artifacts=((str(receipt.meta.id),rp),),reason=str(exc)); raise
        except Exception as exc:
            elapsed=round((time.monotonic()-started)*1000,3); reason=f"{exc.__class__.__name__}: {exc}"; receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.FAILED,created_at=created_at,actor=actor,failure_reason=reason,elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.FAILED,artifacts=((str(receipt.meta.id),rp),),reason=reason); raise TribunalLiveDialogueError(str(exc)) from exc
        try:
            draft=_parse_advocate_payload(out,contract,disclosure)
            response=materialize_advocate_draft(contract=contract,disclosure=disclosure,draft=draft,id_factory=id_factory,actor=actor,created_at=created_at)
        except Exception as exc:
            elapsed=round((time.monotonic()-started)*1000,3); reason=f"{exc.__class__.__name__}: {exc}"; receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.REJECTED,created_at=created_at,actor=actor,provider_output=out,failure_reason=reason,elapsed_ms=elapsed); rp=self._write_receipt(receipt)
            self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.REJECTED,artifacts=((str(receipt.meta.id),rp),),reason=reason); raise TribunalLiveDialogueError(str(exc)) from exc
        elapsed=round((time.monotonic()-started)*1000,3); receipt=self._receipt(id_factory=id_factory,contract=contract,binding=binding,envelope=envelope,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.COMPLETED,created_at=created_at,actor=actor,provider_output=out,output_turn_id=response.turn.meta.id,output_argument_id=response.argument.meta.id,elapsed_ms=elapsed)
        payload={"schema":"tribunal-live-advocate-output/1.0","binding":role_provider_binding_to_dict(binding),"envelope":execution_envelope_to_dict(envelope),"provider_output":out,"response":advocate_response_to_dict(response),"turn":inquiry_turn_to_dict(response.turn),"argument":argument_artifact_to_dict(response.argument),"receipt":provider_execution_receipt_to_dict(receipt)}
        path=self.artifact_dir/f"{response.argument.meta.id}.json"; job_ctl.atomic_write(path,payload); rp=self._write_receipt(receipt)
        self._finish(child_path=child_path,parent_path=parent_path,child_id=child_id,attempt_id=attempt_id,status=ProviderExecutionStatus.COMPLETED,artifacts=((str(response.argument.meta.id),path),(str(receipt.meta.id),rp)),reason=None)
        return response,receipt
