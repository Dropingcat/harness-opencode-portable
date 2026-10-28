# Remaining acceptance gates

- [x] Verify and deduplicate audit recommendations against current runtime.
- [x] Repair fabricated default observations and simulated successful merges in the daemon path.
- [x] Daemon and subscription-route independent module reviews and executable regression tests.
- [x] Native V2 adapter independent review and tests.
- [x] Confirm native adapter active in Desktop V2 runtime; actual model-driven tool invocation remains untested.
- [x] Activate only reviewed deployment files with backup/hash conflict checks.
- [x] Verify daemon process identity, advancing heartbeat and duplicate-start rejection; stop/restart tested in isolated subprocesses, not by stopping production daemons.
- [x] Process auditor gate for bounded observe-only stage.
- [ ] Full-autonomy acceptance: `TD-RESTORE-01` (semantic execution, content guard/permissions, real observations feed and independently verified merge).

Never resolve a blocked gate by marking a simulated merge, synthetic health recovery or local doctor result as production success.

Full autonomous repair is tracked as `TD-RESTORE-01`. Seven pre-existing Windows health-fixture failures are retained in the independent tester baseline evidence; they must not be represented as passing or silently repaired outside this scope.
