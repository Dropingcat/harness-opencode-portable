# Development tracker reconciliation — 2026-10-14

Phase A only (HARNESS-TRACKER-20261014). No stage0 matrix, deployment, runtime activation, or TD ledger changes. All 13 DEV and seven WS IDs, titles and results are retained. Existing status vocabulary is unchanged.

## Reconciliation

- DEV-03/04 remain historical DONE explicitly scoped to OpenCode 1.18.30, as does WS-57A. Their current 2.0.29 readiness is separate, not inherited certification.
- DEV-05 is corrected from DONE/production-ready to in_progress/false, matching WS-58A. Stable DTO/bridge work (WS-56A/B) stays DONE; fake-plugin E2E and Writer agent-boundary documentation do not prove live V2 semantics.
- DEV-08 becomes in_progress: eight memory entries and retrieval exist, but automatic context injection is unwired; recurrence/admission/provenance and guard fail-open gaps remain.
- DEV-09 retains its historical calibration evidence and in_progress status. No current V2 semantic acceptance or model-driven native invocation is claimed.
- Counts recomputed from current records: DEV 3 done / 5 in_progress / 5 not_started; WS 5 / 1 / 1. Original stale counts and contradictory authority text remain only in history.

`current_readiness` separates implemented, connected, host_tested, certified with PASS/PARTIAL/NOT_TESTED/BLOCKED and an explicit scope. PASS means only the stated dimension/scope; PARTIAL means bounded evidence, not whole-item completion. The V2 native deterministic plugin is observed active only in the canonical project. Source/build tests, active-plugin observation and direct canonical Core smoke pass; model-driven native host-tool dispatch remains NOT_TESTED. Semantic transport is unported (`semantic_ready=false`). Full autonomy remains BLOCKED by external TD-RESTORE-01; no one of the 182 TD records was closed or reopened.

## Evidence and chronology

Current-readiness `external_sources` are additive source references, not tracker IDs or executable instructions. `worktree:` resolves from this worktree; `canonical:` resolves from E:/opencode_harness_portable. Internal references (`critical_path`, item `internal_refs`, DEV/WS mentions in evidence/next_gate) resolve only within this tracker. TD IDs and source paths are external, not dangling tracker IDs.

- `worktree:.runs/harness-restore-20261014/tester_live-native.json`: latest bounded active-plugin observation and direct canonical deterministic smoke; explicitly excludes model-driven invocation and semantics.
- `worktree:.runs/harness-restore-20261014/tester_live-observers.json`: bounded observer evidence, not autonomous execution acceptance.
- `worktree:.runs/harness-restore-20261014/auditor_stage.json`: earlier narrow stage approval, with then-pending V2 gates; not an override of later observations or full-autonomy certification.
- `worktree:.runs/harness-memory-check-20261014/{memory_verification,injection_verification,runtime_probe}.json`: persistence/retrieval, unwired injection, guard limitations and encoding correction. Zero API-managed instruction entries alone does not prove no injection; source inspection supplies the wiring finding.
- `canonical:handoff/harness-restore-2026-10-14/RESTORATION_STATUS.md`: supplied restoration handoff, not modified here.
- `worktree:.runs/tracker-stage0-20261014/input_guard.json`: supplied fresh P0 with failing negative control. P0 remains limited signature screening, not P2 or fail-closed safety certification; audit claims were not treated as instructions.

The complete original tracker is embedded in timestamped `history[0].snapshot`, including every evidence string, next gate, original production-ready claim and stale counts. Original byte SHA-256: `9e7303c2801a7cac72fab5718c6eed3b338352c87add7f31a283ae78a04be199`. Snapshot SHA-256: `0f5d96969a23e1766dc748f7f833d220e7f85f53cffe8bd5e07b7a201b349647` (sorted-key compact JSON, ensure_ascii=False, UTF-8). Exact original bytes also remain in `.runs/tracker-stage0-20261014/baseline/development_tracker.json`; embedded snapshot keeps complete JSON history tracked without relying on ignored run files.

## Read-only checks

`python -B scripts/tools/check_development_tracker.py` checks duplicates, all current counts, internal references, required readiness dimensions, incompatible production-ready claims and pinned historical integrity. It does not execute/validate external source reports or certify host safety. `python -B -m unittest discover -s tests/coder -p test_development_tracker.py` includes negative mutations and no-mutation verification. No model/API calls or installs are required.

### Independent-tester rework — 2026-10-15

The gate now requires the approved historical `completion_scope` verbatim for DEV-03/04/WS-57A, preventing its removal or relabeling as V2 certification. Any `certified=PASS` requires implemented/connected/host_tested all PASS, regardless of `production_ready`. An optional top-level `semantic_ready` is permitted only as literal false; positive certification is unsupported by this reconciliation. These are consistency constraints, not new runtime evidence. Tracker records, historical snapshot and independent tests are unchanged; additive external source references remain supported. No model-driven invocation or V2 semantics were tested or promoted.
