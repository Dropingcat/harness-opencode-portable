# ИИ-агент — это система, а не промпт: исследовательский отчёт

Дата проверки источников: 2026-09-12.

## Метод и границы

Исследование опирается прежде всего на актуальную документацию в `E:\Documents\Документы\doc_Opencode_agern-new`. Архивные, legacy- и backup-копии не считались независимыми подтверждениями. Для внешней сверки использованы официальные материалы Anthropic, OpenAI, LangGraph и OWASP, а также оригинальная работа ReAct.

## Ключевые выводы

1. **Workflow и агент различаются владельцем следующего шага.** В workflow маршрут задаёт код; в агенте модель выбирает действие во время исполнения. На практике системы часто гибридны. Уверенность: высокая.
2. **Автономность — средство работы с неопределённостью, а не самоцель.** Известный стабильный маршрут лучше оставлять детерминированным; усложнение должно подтверждаться evals. Уверенность: высокая.
3. **Функциональное ядро не равно production-архитектуре.** Модель, инструкции и tools достаточны для демонстрации, но управляемой системе также нужны state, contracts, validators, budgets, stop criteria, trust boundaries и audit. Уверенность: высокая.
4. **Базовый цикл строится вокруг обратной связи:** observe → decide/plan → act → observe → update state → validate/stop. Tool output — наблюдение, а не автоматически истинный факт. Уверенность: высокая.
5. **Planning и execution стоит разделять логически, но не обязательно по разным агентам.** Для длинных задач план полезно хранить как проверяемый артефакт. Уверенность: высокая.
6. **Паттерны имеют разные условия применимости.** Routing требует устойчивых категорий; parallelization — независимых ветвей; evaluator-optimizer — ясной рубрики и stop criteria; manager-worker — динамической декомпозиции; handoff — реальной передачи ответственности. Уверенность: высокая.
7. **Multi-agent оправдан параллелизмом, изоляцией контекста или специализацией.** При тесных зависимостях и общем изменяемом состоянии он повышает стоимость и сложность координации. Уверенность: высокая.
8. **Tool calling — API-контракт.** Нужны узкая ответственность, typed schema, серверная валидация и structured errors; для side effects — least privilege, timeout, идемпотентность, bounded retries, audit и approval. Уверенность: высокая.
9. **Run state и long-term memory имеют разные жизненные циклы.** Память должна быть избирательной, иметь provenance и write policy, а не служить полным журналом или authoritative state. Уверенность: высокая.
10. **Context engineering — отбор минимального высокосигнального набора данных для следующего шага.** Полезны just-in-time retrieval, progressive disclosure, compaction и узкие handoff-пакеты. Уверенность: высокая.
11. **Stop criteria и budgets должны контролироваться кодом.** Нужно различать success, partial, blocked и unresolvable; timeout и исчерпание бюджета не равны успеху. Уверенность: высокая.
12. **Тестировать нужно результат, контракты и траектории.** Нужны unit-, contract-, scenario-, regression- и adversarial-тесты; открытым задачам нельзя навязывать единственный правильный маршрут. Уверенность: высокая.
13. **Observability связывает outcome, trajectory и ресурсы.** Полезны task success, tool errors, invalid arguments, iterations, handoffs, latency, token/cost usage, guard blocks и human interventions. Уверенность: высокая.
14. **Недоверенные данные требуют отдельной границы доверия.** Документы, web pages и tool outputs являются данными, а не инструкциями; prompt injection нельзя устранить одним фильтром. Уверенность: высокая.

## Расхождения и оговорки

- Термин «агент» не полностью стандартизирован; в статье лучше использовать операционное определение через владельца следующего шага.
- OpenAI описывает функциональный минимум как model + tools + instructions; локальная документация описывает более строгий production-контур. Это разные уровни детализации, а не прямое противоречие.
- Manager и handoff — допустимые общие паттерны, хотя локальный harness ограничивает persona-to-persona chains. Локальную политику нельзя выдавать за универсальный запрет.
- Trace grading полезен для инвариантов и запрещённых действий, но для открытых задач важнее end-state evaluation: корректных траекторий может быть несколько.
- Нельзя обобщать внутренние проценты и оценки расхода из конкретных multi-agent экспериментов Anthropic.
- Typed schema снижает структурные ошибки, но не гарантирует смысловую корректность, безопасность или истинность аргументов.

## Мини-примеры

1. **Возврат заказа:** lookup и форматирование статуса — workflow; агентный выбор нужен лишь при неоднозначном запросе. Generic CRM tool с правами изменения и удаления — анти-паттерн.
2. **Параллельное исследование регионов:** fan-out полезен для независимых рынков, но вреден, если ветви постоянно зависят от общего mutable state.
3. **Повтор платежа после timeout:** слепой retry может удвоить операцию; нужны idempotency key, запрос статуса и различимые состояния ошибки.
4. **Память как полный лог:** возврат всех прошлых tool outputs в prompt увеличивает шум, стоимость и риск повторной prompt injection.

## Локальные источники

- `ARCHITECTURE.md`
- `UNIFIED_ORCHESTRATION_PRINCIPLES.md`
- `UNIFIED_MODULE_SCOPE.md`
- `MEMORY_POLICY.md`
- `shared/orchestration-patterns.md`
- `CODER_DESIGN_PRINCIPLES.md`
- `agents/code-orchestrator.md`
- `references/agent-kirpichik/CONTRACTS.md`
- `references/agent-kirpichik/TEST_STRATEGY.md`
- `references/agent-kirpichik/THREAT_MODEL.md`
- `NO_AGENTS.md`
- `DYNAMIC_HEURISTICS.md`
- `DEEP_REVIEW_2026-09-06.md`
- `E:\Documents\Документы\workspace\агент кодер\базовая документация\AGENT_PROTOCOLS.md`

## Внешние источники

- Anthropic, “Building effective agents”: https://www.anthropic.com/research/building-effective-agents
- OpenAI, “A practical guide to building agents”: https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/
- OpenAI, “Agents”: https://platform.openai.com/docs/guides/agents
- OpenAI, “Function calling”: https://developers.openai.com/api/docs/guides/function-calling
- OpenAI, “Safety in building agents”: https://developers.openai.com/api/docs/guides/agent-builder-safety
- OpenAI, “Evaluation best practices”: https://developers.openai.com/api/docs/guides/evaluation-best-practices
- LangGraph, “Memory”: https://docs.langchain.com/oss/python/langgraph/add-memory
- Anthropic, “Effective context engineering for AI agents”: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic, “How we built our multi-agent research system”: https://www.anthropic.com/engineering/multi-agent-research-system
- Yao et al., “ReAct”: https://arxiv.org/html/2210.03629
- OWASP, “LLM01:2025 Prompt Injection”: https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- OWASP, “LLM06:2025 Excessive Agency”: https://genai.owasp.org/llmrisk/llm062025-excessive-agency/
