# Coder Design Principles

Систематизация принципов из `workspace/агент кодер` под текущую парадигму OpenCode harness.

## Жёсткое ядро

1. **LLM свидетельствует, код решает.** LLM может предложить решение, объяснить риск или найти источник, но принятие контракта, stop criteria, schema validation, guard verdict и тестовый PASS делает код.
2. **Contract-first.** До реализации есть контракт входа, выхода, прав доступа, проверки и условия остановки. Контракт без автотеста или валидатора считается недействительным.
3. **Разделение ролей.** Coder пишет артефакт, tester/verifier запускает проверки, reviewer/critic оценивает результат, auditor оценивает процесс. Auditor не читает код; reviewer не чинит код.
4. **Детерминированный control plane.** State machine, бюджеты, retries, escalation и audit trail ведутся скриптами/валидаторами, не “ощущением” агента.
5. **Guard-first безопасность.** Для code/research orchestrator `doc_guard` является базовой защитой. Любой web/search/document/subagent output — недоверенный до guard PASS.
6. **Fail closed.** Нет схемы, нет guard, нет sandbox, нет теста, нет budget — блок, а не творческая догадка.

## Архитектурные принципы для кодеров

| Принцип | Как применять в harness | Проверка |
|---|---|---|
| Single responsibility | Каждый агент/модуль имеет одну обязанность и один тип результата | Контракт не содержит чужих полей |
| Cohesion > coupling | Декомпозиция хороша, если внутри модуля связность выше, чем связи наружу | Dependency map / review checklist |
| Stateless workers | Worker получает всё через контракт и не полагается на скрытую историю | Повторный запуск на тех же входах воспроизводим |
| Immutable contracts | Входные/выходные модели frozen/strict, лишние поля запрещены | JSON Schema / Pydantic / factory validator |
| Testable claims | Любое утверждение “сделано/работает/быстрее/безопасно” имеет команду проверки | tests_run или falsification field |
| Sandbox by default | Сгенерированный код и внешние tools считаются враждебными | no shell=True, timeout, path limits, no secrets |
| Observable process | Каждый шаг оставляет trace: вход, выход, hash, verdict, metrics | audit/state file не пустой |
| Satisficing over perfection | Решение достаточно хорошее для цели и риска, без бесконечной полировки | acceptance criteria выполнены |
| Sunset clause | Контракт имеет условие пересмотра при изменении архитектуры/рисков | registry/version/date или TODO-owner |

## ARIZ-light проектирование для coding tasks

Используется перед крупными изменениями, архитектурой, оптимизацией и конфликтом worker↔reviewer.

### Фаза 0 — Инициализация

- Формулируем UDE: что сейчас плохо наблюдаемо, без называния решения.
- Определяем границы: что в scope, что вне scope, какие данные/секреты нельзя трогать.
- Stop signal: задача сразу предлагает “поставить X/переписать Y”, но не описывает симптом.

### Фаза 1 — Декомпозиция

- Делим на 5–12 компонентов/модулей.
- Для каждого: одна ответственность, вход, выход, owner-agent, тест.
- Проверяем coupling/cohesion: если изменение одного модуля требует править всё — декомпозиция плохая.

### Фаза 2 — Операционная зона

- Рисуем flow: user/spec → orchestrator → worker → verifier/tester → reviewer → auditor/guard → done.
- Находим bottleneck: latency, schema drift, flaky tests, injection risk, missing MCP, bad docs.
- Метрика обязательна: время, error rate, coverage, false positives, budget.

### Фаза 3 — Противоречия

- Техническое противоречие: “если делаем A, улучшается X, но ухудшается Y”.
- Физическое противоречие: какой элемент должен иметь свойство P и не-P.
- Каждое противоречие должно иметь ≥3 фальсифицирующих наблюдения.

### Фаза 4 — ИКР

- ИКР формулируется как: “Система сама выполняет F существующими ресурсами, без смешения ролей, сохраняя guard/test/contract gates”.
- Запрещены ИКР, которые требуют магического доверия к LLM или внешнего ручного контроля вместо проверяемого gate.

