# Harness ↔ OpenCode Interface Control — Current Canonical Boundary

Status: CURRENT DESIGN CONTROL, 2026-09-14

Этот документ определяет, что разрешено пересекать границу Core↔OpenCode. Он должен переживать обновления OpenCode без изменений Writer/Researcher/Coder contracts.



The Harness core is already substantially separable from OpenCode. The dangerous coupling is concentrated in the historical host-integration shell, not in the main Researcher/Writer/Coder state models.

The correct target is:

```text
Harness Core
    knows:
      HostContext
      SemanticExecutionRequest
      SemanticExecutionResult
      cancellation
      normalized capability snapshot

    does NOT know:
      OpenCode CLI syntax
      Electron/Desktop IPC
      OpenCode DB path
      OpenCode hook object shapes
      npm/Bun layout
      OpenCode private runtime objects

OpenCode Plugin
    knows:
      exact OpenCode SDK/plugin API
      session/message/agent IDs
      directory/worktree
      child session execution
      provider/model runtime
      AbortSignal
      OpenCode version/features

    does NOT own:
      routing truth
      Job/Attempt authority
      Claim/Evidence/Hypothesis state
      Tribunal composition
      admission
      Writer/Coder/Researcher semantics
```

This is the anti-corruption boundary that lets OpenCode update independently.

---

# 1. Current outward surfaces of Harness

## 1.1 Router / capability runtime

Canonical code:
- `scripts/router/resolve_route.py`
- `scripts/router/resolve_bundle.py`
- `scripts/router/capability_preflight.py`
- `scripts/router/compile_runtime.py`
- `scripts/router/compile_capability_runtime.py`
- `config/runtime_snapshot.json`
- `config/capability_runtime_snapshot.json`

Current public semantic:
- input: task text + optional route/stage/profile + capability preflight;
- output: deterministic route/bundle with:
  - route;
  - stage;
  - skills;
  - logical tools;
  - required/optional/forbidden capabilities;
  - selected provider IDs;
  - policy hashes;
  - readiness state.

Authority:
- CORE.

Plugin requirement:
- NONE for routing decisions.
- Plugin may supply normalized host capability facts.
- Plugin must never select route/stage/provider itself.

Stable plugin-facing operation:

```text
harness.run(request, mode?, host_context)
    -> Router
    -> Bundle
```

Risk if ignored:
If plugin starts mapping "research" to agents directly, it creates a second router and bypasses capability policy.

---

## 1.2 Job / Attempt runtime

Canonical:
- `scripts/jobs/job_ctl.py`

Current state:
- event-sourced JSON state;
- attempts;
- children;
- artifacts;
- stages;
- gates;
- reconciliation;
- completion.

Authority:
- CORE.

Plugin must provide only external correlation:

```text
host_session_id
host_message_id
host_execution_id
```

These are metadata/external refs, never Job IDs.

Required mapping:

```text
OpenCode session  != Harness Job
OpenCode message  != Harness Attempt
OpenCode child session != Harness Child Job
```

Recommended normalized link:

```json
{
  "host_ref": {
    "host": "opencode",
    "session_id": "...",
    "message_id": "...",
    "execution_id": "..."
  }
}
```

Cancellation:
OpenCode AbortSignal -> bridge cancel -> Job/Attempt runtime.
Runtime CANCELLED/TIMED_OUT must remain distinct from scientific OPEN.

---

## 1.3 Writer

Canonical public facade:
- `scripts/writer/cli.py`

Core commands:
- plan
- draftcheck
- live-cycle
- extract
- graphs
- annotate
- consolidate
- vectorsim
- dom
- review
- uncertainty
- register

Compatibility/module commands also expose:
- verify-claims
- draft-loop
- citation-trace
- research-adapt
- release-check
- object/reference/evidence operations
- provenance/state/invalidation operations.

Authority:
- Writer DOM/state, provenance, RTT, repair, validation are CORE.

