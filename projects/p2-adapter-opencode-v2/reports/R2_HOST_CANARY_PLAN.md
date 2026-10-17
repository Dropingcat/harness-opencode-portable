# R2 host canary plan (separate authorization required)

Task r1-p2-adapter-20261017 → R2 gate. NOT authorized by R1. Every number below is a
proposal from the R0 plan (`handoff/p2-r0-2026-10-17/R1_IMPLEMENTATION_AND_CANARY_PLAN.md`,
"Host canary" section) and the R1 contract; R2 requires explicit owner approval.

## Prerequisite (first R2 design gate)

Supply trusted current-parent capability from an actual host tool invocation. Resolve
parent metadata in that authorized context and bind to the triggering execution's
provider/model/variant. If only the session-selected model is observable while the
triggering model snapshot is ambiguous → BLOCK (or owner-approved revised binding rule).
A bare environment variable is not accepted as parent identity (R0 REQUIREMENTS_MATRIX:
`Current parent trusted identity = UNKNOWN`).

## Scenario envelope (proposal)

- Two owner-designated authorized existing parents A/B with different explicit model
  bindings. No session enumeration.
- At most two adapter-owned child sessions, one per parent; unique
  run/request/input sha256 correlation tokens.
- Three classification votes per child → at most six prompt admissions total.
  Parallel A/B chains allowed only inside this bounded canary.
- Per-prompt deadline 30 s; overall canary window 180 s; zero retries.
- Spend ceiling USD 0.50 total, enforced by a host-provided enforceable
  bound/reservation BEFORE admission. A post-hoc counter alone is not a hard ceiling;
  without an enforceable reservation the paid phase stays BLOCKED.

## Checks (must each be positive or explicit BLOCK)

1. Parent binding: child created with explicit parentID + snapshot ModelRef (providerID,
   id, variant) from the trusted parent context.
2. Model: compare requested model vs host-reported `Session.Message.Assistant.model`;
   capture expected and reported provider/model/variant; mismatch → BLOCK, no verification.
3. Isolation: A and B chains in parallel never observe each other's messages/ids; a
   message addressed to A is rejected by B's tracker.
4. Async: queue admission (Session.Inbox.User) is not a terminal result; completion
   requires correlated assistant message with finish='stop' and matching binding.
5. Cancel/late reply: interrupt only owned child; late replies after terminal are
   discarded; interrupt completion observed.
6. Cleanup: remove owned children in `finally`; verify removal via `session.get`;
   never delete a parent (delete affects descendants).
7. No fallback/recursion/credentials: adapter only; no Polza/local/global-default route;
   logs carry correlation tokens and hashes, never credentials or prompts.

## Resources created/removed

- Created: up to 2 adapter-owned child sessions (unique ids), temporary fixtures with
  synthetic data only.
- Removed: all owned children, verified removed; parent history/model/permissions
  unchanged; no third-party session read; no credentials read.

## Independent gates for R2

Worker (host-invoke bridge) → independent specialized tester → scoped reviewer →
metadata-only auditor. Same isolated worktree/branch pattern; budget/time envelope fixed
before the first host call.

## Exit

`R2_CANARY_PASSED` (all checks positive) or `R2_BLOCKED` with the specific technical
obstacle (not a generic "needs approval"), then separate authorization for real
document inputs and TD-DEV-57..61 closure.