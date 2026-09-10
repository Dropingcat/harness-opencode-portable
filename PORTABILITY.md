# Portability Notes

This bundle is currently a Windows-collected archive of OpenCode harness parts. Several files came from Linux/Pi paths and must be parameterized before use as a portable runtime.

## Required path abstraction

Use environment variables instead of hardcoded machine paths:

- `OPENCODE_BIN` — path to the OpenCode executable.
- `OPENCODE_CONFIG_DIR` — user OpenCode config directory.
- `OPENCODE_HARNESS_ROOT` — this bundle root.
- `OPENCODE_RUNS_DIR` — writable run/session directory.
- `HERMES_ROOT` — optional location of Hermes scripts/data if present.
- `DOC_GUARD_CONFIG` — path to real guard config outside the bundle.
- `WRITER_CORE_ROOT` — Writer Core directory containing `wc_cli.py`.
- `WRITER_PYTHON` — Python executable for Writer Core and writer/research bridge scripts.

Writer commands deliberately do not reuse shell-specific `${PYTHON}` syntax. Set
`WRITER_PYTHON` before starting OpenCode. PowerShell 5.1 example:

```powershell
$env:WRITER_PYTHON = $env:PYTHON
$env:WRITER_CORE_ROOT = Join-Path $env:OPENCODE_HARNESS_ROOT "scripts\writer-core"
```

POSIX example:

```sh
export WRITER_PYTHON="${PYTHON:-python3}"
export WRITER_CORE_ROOT="$OPENCODE_HARNESS_ROOT/scripts/writer-core"
```

## Known hardcoded paths to replace

Search and replace by configuration layer, not by one-off edits:

- `/home/orangepi/.opencode/bin/opencode`
- `/home/orangepi/.config/opencode/...`
- `/home/orangepi/.hermes/...`
- `/tmp/opencode/runs`
- `/tmp/factory-bubble/...`

On Windows, prefer paths under a user-selected workspace, for example:

- `OPENCODE_HARNESS_ROOT=E:\opencode_harness` (ASCII junction; реальный путь `E:\Documents\Документы\doc_Opencode_agern-new`)
- `OPENCODE_RUNS_DIR=E:\opencode_harness\.runs`

Do not commit `.runs/` or any runtime database.

## Runtime connection order

1. Smoke-test each Python MCP server directly.
2. Smoke-test `doc_guard` on synthetic databases only.
3. Create MCP config templates referencing this bundle through env variables.
4. Connect one MCP server at a time in OpenCode.
5. Only after MCP works, enable launchers that spawn OpenCode subagents.

## Capability fallback rule

If an agent expects `research_papers` but current runtime lacks it, route academic search to `mcp/academic_search_server.py` instead. Do not leave implicit tool assumptions in agent prompts.
