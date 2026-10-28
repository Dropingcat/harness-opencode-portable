# paper-review-claude-port - порт Claude-специфичных файлов плагина в OpenCode

Цель: адаптировать `.claude-plugin/plugin.json`, `.mcp.json`, `hooks/hooks.json`
(Claude-специфичны, в OpenCode как есть не работают) к конвенциям portable harness
через фабрику кода (код-оркестратор -> worker/reviewer/tester/auditor, детерминированная сшивка).

## PROJECT_ID
`paper-review-claude-port` (kebab-case)

## Фабрика кода
- Задача: `PRS-CLAUDE-PORT` (state: `runs/factory_state.json`), итог `DONE`.
- Гейты: reviewer PASS, tester PASS, auditor PASS (attempt 1, rework 0).
- Проверки: `factory_ctl.py status/replay --state runs/factory_state.json`.

## Что куда переехало

| Claude-файл | OpenCode-эквивалент | Статус |
|---|---|---|
| `.claude-plugin/plugin.json` | `packages/paper-review-plugin/manifest.json` + `package.json` | перенесён |
| `.mcp.json` | `mcp/paper-parser-mcp`, `mcp/academic-search-mcp` + регистрация в `.opencode/opencode.json` (env `{env:CROSSREF_MAILTO}`, `{env:SEMANTIC_SCHOLAR_API_KEY}`) | перенесён |
| `hooks/hooks.json` (SessionStart check-deps) | `packages/paper-review-plugin/dist-v2/v2/index.js` (plugin `paper-review.system.v2`: check-deps при setup + `ctx.session.hook('context')`) | перенесён |
| — (bash check-deps.sh) | `scripts/paper-review/check-deps.py` (Windows/portable) | перенесён |

## Артефакты
- `artifacts/worker_paper-review-claude-port-v1.json`
- `artifacts/reviewer_paper-review-claude-port-v1.json`
- `artifacts/tester_paper-review-claude-port-v1.json` (5/5 PASS)
- `artifacts/auditor_paper-review-claude-port-v1.json`
- `runs/factory_state.json` (event-sourced + provenance)

## Ссылки
- shared: `shared/paper-review-chain-contracts.md`, `shared/paper-review-orchestration.md`
- Оригиналы плагина: `C:\Temp\opencode\integration\paper-review\`