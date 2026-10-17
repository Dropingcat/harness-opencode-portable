# R1 next stage

Task r1-p2-adapter-20261017; parent p2-r0-20261017; status target
R1_COMPONENT_VERIFIED / HOST_NOT_TESTED.

## Gates in order

1. Worker slice — DONE (committed 19afcfb on branch r1/p2-adapter-20261017; factory
   state RUNNING, attempt 1, awaiting reviewer,tester,auditor).
2. Tester — dispatched via managed CLI (code-tester-runner, explicit model
   polza/deepseek/deepseek-v4-flash-0731). Result in `runs/tester_a1.json`; only
   accepted through `factory_ctl submit tester` with CWD in the isolated worktree.
3. Reviewer — scoped delta review (contract → modules diff → test results → known
   limits). Dispatched only after tester submission; reviewer gets NO full history.
4. Auditor — process audit with metadata only (authorizations, contracts, roles,
   metrics); auditor must NOT receive code paths.
5. Rework loop bounded: max 2 real rework submissions; on divergence after 2 rounds →
   tribunal/escalation, not infinite loop.

## Exit criteria for R1_COMPLETE

- Component tests pass; reviewer APPROVE; auditor APPROVE; factory finalize.
- No guard bypass; no hidden fallback; no DEGRADED-as-PASS.
- R2_HOST_CANARY_PLAN.md final (envelope, scenarios, cleanup) with explicit budget
  enforcement requirement — but R2 execution is a SEPARATE authorization.

## Owner decisions still open

- Authorize R2 host canary (in separate approval flow).
- Parent-trusted-context bridge: host tool invocation may expose session/metadata; if
  only session-selected model is observable while the triggering model snapshot is
  ambiguous, block or approve a revised binding rule (R0 REQUIREMENTS_MATRIX: UNKNOWN).

## Handled incidents (process log)

- factory_ctl auto-commit landed in canonical worktree (90a0bef) instead of the
  isolated branch; reverted with `reset --mixed HEAD~1`, no content lost; prevention:
  run factory_ctl with CWD in the isolated worktree (see CHANGES.md).