# A1 accepted: durable TraceStore evidence

Task HARNESS-ARCH-FOUNDATION-A1-20261015 — factory DONE, canonical source release verified.

Implemented: timestamp-preserving reload, visible corruption/unsupported-state errors, kernel-locked read/modify/atomic-replace operations preserving stale/concurrent writers, bounded cleanup and timeout, unsupported leaf-link/hardlink rejection, and narrow FileLease acquisition cleanup. No production trace file was opened or migrated by the tests.

Quality chain used actual specialized factory profiles, independent tests, Mode-A process audit, analyst synthesis and local LIGHT verification. Source contracts: CODERS06/09/10/13/14, with documented worktree/V2/no-push adaptations. Raw and normalized review evidence and the historical budget failure are preserved, not silently flattened into PASS.

Canonical release: eight reviewed files, 24 checks / zero skips, exact hash verification and rollback-protected deployment. Earlier blocked/rolled-back attempts are recorded separately. No TD status closed; no runtime/memory/provider activation or daemon restart.

The extra kernel check reproduces the unchanged AST method from pinned Git commit e6d3c3f0a80603e686bc59f591660a423f2d4f23 rather than relying on a missing canonical test file or importing its entire module. Release input manifest and receipts are included under evidence/ for reproducibility.

Next: A2 DamageBasket identity, transactions, idempotence and snapshot-scoped acknowledgement. Existing guard and self-learning blockers remain open. This is not full Harness/guard certification.

Closing monitor warning: liveness projected stale heartbeat (76 minutes versus 30-minute threshold). This is recorded as a separate observation, not silently treated as healthy and not proof of OS-process death. No daemon restart or HP edit was performed. The required closing sleep-cycle command was forced to simulation with no Git; its output is not evidence of real repair, learning or health recovery.
