# Next gates

1. Independently review the five changed source files plus two new test files.
   Review scope: provider disabling, explicit routing, deadline bounds, native
   response parsing/correlation/replay and unchanged admission requirements.
   Comments must have file/line evidence and falsification. No policy weakening.
2. A specialized tester independently reproduces the offline regression suite.
   Fixtures must never contact live endpoints. Process auditor receives only
   authorization/scope/budget/role/evidence metadata, not a code-review task.
   These gates are PENDING; no fabricated role output is submitted to factory.
3. After separate approval, integrate this checkpoint into the canonical
   harness. Do not merge the R1 branch wholesale: it has separate unverified
   work and this patch changes the component callback contract.
4. Complete the real OpenCode P2 boundary under the existing adapter debt:
   trusted current-parent context, actual model evidence, prompt/result polling,
   cost accounting, cancellation and owned-child cleanup. Structural DTOs and
   component-generated session ids do not establish these properties.
5. Separately authorize synthetic real-host canary. Require real response
   classification, coverage, concurrent model isolation, timeout/cancel,
   cleanup and no hidden provider/model fallback. Never use preflight or a
   fixture PASS as host acceptance.
6. Only after a real authorized P2 route passes, resume the blocked branch
   integration audit. No real documents, push, merge or restart authorized by
   this local recovery task.

Runtime state: `../runs/factory_state.json` in the isolated worktree. Default
reviewer/tester/auditor gates remain pending; there is no factory DONE claim.
