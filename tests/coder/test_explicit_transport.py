"""Unit tests for M3a explicit transport selection (DEV-05).

Covers `scripts/code-factory/semantic_transport.py` (resolve_transport,
execute_coder_semantic transport=, build_coder_request model-id split) and
`mcp/coder_router_server.py` (no silent CLI fallback when the plugin
transport is explicitly selected; HARNESS_TRANSPORT=cli -> legacy with the
opencode_cli_legacy label).

Fail-closed rules under test:
  * explicit "cli"  -> REJECTED_BY_HOST (never launched from M1);
  * explicit "plugin" + unavailable bridge -> HOST_UNAVAILABLE / router
    error, the legacy CLI subprocess is NEVER called;
  * auto -> plugin iff bridge conditions hold, else cli;
  * HARNESS_TRANSPORT=plugin + M1 ImportError -> error, 0 subprocess calls.

No real opencode/model calls — everything is mocked.

Run:  python -m unittest discover -s tests/coder -p "test_*.py" -v
"""
from __future__ import annotations

import asyncio
import builtins
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


def _load_router(module_name: str = "coder_router_server_explicit") -> Any:
    """Load mcp/coder_router_server.py standalone (avoid SDK shadowing)."""
    spec = importlib.util.spec_from_file_location(module_name, _ROUTER_PATH)
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clean_env() -> None:
    os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
    os.environ.pop("OPENCODE_HARNESS_ROOT", None)
    os.environ.pop("HARNESS_TRANSPORT", None)
    os.environ["CODER_ROUTER_ALLOWED_ROOTS"] = str(_ROOT)


def _valid_request(**overrides: object) -> dict:
    req = build_coder_request(
        execution_id="m3a-exec",
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
    """Save/restore env vars across each test (no cross-test leakage)."""

    _KEYS = (
        "HARNESS_SEMANTIC_ENABLED",
        "OPENCODE_HARNESS_ROOT",
        "CODER_ROUTER_ALLOWED_ROOTS",
        "HARNESS_TRANSPORT",
    )

    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in self._KEYS}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# --- 1. resolve_transport --------------------------------------------------

class ResolveTransportTests(EnvIsolationMixin, unittest.TestCase):
    def test_resolve_transport_explicit_plugin(self) -> None:
        self.assertEqual(resolve_transport(explicit="plugin"), "plugin")

    def test_resolve_transport_explicit_cli(self) -> None:
        self.assertEqual(resolve_transport(explicit="cli"), "cli")

    def test_resolve_transport_auto_no_env(self) -> None:
        _clean_env()
        self.assertEqual(resolve_transport(explicit="auto"), "cli")

    def test_resolve_transport_auto_bridge_available(self) -> None:
        """auto with HARNESS_SEMANTIC_ENABLED=1 + root -> plugin."""
        _clean_env()
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if not peer.is_file():
            self.skipTest("plugin bridge peer file not present in this checkout")
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        self.assertEqual(resolve_transport(explicit="auto"), "plugin")

    def test_resolve_transport_env_var_plugin(self) -> None:
        _clean_env()
        os.environ["HARNESS_TRANSPORT"] = "plugin"
        self.assertEqual(resolve_transport(), "plugin")

    def test_resolve_transport_env_var_cli(self) -> None:
        _clean_env()
        os.environ["HARNESS_TRANSPORT"] = "cli"
        self.assertEqual(resolve_transport(), "cli")


# --- 2. execute_coder_semantic(transport="cli") ----------------------------

class ExecuteExplicitCliTests(EnvIsolationMixin, unittest.TestCase):
    def test_execute_explicit_cli_rejected_by_host(self) -> None:
        """transport="cli" -> REJECTED_BY_HOST with the explicit-cli error."""
        _clean_env()
        req = _valid_request()
        res = execute_coder_semantic(req, transport="cli")
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("explicit cli transport selected", res["host_error"])
        # Not implemented in M1: no model launch, no subprocess from M1.
        self.assertIn("not implemented in M1", res["host_error"])
        self.assertEqual(res["schema"], "semantic-execution-result/1.0")

    def test_execute_explicit_cli_never_raises(self) -> None:
        """transport="cli" must never raise for a valid request."""
        _clean_env()
        req = _valid_request()
        res = execute_coder_semantic(req, transport="cli")  # must not raise
        self.assertIsInstance(res, dict)

    def test_execute_explicit_cli_no_subprocess_import(self) -> None:
        """M1 must not spawn a process: verify no subprocess machinery is used.

        M1 never imports subprocess/launchers; the closest observable proof is
        that transport="cli" returns before any exec path. We assert the result
        is the canonical rejection, which is the only allowed outcome.
        """
        _clean_env()
        res = execute_coder_semantic(_valid_request(), transport="cli")
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("explicit cli transport selected", res["host_error"])


# --- 3. execute_coder_semantic(transport="plugin") unavailable bridge -------

