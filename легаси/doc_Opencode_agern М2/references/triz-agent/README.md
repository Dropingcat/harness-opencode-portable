# ТРИЗ-агент (triz-agent)

Профиль Hermes Agent для решения изобретательских задач по методологии **ТРИЗ/АРИЗ/Веполь**.

**Статус: ✅ Phase D завершена** — 97 тестов ResearcherAgent + 272 ariz + 125 profile-wide. АРИЗ + исследование литературы.

---

## Архитектура трёх ролей

```
┌──────────────────────────────────────────────────────────┐
│               ПРОВИЗОР (Provisor)                        │
│  - Хранит TRIZ_MEMORY / ARIZ_MEMORY                      │
│  - Считает метрики: completeness/coherence — кодом       │
│                feasibility/novelty — через LLM            │
│  - Решает STOP/CONTINUE (quality, plateau, limit)        │
│  - Синтезирует финальную рекомендацию                     │
│  - Rule-based fallback при отказе LLM                     │
└────────────────────────┬─────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
┌─────────────────────┐  ┌────────────────────────────┐
│    ГЕНЕРАТОР        │  │      КРИТИК                │
│  (Generator)        │  │  (Critic)                  │
│                     │  │                            │
│ - 8 шагов АРИЗ      │◄─│ - 6 проверок (CHECKLIST)   │
│ - 2–4 концепции     │  │ - Severity: critical/major  │
│ - JSON-выход        │  │ - Post-валидация (запрет    │
│ - Линеаризация      │  │   глаголов-нарушителей)    │
│ - Два прохода       │  │ - temperature=0.0          │
│   (strict mode)     │  │ - Auto-fix critical→reject │
└─────────────────────┘  └────────────────────────────┘
         ▲                         │
         └──────── rework ─────────┘
         (sufficiency: max 3, optimality: max 5)
```

### Как это работает

1. **Провизор** получает задачу, заводит в канбане, запускает цикл
2. **Генератор** выполняет АРИЗ (8 шагов), выдаёт концепции
3. **Критик** проверяет концепции по чек-листу
4. **Провизор** оценивает итерацию (2 метрики кодом + 2 через LLM)
5. **Провизор** решает: STOP (качество/плато/лимит) или CONTINUE (rework)
6. **Провизор** синтезирует финальную рекомендацию

При отказе LLM — rule-based fallback (среднее по истории, выбор по idealness).

---

## Роли

| Роль | Вызов | Модель | Метрики |
|------|-------|--------|---------|
| **Provisor** | `delegate_task` (leaf) | DeepSeek v4 Flash / qwen3-30b-a3b | completeness, coherence (код); feasibility, novelty (LLM) |
| **Generator** | `delegate_task` (leaf) | DeepSeek v4 Flash, t=0.0 | 8 шагов АРИЗ, концепции, линеаризация |
| **Critic** | `delegate_task` (leaf) | DeepSeek v4 Flash, t=0.0 | 6 проверок, issues, пост-валидация |

---

## Режимы работы

| Параметр | Sufficiency | Optimality |
|----------|-------------|------------|
| Макс. итераций | 3 | 5 |
| Порог качества | 7.0 / 10 | 9.0 / 10 |
| Плато threshold | 0.3 | 0.1 |
| Patience | 2 | 3 |
| Автостоп | ✅ Да | ❌ Нет (запрос пользователя) |
| Стоимость | ~$0.0014 | ~$0.0024 |
| Время | ~30 сек | ~50 сек |

### Критерии остановки (в порядке приоритета)

1. `STOP_QUALITY` — `overall >= threshold`
2. `STOP_LIMIT` — `iteration >= max_iterations`
3. `STOP_PLATEAU` — `patience` итераций без улучшения
4. `STOP_USER` — решение пользователя (optimality)
5. `STOP_CONFIDENCE` — статистическая значимость (задел)

---

## Метрики оценки итерации

| Метрика | Источник | Диапазон | Формула |
|---------|----------|----------|---------|
| completeness | Код | 0.0–1.0 | `min(1, len(concepts) / target)` |
| coherence | Код | 0.0–1.0 | `1 - (n_issues / n_checks)` |
| feasibility | LLM (fallback: код) | 0.0–1.0 | LLM-оценка реализуемости |
| novelty | LLM (fallback: код) | 0.0–1.0 | LLM-оценка новизны |
| overall | Формула | 0.0–10.0 | `(c+co+f+n)/4 * 10` |
| improvement_delta | Формула | -10–10 | `current - previous` |

---

## Канбан

```
[queue] → [generator] → [critic] → [rework] → [done]
                                         → [failed]
```

- SQLite-бэкенд (`kanban.db`)
- 6 статусов: QUEUE, GENERATOR, CRITIC, REWORK, DONE, FAILED
- Идемпотентность: `compute_seed(task_id, iteration, role)`
- Circuit breaker + retry (3 попытки)

---

## Структура профиля