Current semantic-host leakage:
- `agent.writer`;
- `scripts/writer/drafting/agent_dispatch.py`;
- `agents/article-writer.md`;
- older orchestration assumes OpenCode agent files.

Target:
Writer must request semantic prose via generic core request:

```text
SemanticExecutionRequest
  purpose = WRITER_DRAFT | WRITER_REPAIR | WRITER_REVIEW
  contract_ref
  bounded_context
  output_schema
  permission_profile
```

Plugin knows nothing about Writer DOM internals.

Do NOT create OpenCode tools:
- `writer_draft_internal`
- `writer_repair_internal`
- etc.

User-facing model sees only `harness_run`; Harness decides Writer path.

---

## 1.4 Researcher core

Canonical:
- `scripts/researcher/`
- `scripts/researcher/researcher_core/`
- `scripts/researcher/verify_claims.py`

Core owns:
- Claim/Evidence;
- ResearchDOM;
- Relation/Uncertainty;
- ReviewWorkField;
- Tribunal composition;
- Dialectic;
- Gap/ResearchChallenge;
- ArgumentGraph;
- provider binding;
- grounding;
- admission.

Authority:
- CORE.

Plugin has no right to:
- assign specialists;
- widen evidence slices;
- choose questions;
- resolve issues;
- mutate graph/truth.

Plugin only executes bounded semantic work.

This boundary is already strong because:

```text
TribunalProviderTransport
    invoke(binding, envelope, timeout)
```

is a transport protocol, and:

```text
LogicalToolProviderTransport
```

already forwards only:
- selected runtime tool;
- selected provider;
- bounded TEX.

Therefore new OpenCode plugin transport can be inserted without changing DQC/TEX/PER/ArgumentGraph.

---

## 1.5 Tribunal / live semantic execution

Canonical:
- `tribunal_provider_binding.py`
- `tribunal_live_dialogue.py`
- `tribunal_dialectic.py`

Current core contracts:
- RPB
- DQC / ADC / IQC
- TEX
- PER
- IQT
- ARG

Current transport:
- `LogicalToolProviderTransport`
- `SubprocessJsonProviderTransport`
- legacy runtime binding `tribunal_role -> mcp/launchers/opencode_tribunal_role.py`
- legacy launcher eventually calls `opencode run`.

Target replacement:

```text
RPB/TEX
  -> LogicalToolProviderTransport
  -> plugin-backed logical runtime
  -> semantic.execute bridge RPC
  -> OpenCode SDK child session
  -> SemanticExecutionResult
  -> PER
```

Important:
No Tribunal contract needs an OpenCode-specific version.

Only runtime binding/provider policy changes.

---

## 1.6 Coder / code-factory

Canonical:
- `scripts/code-factory/factory_ctl.py`
- `scripts/run_coder_acceptance.py`

Core owns:
- task/factory state;
- worker/reviewer/tester/auditor stages;
- artifact provenance;
- guard state;
- budgets;
- convergence;
- finalization.

Current host leakage:
- `mcp/coder_router_server.py` invokes `opencode run`;
- `mcp/launchers/opencode_code_worker.py` invokes shared `_runner.py`;
- model IDs are embedded in launcher layer.

Target:

```text
Coder Core
  -> SemanticExecutionRequest
       purpose = CODE_WORK | CODE_REVIEW | CODE_TEST_ANALYSIS
       workspace_ref
       bounded instructions
       permission profile
  -> plugin semantic executor
```

Critical normalized host input:
- `directory`;
- `worktree`.

But plugin does not authorize workspace. Core policy validates the normalized WorkspaceRef.

Never fall back to process cwd.

---

## 1.7 MCP / capsules

Current:
- MCP servers for coder/search/document;
- local deterministic capsules;
- capability/provider registry.

Decision:
Do not absorb all MCP/capsules into OpenCode plugin.

Why:
- they are Harness capabilities;
- some are deterministic;
- some may be used headlessly without OpenCode;
- plugin should not duplicate provider policy.

