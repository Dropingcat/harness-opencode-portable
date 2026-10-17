# R1 architecture delta — P2-adapter component recovery

Task r1-p2-adapter-20261017; parent p2-r0-20261017; status target R1_COMPONENT_VERIFIED / HOST_NOT_TESTED.
Scope authority: owner R1 contract in handoff/p2-r0-2026-10-17/R1_IMPLEMENTATION_AND_CANARY_PLAN.md.
No host session/model mutation, no paid calls, no credentials read, no active plugin/config change.

## 1. What is reused (unchanged)

- `guard/src/artifact_guard.py` scanner shell: `scan_artifact` admission pipeline,
  `_report`, `_chunks`, `_hash`, `_identity`, `_config`, `_load_stages`,
  `_bounded_p2` (multiprocess fence), coverage/identity/config-change checks,
  P0 `session_guard._normalize`/`_suspicion`/`STRONG_EN`/`WEAK_RU`.
- `guard/src/session_guard.py` P0 stage — untouched.
- `guard/src/semantic_layer.py` classification schema:
  `Budget`, `ClassifierChain`, `_parse_verdict`, `P2_PROMPT`, `P2_VOTES`,
  majority vote, `analyze` coverage semantics — untouched.
- Existing P2 contract surface consumed by `artifact_guard._p2_run`:
  keys verdict/votes/provider/cost/alarm_level/alarm_info; fail-closed checks.
- Repo test convention: stdlib `unittest`, files in `tests/coder/`, pattern
  `test_guard_*_stage1.py`, `ROOT = Path(__file__).resolve().parents[2]`,
  `sys.path.insert(0, str(ROOT / 'guard/src'))`, fixture chains via
  `chain_factory=` (function-argument injection only, no CLI/env selection).
- R0 evidence: `handoff/p2-r0-2026-10-17/evidence/openapi-managed.json`.

## 2. Components added (new files)

| File | Responsibility |
|---|---|
| `guard/src/opencode_transport.py` | Provenance-typed DTOs (ParentContext, RequestSnapshot, HostMessage, AdapterResult), immutable snapshot, strict `from_cli_json` decoders bound to `Session.Info`/`Model.Ref`/`Session.Message.Assistant` shapes, fail-closed model/context validation. No HTTP; no credentials. Pure stdlib. |
| `guard/src/execution_tracker.py` | Internal states NEW→BOUND→SUBMITTED→WAITING→COMPLETED/FAILED/TIMED_OUT/CANCELLED; queue-admission ≠ terminal; owner/session/message correlation; late-result refusal; fail-closed progression. Fake-transport driven. |
| `guard/src/lifecycle.py` | Per-request context: shared deadline, interrupt request, cleanup finalizer; cleanup of owned child only; parent never targeted; cleanup errors surfaced, never masking primary failure. |
| `guard/src/native_semantic_transport.py` | `NativeTransportChain(cfg, budget)` — drop-in P2 chain mirroring `ClassifierChain` result schema, delegating each classify-vote to the deterministic adapter result cache keyed by (input_hash, model_ref); no fallback; timeout/absent → fail-closed verdict None + `alarm_level`; **no network, no subprocess** in R1 component layer. Real CLI transport remains HOST_NOT_TESTED by contract. |

Integration seam: `artifact_guard.scan_artifact(..., chain_factory=NativeTransportChain)` is
already supported (function-argument injection), so the native chain can be tested by the
existing scanner pipeline without changing `artifact_guard.py`. `semantic_layer.py` remains
canonical for legacy routes; the native chain reuses its clients.

## 3. Interfaces changed

- `artifact_guard.py`: **no functional change**. Imports `open_code_transport`-style module
  only if present. Diagnostic reason mapping stays in `_p2_run` (unchanged) because the
  chain returns the existing schema.
- `semantic_layer.py`: **no source change**. Native classification requests come only
  through `NativeTransportChain` and a fake provider adapter; nothing selects it by
  CLI/env, mirroring the existing `chain_factory` convention.
- Config: no new policy surface. Budget rules and fail-closed verdicts unchanged.

## 4. Provenance and security properties (component-level)

- Parent identity: only from a trusted host/transport-supplied context object; a bare
  `session ID` string in a payload is rejected. Workspace/mount binding is part of the
  context and must match an allowlist when provided.
- Model binding: immutable snapshot (providerID + id + variant) taken at BOUND; missing
  or ambiguous provider/model → BLOCK; global default is never consulted.
- No implicit fallback: NativeTransportChain returns an explicit fail-closed alarm dict on
  any absence; it never reaches Local/Cloud classifiers.
- Correlation: adapter results are addressed by (owned child session, message id,
  request hash); an assistant reply with mismatched model binding or unknown/foreign
  (child, message) is rejected, not accepted as terminal.
- Async: queue admission is only SUBMITTED; terminal completion requires a correlated
  assistant message with finish=stop and matching model binding.
- Secrets: fixtures and logs carry only public hashes and neutral IDs; no keys, no
  prompt payload, no real parent identity.

## 5. Deferred to R2 host canary (known)

Parent trusted capability from real host invocation; actual execution model reported vs
requested; real isolation/two-model parallel chains; real interrupt completion and late
reply; real cleanup verify; real CLI subprocess deadline; exact P2 schema coverage against
live backend. Envelope and scenario numbers live in
`handoff/p2-r0-2026-10-17/R1_IMPLEMENTATION_AND_CANARY_PLAN.md`.