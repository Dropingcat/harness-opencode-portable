# Agent Architecture: Plan vs Live Fact

## Planned architecture (15 agents)

| Агент | Mode | Роль |
|---|---|---|
| `code-orchestrator` | primary | фабрика кода: декомпозиция, dispatch, контроль |
| `coder-worker` | subagent | пишет модуль по контракту |
| `code-reviewer` | subagent | критик: код, безопасность, фальсифицируемость |
| `code-tester` | subagent | тесты, coverage |
| `code-auditor` | subagent | трибунал: процесс, не код |
| `experimenter` | primary | autoresearch/оптимизация |
| `research-orchestrator` | primary | цикл верификации текстов |
| `source-fetcher` | subagent | поиск источников |
| `claim-parser` | subagent | атомарные клаймы |
| `fact-checker` | subagent | вердикты (пред.) |
| `tribunal-judge` | subagent | 5 ролей, диалектика |
| `synthesizer` | subagent | финальный отчёт |
| `researcher` | primary | web-исследование (disabled ранее) |
| `writing-orchestrator` | primary | стратегия статьи |
| `article-writer` | subagent | драфт/ревью статьи |

## Live fact (C:\Users\Arhys\.config\opencode\agent)

**15 агентов из module синхронизированы в live — результат полный (1:1).**

- MODULE->NOT in live: none
- LIVE->extras: none

Проверка от 2026-09-01: все 15 файлов присутствуют, frontmatter и mode совпадают.

## Что на самом деле live подцепит

- первичные агенты: `code-orchestrator`, `research-orchestrator`, `writing-orchestrator`, `experimenter`, `researcher`, `article-writer` (mode all)
- субагенты: `coder-worker`, `code-reviewer`, `code-tester`, `code-auditor`, `source-fetcher`, `claim-parser`, `fact-checker`, `tribunal-judge`, `synthesizer`

## Зависимости, которые агенты ещё требуют

| Контур | Agent | Runtime dep | На этой машине |
|---|---|---|---|
| code | `code-orchestrator` | `factory_ctl.py` + `contract_validator.py` + `code_factory_runner.py` | ✅ в `~/.config/opencode/scripts/code-factory` |
| code | kanban | `global_kanban.py` | ✅ module-owned copy в bundle; env должен указать `.kanban.db` |
| research | `research-orchestrator`+субагенты | `run_research.sh`, `numeric_comparator.py`, `judge_brief.py`, `synthesizer.py`, `rules_balanced.yaml` | ❌ отсутствуют (claimeai-service не перенесён) |
| guard | все | `session_guard.py` | ✅ в bundle (`DOC_GUARD_ENTRYPOINT`) |
| MCP | `coder_run`, `arxiv_search`, `openalex_search`, `extract_document`, `searxng_search` | 4 MCP servers | ⚠️ скрипты есть, серверы не запущены |

## Вывод

Планировавшаяся агентная архитектура **перенесена в live без потерь** (15/15).

Однако **не все runtime-зависимости исполняемы на этой машине прямо сейчас**:

- code-контур — да, исполняем (runtime scripts в live есть).
- research-контур — **агенты есть, но детерминированный runner отсутствует**:
  - research-agents будут честно падать / требовать ручного разбора, если их детерминированные скрипты не перенесены.
  - Это явный gap, зафиксирован в `RUNTIME_RUNBOOK.md -> Known gaps`.

## Gap-решение (для research-контура)

Пока нет claimeai-service на машине:
1. research-оркестратор должен при запуске проверять `${RESEARCH_*}` env и, если пусто, честно сообщать «research runner не сконфигурирован».
2. Не выдумывать: без детерминированного слоя вердикты не принимать.
3. Перенос claimeai-service = отдельный миграционный шаг (WS-16, если понадобится).