Target:
Plugin exposes Harness as one integration surface.
Harness may internally use MCP/capsules through its capability runtime.

OpenCode-native MCP can remain available to OpenCode for unrelated user workflows, but it is not an authority path for Harness unless admitted by Harness provider policy.

---

## 1.8 Guard / session security

Current historical coupling:
- `OPENCODE_SESSION_DB`;
- `guard/src/session_guard.py`;
- old plugin tries post-tool scanning;
- `health_check.py` expects DB path.

This is a fragile host-private dependency.

Target:
Correctness must not require reading OpenCode's SQLite DB.

New order:

```text
typed tool/semantic result
  -> Harness guard/admission
  -> provenance
```

OpenCode session DB scan may remain:
- OPTIONAL;
- diagnostics/forensics;
- defense-in-depth;
- never required for normal plugin readiness.

New plugin provides normalized:
- session ID;
- message ID;
- host events if available;
- tool/result metadata if needed.

No core module should know where OpenCode stores SQLite.

---

## 1.9 Agents / skills / shared markdown

Current:
- `agents/*.md`
- `skills/opencode-current`
- `shared/*.md`
- some docs still reference `.opencode/...`
- old research orchestration directly documents `opencode run --agent`.

Classification:
- useful content/persona/reference pack;
- NOT stable machine protocol.

Migration:
- user-facing OpenCode agents may remain optional packaging;
- internal Tribunal/Writer/Coder semantic roles must be generated from Harness Role/ExecutionProfile contracts;
- do not make core correctness depend on a file being auto-discovered as an OpenCode agent.

---

# 2. Historical host shell that must leave the authority path

## RED-1 legacy plugin

`plugins/tool-skill-contract-router.ts`

Action:
- DEPRECATED;
- never load simultaneously with Native Harness Plugin;
- preserve policy data, not hook implementation.

## RED-2 runtime integration policy v1

`config/runtime_integration_policy.json`

Problems:
- hardcoded legacy plugin path;
- requires `OPENCODE_BIN`;
- treats old plugin as mandatory;
- health semantics tied to old runtime.

Replace with:
`config/host_integration_policy.json` schema `harness-host-integration/2.0`.

## RED-3 plugin registration script

`scripts/register_plugin.py`

Problems:
- hardcoded personal Windows path;
- rewrites JSONC;
- tied to legacy plugin.

Replace with installer/package registration.

## RED-4 setup_env OPENCODE_BIN

`scripts/setup_env.ps1/.sh`

`OPENCODE_BIN` becomes optional legacy CLI-provider config, not base Harness requirement.

## RED-5 direct CLI semantic launchers

- `mcp/launchers/_runner.py`
- `mcp/launchers/opencode_code_worker.py`
- `mcp/launchers/opencode_research_*`
- `mcp/coder_router_server.py`
- `mcp/launchers/opencode_tribunal_role.py`

Keep temporarily as:
`transport=opencode_cli_legacy`.

Do not delete before plugin semantic E2E passes.

## RED-6 health_check old assumptions

`scripts/health_check.py`

Replace old:
- legacy plugin registered;
- DB accessible.

With:
- plugin loaded runtime probe;
- bridge handshake;
- core health;
- protocol compatibility;
- host feature snapshot;
- semantic provider readiness.

---

# 3. Stable interface the plugin should see

The plugin should see exactly one normalized Core API family.

## 3.1 HostContext/1.0

```json
{
  "schema": "host-context/1.0",
  "host": "opencode",
  "host_version": "1.18.30",
  "plugin_version": "0.1.0",
  "session_id": "ses...",
  "message_id": "msg...",
  "agent_id": "build",
  "directory": "C:/project",
  "worktree": "C:/project",
  "project_ref": "...",
  "features_fingerprint": "sha256:..."
}
```

No raw OpenCode SDK object crosses RPC.

## 3.2 WorkspaceRef/1.0

