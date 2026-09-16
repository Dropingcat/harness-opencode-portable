#!/usr/bin/env python3
"""Semantic transport adapter for the Coder agent (DEV-05, module M1).

Single, canonical transport for Coder semantic executions. Replaces the
duplicated direct `opencode run --pure` calls (legacy `mcp/launchers/_runner.py`).

Contract-first rules honoured here (CODER_DESIGN_PRINCIPLES.md):

  * Contract-first / Immutable contracts — the request must be a valid
    SemanticExecutionRequest/1.0 and the output MUST always be a valid
    SemanticExecutionResult/1.0 (all 12 required fields present, no unknown
    fields, correct per-field types). There is no third "error blob" shape:
    diagnostics travel in the canonical `host_error` / `runtime_status` fields.
  * Schema-valid fail closed — every fail-closed path returns a dict that
    validates against SemanticExecutionResult.schema.json. The schema declares
    `provider_id` / `model_id` / `host_session_id` / `execution_id` as
    NON-nullable strings, so unknown values are rendered as the non-empty
    placeholder ``"unknown"`` (never ``None`` and never ``""``). No host
    session is fabricated: `host_session_id` is ``"unknown"`` on rejections.
  * Fail closed — this module NEVER launches a model. M1 is transport-only:
      - plugin bridge nominally present but not wired -> honest
        HOST_UNAVAILABLE (never a fabricated COMPLETED),
      - legacy CLI fallback -> REJECTED_BY_HOST (the legacy `mcp` boundary is
        out of scope for M1 and must not be imported),
      - an EXPLICIT legacy CLI selection (HARNESS_TRANSPORT=cli /
        transport="cli") -> REJECTED_BY_HOST with an explicit-cli diagnostic
        (never a silent launch, never a silent switch to another transport).
  * Explicit transport selection (M3a): the transport is chosen by the
    operator via `resolve_transport()` (env `HARNESS_TRANSPORT`,
    plugin|cli|auto). "auto" resolves to the plugin bridge only when the
    bridge conditions hold (HARNESS_SEMANTIC_ENABLED=1 + resolvable adapter);
    otherwise it resolves to "cli" (the legacy path, which M1 rejects).
    There is NO silent transport switching anywhere.
  * Non-object requests fail closed to REJECTED_BY_HOST, never raise.
  * No OpenCode SDK / no OpenCode types are imported here (stdlib only).

Explicitly out of scope (do not touch): `mcp/launchers/_runner.py`,
`mcp/coder_router_server.py`, factory gates, Coder authority.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# Canonical schema identifiers (see packages/opencode-harness-plugin/schemas).
SEMANTIC_REQUEST_SCHEMA = "semantic-execution-request/1.0"
SEMANTIC_RESULT_SCHEMA = "semantic-execution-result/1.0"
CONTRACT_SCHEMA = "coder-contract/1.0"

# Schema-valid placeholder for unknown string fields (SemanticExecutionResult/1.0
# declares provider_id/model_id/host_session_id/execution_id as non-nullable
# strings, so an unknown value must be a non-empty string, never None/"").
_UNKNOWN = "unknown"

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

# Transport selection env var (M3a). Values: plugin | cli | auto. Default
# "auto" = resolve to the plugin bridge when it is available, else "cli".
# A MISSING/empty value behaves exactly like "auto" (backwards compatible
# with the pre-M3a routing, where the flag+adapter decided the transport).
_TRANSPORT_ENV = "HARNESS_TRANSPORT"

# Canonical transport identifiers used by the router responses.
TRANSPORT_PLUGIN = "plugin"
TRANSPORT_CLI = "cli"
_TRANSPORT_AUTO = "auto"
_VALID_TRANSPORT_VALUES = frozenset({TRANSPORT_PLUGIN, TRANSPORT_CLI, _TRANSPORT_AUTO})

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

# Every top-level field the request schema permits: the required fields plus
# the optional `role_ref`. Anything else violates additionalProperties=false.
_REQUEST_ALLOWED = frozenset(_REQUEST_REQUIRED) | {"role_ref"}


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

    Returns ``(ok, error)``. Deterministic and side-effect free. Mirrors the
    canonical schema: all required fields present, no unknown top-level fields
    (additionalProperties=false), and per-field types. Unknown purpose values
    fail here because the canonical schema enumerates them.
    """
    if not isinstance(req, dict):
        return False, "BAD_SCHEMA: request must be a SemanticExecutionRequest object"
    if req.get("schema") != SEMANTIC_REQUEST_SCHEMA:
        return False, f"BAD_SCHEMA: expected schema={SEMANTIC_REQUEST_SCHEMA!r}"
    unknown = set(req) - _REQUEST_ALLOWED
    if unknown:
        return False, (
            f"BAD_SCHEMA: unknown fields {sorted(unknown)!r} "
            "(additionalProperties=false)"
        )
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
    if not isinstance(req.get("contract_schema"), str) or not req["contract_schema"]:
        return False, "BAD_SCHEMA: contract_schema must be a non-empty string"
    if not isinstance(req.get("parent_host_session_id"), str) or not req["parent_host_session_id"]:
        return False, "BAD_SCHEMA: parent_host_session_id must be a non-empty string"
    if not isinstance(req.get("permission_profile"), str) or not req["permission_profile"]:
        return False, "BAD_SCHEMA: permission_profile must be a non-empty string"
    if "role_ref" in req and not isinstance(req["role_ref"], str):
        return False, "BAD_SCHEMA: role_ref must be a string"
    if not isinstance(req.get("bounded_input"), dict):
        return False, "BAD_SCHEMA: bounded_input must be an object"
    if not isinstance(req.get("expected_output"), dict):
        return False, "BAD_SCHEMA: expected_output must be an object"
    if not isinstance(req.get("model_policy"), dict):
        return False, "BAD_SCHEMA: model_policy must be an object"
    for key in ("provider_id", "model_id", "agent"):
        if key in req["model_policy"] and not isinstance(req["model_policy"][key], str):
            return False, f"BAD_SCHEMA: model_policy.{key} must be a string"
    if not isinstance(req.get("trace"), dict):
        return False, "BAD_SCHEMA: trace must be an object"
    timeout_ms = req.get("timeout_ms")
    if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or timeout_ms <= 0:
        return False, "BAD_SCHEMA: timeout_ms must be a positive integer"
    return True, ""


