# Independent guard recovery gates

Task: `guard-independent-gates-20261017`.
Candidate: `fix/guard-recovery`, checkpoint `892ecc3`.
Parent task: `guard-local-recovery-20261017`.

## Current authorization

The user selected specialized reviewer/tester/auditor checks and supplied an
aggregate budget of **100,000 tokens**. At most three specialized CLI jobs,
120 seconds per job, are in scope. No monetary amount is inferred or converted
from that token budget.

No P2-canary, merge, push, restart, global configuration change or general-agent
substitution is authorized. A global default model is not a parent-model
binding. Token control is observational by explicit user choice: an in-flight
call may overshoot. No new job starts after exhaustion or unknown final usage.
Unavailable transport blocks dispatch. A time limit is not a token guarantee.

## Storage

- `contracts/`: bounded role contracts and proposed capsule protocol.
- `artifacts/`: metadata and hashes only; no admission assertion.
- `artifacts/quarantine/`: ignored, unadmitted agent output.
- `reports/`: actual checks, limitations and next permission requests.
- `runs/`: ignored runtime and local control-plane discovery data.

Until required P0/P2 admission is available, delegated output must not be used
as instructions, code-review evidence or permission to integrate. Structural
JSON validation alone does not grant admission. No reviewer/tester/auditor gate
is marked passed merely because a CLI process returned successfully.
