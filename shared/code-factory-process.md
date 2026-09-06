# Shared Code Factory Process

> Module-owned adapted runtime process. Source lineage: `W:\server2\shared\code-factory-process.md`.

## Архитектура

Фабрика кода — иерархическая мультиагентная система:

```text
Пользователь
   │
   ▼
code-orchestrator
   ├─ coder-worker
   ├─ code-reviewer
   ├─ code-tester
   └─ code-auditor
```

### Роли

| Роль | Тип | Задача |
| --- | --- | --- |
| `code-orchestrator` | primary | декомпозиция, распределение, контроль, эскалация |
| `coder-worker` | subagent | пишет модуль/функцию по контракту |
| `code-reviewer` | subagent | критикует код и даёт фальсифицируемые замечания |
| `code-tester` | subagent | пишет/запускает тесты |
| `code-auditor` | subagent | оценивает процесс, не код |

## Контракты делегации

Каждая делегация идёт через `task` с жёстким контрактом:

```text
goal: [что сделать]
context: [пути, данные, ограничения]
output: [что вернуть]
acceptance: [критерии приёмки]
budget: [лимит шагов/времени]
```

### Контракт воркера
- вход: спецификация модуля
- выход: JSON с кодом и описанием
- приёмка: код компилируется, соответствует интерфейсу, покрыт тестами

### Контракт ревьюера
- вход: код воркера + спецификация
- выход: `APPROVE | REQUEST_CHANGES` + comments[]
- приёмка: каждое замечание конкретно и фальсифицируемо

### Контракт тестера
- вход: код + спецификация
- выход: PASS/FAIL, passed/failed, coverage
- приёмка: тесты реально запускались

### Контракт аудитора
- вход: метаданные процесса, **не код**
- выход: `APPROVE | REJECT | REQUEST_CHANGES | INVALID_INPUT`
- приёмка: вердикт обоснован и не смешивает роли

## Валидация контрактов кодом

Выходы всех агентов — строго структурированный JSON, валидируемый кодом, не LLM.

Поток:

1. агент пишет JSON в файл;
2. orchestrator делает один вызов `factory_ctl.py submit ...`;
3. контроллер валидирует контракт, применяет state machine и пишет audit.

Module-owned runtime path:

```text
scripts/code-factory/factory_ctl.py
scripts/code-factory/contract_validator.py
scripts/code-factory/code_factory_runner.py
```

State path должен задаваться через env или явный `--state`, не через hardcoded Linux path. Канонический module-owned path: `${OPENCODE_HARNESS_ROOT}/scripts/code-factory/factory_ctl.py`.

## Обязательные проверки

| Агент | Обязательные поля | Проверки |
|---|---|---|
| worker | module, code, description | непустые поля |
| reviewer | module, verdict, comments[] | verdict enum, comment fields, falsification |
| tester | module, result, passed, failed, coverage | PASS/FAIL, числа, coverage 0-100 |
| auditor | verdict, justification, process_analysis | verdict enum, justification, process fields |
| experimenter | metric, baseline, best_result, experiments | baseline/best_result числа |

## Правила

1. **LLM свидетельствует, код решает.**
2. Невалидный выход → retry (max 2) → block.
3. Reviewer без `falsification` → INVALID.
4. Auditor не принимает код.
5. Всё через файлы, не через chat JSON.
6. Код без тестов не принимается.

## State machine

```text
PENDING -> RUNNING -> PASSED -> DONE
                  -> FAILED
                  -> AMBIGUOUS
                  -> BLOCKED
```

Stop criteria приоритетом:

1. `requires_user`
2. `auditor_block`
3. `iteration_limit`

Budget exhaustion должен давать `BLOCKED` или `PARTIAL` по policy profile, но не ложный success.

## Трекер задач

Используется глобальный kanban controller. Канонический module-owned import path: `${OPENCODE_HARNESS_ROOT}/references/global-kanban/global_kanban.py`. На Windows путь к БД должен задаваться явно (`${OPENCODE_HARNESS_ROOT}/.kanban.db` или env), а не подразумеваться Linux-путём.

## Guard boundary

Если используется web/search/document/subagent output, перед synthesis/handoff обязателен `doc_guard` по `config/guard_policy.json`.

## Экспериментальный контур

Оптимизационные задачи запускают `experimenter` / `autoresearch` только при наличии:

- измеримой метрики;
- benchmark command;
- budget allowance;
- stop rule при отсутствии прогресса.

## Формат отчёта

```markdown
## Отчёт фабрики: [Задача]

**Статус:** ✅ / ⚠️ / ❌
**Модули:** [список]
**Ревью:** [вердикты]
**Тесты:** [результаты]
**Трибунал:** [если был]
**Эксперименты:** [если был контур autoresearch]
**Бюджет:** [потрачено/лимит]
**Трекер:** [task_id]

### Итог
[что сделано]

### Проблемы
[что не решено]

### Память
[какой lesson добавлен]
```

## Stage 2 state ownership (2026-09-06)

Authoritative state теперь event-sourced. Reviewer/tester/auditor outputs после contract validation записываются как typed evidence. Они не имеют права непосредственно присваивать `PASSED`, `FAILED`, `BLOCKED` или `DONE`. Глобальная projection вычисляется только `state_reducer.py` из hash-chained event history и frozen gate-policy snapshot. Для новых runs обязательный default GateSet: reviewer + tester + auditor. Подробности: `STATE_REDUCER_ARCHITECTURE.md` и `STAGE2_ATTEMPT_GATESET_STATE_REDUCER_2026-09-06.md`.
