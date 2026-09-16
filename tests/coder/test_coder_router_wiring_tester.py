"""Code-tester independent tests for M2 coder router wiring (DEV-05/TD-062).

Independent verification of `mcp/coder_router_server.py`, complementing the
worker's suite with the gaps it leaves open:

- OSError branch of the legacy path must ALSO be flagged
  transport=opencode_cli_legacy (worker covered success + timeout only);
- workdir validation must fail BEFORE any transport: outside allowed roots
  and missing workdir must never reach subprocess OR the semantic bridge;
- the bridge path must NOT launch the legacy subprocess at all;
- the legacy command shape (--pure --model --dir) is verified via a captured
  mocked subprocess call;
- unknown model_class errors before any transport.

No real opencode/model calls — everything is mocked.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import shutil
import tempfile
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


def _load_router(module_name: str = "coder_router_server") -> Any:
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
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode

    async def communicate(self) -> tuple[bytes, bytes]:
        return b"fake stdout", b""

    async def wait(self) -> int:
        return self.returncode


def _no_transport_ever(*args: Any, **kwargs: Any) -> Any:
    """Sentinel transport mock: reaching it means validation did NOT gate."""
    raise AssertionError("a transport was reached when it must have been gated before")


def _fake_completed_result() -> dict:
    """Schema-valid COMPLETED result per SemanticExecutionResult/1.0."""
    return {
        "schema": "semantic-execution-result/1.0",
        "execution_id": "coder-" + "b" * 32,
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


class TesterCoderRouterWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            k: os.environ.get(k)
            for k in ("HARNESS_SEMANTIC_ENABLED", "OPENCODE_HARNESS_ROOT", "CODER_ROUTER_ALLOWED_ROOTS", "HARNESS_TRANSPORT")
        }

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    # --- 1. OSError branch of the legacy path must be flagged ---------------

    def test_legacy_oserror_is_flagged(self) -> None:
        """create_subprocess_exec raises OSError -> flagged legacy, no crash."""
        _clean_env()
        router = _load_router()
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        os.environ.pop("HARNESS_TRANSPORT", None)

        def _raise_oserror(*args: Any, **kwargs: Any) -> Any:
            raise OSError(2, "No such file or directory (mocked)")

        with mock.patch("asyncio.create_subprocess_exec", new=_raise_oserror):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["transport"], "opencode_cli_legacy")
        self.assertEqual(payload["legacy_reason"], "plugin bridge not enabled or adapter unavailable")
        self.assertIn("failed to start opencode", payload["error"])

    # --- 2. workdir validation gates BEFORE any transport ------------------

    def test_workdir_outside_allowed_roots_fails_before_transport(self) -> None:
        """Workdir outside CODER_ROUTER_ALLOWED_ROOTS -> error, NO transport."""
        _clean_env()
        router = _load_router()
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        os.environ.pop("HARNESS_TRANSPORT", None)

        tmp = Path(tempfile.mkdtemp(prefix="m2_outside_"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        # Guard: the temp dir must genuinely be outside the allowed root,
        # otherwise this test would be vacuous.
        self.assertNotIn(_ROOT, tmp.parents)

        with mock.patch("asyncio.create_subprocess_exec", new=_no_transport_ever), mock.patch.object(
            router, "execute_coder_semantic", new=_no_transport_ever
        ):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(tmp)})
            )
        payload = json.loads(out[0].text)
        self.assertFalse(payload["ok"])
        self.assertIn("outside CODER_ROUTER_ALLOWED_ROOTS", payload["error"])
        self.assertIn("allowed_roots", payload)
        self.assertNotIn("transport", payload)  # no transport decision at all

    def test_workdir_missing_fails_before_transport(self) -> None:
        """Non-existent workdir -> error, NO transport."""
        _clean_env()
        router = _load_router()
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        os.environ.pop("HARNESS_TRANSPORT", None)

        missing = _ROOT / "does-not-exist-m2-xyz"
        with mock.patch("asyncio.create_subprocess_exec", new=_no_transport_ever), mock.patch.object(
            router, "execute_coder_semantic", new=_no_transport_ever
        ):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(missing)})
            )
        payload = json.loads(out[0].text)
        self.assertFalse(payload["ok"])
        self.assertIn("workdir does not exist or is not a directory", payload["error"])
        self.assertNotIn("transport", payload)

    # --- 3. Bridge path never touches the legacy subprocess ----------------

    def test_bridge_never_launches_legacy_subprocess(self) -> None:
        """Bridge conditions hold (M3a) -> bridge only; subprocess unused."""
        _clean_env()
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        router = _load_router()
        self.assertFalse(router._LEGACY_ONLY)

        completed = _fake_completed_result()
        exec_calls: list[tuple] = []

        def _fake_execute(req: dict) -> dict:
            return completed

        def _capture_exec(*args: Any, **kwargs: Any) -> _FakeProc:
            exec_calls.append(args)
            return _FakeProc()

        with mock.patch("asyncio.create_subprocess_exec", new=_capture_exec), mock.patch.object(
            router, "execute_coder_semantic", new=_fake_execute
        ):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertEqual(payload["transport"], "harness-plugin-bridge")
        self.assertEqual(exec_calls, [])  # legacy subprocess must NOT be launched
        self.assertEqual(payload["semantic_result"]["runtime_status"], "COMPLETED")
        if HAVE_JSONSCHEMA:
            schema = json.loads(_RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
            jsonschema.validate(instance=payload["semantic_result"], schema=schema)

    # --- 4. Legacy command shape via captured mock ------------------------

    def test_legacy_command_shape_captured(self) -> None:
        """Legacy CLI command must be [BIN run --pure --model M --dir D task]."""
        _clean_env()
        router = _load_router()
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        os.environ.pop("HARNESS_TRANSPORT", None)

        calls: list[tuple] = []

        async def _capture_exec(*args: Any, **kwargs: Any) -> _FakeProc:
            calls.append((args, kwargs))
            return _FakeProc()

        with mock.patch("asyncio.create_subprocess_exec", new=_capture_exec):
            out = asyncio.run(
                router.handle_coder_run(
                    {"task": "my task", "model_class": "polza", "workdir": str(_ROOT)}
                )
            )
        payload = json.loads(out[0].text)
        self.assertEqual(payload["transport"], "opencode_cli_legacy")
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        # create_subprocess_exec(*cmd, ...) forwards each cmd element as a
        # separate positional argument, so args == tuple(cmd).
        cmd = list(args)
        expected = [
            router.OPENCODE_BIN,
            "run", "--pure", "--model", router.MODEL_BY_CLASS["polza"],
            "--dir", str(_ROOT), "my task",
        ]
        self.assertEqual(cmd, expected)
        self.assertEqual(kwargs["cwd"], str(_ROOT))
        self.assertEqual(payload["exit_code"], 0)

    # --- 5. Unknown model_class errors before any transport ----------------

    def test_unknown_model_class_errors_before_transport(self) -> None:
        """Unknown model_class -> ValueError response BEFORE legacy/bridge."""
        _clean_env()
        router = _load_router()
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
        os.environ.pop("HARNESS_TRANSPORT", None)

        with mock.patch("asyncio.create_subprocess_exec", new=_no_transport_ever), mock.patch.object(
            router, "execute_coder_semantic", new=_no_transport_ever
        ):
            out = asyncio.run(
                router.handle_coder_run({"task": "t", "model_class": "no-such-class", "workdir": str(_ROOT)})
            )
        payload = json.loads(out[0].text)
        self.assertFalse(payload["ok"])
        self.assertIn("Unknown model_class", payload["error"])
        self.assertIn("known_model_classes", payload)
        self.assertNotIn("transport", payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
