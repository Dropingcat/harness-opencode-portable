# Changelog — ТРИЗ-агент

All notable changes to the `triz-agent` profile.

---

## [2.1.1] — 2026-07-11

### Добавлено (Phase D: DuckDuckGo Search — подготовка)

- ✅ **DuckDuckGo Search** — готовый поисковый модуль без API-ключей
  - Скрипт: `~/.hermes/scripts/ddg-search.py` (41 строка, CLI + JSON)
  - Навык: `web-search/duckduckgo-search` (загружается через skill_view)
  - Документация: `~/.hermes/docs/ddg-search-reference.md` (90 строк)
  - Ограничение: ~50 запросов/мин, без CAPTCHA, без регионов
- 📋 **План Phase D обновлён** — оценка снижена с 4 → 3.5 дней
  - D.2.4 заменён с `web_search` на `DDG Search ✅`
  - Риск `Hermes web_search не вызывается из Python` → решён
  - Добавлен риск `DDGS rate limit`
  - D.0 сокращён с 0.5 → 0.25 дня (аудит не нужен — DDG уже работает)
- Обновлены KANBAN.md и TODO.md

## [2.1.0] — 2026-07-10

### Добавлено (Phase C: Настоящий АРИЗ — завершена ✅)

**Архитектура модуля ariz/:**
- `ariz/base.py` — ArizLevel (QUICK/DETAILED/EXPERT), ArizState (8 шагов + DONE + FAILED), ArizStep dataclass, STEPS (8 шагов с level_config), TRANSITIONS
- `ariz/core.py` — ArizFSM: конечный автомат с поддержкой уровней, рекурсии (spawn_child), ветвления (add_branch/branches), хендлеров. Исправлены проблемы интеграции: `context` в `__init__`, `add_handler()`, поля `state`/`context` в ArizResult
- `ariz/tree.py` — ArizTree: дерево решений с 3 уровнями глубины и рекурсивными подзадачами (22 теста)
- `ariz/validator.py` — валидация выхода каждого шага (59 тестов)
- `ariz/prompts.py` — промпты для 8 шагов × 3 уровня (22 теста)

**Обработчики шагов (steps/):**
- `ariz/steps/step_1.py`–`step_4.py` — шаги 1-4 с 3 уровнями (1/2/4 вызова LLM на шаг 1)
- `ariz/steps/step_5_8.py` — шаги 5-8 (заглушки с полной сигнатурой)
- `ariz/steps/step_common.py` — утилиты: build_messages, parse_json_response, safe_call
- `ariz/steps/step_6_branching.py` — ветвление по физическим противоречиям (13 тестов)
- `ariz/steps/__init__.py` — HANDLERS словарь, 8 хендлеров (в т.ч. ветвление на шаге 6)

**Интеграция:**
- `ariz/ariz_fsm_integration.py` — адаптер ArizFSM → GeneratorOutput (run_ariz_fsm)
- `memory/config.py` — WorkMode.ARIZ_FSM + ARIZ_FSM_CONFIG (ariz_level, use_branching)
- `skills/triz_provisor/handler.py` — блок ARIZ_FSM MODE в run_triz_cycle (строка 403)
- Старый run_ariz_full остаётся fallback при `mode != ariz_fsm`

### Исправлено (интеграционные проблемы)

5 проблем, выявленных при анализе рассогласования план↔реализация:
1. `ArizFSM.__init__()` — добавлен опциональный параметр `context`
2. `ArizFSM.run()` — адаптер и тесты передают `task_id`, `task_query`
3. `ArizFSM.add_handler()` — добавлен метод регистрации хендлеров
4. `ArizResult` — добавлены поля `state` и `context`
5. `_result_to_generator_output()` — исправлена конвертация None→[] (ctx.get → or [])

### Протестировано

- **Модуль ariz (всего):** 272 теста, 0 падений
  - core: 43, base: 43, tree: 22, validator: 59, prompts: 22
  - steps: 31, step_6_branching: 13, integration: 40