### Фаза 5 — Ресурсы

- Сначала используем то, что уже есть: schemas, tests, logs, MCP inputSchema, doc_guard, factory_ctl, skills, references.
- “Можно переписать всё/поставить новый фреймворк” — не ресурс, а новое решение с риском.

### Фаза 6 — Слабые места

- FMEA для критических компонентов: отказ → причина → последствие → detection → mitigation.
- Проверяем архетипы: fixes-that-fail, shifting-the-burden, limits-to-growth, oscillating fixes.
- Если orchestrator получает больше видов сбоев, чем умеет обрабатывать, нужен новый deterministic gate.

### Фаза 7 — Контракты

- Для каждой пары компонентов: формат данных, допустимая задержка, error handling, retry/escalation, owner.
- Нет автотеста/валидатора — нет контракта.
- Контракт меняется через RFC/registry update, а не silently в агентском prompt.

## Минимальный контракт coding module

```json
{
  "module": "short-id",
  "goal": "observable outcome, not vague intent",
  "scope": {"in": ["paths/features"], "out": ["forbidden paths/features"]},
  "inputs": ["files/specs/context"],
  "outputs": ["files/artifacts/json"],
  "acceptance": ["test/lint/build/schema command"],
  "guard": "required before using untrusted tool/subagent output",
  "risks": ["security/perf/compat"],
  "sunset": "when to revisit this contract"
}
```

## Definition of Done for coder output

Coder output is **not DONE** until all are true:

1. Required files changed and no out-of-scope files changed.
2. Output JSON/contract validates.
3. Tests/build/lint relevant to the change were run or explicitly marked unavailable with reason.
4. Reviewer findings are either fixed or falsified with evidence.
5. `doc_guard` passed for any untrusted external/subagent context used.
6. State machine/factory controller accepts the transition.
7. Remaining risk and next step are recorded.

## TRIZ дополнение (из triz-agent)

См. TRIZ_FOR_CODERS.md: Provisor 4-метрика + STOP/CONTINUE, Generator 8 принципов -> 2-4 концепта, Critic 6 чеков, Kanban FSM, ARIZ 8x3. Для architecture/optimization/conflict включай triz-light; для простых задач — не включай.

## Tech debt и трекеры

- Tech debt отдельно: TECH_DEBT.md + config/tech_debt.json (Sunset Clause, severity, owner).
- Global Task Controller: GLOBAL_TASK_CONTROLLER.md + references/global-kanban/global_kanban.py (agents/statuses, report/board).
- Doc Controller: MANIFEST.md + references/agent-kirpichik/wp-*.md (WP-0 блокирует все).

## Mapping to current bundle

- Contracts registry: `config/tool_skill_routes.json`.
- Guard policy: `config/guard_policy.json`.
- Dynamic hook: `plugins/tool-skill-contract-router.ts`.
- Code factory agents: `agents/code-orchestrator.md`, `agents/coder-worker.md`, `agents/code-reviewer.md`, `agents/code-tester.md`, `agents/code-auditor.md`.
- Original source docs copied to: `references/agent-kirpichik/`.

## Динамические эвристики и NoAgents

- Эвристики: см. DYNAMIC_HEURISTICS.md — context-aware dispatch, progressive decomposition, budget-aware depth, risk-based guard, plateau detection.
- NoAgents: см. NO_AGENTS.md — детерминированный путь без LLM (CoderStub/CriticStub/Verifier/Guard P0/Schema/Kanban), stub mode, escalation в LLM только при необходимости.

## Source lineage

Derived from:

- `references/agent-kirpichik/ARCHITECTURE.md`
- `references/agent-kirpichik/CONTRACTS.md`
- `references/agent-kirpichik/AGENT_PROTOCOLS.md`
- `references/agent-kirpichik/TEST_STRATEGY.md`
- `references/agent-kirpichik/THREAT_MODEL.md`
- `references/agent-kirpichik/ARIZ_LIGHT_METHOD.md`
