"""R4.4 L3 provider binding for bounded Tribunal role execution.

Role identity, role authority and provider identity are deliberately separate.
The role says *what semantic duty is performed*.  This module selects *which
currently healthy authorized runtime provider may execute that duty*.

The compiler is deterministic and fail-closed.  Provider/runtime failure never
becomes epistemic OPEN.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from researcher_core.r0.commands import ActorRef
from researcher_core.r0.entities import EntityMeta
from researcher_core.r0.events import _deep_freeze
from researcher_core.r0.ids import EntityId, EntityIdFactory
from researcher_core.tribunal_composition import TribunalCompositionPolicy
from researcher_core.tribunal_disclosure import DialecticQuestionContract
from researcher_core.tribunal_inquiry import ArgumentArtifact, InquiryContract
from researcher_core.tribunal_advocate import AdvocateDefenseContract


class TribunalProviderBindingError(RuntimeError):
    pass


class RoleExecutionKind(StrEnum):
    FIRST_PASS = "FIRST_PASS"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    DEFENSE = "DEFENSE"


class ProviderBindingStatus(StrEnum):
    READY = "READY"
    ROLE_MISMATCH = "ROLE_MISMATCH"
    WRONG_PROVIDER = "WRONG_PROVIDER"
    NO_HEALTHY_PROVIDER = "NO_HEALTHY_PROVIDER"
    EXECUTOR_CARDINALITY_EXCEEDED = "EXECUTOR_CARDINALITY_EXCEEDED"


class ProviderBindingReason(StrEnum):
    ROLE_AUTHORITY_MATCH = "ROLE_AUTHORITY_MATCH"
    REQUESTED_PROVIDER_SELECTED = "REQUESTED_PROVIDER_SELECTED"
    PRIORITY_SELECTED = "PRIORITY_SELECTED"
    MULTIPLE_HEALTHY_CANDIDATES = "MULTIPLE_HEALTHY_CANDIDATES"
    PROVIDER_NOT_EXECUTION_READY = "PROVIDER_NOT_EXECUTION_READY"
    PROVIDER_CAPABILITY_MISMATCH = "PROVIDER_CAPABILITY_MISMATCH"
    PROVIDER_ROLE_KIND_MISMATCH = "PROVIDER_ROLE_KIND_MISMATCH"
    PROVIDER_CONTRACT_MISMATCH = "PROVIDER_CONTRACT_MISMATCH"
    REQUESTED_PROVIDER_UNKNOWN = "REQUESTED_PROVIDER_UNKNOWN"
    REQUESTED_ROLE_MISMATCH = "REQUESTED_ROLE_MISMATCH"
    EXECUTOR_CARDINALITY_EXCEEDED = "EXECUTOR_CARDINALITY_EXCEEDED"
    NO_HEALTHY_PROVIDER = "NO_HEALTHY_PROVIDER"


@dataclass(frozen=True, slots=True)
class TribunalProviderBindingPolicy:
    policy_id: str
    version: str
    execution_capability: str
    require_live_execution_ready: bool
    max_executors_per_contract: int
    allowed_provider_kinds: tuple[str, ...]
    allowed_contract_namespaces: tuple[str, ...]
    selection_order: tuple[str, ...]
    fail_on_requested_wrong_provider: bool
    fail_on_executor_cardinality_exceeded: bool
    policy_hash: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class RoleProviderBinding:
    meta: EntityMeta
    contract_id: EntityId
    role_id: str
    role_kind: str
    execution_kind: RoleExecutionKind
    status: ProviderBindingStatus
    execution_capability: str
    selected_provider_id: str | None
    selected_runtime_tool: str | None
    selected_runtime_provider: str | None
    candidate_provider_ids: tuple[str, ...]
    rejected_provider_reasons: Mapping[str, tuple[str, ...]]
    requested_provider_id: str | None
    requested_executor_count: int
    max_executors: int
    provider_state_fingerprint: str | None
    selected_provider_authority_fingerprint: str | None
    selected_runtime_binding_fingerprint: str | None
    preflight_fingerprint: str
    composition_policy_version: str
    composition_policy_hash: str
    provider_policy_version: str
    provider_policy_hash: str
    capability_policy_hash: str
    reason_codes: tuple[ProviderBindingReason, ...]
    binding_fingerprint: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.meta.id.namespace != "RPB":
            raise ValueError("RoleProviderBinding id must use RPB prefix")
        if self.contract_id.namespace not in {"IQC", "DQC", "ADC"}:
            raise ValueError("provider binding contract must be IQC/DQC/ADC")
        if not self.role_id or not self.role_kind or not self.execution_capability:
            raise ValueError("role_id/role_kind/execution_capability are required")
        if self.requested_executor_count < 1 or self.max_executors < 1:
            raise ValueError("executor counts must be positive")
        if self.status is ProviderBindingStatus.READY:
            if not self.selected_provider_id or not self.selected_runtime_tool or not self.selected_runtime_provider:
                raise ValueError("READY binding requires selected provider/runtime")
            if not self.provider_state_fingerprint or not self.selected_provider_authority_fingerprint or not self.selected_runtime_binding_fingerprint:
                raise ValueError("READY binding requires provider/authority/runtime fingerprints")
        object.__setattr__(self, "candidate_provider_ids", tuple(self.candidate_provider_ids))
        object.__setattr__(self, "rejected_provider_reasons", _deep_freeze({k: tuple(v) for k, v in self.rejected_provider_reasons.items()}))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "metadata", _deep_freeze(dict(self.metadata)))


def _canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _fp(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(_canon(obj)).hexdigest()


def _meta_to_dict(meta: EntityMeta) -> dict[str, Any]:
    return {
        "id": str(meta.id),
        "schema_version": meta.schema_version,
        "revision": meta.revision,
        "run_id": str(meta.run_id),
        "created_at": meta.created_at.isoformat(),
        "created_by": {"kind": meta.created_by.actor_type, "id": meta.created_by.actor_id},
    }


def _meta_from_dict(payload: Mapping[str, Any]) -> EntityMeta:
    actor = payload.get("created_by") or {}
    return EntityMeta(
        EntityId(str(payload["id"])),
        str(payload["schema_version"]),
        int(payload["revision"]),
        EntityId(str(payload["run_id"])),
        datetime.fromisoformat(str(payload["created_at"])),
        ActorRef(str(actor["kind"]), str(actor["id"])),
    )


def load_provider_binding_policy(path: Path) -> TribunalProviderBindingPolicy:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != "tribunal-provider-binding-policy/1.0":
        raise TribunalProviderBindingError("unsupported provider-binding policy schema")
    max_exec = int(raw.get("max_executors_per_contract", 0))
    if max_exec < 1:
        raise TribunalProviderBindingError("max_executors_per_contract must be positive")
    policy_hash = _fp(raw)
    return TribunalProviderBindingPolicy(
        policy_id=str(raw.get("policy_id") or ""),
        version=str(raw.get("version") or ""),
        execution_capability=str(raw.get("execution_capability") or ""),
        require_live_execution_ready=bool(raw.get("require_live_execution_ready", True)),
        max_executors_per_contract=max_exec,
        allowed_provider_kinds=tuple(str(x) for x in raw.get("allowed_provider_kinds", ())),
        allowed_contract_namespaces=tuple(str(x) for x in raw.get("allowed_contract_namespaces", ())),
        selection_order=tuple(str(x) for x in raw.get("selection_order", ())),
        fail_on_requested_wrong_provider=bool(raw.get("fail_on_requested_wrong_provider", True)),
        fail_on_executor_cardinality_exceeded=bool(raw.get("fail_on_executor_cardinality_exceeded", True)),
        policy_hash=policy_hash,
        source_path=path,
    )


def _provider_state_fingerprint(state: Mapping[str, Any]) -> str:
    stable = {
        "status": state.get("status"),
        "available": bool(state.get("available")),
        "implemented": bool(state.get("implemented")),
        "kind": state.get("kind"),
        "provides": list(state.get("provides", ())),
        "priority": int(state.get("priority", 0)),
        "detail": state.get("detail"),
    }
    return _fp(stable)


def _preflight_fingerprint(preflight: Mapping[str, Any]) -> str:
    return _fp({"schema": preflight.get("schema"), "network_probes": preflight.get("network_probes"), "providers": preflight.get("providers", {})})


def compile_role_provider_binding(
    *,
    contract_id: EntityId,
    run_id: EntityId,
    expected_role_id: str,
    requested_role_id: str | None,
    execution_kind: RoleExecutionKind,
    composition_policy: TribunalCompositionPolicy,
    binding_policy: TribunalProviderBindingPolicy,
    providers_authority: Mapping[str, Any],
    runtime_bindings: Mapping[str, Any],
    preflight: Mapping[str, Any],
    capability_policy_hash: str,
    id_factory: EntityIdFactory,
    actor: ActorRef,
    created_at: datetime,
    requested_provider_id: str | None = None,
    requested_executor_count: int = 1,
) -> RoleProviderBinding:
    if contract_id.namespace not in set(binding_policy.allowed_contract_namespaces):
        raise TribunalProviderBindingError(f"contract namespace is not allowed:{contract_id.namespace}")
    role_id = requested_role_id or expected_role_id
    reasons: list[ProviderBindingReason] = []
    rejected: dict[str, tuple[str, ...]] = {}
    status = ProviderBindingStatus.READY
    selected_provider: str | None = None
    selected_tool: str | None = None
    selected_runtime_provider: str | None = None
    state_fp: str | None = None
    provider_authority_fp: str | None = None
    runtime_binding_fp: str | None = None

    if role_id != expected_role_id or role_id not in composition_policy.roles:
        status = ProviderBindingStatus.ROLE_MISMATCH
        reasons.append(ProviderBindingReason.REQUESTED_ROLE_MISMATCH)
    else:
        reasons.append(ProviderBindingReason.ROLE_AUTHORITY_MATCH)

    if requested_executor_count > binding_policy.max_executors_per_contract:
        status = ProviderBindingStatus.EXECUTOR_CARDINALITY_EXCEEDED
        reasons.append(ProviderBindingReason.EXECUTOR_CARDINALITY_EXCEEDED)

    role_spec = composition_policy.roles.get(role_id)
    providers = providers_authority.get("providers", providers_authority)
    pstate = preflight.get("providers", {})
    eligible: list[tuple[int, str, Mapping[str, Any], Mapping[str, Any]]] = []
    for pid, spec in providers.items():
        reject: list[str] = []
        if binding_policy.execution_capability not in spec.get("provides", ()):
            continue
        declared_contracts = tuple(str(x) for x in spec.get("execution_contracts", ()))
        if declared_contracts and contract_id.namespace not in declared_contracts:
            reject.append("PROVIDER_CONTRACT_MISMATCH")
        declared_role_kinds = tuple(str(x) for x in spec.get("role_kinds", ()))
        if declared_role_kinds and (role_spec is None or role_spec.kind.value not in declared_role_kinds):
            reject.append("PROVIDER_ROLE_KIND_MISMATCH")
        if spec.get("kind") not in set(binding_policy.allowed_provider_kinds):
            reject.append("PROVIDER_KIND_FORBIDDEN")
        if spec.get("enabled") is False:
            reject.append("PROVIDER_DISABLED")
        if binding_policy.require_live_execution_ready and not spec.get("live_probe"):
            reject.append("LIVE_PROBE_REQUIRED")
        provider_max = int(spec.get("max_executors_per_contract", binding_policy.max_executors_per_contract))
        if requested_executor_count > provider_max:
            reject.append("PROVIDER_EXECUTOR_LIMIT")
        state = pstate.get(pid, {})
        if not state.get("available") or state.get("status") != "available":
            reject.append("PROVIDER_NOT_EXECUTION_READY")
        tool = spec.get("tool")
        runtime = runtime_bindings.get("tools", runtime_bindings).get(tool, {}) if tool else {}
        if not tool or not runtime:
            reject.append("RUNTIME_BINDING_MISSING")
        if reject:
            rejected[pid] = tuple(reject)
            continue
        eligible.append((int(spec.get("priority", 0)), pid, spec, state))

    eligible.sort(key=lambda x: (-x[0], x[1]))
    candidate_ids = tuple(x[1] for x in eligible)

    if status is ProviderBindingStatus.READY:
        if requested_provider_id:
            if requested_provider_id not in providers:
                status = ProviderBindingStatus.WRONG_PROVIDER
                reasons.append(ProviderBindingReason.REQUESTED_PROVIDER_UNKNOWN)
            else:
                matching = [x for x in eligible if x[1] == requested_provider_id]
                if not matching:
                    status = ProviderBindingStatus.WRONG_PROVIDER
                    reasons.append(ProviderBindingReason.PROVIDER_CAPABILITY_MISMATCH)
                else:
                    _, selected_provider, spec, state = matching[0]
                    reasons.append(ProviderBindingReason.REQUESTED_PROVIDER_SELECTED)
        elif eligible:
            _, selected_provider, spec, state = eligible[0]
            reasons.append(ProviderBindingReason.PRIORITY_SELECTED)
            if len(eligible) > 1:
                reasons.append(ProviderBindingReason.MULTIPLE_HEALTHY_CANDIDATES)
        else:
            status = ProviderBindingStatus.NO_HEALTHY_PROVIDER
            reasons.append(ProviderBindingReason.NO_HEALTHY_PROVIDER)

        if selected_provider:
            selected_tool = str(spec.get("tool"))
            selected_runtime_binding = runtime_bindings.get("tools", runtime_bindings)[selected_tool]
            selected_runtime_provider = str(selected_runtime_binding.get("provider") or "")
            state_fp = _provider_state_fingerprint(state)
            provider_authority_fp = _fp(spec)
            runtime_binding_fp = _fp(selected_runtime_binding)

    preflight_fp = _preflight_fingerprint(preflight)
    payload = {
        "contract_id": str(contract_id),
        "role_id": role_id,
        "role_kind": role_spec.kind.value if role_spec is not None else "UNKNOWN",
        "execution_kind": execution_kind.value,
        "status": status.value,
        "execution_capability": binding_policy.execution_capability,
        "selected_provider_id": selected_provider,
        "selected_runtime_tool": selected_tool,
        "selected_runtime_provider": selected_runtime_provider,
        "candidate_provider_ids": candidate_ids,
        "rejected_provider_reasons": {k: list(v) for k, v in sorted(rejected.items())},
        "requested_provider_id": requested_provider_id,
        "requested_executor_count": requested_executor_count,
        "max_executors": binding_policy.max_executors_per_contract,
        "provider_state_fingerprint": state_fp,
        "selected_provider_authority_fingerprint": provider_authority_fp,
        "selected_runtime_binding_fingerprint": runtime_binding_fp,
        "preflight_fingerprint": preflight_fp,
        "composition_policy_version": composition_policy.version,
        "composition_policy_hash": composition_policy.policy_hash,
        "provider_policy_version": binding_policy.version,
        "provider_policy_hash": binding_policy.policy_hash,
        "capability_policy_hash": capability_policy_hash,
        "reason_codes": [x.value for x in reasons],
    }
    return RoleProviderBinding(
        meta=EntityMeta(id_factory.new("RPB"), "role-provider-binding/1.0", 1, run_id, created_at, actor),
        contract_id=contract_id,
        role_id=role_id,
        role_kind=role_spec.kind.value if role_spec is not None else "UNKNOWN",
        execution_kind=execution_kind,
        status=status,
        execution_capability=binding_policy.execution_capability,
        selected_provider_id=selected_provider,
        selected_runtime_tool=selected_tool,
        selected_runtime_provider=selected_runtime_provider,
        candidate_provider_ids=candidate_ids,
        rejected_provider_reasons=rejected,
        requested_provider_id=requested_provider_id,
        requested_executor_count=requested_executor_count,
        max_executors=binding_policy.max_executors_per_contract,
        provider_state_fingerprint=state_fp,
        selected_provider_authority_fingerprint=provider_authority_fp,
        selected_runtime_binding_fingerprint=runtime_binding_fp,
        preflight_fingerprint=preflight_fp,
        composition_policy_version=composition_policy.version,
        composition_policy_hash=composition_policy.policy_hash,
        provider_policy_version=binding_policy.version,
        provider_policy_hash=binding_policy.policy_hash,
        capability_policy_hash=capability_policy_hash,
        reason_codes=tuple(dict.fromkeys(reasons)),
        binding_fingerprint=_fp(payload),
        metadata={
            "authority_boundary": "provider binding selects one runtime executor only; role/evidence/tool authority remains upstream",
            "selection_order": list(binding_policy.selection_order),
        },
    )


def compile_question_provider_binding(
    *,
    contract: DialecticQuestionContract,
    requested_role_id: str | None,
    **kwargs: Any,
) -> RoleProviderBinding:
    return compile_role_provider_binding(
        contract_id=contract.meta.id,
        run_id=contract.meta.run_id,
        expected_role_id=contract.role_id,
        requested_role_id=requested_role_id,
        execution_kind=RoleExecutionKind.QUESTION,
        **kwargs,
    )


def compile_answer_provider_binding(
    *,
    contract: DialecticQuestionContract,
    target_argument: ArgumentArtifact,
    requested_role_id: str | None,
    **kwargs: Any,
) -> RoleProviderBinding:
    if target_argument.meta.id != contract.target_argument_id:
        raise TribunalProviderBindingError("answer target argument does not match DQC target")
    expected = contract.answer_role_id or target_argument.role_id
    return compile_role_provider_binding(
        contract_id=contract.meta.id,
        run_id=contract.meta.run_id,
        expected_role_id=expected,
        requested_role_id=requested_role_id,
        execution_kind=RoleExecutionKind.ANSWER,
        **kwargs,
    )


def compile_defense_provider_binding(
    *,
    contract: AdvocateDefenseContract,
    requested_role_id: str | None,
    **kwargs: Any,
) -> RoleProviderBinding:
    return compile_role_provider_binding(
        contract_id=contract.meta.id,
        run_id=contract.meta.run_id,
        expected_role_id=contract.role_id,
        requested_role_id=requested_role_id,
        execution_kind=RoleExecutionKind.DEFENSE,
        **kwargs,
    )


def compile_first_pass_provider_binding(
    *,
    contract: InquiryContract,
    requested_role_id: str | None,
    **kwargs: Any,
) -> RoleProviderBinding:
    return compile_role_provider_binding(
        contract_id=contract.meta.id,
        run_id=contract.meta.run_id,
        expected_role_id=contract.role_id,
        requested_role_id=requested_role_id,
        execution_kind=RoleExecutionKind.FIRST_PASS,
        **kwargs,
    )


def validate_role_provider_binding_integrity(binding: RoleProviderBinding) -> None:
    payload = {
        "contract_id": str(binding.contract_id),
        "role_id": binding.role_id,
        "role_kind": binding.role_kind,
        "execution_kind": binding.execution_kind.value,
        "status": binding.status.value,
        "execution_capability": binding.execution_capability,
        "selected_provider_id": binding.selected_provider_id,
        "selected_runtime_tool": binding.selected_runtime_tool,
        "selected_runtime_provider": binding.selected_runtime_provider,
        "candidate_provider_ids": binding.candidate_provider_ids,
        "rejected_provider_reasons": {k: list(v) for k, v in sorted(binding.rejected_provider_reasons.items())},
        "requested_provider_id": binding.requested_provider_id,
        "requested_executor_count": binding.requested_executor_count,
        "max_executors": binding.max_executors,
        "provider_state_fingerprint": binding.provider_state_fingerprint,
        "selected_provider_authority_fingerprint": binding.selected_provider_authority_fingerprint,
        "selected_runtime_binding_fingerprint": binding.selected_runtime_binding_fingerprint,
        "preflight_fingerprint": binding.preflight_fingerprint,
        "composition_policy_version": binding.composition_policy_version,
        "composition_policy_hash": binding.composition_policy_hash,
        "provider_policy_version": binding.provider_policy_version,
        "provider_policy_hash": binding.provider_policy_hash,
        "capability_policy_hash": binding.capability_policy_hash,
        "reason_codes": [x.value for x in binding.reason_codes],
    }
    if _fp(payload) != binding.binding_fingerprint:
        raise TribunalProviderBindingError("RoleProviderBinding fingerprint mismatch")


def assert_binding_execution_ready(binding: RoleProviderBinding, current_preflight: Mapping[str, Any]) -> None:
    validate_role_provider_binding_integrity(binding)
    if binding.status is not ProviderBindingStatus.READY:
        raise TribunalProviderBindingError(f"provider binding is not executable:{binding.status.value}")
    state = current_preflight.get("providers", {}).get(binding.selected_provider_id or "", {})
    if not state or not state.get("available") or state.get("status") != "available":
        raise TribunalProviderBindingError("selected provider is no longer execution-ready")
    if _provider_state_fingerprint(state) != binding.provider_state_fingerprint:
        raise TribunalProviderBindingError("provider health state changed after binding")


def role_provider_binding_to_dict(binding: RoleProviderBinding) -> dict[str, Any]:
    return {
        "schema_version": "role-provider-binding/1.0",
        "meta": _meta_to_dict(binding.meta),
        "id": str(binding.meta.id),
        "contract_id": str(binding.contract_id),
        "role_id": binding.role_id,
        "role_kind": binding.role_kind,
        "execution_kind": binding.execution_kind.value,
        "status": binding.status.value,
        "execution_capability": binding.execution_capability,
        "selected_provider_id": binding.selected_provider_id,
        "selected_runtime_tool": binding.selected_runtime_tool,
        "selected_runtime_provider": binding.selected_runtime_provider,
        "candidate_provider_ids": list(binding.candidate_provider_ids),
        "rejected_provider_reasons": {k: list(v) for k, v in binding.rejected_provider_reasons.items()},
        "requested_provider_id": binding.requested_provider_id,
        "requested_executor_count": binding.requested_executor_count,
        "max_executors": binding.max_executors,
        "provider_state_fingerprint": binding.provider_state_fingerprint,
        "selected_provider_authority_fingerprint": binding.selected_provider_authority_fingerprint,
        "selected_runtime_binding_fingerprint": binding.selected_runtime_binding_fingerprint,
        "preflight_fingerprint": binding.preflight_fingerprint,
        "composition_policy_version": binding.composition_policy_version,
        "composition_policy_hash": binding.composition_policy_hash,
        "provider_policy_version": binding.provider_policy_version,
        "provider_policy_hash": binding.provider_policy_hash,
        "capability_policy_hash": binding.capability_policy_hash,
        "reason_codes": [x.value for x in binding.reason_codes],
        "binding_fingerprint": binding.binding_fingerprint,
        "metadata": dict(binding.metadata),
    }

def role_provider_binding_from_dict(payload: Mapping[str, Any]) -> RoleProviderBinding:
    if payload.get("schema_version") != "role-provider-binding/1.0":
        raise TribunalProviderBindingError("unsupported RoleProviderBinding schema")
    try:
        binding = RoleProviderBinding(
            meta=_meta_from_dict(payload["meta"]),
            contract_id=EntityId(str(payload["contract_id"])),
            role_id=str(payload["role_id"]),
            role_kind=str(payload["role_kind"]),
            execution_kind=RoleExecutionKind(str(payload["execution_kind"])),
            status=ProviderBindingStatus(str(payload["status"])),
            execution_capability=str(payload["execution_capability"]),
            selected_provider_id=(str(payload["selected_provider_id"]) if payload.get("selected_provider_id") else None),
            selected_runtime_tool=(str(payload["selected_runtime_tool"]) if payload.get("selected_runtime_tool") else None),
            selected_runtime_provider=(str(payload["selected_runtime_provider"]) if payload.get("selected_runtime_provider") else None),
            candidate_provider_ids=tuple(str(x) for x in payload.get("candidate_provider_ids", ())),
            rejected_provider_reasons={str(k): tuple(str(x) for x in v) for k,v in (payload.get("rejected_provider_reasons") or {}).items()},
            requested_provider_id=(str(payload["requested_provider_id"]) if payload.get("requested_provider_id") else None),
            requested_executor_count=int(payload["requested_executor_count"]),
            max_executors=int(payload["max_executors"]),
            provider_state_fingerprint=(str(payload["provider_state_fingerprint"]) if payload.get("provider_state_fingerprint") else None),
            selected_provider_authority_fingerprint=(str(payload["selected_provider_authority_fingerprint"]) if payload.get("selected_provider_authority_fingerprint") else None),
            selected_runtime_binding_fingerprint=(str(payload["selected_runtime_binding_fingerprint"]) if payload.get("selected_runtime_binding_fingerprint") else None),
            preflight_fingerprint=str(payload["preflight_fingerprint"]),
            composition_policy_version=str(payload["composition_policy_version"]),
            composition_policy_hash=str(payload["composition_policy_hash"]),
            provider_policy_version=str(payload["provider_policy_version"]),
            provider_policy_hash=str(payload["provider_policy_hash"]),
            capability_policy_hash=str(payload["capability_policy_hash"]),
            reason_codes=tuple(ProviderBindingReason(str(x)) for x in payload.get("reason_codes", ())),
            binding_fingerprint=str(payload["binding_fingerprint"]),
            metadata=dict(payload.get("metadata") or {}),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TribunalProviderBindingError("invalid serialized RoleProviderBinding") from exc
    validate_role_provider_binding_integrity(binding)
    return binding