def _string_field(value: object, fallback: str = _UNKNOWN) -> str:
    """Non-empty string, else ``fallback``.

    SemanticExecutionResult/1.0 declares provider_id/model_id/host_session_id/
    execution_id as plain strings (NOT nullable), so unknown values are
    rendered as the non-empty placeholder ``"unknown"`` — never None/"".
    """
    if isinstance(value, str) and value:
        return value
    return fallback


def _dict_field(value: object) -> dict:
    """Plain dict (copied), else {} — never None."""
    if isinstance(value, dict):
        return dict(value)
    return {}


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
    """Build a strict SemanticExecutionResult/1.0 dict (all 12 fields).

    Schema-valid by construction: string fields are non-empty (``"unknown"``
    fallback), object fields are dicts, nullable fields stay null.
    """
    if runtime_status not in _RUNTIME_STATUSES:
        raise ValueError(f"invalid runtime_status: {runtime_status!r}")
    return {
        "schema": SEMANTIC_RESULT_SCHEMA,
        "execution_id": _string_field(execution_id),
        "runtime_status": runtime_status,
        "host_session_id": _string_field(host_session_id),
        "provider_id": _string_field(provider_id),
        "model_id": _string_field(model_id),
        "structured_output": _dict_field(structured_output),
        "raw_output_ref": raw_output_ref if isinstance(raw_output_ref, str) else None,
        "usage": _dict_field(usage),
        "timing": _dict_field(timing),
        "host_error": host_error if isinstance(host_error, str) else None,
        "host_features_fingerprint": (
            host_features_fingerprint if isinstance(host_features_fingerprint, str) else None
        ),
    }


