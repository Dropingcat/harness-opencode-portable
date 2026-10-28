# Deterministic V2 adapter

The V1 `src/index.ts`, dependencies and `dist/` build remain unchanged.
This separate entrypoint is a plain default `{ id, setup }` definition; it uses
no runtime OpenCode package and does not claim SDK type certification.

## Build and test

```powershell
node --test packages/opencode-harness-plugin/tests-v2/host-contract.test.mjs
node packages/opencode-harness-plugin/scripts/build-v2.mjs <local-typescript-package-path>
node packages/opencode-harness-plugin/tests-v2/core-smoke.mjs <explicit-python-interpreter>
```

The compiler argument is optional if TypeScript resolves locally. No installation
or network access is performed. Build output is `dist-v2/v2/index.js`; the builder
transpiles only the existing bridge transport and copies the JavaScript adapter.
It does not typecheck against V2 SDK declarations. Configure the **built** file
only after review and approval; no runtime configuration is changed here.

Options: `harnessRoot` is the Harness tree containing Core; `pythonPath` must be
an explicit suitable interpreter (or WRITER_PYTHON/PYTHON_BIN/PYTHON environment
variable). Root defaults to the package's containing Harness tree, not session cwd.

Both tools operate on the plugin instance's `ctx.location.directory`, used as
the local workspace/worktree directory, not the canonical Git checkout. Invocation
session/message/agent IDs come from the V2 execution context. This is deliberately
a Location-scoped deterministic tool, not cross-session semantic execution.

Only `harness_status` and `harness_run` are registered. All reverse requests except
`bridge.health` fail closed, including `semantic.execute`, regardless of environment
flags. Responses always include `semantic_ready: false`. The internal-tool guard
is retained. Cleanup closes the owned bridge once, including setup failure.
Abort is checked before/after deterministic RPC; the existing transport has no
per-request abort API, so in-flight deterministic work may finish after cancellation.

## Contract evidence

- Official V2 plugin guide: https://opencode.ai/v2/docs/build/plugins
  (default definition, synchronous `ctx.tool.transform`, JSON Schema `input`,
  `{ content: string }`, cleanup function and `ctx.tool.hook`).
- Guarded cached full guide SHA256:
  `1ee1f2c6ed5d950b28dc7640092f5c23a5ada92e2e41407db95ec50136fdc22f`.
  Bundled `researcher_core.guard.scan_text`: PASS, zero high findings.
- Installed Desktop CLI `2.0.29-x64/opencode-cli.exe` embedded Promise adapter:
  `s.execute(e,{...a,signal:y,progress:...})`; tool hook event carries
  `sessionID`, `agent`, `messageID`, `id`, `input`. Its loader requires a default
  definition with id and setup/effect. Extracted fragments were P0-scanned before
  use; evidence is `C:/Temp/opencode/host-v2-desktop-contract.json`.
- Official guide explicitly says V2 reads default export id/setup and that
  plugin Location is instance-scoped, not necessarily every session's location.

Node contract tests exercise this host-facing shape with an in-memory bridge.
They are not a real Desktop activation or release-compatible SDK typecheck.
