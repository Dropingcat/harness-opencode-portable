"""
P4 integration: PluginBridgeProviderTransport wired to the real bridge peer's
full-duplex reverse channel. Core -> bridge peer -> (fake plugin reverse handler)
-> semantic result -> back to transport.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_root / "scripts" / "researcher"))

from researcher_core.tribunal_live_dialogue import PluginBridgeProviderTransport
from researcher_core.tribunal_provider_binding import RoleExecutionKind, ProviderBindingStatus


class _FakePlugin:
    """Acts like the TS plugin's reverse handler for semantic.execute."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def handle(self, method: str, params: dict) -> dict:
        if method != "semantic.execute":
            raise RuntimeError(f"unexpected method: {method}")
        self.calls.append(json.loads(params["request"]))
        return {"tool_result": {"ok": True, "runtime_status": "COMPLETED", "structured_output": {"text": "PLUGIN_ANSWER"}}}


@pytest.fixture()
def peer():
    proc = _spawn_peer()
    yield proc
    proc.stdin.close()
    proc.wait(timeout=5)


def test_transport_through_real_bridge() -> None:
    fake = _FakePlugin()
    transport = PluginBridgeProviderTransport(fake.handle)

    envelope = {
        "schema_version": "tribunal-execution-envelope/1.1",
        "meta": {"id": "tex-1", "run_id": "run-9", "created_by": {"kind": "AGENT", "id": "researcher"}},
        "id": "tex-1",
        "binding_id": "rpb-1",
        "role_id": "physicist",
        "execution_kind": "QUESTION",
        "branch_key": "q1",
        "output_contract": {},
    }

    results: list[dict] = []
    errors: list[Exception] = []

    def runner() -> None:
        try:
            r = transport.invoke(binding=MagicMock(
                status=ProviderBindingStatus.READY,
                execution_kind=RoleExecutionKind.QUESTION,
            ), envelope_dict=envelope, timeout_seconds=5)
            results.append(r)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=runner)
    t.start()
    t.join(timeout=10)

    assert not errors, errors
    assert len(results) == 1
    assert results[0]["semantic_execution_result"]["runtime_status"] == "COMPLETED"
    assert results[0]["semantic_execution_result"]["structured_output"]["text"] == "PLUGIN_ANSWER"
    assert fake.calls[0]["schema"] == "semantic-execution-request/1.0"
    assert fake.calls[0]["role_ref"] == "physicist"