def _validate_result(res: dict) -> tuple[bool, str]:
    """Strict check of a SemanticExecutionResult/1.0 dict.

    Mirrors packages/opencode-harness-plugin/schemas/SemanticExecutionResult.schema.json:
    all 12 required fields, exact field set (additionalProperties=false) and
    per-field TYPES — provider_id/model_id/host_session_id are strings (NOT
    nullable), execution_id is a non-empty string, runtime_status is in the
    canonical enum. Returns ``(ok, error)``.
    """
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
    unknown = set(res) - set(required)
    if unknown:
        return False, f"unknown fields in result: {sorted(unknown)!r}"
    return True, ""


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


def resolve_transport(*, explicit: str | None = None) -> str:
    """Resolve the transport to use (M3a explicit transport selection).

    ``explicit`` is the operator-chosen transport: ``"plugin"``, ``"cli"``,
    ``"auto"`` or ``None``. When ``explicit`` is None the value is read from
    the ``HARNESS_TRANSPORT`` env var; a missing/empty env value behaves as
    ``"auto"`` (pre-M3a compatible default).

    Resolution rules (deterministic, no I/O beyond the bridge probe):

    * ``"plugin"`` -> ``"plugin"`` (unconditional; fail-closed handling of an
      unavailable bridge is the caller's job — it must NOT silently switch).
    * ``"cli"`` -> ``"cli"`` (unconditional).
    * ``"auto"`` -> ``"plugin"`` iff the plugin bridge conditions hold
      (``HARNESS_SEMANTIC_ENABLED=1`` + resolvable bridge adapter),
      otherwise ``"cli"``.
    * Unknown/empty values -> ``"auto"`` semantics (defensive: a typo in
      HARNESS_TRANSPORT must never produce a surprise transport).

    Note: in ``"auto"`` mode an unavailable bridge legitimately resolves to
    ``"cli"``. That is the documented auto behaviour, NOT a silent switch —
    a silent switch would be ``HARNESS_TRANSPORT=plugin`` + unavailable
    bridge falling back to the CLI, which is forbidden and handled by the
    callers as fail-closed (see ``execute_coder_semantic``).
    """
    if explicit is None:
        explicit = os.environ.get(_TRANSPORT_ENV) or _TRANSPORT_AUTO
    if explicit in _VALID_TRANSPORT_VALUES and explicit != _TRANSPORT_AUTO:
        # "plugin" / "cli" are unconditional. Unknown values fall through to
        # auto semantics (defensive: a typo in HARNESS_TRANSPORT must never
        # produce a surprise transport).
        return explicit
    if _plugin_bridge_available():
        return TRANSPORT_PLUGIN
    return TRANSPORT_CLI


def _explicit_cli_rejected(request: dict) -> dict:
    """Fail-closed path for an explicit legacy CLI selection.

    M3a rule (DEV-05): when the OPERATOR explicitly selects the CLI transport
    (HARNESS_TRANSPORT=cli / transport="cli"), M1 must NOT launch OpenCode and
    must NOT silently switch to another transport. The honest outcome is
    REJECTED_BY_HOST with a diagnostic that names the explicit selection.
    """
    reason = "explicit cli transport selected; not implemented in M1"
    model_policy = request.get("model_policy") or {}
    return _result(
        execution_id=request["execution_id"],
        runtime_status="REJECTED_BY_HOST",
        host_error=reason,
        provider_id=model_policy.get("provider_id"),
        model_id=model_policy.get("model_id"),
    )


