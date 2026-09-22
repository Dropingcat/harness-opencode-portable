# TRIZ-Agent Analysis: что извлечь как skill/MCP/плагин

> Источник: `/home/orangepi/.hermes/profiles/_archive/triz-agent/` (v2.1.1, Phase D завершена, 494+ тестов).
> Формат: факты + опции, решение за пользователем (принцип сервера).
> Дата: 2026-08-27

## Что это

Зрелый production-профиль Hermes Agent для решения изобретательских задач по ТРИЗ/АРИЗ/Веполь. Архивирован (июль 2026), но полностью функционален.

### Архитектура (3 роли + FSM)
```
Provisor (супервизор)
  → Generator (8 шагов АРИЗ → 2-4 концепции)
  → Critic (6 проверок по чеклисту, severity, post-валидация)
  → Provisor (4 метрики: completeness+coherence кодом, feasibility+novelty LLM)
  → STOP (quality/plateau/limit) или rework (max 3-5 итераций)
```

### Компоненты
| Модуль | Что | Тесты | Ценность для нас |
|--|--|--|--|
| `memory/triz_memory.py` | 18 принципов ТРИЗ + contradiction matrix (7 пар) + ИКР templates + ВПР resources | 20 | **HIGH** — knowledge base для experimenter/tribunal |
| `memory/ariz_memory.py` | 8 шагов АРИЗ (input/operation/output/validation_rule) | 20 | **HIGH** — structured problem-solving |
| `ariz/` (core, base, tree, validator, prompts, steps, fsm_integration) | FSM 8-step, 3 уровня (QUICK/DETAILED/EXPERT), ветвление | 272 | **HIGH** — contradiction resolution engine |
| `skills/triz_generator/` | 8 шагов АРИЗ → концепции | 14 | **MED** — можно как skill |
| `skills/triz_critic/` | 6 проверок, severity, post-валидация (запрет глаголов-нарушителей) | 16 | **HIGH** — adversarial checklist |
| `skills/triz_provisor/` | метрики, STOP/CONTINUE, synthesis, rule-based fallback | 13 | **HIGH** — stop-criteria кодом |
| `skills/researcher/` | arXiv + DDG + Sci-Bot search → research_bridge к АРИЗ | 97 | **MED** — у нас есть source-fetcher |
| `metrics/` | JSONL-логгер, aggregator (completeness/coherence/feasibility/novelty) | — | **MED** — метрики итераций |
| `resilience/` | Circuit breaker + retry + idempotency | — | **MED** — у нас есть dispatch-retry |
| `kanban/` | SQLite, 6 статусов, idempotency | — | LOW — у нас global_kanban |
| `api.py` | Flask HTTP API (6 endpoints: health/submit/status/result/metrics/kanban) | — | **MED** — MCP candidate |
| `input/analyzer.py` | StructuredInputAnalyzer (40 тестов) | 40 | **MED** — для claim-parser |

---

## Оценка: skill vs MCP vs плагин

### Вариант 1: SKILLS (рекомендую — high ROI, low effort)

Извлечь knowledge base + methodology как 2-3 opencode skills:

**Skill 1: `triz-problem-solving`** (для experimenter, code-orchestrator, research-orchestrator)
- Содержание: 18 принципов ТРИЗ + contradiction matrix + ИКР templates + ВПР resources (из `memory/triz_memory.py`)
- Применение: при оптимизации/дизайне — найти противоречие, применить принцип, сформулировать ИКР
- Формат: SKILL.md с embedded knowledge (принципы, матрица, шаблоны) + workflow (найти противоречие → ИКР → принципы → ресурсы)
- Усилие: low (копирование knowledge base в SKILL.md)

**Skill 2: `ariz-contradiction-resolution`** (для tribunal-judge, code-auditor, fact-checker)
- Содержание: 8 шагов АРИЗ (из `memory/ariz_memory.py`) + workflow
- Применение: при конфликте воркер↔ревьюер, при верификации клаймов — структурированный анализ противоречия
- Формат: SKILL.md с 8-step workflow (анализ→модель→ИКР→ресурсы→...)
- Усилие: low

**Skill 3: `adversarial-critic-checklist`** (для code-reviewer, tribunal-judge)
- Содержание: 6 проверок Critic + severity (critical/major) + post-валидация (запрет глаголов-нарушителей)
- Применение: adversarial review — структурированная критика по чеклисту, не "мне не нравится"
- Формат: SKILL.md с checklist + severity labels + post-validation rules
- Усилие: low
- Связь с нашими: дополняет `doubt-driven-development` (R2) — doubt-driven = цикл, adversarial-critic = чеклист

### Вариант 2: MCP SERVER (мед, high effort — если нужна runtime FSM)

Извлечь `ariz/` (FSM 8-step) как MCP server для opencode:
- MCP tools: `ariz_analyze_task`, `ariz_run_step`, `ariz_get_contradiction`, `ariz_apply_principle`, `ariz_formulate_ikr`
- State: FSM сохраняется между вызовами (как session_context_epoch)
- Плюс: настоящий stateful FSM, ветвление, рекурсия
- Минус: high effort (MCP server + transport + state management), усложнение архитектуры
- Когда: если нужен интерактивный многошаговый АРИЗ с сохранением состояния

### Вариант 3: PLUGIN (мед — для metrics/stop-criteria)

Извлечь `metrics/` + `skills/triz_provisor/` (stop-criteria) как opencode plugin:
- Hook: после каждой итерации worker↔reviewer → считать completeness/coherence → STOP/CONTINUE
- Плюс: автоматический stop-criteria (сейчас factory_ctl.py делает проще)
- Минус: дублирование с factory_ctl.py (наш контроллер уже ведёт state machine)
- Когда: если нужны более сложные метрики (feasibility/novelty через LLM, не только verdict)

---

## Рекомендация (моя, как оркестратора)

**Вариант 1 (3 SKILLS) — highest ROI, low effort.** TRIZ knowledge base (18 принципов, contradiction matrix, ИКР) — уникальная ценность, которой нет ни в одном из 180 наших skills. АРИЗ 8-step — структурированный problem-solving. Adversarial critic checklist — структурированная критика (дополняет doubt-driven-development).

**НЕ рекомендую** Вариант 2 (MCP) сейчас — high effort, наш factory_ctl.py уже ведёт FSM. Если позже понадобится интерактивный АРИЗ с stateful branching — тогда MCP.

**НЕ рекомендую** Вариант 3 (plugin metrics) — дублирование с factory_ctl.py. Metрики Provisor (feasibility/novelty через LLM) — интересная идея, но это расширение factory_ctl, не отдельный плагин.

## Что требует решения пользователя

1. **Извлечь 3 skills (Вариант 1)?** — triz-problem-solving, ariz-contradiction-resolution, adversarial-critic-checklist. Low effort, high ROI.
2. **Какой scope?** — только knowledge base (принципы/матрица/ИКР — минимальный) или + workflow (8-step АРИЗ как процесс — полный)?
3. **MCP server (Вариант 2) — позже?** — если нужен stateful АРИЗ с ветвлением.
4. **Сохранить архив как reference?** — переместить в `~/Документы/doc_guard/references/triz-agent/` для изучения кода.

## Файл
`/home/orangepi/Документы/doc_guard/docs/TRIZ_AGENT_ANALYSIS.md`