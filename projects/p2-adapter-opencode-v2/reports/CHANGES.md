# R1 changes log

Task r1-p2-adapter-20261017; base fd4c39b8f128dbf99883ea7a9f8cd73490e9dd64;
isolated worktree C:/Temp/opencode/r1-p2-adapter (branch r1/p2-adapter-20261017).

## Implementation (worker slice)

- guard/src/opencode_transport.py — provenance-typed DTOs (ModelRef, ParentContext,
  RequestSnapshot, HostMessage), strict CLI-JSON decoders, Clock abstraction,
  KNOWN_HOST_VERSIONS. Stdlib only.
- guard/src/execution_tracker.py — atomic per-request state machine
  NEW→BOUND→SUBMITTED→WAITING→COMPLETED/FAILED/TIMED_OUT/CANCELLED with correlation
  and late-reply refusal (threading.Lock).
- guard/src/lifecycle.py — RequestLifecycle: deadline, wait_for_terminal polling,
  timeout/cancel/finish, cleanup descriptor for owned child only.
- guard/src/native_semantic_transport.py — NativeAdapter + NativeTransportChain
  producing the existing P2 chain schema; fail-closed on missing parent/model; NO
  fallback to Local/Cloud; result cache keyed by (sha256, model); no env reads.

## Factory / process

- Factory state machine initialized: C:/.../r1-p2-adapter/.runs/r1-p2-adapter-20261017/
  factory_state.json; gates reviewer,tester,auditor; attempt_limit=2; budget=0
  (offline component scope).
- Worker submission accepted (native_semantic_transport, attempt=1, rework_rounds=0).
- Tester dispatched via managed CLI runner (code-tester-runner), model
  polza/deepseek/deepseek-v4-flash-0731 (explicit). Result pending in this package.

## Incident: erroneous auto-commit by factory_ctl

- `factory_ctl submit worker` (run from harness canonical worktree CWD) triggered its
  built-in `_git_snapshot` and committed ALL untracked task-owned docs/handoffs from the
  PREVIOUS tasks (R0/dispatch/localization etc.) into a commit
  `90a0bef factory: r1-p2-adapter-20261017 native_semantic_transport` on the canonical
  worktree — NOT the isolated task branch. No code was touched; commit contained only
  untracked handoff/docs files.
- Corrective action (read-only-safe): `git reset --mixed HEAD~1` restored HEAD to
  fd4c39b and returned files to untracked; no file content lost; no tag referenced the
  commit; no foreign modifications were present in the diff (verified via diff-tree filter).
- Prevention: subsequent `factory_ctl` runs are executed with CWD set to the isolated
  task worktree, so the snapshot commit lands on branch r1/p2-adapter-20261017 and the
  canonical worktree stays untouched. If factory_ctl is invoked without explicit CWD
  again, its snapshot will be reverted the same way.

## Proofs captured

- evidence/dispatch-worker-a1.txt, evidence/dispatch-worker-a1-fix.txt (managed CLI
  transcripts; no credentials in them).