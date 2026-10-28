# Guard local recovery candidate

Status: `OFFLINE_COMPONENT_CANDIDATE / NOT_INTEGRATED / HOST_NOT_TESTED`.
Author: code-orchestrator, direct user-authorized local recovery. No separate
worker, reviewer, tester or process-auditor role is impersonated.

## Source-grounded defects

- The bundled config explicitly disables every provider, but the old chain
  constructed cloud/fallback classifiers anyway and always added a local
  classifier. Thus an intentionally unavailable configuration triggered real
  endpoint attempts instead of immediate refusal.
- Scanner's default worker deadline is 180 seconds. Killing its outer process
  after 45/120 seconds did not establish an infinite hang. The scanner now
  exposes a caller deadline without increasing the configured bound.
- Native completion metadata was interpreted as a NO answer; cached results
  manufactured three votes and allowed input/model-only cache reuse. This is
  unsafe to connect to a real classifier.

## Changes

1. Disabled and unavailable providers are never constructed. Missing provider
   entries do not create implicit localhost routes. Explicit legacy HTTP
   entries may still omit enabled/transport. Unsupported enabled transports
   fail closed, not through an HTTP fallback.
2. No configured route produces immediate `BLOCK / p2_not_configured`, with
   P0 only executed and incomplete coverage. Preflight exposes configured
   routes but remains READINESS, never admission or availability proof.
3. `scan --timeout SECONDS` only tightens the configured
   `security.timeout_sec` deadline (global maximum 180 seconds). Invalid values
   return structured BLOCK. Owned worker cleanup remains required on timeout.
4. Native classification requires `ClassificationReply`: explicit strict
   YES/NO plus HostMessage provenance. Completion alone and absent request
   hashes are refused. YES remains YES. Distinct message IDs are required;
   one reply cannot be reused for several votes.
5. The component callback now takes `(chunk, snapshot, vote_index)`. Each
   chunk invocation receives a unique component-only request id. These are
   not real host sessions; no claim of trusted parent provenance is made.

## Verification

- Existing guard suite before changes: 28 tests passed.
- Red regressions: 32 failed outcomes, 3 passed, 1 subtest passed. Pytest counts
  both test and subtest failures; do not interpret this as 32 distinct bugs.
- Initial green: 47 tests and 32 subtests passed.
- Expanded regression: 53 tests and 37 subtests passed.
- JUnit evidence: `../artifacts/{baseline,red,green,regression}.xml`.
- Raw JUnit failure output is retained byte-for-byte; task-local attributes
  exempt only generated `artifacts/*.xml` from whitespace lint, not source code.
- Full repository/release suites and independent specialized gates were not run.
- No real host/model/provider calls, credentials or external inputs used.

## Unchanged boundaries

Admission policy, bundled unavailable configuration, active plugin and main
checkout guard are unchanged. P2 coverage and identity checks are not relaxed.
Fixture PASS reports carry `testing_only_not_host_certification`; they are not
authorization receipts. The native chain is still not production-wired.

## Rollback

This is a local checkpoint only. Warning-only W1 hooks are skipped through
their supported `W1_SKIP_HOOKS=1` switch for this commit, to avoid their automatic
session-history import outside the approved local-input scope. This does not
skip or satisfy an independent gate, guard admission or release acceptance.

Do not merge this candidate until independent gates pass. Leaving or reverting
the isolated checkpoint does not change the running/main harness. Never remove
its worktree until commits and durable task evidence are verified.
