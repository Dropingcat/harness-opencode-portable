"""Code-tester autotests for the Coder semantic transport / bridge channel.

Hard coverage of the transport boundary (DEV-05 / BRIDGE-01..05), extending
the existing suites with focused, deterministic, in-process tests:

* ``bridge_peer._semantic_execute`` — request validation, reverse wiring,
  ``timeout_ms`` capping and validation, tool_result vs raw result envelope.
* ``bridge_peer._send_reverse`` / ``_await_reverse`` — timeout, ok=False
  error envelope, ok=True result, default (None) reverse timeout.
* ``bridge_peer`` serve-loop — a request without ``params.request`` is wrapped
  as ``HANDLER_ERROR`` (never leaks a ValueError to the wire).
* ``semantic_transport._execute_via_plugin_bridge`` — every fail-closed path
  returns a schema-valid HOST_UNAVAILABLE and NEVER raises; plugin_side
  invalid/raising, peer ok=False, non-JSON line, result without
  ``semantic_result``, read-timeout with peer kill, non-dict request
  (BRIDGE-04 regression).
* ``build_coder_request`` — model_policy split, explicit provider wins,
  role_ref matrix, timeout_ms validity, worktree in trace only.
* ``classify_purpose`` / ``resolve_transport`` — full matrix.

No network, no model, no OpenCode SDK. ``subprocess.Popen`` and the plugin
side are mocked. Stdlib-only (unittest).

Run:  python -m unittest discover -s tests/coder -p "test_*.py" -v
"""
from __future__ import annotations

import io
import json
import os
import queue
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

_ROOT = Path(__file__).resolve().parents[2]
_CODE_FACTORY = _ROOT / "scripts" / "code-factory"
_CORE = _ROOT / "packages" / "opencode-harness-plugin" / "core"
if str(_CODE_FACTORY) not in sys.path:
    sys.path.insert(0, str(_CODE_FACTORY))
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

import bridge_peer as bp  # noqa: E402
import semantic_transport as st  # noqa: E402

_ENV_KEYS = ("HARNESS_SEMANTIC_ENABLED", "OPENCODE_HARNESS_ROOT", "HARNESS_TRANSPORT")


def _valid_request(**overrides):
    req = {
        "schema": st.SEMANTIC_REQUEST_SCHEMA,
        "execution_id": "autotest-req",
        "purpose": "CODE_WORK",
        "contract_schema": st.CONTRACT_SCHEMA,
        "parent_host_session_id": "autotest-host",
        "bounded_input": {"task": "t"},
        "expected_output": {},
        "model_policy": {"provider_id": "p", "model_id": "m"},
        "permission_profile": "code-worker-write",
        "timeout_ms": 60000,
        "trace": {"worktree": "w"},
    }
    req.update(overrides)
    return req


def _completed(execution_id="autotest-req"):
    return {
        "schema": st.SEMANTIC_RESULT_SCHEMA,
        "execution_id": execution_id,
        "runtime_status": "COMPLETED",
        "host_session_id": "autotest-session",
        "provider_id": "p",
        "model_id": "m",
        "structured_output": {"text": "ok"},
        "raw_output_ref": None,
        "usage": {},
        "timing": {},
        "host_error": None,
        "host_features_fingerprint": None,
    }


class EnvIsolationMixin:
    """Snapshot/restore the harness env keys for every test."""

    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in _ENV_KEYS}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# --- Fakes for _execute_via_plugin_bridge (mock subprocess.Popen) -----------


class _FakeStdin:
    def __init__(self) -> None:
        self.written: list[str] = []

    def write(self, s: str) -> None:
        self.written.append(s)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        pass


class _FakeStdout:
    """Line producer with a req_id-aware callable response mode.

    ``responses`` items are either raw strings (JSON lines) or callables
    ``callable(req_id) -> str``. ``spin`` mode keeps returning blank lines
    (JSONDecodeError -> transport loop spins until ITS deadline -> TimeoutError),
    which models a silent peer that never answers.
    """

    def __init__(self, responses, stdin: _FakeStdin, spin: bool = False) -> None:
        self._responses = list(responses)
        self._stdin = stdin
        self._idx = 0
        self._spin = spin

    def _req_id(self) -> str:
        for chunk in self._stdin.written:
            for line in chunk.splitlines():
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if isinstance(obj, dict) and obj.get("id"):
                    return obj["id"]
        return "req-unknown"

    def readline(self) -> str:
        if self._spin:
            time.sleep(0.001)
            return "\n"
        if self._idx < len(self._responses):
            item = self._responses[self._idx]
            self._idx += 1
            if callable(item):
                item = item(self._req_id())
            return item + "\n"
        time.sleep(0.005)
        return ""

    def close(self) -> None:
        pass


class _FakeStderr:
    def __iter__(self):
        return iter(())

    def close(self) -> None:
        pass


class _FakePeerProc:
    def __init__(self, responses=(), spin: bool = False) -> None:
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(responses, self.stdin, spin=spin)
        self.stderr = _FakeStderr()
        self.returncode = None
        self.killed = False
        self.waited = False

    def poll(self):
        return self.returncode

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout=None) -> None:
        self.waited = True
        return self.returncode


