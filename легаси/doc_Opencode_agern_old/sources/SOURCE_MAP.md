# Source Map

## Primary source folders inspected

- `Z:\server\.checkpoints`
- `Z:\server\.hermes\mcp`
- `E:\Documents\.opencode\node_modules`
- `E:\Documents\Документы`
- `E:\Documents\Документы\doc_guard`
- `E:\Documents\Документы\doc_hermes_pi`
- `E:\Documents\Документы\workspace\агент кодер`
- `Z:\server\opencode\packages\oh-my-opencode-slim@latest`
- `Z:\server\projects\openworkers`

## High-value documents

- `doc_guard/docs/SKILLS_ROUTING.md`
- `doc_guard/docs/ROUTER_CONFIG.md`
- `doc_guard/docs/README.md`
- `doc_guard/docs/ARCHITECTURE.md`
- `doc_hermes_pi/CODER-BRIEFING-2026-08-22-v2.md`
- `doc_hermes_pi/router-delegate-contracts-2026-08-22.md`
- `doc_hermes_pi/coder-mcp-router-plan.md`
- `doc_hermes_pi/coder-harness-plugins-plan.md`
- `doc_hermes_pi/consolidated-proposals.md`
- `workspace/агент кодер/агент кодер/базовая документация/ARCHITECTURE.md`
- `workspace/агент кодер/агент кодер/базовая документация/AGENT_PROTOCOLS.md`
- `workspace/агент кодер/агент кодер/базовая документация/CONFIG_GUIDE.md`

## Runtime mismatch found

- `E:\Documents\.opencode\opencode.json` contains only `@sndrgrdn/opencode-autoresearch`.
- `C:\Users\Arhys\.config\opencode\opencode.jsonc` contains plugins: arise, hiai, command-inject, envsitter-guard, token-tracker.
- Current Windows MCP config has only `sequential-thinking` and `grep_app`.
- Many documented capabilities exist as source files but are not connected to current Windows runtime.

## Copied into this bundle, pass 1

- Current OpenCode agents: `C:\Users\Arhys\.config\opencode\agent\*.md` → `agents/`.
- Current OpenCode skills: `C:\Users\Arhys\.config\opencode\skills\*` → `skills/opencode-current/`.
- MCP servers: `Z:\server\.hermes\mcp\*.py` selected safe servers → `mcp/`.
- MCP launchers: `Z:\server\.hermes\mcp\launchers\*.py` selected safe launchers → `mcp/launchers/`.
- Guard source: `E:\Documents\Документы\doc_guard\src\*.py` → `guard/src/`.
- Guard docs and example config: `doc_guard/docs/*.md`, `guard_config.json.example` → `guard/docs/`, `guard/configs/`.
- Router/reference docs from `doc_hermes_pi` → `references/`.

Pass-1 inventory observed after copy:

- Python files: 123
- Markdown files: 446
- Skill directories: 183
- Agent files: 15

Note: this inventory includes scripts inside copied skills. It intentionally excludes `.env`, runtime DBs, pycache and real secret config files.
