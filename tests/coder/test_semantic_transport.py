"""Unit tests for scripts/code-factory/semantic_transport.py (DEV-05, M1).

Stdlib-only (unittest): the factory environment does not guarantee pytest.
JSON-schema checks run against the canonical SemanticExecutionResult/1.0
schema via jsonschema when installed (4.26.0 in this environment); the
structural mirror-check covers types as a fallback.

Run:  python -m unittest discover -s tests/coder -p "test_*.py" -v
or:   python scripts/code-factory/semantic_transport.py   (built-in suite)
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CODE_FACTORY = _ROOT / "scripts" / "code-factory"
if str(_CODE_FACTORY) not in sys.path:
    sys.path.insert(0, str(_CODE_FACTORY))

from semantic_transport import (  # noqa: E402
    SEMANTIC_REQUEST_SCHEMA,
    SEMANTIC_RESULT_SCHEMA,
    build_coder_request,
    classify_purpose,
    execute_coder_semantic,
)

_RESULT_REQUIRED = (
    "schema", "execution_id", "runtime_status", "host_session_id",
    "provider_id", "model_id", "structured_output", "raw_output_ref",
    "usage", "timing", "host_error", "host_features_fingerprint",
)
_RUNTIME_STATUSES = frozenset(
    {
        "COMPLETED", "FAILED", "TIMED_OUT", "CANCELLED",
        "REJECTED_BY_HOST", "AUTH_REQUIRED", "HOST_UNAVAILABLE",
    }
)

_SCHEMA_DIR = _ROOT / "packages" / "opencode-harness-plugin" / "schemas"
_RESULT_SCHEMA_PATH = _SCHEMA_DIR / "SemanticExecutionResult.schema.json"

try:
    import jsonschema

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover - environment fallback
    HAVE_JSONSCHEMA = False


def _validate_result(res: dict) -> tuple[bool, str]:
    """Mirror of the module's _validate_result: keys AND types.

    Matches SemanticExecutionResult.schema.json: provider_id/model_id/
    host_session_id are strings (NOT nullable), execution_id is a non-empty
    string, runtime_status is in the canonical enum.
    """
    if not isinstance(res, dict):
        return False, "result must be an object"
    for field in _RESULT_REQUIRED:
        if field not in res:
            return False, f"result missing required field {field!r}"
    if res.get("schema") != SEMANTIC_RESULT_SCHEMA:
        return False, f"result schema mismatch: {res.get('schema')!r}"
    if not isinstance(res.get("runtime_status"), str) or res["runtime_status"] not in _RUNTIME_STATUSES:
        return False, f"invalid runtime_status: {res.get('runtime_status')!r}"
    for field in ("execution_id", "host_session_id", "provider_id", "model_id"):
        if not isinstance(res.get(field), str) or not res[field]:
            return False, f"{field} must be a non-empty string"
    for field in ("structured_output", "usage", "timing"):
        if not isinstance(res.get(field), dict):
            return False, f"{field} must be an object"
    for field in ("raw_output_ref", "host_error", "host_features_fingerprint"):
        if res.get(field) is not None and not isinstance(res.get(field), str):
            return False, f"{field} must be a string or null"
    unknown = set(res) - set(_RESULT_REQUIRED)
    if unknown:
        return False, f"unknown fields in result: {sorted(unknown)!r}"
    return True, ""


def _assert_result_schema_valid(test: unittest.TestCase, res: dict) -> None:
    """JSON-schema check of a result; typed mirror-check fallback."""
    if HAVE_JSONSCHEMA:
        schema = json.loads(_RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=res, schema=schema)
        return
    ok, error = _validate_result(res)
    test.assertTrue(ok, msg=error)


def _clean_env() -> None:
    os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
    os.environ.pop("OPENCODE_HARNESS_ROOT", None)


class SemanticTransportTests(unittest.TestCase):
    def test_build_request_valid(self) -> None:
        req = build_coder_request(
            execution_id="exec-1",
            purpose="CODE_WORK",
            bounded_input={"task": "implement X"},
            expected_output={"schema": "coder-contract/1.0"},
            worktree="feature/abc",
        )
        self.assertEqual(req["schema"], SEMANTIC_REQUEST_SCHEMA)
        self.assertEqual(req["role_ref"], "coder-worker")
        self.assertEqual(req["permission_profile"], "code-worker-write")
        self.assertEqual(req["parent_host_session_id"], "cli")
        self.assertEqual(req["trace"], {"worktree": "feature/abc"})
        self.assertEqual(req["timeout_ms"], 180000)
        # No unknown top-level fields (schema has additionalProperties=false).
        self.assertEqual(
            set(req),
            {
                "schema", "execution_id", "purpose", "contract_schema",
                "role_ref", "parent_host_session_id", "bounded_input",
                "expected_output", "model_policy", "permission_profile",
                "timeout_ms", "trace",
            },
        )

    def test_build_request_roles_and_profiles(self) -> None:
        self.assertEqual(
            build_coder_request(execution_id="e2", purpose="CODE_REVIEW",
                                bounded_input={}, expected_output={},
                                worktree="w")["role_ref"],
            "coder-reviewer",
        )
        self.assertEqual(
            build_coder_request(execution_id="e3", purpose="CODE_TEST_ANALYSIS",
                                bounded_input={}, expected_output={},
                                worktree="w")["permission_profile"],
            "code-tester-readonly",
        )
        # Unknown purpose is classified read-only and rejected at validation.
        self.assertEqual(classify_purpose("CODE_WHATEVER"), "semantic-worker-readonly")
        req = build_coder_request(execution_id="e4", purpose="CODE_WHATEVER",
                                  bounded_input={}, expected_output={}, worktree="w")
        self.assertEqual(execute_coder_semantic(req)["runtime_status"], "REJECTED_BY_HOST")

    def test_execute_fail_closed_legacy(self) -> None:
        # Clear the semantic flag so the legacy path is exercised.
        _clean_env()
        req = build_coder_request(
            execution_id="exec-2",
            purpose="CODE_WORK",
            bounded_input={"task": "t"},
            expected_output={},
            worktree="w",
        )
        res = execute_coder_semantic(req)
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("legacy CLI fallback not allowed in M1", res["host_error"])
        ok, error = _validate_result(res)
        self.assertTrue(ok, msg=error)

    def test_execute_bridge_available_not_wired(self) -> None:
        # Simulate a nominally available bridge: flag + env root + peer file.
        root = _ROOT
        peer = root / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if not peer.is_file():
            self.skipTest("plugin bridge peer file not present in this checkout")
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        os.environ["OPENCODE_HARNESS_ROOT"] = str(root)
        try:
            req = build_coder_request(
                execution_id="exec-3",
                purpose="CODE_REVIEW",
                bounded_input={"task": "t"},
                expected_output={},
                worktree="w",
            )
            res = execute_coder_semantic(req)
            self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
            self.assertIn("plugin bridge failed", res["host_error"])
            ok, error = _validate_result(res)
            self.assertTrue(ok, msg=error)
        finally:
            _clean_env()

    def test_execute_bad_schema(self) -> None:
        res = execute_coder_semantic({"schema": "wrong/1.0", "execution_id": "x"})
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertTrue(res["host_error"].startswith("BAD_SCHEMA"))
        ok, error = _validate_result(res)
        self.assertTrue(ok, msg=error)

    def test_execute_missing_execution_id(self) -> None:
        res = execute_coder_semantic({"schema": SEMANTIC_REQUEST_SCHEMA, "purpose": "CODE_WORK"})
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("execution_id", res["host_error"])
        ok, error = _validate_result(res)
        self.assertTrue(ok, msg=error)

    def test_execute_non_dict_safe(self) -> None:
        """Non-dict requests fail closed to REJECTED_BY_HOST, never raise."""
        _clean_env()
        for bad in (None, "not-a-dict", ["x", 1], 42, 3.14):
            with self.subTest(bad=type(bad).__name__):
                res = execute_coder_semantic(bad)  # must not raise
                self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
                self.assertTrue(res["host_error"].startswith("BAD_SCHEMA"))
                self.assertIn(
                    "request must be a SemanticExecutionRequest object",
                    res["host_error"],
                )
                ok, error = _validate_result(res)
                self.assertTrue(ok, msg=error)

    def test_fail_closed_schema_valid(self) -> None:
        """Every fail-closed path returns a canonical-schema-valid result."""
        _clean_env()
        req = build_coder_request(
            execution_id="exec-sc",
            purpose="CODE_WORK",
            bounded_input={"task": "t"},
            expected_output={},
            worktree="w",
        )
        results = (
            execute_coder_semantic({"schema": "wrong/1.0", "execution_id": "x"}),
            execute_coder_semantic({"schema": SEMANTIC_REQUEST_SCHEMA, "purpose": "CODE_WORK"}),
            execute_coder_semantic(req),
            execute_coder_semantic(None),
            execute_coder_semantic(42),
        )
        for res in results:
            with self.subTest(status=res["runtime_status"]):
                _assert_result_schema_valid(self, res)
                ok, error = _validate_result(res)
                self.assertTrue(ok, msg=error)
                # String identity fields are never None/empty.
                for field in ("execution_id", "host_session_id", "provider_id", "model_id"):
                    self.assertIsInstance(res[field], str)
                    self.assertTrue(res[field])

    def test_execute_unknown_top_level_field_rejected(self) -> None:
        """additionalProperties=false: unknown top-level fields -> BAD_SCHEMA."""
        _clean_env()
        req = build_coder_request(
            execution_id="exec-evil",
            purpose="CODE_WORK",
            bounded_input={},
            expected_output={},
            worktree="w",
        )
        req["evil_field"] = 1
        res = execute_coder_semantic(req)
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertTrue(res["host_error"].startswith("BAD_SCHEMA"))
        self.assertIn("unknown fields", res["host_error"])
        ok, error = _validate_result(res)
        self.assertTrue(ok, msg=error)


if __name__ == "__main__":
    unittest.main(verbosity=2)