def _reverse_line(request=...):
    """Producer for the peer's ``semantic.execute`` reverse request line."""
    if request is ...:
        request = _valid_request()

    def _produce(_req_id: str) -> str:
        return json.dumps(
            {"id": "rev-1", "method": "semantic.execute", "params": {"request": request}}
        )

    return _produce


def _peer_ok_false(code="HANDLER_ERROR", message="boom"):
    def _produce(req_id: str) -> str:
        return json.dumps({"id": req_id, "ok": False, "error": {"code": code, "message": message}})

    return _produce


def _peer_ok_true(result):
    def _produce(req_id: str) -> str:
        return json.dumps({"id": req_id, "ok": True, "result": result})

    return _produce


# --- 1. bridge_peer._semantic_execute ---------------------------------------


class SemanticExecuteTests(unittest.TestCase):
    def _make_server(self) -> bp.BridgeServer:
        server = bp.BridgeServer(_ROOT)
        server._pending_reverse = {}
        server._inbox = queue.Queue()
        server.reverse_request = server._send_reverse
        server._shutdown_requested = False
        return server

    def test_semantic_execute_missing_request_raises_valueerror(self) -> None:
        server = self._make_server()
        with self.assertRaises(ValueError):
            server._semantic_execute({})

    def test_semantic_execute_request_none_raises_valueerror(self) -> None:
        server = self._make_server()
        with self.assertRaises(ValueError):
            server._semantic_execute({"request": None})

    def test_semantic_execute_reverse_not_configured_raises_runtimeerror(self) -> None:
        # A fresh BridgeServer has reverse_request=None until serve() runs.
        server = bp.BridgeServer(_ROOT)
        with self.assertRaises(RuntimeError):
            server._semantic_execute({"request": _valid_request()})

    def test_semantic_execute_timeout_capped_at_120000(self) -> None:
        server = self._make_server()
        captured: dict = {}

        def _fake_send_reverse(method, params, timeout_ms=None):
            captured["timeout_ms"] = timeout_ms
            return {"tool_result": _completed()}

        server._send_reverse = _fake_send_reverse  # type: ignore[assignment]
        server._semantic_execute({"request": _valid_request(timeout_ms=999999)})
        self.assertEqual(captured["timeout_ms"], 120000)
        # Direct helper check as well (falsification of the cap constant).
        self.assertEqual(bp._request_timeout_ms({"timeout_ms": 999999}), bp._REVERSE_TIMEOUT_MS_CAP)

    def test_request_timeout_ms_invalid_values_return_none(self) -> None:
        """negative/0/bool/str are not positive ints -> None -> default 15000."""
        for bad in (0, -5, True, False, "5000", 3.5, None):
            with self.subTest(value=repr(bad)):
                self.assertIsNone(bp._request_timeout_ms({"timeout_ms": bad}))
        self.assertIsNone(bp._request_timeout_ms({}))
        self.assertIsNone(bp._request_timeout_ms("nope"))

    def test_semantic_execute_tool_result_wrapper_extracted(self) -> None:
        server = self._make_server()

        def _fake_send_reverse(method, params, timeout_ms=None):
            return {"tool_result": _completed()}

        server._send_reverse = _fake_send_reverse  # type: ignore[assignment]
        out = server._semantic_execute({"request": _valid_request()})
        self.assertEqual(out, {"semantic_result": _completed()})
        self.assertEqual(out["semantic_result"]["runtime_status"], "COMPLETED")

    def test_semantic_execute_raw_result_no_wrapper(self) -> None:
        server = self._make_server()

        def _fake_send_reverse(method, params, timeout_ms=None):
            return _completed()  # raw result, no tool_result wrapper

        server._send_reverse = _fake_send_reverse  # type: ignore[assignment]
        out = server._semantic_execute({"request": _valid_request()})
        self.assertEqual(out, {"semantic_result": _completed()})


# --- 2. bridge_peer._send_reverse / _await_reverse ---------------------------


