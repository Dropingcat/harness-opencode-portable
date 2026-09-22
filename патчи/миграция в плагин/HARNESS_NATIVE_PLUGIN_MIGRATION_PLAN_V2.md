# Harness Native Plugin Migration Plan v2

## Objective

Move from historical OpenCode-host shell to a versioned Native Plugin integration without modifying Writer/Researcher/Coder authority models.

## M0 — Freeze current boundary

- mark `tool-skill-contract-router.ts` legacy;
- forbid simultaneous legacy/native plugin activation;
- snapshot current capability/provider policy hashes;
- add boundary audit to architecture docs.

## M1 — Stable DTOs

Create shared schemas:
- HostContext/1.0
- WorkspaceRef/1.0
- SemanticExecutionRequest/1.0
- SemanticExecutionResult/1.0

No OpenCode dependency.

Acceptance:
- JSON round-trip;
- unknown-field policy;
- version rejection;
- fingerprints.

## M2 — Bridge RPC

Implement `harness-bridge-rpc/1.0`:
- full-duplex;
- correlation IDs;
- hello/health/shutdown;
- harness.run/status/cancel;
- reverse semantic.execute/cancel;
- crash and timeout classification.

Acceptance:
- TS/Python fake E2E;
- pending parent request + reverse request;
- cancellation;
- 100 concurrent messages;
- protocol major mismatch.

## M3 — HostAdapter 1.18.30

Implement OpenCode-specific adapter only in plugin package.

Inputs normalized from official PluginInput/ToolContext.
No OpenCode types cross RPC.

Acceptance:
- exact 1.18.30 source compatibility;
- live plugin tool visibility;
- host feature snapshot;
- directory/worktree normalization;
- AbortSignal propagation.

## M4 — Status-only plugin

Expose:
- harness_status

No semantic execution yet.

Replace health check semantics:
- plugin loaded;
- bridge handshake;
- core healthy;
- compatibility certified;
- legacy plugin absent.

## M5 — deterministic harness_run

Expose:
- harness_run

Run Router/Job/core deterministic path only.

Test:
- Writer route;
- Researcher route;
- Coder route;
- concurrent sessions;
- invalid mode;
- cancel.

## M6 — reverse semantic.execute

Implement plugin -> OpenCode SDK execution.

First use a generic read-only worker.
Do not start with Tribunal.

Acceptance:
- child session;
- output;
- timeout;
- auth failure;
- cancel;
- recursion isolation;
- credentials not visible to Python.

## M7 — Tribunal transport swap

Add plugin-backed provider/runtime binding.

Keep RPB/TEX/PER unchanged.

Dual provider period:
- plugin provider preferred;
- CLI provider explicit fallback;
- no silent swap.

Run production Q1/A1/Q2/A2/Advocate.

## M8 — Writer/Coder semantic convergence

Replace their direct OpenCode CLI launchers with the same generic semantic execution bridge.

Do not create role-specific transports.

## M9 — retire old shell

After two certified releases:
- disable old plugin registration;
- OPENCODE_BIN no longer required;
- OPENCODE_SESSION_DB optional;
- old direct launchers moved to `legacy/` or compatibility package;
- `shared/research-orchestration-process.md` rewritten to stop advertising direct `opencode run`.

## M10 — certification/upgrade lane

For every supported OpenCode release:
1. install host in clean fixture;
2. plugin load probe;
3. bridge health;
4. deterministic harness_run;
5. one semantic smoke;
6. Tribunal smoke;
7. package upgrade;
8. rollback.

Unknown versions:
- default DEGRADED_UNCERTIFIED;
- no production semantic provider selection until certified, unless explicit operator override.
