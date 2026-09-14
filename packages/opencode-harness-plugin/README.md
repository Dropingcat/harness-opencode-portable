# @harness/opencode-plugin

OpenCode native plugin bridge to Harness Core (Writer + Researcher + Coder).

Host adapter only. Core authority stays in Harness. The plugin never selects
route/role/evidence/truth.

## Install (standard OpenCode mechanism)

Local (development):

```json
// opencode.jsonc
{
  "plugin": ["file:///E:/opencode_harness/packages/opencode-harness-plugin/src/index.ts"]
}
```

Or auto-discovery: copy `src/index.ts` to `.opencode/plugins/opencode-harness-plugin.ts`.

npm distribution (transfer to other devices):

```bash
npm pack
# then on target host:
npm install /path/to/@harness-opencode-plugin-0.1.0.tgz
# register in opencode.jsonc as "@harness/opencode-plugin"
```

Requires `OPENCODE_HARNESS_ROOT` to point at the Harness checkout.

## Tools

- `harness_status` — plugin/bridge/core readiness. No semantic execution.
- `harness_run` — deterministic Harness route/bundle (Writer/Researcher/Coder). No semantic execution.

`semantic.execute` (child-session model execution) is reserved and disabled by default pending live certification.

## Layout

- `src/host/` — anti-corruption layer: normalizes OpenCode SDK/ToolContext into HostContext/WorkspaceRef.
- `src/bridge/` — NDJSON full-duplex `harness-bridge-rpc/1.0`.
- `src/tools/` — plugin tools.
- `core/` — Python Core bridge peer, installer, doctor.
- `schemas/` — JSON Schema for the four boundary contracts.

## Rules

- Never load this together with legacy `plugins/tool-skill-contract-router.ts`.
- `OPENCODE_BIN` and `OPENCODE_SESSION_DB` are not required in native mode.
- OpenCode SDK objects are normalized at the plugin edge and never persisted as Core state.