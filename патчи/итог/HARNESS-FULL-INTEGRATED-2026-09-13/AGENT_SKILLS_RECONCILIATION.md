# Agent → Skills → Corpus Reconciliation

Дата: 2026-09-01. Цель: сверить, какие скилы реально вызываются агентами, с корпусом `skills/` и роутером скилов.

## Метод

1. Скан agent docs на реально упоминаемые скил-имена.
2. Сверить с `skills/server2-corpus` и `skills/opencode-current`.
3. Проверить связку с роутером (`skills_graph.json`, `resolve_route.py`).

## Результат сверки

### Корпус
- `skills/server2-corpus`: 55 skill-модулей
- `skills/opencode-current`: 129 skill-модулей
- Итого уникально на диске: подтверждено наличие ключевых orchestration/review/triz skills.

### Ключевые скилы, используемые агентами — presence on disk

| Skill | Используется в | В корпусе |
|---|---|---|
| `triz-problem-solving` | code-orchestrator, experimenter, research-orchestrator | ✅ |
| `ariz-contradiction-resolution` | code-orchestrator, tribunal-judge, code-auditor | ✅ |
| `doubt-driven-development` | code-orchestrator, code-reviewer, tribunal-judge | ✅ |
| `verification-planning` | code-orchestrator | ✅ |
| `incremental-implementation` | code-orchestrator (implicit) | ✅ |
| `code-review-and-quality` | code-reviewer | ✅ |
| `adversarial-critic-checklist` | code-reviewer | ✅ |
| `code-factory` | code-orchestrator | ✅ |
| `compare` / `export` | common | ✅ |
| `long-context` | general | ✅ |
| `ai-slop-avoidance` | **article-writer, writing-orchestrator** | ❌ **MISSING** |
| `article-writing` | writing-orchestrator (implicit) | ❌ **MISSING** |
| `secure-code-guardian` | code-auditor (doc) | не обязателен (док-референс) |

## ГАП: writing-контур

- `ai-slop-avoidance` — **обязательная** зависимость `article-writer` (шаги 1, 7, 29) и `writing-orchestrator` (шаги 21, 118) — slop-audit обязателен перед handoff.
- На машине skill **отсутствует** (ни в W:\server2, ни в opencode-current).
- Это блокирует полноценную работу writing-контура: агент не сможет выполнить обязательный slop-audit.

## Роутер скилов — целостность

- `config/skills_graph.json` существует (mtime 2026-08-31 23:16): 61 nodes / 125 edges.
- Индексы: 8 routes, 5 capsules, 17 skills, 12 tools.
- `resolve_route.py` (graph-backed) использует этот граф — проверено выше, rc=0.
- Builder `build_skill_graph.py` на месте для регенерации.

**Вывод:** граф знаний для роутера **не потерян** и подключён. Но он отражает registry (который ещё не содержит всех реально используемых skills вроде `ai-slop-avoidance`), поэтому после добора скилов граф нужно **регенерировать**.

## План исправления

1. Довнести недостающие writing-скилы в corpus:
   - `ai-slop-avoidance` (скачать/скопировать официальный)
   - при необходимости `article-writing` шаблон
2. Обновить `config/skills_registry.json` (добавить в core/optional).
3. Обновить `config/skill_capsule_policy.json` (writing capsule → provided_skills).
4. Обновить `config/skill_to_route_map.json` (writing-route bindings).
5. Регенерировать `config/skills_graph.json`: `python scripts/router/build_skill_graph.py`.
6. Перепроверить `resolve_route.py` на writing-route.
7. Зафиксировать в README/MANIFEST/TRACKER.