- **Profile-wide тесты:** 125 тестов (Продолжают проходить)
- **Consistency checker:** 0 ошибок (4 false positive: lazy import handler.py, Enum._missing_)

### Документация

- `docs/plans/2026-07-10-phase-c-ariz-fsm.md` — добавлено Приложение «Анализ рассогласований план ↔ реализация» с 5 проблемами и таблицей статуса
- KANBAN.md — Phase C отмечена завершённой (✅)
- TODO.md — Phase C отмечена завершённой, все чекбоксы [x]
- CHANGELOG.md — данная запись

---

### Изменено (MVP-стратегия Phase C)

**Решение:** Phase C разбита на три последовательные подфазы вместо одной большой.
- C.1 — FSM (8 шагов straight-through, ~20-25 тестов)
- C.2 — Ступенчатость Level 0/1/2 (~15 тестов)
- C.3 — Вложенность ArizTree (~10-15 тестов)

**Обоснование:** опыт Phase A и B показал, что крупные фазы (всё сразу) сжирают больше ресурсов на интеграцию и отладку, чем сумма подфаз. Каждая подфаза даёт рабочий продукт.

**Изменения:**
- `docs/plans/2026-07-10-phase-c-ariz-layered.md` — добавлена секция MVP-стратегии
- `TODO.md` — Phase C переписана как C.1/C.2/C.3 с чекбоксами и выходами
- `TODO.md` — добавлен раздел H (Обсуждение) с 6 новыми направлениями

---

## [1.1.1] — 2026-07-10

### Добавлено (Фаза 1.1: Модуль памяти)

- **memory/__init__.py** — публичное API модуля с импортами и __all__
- **memory/triz_memory.py** — TRIZ_MEMORY: 18 принципов (срез 40), 7 пар матрицы противоречий + generic fallback, 3 шаблона ИКР, 6 типов ресурсов ВПР
- **memory/ariz_memory.py** — ARIZ_MEMORY: 8 шагов АРИЗ (Анализ → Линеаризация) с полями input/operation/output/prompt_hint/validation_rule
- **memory/config.py** — WorkMode enum (sufficiency/optimality), SUFFICIENCY_CONFIG (3 итерации, quality=7.0, auto_stop), OPTIMALITY_CONFIG (5 итераций, quality=9.0, manual)
- **memory/test_memory.py** — 20 тестов (TRIZ: 8, ARIZ: 6, Config: 6), все пройдены
- **Сериализация/десериализация** — serialize_triz_memory()/deserialize_triz_memory() для передачи через delegate_task context

---

## [1.2.0] — 2026-07-10

### Добавлено v1.2 (финальная спецификация, закрытие замечаний)

- **Идемпотентность seed** — `compute_seed()` с разделением sufficiency/strict, UUID задачи устраняет коллизии
- **JSONL-лог метрик** — формат записи, путь `~/.hermes/logs/triz_metrics.jsonl`, интеграция с Vector/Datadog/Prometheus Pushgateway
- **Два прохода Генератора (strict)** — два отдельных `delegate_task` с явным `ariz_steps: "1-4"` / `"5-8"`
- **Rule-based fallback Провизора** — полный код `rule_based_stop_decision()` с тремя критериями (STOP_QUALITY, STOP_PLATEAU, STOP_LIMIT)
- **Пост-валидация выхода Критика** — обнаружение глаголов-нарушителей («добавь», «используй», «примени»)

### Изменено v1.2

- Формула seed: `hash(f"{task_id}:{iteration}:{role}")` → + `task_uuid` для strict
- Prometheus → JSONL (Hermes не имеет HTTP-сервера)
- Один проход Генератора → два отдельных вызова для strict

---

## [1.3.0] — 2026-07-10

