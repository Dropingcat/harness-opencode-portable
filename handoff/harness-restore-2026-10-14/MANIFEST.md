# Harness restoration handoff

- Task: `HARNESS-RESTORE-20261014`
- Accepting repository: current `clever-squid` worktree.
- Baseline commit: `dc83907` (disabled Desktop configuration retained).
- Contract: `docs/HARNESS_RESTORE_20261014.md`.
- Controller state and evidence: `.runs/harness-restore-20261014/` (ignored runtime data, retained locally).
- Deployment: `E:\opencode_harness_portable`; unrelated dirty changes must be preserved.
- Configuration and meta-state backups: `.runs/harness-restore-20261014/backups/` (private; do not publish).

No full-restoration or autonomous-merge acceptance is implied by this manifest. Consult TASKS and factory status for remaining gates.

Final component-level result: `RESTORATION_STATUS.md`. Native adapter is active and observer daemons are running; full autonomous repair is explicitly blocked.