```
~/.hermes/profiles/triz-agent/
├── CHANGELOG.md                # История версий
├── TODO.md                     # План реализации + фазы D–G
├── README.md                   # Этот файл
├── SOUL.md                     # Persona профиля
│
├── kanban/                     # [Фаза 0] Канбан-модуль
│   ├── __init__.py, models.py, storage.py, operations.py
│
├── metrics/                    # [Фаза 0] JSONL-логгер метрик
│   ├── __init__.py, logger.py, aggregator.py
│
├── resilience/                 # [Фаза 0] Circuit breaker + retry
│   ├── __init__.py, breaker.py, idempotency.py, retry.py
│
├── memory/                     # [Фаза 1.1] Память ТРИЗ/АРИЗ ✅
│   ├── __init__.py, triz_memory.py (18 принципов, 7 пар матрицы,
│   │   ariz_memory.py (8 шагов), config.py (2 режима)
│   └── test_memory.py (20/20)
│
├── input/                      # [Phase B] Structured Input ✅
│   ├── __init__.py, fact_pack.py, local_search.py,
│   │   external_search.py, analyzer.py (40 тестов)
│
├── llm/                        # [Phase A] RealLLMClient ✅
│   ├── __init__.py             # Публичное API
│   ├── client.py               # RealLLMClient (OpenAI SDK, profile.yaml)
│   └── test_client.py          # 16/16 тестов
│
├── ariz/                       # [Phase C] Layered АРИЗ — FSM ✅
│   ├── __init__.py, base.py, core.py, tree.py,
│   │   validator.py, prompts.py, steps/ (8 шагов)
│   └── ariz_fsm_integration.py (272 теста)
│
├── skills/                     # [Фаза 2] Навыки агентов ✅
│   ├── triz_generator/         # 6 файлов, 14 тестов
│   ├── triz_critic/            # 7 файлов, 16 тестов
│   ├── triz_provisor/          # 8 файлов, 13 тестов
│   └── researcher/             # [Phase D] ResearcherAgent ✅
│       ├── schemas.py          # Data-классы (80 строк)
│       ├── arxiv_search.py     # Адаптер arXiv API (150 сток)
│       ├── ddg_search.py       # Адаптер DuckDuckGo (100 строк)
│       ├── sci_bot_search.py   # Адаптер Sci-Bot (384 строк)
│       ├── researcher_agent.py # Оркестратор (400 строк)
│       ├── research_bridge.py  # Мост к АРИЗ (198 строк)
│       ├── __init__.py         # Экспорт (97 тестов)
│
├── profile/                    # [Фаза 3] Конфигурация профиля ✅
│   ├── profile.yaml            # YAML-конфиг (модели, режимы, навыки, API)
├── main.py                     # [Фаза 3] CLI-интерфейс (4 команды)
├── api.py                      # [Фаза 3] HTTP API (Flask, 6 эндпоинтов)
├── references/                 # [Фаза 1.2] Расширенная память (план)
├── tests/                      # [Phase A] Интеграционные + E2E тесты
│   ├── test_integration.py     # 4 интеграционных теста ✅
│   ├── unit/
│   └── e2e/
├── docs/plans/                 # Подробные планы фаз
│   ├── 2026-07-10-phase-b-structured-input.md
│   ├── 2026-07-10-phase-c-ariz-fsm.md
│   ├── 2026-07-10-phase-c-ariz-layered.md
│   ├── 2026-07-10-phase-d-researcher.md
│   └── 2026-07-11-phase-d-complete.md
```

---

## E2E Smoke Test (Phase A)

Прогон полного цикла с реальным deepseek-v4-flash:

```bash
cd ~/.hermes/profiles/triz-agent
python3 _e2e_test.py
```

**Результат:**
- Время: 204 секунды
- Итераций: 1 (автостоп по качеству 8.2)
- Концепция: *Spatial-Time Decoupled KVCache* (idealness 8.2)
- Токены: 636 in / 480 out
- Ошибок: 0

**Набор диагностических скриптов:**
```bash
python3 _debug_api.py       # Прямой API вызов к aitunnel
python3 _debug_client.py    # RealLLMClient.chat() 
python3 _debug_prompt.py    # Размер промпта + генерация концепций
python3 _debug_llm.py       # Чтение конфигов (без API)
```

---

## История изменений

История версий ведётся в **[CHANGELOG.md](./CHANGELOG.md)**.

---

## Зависимости

- Python 3.11+
- SQLite3 (встроен)
- Hermes Agent (delegate_task, kanban, cron)
- DeepSeek v4 Flash (модель по умолчанию)

## Быстрый старт

```bash
# Войти в профиль
triz-agent chat

# Запустить задачу через CLI
cd ~/.hermes/profiles/triz-agent
python main.py submit "Школьный проект по наблюдению за ветром" --mode sufficiency

# Статус задачи
python main.py status <task_id>

# Метрики системы
python main.py metrics

# Запустить HTTP API
python api.py &
curl http://localhost:8080/health
curl -X POST http://localhost:8080/submit \
  -H "Content-Type: application/json" \
  -d '{"task": "Оптимизация кода", "mode": "sufficiency"}'

# Запустить тесты
cd ~/.hermes/profiles/triz-agent
python -m memory.test_memory                          # 20 тестов
python -m skills.triz_generator.test_generator        # 12 тестов
python -m skills.triz_critic.test_critic              # 16 тестов
python -m skills.triz_provisor.test_provisor          # 13 тестов
python -m llm.test_client                             # 16 тестов
python -m tests.test_integration                      # 4 интеграционных теста
python _e2e_test.py                                   # E2E smoke test (real LLM)
```

## Ресурсы

- [ТРИЗ: 40 принципов](https://triz.org/)
- [АРИЗ-85В](https://ru.wikipedia.org/wiki/АРИЗ)
- [Вепольный анализ](https://ru.wikipedia.org/wiki/Вепольный_анализ)
- Hermes Agent: [документация конфигурации профилей](https://hermes-agent.nousresearch.com/docs)
- План доработок: **[TODO.md](./TODO.md)**
- Самообучающаяся память: **TODO.md → Фаза G**
