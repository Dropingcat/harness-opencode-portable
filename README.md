# Harness Portable Module

Fully self-contained, portable Harness orchestrator module for OpenCode Desktop.
Ship this repo to any machine, run one bootstrap command, open the folder in
OpenCode Desktop — the native plugin, all 15 agents, runtime policy, guard,
MCP servers and 132 skills are connected automatically.

Project-scoped: nothing is written to the user's global OpenCode config.

## Versions

- **v1** (tag `v1`) — native plugin + deterministic routing + full agent specs +
  runtime policy + MCP + bootstrap. Agents are role specifications; **not yet**
  wired as OpenCode subagents. Tribunal ported and self-contained; **live**
  tribunal (semantic role execution) is **not** reachable until P4.
- **v1.1** — planned: OpenCode subagents, dynamic role prompts, harness memory,
  role contracts, native guard, live tribunal, plus reconciliation with the
  canonical "migration to plugin" documentation (`патчи/миграция в плагин`,
  TD-D* ledger). See `ROADMAP_v1.1.md` and `TECH_DEBT_AGENTS.md`.

## Layout

```
.
├── .opencode/                    project-scoped OpenCode config (plugin + MCP)
├── agents/                       15 Harness subagents (orchestrators, workers, researcher, tribunal…)
├── config/                       runtime policy (runtime_snapshot.json, routes, guard_policy, …)
├── guard/                        doc_guard: session_guard.py, guard_runner.py, semantic_layer
├── mcp/                          bundled MCP servers (academic_search, coder_router, doc_extract, searxng)
├── packages/opencode-harness-plugin/   native OpenCode plugin bridge to Core (build -> dist/index.js)
├── scripts/                      router, orchestration, code-factory, researcher, writer-core
├── skills/opencode-current/      132 skills referenced by runtime routes
├── templates/                    reusable templates
├── AGENT_REPO_ACCESS.md          how an agent gets repo access from a new session
└── deploy/                       bootstrap.ps1 (Windows) / bootstrap.sh (Linux/macOS)
```

## Quick start

Windows:
```powershell
cd opencode_harness_portable
powershell -ExecutionPolicy Bypass -File deploy\bootstrap.ps1
```

Linux / macOS:
```bash
cd opencode_harness_portable
bash deploy/bootstrap.sh
```

Bootstrap will:
1. Create `.venv` (Python 3.11+) and install requirements.
2. Build the native plugin (`npm run build` -> `dist/index.js`).
3. Install project plugin deps (`@opencode-ai/plugin`).
4. Register the plugin in `.opencode/opencode.json` (file:// URI, project-scoped).
5. Recompile the runtime policy snapshot (`compile_runtime.py`).
6. Write `.env`.
7. Run `doctor.py` and `health_check.py`.

Then **open this folder in OpenCode Desktop**. The plugin loads automatically.

## Verify

- Log marker on load: `harness plugin loaded protocol=harness-bridge-rpc/1.0 required_features_ok=true`
- Chat tools: `harness_status` (readiness) and `harness_run` (deterministic routing).

## Requirements

- Python 3.11+ (auto-detected, or set `PYTHON_BIN`)
- Node.js + npm (for plugin build; a prebuilt `dist/` can be shipped instead)
- OpenCode Desktop 1.18.30+ (tested)

## GitHub remote & access token

The external GitHub repository is wired in as the `origin` remote:

```bash
git remote -v
# origin  https://github.com/Dropingcat/harness-opencode-portable.git
```

The access token is stored **as an environment variable** in the git-ignored file
`.github-token.env` (never commit it):

```bash
export GITHUB_TOKEN="ghp_************"   # full value lives only in .github-token.env
```

Load and use it:

```bash
source ./.github-token.env
git config --local credential.helper '!f() { echo "username=x-access-token"; echo "password=$GITHUB_TOKEN"; }; f'
git fetch origin && git push origin <branch>
```

> ⚠️ Verification status: with the token currently provided, `git ls-remote origin` and
> `GET /user` both return **401 (invalid credentials)**, and the repo returns **404** when
> accessed anonymously (private or not yet created). Replace the value in
> `.github-token.env` with a valid PAT to enable fetch/push.
> Full instructions: [GITHUB_ACCESS.md](GITHUB_ACCESS.md).

## Notes

- Never load the legacy `plugins/tool-skill-contract-router.ts` alongside the native plugin.
- All paths are resolved relative to the repo root (`OPENCODE_HARNESS_ROOT` auto-detected).
- Secrets belong in `.env` / `.github-token.env` (git-ignored), never in committed configs.