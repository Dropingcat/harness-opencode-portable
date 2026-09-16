"""M3b boundary E2E: real reverse bridge channel for Coder semantic execution.

Topology:
    semantic_transport._execute_via_plugin_bridge
        -> spawns bridge_peer.py subprocess (NDJSON stdio)
        -> peer forwards semantic.execute as a REVERSE request to its stdout
        -> the TRANSPORT itself is the plugin-side consumer (BRIDGE-01): it
           reads the peer's stdout, distinguishes reverse requests from
           responses, services ``semantic.execute`` reverse requests through
           the injectable ``plugin_side`` callable, and writes the plugin
           envelope back to the peer's stdin
        -> peer returns the plugin result to semantic_transport

Coverage (BRIDGE-01..05):
  * production-equivalent wiring (NO test-injected relay): without
    ``plugin_side`` the transport must fail closed honestly (HOST_UNAVAILABLE)
    and must NOT misparse the peer's reverse request as a response;
  * with ``plugin_side``: full COMPLETED round-trip serviced in-process;
  * ``timeout_ms`` propagation (BRIDGE-03) — the peer awaits the reverse
    response with the request's timeout bound (capped at 120000), so a slow
    plugin-side handler completes instead of hitting the old 15s default;
  * non-dict input to the private bridge entry point is schema-valid
    HOST_UNAVAILABLE, never a raise (BRIDGE-04);
  * peer stderr is drained in the background (BRIDGE-05) — a chatty peer can
    never block on a full pipe buffer.

No network, no model, no OpenCode SDK. Deterministic fake plugin side.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
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


def _fake_plugin_completed(req: dict) -> dict:
    """Schema-valid COMPLETED result, as a real plugin would return."""
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


class _SlowPluginSide:
    """plugin_side that sleeps ~1.5x the default 15s reverse timeout.

    BRIDGE-03: with timeout_ms threaded through (capped at 120000) the peer
    awaits the reply for up to the REQUEST's timeout, so a healthy plugin that
    legitimately takes longer than the old hardcoded 15s must still COMPLETE.
    """

    def __init__(self, delay_s: float) -> None:
        self.delay_s = delay_s
        self.calls = 0

    def __call__(self, request: dict) -> dict:
        self.calls += 1
        time.sleep(self.delay_s)
        return _fake_plugin_completed(request)


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

    # --- BRIDGE-01: production-equivalent wiring -----------------------------

    def test_production_wiring_no_plugin_side_fails_closed_not_misparsed(self) -> None:
        """No plugin-side consumer: honest HOST_UNAVAILABLE, never a misparse.

        Production wiring (no test-injected relay, no ``plugin_side``): the
        transport spawns the peer and consumes its stdout itself. The peer's
        reverse request (a ``semantic.execute`` line with no ``ok``) must NOT
        be treated as the response to our call — the outcome is an honest
        HOST_UNAVAILABLE whose host_error does NOT echo the raw reverse
        request (BRIDGE-01 falsification: no 'bridge error ERROR: {...method:
        semantic.execute...}').
        """
        started = time.monotonic()
        res = st._execute_via_plugin_bridge(self._request(), timeout_s=15, plugin_side=None)
        elapsed = time.monotonic() - started

        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge failed", res["host_error"])
        # BRIDGE-01: the reverse request must never be misparsed as a response
        # nor echoed as a raw JSON blob inside host_error.
        self.assertNotIn("semantic.execute", res["host_error"])
        self.assertNotIn("bridge error ERROR", res["host_error"])
        # Honest fail-closed: never a fabricated COMPLETED.
        self.assertNotEqual(res["runtime_status"], "COMPLETED")
        self._assert_result_schema_valid(res)
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)
        # The peer answers the unserviceable reverse request immediately, so
        # this must complete quickly (well under the 15s timeout_s).
        self.assertLess(elapsed, 15.0)

    def test_execute_coder_semantic_no_plugin_side_honest_fail_closed(self) -> None:
        """Top-level entry, no plugin_side: honest HOST_UNAVAILABLE.

        Regression for BRIDGE-01/BRIDGE-02: the public entry point, when the
        bridge is nominally available but no plugin side is wired, must fail
        closed honestly — never a fabricated COMPLETED, never a misparse.
        """
        res = st.execute_coder_semantic(self._request())
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge failed", res["host_error"])
        self.assertNotIn("semantic.execute", res["host_error"])
        self._assert_result_schema_valid(res)
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)

    # --- BRIDGE-01: round-trip COMPLETED through in-process plugin_side ------

    def test_round_trip_via_plugin_bridge_completed(self) -> None:
        """plugin_side services the reverse request -> COMPLETED round-trip."""
        res = st._execute_via_plugin_bridge(
            self._request(), timeout_s=15, plugin_side=_fake_plugin_completed
        )

        self.assertEqual(res["runtime_status"], "COMPLETED")
        self.assertEqual(res["execution_id"], "m3b-e2e-roundtrip")
        self.assertEqual(res["schema"], "semantic-execution-result/1.0")
        self.assertIn("fake plugin COMPLETED", res["structured_output"]["text"])
        self._assert_result_schema_valid(res)
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)

    def test_execute_coder_semantic_forwards_plugin_side(self) -> None:
        """execute_coder_semantic(plugin_side=...) services the reverse request.

        The plugin-side consumer may be injected through the public entry
        point (BRIDGE-01: "execute_coder_semantic может пробрасывать
        plugin_side (по умолчанию None)").
        """
        res = st.execute_coder_semantic(
            self._request(), transport="plugin", plugin_side=_fake_plugin_completed
        )
        self.assertEqual(res["runtime_status"], "COMPLETED")
        self.assertIn("fake plugin COMPLETED", res["structured_output"]["text"])
        self._assert_result_schema_valid(res)

    def test_plugin_side_error_fails_closed(self) -> None:
        """A raising plugin_side -> error envelope -> honest HOST_UNAVAILABLE."""

        def _boom(_request: dict) -> dict:
            raise RuntimeError("fake plugin execution failed")

        res = st._execute_via_plugin_bridge(self._request(), timeout_s=15, plugin_side=_boom)
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge failed", res["host_error"])
        self._assert_result_schema_valid(res)

    def test_plugin_side_invalid_result_fails_closed(self) -> None:
        """A schema-invalid plugin_side result must NOT be accepted."""

        def _invalid(_request: dict) -> dict:
            return {"runtime_status": "COMPLETED"}  # not SemanticExecutionResult/1.0

        res = st._execute_via_plugin_bridge(self._request(), timeout_s=15, plugin_side=_invalid)
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge failed", res["host_error"])
        self._assert_result_schema_valid(res)

    # --- BRIDGE-03: timeout_ms propagation through the reverse call ----------

    def test_timeout_ms_propagates_to_reverse_await(self) -> None:
        """A slow plugin side completes when timeout_ms is threaded through.

        BRIDGE-03: the peer's ``_await_reverse`` must honour the request's
        timeout_ms (capped at 120000) instead of the hardcoded 15s default.
        Without propagation this 20s handler would fail as a fabricated
        HOST_UNAVAILABLE; with propagation it COMPLETES.
        """
        delay_s = 20.0
        slow = _SlowPluginSide(delay_s=delay_s)
        started = time.monotonic()
        res = st._execute_via_plugin_bridge(
            self._request(timeout_ms=60000), timeout_s=60, plugin_side=slow
        )
        elapsed = time.monotonic() - started

        self.assertEqual(slow.calls, 1)
        self.assertEqual(res["runtime_status"], "COMPLETED")
        # The handler actually ran for its full delay (not cut off at 15s).
        self.assertGreaterEqual(elapsed, delay_s - 1.0)
        self._assert_result_schema_valid(res)

    # --- BRIDGE-04: non-dict input safety ------------------------------------

    def test_non_dict_input_safe(self) -> None:
        """Non-dict input to the bridge entry point never raises.

        BRIDGE-04: the fail-closed handler must not index a non-dict request.
        The result is a schema-valid HOST_UNAVAILABLE, never a KeyError/
        TypeError escaping the private API.
        """
        for bad in (None, "not-a-dict", ["x", 1], 42, 3.14):
            with self.subTest(bad=type(bad).__name__):
                res = st._execute_via_plugin_bridge(bad, timeout_s=5)  # must not raise
                self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
                self._assert_result_schema_valid(res)
                ok, error = st._validate_result(res)
                self.assertTrue(ok, msg=error)

    # --- Legacy tests retained (fail-closed paths) ---------------------------

    def test_plugin_error_fails_closed(self) -> None:
        """A plugin-side consumer that errors -> honest HOST_UNAVAILABLE."""

        def _plugin_error(_request: dict) -> dict:
            raise RuntimeError("fake plugin execution failed")

        res = st._execute_via_plugin_bridge(self._request(), timeout_s=15, plugin_side=_plugin_error)
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

    # --- BRIDGE-05: chatty stderr must never block the channel ---------------

    def test_chatty_stderr_peer_is_still_serviced(self) -> None:
        """A peer that floods stderr (1MB, > OS pipe buffer) still round-trips.

        BRIDGE-05: the transport drains proc.stderr in the background. Without
        that drain, a chatty peer would block on a full pipe buffer and the
        healthy execution would be failed as HOST_UNAVAILABLE.
        """
        import shutil
        import tempfile

        fake_peer = """\
import json, sys
# Flood stderr well past the OS pipe buffer (~64KB on Windows).
sys.stderr.write("x" * (1024 * 1024) + "\\n")
sys.stderr.flush()
msg = json.loads(sys.stdin.readline())
rid = msg["id"]
# Emit a reverse semantic.execute request; the transport (plugin-side
# consumer) answers it on our stdin.
sys.stdout.write(json.dumps(
    {"id": "rev-1", "method": "semantic.execute", "params": {"request": msg["params"]["request"]}}
) + "\\n")
sys.stdout.flush()
answer = json.loads(sys.stdin.readline())
# Forward the plugin result to the transport with the real peer's envelope:
# the handler returns {"semantic_result": <tool_result>}.
tool_result = answer["result"]["tool_result"]
sys.stdout.write(json.dumps(
    {"id": rid, "ok": answer.get("ok"), "result": {"semantic_result": tool_result}}
) + "\\n")
sys.stdout.flush()
"""
        tmp = Path(tempfile.mkdtemp(prefix="m3b_chatty_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        peer_dir = tmp / "packages" / "opencode-harness-plugin" / "core"
        peer_dir.mkdir(parents=True)
        (peer_dir / "bridge_peer.py").write_text(fake_peer, encoding="utf-8")

        saved_root = os.environ.get("OPENCODE_HARNESS_ROOT")
        try:
            os.environ["OPENCODE_HARNESS_ROOT"] = str(tmp)
            res = st._execute_via_plugin_bridge(
                self._request(), timeout_s=30, plugin_side=_fake_plugin_completed
            )
        finally:
            if saved_root is None:
                os.environ.pop("OPENCODE_HARNESS_ROOT", None)
            else:
                os.environ["OPENCODE_HARNESS_ROOT"] = saved_root

        self.assertEqual(res["runtime_status"], "COMPLETED")
        self.assertIn("fake plugin COMPLETED", res["structured_output"]["text"])
        self._assert_result_schema_valid(res)


if __name__ == "__main__":
    unittest.main(verbosity=2)