```json
{
  "schema": "workspace-ref/1.0",
  "kind": "local",
  "directory": "...",
  "worktree": "...",
  "readonly": false,
  "identity": "sha256:..."
}
```

Core validates it.

## 3.3 harness.run

Plugin -> Core.

```text
request
mode?
host_context
workspace_ref
resume_token?
```

Output is a Harness result envelope, not an OpenCode message object.

## 3.4 semantic.execute

Core -> Plugin.

Generic request for all modules:

```json
{
  "schema": "semantic-execution-request/1.0",
  "execution_id": "...",
  "purpose": "TRIBUNAL_ROLE",
  "contract_schema": "TEX/...",
  "role_ref": "...",
  "parent_host_session_id": "...",
  "bounded_input": {},
  "expected_output": {},
  "model_policy": {},
  "permission_profile": "semantic-worker-readonly",
  "timeout_ms": 180000,
  "trace": {}
}
```

Purpose values initially:
- TRIBUNAL_ROLE
- WRITER_DRAFT
- WRITER_REPAIR
- CODE_WORK
- CODE_REVIEW

Plugin maps purpose/profile into OpenCode runtime details.

Core never calls `client.session.prompt()` directly.

## 3.5 SemanticExecutionResult/1.0

```json
{
  "schema": "semantic-execution-result/1.0",
  "execution_id": "...",
  "runtime_status": "COMPLETED",
  "host_session_id": "...",
  "provider_id": "...",
  "model_id": "...",
  "structured_output": {},
  "raw_output_ref": null,
  "usage": {},
  "timing": {},
  "host_error": null,
  "host_features_fingerprint": "sha256:..."
}
```

Runtime status:
- COMPLETED
- FAILED
- TIMED_OUT
- CANCELLED
- REJECTED_BY_HOST
- AUTH_REQUIRED
- HOST_UNAVAILABLE

Epistemic statuses do NOT belong here.

---

# 4. What the plugin expects from Harness Core

At bridge startup:

1. protocol negotiation;
2. core version/commit;
3. core schema range;
4. policy hashes;
5. supported semantic purposes;
6. core health;
7. run root;
8. cancellation support;
9. no request for provider credentials.

At runtime:

- deterministic request IDs;
- bounded payloads;
- explicit timeout;
- explicit expected-output schema;
- explicit permission profile;
- no hidden request for arbitrary host tools;
- no OpenCode-specific Python imports.

---

# 5. What Harness Core expects from plugin

Minimum certified host capabilities:

```text
PLUGIN_LOADED
CUSTOM_TOOL_VISIBLE
SDK_CLIENT_AVAILABLE
SESSION_CREATE
SESSION_PROMPT
SESSION_ABORT
HOST_CONTEXT
WORKSPACE_CONTEXT
BRIDGE_FULL_DUPLEX
```

Conditional:
- CHILD_PARENT_LINK
- STRUCTURED_OUTPUT
- USAGE_METADATA
- EVENT_STREAM

Harness must not require optional capability silently.

If missing:
- select compatible execution profile;
- or block with typed reason.

No silent downgrade.

---

# 6. Anti-corruption layer

Package:

```text
packages/opencode-plugin/src/host/
    types.ts
    adapter.ts
    adapter_1_18.ts
    probes.ts
    normalize.ts
```

Only this layer may import/use changing OpenCode SDK/plugin-specific details.

Everything below receives normalized contracts.

Rule:

```text
OpenCode object -> normalize immediately -> internal Host* DTO
```

Never persist raw SDK response as authoritative state.

Raw host payload may be retained only as optional diagnostic artifact.

---

# 7. Update-resilience strategy

## 7.1 Version is not capability

Never:

```text
if opencode >= 1.18:
    assume tool works
```

Use:
- exact version identification;
- live tool registration probe;
- session API probe;
- abort probe;
- structured-output probe;
- compatibility manifest.

## 7.2 Compatibility record

```text
compatibility/opencode/1.18.30.json
compatibility/opencode/1.18.31.json
...
```

