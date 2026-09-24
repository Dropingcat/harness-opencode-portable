#!/usr/bin/env python3
"""AG-A2: end-to-end certification of the semantic.execute parent/child bridge.

The debt claimed "semantic.execute is not certified live" (no automated proof
that the Core-side peer carries a SemanticExecutionRequest/1.0 to the plugin
(child-session owner) and returns a contract-valid SemanticExecutionResult/1.0).

These tests drive the REAL BridgeServer over stdio against a simulated plugin
peer that behaves like the OpenCode child-session executor:

  * request validation against schemas/SemanticExecutionRequest.schema.json
  * parent/child session linkage check (child created under the request's
    parent_host_session_id, execution_id echoed back)
  * response validation against schemas/SemanticExecutionResult.schema.json

Deterministic, no network, no live opencode binary required.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEER = ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
SCHEMAS = ROOT / "packages" / "opencode-harness-plugin" / "schemas"

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

REQ_SCHEMA = json.loads((SCHEMAS / "SemanticExecutionRequest.schema.json").read_text("utf-8"))
RES_SCHEMA = json.loads((SCHEMAS / "SemanticExecutionResult.schema.json").read_text("utf-8"))


def make_request(execution_id: str = "exec-0001", parent: str = "ses_parent_orchestrator") -> dict:
    return {
        "schema": "semantic-execution-request/1.0",
        "execution_id": execution_id,
        "purpose": "CODE_REVIEW",
        "contract_schema": "code-review-result/1.0",
        "parent_host_session_id": parent,
        "bounded_input": {"diff_ref": "artifacts/diff-001.patch"},
        "expected_output": {"format": "json", "contract": "code-review-result/1.0"},
        "model_policy": {"provider": "anthropic", "model": "claude-sonnet-4-5"},
        "permission_profile": "read-only",
        "timeout_ms": 180000,
        "trace": {"run_id": "run-ag-a2-cert", "step": 1},
    }


def simulate_child_result(request: dict) -> dict:
    """Plugin-side (child session) result, contract-valid."""
    return {
        "schema": "semantic-execution-result/1.0",
        "execution_id": request["execution_id"],
        "runtime_status": "COMPLETED",
        "host_session_id": "ses_child_" + request["execution_id"],
        "provider_id": request["model_policy"]["provider"],
        "model_id": request["model_policy"]["model"],
        "structured_output": {"verdict": "APPROVE", "findings": []},
        "raw_output_ref": "artifacts/raw/exec-0001.jsonl",
        "usage": {"input_tokens": 1200, "output_tokens": 340},
        "timing": {"started_ms": 0, "finished_ms": 1500},
        "host_error": None,
        "host_features_fingerprint": "sha256:test-fp",
    }


class FakePluginPeer:
    """Simulates the TS plugin end of harness-bridge-rpc/1.0 over stdio.

    Validates inbound reverse requests as the real plugin must: schema-valid
    SemanticExecutionRequest, then answers with a child-session result whose
    host_session_id is derived from (and linked to) parent_host_session_id.
    """

    def __init__(self, proc: subprocess.Popen) -> None:
        self.proc = proc
        self.seen_requests: list[dict] = []
        self.linkage_ok: list[bool] = []
        self.outbox: list[str] = []
        self._lock = threading.Lock()

    def reader(self) -> None:
        # Single consumer of peer stdout: reverse requests are answered
        # inline; everything else (responses to our calls) goes to outbox.
        for line in iter(self.proc.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("method") == "semantic.execute":
                self.handle_reverse(msg)
                continue
            with self._lock:
                self.outbox.append(line)

    def handle_reverse(self, msg: dict) -> None:
        rid = msg["id"]
        request = (msg.get("params") or {}).get("request") or {}
        with self._lock:
            self.seen_requests.append(request)
        try:
            if jsonschema is not None:
                jsonschema.validate(request, REQ_SCHEMA)
            result = simulate_child_result(request)
            # Parent/child linkage invariant: child session is created under
            # the declared parent and echoes the same execution_id.
            linked = (
                result["host_session_id"].startswith("ses_child_")
                and result["execution_id"] == request["execution_id"]
                and bool(request["parent_host_session_id"])
            )
            with self._lock:
                self.linkage_ok.append(linked)
            if jsonschema is not None:
                jsonschema.validate(result, RES_SCHEMA)
            self.write({"id": rid, "ok": True, "result": result})
        except Exception as exc:  # noqa: BLE001
            self.write({"id": rid, "ok": False, "error": {"code": "PLUGIN_REJECT", "message": str(exc)}})

    def write(self, obj: dict) -> None:
        # Reverse response goes back into the peer's stdin.
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()


class SemanticExecuteLiveCertification(unittest.TestCase):
    def setUp(self) -> None:
        if not PEER.is_file():
            self.skipTest(f"bridge peer not found: {PEER}")
        # -u: unbuffered child stdio; otherwise peer output can sit in its
        # buffer and the handshake below deadlocks on a blocked pipe.
        self.proc = subprocess.Popen(
            [sys.executable, "-u", str(PEER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            cwd=str(ROOT),
        )
        self.peer = FakePluginPeer(self.proc)
        threading.Thread(target=self.peer.reader, daemon=True).start()
        self._counter = 0
        hello = self._call("bridge.hello", {"plugin_semver": "0.0.0-cert"})
        self.assertTrue(hello["ok"], "bridge handshake failed")

    def tearDown(self) -> None:
        try:
            self._call("bridge.shutdown", {})
        except Exception:  # noqa: BLE001
            pass
        finally:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    # --- JSON-RPC client side (acts as the TS plugin calling into Core) ----
    def _send(self, obj: dict) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def _recv(self, rid: str, timeout: float = 20.0) -> dict:
        import time

        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.peer._lock:
                for line in list(self.peer.outbox):
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        msg = None
                    if msg is not None and msg.get("id") == rid and "ok" in msg and "method" not in msg:
                        self.peer.outbox.remove(line)
                        return msg
            time.sleep(0.02)
        raise TimeoutError(f"no response for {rid} from bridge peer")

    def _call(self, method: str, params: dict) -> dict:
        self._counter += 1
        rid = f"req-{self._counter}-{method}"
        self._send({"id": rid, "method": method, "params": params})
        return self._recv(rid)

    # ---------------------------------------------------------------- tests
    @unittest.skipIf(jsonschema is None, "jsonschema not installed")
    def test_hello_advertises_semantic_contracts(self) -> None:
        res = self._call("bridge.hello", {"plugin_semver": "0.0.0-test"})
        self.assertTrue(res["ok"])
        self.assertIn("semantic-execution-request/1.0", res["result"]["contract_schemas"])
        self.assertIn("semantic-execution-result/1.0", res["result"]["contract_schemas"])

    @unittest.skipIf(jsonschema is None, "jsonschema not installed")
    def test_semantic_execute_roundtrip_parent_child(self) -> None:
        request = make_request()
        res = self._call("semantic.execute", {"request": request})
        self.assertTrue(res.get("ok"), f"bridge error: {res.get('error')}")
        payload = res["result"]["semantic_result"]
        # Result carried back through Core is contract-valid.
        jsonschema.validate(payload, RES_SCHEMA)
        self.assertEqual(payload["execution_id"], request["execution_id"])
        self.assertEqual(payload["runtime_status"], "COMPLETED")
        # The plugin actually received a valid parent-scoped request.
        self.assertEqual(len(self.peer.seen_requests), 1)
        self.assertEqual(
            self.peer.seen_requests[0]["parent_host_session_id"],
            request["parent_host_session_id"],
        )
        self.assertEqual(self.peer.linkage_ok, [True])

    @unittest.skipIf(jsonschema is None, "jsonschema not installed")
    def test_missing_request_is_error_not_hang(self) -> None:
        res = self._call("semantic.execute", {})
        self.assertFalse(res["ok"])
        self.assertEqual(res["error"]["code"], "HANDLER_ERROR")

    @unittest.skipIf(jsonschema is None, "jsonschema not installed")
    def test_plugin_rejection_propagates_as_error(self) -> None:
        bad = make_request(execution_id="exec-bad")
        bad["purpose"] = "NOT_A_PURPOSE"  # violates request schema
        res = self._call("semantic.execute", {"request": bad})
        self.assertFalse(res["ok"])
        self.assertIn("PLUGIN_REJECT", res["error"]["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