class SendReverseAwaitTests(unittest.TestCase):
    def _make_server(self) -> bp.BridgeServer:
        server = bp.BridgeServer(_ROOT)
        server._pending_reverse = {}
        server._inbox = queue.Queue()
        server.reverse_request = server._send_reverse
        server._shutdown_requested = False
        return server

    def test_send_reverse_timeout_raises_timeouterror(self) -> None:
        server = self._make_server()
        server._write = lambda obj: None  # never resolves -> await times out
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            server._send_reverse("semantic.execute", {"request": _valid_request()}, timeout_ms=100)
        self.assertLess(time.monotonic() - started, 5.0)

    def test_send_reverse_ok_false_raises_runtimeerror_with_code(self) -> None:
        server = self._make_server()

        def _write(obj):
            server._resolve_reverse(
                {"id": obj["id"], "ok": False, "error": {"code": "HANDLER_ERROR", "message": "boom"}}
            )

        server._write = _write  # type: ignore[assignment]
        with self.assertRaises(RuntimeError) as ctx:
            server._send_reverse("semantic.execute", {"request": _valid_request()}, timeout_ms=2000)
        self.assertIn("HANDLER_ERROR", str(ctx.exception))

    def test_send_reverse_ok_true_returns_result(self) -> None:
        server = self._make_server()

        def _write(obj):
            server._resolve_reverse({"id": obj["id"], "ok": True, "result": {"x": 1}})

        server._write = _write  # type: ignore[assignment]
        out = server._send_reverse("semantic.execute", {"request": _valid_request()}, timeout_ms=2000)
        self.assertEqual(out, {"x": 1})

    def test_send_reverse_none_timeout_uses_default_15000(self) -> None:
        server = self._make_server()
        captured: dict = {}

        def _fake_await(rid, timeout_ms):
            captured["timeout_ms"] = timeout_ms
            return {"ok": True}

        server._await_reverse = _fake_await  # type: ignore[assignment]
        server._write = lambda obj: None
        server._send_reverse("semantic.execute", {"request": _valid_request()}, timeout_ms=None)
        self.assertEqual(captured["timeout_ms"], bp._REVERSE_TIMEOUT_MS_DEFAULT)

    def test_await_reverse_timeout_when_unresolved(self) -> None:
        server = self._make_server()
        server._pending_reverse["rid-solo"] = {"resolved": False, "result": None, "error": None}
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            server._await_reverse("rid-solo", timeout_ms=100)
        self.assertLess(time.monotonic() - started, 5.0)

    def test_await_reverse_error_raises_runtimeerror(self) -> None:
        server = self._make_server()
        server._pending_reverse["rid-err"] = {
            "resolved": True, "result": None, "error": "PLUGIN_SIDE_UNAVAILABLE: no plugin-side consumer wired",
        }
        with self.assertRaises(RuntimeError) as ctx:
            server._await_reverse("rid-err", timeout_ms=2000)
        self.assertIn("PLUGIN_SIDE_UNAVAILABLE", str(ctx.exception))


# --- 3. bridge_peer serve-loop: missing request -> HANDLER_ERROR -------------


class ServeLoopHandlerErrorTests(unittest.TestCase):
    def test_serve_loop_wraps_missing_request_as_handler_error(self) -> None:
        server = bp.BridgeServer(_ROOT)
        lines = [
            json.dumps({"id": "s1", "method": "semantic.execute", "params": {}}),
            json.dumps({"id": "s2", "method": "bridge.shutdown", "params": {}}),
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
        parsed = {
            m["id"]: m for m in (json.loads(ln) for ln in fake_stdout.getvalue().splitlines() if ln.strip())
        }
        self.assertIn("s1", parsed)
        self.assertFalse(parsed["s1"]["ok"])
        self.assertEqual(parsed["s1"]["error"]["code"], "HANDLER_ERROR")
        self.assertIn("params.request", parsed["s1"]["error"]["message"])


# --- 4. semantic_transport._execute_via_plugin_bridge (mocked Popen) ---------


class PluginBridgeMockedTests(EnvIsolationMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if not peer.is_file():
            self.skipTest("plugin bridge peer file not present in this checkout")
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)

    def _run_bridge(self, responses, plugin_side=None, timeout_s=5.0, request=_valid_request()):
        proc = _FakePeerProc(responses=responses)
        with mock.patch("subprocess.Popen", return_value=proc):
            res = st._execute_via_plugin_bridge(request, timeout_s=timeout_s, plugin_side=plugin_side)
        return proc, res

    def _assert_host_unavailable(self, res) -> None:
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge failed", res["host_error"])
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)

    def test_plugin_side_invalid_result_host_unavailable(self) -> None:
        """plugin_side returns a schema-invalid result -> HOST_UNAVAILABLE, no raise."""

        def _bad_plugin(_req):
            return {"runtime_status": "COMPLETED"}  # not a SemanticExecutionResult

        proc, res = self._run_bridge(
            responses=[_reverse_line(), _peer_ok_false()], plugin_side=_bad_plugin
        )
        self._assert_host_unavailable(res)
        # The transport must have rejected the invalid result with a
        # PLUGIN_SIDE_ERROR envelope to the peer.
        written = "\n".join(proc.stdin.written)
        self.assertIn("PLUGIN_SIDE_ERROR", written)

    def test_plugin_side_raises_host_unavailable(self) -> None:
        def _boom(_req):
            raise RuntimeError("fake plugin execution failed")

        proc, res = self._run_bridge(
            responses=[_reverse_line(), _peer_ok_false()], plugin_side=_boom
        )
        self._assert_host_unavailable(res)
        written = "\n".join(proc.stdin.written)
        self.assertIn("PLUGIN_SIDE_ERROR", written)
        self.assertIn("fake plugin execution failed", written)

    def test_peer_ok_false_error_code_host_unavailable(self) -> None:
        _, res = self._run_bridge(
            responses=[_peer_ok_false(code="HOST_ERROR", message="reverse call failed")]
        )
        self._assert_host_unavailable(res)
        self.assertIn("HOST_ERROR", res["host_error"])

    def test_peer_non_json_line_host_unavailable(self) -> None:
        """A non-JSON stdout line is never misparsed; outcome is HOST_UNAVAILABLE."""
        proc, res = self._run_bridge(responses=["this is not json {", "also not json"])
        self._assert_host_unavailable(res)
        self.assertIn("closed stdout", res["host_error"])
        # No fabricated COMPLETED ever.
        self.assertNotEqual(res["runtime_status"], "COMPLETED")

    def test_peer_result_without_semantic_result_host_unavailable(self) -> None:
        """Peer result without a semantic_result key (and invalid) -> HOST_UNAVAILABLE."""
        _, res = self._run_bridge(
            responses=[_peer_ok_true({"runtime_status": "COMPLETED"})]
        )
        self._assert_host_unavailable(res)
        self.assertIn("invalid SemanticExecutionResult", res["host_error"])

    def test_peer_bare_valid_result_accepted(self) -> None:
        """A bare VALID result (no wrapper) is accepted by the else-branch."""
        proc, res = self._run_bridge(
            responses=[_reverse_line(), _peer_ok_true(_completed())],
            plugin_side=lambda _req: _completed(),
        )
        self.assertEqual(res["runtime_status"], "COMPLETED")
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)

    def test_read_timeout_peer_killed_host_unavailable(self) -> None:
        """Silent peer + small timeout_s -> TimeoutError -> HOST_UNAVAILABLE, peer killed."""
        proc = _FakePeerProc(responses=[], spin=True)
        started = time.monotonic()
        with mock.patch("subprocess.Popen", return_value=proc):
            res = st._execute_via_plugin_bridge(_valid_request(), timeout_s=0.3, plugin_side=None)
        elapsed = time.monotonic() - started
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("no response from plugin bridge", res["host_error"])
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)
        # finally-block must kill the peer process.
        self.assertTrue(proc.killed)
        self.assertLess(elapsed, 5.0)

    def test_non_dict_request_schema_valid_host_unavailable(self) -> None:
        """BRIDGE-04 regression: non-dict request never raises, schema-valid.

        A callable plugin_side is injected so the request-type guard inside
        ``_serve_reverse_request`` is reached (with plugin_side=None the
        PLUGIN_SIDE_UNAVAILABLE branch returns first): a non-dict request must
        produce a BAD_REQUEST envelope to the peer, then the fail-closed
        HOST_UNAVAILABLE result — never a raise, never a COMPLETED.
        """
        for bad in (None, "not-a-dict", ["x", 1], 42, 3.14):
            with self.subTest(bad=type(bad).__name__):
                proc = _FakePeerProc(
                    responses=[_reverse_line(request=bad), _peer_ok_false()]
                )
                with mock.patch("subprocess.Popen", return_value=proc):
                    res = st._execute_via_plugin_bridge(
                        bad, timeout_s=5, plugin_side=lambda _req: _completed()
                    )  # must not raise
                self._assert_host_unavailable(res)
                written = "\n".join(proc.stdin.written)
                self.assertIn("BAD_REQUEST", written)