Each record stores:
- plugin API package version;
- tested host platform;
- feature probe results;
- semantic smoke result;
- known upstream issues;
- supported plugin version range;
- certification date.

## 7.3 Bridge negotiation

Plugin/core versions evolve separately.

Handshake fields:
- plugin_semver;
- bridge_protocol_supported[];
- core_api_supported[];
- contract_schemas[];
- host_features.

Major mismatch -> BLOCK.
Minor compatible -> negotiate highest common.

## 7.4 No raw host types in Core

This is the most important maintenance rule.

If tomorrow OpenCode renames:
- `worktree`;
- `messageID`;
- session method;
- output field;

only `HostAdapter` and compatibility fixture change.

## 7.5 Provider fallback creates new lineage

If plugin provider becomes unhealthy:
- do not silently switch to CLI;
- rerun preflight;
- compile a new RPB/provider binding;
- preserve old failed receipt.

This preserves existing R4-D071 semantics.

---

# 8. Proposed provider/runtime migration

Current:

```text
existing.opencode_tribunal_role
  -> tool tribunal_role
  -> launcher opencode_tribunal_role.py
  -> opencode CLI
```

Target dual period:

```text
existing.opencode_plugin_semantic   priority 120
  kind = plugin
  provides = tribunal.role.execute
  tool = tribunal_role_plugin
  live_probe = bridge semantic probe

existing.opencode_tribunal_role_cli priority 50
  kind = legacy_launcher
  provides = tribunal.role.execute
  tool = tribunal_role_cli
```

Runtime bindings:

```text
tribunal_role_plugin
  kind = bridge
  transport = harness-bridge-rpc
  method = semantic.execute

tribunal_role_cli
  kind = launcher
  entrypoint = mcp/launchers/opencode_tribunal_role.py
```

After certification:
- plugin preferred;
- CLI fallback disabled by default but retained for one deprecation cycle.

Writer/Coder use the same generic semantic transport later, not new ad-hoc OpenCode providers.

---

# 9. Provider readiness model

Replace coarse:

```text
implemented
available
```

with:

```text
adapter_present
bridge_ready
runtime_ready
authenticated
healthy
semantic_smoke_passed
certified_host
```

Projected states:
- MISSING
- INSTALLED
- DEGRADED
- EXECUTION_READY
- SEMANTIC_VALIDATED
- CERTIFIED

RPB requires the policy-selected level.

---

# 10. Plugin lifecycle

## startup

```text
load plugin
-> detect legacy plugin conflict
-> normalize host version/context
-> load compatibility manifest
-> spawn bridge daemon
-> bridge.hello
-> feature probes
-> core health
-> register status
-> READY/DEGRADED/BLOCKED
```

## request

```text
OpenCode tool harness_run
-> normalize ToolContext
-> harness.run RPC
-> possible reverse semantic.execute
-> return final Harness result
```

## cancel

```text
AbortSignal
-> harness.cancel
-> cancel active semantic execution
-> session abort if owned by plugin
-> receipt/status preservation
```

## shutdown

```text
stop accepting new requests
-> bridge.shutdown
-> flush diagnostics
-> terminate daemon
```

---

# 11. Ownership matrix

| Concern | Harness Core | OpenCode Plugin | OpenCode Host |
|---|---|---|---|
| Route selection | YES | NO | NO |
| Job/Attempt | YES | correlation only | NO |
| Claim/Evidence/Hypothesis | YES | NO | NO |
| Tribunal composition | YES | NO | NO |
| TEX creation | YES | NO | NO |
| Model credentials | NO | NO | YES |
| Model execution | request only | adapter | YES |
| Session creation | NO | YES | YES |
| Workspace context source | validate | normalize | source |
| Workspace authorization | YES | NO | permissions also apply |
| Cancellation semantics | authoritative mapping | propagate | signal/source |
| Admission | YES | NO | NO |
| Structured output first-pass | revalidate | configure | execute |
| Plugin compatibility | consume status | YES | runtime |
| Provider policy | YES | report facts | NO |

