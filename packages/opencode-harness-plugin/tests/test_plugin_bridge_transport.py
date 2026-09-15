"""
PluginBridgeProviderTransport: Tribunal transport via the native plugin bridge.
Verifies envelope -> SemanticExecutionRequest mapping and result routing using a
REAL TribunalExecutionEnvelope (with correct integrity fingerprint).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Harness root: <root>/packages/opencode-harness-plugin/tests -> parents[3]
_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_root / "scripts" / "researcher"))

from researcher_core.tribunal_live_dialogue import (
    PluginBridgeProviderTransport,
    TribunalExecutionEnvelope,
    TribunalLiveDialogueError,
    _execution_envelope_integrity_payload,
    _fp,
)
from researcher_core.tribunal_provider_binding import (
    RoleExecutionKind,
    ProviderBindingStatus,
)
from researcher_core.tribunal_provider_binding import EntityId, EntityMeta, ActorRef
from researcher_core.r0.ids import EntityIdFactory


class Clock:
    def now_ms(self) -> int:
        return 1789412000000


def _envelope() -> TribunalExecutionEnvelope:
    ids = EntityIdFactory(Clock(), __import__("random").Random(7))
    actor = ActorRef("AGENT", "researcher")
    meta = EntityMeta(ids.new("TEX"), "tribunal-execution-envelope/1.1", 1, ids.new("RUN"), datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc), actor)
    env = TribunalExecutionEnvelope(
        meta=meta,
        binding_id=ids.new("RPB"),
        binding_fingerprint="sha256:binding",
        contract_id=ids.new("DQC"),
        role_id="physicist",
        execution_kind=RoleExecutionKind.QUESTION,
        branch_key="q1",
        disclosure_contract_id=ids.new("DDC"),
        disclosure_fingerprint="sha256:disclosure",
        instruction_id="inst-1",
        instruction_fingerprint="sha256:instruction",
        visible_argument_ids=(),
        visible_turn_ids=(),
        visible_evidence_refs=(ids.new("EVD"),),
        visible_target_refs=(ids.new("CLM"),),
        control_contract={},
        material={},
        question_turn_id=None,
        max_response_tokens=4000,
        expected_output_schema="tribunal-question-draft/1.0",
        output_contract={},
        envelope_fingerprint="",
    )
    fp = _fp(_execution_envelope_integrity_payload(env))
    return TribunalExecutionEnvelope(
        meta=meta,
        binding_id=env.binding_id,
        binding_fingerprint=env.binding_fingerprint,
        contract_id=env.contract_id,
        role_id=env.role_id,
        execution_kind=env.execution_kind,
        branch_key=env.branch_key,
        disclosure_contract_id=env.disclosure_contract_id,
        disclosure_fingerprint=env.disclosure_fingerprint,
        instruction_id=env.instruction_id,
        instruction_fingerprint=env.instruction_fingerprint,
        visible_argument_ids=env.visible_argument_ids,
        visible_turn_ids=env.visible_turn_ids,
        visible_evidence_refs=env.visible_evidence_refs,
        visible_target_refs=env.visible_target_refs,
        control_contract=env.control_contract,
        material=env.material,
        question_turn_id=env.question_turn_id,
        max_response_tokens=env.max_response_tokens,
        expected_output_schema=env.expected_output_schema,
        output_contract=env.output_contract,
        envelope_fingerprint=fp,
    )


def _binding():
    binding = MagicMock()
    binding.status = ProviderBindingStatus.READY
    binding.execution_kind = RoleExecutionKind.QUESTION
    return binding


def test_transport_builds_semantic_request_and_returns_result() -> None:
    captured: dict = {}
    question = {"schema": "tribunal-question-draft/1.0", "question": "Which observation discriminates?"}

    def reverse_call(method: str, params: dict) -> dict:
        assert method == "semantic.execute"
        captured["request"] = json.loads(params["request"])
        return {"tool_result": {"ok": True, "runtime_status": "COMPLETED", "structured_output": {"text": json.dumps(question, ensure_ascii=False)}}}

    transport = PluginBridgeProviderTransport(reverse_call)
    result = transport.invoke(binding=_binding(), envelope=_envelope(), timeout_seconds=30)

    req = captured["request"]
    assert req["schema"] == "semantic-execution-request/1.0"
    assert req["purpose"] == "TRIBUNAL_ROLE"
    assert req["contract_schema"] == "tribunal-execution-envelope/1.1"
    assert req["role_ref"] == "physicist"
    assert req["timeout_ms"] == 30000
    assert "bounded_input" in req
    # Provider output is returned exactly (same contract as subprocess transport).
    assert result == question


def test_transport_rejects_non_completed_runtime() -> None:
    def reverse_call(method: str, params: dict) -> dict:
        return {"tool_result": {"ok": False, "runtime_status": "FAILED", "host_error": "model error"}}

    transport = PluginBridgeProviderTransport(reverse_call)
    with pytest.raises(TribunalLiveDialogueError):
        transport.invoke(binding=_binding(), envelope=_envelope(), timeout_seconds=30)


def test_transport_rejects_non_ready_binding() -> None:
    def reverse_call(method: str, params: dict) -> dict:
        raise AssertionError("must not call")

    transport = PluginBridgeProviderTransport(reverse_call)
    binding = _binding()
    binding.status = ProviderBindingStatus.NO_HEALTHY_PROVIDER
    with pytest.raises(TribunalLiveDialogueError):
        transport.invoke(binding=binding, envelope=_envelope(), timeout_seconds=30)


def test_transport_maps_each_execution_kind_to_purpose() -> None:
    from researcher_core.tribunal_live_dialogue import _role_execution_kind_to_purpose

    for kind in RoleExecutionKind:
        assert _role_execution_kind_to_purpose(kind) == "TRIBUNAL_ROLE"


def test_transport_propagates_plugin_failure_as_timeout() -> None:
    def reverse_call(method: str, params: dict) -> dict:
        raise RuntimeError("plugin child session crashed")

    transport = PluginBridgeProviderTransport(reverse_call)
    with pytest.raises(TribunalLiveDialogueError):
        transport.invoke(binding=_binding(), envelope=_envelope(), timeout_seconds=30)