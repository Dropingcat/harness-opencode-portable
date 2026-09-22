# Script/Module Scatter Map

Фактический разброс скриптов и модулей по машине (сверено 2026-09-01).

## Карта владения

| Файл / группа | HARNESS (source of truth) | LIVE opencode | W:\server2 | Z:\server\.hermes | doc_guard (orig) |
|---|---|---|---|---|---|
| `factory_ctl.py` | ✅ scripts/code-factory | ✅ (copy) | ✅ (orig) | — | — |
| `contract_validator.py` | ✅ scripts/code-factory | ✅ (copy) | ✅ (orig) | — | — |
| `code_factory_runner.py` | ✅ scripts/code-factory | ✅ (copy) | ✅ (orig) | — | — |
| router (`resolve_*`, `split_claims`, `build_*`, `build_task_plan`) | ✅ scripts/router | ✅ (copy) | — | — | — |
| memory (`collect_l2`, `promote_l2_to_l3`) | ✅ scripts/memory | ✅ (copy) | — | — | — |
| `add_skill.py` | ✅ scripts/add_skill.py | — | — | — | — |
| guard (`session_guard`, `semantic_layer`, `adversarial_build`) | ✅ guard/src | — | — | — | ✅ doc_guard/src |
| `global_kanban.py` | ✅ (module-owned copy in `references/global-kanban`) | — | — | ✅ Z_HERMES/kanban | — |
| MCP servers (4) | ✅ mcp/ | — | — | ✅ Z_HERMES/mcp | — |
| MCP launchers (5) | ✅ mcp/launchers | — | — | ✅ Z_HERMES/mcp/launchers | — |
| research runner (`run_research.sh`, `numeric_comparator`, `judge_brief`, `synthesizer`) | ❌ **отсутствует** | — | ❌ не найдено | — | — |

## Проблемы, которые ты верно заметил

1. **Тройное повторение runtime-скриптов** (factory_ctl + validator + runner):
   - HARNESS (источник) / LIVE (рабочая копия) / W:\server2 (оригинал старого сервера).
   - Это риск дрейфа: кто-то правит одну копию, остальные устаревают.

2. **guard в двух местах**:
   - HARNESS/guard/src (source of truth)
   - doc_guard/src (оригинал отдельного проекта)

3. **MCP в двух местах**:
   - HARNESS/mcp
   - Z:\server\.hermes\mcp (оригинал сервера)

4. **global_kanban.py**:
   - HARNESS/references/global-kanban (module-owned copy)
   - Z:\server\.hermes\kanban (origin)

5. **research runner** — вообще не найден нигде (gap, уже зафиксирован в runbook).

## Принцип (что должно быть)

> **Один source of truth в HARNESS. Всё остальное — либо односторонняя синхронизация, либо ссылка.**

- HARNESS = единственная редактируемая копия.
- LIVE `~/.config/opencode` = runtime-зеркало, синхронизируется ИЗ HARNESS (односторонне).
- W:\server2 / Z:\server\.hermes / doc_guard = archival-источники, читаются только для миграции/сверки, НЕ редактируются.
- research runner = пока отсутствует; когда появится — класть в HARNESS, а не параллельно.

## Исключения (легитимные, НЕ трогать)

- LIVE agents/shared — это копии агентных доков/процессов, синхронизированы из HARNESS (см. AGENT_ARCHITECTURE_PLAN_VS_FACT).
- skill corpus (`skills/server2-corpus`) — module-owned, уже сконсолидирован.

## Что делать дальше (консолидация)

1. Заменить имя «copy» на явный режим sync: добавить в `scripts/` маленький `sync_to_live.py`, который односторонне копирует HARNESS scripts/agents/shared → LIVE (dry-run по умолчанию).
2. Пометить W:\server2 и Z:\server\.hermes в `sources/SERVER_SOURCE_LAYOUT.md` как **archival (read-only)**, чтобы не было соблазна править их напрямую.
3. Зафиксировать guard: HARNESS/guard/src — source of truth; doc_guard/src — присоединено как reference.
4. При появлении research runner — инсталлировать ТОЛЬКО в HARNESS и прописать env.