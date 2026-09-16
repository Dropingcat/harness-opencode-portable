"""Code-tester additional tests for semantic_transport (DEV-05, M1).

Extends the worker suite with edge cases:
- non-object requests must fail closed (REJECTED_BY_HOST), never crash;
- full JSON-schema validation (request AND result) via jsonschema when
  available, structural mirror-check otherwise;
- partial bridge env (flag/root mismatch) must still fail closed;
- classify_purpose defaults.

Run:  python -m unittest discover -s tests/coder -p "test_*.py" -v
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

_SCHEMA_DIR = _ROOT / "packages" / "opencode-harness-plugin" / "schemas"
_REQUEST_SCHEMA_PATH = _SCHEMA_DIR / "SemanticExecutionRequest.schema.json"
_RESULT_SCHEMA_PATH = _SCHEMA_DIR / "SemanticExecutionResult.schema.json"

try:
    import jsonschema

    HAVE_JSONSCHEMA = True
except ImportError:  # pragma: no cover - environment fallback
    HAVE_JSONSCHEMA = False

_RESULT_REQUIRED = (
    "schema", "execution_id", "runtime_status", "host_session_id",
    "provider_id", "model_id", "structured_output", "raw_output_ref",
    "usage", "timing", "host_error", "host_features_fingerprint",
)


def _clean_env() -> None:
    os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
    os.environ.pop("OPENCODE_HARNESS_ROOT", None)


def _valid_request(**overrides: object) -> dict:
    req = build_coder_request(
        execution_id="tester-exec-1",
        purpose="CODE_WORK",
        bounded_input={"task": "t"},
        expected_output={"schema": "coder-contract/1.0"},
        worktree="w",
    )
    req.update(overrides)
    return req


def _assert_request_schema_valid(test: unittest.TestCase, req: dict) -> None:
    """JSON-schema check of a request; mirror-check fallback."""
    if HAVE_JSONSCHEMA:
        schema = __import__("json").loads(_REQUEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=req, schema=schema)
        return
    # Structural mirror-check (no jsonschema in environment).
    required = {
        "schema", "execution_id", "purpose", "contract_schema",
        "parent_host_session_id", "bounded_input", "expected_output",
        "model_policy", "permission_profile", "timeout_ms", "trace",
    }
    test.assertTrue(required.issubset(set(req)), f"missing required fields: {required - set(req)}")
    test.assertEqual(req["schema"], SEMANTIC_REQUEST_SCHEMA)
    test.assertEqual(set(req) - required, set(), f"unknown fields: {set(req) - required}")


def _assert_result_schema_valid(test: unittest.TestCase, res: dict) -> None:
    """JSON-schema check of a result; mirror-check fallback."""
    if HAVE_JSONSCHEMA:
        schema = __import__("json").loads(_RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=res, schema=schema)
        return
    test.assertTrue(set(_RESULT_REQUIRED).issubset(set(res)))
    test.assertEqual(res["schema"], SEMANTIC_RESULT_SCHEMA)
    test.assertEqual(set(res) - set(_RESULT_REQUIRED), set())


class TesterSemanticTransportTests(unittest.TestCase):
    # --- 1. Invalid schema must fail closed, never crash -------------------

    def test_execute_non_object_no_exception(self) -> None:
        """Non-dict request (None/str/list) must NOT crash.

        Module contract: 'Always returns a valid SemanticExecutionResult/1.0
        dict.' A non-object request is BAD_SCHEMA -> REJECTED_BY_HOST.
        """
        _clean_env()
        for bad in (None, "not-a-dict", ["x", 1], 42):
            with self.subTest(bad=type(bad).__name__):
                res = execute_coder_semantic(bad)  # must not raise
                self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
                self.assertTrue(res["host_error"].startswith("BAD_SCHEMA"), res["host_error"])
                _assert_result_schema_valid(self, res)

    def test_execute_bad_schema_wrong_types(self) -> None:
        """Type violations inside an otherwise complete request -> BAD_SCHEMA."""
        _clean_env()
        cases = {
            "bounded_input_list": _valid_request(bounded_input=["not", "obj"]),
            "model_policy_str": _valid_request(model_policy="strict"),
            "timeout_bool": _valid_request(timeout_ms=True),
            "timeout_zero": _valid_request(timeout_ms=0),
            "timeout_negative": _valid_request(timeout_ms=-5),
            "trace_list": _valid_request(trace=["not", "obj"]),
        }
        for name, req in cases.items():
            with self.subTest(case=name):
                res = execute_coder_semantic(req)
                self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST", name)
                self.assertTrue(res["host_error"].startswith("BAD_SCHEMA"), res["host_error"])
                _assert_result_schema_valid(self, res)

    def test_execute_unknown_purpose_full_request(self) -> None:
        """Unknown purpose in a full valid-shaped request -> BAD_SCHEMA."""
        _clean_env()
        req = _valid_request(purpose="CODE_WHATEVER")
        res = execute_coder_semantic(req)
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("unknown purpose", res["host_error"])
        self.assertTrue(res["host_error"].startswith("BAD_SCHEMA"))
        _assert_result_schema_valid(self, res)

    # --- 2. Valid request, no bridge -> fail-closed legacy -----------------

    def test_execute_valid_no_bridge_fail_closed(self) -> None:
        """Clean env (no flag, no root): valid request -> REJECTED_BY_HOST."""
        _clean_env()
        req = _valid_request()
        res = execute_coder_semantic(req)
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("legacy CLI fallback not allowed in M1", res["host_error"])
        self.assertIn("DEV-05", res["host_error"])
        self.assertEqual(res["execution_id"], "tester-exec-1")
        _assert_result_schema_valid(self, res)

    def test_execute_partial_bridge_env_fail_closed(self) -> None:
        """Partial bridge env (flag xor root) must NOT reach the bridge.

        Availability requires BOTH HARNESS_SEMANTIC_ENABLED=1 AND a resolvable
        existing bridge peer. Any partial state -> REJECTED_BY_HOST.
        """
        # Root set, flag unset.
        _clean_env()
        os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
        res = execute_coder_semantic(_valid_request())
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("legacy CLI fallback not allowed in M1", res["host_error"])
        # Flag set, root unset.
        _clean_env()
        os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
        res = execute_coder_semantic(_valid_request())
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        self.assertIn("legacy CLI fallback not allowed in M1", res["host_error"])
        _clean_env()

    # --- 3. build_coder_request -> valid per SemanticExecutionRequest/1.0 --

    def test_build_request_validates_against_json_schema(self) -> None:
        """Built requests must satisfy the canonical request schema.

        Covers: all required fields, additionalProperties=false, purpose enum,
        timeout_ms>=1, schema const.
        """
        purposes = ("CODE_WORK", "CODE_REVIEW", "CODE_TEST_ANALYSIS")
        for purpose in purposes:
            with self.subTest(purpose=purpose):
                req = build_coder_request(
                    execution_id=f"exec-{purpose}",
                    purpose=purpose,
                    bounded_input={"task": "implement X"},
                    expected_output={"schema": "coder-contract/1.0"},
                    worktree="feature/abc",
                    timeout_ms=30000,
                    model_policy={"provider_id": "p", "model_id": "m"},
                )
                _assert_request_schema_valid(self, req)
                self.assertEqual(req["purpose"], purpose)
                self.assertNotIn("worktree", req)  # must travel in trace only

    def test_build_request_trace_carries_worktree(self) -> None:
        """worktree has no canonical field (additionalProperties=false)."""
        req = build_coder_request(
            execution_id="e", purpose="CODE_WORK", bounded_input={},
            expected_output={}, worktree="feature/z",
        )
        self.assertEqual(req["trace"], {"worktree": "feature/z"})
        self.assertNotIn("worktree", set(req) - {"trace"})
        _assert_request_schema_valid(self, req)

    # --- 4. classify_purpose default ----------------------------------------

    def test_classify_purpose_default(self) -> None:
        """Unknown/missing/empty purpose -> least-privileged default."""
        self.assertEqual(classify_purpose("semantic-worker-readonly"), "semantic-worker-readonly")
        self.assertEqual(classify_purpose("CODE_WHATEVER"), "semantic-worker-readonly")
        self.assertEqual(classify_purpose(""), "semantic-worker-readonly")
        self.assertEqual(classify_purpose(""), "semantic-worker-readonly")
        self.assertEqual(classify_purpose("CODE_WORK"), "code-worker-write")
        self.assertEqual(classify_purpose("CODE_REVIEW"), "code-reviewer-readonly")
        self.assertEqual(classify_purpose("CODE_TEST_ANALYSIS"), "code-tester-readonly")

    # --- 5. Result canonical-schema validity across all paths ---------------

    def test_result_schema_all_paths(self) -> None:
        """Every transport path returns a canonical-valid result."""
        # Bad schema path.
        _clean_env()
        res = execute_coder_semantic({"schema": "wrong/1.0", "execution_id": "x"})
        _assert_result_schema_valid(self, res)
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        # Legacy path.
        res = execute_coder_semantic(_valid_request())
        _assert_result_schema_valid(self, res)
        self.assertEqual(res["runtime_status"], "REJECTED_BY_HOST")
        # Bridge path (available, not wired).
        peer = _ROOT / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"
        if peer.is_file():
            os.environ["HARNESS_SEMANTIC_ENABLED"] = "1"
            os.environ["OPENCODE_HARNESS_ROOT"] = str(_ROOT)
            try:
                res = execute_coder_semantic(_valid_request())
                _assert_result_schema_valid(self, res)
                self.assertEqual(res["runtime_status"], "HOST_UNAVAILABLE")
            finally:
                _clean_env()


if __name__ == "__main__":
    unittest.main(verbosity=2)