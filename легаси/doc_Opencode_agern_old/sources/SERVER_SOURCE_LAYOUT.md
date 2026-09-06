# Server Source Layout

Цель: не потерять, **где именно что лежало на сервере**, пока мы собираем единый модуль.

> **READ-ONLY (ARCHIVE).** Диски `W:\server2` / `Z:\server` и папки-источники (`doc_guard`, `doc_hermes_pi`, `workspace\агент кодер`, `Default Project`) — это **архив**. Они могут быть **отключены/удалены в перспективе**. Всё, что из них нужно, уже физически перенесено в HARNESS (`E:\Documents\Документы\doc_Opencode_agern`) и считается **source of truth**. Запрещено править или дописывать что-либо в этих источниках — только читать для сверки. Если чего-то не хватает в HARNESS — добавить в HARNESS, а не в архив.

## Primary sources used so far

### `W:\server2`

- `W:\server2\agent\`
  - server variants of `code-orchestrator`, `coder-worker`, `code-reviewer`, `code-tester`, `code-auditor`
- `W:\server2\shared\code-factory-process.md`
  - original shared factory methodology
- `W:\server2\scripts\code-factory\`
  - `factory_ctl.py`
  - `contract_validator.py`
  - `code_factory_runner.py`
- `W:\server2\skills\`
  - server skill corpus: **184 skill modules**

### `Z:\server\.hermes`

- `Z:\server\.hermes\mcp\`
  - MCP servers and launcher wrappers copied into `mcp/`
- `Z:\server\.hermes\profiles\_archive\triz-agent\`
  - TRIZ patterns and archived kanban/runtime references
- `Z:\server\.hermes\kanban\global_kanban.py`
  - global task controller reference

### `E:\Documents\Документы\workspace\агент кодер`

- WP docs / architecture / contracts / threat model / ARIZ-light

### `E:\барахло\Documents\Default Project`

- researcher-core architecture
- claim pipeline
- deterministic runtime
- policy/heuristics

### `C:\Users\Arhys\.config\opencode`

- live OpenCode agents / current skills / live config (`opencode.jsonc`)
- **это runtime-зеркало HARNESS** (односторонняя синхронизация `scripts/sync_to_live.py`), а не отдельный источник истины
- `shared/` и `scripts/` — синхронизированы из HARNESS

## Module landing zones

What from scattered locations now belongs in the unified module:

- `agents/` ← live/current + selected server agent variants
- `shared/` ← module-owned shared process docs
- `scripts/code-factory/` ← module-owned deterministic runtime scripts
- `scripts/router/`, `scripts/memory/` ← module-owned resolvers/collectors
- `skills/opencode-current/` ← copied current OpenCode skills
- `skills/server2-corpus/` ← copied server skill corpus
- `mcp/` ← copied MCP servers/launchers
- `guard/` ← copied doc_guard runtime + `guard/docs/` (полный doc-набор)
- `references/` ← archival/source lineage only
- `config/` ← all machine-readable policies and registries

## Consolidation status (2026-09-01)

- **Skills:** W2=184/184, current=129/129 физически в HARNESS+`skills/` (0 недостающих; 54 non-SKILL dirs в opencode-current — это обёртки, полные версии лежат в server2-corpus с SKILL.md).
- **Runtime scripts:** code-factory (3), router (6), memory (2), add_skill, sync_to_live — в HARNESS.
- **Guard:** 3 src + 11 docs → `guard/src` + `guard/docs`.
- **MCP:** 4 сервера + 5 launchers — в HARNESS.
- **Kanban:** `global_kanban.py` — в HARNESS (references/global-kanban).
- **Not transferred (external dep):** research runner (`run_research.sh`, `numeric_comparator.py`, `judge_brief.py`, `synthesizer.py`) — отсутствует на машине; при появлении класть только в HARNESS.