# --- 5. build_coder_request --------------------------------------------------


class BuildCoderRequestTests(unittest.TestCase):
    def test_build_model_policy_split_provider_model(self) -> None:
        req = st.build_coder_request(
            execution_id="e1", purpose="CODE_WORK", bounded_input={},
            expected_output={}, worktree="w",
            model_policy={"model_id": "opencode/big-pickle"},
        )
        self.assertEqual(req["model_policy"]["provider_id"], "opencode")
        self.assertEqual(req["model_policy"]["model_id"], "big-pickle")
        ok, error = st._validate_request(req)
        self.assertTrue(ok, msg=error)

    def test_build_model_policy_split_multi_slash(self) -> None:
        """Split at the FIRST '/' only: 'a/b/c' -> provider='a', model='b/c'."""
        req = st.build_coder_request(
            execution_id="e2", purpose="CODE_WORK", bounded_input={},
            expected_output={}, worktree="w",
            model_policy={"model_id": "a/b/c"},
        )
        self.assertEqual(req["model_policy"]["provider_id"], "a")
        self.assertEqual(req["model_policy"]["model_id"], "b/c")

    def test_build_explicit_provider_id_wins(self) -> None:
        """Explicit provider_id always wins over the inferred one."""
        req = st.build_coder_request(
            execution_id="e3", purpose="CODE_WORK", bounded_input={},
            expected_output={}, worktree="w",
            model_policy={"provider_id": "my-provider", "model_id": "opencode/big-pickle"},
        )
        self.assertEqual(req["model_policy"]["provider_id"], "my-provider")
        self.assertEqual(req["model_policy"]["model_id"], "big-pickle")

    def test_build_model_id_no_slash_provider_equals_model(self) -> None:
        req = st.build_coder_request(
            execution_id="e4", purpose="CODE_WORK", bounded_input={},
            expected_output={}, worktree="w",
            model_policy={"model_id": "big-pickle"},
        )
        self.assertEqual(req["model_policy"]["provider_id"], "big-pickle")
        self.assertEqual(req["model_policy"]["model_id"], "big-pickle")

    def test_build_purpose_role_ref_matrix(self) -> None:
        expected = {
            "CODE_WORK": ("coder-worker", "code-worker-write"),
            "CODE_REVIEW": ("coder-reviewer", "code-reviewer-readonly"),
            "CODE_TEST_ANALYSIS": ("coder-tester", "code-tester-readonly"),
        }
        for purpose, (role, profile) in expected.items():
            with self.subTest(purpose=purpose):
                req = st.build_coder_request(
                    execution_id=f"e-{purpose}", purpose=purpose, bounded_input={},
                    expected_output={}, worktree="w",
                )
                self.assertEqual(req["role_ref"], role)
                self.assertEqual(req["permission_profile"], profile)
                ok, error = st._validate_request(req)
                self.assertTrue(ok, msg=error)

    def test_build_timeout_ms_preserved_and_default(self) -> None:
        req = st.build_coder_request(
            execution_id="e5", purpose="CODE_WORK", bounded_input={},
            expected_output={}, worktree="w", timeout_ms=12345,
        )
        self.assertEqual(req["timeout_ms"], 12345)
        ok, error = st._validate_request(req)
        self.assertTrue(ok, msg=error)
        req_default = st.build_coder_request(
            execution_id="e6", purpose="CODE_WORK", bounded_input={},
            expected_output={}, worktree="w",
        )
        self.assertEqual(req_default["timeout_ms"], 180000)
        ok, error = st._validate_request(req_default)
        self.assertTrue(ok, msg=error)

    def test_build_worktree_in_trace_only(self) -> None:
        """worktree has no canonical field (additionalProperties=false)."""
        req = st.build_coder_request(
            execution_id="e7", purpose="CODE_WORK", bounded_input={},
            expected_output={}, worktree="feature/z",
        )
        self.assertEqual(req["trace"], {"worktree": "feature/z"})
        self.assertNotIn("worktree", req)
        ok, error = st._validate_request(req)
        self.assertTrue(ok, msg=error)


