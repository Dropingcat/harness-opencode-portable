# @harness/opencode-plugin — P1+P2+P3 Status

Status: `P1 HOSTLESS PASS / P2 LIVE LOAD + TOOLS VERIFIED / P3 SEMANTIC LIVE SMOKE PASS`

## Boundary

- Host adapter only. Never selects route/role/evidence/truth.
- Raw OpenCode SDK objects are normalized at the plugin edge (`src/host/`) and never cross the bridge as Core state.
- Protocol: `harness-bridge-rpc/1.0` (NDJSON full-duplex over stdio).
- DTO: `HostContext/1.0`, `WorkspaceRef/1.0`, `SemanticExecutionRequest/1.0`, `SemanticExecutionResult/1.0` (+ JSON Schemas in `schemas/`).

## P1 tool surface

- `harness_status` — plugin/bridge/core readiness, no semantic execution.
- `harness_run` — deterministic Harness route/bundle through Core (Writer/Researcher/Coder), no semantic execution.
- `semantic.execute` reverse adapter is reserved; production semantic execution remains disabled pending live certification.

## Verified against actual SDK types

- `@opencode-ai/plugin` / `@opencode-ai/sdk` `1.18.16` (installed in this package).
- Confirmed: `Plugin` is `(input: PluginInput) => Promise<Hooks>`; `Hooks.tool` is a map of `tool()` definitions; `ToolContext` carries `sessionID/messageID/agent/directory/worktree/abort`.
- SDK v1 client: `session.create/prompt/abort/messages`, `event.subscribe` — these are the future child-session transport.
- Compatibility record: type-level verification is reflected in `compatibility/opencode/1.18.30.json` as `TYPE_VERIFIED` probes (the separate 1.18.16 record was not carried into v1; see TD-D8 rescore).

## Test evidence

- TS: `tests/bridge.test.ts` — 8/8 PASS (protocol round-trip, host types, sha256, real Python-peer E2E hello/status/run, full-duplex reverse request while parent pending, missing-method error).
- Python: `tests/test_plugin_factory.py` — 4/4 PASS (dist tools present, bridge peer hello/status/run, doctor, installer).
- Harness regression on working repo:
  - Researcher full: 590 passed + 2 skipped.
  - runtime compiler PASS (hash `8910fd...dfef`), capability compiler PASS (hash `f9de81...47a0`).
  - Pre-existing unrelated failure: `test_writer_migration_manifest.py::test_targets_are_contained_by_classification` (manifest maps `semantic-tests -> tests/writer/semantic` under `canonical_root=scripts/writer`); not caused by this package (tracked tree clean).

## P3 semantic.execute live smoke (2026-09-14, OpenCode 1.18.30)

- Gated behind `HARNESS_SEMANTIC_ENABLED=1` (absent by default; Core enables after live certification).
- Live call via real model: created isolated child session (`parentID=ses_f5e953b5...`), ran a prompt with NO tools (`tools: {}`), returned `runtime_status=COMPLETED` with `structured_output.text`.
- Evidence (session created, child loop, prompt stream, tool_use completed) captured in `opencode.log`.
- Timeout/cancel path unit-tested (fake client: abort called, `TIMED_OUT` returned).

## P2 live verification (2026-09-14, OpenCode 1.18.30)

- Plugin loaded through explicit registration `.opencode/opencode.json` -> `plugin: ["file:///...dist/index.js"]` (single load, no auto-discovery duplicate).
- Log marker: `harness plugin loaded protocol=harness-bridge-rpc/1.0 ... required_features_ok=true`.
- `harness_status` invoked by live model (`opencode/big-pickle`), returned real core status; `host_version` correctly reported as `1.18.30` (captured from `session.created` event).
- `harness_run` invoked by live model, routed through the Python core `resolve()` (deterministic escalation on unmatched task = correct).
- Verified in both OpenCode CLI 1.18.30 and Desktop (session agent=`build`).
- Compatibility record: `compatibility/opencode/1.18.30.json` (schema 2.0, evidence-level scale; semantic status `NOT_CERTIFIED`).

## P2 (next, live OpenCode)

1. Verify in Desktop GUI (same engine; plugin auto-discovery is identical).
2. Capture HostCapabilitySnapshot from live logs.
3. Confirm legacy `tool-skill-contract-router.ts` is not loaded simultaneously.
4. Only then enable read-only `semantic.execute` smoke (P3), then Tribunal transport migration (P4).

## Rules

- Never load this plugin together with legacy `plugins/tool-skill-contract-router.ts`.
- `OPENCODE_BIN` / `OPENCODE_SESSION_DB` are not required in native mode (`config/host_integration_policy.json`, schema `harness-host-integration/2.0`).