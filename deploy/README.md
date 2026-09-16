# Portable Harness Deployment

Fully self-contained, portable Harness runtime for OpenCode Desktop (project-scoped).

## What this is

A portable copy of the Harness orchestrator module (agents, native plugin,
runtime policy, guard, MCP servers, skills, writer-core) that installs and
connects to OpenCode Desktop **without touching your global config**.

## Layout

```
opencode_harness_portable/
  .opencode/            project-scoped OpenCode config + MCP servers
  agents/               15 Harness subagents
  config/               runtime policy (runtime_snapshot.json, routes, guard_policy...)
  guard/                doc_guard (session_guard.py, guard_runner.py)
  mcp/                  bundled MCP servers (academic_search, coder_router, doc_extract, searxng)
  packages/opencode-harness-plugin/   native OpenCode plugin bridge to Core
  scripts/              router, orchestration, code-factory, researcher, writer-core
  skills/opencode-current/  132 skills
  templates/            reusable templates
  deploy/               bootstrap scripts (bootstrap.ps1, bootstrap.sh)
```

## Quick start (Windows)

```powershell
cd opencode_harness_portable
powershell -ExecutionPolicy Bypass -File deploy\bootstrap.ps1
```

On Linux/macOS:

```bash
cd opencode_harness_portable
bash deploy/bootstrap.sh
```

## What bootstrap does

1. Creates `.venv` (Python 3.11+), installs `requirements-core.txt` + `requirements-capability-bundle.txt` + `requirements-mcp-doc.txt`.
2. Builds the native plugin (`npm run build` in `packages/opencode-harness-plugin`), compiling `src/` -> `dist/`.
3. Installs project plugin deps (`@opencode-ai/plugin`) into `.opencode/node_modules`.
4. Registers the plugin in `.opencode/opencode.json` with a `file://` URI pointing to the built `dist/index.js` (project-scoped, no global writes).
5. Recompiles the runtime policy snapshot from authoritative configs (`scripts/router/compile_runtime.py`).
6. Writes `.env` with resolved environment variables (OPENCODE_HARNESS_ROOT, PYTHON_BIN, etc.).
7. Runs `doctor.py` to verify plugin/core/legacy status, and `health_check.py`.
8. Prints the final "connect to Desktop" instruction: open the repo folder in OpenCode Desktop.

## Connect to OpenCode Desktop

1. Run bootstrap once (creates `.venv`, builds plugin, registers in `.opencode/opencode.json`).
2. Open **this folder** in OpenCode Desktop.
3. The project config `.opencode/opencode.json` loads the native plugin automatically.
4. Check plugin loaded in logs: `harness plugin loaded protocol=harness-bridge-rpc/1.0 required_features_ok=true`.
5. Use `harness_status` / `harness_run` tools.

## Notes

- Never load the legacy `plugins/tool-skill-contract-router.ts` alongside the native plugin (doctor flags it).
- `OPENCODE_HARNESS_ROOT` env is optional; the plugin auto-detects root from its own path.
- Secrets are never written to config; use `.env` (git-ignored) or your shell env.