# --- 6. classify_purpose -----------------------------------------------------


class ClassifyPurposeTests(unittest.TestCase):
    def test_classify_purpose_matrix(self) -> None:
        cases = {
            "CODE_WORK": "code-worker-write",
            "CODE_REVIEW": "code-reviewer-readonly",
            "CODE_TEST_ANALYSIS": "code-tester-readonly",
            "UNKNOWN_PURPOSE": "semantic-worker-readonly",
            "": "semantic-worker-readonly",
            None: "semantic-worker-readonly",
            "semantic-worker-readonly": "semantic-worker-readonly",
        }
        for purpose, expected in cases.items():
            with self.subTest(purpose=repr(purpose)):
                self.assertEqual(st.classify_purpose(purpose), expected)


# --- 7. resolve_transport matrix ---------------------------------------------


class ResolveTransportMatrixTests(EnvIsolationMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        self._bridge_available = peer.is_file()
        self._bridge_env = {
            "HARNESS_SEMANTIC_ENABLED": "1",
            "OPENCODE_HARNESS_ROOT": str(_ROOT),
            "HARNESS_TRANSPORT": None,
        }

    def _set(self, **env) -> None:
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        for key, value in env.items():
            if value is not None:
                os.environ[key] = value

    def test_resolve_transport_explicit_wins_over_env(self) -> None:
        for env in (self._bridge_env, {"HARNESS_TRANSPORT": "cli"}, {}):
            with self.subTest(env=env):
                self._set(**env)
                self.assertEqual(st.resolve_transport(explicit="plugin"), "plugin")
                self.assertEqual(st.resolve_transport(explicit="cli"), "cli")

    def test_resolve_transport_env_explicit_plugin_cli(self) -> None:
        self._set(HARNESS_TRANSPORT="plugin")
        self.assertEqual(st.resolve_transport(), "plugin")
        self._set(HARNESS_TRANSPORT="cli")
        self.assertEqual(st.resolve_transport(), "cli")

    def test_resolve_transport_auto_matrix(self) -> None:
        # auto + bridge conditions hold -> plugin (only when the peer file exists).
        if self._bridge_available:
            self._set(**self._bridge_env)
            self.assertEqual(st.resolve_transport(explicit="auto"), "plugin")
        # auto + clean env -> cli.
        self._set()
        self.assertEqual(st.resolve_transport(explicit="auto"), "cli")
        # auto + flag but no root -> cli (incomplete bridge conditions).
        self._set(HARNESS_SEMANTIC_ENABLED="1")
        self.assertEqual(st.resolve_transport(explicit="auto"), "cli")

    def test_resolve_transport_unknown_env_falls_back_to_auto(self) -> None:
        for bogus in ("plug-in", "CLI ", "Plugin", "  ", "1", "auto-matic"):
            with self.subTest(value=repr(bogus)):
                self._set(HARNESS_TRANSPORT=bogus)
                self.assertEqual(st.resolve_transport(), "cli")  # auto semantics, no bridge

    def test_resolve_transport_missing_env_is_auto(self) -> None:
        self._set()
        self.assertEqual(st.resolve_transport(), "cli")
        if self._bridge_available:
            self._set(**self._bridge_env)
            self.assertEqual(st.resolve_transport(), "plugin")


# --- 8. Extra transport edge paths (harder coverage) -------------------------


class PluginBridgeExtraTests(EnvIsolationMixin, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if not peer.is_file():
            self.skipTest("plugin bridge peer file not present in this checkout")
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)

    def test_peer_exits_early_host_unavailable(self) -> None:
        """Peer.poll() non-None before responding -> fail-closed HOST_UNAVAILABLE."""
        proc = _FakePeerProc(responses=[])
        proc.returncode = 1

        class _ExitFakeStdout:
            def close(self):
                pass

            def readline(self):
                return "x"  # any line; poll() is checked BEFORE the read

        proc.stdout = _ExitFakeStdout()  # type: ignore[assignment]
        with mock.patch("subprocess.Popen", return_value=proc):
            res = st._execute_via_plugin_bridge(_valid_request(), timeout_s=5)
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("exited before responding", res["host_error"])
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)
        self.assertTrue(proc.killed)

    def test_non_dict_json_line_skipped_then_fail_closed(self) -> None:
        """A JSON non-dict line (e.g. a list) is skipped, never misparsed.

        The transport must keep spinning (never treat the list as a response)
        until the peer's stdout closes -> honest HOST_UNAVAILABLE.
        """
        proc, res = self._run_bridge(responses=['[1, 2, 3]'])
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("closed stdout", res["host_error"])
        self.assertNotIn("bridge error", res["host_error"])

    def _run_bridge(self, responses, plugin_side=None, timeout_s=5.0, request=_valid_request()):
        proc = _FakePeerProc(responses=responses)
        with mock.patch("subprocess.Popen", return_value=proc):
            res = st._execute_via_plugin_bridge(request, timeout_s=timeout_s, plugin_side=plugin_side)
        return proc, res

    def test_wrong_id_line_skipped_then_fail_closed(self) -> None:
        """A response with a DIFFERENT id is never treated as our answer.

        The transport must skip the foreign-id line and keep reading until EOF
        -> HOST_UNAVAILABLE (never a fabricated COMPLETED from a foreign id).
        """
        proc = _FakePeerProc(
            responses=[lambda _rid: json.dumps({"id": "other-id", "ok": True, "result": _completed()})]
        )
        with mock.patch("subprocess.Popen", return_value=proc):
            res = st._execute_via_plugin_bridge(_valid_request(), timeout_s=0.5)
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("closed stdout", res["host_error"])

    def test_wrong_method_reverse_ignored(self) -> None:
        """A reverse request for a NON semantic.execute method is not serviced.

        The transport only services ``semantic.execute`` reverse requests;
        any other reverse line (still no ``ok``) is skipped, not misparsed.
        """

        def _other_reverse(_req_id):
            return json.dumps({"id": "rev-2", "method": "harness.ping", "params": {}})

        proc, res = self._run_bridge(
            responses=[_other_reverse, _peer_ok_false()], plugin_side=lambda _req: _completed()
        )
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        # The non-semantic reverse line must NOT have been answered on stdin.
        written = "\n".join(proc.stdin.written)
        self.assertNotIn("harness.ping", written)

    def test_plugin_side_wrapped_semantic_result_envelope(self) -> None:
        """plugin_side returning {'semantic_result': <valid>} is unwrapped.

        The transport unwraps the envelope, validates the inner result and
        writes ``{"tool_result": <semantic_result>}`` back to the peer; the
        peer then answers OUR request with ok=True -> COMPLETED.
        """
        proc, res = self._run_bridge(
            responses=[_reverse_line(), _peer_ok_true(_completed())],
            plugin_side=lambda _req: {"semantic_result": _completed()},
        )
        self.assertEqual(res["runtime_status"], "COMPLETED")
        written = "\n".join(proc.stdin.written)
        # The reverse reply must carry the tool_result envelope with ok=true.
        self.assertIn('"tool_result"', written)
        self.assertIn('"ok": true', written)

    def test_plugin_side_write_failure_swallowed(self) -> None:
        """_serve_reverse_request._write swallows BrokenPipeError/OSError/ValueError.

        The reverse request is written to a closed stdin; the transport must
        not raise — it times out and fails closed to HOST_UNAVAILABLE.
        """

        class _BrokenStdin(_FakeStdin):
            def write(self, s: str) -> None:
                raise BrokenPipeError("stdin closed")

        proc = _FakePeerProc(responses=[_reverse_line(), _peer_ok_false()])
        proc.stdin = _BrokenStdin()  # type: ignore[assignment]
        with mock.patch("subprocess.Popen", return_value=proc):
            res = st._execute_via_plugin_bridge(_valid_request(), timeout_s=5, plugin_side=lambda _req: _completed())
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)