---

# 12. Current components and disposition

| Current component | Status | Target |
|---|---|---|
| `plugins/tool-skill-contract-router.ts` | LEGACY | remove from authority path |
| `config/opencode_plugin_config.json` | LEGACY | replace by npm/local plugin package config |
| `scripts/register_plugin.py` | LEGACY | replace installer |
| `config/runtime_integration_policy.json` | MIGRATE | host-integration/2.0 |
| `scripts/health_check.py` | MIGRATE | plugin-aware doctor |
| `scripts/setup_env.*` | MIGRATE | minimal core env; CLI vars optional |
| `mcp/launchers/_runner.py` | LEGACY FALLBACK | CLI provider only |
| `opencode_* launchers` | LEGACY FALLBACK | semantic.execute plugin transport |
| `mcp/coder_router_server.py` | LEGACY SEMANTIC | core Coder + generic semantic.execute |
| `agents/*.md` | OPTIONAL PACK | user-facing profiles, not core protocol |
| `OPENCODE_SESSION_DB` | OPTIONAL LEGACY | diagnostics only |
| `LogicalToolProviderTransport` | KEEP | primary insertion point |
| `SubprocessJsonProviderTransport` | KEEP | deterministic E2E/fallback |
| RPB/TEX/PER | KEEP | unchanged |

---

# 13. Tests that guarantee tomorrow's OpenCode update does not break Core

## Layer A: Hostless Core

Run without OpenCode:
- Writer;
- Researcher;
- Coder;
- R4;
- bridge schema validation.

Must remain green on every plugin update.

## Layer B: fake bridge

- TS <-> Python;
- reverse request;
- concurrent calls;
- cancel;
- crash;
- protocol mismatch;
- large artifact references.

## Layer C: OpenCode compatibility probe

For each host version:
- plugin loads;
- tool visible;
- ToolContext normalized;
- SDK client works;
- session create/prompt/abort;
- permission isolation;
- structured output if certified.

## Layer D: semantic smoke

One bounded read-only role.
No Claim admission yet.

## Layer E: Tribunal E2E

Q1/A1/Q2/A2/Advocate through unchanged RPB/TEX/PER.

## Layer F: cross-module

Same plugin semantic adapter:
- Writer draft/repair;
- Coder worker/reviewer;
- Researcher Tribunal.

## Upgrade acceptance

Test:
1. old plugin + old Core;
2. new plugin + old compatible Core;
3. old plugin + new compatible Core;
4. protocol-major mismatch blocks cleanly;
5. host upgrade with same plugin:
   - compatibility probe;
   - no Core code changes required unless contract actually changes.

---

# 14. Recommended immediate implementation boundary

Do not begin with OpenCode hooks.

Implement first:

```text
P1A Host-independent DTO contracts
    HostContext/1.0
    WorkspaceRef/1.0
    SemanticExecutionRequest/1.0
    SemanticExecutionResult/1.0

P1B harness-bridge-rpc/1.0
    full-duplex peer
    hello
    health
    run
    cancel
    semantic.execute

P1C fake TS/Python E2E
```

Then P2 status-only OpenCode plugin.

This isolates the stable Harness/plugin contract before touching volatile OpenCode APIs.

---

# 15. Hard invariants

1. OpenCode-specific objects never enter Researcher/Writer/Coder state.
2. Plugin never selects route, role, evidence or truth.
3. Core never reads provider credentials.
4. Direct `opencode run` is legacy transport only.
5. OpenCode DB is not required for correctness.
6. One generic semantic execution contract serves Researcher/Writer/Coder.
7. Provider fallback always creates new binding lineage.
8. Host update cannot require edits to Claim/TEX/Writer/Coder schemas.
9. Legacy and native plugins must not run simultaneously.
10. Unsupported host feature fails closed or degrades explicitly, never silently.