class ExecuteExplicitPluginTests(EnvIsolationMixin, unittest.TestCase):
    def test_execute_explicit_plugin_unavailable_bridge(self) -> None:
        """transport="plugin" + no bridge -> HOST_UNAVAILABLE (fail-closed)."""
        _clean_env()
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        req = _valid_request()
        res = execute_coder_semantic(req, transport="plugin")
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge unavailable", res["host_error"])
        # Fail-closed: no CLI fallback, no silent switch to legacy.
        self.assertNotIn("REJECTED_BY_HOST", res["runtime_status"])
        self.assertEqual(res["schema"], "semantic-execution-result/1.0")

    def test_execute_explicit_plugin_available_bridge(self) -> None:
        """transport="plugin" + bridge present -> HOST_UNAVAILABLE (not wired)."""
        _clean_env()
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if not peer.is_file():
            self.skipTest("plugin bridge peer file not present in this checkout")
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        res = execute_coder_semantic(_valid_request(), transport="plugin")
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge failed", res["host_error"])


# --- 4. build_coder_request model-id split ----------------------------------

class BuildCoderRequestSplitTests(unittest.TestCase):
    def test_model_id_with_provider_slash_split(self) -> None:
        """'opencode/big-pickle' -> provider_id='opencode', model_id='big-pickle'."""
        req = build_coder_request(
            execution_id="e-split",
            purpose="CODE_WORK",
            bounded_input={},
            expected_output={},
            worktree="w",
            model_policy={"model_id": "opencode/big-pickle"},
        )
        self.assertEqual(req["model_policy"]["provider_id"], "opencode")
        self.assertEqual(req["model_policy"]["model_id"], "big-pickle")

    def test_model_id_without_slash_provider_equals_model(self) -> None:
        """'big-pickle' (no '/') -> provider_id='big-pickle', model_id='big-pickle'."""
        req = build_coder_request(
            execution_id="e-noslash",
            purpose="CODE_WORK",
            bounded_input={},
            expected_output={},
            worktree="w",
            model_policy={"model_id": "big-pickle"},
        )
        self.assertEqual(req["model_policy"]["provider_id"], "big-pickle")
        self.assertEqual(req["model_policy"]["model_id"], "big-pickle")

    def test_explicit_provider_id_wins_over_split(self) -> None:
        """Explicit provider_id takes precedence over the inferred one."""
        req = build_coder_request(
            execution_id="e-explicit",
            purpose="CODE_WORK",
            bounded_input={},
            expected_output={},
            worktree="w",
            model_policy={"provider_id": "my-provider", "model_id": "opencode/big-pickle"},
        )
        self.assertEqual(req["model_policy"]["provider_id"], "my-provider")
        self.assertEqual(req["model_policy"]["model_id"], "big-pickle")


# --- 5. coder_router: HARNESS_TRANSPORT=plugin + ImportError -> fail-closed --

class RouterExplicitPluginImportErrorTests(EnvIsolationMixin, unittest.TestCase):
    def test_plugin_explicit_import_error_no_subprocess(self) -> None:
        """HARNESS_TRANSPORT=plugin + M1 ImportError -> error, 0 subprocess calls."""
        _clean_env()
        os.environ["HARNESS_TRANSPORT"] = "plugin"
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)

        real_import = builtins.__import__

        def _block_semantic_transport(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "semantic_transport":
                raise ImportError("blocked for test: M1 adapter unavailable")
            return real_import(name, *args, **kwargs)

        calls: list[tuple] = []

        async def _capture_exec(*args: Any, **kwargs: Any) -> _FakeProc:
            calls.append(args)
            return _FakeProc()

        with mock.patch("builtins.__import__", new=_block_semantic_transport):
            router = _load_router("coder_router_plugin_explicit_import_error")

        self.assertTrue(router._LEGACY_ONLY)
        with mock.patch("asyncio.create_subprocess_exec", new=_capture_exec):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertFalse(payload["ok"])
        self.assertIn("fail-closed", payload["error"])
        self.assertEqual(calls, [])  # legacy subprocess MUST NOT be launched
        self.assertEqual(payload["transport"], "plugin_transport_unavailable")


# --- 6. coder_router: HARNESS_TRANSPORT=cli -> legacy with label -------------

class RouterExplicitCliTests(EnvIsolationMixin, unittest.TestCase):
    def test_cli_explicit_legacy_label(self) -> None:
        """HARNESS_TRANSPORT=cli -> legacy path with opencode_cli_legacy label."""
        _clean_env()
        os.environ["HARNESS_TRANSPORT"] = "cli"
        os.environ["CODER_ROUTER_ALLOWED_ROOTS"] = str(_ROOT)
        router = _load_router()
        self.assertFalse(router._LEGACY_ONLY)

        with mock.patch("asyncio.create_subprocess_exec", new=_fake_create_subprocess_exec):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertEqual(payload["transport"], "opencode_cli_legacy")
        self.assertEqual(payload["legacy_reason"], "plugin bridge not enabled or adapter unavailable")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["exit_code"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)