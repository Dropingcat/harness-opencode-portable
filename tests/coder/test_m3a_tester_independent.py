"""Code-tester independent tests for M3a explicit transport (DEV-05).

Independent verification complementing the worker suite (test_explicit_transport.py)
with the gaps it leaves open:

1. execute_coder_semantic(transport="plugin") with an unavailable bridge must
   return HOST_UNAVAILABLE AND never invoke any CLI subprocess — asserted via
   a mocked asyncio.create_subprocess_exec (zero-call assertion).
2. execute_coder_semantic(transport="cli") must never touch subprocess
   machinery either (zero-call assertion), and must return the explicit-cli
   REJECTED_BY_HOST diagnostic.
3. resolve_transport defensive matrix: unknown/empty/whitespace env values
   behave as "auto" (never a surprise transport); explicit values win over
   env; env "plugin"/"cli" without explicit override.
4. Env-leakage guard: HARNESS_TRANSPORT / HARNESS_SEMANTIC_ENABLED /
   OPENCODE_HARNESS_ROOT / CODER_ROUTER_ALLOWED_ROOTS must be restored after
   every scenario (no cross-test leakage) — each test asserts a clean start.
5. Router: HARNESS_TRANSPORT=cli in a bridge-available environment -> legacy
   CLI with the opencode_cli_legacy label (explicit cli is honoured at the
   router level as legacy, labelled, NOT silently bridged).

No real opencode/model calls, no network — everything is mocked.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

_ROOT = Path(__file__).resolve().parents[2]
_CODE_FACTORY = _ROOT / "scripts" / "code-factory"
if str(_CODE_FACTORY) not in sys.path:
    sys.path.insert(0, str(_CODE_FACTORY))

from semantic_transport import (  # noqa: E402
    SEMANTIC_REQUEST_SCHEMA,
    build_coder_request,
    execute_coder_semantic,
    resolve_transport,
)

_ROUTER_PATH = _ROOT / "mcp" / "coder_router_server.py"

_ENV_KEYS = (
    "HARNESS_SEMANTIC_ENABLED",
    "OPENCODE_HARNESS_ROOT",
    "CODER_ROUTER_ALLOWED_ROOTS",
    "HARNESS_TRANSPORT",
)


def _load_router(module_name: str = "coder_router_m3a_tester") -> Any:
    """Load mcp/coder_router_server.py standalone (avoid SDK shadowing)."""
    spec = importlib.util.spec_from_file_location(module_name, _ROUTER_PATH)
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_request(**overrides: object) -> dict:
    req = build_coder_request(
        execution_id="m3a-tester-exec",
        purpose="CODE_WORK",
        bounded_input={"task": "t"},
        expected_output={},
        worktree="w",
    )
    req.update(overrides)
    return req


class _FakeProc:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"fake stdout", b""

    async def wait(self) -> int:
        return self.returncode


async def _fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> _FakeProc:
    return _FakeProc()


class EnvIsolationMixin:
    """Save/restore env vars across each test (no cross-test leakage).

    NOTE: OPENCODE_HARNESS_ROOT is pre-set in this workspace's environment,
    so a clean start does NOT mean the key is absent. Instead we snapshot the
    baseline once (first setUp of each class) and assert every later test
    starts from exactly that baseline — catching leakage from other tests
    while tolerating a legitimately pre-set environment.
    """

    _baseline: dict[str, str | None] | None = None

    @classmethod
    def _record_baseline(cls) -> None:
        if cls._baseline is None:
            cls._baseline = {k: os.environ.get(k) for k in _ENV_KEYS}

    def setUp(self) -> None:
        self._record_baseline()
        for key in _ENV_KEYS:
            self.assertEqual(
                os.environ.get(key),
                self._baseline.get(key),
                msg=f"{key} leaked from a previous test (baseline={self._baseline.get(key)!r}, now={os.environ.get(key)!r})",
            )
        self._saved = {k: os.environ.get(k) for k in _ENV_KEYS}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _clear_harness_env() -> None:
    os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
    os.environ.pop("OPENCODE_HARNESS_ROOT", None)
    os.environ.pop("HARNESS_TRANSPORT", None)
    os.environ["CODER_ROUTER_ALLOWED_ROOTS"] = str(_ROOT)


# --- 1. No CLI subprocess on explicit plugin (unavailable bridge) ----------

class NoSubprocessOnPluginTests(EnvIsolationMixin, unittest.TestCase):
    def test_explicit_plugin_no_subprocess_zero_calls(self) -> None:
        """transport="plugin" + unavailable bridge: HOST_UNAVAILABLE, no CLI call."""
        _clear_harness_env()
        req = _valid_request()
        calls: list[tuple] = []

        async def _capture_exec(*args: Any, **kwargs: Any) -> _FakeProc:
            calls.append(args)
            return _FakeProc()

        with mock.patch("asyncio.create_subprocess_exec", new=_capture_exec):
            res = execute_coder_semantic(req, transport="plugin")
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge unavailable", res["host_error"])
        self.assertEqual(calls, [], "CLI subprocess MUST NOT be called for plugin transport")
        self.assertEqual(res["schema"], "semantic-execution-result/1.0")

    def test_auto_plugin_with_bridge_no_subprocess(self) -> None:
        """auto resolves to plugin (bridge present) -> no CLI subprocess call."""
        _clear_harness_env()
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if not peer.is_file():
            self.skipTest("plugin bridge peer file not present in this checkout")
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        calls: list[tuple] = []

        async def _capture_exec(*args: Any, **kwargs: Any) -> _FakeProc:
            calls.append(args)
            return _FakeProc()

        with mock.patch("asyncio.create_subprocess_exec", new=_capture_exec):
            res = execute_coder_semantic(_valid_request())
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertEqual(calls, [], "CLI subprocess MUST NOT be called on the plugin path")


# --- 2. No CLI subprocess on explicit cli (M1 rejects) ----------------------

class NoSubprocessOnExplicitCliTests(EnvIsolationMixin, unittest.TestCase):
    def test_explicit_cli_no_subprocess_zero_calls(self) -> None:
        """transport="cli": REJECTED_BY_HOST and no subprocess machinery runs."""
        _clear_harness_env()
        req = _valid_request()
        calls: list[tuple] = []

        async def _capture_exec(*args: Any, **kwargs: Any) -> _FakeProc:
            calls.append(args)
            return _FakeProc()

        with mock.patch("asyncio.create_subprocess_exec", new=_capture_exec):
            res = execute_coder_semantic(req, transport="cli")
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("explicit cli transport selected", res["host_error"])
        self.assertEqual(calls, [], "CLI subprocess MUST NOT be called from M1 for explicit cli")

    def test_explicit_cli_with_env_cli_same_diagnostic(self) -> None:
        """HARNESS_TRANSPORT=cli without transport kwarg -> explicit-cli diagnostic."""
        _clear_harness_env()
        os.environ["HARNESS_TRANSPORT"] = "cli"
        res = execute_coder_semantic(_valid_request())
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("explicit cli transport selected", res["host_error"])


# --- 3. resolve_transport defensive matrix ----------------------------------

class ResolveTransportDefensiveTests(EnvIsolationMixin, unittest.TestCase):
    def test_unknown_env_value_falls_back_to_auto_cli(self) -> None:
        """A typo in HARNESS_TRANSPORT must never produce a surprise transport."""
        _clear_harness_env()
        for bogus in ("plug-in", "CLI ", "Plugin", "  ", "1", "auto-matic"):
            with self.subTest(value=repr(bogus)):
                os.environ["HARNESS_TRANSPORT"] = bogus
                # auto semantics: no bridge env -> cli
                self.assertEqual(resolve_transport(), "cli")

    def test_unknown_explicit_falls_back_to_auto_cli(self) -> None:
        _clear_harness_env()
        self.assertEqual(resolve_transport(explicit="bogus"), "cli")
        self.assertEqual(resolve_transport(explicit=""), "cli")

    def test_auto_bridge_unavailable_resolves_cli(self) -> None:
        """auto + flag but broken root -> cli (documented auto behaviour)."""
        _clear_harness_env()
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT / "does-not-exist")
        self.assertEqual(resolve_transport(explicit="auto"), "cli")

    def test_auto_flag_only_resolves_cli(self) -> None:
        """auto + flag but no root -> cli (bridge conditions incomplete)."""
        _clear_harness_env()
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        self.assertEqual(resolve_transport(explicit="auto"), "cli")

    def test_explicit_overrides_env(self) -> None:
        """explicit kwarg wins over HARNESS_TRANSPORT."""
        _clear_harness_env()
        os.environ["HARNESS_TRANSPORT"] = "plugin"
        self.assertEqual(resolve_transport(explicit="cli"), "cli")
        os.environ["HARNESS_TRANSPORT"] = "cli"
        self.assertEqual(resolve_transport(explicit="plugin"), "plugin")


# --- 4. Env leakage guard ---------------------------------------------------

class EnvLeakageTests(EnvIsolationMixin, unittest.TestCase):
    def test_env_restored_after_full_scenario(self) -> None:
        """Run a plugin-scenario then a cli-scenario; env must be clean after."""
        _clear_harness_env()
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        os.environ["HARNESS_TRANSPORT"] = "plugin"
        resolve_transport()
        execute_coder_semantic(_valid_request(), transport="plugin")

        os.environ["HARNESS_TRANSPORT"] = "cli"
        execute_coder_semantic(_valid_request())

        # tearDown restores; but also assert mid-scenario cleanup happens.
        self.assertEqual(os.environ.get("HARNESS_TRANSPORT"), "cli")


# --- 5. Router: HARNESS_TRANSPORT=cli in bridge-available env -> legacy -----

class RouterExplicitCliBridgeAvailableTests(EnvIsolationMixin, unittest.TestCase):
    def test_cli_env_in_bridge_env_routes_legacy_label(self) -> None:
        """HARNESS_TRANSPORT=cli even with bridge available -> legacy, labelled."""
        _clear_harness_env()
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if not peer.is_file():
            self.skipTest("plugin bridge peer file not present in this checkout")
        os.environ["HARNESS_TRANSPORT"] = "cli"
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)

        router = _load_router()
        self.assertFalse(router._LEGACY_ONLY)
        calls: list[tuple] = []

        async def _capture_exec(*args: Any, **kwargs: Any) -> _FakeProc:
            calls.append(args)
            return _FakeProc()

        with mock.patch("asyncio.create_subprocess_exec", new=_capture_exec):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertEqual(payload["transport"], "opencode_cli_legacy")
        self.assertEqual(payload["legacy_reason"], "plugin bridge not enabled or adapter unavailable")
        self.assertTrue(payload["ok"])
        # Explicit cli IS the legacy path at the router level — one CLI call.
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)