class ResultAndSplitUnitTests(unittest.TestCase):
    def test_result_rejects_invalid_runtime_status(self) -> None:
        with self.assertRaises(ValueError):
            st._result(execution_id="e", runtime_status="NOT_A_STATUS", host_error=None)

    def test_result_non_string_fields_default_to_unknown(self) -> None:
        res = st._result(
            execution_id=None, runtime_status="FAILED", host_error=None,
            provider_id="", model_id=None,
            structured_output=[], usage=None, timing="not-dict",
        )
        self.assertEqual(res["execution_id"], "unknown")
        self.assertEqual(res["provider_id"], "unknown")
        self.assertEqual(res["model_id"], "unknown")
        self.assertEqual(res["structured_output"], {})
        self.assertEqual(res["usage"], {})
        self.assertEqual(res["timing"], {})
        self.assertIsNone(res["raw_output_ref"])
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)

    def test_validate_result_rejects_wrong_shapes(self) -> None:
        good = _completed()
        ok, _ = st._validate_result(good)
        self.assertTrue(ok)
        # Non-dict result.
        self.assertFalse(st._validate_result("nope")[0])
        self.assertFalse(st._validate_result([1])[0])
        # Missing field.
        bad1 = dict(good)
        del bad1["host_error"]
        ok, error = st._validate_result(bad1)
        self.assertFalse(ok)
        self.assertIn("missing required field", error)
        # Wrong schema const.
        bad2 = dict(good, schema="wrong/1.0")
        self.assertFalse(st._validate_result(bad2)[0])
        # Non-string provider_id.
        bad3 = dict(good, provider_id=None)
        self.assertFalse(st._validate_result(bad3)[0])
        # Unknown extra field.
        bad4 = dict(good, evil_field=1)
        self.assertFalse(st._validate_result(bad4)[0])
        # Non-dict structured_output.
        bad5 = dict(good, structured_output=[])
        self.assertFalse(st._validate_result(bad5)[0])
        # Invalid runtime_status enum.
        bad6 = dict(good, runtime_status="NOPE")
        self.assertFalse(st._validate_result(bad6)[0])
        # Non-string host_error (should be str or null).
        bad7 = dict(good, host_error=123)
        self.assertFalse(st._validate_result(bad7)[0])

    def test_validate_request_rejects_bad_shapes(self) -> None:
        ok, _ = st._validate_request(_valid_request())
        self.assertTrue(ok)
        # Non-dict.
        self.assertFalse(st._validate_request("nope")[0])
        self.assertFalse(st._validate_request(["x"])[0])
        # Wrong schema.
        self.assertFalse(st._validate_request({"schema": "wrong", "execution_id": "x"})[0])
        # Unknown purpose.
        bad = dict(_valid_request(), purpose="CODE_WHATEVER")
        self.assertFalse(st._validate_request(bad)[0])
        # Empty execution_id.
        bad = dict(_valid_request(), execution_id="")
        self.assertFalse(st._validate_request(bad)[0])
        # role_ref non-string.
        bad = dict(_valid_request(), role_ref=5)
        self.assertFalse(st._validate_request(bad)[0])
        # model_policy non-object.
        bad = dict(_valid_request(), model_policy="strict")
        self.assertFalse(st._validate_request(bad)[0])

    def test_split_provider_model_edges(self) -> None:
        self.assertEqual(st._split_provider_model("opencode/big-pickle"), ("opencode", "big-pickle"))
        self.assertEqual(st._split_provider_model("big-pickle"), ("big-pickle", "big-pickle"))
        self.assertEqual(st._split_provider_model("/model"), (None, "/model"))
        self.assertEqual(st._split_provider_model("a/b/c"), ("a", "b/c"))
        self.assertEqual(st._split_provider_model(42), (None, 42))
        self.assertEqual(st._split_provider_model(""), ("", ""))


