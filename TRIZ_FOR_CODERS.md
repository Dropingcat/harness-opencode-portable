# TRIZ для кодеров в harness

Перенос полезных паттернов из `Z:\server\.hermes\profiles\_archive\triz-agent` в парадигму кодеров. Копия исходников в `references/triz-agent/`.

## 1. Зачем TRIZ кодеру

Кодовые задачи упираются в противоречия: быстро vs надежно, изолировано vs производительно, детальный лог vs объем, частый аудит vs нагрузка. TRIZ дает дисциплину формулировать ИКР и искать решение через ресурсы системы, а не через добавление сложности.

Применяется в двух режимах: **light** (фазы 0-7 за 1-2 часа на пилоте) и **full** (ArizLevel 0/1/2 для архитектуры/рефактора).

## 2. Что переносим из triz-agent

| Паттерн | Источник | Применение у кодеров |
|---|---|---|
| **Provisor: 4-метрика + STOP/CONTINUE** | `skills/triz_provisor` | Оценка итерации кодинга: completeness/coherence/feasibility/novelty → overall 0-10. Решает STOP_QUALITY / STOP_LIMIT / STOP_PLATEAU / CONTINUE |
| **Generator: 8 принципов + 2-4 концепта** | `skills/triz_generator` | На вход — задача + FactPack. На выход — conflicting_pairs, ИКР, technical/physical противоречия, operational zone/time, resources, 2-4 концепта с triz_principles_used и estimated_metrics |
| **Critic: 6 чеков + severity + post-валидация** | `skills/triz_critic` | domain_coverage, fact_concept_consistency, concept_diversity, source_specificity, triz_correctness, estimates_realism. Severity: critical/major/minor. Пост-валидация: запрещенные глаголы решения в ИКР |
| **Kanban FSM: QUEUE→GENERATOR→CRITIC→REWORK→DONE/FAILED** | `kanban/` | Оркестрация цикла кодер↔ревьюер↔аудитор через SQLite, seed, circuit breaker, retry 3 |
| **ARIZ 8 шагов × 3 уровня** | `references/triz-agent` Phase C docs | Для архитектурных задач: Level 0 (задача), Level 1 (система), Level 2 (надсистема). Каждый из 8 шагов имеет input/operation/output/validation_rule — проверка кодом |

## 3. Минимальный цикл для кодинга (Provisor-Generator-Critic)

```
[task_query + FactPack] -> [Generator: 8 принципов -> 2-4 концепта] -> [Critic: 6 чеков] -> [Provisor: оценка 4 метрик -> STOP/CONTINUE -> rework (max 3 / 5) -> synthesize_final]
```

### 3.1 Provisor — оценка

```python
completeness = min(1.0, len(concepts) / target)   # покрытие концептами
coherence    = 1 - (n_issues / n_checks)          # согласованность без issues
feasibility  = LLM оценка (fallback: rule-based по длине/деталям)
novelty      = LLM оценка (fallback: rule-based)
overall      = (completeness+coherence+feasibility+novelty)/4 * 10
improvement_delta = current - previous
```

Пороги из triz-agent: sufficiency `overall >= 7.0 / patience 2 / max 3`, optimality `overall >= 9.0 / patience 3 / max 5`. Стоимость ~$0.0014 / ~30 сек vs ~$0.0024 / ~50 сек.

Fallback: если LLM недоступен или circuit breaker OPEN → baseline rule-based оценка + STOP только по лимиту/качеству без LLM.

### 3.2 Generator — генерация концептов

Вход:

```json
{
  "task_id": "uuid",
  "task_query": "рефактор X без поломки Y",
  "context": {"budget":5000, "deadline_days":3},
  "iteration": 0,
  "mode": "sufficiency|optimality",
  "triz_memory": {"principles":{}, "contradiction_matrix":{}},
  "ariz_memory": {"steps":[]},
  "previous_critique": null
}
```

Выход: `GeneratorOutput {task_model, enhanced_model, conflicting_pairs, ikr, technical_contradictions, physical_contradictions, operational_zone, operational_time, resources, concepts[2-4], vepol_model, sources}`.

Каждый concept:

```json
{
  "id":"concept_001",
  "name":"адаптивный TTL",
  "resolved_contradictions":["contr_001"],
  "triz_principles_used":[22,26],
  "estimated_metrics":{"idealness":9.0,"feasibility":10.0,"cost_rub":2000,"time_days":90}
}
```

### 3.3 Critic — 6 чеков

