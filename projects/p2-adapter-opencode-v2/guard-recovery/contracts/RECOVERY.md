# Local recovery contract

Authorization: current user's explicit selection of local recovery, followed by
approval of `fix/guard-recovery` and an in-harness isolated worktree.

This is not a guard-PASS, not permission to reuse blocked gathered context, and
not an exemption for normal document admission. Inputs are current source code
and synthetic fixtures only. No web, delegated output or historical session
payload is used. No delegated gate is claimed.

## Modules

1. Provider configuration: honor explicit `enabled: false` and unavailable
   transport; do not instantiate an implicit local provider when none is
   configured. Preserve documented legacy HTTP configurations with no enabled
   flag. Disabled routes never make network calls. Unknown enabled transports
   fail closed.
2. Scanner deadline: expose a finite bounded CLI timeout, reject invalid values
   and return a structured BLOCK promptly when no usable route is configured.
   Keep P0/P2 requirements, coverage, hashes and all admission criteria intact.
3. Native classifier boundary: transport completion is not classification.
   Require a correlated explicit YES/NO response, reject missing/malformed
   verdicts and request hashes, and never count a cached response three times.
   Keep real host integration disconnected until separately verified.

## Scope

Allow: `guard/src/semantic_layer.py`, `artifact_guard.py`,
`opencode_transport.py`, `native_semantic_transport.py`,
`scripts/tools/doc_guard.py`, focused tests and this task's documentation.
Task metadata may register the open recovery/integration debt through the
canonical tech_debt_cli; this does not change guard policy or acceptance.
No changes to admission policy, credentials, active plugin/config or unrelated
code. No new dependencies.

## Evidence and budget

Use unittest/pytest conventions already in the repository. Add failing
regressions before implementation, then run focused and existing guard suites.
Fixtures/fakes at the network boundary only; no real provider calls. Local
runtime files belong in `runs/`. Max two implementation rework rounds, zero
model/provider-call budget. Stop on scope expansion.

Acceptance of the component candidate requires reproducible offline results.
Independent specialized review and process audit are separate pending gates;
no self-authored report may impersonate them. Host parent binding, real model
identity, cancellation, cleanup and end-to-end P2 admission remain NOT_TESTED.
Sunset: remove recovery-only runtime files after durable evidence and commits
are preserved; retain the branch/worktree until integration is separately
authorized.
