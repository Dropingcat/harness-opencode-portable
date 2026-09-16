"""Wiring tests for M2: SemanticTransport integration in the coder router.

Covers the DEV-05/TD-062 rule: a single semantic transport; the legacy CLI
fallback is allowed ONLY as an explicit (flagged) fallback — never silent.

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
_ROUTER_PATH = _ROOT / "mcp" / "coder_router_server.py"

try:
    import jsonschema

    _RESULT_SCHEMA_PATH = _ROOT / "packages" / "opencode-harness-plugin" / "schemas" / "SemanticExecutionResult.schema.json"
    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover - environment fallback
    HAVE_JSONSCHEMA = False

_RUNTIME_STATUSES = frozenset(
    {
        "COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED",
        "REJECTED_BY_HOST", "AUTH_REQUIRED", "HOST_UNAVAILABLE",
    }
)


def _load_router(module_name: str = "coder_router_server") -> Any:
    """Load mcp/coder_router_server.py as a standalone module.

    NOTE: `import mcp.coder_router_server` does NOT work here — the local
    `mcp/` dir is shadowed by the installed `mcp` SDK package, so the module
    is loaded via importlib with a synthetic top-level name.
    """
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


class _FakeProc:
    """Minimal fake subprocess for the legacy CLI path (no real launch)."""

    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"fake stdout", b""

    async def wait(self) -> int:
        return self.returncode


async def _fake_create_subprocess_exec(*args: Any, **kwargs: Any) -> _FakeProc:
    return _FakeProc()


def _fake_completed_result() -> dict:
    """Schema-valid COMPLETED result per SemanticExecutionResult/1.0."""
    return {
        "schema": "semantic-execution-result/1.0",
        "execution_id": "coder-" + "a" * 32,
        "runtime_status": "COMPLETED",
        "host_session_id": "fake-host-session",
        "provider_id": "fake-provider",
        "model_id": "fake-model",
        "structured_output": {},
        "raw_output_ref": None,
        "usage": {},
        "timing": {},
        "host_error": None,
        "host_features_fingerprint": None,
    }


class CoderRouterWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in ("HARNESS_SEMANTIC_ENABLED", "OPENCODE_HARNESS_ROOT", "CODER_ROUTER_ALLOWED_ROOTS", "HARNESS_TRANSPORT")}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # --- 1. Legacy path is explicit and flagged -----------------------------

    def test_legacy_transport_flagged(self) -> None:
        """No HARNESS_SEMANTIC_ENABLED -> legacy CLI, clearly flagged."""
        _clean_env()
        router = _load_router()
        self.assertFalse(router._LEGACY_ONLY)  # adapter IS importable here
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        os.environ.pop("HARNESS_TRANSPORT", None)
        with mock.patch("asyncio.create_subprocess_exec", new=_fake_create_subprocess_exec):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "model_class": "free", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertEqual(payload["transport"], "opencode_cli_legacy")
        self.assertEqual(payload["legacy_reason"], "plugin bridge not enabled or adapter unavailable")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["exit_code"], 0)

    def test_legacy_timeout_is_flagged(self) -> None:
        """The legacy timeout branch must also carry the explicit flag."""
        _clean_env()
        router = _load_router()
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        os.environ.pop("HARNESS_TRANSPORT", None)

        class _TimedOutProc(_FakeProc):
            def __init__(self) -> None:
                super().__init__(returncode=1)
                self.killed = False

            async def communicate(self) -> tuple[bytes, bytes]:  # noqa: D102
                raise asyncio.TimeoutError

            def kill(self) -> None:  # noqa: D102
                self.killed = True

        async def _slow_exec(*args: Any, **kwargs: Any) -> _FakeProc:
            return _TimedOutProc()

        with mock.patch("asyncio.create_subprocess_exec", new=_slow_exec):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["transport"], "opencode_cli_legacy")
        self.assertIn("timed out", payload["error"])

    # --- 2. Bridge transport when enabled -----------------------------------

    def test_bridge_transport_when_enabled(self) -> None:
        """Bridge conditions hold (M3a) -> harness-plugin-bridge transport.

        execute_coder_semantic is mocked to return a schema-valid COMPLETED
        result; the built request is verified against the M1 contract.
        """
        _clean_env()
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        os.environ.pop("HARNESS_TRANSPORT", None)  # "auto"
        router = _load_router()
        self.assertFalse(router._LEGACY_ONLY)

        completed = _fake_completed_result()
        captured: dict[str, Any] = {}

        def _fake_execute(req: dict) -> dict:
            captured["req"] = req
            return completed

        with mock.patch.object(router, "execute_coder_semantic", new=_fake_execute):
            out = asyncio.run(
                router.handle_coder_run({"task": "do work", "model_class": "polza", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertEqual(payload["transport"], "harness-plugin-bridge")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["model"], router.MODEL_BY_CLASS["polza"])
        self.assertEqual(payload["workdir"], str(_ROOT))
        # semantic_result must be present and carry a canonical runtime_status.
        self.assertIn("semantic_result", payload)
        self.assertIn(payload["semantic_result"]["runtime_status"], _RUNTIME_STATUSES)
        self.assertEqual(payload["semantic_result"]["runtime_status"], "COMPLETED")
        if HAVE_JSONSCHEMA:
            schema = json.loads(_RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(instance=payload["semantic_result"], schema=schema)

        # The request routed to the adapter honours the M1 contract (M3a:
        # model_id is split into provider_id/model_id at the first "/").
        req = captured["req"]
        self.assertEqual(req["purpose"], "CODE_WORK")
        self.assertEqual(req["permission_profile"], "code-worker-write")
        self.assertEqual(req["bounded_input"], {"task": "do work", "workdir": str(_ROOT)})
        self.assertEqual(
            req["model_policy"],
            {
                "provider_id": router.MODEL_BY_CLASS["polza"].split("/", 1)[0],
                "model_id": router.MODEL_BY_CLASS["polza"].split("/", 1)[1],
            },
        )
        self.assertEqual(req["timeout_ms"], router.TIMEOUT_SECONDS * 1000)
        self.assertEqual(req["trace"], {"worktree": str(_ROOT)})

    # --- 3. Import failure of the M1 adapter -> flagged legacy --------------

    def test_import_failure_falls_back_legacy(self) -> None:
        """M1 import fails -> legacy_only=True; even flag=1 must NOT bridge."""
        _clean_env()
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"  # flag alone is not enough
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        os.environ.pop("HARNESS_TRANSPORT", None)  # "auto"

        real_import = builtins.__import__

        def _block_semantic_transport(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "semantic_transport":
                raise ImportError("blocked for test: M1 adapter unavailable")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", new=_block_semantic_transport):
            router = _load_router("coder_router_server_legacy_only")

        self.assertTrue(router._LEGACY_ONLY)
        with mock.patch("asyncio.create_subprocess_exec", new=_fake_create_subprocess_exec):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertEqual(payload["transport"], "opencode_cli_legacy")
        self.assertEqual(payload["legacy_reason"], "plugin bridge not enabled or adapter unavailable")


if __name__ == "__main__":
    unittest.main(verbosity=2)