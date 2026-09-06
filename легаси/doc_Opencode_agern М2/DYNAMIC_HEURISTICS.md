# Динамические эвристики для кода и валидации

Дополнение к `CODER_DESIGN_PRINCIPLES.md` и `TRIZ_FOR_CODERS.md`. Эвристика здесь — не "магия LLM", а детерминированное правило выбора стратегии, которое адаптируется по сигналам процесса.

## 1. Принцип динамической эвристики

> Статическое правило ("всегда делай X") ломается на разнородных задачах. Динамическая эвристика выбирает X(t) = f(сигналы, бюджет, риск, история).

Сигналы: `task_complexity`, `tool_results`, `critic findings`, `process_metrics`, `guard_verdict`, `budget_left`, `iteration`, `kanban_phase`.

Инвариант: эвристика **предлагает**, код **решает**. Любое решение эвристики должно быть проверяемо отдельным валидатором.

## 2. Эвристики для кода (генерация)

| Эвристика | Сигнал | Правило | Пример |
|---|---|---|---|
| **Complexity-aware dispatch** | `spec_tokens`, `files_count`, `dependencies` | `simple (<1 файл, <100 строк) → CoderStub / fast model; complex → polza/deepseek + decomposition` | `coder_run(model_class)` выбирается не фиксированно, а по оценке сложности |
| **Progressive decomposition** | `iteration`, `fix_repetition_rate` | `if iteration==0 → крупная декомпозиция (3-5 модулей); if fix_repetition_rate>0.3 → мельче (5-8) + добавить verifier` | Оркестратор переразбивает WP при осцилляции |
| **Resource-aware tool choice** | `SearXNG availability`, `MCP latency`, `local corpus hit` | `if local_search hit → используй его; else if SearXNG ok → searxng_search; else → webfetch fallback` | Source-fetcher динамически выбирает канал |
| **Budget-aware depth** | `budget_left`, `cost_per_iteration` | `if budget_left < 20% → sufficiency mode (3 итерации, 7.0); else optimality (5, 9.0)` | Provisor из triz-agent: тот же паттерн |
| **History-driven fixNotes** | `previous findings`, `semantic_diff_ratio` | `if diff_ratio < 0.05 → усилить fix_notes (добавить пример, указать файл:line); if >0.5 → сократить` | FixNotesAdapter адаптирует детализацию |
| **Canary-first** | `risk=high`, `files_touched` | `сначала патч 1 файла + тест, затем остальные; если canary PASS → расширяй` | Инкрементальная имплементация вместо big-bang |

Все эвристики — чистые функции `choose_strategy(signals) -> strategy_id`, без сайд-эффектов, тестируются property-based.

## 3. Эвристики для валидации (проверка)

| Эвристика | Сигнал | Правило | Валидатор |
|---|---|---|---|
| **Risk-based guard strictness** | `untrusted_tool_used`, `external_doc` | `if web/search/document/subagent → guard=mandatory+fail-closed; if local-only → guard=warn` | `config/guard_policy.json` |
| **Quality-gated critic depth** | `overall` из Provisor | `if overall<5 → critic severity=critical only; if >7 → все 6 чеков` | `skills/triz_critic/validator.py` |
| **Falsifiability gate** | `finding without falsification` | `reject finding, вернуть критику на доработку` | `factory_ctl.py submit reviewer` |
| **Schema drift heuristic** | `contract_violations_count` | `if >0 → block + запустить generate_schemas; if 0 → pass` | `scripts/generate_schemas.py` |
| **Flaky-test heuristic** | `tool_usage_consistency=false` | `if верификатор нестабилен → повторить 2 раза, затем BLOCK` | `ProcessMetrics.tool_usage_consistency` |
| **Sunset heuristic** | `now > sunset_at` | `debt/status → REVIEW_REQUIRED, kanban phase=tech_debt` | `TECH_DEBT.md` |
| ** plateau detection** | `improvement_delta < 0.1 за 2 итерации` | `STOP_PLATEAU → synthesize_final вместо продолжения` | `triz_provisor/decide_continue()` |

Ключевое: валидация тоже динамическая — пороги `threshold`, `patience` берутся из `mode=sufficiency|optimality`, а не хардкодятся.

## 4. Связь с TRIZ

Динамические эвристики — это реализация приемов:

- **Принцип 15 (Динамичность)** — менять структуру/параметры системы во время работы (sandbox local vs Docker, sufficiency vs optimality).
- **Принцип 23 (Обратная связь)** — использовать `process_metrics` и `critic_report` для коррекции следующего шага.
- **Принцип 10 (Предварительное действие)** — pre-compute metrics до вызова LLM, чтобы не тратить бюджет.
- **Переход в новое измерение** — вместо цикла `retry forever` → триггерный аудит/проверка.

## 5. Реализация в harness

### 5.1 Конфиг

```json
// config/dynamic_heuristics.json (создать при нужде)
{
  "version": 1,
  "heuristics": {
    "dispatch": {"simple_threshold_files": 1, "simple_threshold_tokens": 800},
    "budget": {"sufficiency_threshold": 7.0, "optimality_threshold": 9.0},
    "guard": {"mandatory_tools": ["webfetch","task","research_papers","extract_document"]}
  }
}
```

### 5.2 Код

- `plugins/tool-skill-contract-router.ts` — уже динамически выбирает `contextRoutes` по `when_regex` (эвристика маршрутизации).
- `mcp/launchers/_runner.py` — должен выбирать `OPENCODE_BIN` и `RUNS_BASE` из env (эвристика окружения).
- `references/triz-agent/skills/triz_provisor/rule_based.py` — пример rule-based fallback без LLM (эвристика деградации).
- `references/global-kanban/global_kanban.py` — хранит `progress` как сигнал для следующей эвристики.

### 5.3 Тест

Каждая эвристика имеет:

- unit-тест на 3 режима (low/medium/high сигнала),
- property-based тест: любой валидный сигнал → валидная стратегия,
- E2E: эвристика + stub mode проходят без LLM.

## 6. Анти-паттерны

- Эвристика без сигнала (хардкод) → удалить.
- Эвристика меняет артефакт напрямую → запрещено, только предлагает стратегию оркестратору.
- Эвристика без валидатора → нет метрики, нет доверия.
- Эвристика требует секретов → вынести в env, иначе fail-closed.

## 7. Связь с noAgents

Когда эвристика решает `no_agent_needed=true`, управление уходит в `NO_AGENTS.md` — детерминированный путь без LLM.
