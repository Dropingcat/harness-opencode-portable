# DEV-05 / Coder M2 — closure and next gate

## Accepted scope

Factory task: `DEV05-CODER-CONV-M2`, module `coder_router_wiring`.
Worker commit: `a2be335`. Attempt 1, rework rounds 0.
Reviewer PASS, tester PASS, process auditor PASS; controller finalized DONE.

This closes only the router's connection to the M1 contract adapter. It does
not close DEV-05, TD-062, or certify a production Coder execution channel.

## Evidence

- `reviewer_coder_router_wiring.json`: APPROVE after the reviewer reconciled
  severity/verdict and repaired report format. R3 is covered by independent tests.
- `tester_coder_router_wiring.json`: PASS, 32 unittest; reported coverage 85%.
- `auditor_coder_router_wiring.json`: process-only APPROVE with scope limitations.
- Orchestrator rerun: `python -m unittest discover -s tests/coder -v` — 32 OK.
- No real OpenCode process or model is invoked by these tests.
- Factory cost counter is 0/20 RUB; actual API cost was not measured.

## Interrupted work recovered

The tester's earlier DNS failure was an infrastructure interruption, not a failing
test. Retried testing succeeded. The refreshed reviewer JSON initially failed
contract validation; its author repaired it before controller submission.
All submissions to the shared factory state were sequential.

## Production blockers retained for M3

1. A response label `opencode_cli_legacy` is not prior operator authorization.
   If plugin transport was selected, an adapter import failure must fail closed,
   not invoke CLI. CLI remains a separately selected compatibility path.
2. M1 has no connected reverse RPC channel: it returns HOST_UNAVAILABLE rather
   than claiming model execution. A file/environment presence check proves no
   live channel readiness.
3. Split an exact `provider/model` identifier at the first slash; passing the
   whole string as model_id is not a complete model policy.
4. Supply actual host/session identity; `cli`, `reverse`, and `unknown` are not
   evidence of a real parent/child session relation.
5. Prove permission enforcement, cancellation, schema validation and result
   correlation before enabling write-capable execution. `tools: {}` alone is
   not evidence of a deny-all host policy.

## Next contract / acceptance

M3a: explicit transport argument, no fallback on plugin failure, split model ID,
negative tests that assert subprocess is never called on the selected plugin path.

M3b: connect Core inside the owning bridge process to reverse semantic RPC;
test TS/Python round-trip with a fake host separately from live-model acceptance.
Do not add a second server, bypass factory gates, or change Claim/TEX authority.

Writer convergence and optional OpenCode orchestrator agent packaging remain
subsequent tasks. Registering UX agents must not imply that Core orchestration,
memory, skills, or cross-agent dispatch are already fully connected.
