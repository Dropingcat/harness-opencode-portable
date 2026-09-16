"""M3b boundary E2E: real reverse bridge channel for Coder semantic execution.

Topology:
    semantic_transport._execute_via_plugin_bridge
        -> spawns bridge_peer.py subprocess (NDJSON stdio)
        -> peer forwards semantic.execute as a REVERSE request to its stdout
        -> fake plugin side (in-test relay) reads peer.stdout, answers on peer.stdin
        -> peer returns the plugin result to semantic_transport

No network, no model, no OpenCode SDK. Deterministic fake plugin side.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CODE_FACTORY = _ROOT / "scripts" / "code-factory"
if str(_CODE_FACTORY) not in sys.path:
    sys.path.insert(0, str(_CODE_FACTORY))

import semantic_transport as st  # noqa: E402

_PEER = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"

try:
    import jsonschema  # noqa: F401
    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    HAVE_JSONSCHEMA = False

_SCHEMA_PATH = _ROOT / "packages" / "opencode-harness-plugin" / "schemas" / "SemanticExecutionResult.schema.json"

_KEYS = ("HARNESS_SEMANTIC_ENABLED", "OPENCODE_HARNESS_ROOT", "HARNESS_TRANSPORT")


class _FakePluginRelay:
    """Reads the peer's stdout, answers reverse semantic.execute requests.

    Mirrors the real plugin's `bridge.onRequest` handler shape: the peer emits
    `{"id", "method": "semantic.execute", "params": {"request": ...}}`, and the
    plugin answers `{"id", "ok": true, "result": {"tool_result": <result>}}`.
    """

    def __init__(self, mode: str = "ok"):
        self.mode = mode
        self.requests: list[dict] = []
        self._stop = False

    def start(self, peer_stdout, peer_stdin) -> threading.Thread:
        def _run() -> None:
            for raw in peer_stdout:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict) or "method" not in msg:
                    continue
                self.requests.append(msg)
                rid = msg.get("id")
                if msg.get("method") != "semantic.execute":
                    reply = {"id": rid, "ok": False, "error": {"code": "NO_METHOD", "message": str(msg.get("method"))}}
                elif self.mode == "error":
                    reply = {"id": rid, "ok": False, "error": {"code": "PLUGIN_ERROR", "message": "fake plugin execution failed"}}
                else:
                    params = msg.get("params") or {}
                    req = params.get("request") or {}
                    reply = {"id": rid, "ok": True, "result": {"tool_result": self._completed(req)}}
                peer_stdin.write(json.dumps(reply, ensure_ascii=False) + "\n")
                peer_stdin.flush()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return t

    @staticmethod
    def _completed(req: dict) -> dict:
        policy = req.get("model_policy") or {}
        return {
            "schema": "semantic-execution-result/1.0",
            "execution_id": req.get("execution_id") or "unknown",
            "runtime_status": "COMPLETED",
            "host_session_id": "fake-plugin-session",
            "provider_id": policy.get("provider_id") or "fake-provider",
            "model_id": policy.get("model_id") or "fake-model",
            "structured_output": {"text": "fake plugin COMPLETED: " + json.dumps(req.get("bounded_input") or {}, ensure_ascii=False)},
            "raw_output_ref": None,
            "usage": {"total_tokens": 7},
            "timing": {"duration_ms": 2},
            "host_error": None,
            "host_features_fingerprint": None,
        }


class BridgeChannelE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        if not _PEER.is_file():
            self.skipTest("bridge peer file not present in this checkout")
        self._saved = {k: os.environ.get(k) for k in _KEYS}
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        os.environ.pop("HARNESS_TRANSPORT", None)

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _request(self, **overrides):
        req = st.build_coder_request(
            execution_id="m3b-e2e-roundtrip",
            purpose="CODE_WORK",
            bounded_input={"task": "implement X", "workdir": "feature/m3b"},
            expected_output={"schema": "coder-contract/1.0"},
            worktree="feature/m3b",
        )
        req.update(overrides)
        return req

    def _assert_result_schema_valid(self, res: dict) -> None:
        if HAVE_JSONSCHEMA:
            import jsonschema

            schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(instance=res, schema=schema)

    def test_round_trip_via_plugin_bridge_completed(self) -> None:
        # Patch Popen so the transport-spawned peer's stdio is relayed to the fake plugin.
        real_popen = subprocess.Popen
        relay = _FakePluginRelay(mode="ok")

        def _wired_popen(*args, **kwargs):
            peer = real_popen(*args, **kwargs)
            relay.start(peer.stdout, peer.stdin)
            return peer

        orig = st.subprocess.Popen if hasattr(st, "subprocess") else None
        import subprocess as sp

        saved_popen = sp.Popen
        try:
            sp.Popen = _wired_popen  # type: ignore[assignment]
            res = st._execute_via_plugin_bridge(self._request(), timeout_s=15)
        finally:
            sp.Popen = saved_popen  # type: ignore[assignment]

        self.assertEqual(res["runtime_status"], "COMPLETED")
        self.assertEqual(res["execution_id"], "m3b-e2e-roundtrip")
        self.assertEqual(res["schema"], "semantic-execution-result/1.0")
        self.assertIn("fake plugin COMPLETED", res["structured_output"]["text"])
        self._assert_result_schema_valid(res)
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)
        self.assertEqual(len(relay.requests), 1)
        self.assertEqual(relay.requests[0]["method"], "semantic.execute")

    def test_plugin_error_fails_closed(self) -> None:
        real_popen = subprocess.Popen
        relay = _FakePluginRelay(mode="error")

        def _wired_popen(*args, **kwargs):
            peer = real_popen(*args, **kwargs)
            relay.start(peer.stdout, peer.stdin)
            return peer

        import subprocess as sp

        saved_popen = sp.Popen
        try:
            sp.Popen = _wired_popen  # type: ignore[assignment]
            res = st._execute_via_plugin_bridge(self._request(), timeout_s=15)
        finally:
            sp.Popen = saved_popen  # type: ignore[assignment]

        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge failed", res["host_error"])
        self._assert_result_schema_valid(res)

    def test_spawn_failure_fails_closed(self) -> None:
        import subprocess as sp

        def _boom(*args, **kwargs):
            raise OSError("peer spawn blocked for test")

        saved_popen = sp.Popen
        try:
            sp.Popen = _boom  # type: ignore[assignment]
            res = st._execute_via_plugin_bridge(self._request(), timeout_s=5)
        finally:
            sp.Popen = saved_popen  # type: ignore[assignment]

        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge failed", res["host_error"])
        self._assert_result_schema_valid(res)

    def test_missing_peer_file_fails_closed(self) -> None:
        saved_root = os.environ.get("OPENCODE_HARNESS_ROOT")
        try:
            os.environ["OPENCODE_HARNESS_ROOT"] = str(Path(__file__).resolve().parent)  # no peer here
            res = st._execute_via_plugin_bridge(self._request(), timeout_s=5)
        finally:
            if saved_root is None:
                os.environ.pop("OPENCODE_HARNESS_ROOT", None)
            else:
                os.environ["OPENCODE_HARNESS_ROOT"] = saved_root

        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self._assert_result_schema_valid(res)


if __name__ == "__main__":
    unittest.main(verbosity=2)