| ID | Вопрос | Fail пример |
|---|---|---|
| domain_coverage | Покрыты ли все домены задачи? | Генератор пропустил security домен при кодинге auth |
| fact_concept_consistency | Концепты следуют из фактов? | Концепт требует Rust, но фактов про Rust нет |
| concept_diversity | Концепты разнообразны? | 3 концепта — вариации кеша, нет альтернативы |
| source_specificity | Источники конкретны (DOI/URL)? | Источник: "документация" без ссылки |
| triz_correctness | Принципы применены корректно? | Принцип 22 (обратить вред) применен без вреда |
| estimates_realism | Оценки реалистичны? | idealness 10 при cost 0 |

Severity → critical = auto-fix или reject, major = rework. Температура 0.0.

### 3.4 Rule-based fallback для кодеров

Если Critic/Provisor недоступны: используй эвристики из `references/triz-agent/skills/triz_provisor/rule_based.py` + `idealness` оценка. Не блокируй цикл — деградируй к sufficiency.

## 4. ARIZ 8 шагов для кодеров (light mapping)

| Шаг | Вход | Операция кодера | Выход | Валидация кодом |
|---|---|---|---|---|
| 0 Инициализация | UDE, границы | Сформулировать нежелательные эффекты без названия решения | UDE list + stakeholder map | UDE не содержит глаголов решения |
| 1 Декомпозиция | Границы | Разложить на 5-12 компонентов по VSM | Компоненты + coupling/cohesion | coupling<0.5, cohesion>0.6 |
| 2 Операционная зона | Компоненты | Нарисовать value stream + узкие места | Bottlenecks ranked | >=3 bottleneck с гипотезой |
| 3 Противоречия | Узкие места | Сформулировать ТП → ФП на уровне элемента | 1-3 ФП + 3 фальсификации | каждое ФП имеет элемент+свойство+P/не-P |
| 4 ИКР | ФП | Сформулировать satisficing ИКР + быстрый прототип | IKR + prototype plan | IKR достижим за 3-5 шагов |
| 5 Ресурсы | ИКР | Собрать 5 типов ресурсов (пространство/время/инфо/энергия/система) через РВС-оператор | Resource list | >=2 реальных ресурса на ФП, демонстрируемы |
| 6 Слабые места | ИКР+ресурсы | Архетипы + FMEA + FRT + закон Эшби | Weak spots ranked | критичность Severity*Occurrence*Detection, >20 → митигация |
| 7 Контракты | Всё | Записать тестируемые контракты с Sunset Clause | Contract list | нет автотеста → нет контракта |

Переход между фазами только при критерии готовности.

## 5. Когда включать TRIZ у кодеров

- Задача имеет явное противоречие (быстро vs качественно, изоляция vs perf) → включай Generator/Critic light.
- Архитектура/рефактор/оптимизация → полный ARIZ 0-2 + Provisor.
- Конфликт worker↔reviewer 2+ раунда → вызывай triz_critic как чеклист (6 чеков).
- Нет противоречия, простая задача → не включай, используй обычный contract-first.

## 6. Связь с текущим harness

- Контракт-реестр: `config/tool_skill_routes.json` → дополни `guard_required` + `triz_required` для optimization/architecture классов.
- Хук: `plugins/tool-skill-contract-router.ts` → добавь ветку для triz context route (см. ARCHITECTURE.md).
- Агенты: `code-orchestrator` уже читает `CODER_DESIGN_PRINCIPLES.md` → теперь также читает этот файл при `triz_required`.
- Метрики: логируй `completeness/coherence/feasibility/novelty/overall/improvement_delta` рядом с `ProcessMetrics` для ретроспективы.

## 7. Динамические эвристики и NoAgents

- Эвристики выбора стратегии — DYNAMIC_HEURISTICS.md.
- Детерминированный fallback — NO_AGENTS.md (WP-0 stubs, rule-based Provisor, Guard P0, factory_ctl).

## 8. Что скопировано и где

- `references/triz-agent/KANBAN.md`, `TODO.md`, `README.md`, `SOUL.md`, `CHANGELOG.md`, `main.py`, `api.py` — общий цикл и статусы.
- `references/triz-agent/skills/triz_provisor/*` — оценка и STOP-логика.
- `references/triz-agent/skills/triz_generator/*` — генерация концептов.
- `references/triz-agent/skills/triz_critic/*` — 6 чеков.
- `references/triz-agent/kanban/*` — FSM и storage.
- `references/global-kanban/global_kanban.py` — глобальный контроллер (см. GLOBAL_TASK_CONTROLLER.md).
