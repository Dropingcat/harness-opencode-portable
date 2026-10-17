# R1 baseline and allowed scope

Task r1-p2-adapter-20261017. Isolated worktree: `C:/Temp/opencode/r1-p2-adapter`
(branch `r1/p2-adapter-20261017`), created from harness HEAD. Task-owned run state:
`.runs/r1-p2-adapter-20261017/factory_state.json` (ignored, not committed).

## Baselines

- Harness root: E:/opencode_harness_portable (git worktree at branch feature/b1-t2-core-config, HEAD fd4c39b8f128dbf99883ea7a9f8cd73490e9dd64).
- R1 worktree HEAD: fd4c39b8f128dbf99883ea7a9f8cd73490e9dd64 (clean at creation).
- R0 package manifest: handoff/p2-r0-2026-10-17/MANIFEST.json — task p2-r0-20261017,
  parent p2-opencode-adapter-20261017, host 2.0.29, files verified by orchestrator.
- OpenAPI authority: handoff/p2-r0-2026-10-17/evidence/openapi-managed.json (sha256 in R0 manifest files list; on-disk identity).
- Guard sources at baseline: guard/src/{artifact_guard,semantic_layer,session_guard}.py,
  guard/src/guard_config.json (bundled default), scripts/tools/doc_guard.py.

## Host/tool identities (from R0, not re-verified here)

- Desktop/CLI/server: 2.0.29; CLI `api` managed auth works; explicit-server auth refused without password.
- Canonical deterministic plugin (E:/.../dist-v2/v2/index.js) observed in canonical Location only.
- No worktree implementation changes to those artifacts.

## Allowed write scope (allowlist)

- New: guard/src/opencode_transport.py, guard/src/execution_tracker.py,
  guard/src/lifecycle.py, guard/src/native_semantic_transport.py,
  tests/coder/test_guard_native_transport_stage1.py.
- Handoff package: handoff/p2-r1-2026-10-17/* (docs + evidence JSON).
- Factory state (ignored): .runs/r1-p2-adapter-20261017/*.
- Any additional file requires scope revision per R1 contract section 13.

## Excluded (forbidden)

- Changes to active canonical build, user OpenCode config, global agent dirs.
- Real host sessions/prompts/model backend calls; paid canary; real documents.
- Credential extraction/copy/logging; POLZA_API_KEY or provider keys in fixtures/logs.
- Loosening P2, coverage, guard threshold or DEGRADED policy.
- Dependency install/update without separate approval.
- push/merge/restart/autonomy/background production processes.
- Global default as implicit fallback; Polza/local implicit route.

## Budget / limits recorded before any role calls

- Component tests: offline only, zero paid calls; harness budget=0 enforced by factory state.
- Rework limit: 2 real rework submissions without convergence → escalation (R1 contract §12).
- No host LLM calls are authorized; no per-call budget exists for R1.

## Role-dispatch envelope (fixed before first role call)

- Transport: managed CLI primary runner — `opencode-cli run --agent <role>-runner` against
  the existing background service (host-managed auth), executed in the isolated worktree
  directory. One child session per role dispatch; no `--auto`, no `--standalone`, no flags
  beyond `--agent`/`--model`.
- Model: `polza/deepseek/deepseek-v4-flash-0731` (parent-session equivalent provider/model),
  explicitly passed via `--model`; no dependence on global default resolution.
- Budget: at most 6 role dispatches total (worker + tester + reviewer + up to 2 rework
  submissions + auditor); per-dispatch timeout 600 s; no retries on transport failure —
  the failing gate is recorded BLOCKED, never substituted with `general`.
- Cost: no per-token price available for the chosen model from the runtime catalog; the
  envelope above is the enforced bound (dispatch count + timeout), consistent with
  R1 contract §3 authorization for specialized reviewers.

## Artifact/report storage convention (owner rule, applies from now on)

All artifacts, reports, evidence and handoff outputs for factory subprojects are stored
in ONE of two canonical places, never scattered:

1. Factory-run folder of the subproject: `E:/opencode_harness_portable/.runs/<task_id>/`
   — the task-owned run directory (factory_state.json, evidence, reports, manifests).
2. Harness temp: `C:/Temp/opencode/<task_id>/` — approved external temp root for
   repro/intermediate artifacts, isolated worktrees, and scratch.

The isolated worktree `C:/Temp/opencode/r1-p2-adapter` (branch `r1/p2-adapter-20261017`)
is the R1 subproject carrier: its `runs/` mirror holds role-output JSONs and its
`handoff/p2-r1-2026-10-17/` holds the human-readable report package. Canonical
`E:/opencode_harness_portable/.runs/r1-p2-adapter-20261017/` gets replicated pointers
(MANIFEST + status JSONs). Do not place new artifacts anywhere else; if a report is
generated in the canonical worktree, mirror it, do not leave it half-placed.
- Model: `polza/deepseek/deepseek-v4-flash-0731` (parent-session equivalent provider/model),
  explicitly passed via `--model`; no dependence on global default resolution.
- Budget: at most 6 role dispatches total (worker + tester + reviewer + up to 2 rework
  submissions + auditor); per-dispatch timeout 600 s; no retries on transport failure —
  the failing gate is recorded BLOCKED, never substituted with `general`.
- Cost: no per-token price available for the chosen model from the runtime catalog; the
  envelope above is the enforced bound (dispatch count + timeout), consistent with
  R1 contract §3 authorization for specialized reviewers.