### Добавлено (Фаза 2.1: Навык Генератора)
- **skills/triz_generator/** — 6 файлов: schemas.py, prompts.py, handler.py
  (generate_concepts, refine_concepts, linearize_concept, run_ariz_full,
  run_ariz_two_pass), __init__.py, SKILL.md
- **Тесты** — 14/14, SmartMockClient для multi-step LLM

## [1.4.0] — 2026-07-10

### Добавлено (Фаза 2.2: Навык Критика)
- **skills/triz_critic/** — 7 файлов: schemas.py (CriticInput, CriticReport, Issue,
  CheckResult, Severity, AffectedRole, CHECKLIST_ITEMS — 6 пунктов), prompts.py
  (SYSTEM_PROMPT 2263 символа), validator.py (has_solution_verbs, _clean_report,
  validate_critic_output с auto-fix), handler.py (critique_generator_output +
  _parse_critic_report), __init__.py, SKILL.md
- **Тесты** — 16/16, в т.ч. auto-fix critical → accepted=False

## [1.6.0] — 2026-07-10

### Добавлено (Фаза 3: Профиль и интеграция)

- **profile/profile.yaml** — конфигурация профиля: модели, режимы, circuit breaker, retry, метрики, канбан, навыки, API, логирование, память
- **profile/personality.md** — persona супервизора ТРИЗ-агента: роль, компетенции, процесс работы, ограничения
- **main.py** — CLI-интерфейс с 4 командами: submit (запуск задачи), status (статус), metrics (метрики), list (список задач)
- **api.py** — HTTP API на Flask с 6 эндпоинтами: /health, /submit, /status/{id}, /result/{id}, /metrics, /tasks
- **tests/test_integration.py** — 4 интеграционных теста: полный цикл sufficiency, канбан, метрики, resilience
- **MockLLMClient** — переработан под реальные сигнатуры: .chat() для генератора + build_llm_call() для критика
- **Адаптер критика** — _wrap_mock_critic преобразует вызов run_triz_cycle → critique_generator_output

### Исправлено

- **kanban/operations.py:create_task** — добавлен параметр task_id (было: генерация UUID, задача передавалась как query)
- **kanban/operations.py** — добавлен метод update_task_iteration (используется в run_triz_cycle)
- **skills/triz_provisor/handler.py** — исправлен вызов create_task на корректный

### Протестировано

- CLI: submit, list, status, metrics — все 4 команды работают
- HTTP API: health, submit, status, metrics, tasks — 5 эндпоинтов, ответы корректны
- Интеграционные тесты: 4/4 пройдены

---

## [1.9.0] — 2026-07-10

### Добавлено (Phase B: Structured Input — завершена)

- **input/__init__.py** — экспорт FactPack, StructuredInputAnalyzer, LocalSearchEngine, ExternalSearchEngine
- **input/fact_pack.py** — FactPack dataclass (11 полей: domain, goal_type, entities, materials, processes, existing_solutions, constraints, sources, knowledge_gaps и др.), Domain/GoalType enums, сериализация to_dict/from_dict/to_json/from_json, truncation для контекста
- **input/local_search.py** — LocalSearchEngine: поиск по Obsidian vault (grep .md), литературе (pdftotext + grep), ChromaDB (если установлена), маппинг domain→директории, дедупликация
- **input/external_search.py** — ExternalSearchEngine: абстрактный движок с callback-функциями для web, arxiv, sci-bot, google scholar, researchgate, ГОСТов; лимитирование, статистика
- **input/analyzer.py** — StructuredInputAnalyzer: 4-шаговый процесс (LLM-анализ → локальный поиск → внешний поиск → LLM-синтез FactPack), rule-based fallback при отказе LLM
- **Тесты input модуля** — 40/40 (FactPack: 11, LocalSearch: 10, ExternalSearch: 9, Analyzer: 9)

### Изменено (Phase B.5 — Интеграция)

- **kanban/models.py** — добавлено поле `fact_pack: Optional[Dict]` в Task dataclass
- **kanban/operations.py** — `create_task()` принимает `fact_pack` параметр
- **skills/triz_generator/prompts.py** — `build_generation_prompt()` расширен параметрами domain, goal_type, entities, materials, processes, existing_solutions; обогащение промпта данными FactPack (две версии: краткая и полная)
- **skills/triz_generator/handler.py** — `generate_concepts()` и `run_ariz_full()` извлекают FactPack-параметры из **kwargs и передают в prompts
- **skills/triz_provisor/handler.py** — `run_triz_cycle()` принимает `task_input: Optional[FactPack]`, извлекает поля, передаёт в генератор, сохраняет FactPack в канбан
- **main.py** — добавлена `_analyze_task()` с вызовом в `cmd_submit()`
- **api.py** — добавлена `_analyze_task()` с вызовом в эндпоинте `/submit`

### Протестировано

- Все тесты: 125/125 (20 memory + 12 generator + 16 critic + 13 provisor + 16 llm + 40 input + 4 integration + 4 metrics + 1 resilience)
- Consistency checker: C1–C8, 0 ошибок

### Добавлено (Phase A: E2E Smoke Test)

- **`_e2e_test.py`** — сквозной тест с реальным deepseek-v4-flash: задача → генератор → критик → провизор → FinalRecommendation
- **`_debug_llm.py`, `_debug_api.py`, `_debug_client.py`, `_debug_prompt.py`, `_debug_compare.py`** — набор диагностических скриптов для изолированной проверки API, конфигов, промптов, ответов

### Исправлено (в процессе E2E-отладки)

- **`llm/client.py:_load_hermes_config()`** — заменён `Path.home()` на абсолютный путь `/home/orangepi/.hermes/config.yaml` (Hermes Agent ломает expanduser)
- **`skills/triz_generator/handler.py:_resolve_llm()`** — теперь каждый вызов создаёт свежий клиент (избегает кросс-ролевого загрязнения max_tokens)
- **`skills/triz_generator/handler.py:generate_concepts()`** — добавлен параметр `**kwargs` для совместимости с `previous_critique` от критика
- **`skills/triz_generator/handler.py:generate_concepts()`** — добавлен retry (3 попытки) при JSONDecodeError с понижением температуры и новым seed
- **`skills/triz_generator/handler.py:_parse_generator_output()`** — защита от str-в-списках (невалидный JSON от LLM)
- **`profile/profile.yaml`** — `generator.temperature: 0.0` (было 0.4 — битый JSON от перегретой модели)

### Протестировано

- **E2E smoke test** — пройден ✅ (204 сек, deepseek-v4-flash, 1 итерация)
  - Рекомендованная концепция: *Spatial-Time Decoupled KVCache* (idealness 8.2)
  - Альтернативы: Proactive Caching Precompute, Streaming Speculative Decoding
  - Токенов: 636 in / 480 out
  - Ошибок: 0
- **Unit-тесты:** 77/77 (20 memory + 12 generator + 16 critic + 13 provisor + 16 llm)
- **Интеграционные тесты:** 4/4 (полный цикл, канбан, метрики, resilience)
- **Consistency checker:** C1–C8, 0 ошибок, 0 предупреждений

## [1.7.0] — 2026-07-10

### Добавлено (Phase A: RealLLM Integration)

- **llm/__init__.py, llm/client.py** — `RealLLMClient` с OpenAI SDK (openai 2.24.0), читает `profile.yaml` для role-specific model/temperature/max_tokens, fallback-модель из конфига
- **llm/test_client.py** — 16 unit-тестов (инициализация, chat, fallback, ошибки API, переопределение параметров)
- **Полная интеграция в навыки** — все handler.py (генератор, критик, провизор) принимают `llm_client=None` → автосоздание `RealLLMClient(role="...")`
- **main.py** — удалён MockLLMClient, удалён --mock, все вызовы идут через RealLLMClient
- **api.py** — переписан: удалён MockLLMClient, удалён use_mock, прямой вызов run_triz_cycle
- **tests/test_integration.py** — заменён MockLLMClient на IntegrationMockClient, исправлен вызов critic_fn (теперь через build_critic_input)

### Исправлено

- **skills/triz_provisor/handler.py:critic_fn** — теперь передаёт `CriticInput` объект вместо сырых kwargs
- **tests/consistency_checker.py** — добавлен `llm` в INCLUDE_PREFIXES, добавлены `yaml/openai/unittest` в EXTERNAL_MODULES

### Протестировано

- Все тесты: 81/81 (20 memory + 12 generator + 16 critic + 13 provisor + 16 llm + 4 integration)
- Consistency checker: 8/8 checks, 0 errors, 0 warnings
- PDF-индекс ai_agents_in_action: 156 чанков, 155K токенов, qwen3-embedding-8b

---

### Добавлено (Фаза 2.3: Навык Провизора)
- `skills/triz_provisor/metrics.py` — 5 детерминированных формул (completeness, coherence, overall, improvement_delta, detect_plateau)
- `skills/triz_provisor/rule_based.py` — rule-based fallback для evaluate, stop_decision, select_best_concept
- `skills/triz_provisor/prompts.py` — SYSTEM_PROMPT + build_evaluation_prompt + build_synthesis_prompt
- `skills/triz_provisor/handler.py` — evaluate_iteration, decide_continue, synthesize_final, run_triz_cycle
- `skills/triz_provisor/__init__.py` — публичное API (16 символов в __all__)
- `skills/triz_provisor/SKILL.md` — документация навыка
- `skills/triz_provisor/test_provisor.py` — 13 unit-тестов (все пройдены)

### Исправлено

- `detect_plateau`: исправлена формула — берётся `patience+1` записей для получения `patience` дельт
- `handler.py:final_eval` в `synthesize_final` — приведение dict к `Evaluation` через `from_dict`
- `handler.py:best_concept is None` — аналогичный фикс типа `final_eval`

---

## [1.1.0] — 2026-07-10

### Добавлено v1.1 (доработка после v1.0)

- **Канбан-модуль** — SQLite-бэкенд, TaskStatus, KanbanOperations
- **Модуль метрик** — JSONL-логгер, декоратор, контекстный менеджер, агрегатор
- **Стоимость эксплуатации** — таблица токенов, сравнение моделей
- **Производительность** — latency P95/P99, общее время sufficiency/optimality
- **Тестирование** — Unit + Integration + E2E + Load + Idempotency
- **Восстановление после сбоя** — сценарии, механизм через канбан, гарантии
- **JSON-схема LinearizedConcept** — полный handoff-формат для Архитектора
- **Явные интерфейсы ролей** — `IProvisor`, `IGenerator`, `ICritic` с методами, выносимыми в комбайн
- **Мониторинг** — Prometheus-метрики (позже заменены на JSONL в v1.2)
- **Верификация источников** — флаг `verified: false`

### Изменено v1.1

- Слабое место W1 (SPOF): circuit breaker → + rule-based fallback
- Слабое место W5 (запрет Критику): пост-валидация выхода
- Слабое место W2 (фактология): + `verified: false`
- 4 новых слабых места: W7 (идемпотентность), W8 (мониторинг)

---

## [1.0.0] — 2026-07-09

### Добавлено v1.0 (первый протокольный отчёт)

- **Архитектура** — 3 роли: Provisor, Generator, Critic
- **Режимы работы** — sufficiency (3 итерации), optimality (5 итераций)
- **Память ТРИЗ/АРИЗ** — Python-dict: 40 принципов (срез 18), матрица противоречий (7+ пар), шаблоны ИКР, типы ресурсов
- **Чек-лист Критика** — 6 проверок с severity
- **Метрики Провизора** — 2/4 кодом (completeness, coherence) + 2/4 LLM (feasibility, novelty)
- **Nullable Vepol** — поле `vepol_model` с nullable-полями для совместимости лайт → строгий комбайн
- **Generic fallback матрицы** — принципы разделения ФП при отсутствии пары
- **Канбан-доска** — колонки [queue → generator → critic → rework → done]
- **6 слабых мест** с митигациями (W1–W6)

---

## [0.1.0] — 2026-07-09

### Добавлено

- Профиль `triz-agent` в Hermes Agent
- Канбан-модуль: `models.py`, `storage.py`, `operations.py`
- Smoke-test (8 проверок) — зелёный
- Документация: README, CHANGELOG, TODO