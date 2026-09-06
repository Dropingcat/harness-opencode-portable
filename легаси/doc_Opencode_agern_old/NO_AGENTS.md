# NoAgents — наработки детерминированного пути без LLM

Режим, в котором задача решается **без вызова LLM-агентов**, только кодом, правилами и локальными инструментами. Нужен для: экономии бюджета, воспроизводимости, офлайна, безопасности (нет промпт-инъекции), скорости.

## 1. Когда включается NoAgents

| Условие | Пример | Решение |
|---|---|---|
| `task` тривиальна и покрывается шаблоном | "добавь LICENSE", "поправь импорт" | NoAgents: прямой edit + тест |
| `budget_left == 0` или `circuit breaker OPEN` | LLM недоступен | Fallback: rule-based |
| `tool_results` достаточно для PASS | Тесты уже зеленые | NoAgents: пропустить LLM, сразу Done |
| `risk == critical`, нужен детерминизм | Миграция схемы, секрет | NoAgents: только валидаторы, без LLM |
| `mode == sufficiency` + `iteration >= 3` | Плато, нет улучшения | NoAgents: synthesize_final без нового LLM |

Решение принимает Provisor/эвристика (`DYNAMIC_HEURISTICS.md`), оркестратор переключает ветку.

## 2. Что уже есть в harness как NoAgents

| Компонент | Где | Что делает без LLM |
|---|---|---|
| **CoderStub / CriticStub** | `references/workspace-wp/.../wp-2.md` → `coder_stub.py`, `critic_stub.py` | Детерминированно генерируют Artifact / CriticReport по keyword matching |
| **FixNotesAdapter** | `wp-2.md` → `fix_notes_adapter.py` | Преобразует findings → fix_notes (сортировка, дедупликация) |
| **Verifier (sandbox)** | `ARCHITECTURE.md` + `THREAT_MODEL.md` | Запускает tools внутри sandbox, хранит raw output при ошибке парсинга |
| **Factory controller** | `code-orchestrator.md` → `factory_ctl.py submit` | Валидирует контракт + state machine без LLM |
| **Guard P0** | `guard/src/session_guard.py` (stdlib only) | Детерминированные сигнатуры инъекций, без сети |
| **Schema generation** | `CONTRACTS.md` → `scripts/generate_schemas.py` | Генерирует JSON Schema из Pydantic без LLM |
| **Triz rule-based fallback** | `references/triz-agent/skills/triz_provisor/rule_based.py` | Оценивает feasibility/novelty без LLM |
| **Global Kanban** | `references/global-kanban/global_kanban.py` | Хранит статусы, не требует LLM |
| **Doc controller** | `MANIFEST.md` | Инвентаризация без LLM |

Все они работают в `stub mode` — полный цикл без единого LLM-вызова, что и есть NoAgents на практике (см. `ARIZ_ANALYSIS.md: Зависимость от LLM устранена — stub mode работает`).

## 3. Архитектура NoAgents ветки

```
[Spec + TaskContext] -> [NoAgents Router] -> [Heuristic choose]
        |-> trivial -> DirectEdit + Verifier -> CriticStub -> Done
        |-> schema  -> GenerateSchemas -> Validate -> Done
        |-> guard   -> SessionGuard P0 -> PASS/FAIL
        |-> triz    -> RuleBased Provisor/Critic -> Concepts
        -> если не покрыто -> эскалация в LLM ветку (с guard)
```

Правило: NoAgents ветка **никогда** не читает `reasoning` кодера, не видит историю итераций, не меняет артефакт через контроллер (Анти-ИКР из `ARIZ_ANALYSIS.md`).

## 4. Контракт NoAgents

```json
{
  "mode": "noagents",
  "allowed_tools": ["read","edit","bash","py_compile","pytest","session_guard","generate_schemas","global_kanban"],
  "forbidden": ["task (LLM dispatch)","webfetch без guard","LLM API"],
  "inputs": ["spec","context","fix_notes"],
  "outputs": ["artifact | critic_report | guard_verdict"],
  "acceptance": ["py_compile pass | pytest pass | schema valid | guard PASS"],
  "escalation": "если acceptance не достигнут за 2 итерации → переключить в LLM ветку с явным reason"
}
```

## 5. Эвристики переключения NoAgents ↔ LLM

- `if spec contains "sum|сумма|error|lazy|hack"` (из `wp-2.md` CoderStub) → NoAgents достаточно.
- `if tool_results contains "error|traceback|TODO"` → CriticStub без LLM дает FAIL.
- `if critic_report.uncertainty_score > 0.6` → требуется LLM (AMBIGUOUS).
- `if process_metrics.fix_repetition_rate > 0.5` → NoAgents зациклился, нужен LLM или эскалация к пользователю.

## 6. Пошаговый план внедрения

1. **WP-0 уже готов как NoAgents**: типы, модели, схемы — без внешних зависимостей (только pydantic/typing).
2. **Активировать stub mode в CI**: все unit/integration тесты гоняются без LLM (см. `TEST_STRATEGY.md: Stub-ability`).
3. **Добавить `mode=noagents` флаг в code-orchestrator**: если бюджет/риск/тривиальность → не диспатчить `task`, а вызвать локальные стабы/валидаторы.
4. **Покрыть guard P0**: `guard/src/session_guard.py` уже stdlib-only — использовать как первый gate в обеих ветках.
5. **Документировать переключение**: каждый `gk.report` должен указывать `mode=noagents|llm` в `message`.

## 7. Связь с остальными документами

- `CODER_DESIGN_PRINCIPLES.md` — ядро: "LLM свидетельствует, код решает" → NoAgents = крайний случай "код решает".
- `DYNAMIC_HEURISTICS.md` — решает, когда NoAgents достаточно.
- `TRIZ_FOR_CODERS.md` — rule-based fallback Provisor/Critic как пример NoAgents.
- `TECH_DEBT.md` — долги вида "нужен NoAgents для X" получают `kind=noagents`.
- `GLOBAL_TASK_CONTROLLER.md` — kanban хранит `mode` рядом с `status`.

## 8. Чек-лист NoAgents готовности

- [ ] `src/core` (WP-0) собирается без LLM.
- [ ] `coder_stub + critic_stub + fix_notes_adapter` проходят воспроизводимо (deterministic).
- [ ] `factory_ctl.py` валидирует контракты без LLM.
- [ ] `session_guard.py --json` дает вердикт без сети.
- [ ] `global_kanban.py` пишет статусы без LLM.
- [ ] CI прогоняет полный цикл в NoAgents за <10 сек.

## 9. Источники

- `references/workspace-wp/агент кодер/базовая документация/wp-0.md`..`wp-4.md` (stub-ability, deterministic)
- `references/workspace-wp/ARIZ_ANALYSIS.md` (Анти-ИКР, ресурсы)
- `references/triz-agent/skills/triz_provisor/rule_based.py` (fallback без LLM)
- `references/global-kanban/global_kanban.py` (агрегатор без LLM)
