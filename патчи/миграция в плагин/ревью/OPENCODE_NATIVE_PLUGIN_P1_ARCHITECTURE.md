# OpenCode Native Plugin P1 — Architecture and boundary

Status: IMPLEMENTED / HOSTLESS ACCEPTANCE PASS / LIVE HOST CERTIFICATION PENDING
Date: 2026-09-14

## 1. Why this integration exists

The historical Harness assumed OpenCode Desktop was the host that called Harness scripts/tools. R4.4 introduced the opposite direction as well: Harness may need its host to execute a bounded semantic worker while a Job is still active. A separate CLI is not a valid universal Desktop assumption.

P1 replaces that assumption with an official OpenCode native-plugin boundary.

## 2. OpenCode recommendations followed

The implementation follows the public OpenCode plugin/custom-tool model:

- local plugins may be loaded from `.opencode/plugins/` or the global config plugin directory;
- npm plugins are a future packaging route;
- custom plugin tools are registered through the OpenCode plugin `tool` map and `tool()` helper;
- plugin context supplies SDK client + project/directory/worktree;
- custom-tool context supplies session/message/agent/directory/worktree and cancellation signal;
- plugin logging uses `client.app.log()` rather than console logging;
- host sessions remain owned by OpenCode SDK/server APIs.

Primary upstream references:
- https://opencode.ai/docs/plugins/
- https://opencode.ai/docs/custom-tools/
- https://opencode.ai/docs/sdk/
- https://github.com/anomalyco/opencode/blob/v1.18.30/packages/plugin/src/index.ts
- https://github.com/anomalyco/opencode/blob/v1.18.30/packages/plugin/src/tool.ts

## 3. Authority split

```text
OpenCode Host
  provider auth
  model execution
  host sessions
  UI
  host permissions
        |
        v
@harness/opencode-plugin
  HostAdapter
  context normalization
  plugin lifecycle
  bridge transport
        |
        v
harness-bridge-rpc/1.0
        |
        v
Harness Core
  Router
  Job/Attempt
  Writer
  Researcher
  Coder
  Tribunal
  Claim/Evidence/Hypothesis
  validation/admission/provenance
```

Plugin never decides route, Claim truth, Tribunal composition, evidence visibility or Coder/Writer authoritative state.

## 4. Stable DTO boundary

P1 introduces:

- `HostContext/1.0`
- `WorkspaceRef/1.0`
- `SemanticExecutionRequest/1.0`
- `SemanticExecutionResult/1.0`

OpenCode SDK objects are normalized immediately at the plugin edge. They are never persisted as Core state.

## 5. Bridge

Transport: line-delimited JSON-RPC over child-process stdin/stdout.

Protocol: `harness-bridge-rpc/1.0`.

Properties:
- request/response correlation IDs;
- concurrent requests;
- reverse requests from Python to plugin while a parent plugin request is pending;
- no TCP port/discovery/firewall dependency;
- Python daemon lifetime owned by plugin lifecycle.

P1 methods:
- `bridge.hello`
- `harness.status`
- `harness.run`
- `bridge.reverse_echo_test` (acceptance only)
- `bridge.shutdown`

Reserved reverse method:
- `semantic.execute`

## 6. OpenCode-visible tool surface

Only:
- `harness_status`
- `harness_run`

This is intentional. OpenCode must not choose internal specialist roles or implementation stages directly.

`harness_run` currently performs authoritative deterministic routing and returns the execution bundle. It does not yet turn on production child semantic sessions. That switch is delayed until live plugin certification.

## 7. Semantic reverse adapter

The plugin already contains the generic `semantic.execute` host adapter shape using OpenCode SDK session create/prompt semantics. It is **disabled by default**.

Reason: exact OpenCode/model behavior must be tested live before RPB selects the plugin provider. This prevents a fake-host unit test from silently becoming proof of production semantic readiness.

## 8. Legacy coexistence

`plugins/tool-skill-contract-router.ts` is legacy/deprecated.

Rules:
- do not load it together with the native plugin;
- keep it for rollback/migration evidence for now;
- direct CLI launchers remain explicit fallback during one deprecation cycle;
- `OPENCODE_BIN` is optional, not required in native mode;
- `OPENCODE_SESSION_DB` is optional diagnostics/forensics, not a correctness dependency.

## 9. P1 acceptance

Hostless:
- Python contracts and bridge tests;
- JS bridge peer test;
- fake OpenCode PluginInput/ToolContext test;
- project/global installer test;
- doctor;
- Writer/Researcher/Coder regression;
- runtime/capability compiler hash stability.

Live P2 (pending on user's OpenCode):
- plugin load;
- tools visible;
- `harness_status` returns host version/context;
- `harness_run` returns deterministic route;
- legacy loader absent;
- no CLI/session-DB requirement;
- then one explicit read-only semantic smoke before Tribunal migration.


## 10. Exact v1.18.30 SDK call-shape hardening

The v1.18.30 generated SDK uses flattened method parameters rather than raw HTTP `{query, body}` wrappers. P1 host-adapter tests explicitly lock this boundary:

- `client.app.log({service, level, message, extra})`;
- `client.session.create({directory, workspace, parentID, title, agent, model})`;
- `client.session.prompt({sessionID, directory, workspace, model, agent, format, parts, ...})`.

This fixture exists because fake SDK objects that accept arbitrary JavaScript objects can otherwise hide a host integration mismatch until Desktop runtime.
