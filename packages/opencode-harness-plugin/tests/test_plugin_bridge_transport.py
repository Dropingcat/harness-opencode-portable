"""
PluginBridgeProviderTransport: Tribunal transport via the native plugin bridge.
Verifies envelope dict -> SemanticExecutionRequest mapping and result routing
without touching the real model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Harness root: <root>/packages/opencode-harness-plugin/tests -> parents[3]
_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_root / "scripts" / "researcher"))

from researcher_core.tribunal_live_dialogue import (
    PluginBridgeProviderTransport,
    TribunalLiveDialogueError,
)
from researcher_core.tribunal_provider_binding import (
    RoleExecutionKind,
    ProviderBindingStatus,
)


def _binding(execution_kind: RoleExecutionKind = RoleExecutionKind.QUESTION):
    binding = MagicMock()
    binding.status = ProviderBindingStatus.READY
    binding.execution_kind = execution_kind
    return binding


def _envelope_dict() -> dict:
    return {
        "schema_version": "tribunal-execution-envelope/1.1",
        "meta": {"id": "tex-456", "run_id": "run-1", "created_by": {"kind": "AGENT", "id": "researcher"}},
        "id": "tex-456",
        "binding_id": "rpb-123",
        "role_id": "physicist",
        "execution_kind": "QUESTION",
        "branch_key": "q1",
        "output_contract": {},
    }


def test_transport_builds_semantic_request_and_returns_result() -> None:
    captured: dict = {}

    def reverse_call(method: str, params: dict) -> dict:
        assert method == "semantic.execute"
        captured["request"] = json.loads(params["request"])
        return {"tool_result": {"ok": True, "runtime_status": "COMPLETED", "structured_output": {"text": "OK"}}}

    transport = PluginBridgeProviderTransport(reverse_call)
    result = transport.invoke(binding=_binding(), envelope_dict=_envelope_dict(), timeout_seconds=30)

    req = captured["request"]
    assert req["schema"] == "semantic-execution-request/1.0"
    assert req["purpose"] == "TRIBUNAL_ROLE"
    assert req["contract_schema"] == "tribunal-execution-envelope/1.1"
    assert req["role_ref"] == "physicist"
    assert req["timeout_ms"] == 30000
    assert "bounded_input" in req
    assert "execution_envelope" in result
    assert result["semantic_execution_result"]["runtime_status"] == "COMPLETED"


def test_transport_rejects_non_ready_binding() -> None:
    def reverse_call(method: str, params: dict) -> dict:
        raise AssertionError("must not call")

    transport = PluginBridgeProviderTransport(reverse_call)
    binding = _binding()
    binding.status = ProviderBindingStatus.NO_HEALTHY_PROVIDER
    with pytest.raises(TribunalLiveDialogueError):
        transport.invoke(binding=binding, envelope_dict=_envelope_dict(), timeout_seconds=30)


def test_transport_maps_each_execution_kind_to_purpose() -> None:
    from researcher_core.tribunal_live_dialogue import _role_execution_kind_to_purpose

    for kind in RoleExecutionKind:
        assert _role_execution_kind_to_purpose(kind) == "TRIBUNAL_ROLE"


def test_transport_propagates_plugin_failure_as_timeout() -> None:
    def reverse_call(method: str, params: dict) -> dict:
        raise RuntimeError("plugin child session crashed")

    transport = PluginBridgeProviderTransport(reverse_call)
    with pytest.raises(TribunalLiveDialogueError):
        transport.invoke(binding=_binding(), envelope_dict=_envelope_dict(), timeout_seconds=30)