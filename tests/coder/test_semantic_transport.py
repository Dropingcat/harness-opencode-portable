"""Unit tests for scripts/code-factory/semantic_transport.py (DEV-05, M1).

Stdlib-only (unittest): the factory environment does not guarantee pytest.

Run:  python -m unittest discover -s tests/coder -p "test_*.py" -v
or:   python scripts/code-factory/semantic_transport.py   (built-in suite)
"""
from __future__ import annotations

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


def _validate_result(res: dict) -> tuple[bool, str]:
    if not isinstance(res, dict):
        return False, "result must be an object"
    for field in _RESULT_REQUIRED:
        if field not in res:
            return False, f"result missing required field {field!r}"
    if res.get("schema") != SEMANTIC_RESULT_SCHEMA:
        return False, f"result schema mismatch: {res.get('schema')!r}"
    if res.get("runtime_status") not in _RUNTIME_STATUSES:
        return False, f"invalid runtime_status: {res.get('runtime_status')!r}"
    unknown = set(res) - set(_RESULT_REQUIRED)
    if unknown:
        return False, f"unknown fields in result: {sorted(unknown)!r}"
    return True, ""


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
        os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
        os.environ.pop("OPENCODE_HARNESS_ROOT", None)
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
        req = build_coder_request(
            execution_id="exec-3",
            purpose="CODE_REVIEW",
            bounded_input={"task": "t"},
            expected_output={},
            worktree="w",
        )
        res = execute_coder_semantic(req)
        self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
        self.assertIn("plugin bridge not yet wired in M1", res["host_error"])
        ok, error = _validate_result(res)
        self.assertTrue(ok, msg=error)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)