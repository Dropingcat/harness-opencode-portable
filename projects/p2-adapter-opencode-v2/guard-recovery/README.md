# Guard: local recovery

Task: `guard-local-recovery-20261017`.
Parent project: `p2-adapter-opencode-v2`.
Baseline: `ac037f3e496153ed6a68463505b26c9c6d850c10`.
Branch: `fix/guard-recovery`.

User-approved scope: local component repair using current repository code and
synthetic inputs only. No old sessions, external documents, credential access,
real host/model calls, policy weakening, merge, push or restart.

## Layout

- `contracts/`: scope and acceptance.
- `artifacts/`: offline test evidence; not guard admission receipts.
- `reports/`: changes, limitations and next gates.
- `runs/`: ignored runtime, temporary test files and isolated Git worktree.

The worktree is `runs/worktree`, inside the harness rather than system temp.
The source checkout and its unrelated uncommitted changes remain untouched.
Independent review, process audit and host-canary remain required. Do not mark
this candidate production-ready or manufacture other agents' verdicts.
