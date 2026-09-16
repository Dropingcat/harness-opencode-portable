"""In-process unit tests for bridge_peer.py (coverage driver).

Exercises BridgeServer handlers directly in-process so `coverage run
--source=bridge_peer` sees real lines (the discover suite only exercises the
peer as a spawned subprocess, invisible to coverage).

No network, no model, no OpenCode SDK.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CORE = _ROOT / "packages" / "opencode-harness-plugin" / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import bridge_peer as bp  # noqa: E402


def _request(**overrides):
    req = {
        "schema": "semantic-execution-request/1.0",
        "execution_id": "peer-cov",
        "purpose": "CODE_WORK",
        "contract_schema": "coder-contract/1.0",
        "parent_host_session_id": "peer-cov-host",
        "bounded_input": {"task": "t"},
        "expected_output": {},
        "model_policy": {"provider_id": "p", "model_id": "m"},
        "permission_profile": "code-worker-write",
        "timeout_ms": 60000,
        "trace": {"worktree": "w"},
    }
    req.update(overrides)
    return req


def _completed(req):
    return {
        "schema": "semantic-execution-result/1.0",
        "execution_id": req.get("execution_id") or "unknown",
        "runtime_status": "COMPLETED",
        "host_session_id": "cov-session",
        "provider_id": "p",
        "model_id": "m",
        "structured_output": {"text": "ok"},
        "raw_output_ref": None,
        "usage": {},
        "timing": {},
        "host_error": None,
        "host_features_fingerprint": None,
    }


class BridgePeerDirectTests(unittest.TestCase):
    def setUp(self):
        self.server = bp.BridgeServer(_ROOT)
        # Pre-init the state serve() would create (unit-test affordance).
        self.server._pending_reverse = {}
        self.server._inbox = __import__("queue").Queue()
        self.server.reverse_request = self.server._send_reverse
        self.server._shutdown_requested = False

    def _plugin_side(self, req):
        return _completed(req)

    def test_request_timeout_ms_cap(self):
        self.assertEqual(bp._request_timeout_ms({"timeout_ms": 60000}), 60000)
        self.assertEqual(bp._request_timeout_ms({"timeout_ms": 10**9}), 120000)  # capped
        self.assertIsNone(bp._request_timeout_ms({"timeout_ms": True}))
        self.assertIsNone(bp._request_timeout_ms({"timeout_ms": 0}))
        self.assertIsNone(bp._request_timeout_ms({"timeout_ms": -5}))
        self.assertIsNone(bp._request_timeout_ms(None))
        self.assertIsNone(bp._request_timeout_ms("nope"))

    def test_semantic_execute_requires_reverse_and_request(self):
        with self.assertRaises(RuntimeError):
            bp.BridgeServer(_ROOT)._semantic_execute({"request": _request()})
        with self.assertRaises(ValueError):
            self.server._semantic_execute({})
        with self.assertRaises(ValueError):
            self.server._semantic_execute({"request": None})

    def test_semantic_execute_roundtrip_with_reverse_stub(self):
        captured = {}

        def _fake_send_reverse(method, params, timeout_ms=None):
            captured["method"] = method
            captured["timeout_ms"] = timeout_ms
            return {"tool_result": _completed(params["request"])}

        self.server._send_reverse = _fake_send_reverse  # type: ignore[assignment]
        out = self.server._semantic_execute({"request": _request(timeout_ms=45000)})
        self.assertEqual(captured["method"], "semantic.execute")
        self.assertEqual(captured["timeout_ms"], 45000)
        self.assertEqual(out["semantic_result"]["runtime_status"], "COMPLETED")

    def test_semantic_execute_raw_result_envelope(self):
        def _fake_send_reverse(method, params, timeout_ms=None):
            return _completed(params["request"])  # no tool_result wrapper

        self.server._send_reverse = _fake_send_reverse  # type: ignore[assignment]
        out = self.server._semantic_execute({"request": _request()})
        self.assertEqual(out["semantic_result"]["runtime_status"], "COMPLETED")

    def test_hello_health_status(self):
        hello = self.server._hello({"plugin_semver": "1.2.3"})
        self.assertEqual(hello["schema"], bp.PROTOCOL)
        self.assertEqual(hello["plugin_semver"], "1.2.3")
        self.assertIn("semantic-execution-result/1.0", hello["contract_schemas"])
        health = self.server._health({})
        self.assertIn("ok", health)
        status = self.server._status({})
        self.assertTrue(status["ok"])
        self.assertEqual(status["protocol"], bp.PROTOCOL)

    def test_reverse_echo_test(self):
        calls = {}

        def _fake_send_reverse(method, params, timeout_ms=None):
            calls["method"] = method
            return "echo-reply"

        self.server.reverse_request = _fake_send_reverse  # type: ignore[assignment]
        self.assertEqual(self.server._reverse_echo_test({"value": 3}), {"reverse_result": "echo-reply"})
        self.assertEqual(calls["method"], "semantic.execute")

    def test_resolve_reverse_and_await(self):
        # Simulate a reverse call: _send_reverse registers pending, then
        # _resolve_reverse resolves it via an incoming message, _await_reverse
        # returns the result.
        import queue
        import threading

        result_holder = {}

        def _do():
            rid = "rid-1"
            self.server._pending_reverse[rid] = {"resolved": False, "result": None, "error": None}
            # Simulate the reader thread resolving it.
            self.server._resolve_reverse({"id": rid, "ok": True, "result": {"x": 1}})
            result_holder["result"] = self.server._await_reverse(rid, timeout_ms=2000)

        t = threading.Thread(target=_do)
        t.start()
        t.join(timeout=5)
        self.assertEqual(result_holder["result"], {"x": 1})

    def test_resolve_reverse_error_and_shutdown(self):
        self.server._shutdown()
        self.assertTrue(self.server._shutdown_requested)
        rid = "rid-err"
        self.server._pending_reverse[rid] = {"resolved": False, "result": None, "error": None}
        self.server._resolve_reverse({"id": rid, "ok": False, "error": {"code": "E", "message": "boom"}})
        with self.assertRaises(RuntimeError):
            self.server._await_reverse(rid, timeout_ms=1000)

    def test_harness_root_fallback(self):
        saved = os.environ.get("OPENCODE_HARNESS_ROOT")
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        try:
            self.assertEqual(bp._harness_root(), _ROOT)  # parents[3] of core/bridge_peer.py
        finally:
            if saved is not None:
                os.environ["OPENCODE_HARNESS_ROOT"] = saved

    def test_serve_loop_in_process(self):
        """Real serve() loop with faked stdio: reader thread + dispatch + shutdown.

        This exercises the same serve-loop/reader-thread/_write paths that the
        E2E tests hit via a spawned subprocess (invisible to coverage there).
        """
        import io

        server = bp.BridgeServer(_ROOT)
        lines = [
            json.dumps({"id": "s1", "method": "bridge.hello", "params": {"plugin_semver": "9.9.9"}}),
            json.dumps({"id": "s2", "method": "harness.status", "params": {}}),
            "not-json-line",
            json.dumps({"id": "s4", "method": "no.such.method", "params": {}}),
            json.dumps({"id": "s5"}),  # no method -> skipped
            json.dumps({"id": "s3", "method": "bridge.shutdown", "params": {}}),
        ]
        fake_stdin = io.StringIO("\n".join(lines) + "\n")
        fake_stdout = io.StringIO()
        real_stdin, real_stdout = sys.stdin, sys.stdout
        sys.stdin, sys.stdout = fake_stdin, fake_stdout
        try:
            t = threading.Thread(target=server.serve, daemon=True)
            t.start()
            t.join(timeout=10)
        finally:
            sys.stdin, sys.stdout = real_stdin, real_stdout
        self.assertFalse(t.is_alive(), "serve() must exit after bridge.shutdown")
        out = fake_stdout.getvalue()
        parsed = [json.loads(ln) for ln in out.splitlines() if ln.strip()]
        by_id = {m["id"]: m for m in parsed}
        self.assertEqual(by_id["s1"]["ok"], True)
        self.assertEqual(by_id["s1"]["result"]["schema"], bp.PROTOCOL)
        self.assertEqual(by_id["s2"]["ok"], True)
        self.assertEqual(by_id["s4"]["ok"], False)
        self.assertEqual(by_id["s4"]["error"]["code"], "NO_METHOD")


if __name__ == "__main__":
    unittest.main(verbosity=2)