class PeerResolutionUnitTests(unittest.TestCase):
    """Direct unit tests for bridge_peer._resolve_reverse and queue-empty shutdown."""

    def _make_server(self) -> bp.BridgeServer:
        server = bp.BridgeServer(_ROOT)
        server._pending_reverse = {}
        server._inbox = queue.Queue()
        server.reverse_request = server._send_reverse
        server._shutdown_requested = False
        return server

    def test_resolve_reverse_false_for_non_bool_ok(self) -> None:
        server = self._make_server()
        self.assertFalse(server._resolve_reverse({"id": "r1", "ok": "yes"}))
        self.assertFalse(server._resolve_reverse({"ok": True}))  # no id
        self.assertFalse(server._resolve_reverse({"id": "ghost", "ok": True}))  # unknown rid

    def test_resolve_reverse_error_without_code_uses_default(self) -> None:
        server = self._make_server()
        server._pending_reverse["r2"] = {"resolved": False, "result": None, "error": None}
        server._resolve_reverse({"id": "r2", "ok": False})  # error key absent
        self.assertTrue(server._pending_reverse["r2"]["resolved"])
        with self.assertRaises(RuntimeError) as ctx:
            server._await_reverse("r2", timeout_ms=1000)
        self.assertIn("ERROR:", str(ctx.exception))

    def test_serve_loop_exits_on_queue_empty_when_shutdown_requested(self) -> None:
        """serve() polls queue.Empty; a pre-set shutdown flag exits the loop."""
        server = bp.BridgeServer(_ROOT)
        real_stdin, real_stdout = sys.stdin, sys.stdout
        sys.stdin, sys.stdout = io.StringIO(""), io.StringIO()
        try:
            t = threading.Thread(target=server.serve, daemon=True)
            t.start()
            # The reader thread blocks on EOF iteration; set the shutdown flag so
            # the queue.Empty branch exits the loop.
            time.sleep(0.1)
            server._shutdown_requested = True
            t.join(timeout=10)
        finally:
            sys.stdin, sys.stdout = real_stdin, real_stdout
        self.assertFalse(t.is_alive(), "serve() must exit via the queue.Empty branch")


