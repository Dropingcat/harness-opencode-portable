# @harness/opencode-plugin — P1 Status

Status: `IMPLEMENTED / HOSTLESS ACCEPTANCE PASS / LIVE OPENCODE INSTALLATION PENDING`

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
- Compatibility record: `compatibility/opencode/1.18.16.json` (`NOT_LIVE_CERTIFIED` for semantic).

## Test evidence

- TS: `tests/bridge.test.ts` — 8/8 PASS (protocol round-trip, host types, sha256, real Python-peer E2E hello/status/run, full-duplex reverse request while parent pending, missing-method error).
- Python: `tests/test_plugin_factory.py` — 4/4 PASS (dist tools present, bridge peer hello/status/run, doctor, installer).
- Harness regression on working repo:
  - Researcher full: 590 passed + 2 skipped.
  - runtime compiler PASS (hash `8910fd...dfef`), capability compiler PASS (hash `f9de81...47a0`).
  - Pre-existing unrelated failure: `test_writer_migration_manifest.py::test_targets_are_contained_by_classification` (manifest maps `semantic-tests -> tests/writer/semantic` under `canonical_root=scripts/writer`); not caused by this package (tracked tree clean).

## P2 (next, live OpenCode)

1. Install entry via installer: `python packages/opencode-harness-plugin/core/install_plugin.py --target project`.
2. Restart OpenCode; verify `harness_status` / `harness_run` visible.
3. Capture doctor + HostCapabilitySnapshot.
4. Only then enable read-only `semantic.execute` smoke, then Tribunal transport migration.

## Rules

- Never load this plugin together with legacy `plugins/tool-skill-contract-router.ts`.
- `OPENCODE_BIN` / `OPENCODE_SESSION_DB` are not required in native mode (`config/host_integration_policy.json`, schema `harness-host-integration/2.0`).