def _execute_via_plugin_bridge(request: dict) -> dict:
    """Route through the plugin bridge reverse call ``semantic.execute``.

    M1 status: the bridge peer is present but the reverse channel is NOT yet
    wired into a live stdio bridge session. Honest classification only — the
    module never fabricates a COMPLETED result. No host session is claimed:
    `host_session_id` falls back to the schema-valid placeholder ``"unknown"``.
    """
    model_policy = request.get("model_policy") or {}
    return _result(
        execution_id=request["execution_id"],
        runtime_status="HOST_UNAVAILABLE",
        host_error="plugin bridge not yet wired in M1",
        provider_id=model_policy.get("provider_id"),
        model_id=model_policy.get("model_id"),
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
    model_policy = request.get("model_policy") or {}
    return _result(
        execution_id=request["execution_id"],
        runtime_status="REJECTED_BY_HOST",
        host_error=f"{reason}: {detail}",
        provider_id=model_policy.get("provider_id"),
        model_id=model_policy.get("model_id"),
    )


def execute_coder_semantic(
    request: dict, *, transport: str | None = None
) -> dict:
    """Execute (transport) a SemanticExecutionRequest/1.0 for the Coder agent.

    Deterministic and fail-closed (M3a explicit transport selection). The
    transport is chosen BEFORE any execution and never silently switched:

    1. Request schema invalid (including non-object requests) ->
       SemanticExecutionResult/1.0 with ``runtime_status=REJECTED_BY_HOST`` and
       ``host_error`` starting with ``BAD_SCHEMA`` (canonical statuses carry no
       separate error code). Non-object inputs never raise.
    2. ``transport="cli"`` (explicit operator selection) -> ``REJECTED_BY_HOST``
       with ``host_error="explicit cli transport selected; not implemented in
       M1"``. The legacy CLI is NEVER launched from M1 and there is NO silent
       switch to another transport.
    3. ``transport="plugin"`` -> the plugin bridge path ONLY when the bridge is
       available; an unavailable bridge fails closed to ``HOST_UNAVAILABLE``
       (no CLI fallback, no silent switch).
    4. ``transport=None`` -> resolved via ``resolve_transport()``:
       - resolves to ``"plugin"`` -> plugin bridge path (HOST_UNAVAILABLE when
         the bridge is not wired, honest per M1);
       - resolves to ``"cli"`` -> ``REJECTED_BY_HOST`` with the legacy-fallback
         diagnostic (M1 never launches a model; the legacy boundary is out of
         M1 scope).

    Always returns a valid SemanticExecutionResult/1.0 dict.
    """
    ok, error = _validate_request(request)
    if not ok:
        execution_id = request.get("execution_id") if isinstance(request, dict) else None
        return _result(
            execution_id=execution_id,
            runtime_status="REJECTED_BY_HOST",
            host_error=error,
        )

    explicit_choice = transport is not None
    selected = transport if explicit_choice else resolve_transport()

    if selected == TRANSPORT_CLI:
        # "cli" can be reached two ways, with two DIFFERENT diagnostics:
        #  * explicit transport="cli" (or HARNESS_TRANSPORT=cli) -> the M3a
        #    explicit-cli diagnostic (never a launch, never a silent switch);
        #  * auto-resolved (flag/bridge unavailable) -> the pre-M3a legacy
        #    fallback diagnostic. Both are REJECTED_BY_HOST; M1 never launches.
        if explicit_choice or os.environ.get(_TRANSPORT_ENV) == TRANSPORT_CLI:
            return _explicit_cli_rejected(request)
        return _legacy_fallback_rejected(request)

    # selected == TRANSPORT_PLUGIN (auto with an available bridge or explicit
    # "plugin"). Explicit "plugin" + unavailable bridge is fail-closed
    # HOST_UNAVAILABLE — never a CLI fallback.
    if _plugin_bridge_available():
        return _execute_via_plugin_bridge(request)
    return _result(
        execution_id=request["execution_id"],
        runtime_status="HOST_UNAVAILABLE",
        host_error="plugin bridge unavailable; fail-closed (no CLI fallback)",
        provider_id=(request.get("model_policy") or {}).get("provider_id"),
        model_id=(request.get("model_policy") or {}).get("model_id"),
    )


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
    policy = dict(model_policy) if model_policy else {}
    if "model_id" in policy:
        provider_id, model_id = _split_provider_model(policy["model_id"])
        # M3a: "provider/model" -> split at the first "/"; a value WITHOUT "/"
        # -> provider_id = model_id. An explicit provider_id (the canonical
        # request field) always wins over the inferred one.
        policy["model_id"] = model_id
        if provider_id is not None:
            policy.setdefault("provider_id", provider_id)
    return {
        "schema": SEMANTIC_REQUEST_SCHEMA,
        "execution_id": execution_id,
        "purpose": purpose,
        "contract_schema": CONTRACT_SCHEMA,
        "role_ref": _role_for_purpose(purpose),
        "parent_host_session_id": parent_host_session_id,
        "bounded_input": dict(bounded_input),
        "expected_output": dict(expected_output),
        "model_policy": policy,
        "permission_profile": classify_purpose(purpose),
        "timeout_ms": int(timeout_ms),
        "trace": trace,
    }


def _split_provider_model(model_id: str) -> tuple[str | None, str]:
    """Split a ``provider/model`` model id at the FIRST ``/`` (M3a).

    ``"opencode/big-pickle"`` -> ``("opencode", "big-pickle")``.
    A value WITHOUT ``/`` -> ``(model_id, model_id)`` (provider_id = model_id
    per M3a). ``/model`` (empty provider) or a non-string -> ``(None, original)``
    so the caller leaves provider_id untouched (an empty provider_id would be
    ambiguous, not a meaningful split).
    """
    if isinstance(model_id, str) and "/" in model_id:
        provider, _, rest = model_id.partition("/")
        if provider:
            return provider, rest
        return None, model_id
    if isinstance(model_id, str):
        return model_id, model_id
    return None, model_id


def _run_unit_tests() -> int:
    """Stdlib unit tests (no pytest available in this environment)."""
    import unittest

    try:
        import jsonschema

        _HAVE_JSONSCHEMA = True
    except ImportError:  # pragma: no cover - environment fallback
        _HAVE_JSONSCHEMA = False

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
                self.assertIn("plugin bridge not yet wired in M1", res["host_error"])
                ok, error = _validate_result(res)
                self.assertTrue(ok, msg=error)
            finally:
                os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
                os.environ.pop("OPENCODE_HARNESS_ROOT", None)

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
            os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
            os.environ.pop("OPENCODE_HARNESS_ROOT", None)
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

        def test_fail_closed_result_schema_valid(self) -> None:
            """All fail-closed paths validate against the canonical schema."""
            if not _HAVE_JSONSCHEMA:
                self.skipTest("jsonschema not installed")
            schema_path = (
                Path(__file__).resolve().parents[2]
                / "packages" / "opencode-harness-plugin" / "schemas"
                / "SemanticExecutionResult.schema.json"
            )
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            os.environ.pop("HARNESS_SEMANTIC_ENABLED", None)
            os.environ.pop("OPENCODE_HARNESS_ROOT", None)
            req = build_coder_request(
                execution_id="e", purpose="CODE_WORK",
                bounded_input={}, expected_output={}, worktree="w",
            )
            results = (
                execute_coder_semantic({"schema": "wrong/1.0", "execution_id": "x"}),
                execute_coder_semantic({"schema": SEMANTIC_REQUEST_SCHEMA, "purpose": "CODE_WORK"}),
                execute_coder_semantic(req),
                execute_coder_semantic(None),
            )
            for res in results:
                with self.subTest(status=res["runtime_status"]):
                    jsonschema.validate(instance=res, schema=schema)
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

        def test_validate_unknown_top_level_field(self) -> None:
            """additionalProperties=false: unknown top-level fields -> BAD_SCHEMA."""
            base = build_coder_request(execution_id="e", purpose="CODE_WORK",
                                       bounded_input={}, expected_output={}, worktree="w")
            bad = dict(base, evil_field=1)
            ok, error = _validate_request(bad)
            self.assertFalse(ok)
            self.assertIn("unknown fields", error)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SemanticTransportTests)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(_run_unit_tests())