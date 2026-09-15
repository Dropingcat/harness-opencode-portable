#!/usr/bin/env python3
"""Semantic transport adapter for the Coder agent (DEV-05, module M1).

Single, canonical transport for Coder semantic executions. Replaces the
duplicated direct `opencode run --pure` calls (legacy `mcp/launchers/_runner.py`).

Contract-first rules honoured here (CODER_DESIGN_PRINCIPLES.md):

  * Contract-first / Immutable contracts — the request must be a valid
    SemanticExecutionRequest/1.0 and the output MUST always be a valid
    SemanticExecutionResult/1.0 (all 12 required fields present, no unknown
    fields). There is no third "error blob" shape: diagnostics travel in the
    canonical `host_error` / `runtime_status` fields.
  * Fail closed — this module NEVER launches a model. M1 is transport-only:
      - plugin bridge nominally present but not wired -> honest
        HOST_UNAVAILABLE (never a fabricated COMPLETED),
      - legacy CLI fallback -> REJECTED_BY_HOST (the legacy `mcp` boundary is
        out of scope for M1 and must not be imported).
  * No OpenCode SDK / no OpenCode types are imported here (stdlib only).

Explicitly out of scope (do not touch): `mcp/launchers/_runner.py`,
`mcp/coder_router_server.py`, factory gates, Coder authority.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

# Canonical schema identifiers (see packages/opencode-harness-plugin/schemas).
SEMANTIC_REQUEST_SCHEMA = "semantic-execution-request/1.0"
SEMANTIC_RESULT_SCHEMA = "semantic-execution-result/1.0"
CONTRACT_SCHEMA = "coder-contract/1.0"

# Valid runtime_status values from SemanticExecutionResult/1.0.
_RUNTIME_STATUSES = frozenset(
    {
        "COMPLETED",
        "FAILED",
        "TIMED_OUT",
        "CANCELLED",
        "REJECTED_BY_HOST",
        "AUTH_REQUIRED",
        "HOST_UNAVAILABLE",
    }
)

# Role that actually executes the bounded task, per purpose.
_ROLE_BY_PURPOSE = {
    "CODE_WORK": "coder-worker",
    "CODE_REVIEW": "coder-reviewer",
    "CODE_TEST_ANALYSIS": "coder-tester",
}

# purpose -> default permission_profile.
_PURPOSE_PROFILES = {
    "CODE_WORK": "code-worker-write",
    "CODE_REVIEW": "code-reviewer-readonly",
    "CODE_TEST_ANALYSIS": "code-tester-readonly",
}

# Fields REQUIRED by the SemanticExecutionRequest/1.0 schema.
_REQUEST_REQUIRED = (
    "schema",
    "execution_id",
    "purpose",
    "contract_schema",
    "parent_host_session_id",
    "bounded_input",
    "expected_output",
    "model_policy",
    "permission_profile",
    "timeout_ms",
    "trace",
)


def classify_purpose(purpose: str) -> str:
    """Map a Coder purpose to its default permission_profile.

    Unknown purposes fail closed to the least-privileged default
    ``semantic-worker-readonly`` (read-only; never elevated).
    """
    return _PURPOSE_PROFILES.get(purpose, "semantic-worker-readonly")


def _role_for_purpose(purpose: str) -> str:
    """role_ref for a Coder purpose (unknown -> coder-worker, no elevation)."""
    return _ROLE_BY_PURPOSE.get(purpose, "coder-worker")


def _validate_request(req: dict) -> tuple[bool, str]:
    """Structural check of a SemanticExecutionRequest/1.0 dict.

    Returns ``(ok, error)``. Deterministic and side-effect free. Unknown
    purpose values fail here because the canonical schema enumerates them.
    """
    if not isinstance(req, dict):
        return False, "BAD_SCHEMA: request must be an object"
    if req.get("schema") != SEMANTIC_REQUEST_SCHEMA:
        return False, f"BAD_SCHEMA: expected schema={SEMANTIC_REQUEST_SCHEMA!r}"
    for field in _REQUEST_REQUIRED:
        if field not in req:
            return False, f"BAD_SCHEMA: missing required field {field!r}"
    if not isinstance(req.get("execution_id"), str) or not req["execution_id"]:
        return False, "BAD_SCHEMA: execution_id must be a non-empty string"
    purpose = req.get("purpose")
    if not isinstance(purpose, str) or not purpose:
        return False, "BAD_SCHEMA: purpose must be a non-empty string"
    if purpose not in _PURPOSE_PROFILES:
        return False, f"BAD_SCHEMA: unknown purpose {purpose!r}"
    if not isinstance(req.get("bounded_input"), dict):
        return False, "BAD_SCHEMA: bounded_input must be an object"
    if not isinstance(req.get("expected_output"), dict):
        return False, "BAD_SCHEMA: expected_output must be an object"
    if not isinstance(req.get("model_policy"), dict):
        return False, "BAD_SCHEMA: model_policy must be an object"
    if not isinstance(req.get("trace"), dict):
        return False, "BAD_SCHEMA: trace must be an object"
    timeout_ms = req.get("timeout_ms")
    if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or timeout_ms <= 0:
        return False, "BAD_SCHEMA: timeout_ms must be a positive integer"
    return True, ""


def _result(
    *,
    execution_id: str,
    runtime_status: str,
    host_error: str | None,
    host_session_id: str | None = None,
    provider_id: str | None = None,
    model_id: str | None = None,
    structured_output: dict | None = None,
    raw_output_ref: str | None = None,
    usage: dict | None = None,
    timing: dict | None = None,
    host_features_fingerprint: str | None = None,
) -> dict:
    """Build a strict SemanticExecutionResult/1.0 dict (all 12 fields)."""
    if runtime_status not in _RUNTIME_STATUSES:
        raise ValueError(f"invalid runtime_status: {runtime_status!r}")
    return {
        "schema": SEMANTIC_RESULT_SCHEMA,
        "execution_id": execution_id,
        "runtime_status": runtime_status,
        "host_session_id": host_session_id,
        "provider_id": provider_id,
        "model_id": model_id,
        "structured_output": structured_output if structured_output is not None else {},
        "raw_output_ref": raw_output_ref,
        "usage": usage if usage is not None else {},
        "timing": timing if timing is not None else {},
        "host_error": host_error,
        "host_features_fingerprint": host_features_fingerprint,
    }


def _bridge_peer_path() -> Path | None:
    """Path to the plugin bridge peer, or None when the env root is unset."""
    root = os.environ.get("OPENCODE_HARNESS_ROOT")
    if not root:
        return None
    return Path(root) / "packages" / "opencode-harness-plugin" / "core" / "bridge_peer.py"


def _plugin_bridge_available() -> bool:
    """Deterministic availability probe for the plugin bridge.

    Mirrors the task gate exactly: ``HARNESS_SEMANTIC_ENABLED=1`` AND
    ``OPENCODE_HARNESS_ROOT`` is set AND the bridge peer file exists.
    """
    if os.environ.get("HARNESS_SEMANTIC_ENABLED") != "1":
        return False
    peer = _bridge_peer_path()
    if peer is None:
        return False
    return peer.is_file()


def _execute_via_plugin_bridge(request: dict) -> dict:
    """Route through the plugin bridge reverse call ``semantic.execute``.

    M1 status: the bridge peer is present but the reverse channel is NOT yet
    wired into a live stdio bridge session. Honest classification only — the
    module never fabricates a COMPLETED result.
    """
    return _result(
        execution_id=request["execution_id"],
        runtime_status="HOST_UNAVAILABLE",
        host_error="plugin bridge not yet wired in M1",
        host_session_id=request.get("parent_host_session_id"),
        provider_id=(request.get("model_policy") or {}).get("provider_id"),
        model_id=(request.get("model_policy") or {}).get("model_id"),
    )


def _legacy_fallback_rejected(request: dict) -> dict:
    """Fail-closed legacy path.

    M1 does NOT import ``mcp.launchers._runner`` (that legacy boundary is out
    of scope for DEV-05/M1) and NEVER launches a model. Any request that would
    otherwise fall back to the legacy CLI is REJECTED_BY_HOST.
    """
    profile = request.get("permission_profile", "")
    reason = "legacy CLI fallback not allowed in M1 (DEV-05)"
    detail = f"permission_profile={profile!r}" if profile else "no permission_profile"
    return _result(
        execution_id=request["execution_id"],
        runtime_status="REJECTED_BY_HOST",
        host_error=f"{reason}: {detail}",
        host_session_id=request.get("parent_host_session_id"),
        provider_id=(request.get("model_policy") or {}).get("provider_id"),
        model_id=(request.get("model_policy") or {}).get("model_id"),
    )


def execute_coder_semantic(request: dict) -> dict:
    """Execute (transport) a SemanticExecutionRequest/1.0 for the Coder agent.

    Deterministic and fail-closed. Three outcomes:

    1. Request schema invalid -> SemanticExecutionResult/1.0 with
       ``runtime_status=REJECTED_BY_HOST`` and ``host_error`` starting with
       ``BAD_SCHEMA`` (canonical statuses carry no separate error code).
    2. Plugin bridge available (env flag + env root + bridge peer file):
       reverse call ``semantic.execute``. Not yet wired in M1, so the honest
       result is ``HOST_UNAVAILABLE`` — never a fabricated COMPLETED.
    3. Otherwise: legacy fallback is FORBIDDEN in M1 (no `mcp` import, no
       model launch) -> ``REJECTED_BY_HOST``.

    Always returns a valid SemanticExecutionResult/1.0 dict.
    """
    ok, error = _validate_request(request)
    if not ok:
        return _result(
            execution_id=str(request.get("execution_id") or ""),
            runtime_status="REJECTED_BY_HOST",
            host_error=error,
        )
    if _plugin_bridge_available():
        return _execute_via_plugin_bridge(request)
    return _legacy_fallback_rejected(request)


def build_coder_request(
    *,
    execution_id: str,
    purpose: str,
    bounded_input: dict,
    expected_output: dict,
    worktree: str,
    timeout_ms: int = 180000,
    model_policy: dict | None = None,
) -> dict:
    """Build a valid SemanticExecutionRequest/1.0 dict for the Coder agent.

    Keyword-only factory. ``worktree`` has no canonical field in
    SemanticExecutionRequest/1.0 (additionalProperties=false), so it travels
    inside ``trace`` (observable, non-payload diagnostic), never as a top-level
    field. Unknown purposes are NOT silently accepted: the canonical schema
    enumerates purposes, so they surface as ``BAD_SCHEMA`` at validation time.
    """
    parent_host_session_id = os.environ.get("OPENCODE_SESSION_ID") or "cli"
    trace = {"worktree": worktree}
    return {
        "schema": SEMANTIC_REQUEST_SCHEMA,
        "execution_id": execution_id,
        "purpose": purpose,
        "contract_schema": CONTRACT_SCHEMA,
        "role_ref": _role_for_purpose(purpose),
        "parent_host_session_id": parent_host_session_id,
        "bounded_input": dict(bounded_input),
        "expected_output": dict(expected_output),
        "model_policy": dict(model_policy) if model_policy else {},
        "permission_profile": classify_purpose(purpose),
        "timeout_ms": int(timeout_ms),
        "trace": trace,
    }


def _run_unit_tests() -> int:
    """Stdlib unit tests (no pytest available in this environment)."""
    import unittest

    class SemanticTransportTests(unittest.TestCase):
        def test_build_request_valid(self) -> None:
            req = build_coder_request(
                execution_id="exec-1",
                purpose="CODE_WORK",
                bounded_input={"task": "implement X"},
                expected_output={"schema": "coder-contract/1.0"},
                worktree="feature/abc",
            )
            ok, error = _validate_request(req)
            self.assertTrue(ok, msg=error)
            self.assertEqual(req["schema"], SEMANTIC_REQUEST_SCHEMA)
            self.assertEqual(req["role_ref"], "coder-worker")
            self.assertEqual(req["permission_profile"], "code-worker-write")
            self.assertEqual(req["parent_host_session_id"], "cli")
            self.assertEqual(req["trace"], {"worktree": "feature/abc"})
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
            # Unknown purpose is classified read-only and validated as BAD_SCHEMA.
            self.assertEqual(classify_purpose("CODE_WHATEVER"), "semantic-worker-readonly")
            req = build_coder_request(execution_id="e4", purpose="CODE_WHATEVER",
                                      bounded_input={}, expected_output={}, worktree="w")
            ok, _ = _validate_request(req)
            self.assertFalse(ok)

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
            root = Path(__file__).resolve().parents[2]
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

        def test_validate_timeout(self) -> None:
            base = build_coder_request(execution_id="e", purpose="CODE_WORK",
                                       bounded_input={}, expected_output={}, worktree="w")
            bad = dict(base, timeout_ms=0)
            ok, error = _validate_request(bad)
            self.assertFalse(ok)
            self.assertIn("timeout_ms", error)

        def test_validate_purpose_missing(self) -> None:
            base = build_coder_request(execution_id="e", purpose="CODE_WORK",
                                       bounded_input={}, expected_output={}, worktree="w")
            bad = dict(base)
            del bad["purpose"]
            ok, error = _validate_request(bad)
            self.assertFalse(ok)
            self.assertIn("purpose", error)

    def _validate_result(res: dict) -> tuple[bool, str]:
        required = (
            "schema", "execution_id", "runtime_status", "host_session_id",
            "provider_id", "model_id", "structured_output", "raw_output_ref",
            "usage", "timing", "host_error", "host_features_fingerprint",
        )
        if not isinstance(res, dict):
            return False, "result must be an object"
        for field in required:
            if field not in res:
                return False, f"result missing required field {field!r}"
        if res.get("schema") != SEMANTIC_RESULT_SCHEMA:
            return False, f"result schema mismatch: {res.get('schema')!r}"
        if res.get("runtime_status") not in _RUNTIME_STATUSES:
            return False, f"invalid runtime_status: {res.get('runtime_status')!r}"
        unknown = set(res) - set(required)
        if unknown:
            return False, f"unknown fields in result: {sorted(unknown)!r}"
        return True, ""

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SemanticTransportTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(_run_unit_tests())
