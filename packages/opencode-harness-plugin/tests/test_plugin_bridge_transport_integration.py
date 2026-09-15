"""
P4 integration: PluginBridgeProviderTransport wired to the real bridge peer's
full-duplex reverse channel. Core -> bridge peer -> (fake plugin reverse handler)
-> semantic result -> back to transport.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_root / "scripts" / "researcher"))

from researcher_core.tribunal_live_dialogue import (
    PluginBridgeProviderTransport,
    TribunalExecutionEnvelope,
    _execution_envelope_integrity_payload,
    _fp,
)
from researcher_core.tribunal_provider_binding import (
    RoleExecutionKind,
    ProviderBindingStatus,
    EntityId,
    EntityMeta,
    ActorRef,
)
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


class _FakePlugin:
    """Acts like the TS plugin's reverse handler for semantic.execute."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def handle(self, method: str, params: dict) -> dict:
        if method != "semantic.execute":
            raise RuntimeError(f"unexpected method: {method}")
        self.calls.append(json.loads(params["request"]))
        draft = json.dumps({"schema": "tribunal-question-draft/1.0", "question": "Which observation discriminates?"}, ensure_ascii=False)
        return {"tool_result": {"ok": True, "runtime_status": "COMPLETED", "structured_output": {"text": draft}}}


@pytest.fixture()
def peer():
    proc = _spawn_peer()
    yield proc
    proc.stdin.close()
    proc.wait(timeout=5)


def test_transport_through_real_bridge() -> None:
    fake = _FakePlugin()
    transport = PluginBridgeProviderTransport(fake.handle)

    results: list[dict] = []
    errors: list[Exception] = []

    def runner() -> None:
        try:
            r = transport.invoke(binding=MagicMock(
                status=ProviderBindingStatus.READY,
                execution_kind=RoleExecutionKind.QUESTION,
            ), envelope=_envelope(), timeout_seconds=5)
            results.append(r)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=runner)
    t.start()
    t.join(timeout=10)

    assert not errors, errors
    assert len(results) == 1
    assert results[0]["schema"] == "tribunal-question-draft/1.0"
    assert results[0]["question"].strip()
    assert fake.calls[0]["schema"] == "semantic-execution-request/1.0"
    assert fake.calls[0]["role_ref"] == "physicist"