class PluginBridgeFinallyFailureTests(EnvIsolationMixin, unittest.TestCase):
    """The finally-block in _execute_via_plugin_bridge must survive failures."""

    def setUp(self) -> None:
        super().setUp()
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if not peer.is_file():
            self.skipTest("plugin bridge peer file not present in this checkout")
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)

    def test_finally_kill_wait_close_failures_are_swallowed(self) -> None:
        """kill()/wait()/close() raising must not mask the HOST_UNAVAILABLE result."""

        class _FragileProc(_FakePeerProc):
            def kill(self):
                raise OSError("kill denied")

            def wait(self, timeout=None):
                raise OSError("wait denied")

            def close(self):  # pragma: no cover - may not be called
                raise OSError("close denied")

        class _FragileStdin(_FakeStdin):
            def close(self):
                raise OSError("stdin close denied")

        proc = _FragileProc(responses=[])
        proc.stdin = _FragileStdin()  # type: ignore[assignment]

        class _FragileStdout:
            def close(self):
                raise OSError("stdout close denied")

            def readline(self):
                return ""

        proc.stdout = _FragileStdout()  # type: ignore[assignment]

        class _FragileStderr:
            def __iter__(self):
                return iter(())

            def close(self):
                raise OSError("stderr close denied")

        proc.stderr = _FragileStderr()  # type: ignore[assignment]

        with mock.patch("subprocess.Popen", return_value=proc):
            res = st._execute_via_plugin_bridge(_valid_request(), timeout_s=5)
        # The finally-block swallowed every failure; the fail-closed result is intact.
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        ok, error = st._validate_result(res)
        self.assertTrue(ok, msg=error)


# --- bridge_peer extra branches ---------------------------------------------


class BridgePeerExtraBranchesTests(unittest.TestCase):
    def _make_server(self) -> bp.BridgeServer:
        server = bp.BridgeServer(_ROOT)
        server._pending_reverse = {}
        server._inbox = queue.Queue()
        server.reverse_request = server._send_reverse
        server._shutdown_requested = False
        return server

    def test_harness_root_env_branch(self) -> None:
        saved = os.environ.get("OPENCODE_HARNESS_ROOT")
        os.environ["OPENCODE_HARNESS_ROOT"] = str(Path("C:/harness-root-xyz"))
        try:
            self.assertEqual(bp._harness_root(), Path("C:/harness-root-xyz"))
        finally:
            if saved is None:
                os.environ.pop("OPENCODE_HARNESS_ROOT", None)
            else:
                os.environ["OPENCODE_HARNESS_ROOT"] = saved

    def test_health_config_missing(self) -> None:
        import tempfile

        tmp = Path(tempfile.mkdtemp(prefix="bp_health_"))
        self.addCleanup(__import__("shutil").rmtree, tmp, ignore_errors=True)
        server = bp.BridgeServer(tmp)
        health = server._health({})
        self.assertFalse(health["ok"])
        self.assertEqual(health["detail"], "config-missing")

    def test_status_reports_policy_files(self) -> None:
        server = self._make_server()
        status = server._status({})
        self.assertTrue(status["ok"])
        self.assertIn("runtime_policy_present", status)
        self.assertIn("capability_policy_present", status)

    def test_run_core_error_envelope(self) -> None:
        """_run catches any exception into {'ok': False, error.code: CORE_ERROR}."""
        server = self._make_server()

        def _boom(params):
            raise RuntimeError("resolve exploded")

        server._run_deterministic = _boom  # type: ignore[assignment]
        out = server._run({"task": "t"})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "CORE_ERROR")
        self.assertIn("resolve exploded", out["error"]["message"])

    def test_run_deterministic_ok(self) -> None:
        server = self._make_server()
        out = server._run({"task": "implement a function", "route": "code-implementation", "profile": "strict"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["result"]["route_id"], "code-implementation")
        self.assertEqual(out["result"]["profile"], "strict")

    def test_reverse_echo_test_not_configured_raises(self) -> None:
        server = bp.BridgeServer(_ROOT)  # fresh: reverse_request is None
        with self.assertRaises(RuntimeError):
            server._reverse_echo_test({"value": 1})

    def test_reader_thread_skips_bad_lines(self) -> None:
        """_reader_thread ignores empty, non-JSON and non-message lines."""
        import queue as _queue

        server = bp.BridgeServer(_ROOT)
        server._pending_reverse = {}
        inbox: _queue.Queue = _queue.Queue()
        server._inbox = inbox
        lines = [
            "",
            "   ",
            "not json {",
            json.dumps({"id": "r1", "ok": True, "result": "rev-ok"}),  # reverse response
            json.dumps({"id": "m1", "method": "bridge.health", "params": {}}),  # normal msg
        ]
        # Pre-register the reverse id so _resolve_reverse consumes it.
        server._pending_reverse["r1"] = {"resolved": False, "result": None, "error": None}
        real_stdin, real_stdout = sys.stdin, sys.stdout
        sys.stdin, sys.stdout = io.StringIO("\n".join(lines) + "\n"), io.StringIO()
        try:
            server._reader_thread()
        finally:
            sys.stdin, sys.stdout = real_stdin, real_stdout
        # The reverse response was resolved, the normal message queued.
        self.assertTrue(server._pending_reverse["r1"]["resolved"])
        self.assertEqual(server._pending_reverse["r1"]["result"], "rev-ok")
        self.assertEqual(inbox.qsize(), 1)
        self.assertEqual(inbox.get_nowait()["method"], "bridge.health")

    def test_request_timeout_ms_bool_is_not_int(self) -> None:
        """bool must be treated as invalid (bool is an int subclass)."""
        self.assertIsNone(bp._request_timeout_ms({"timeout_ms": True}))
        self.assertIsNone(bp._request_timeout_ms({"timeout_ms": False}))
        self.assertEqual(bp._request_timeout_ms({"timeout_ms": 1}), 1)
        self.assertEqual(bp._request_timeout_ms({"timeout_ms": 120000}), 120000)


if __name__ == "__main__":
    unittest.main(verbosity=2)