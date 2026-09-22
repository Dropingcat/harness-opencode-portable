# Глобальный канбан — ТРИЗ-агент

> **Цель:** из текста задачи —> анализ —> поиск материалов —> АРИЗ (8 шагов, несколько веток) —> multi-criteria оценка —> отчёт с вариантами.

---

## Условные обозначения

- [x] — выполнено
- [~] — в работе
- [ ] — в плане
- [-] — отложено / заблокировано

---

## Фаза A — Боевой LLM (завершена ✅)

**Цель:** заменить MockLLMClient на RealLLMClient, подключить настоящий провайдер, проверить E2E.

| Задача | Статус |
|--------|--------|
| A.1 — Унификация LLM-интерфейса (единый протокол chat()) | [x] |
| A.2 — RealLLMClient (чтение profile.yaml, вызов провайдера) | [x] |
| A.3 — Адаптация Критика под chat() | [x] |
| A.4 — Интеграция в main.py + api.py | [x] |
| A.5 — E2E smoke-тест с реальным LLM | [x] ✅ deepseek-v4-flash, 204s |
| A.6 — Документация (CHANGELOG, README, TODO, KANBAN) | [x] |

**Вход:** MockLLMClient, 4 копии, 2 несовместимых интерфейса, CLI с --mock  
**Выход:** RealLLMClient, 1 интерфейс, CLI без --mock, E2E пройден

---

## Фаза B — Структурированный вход (завершена ✅)

**Цель:** заменить `task_query: str` на `FactPack` — структурированный пакет данных (домен, сущности, материалы, процессы, существующие решения).

**Длительность:** 1–2 дня.

| Задача | Статус |
|--------|--------|
| B.1 — FactPack dataclass (Domain, GoalType, 11 полей, сериализация) | [x] |
| B.2 — LocalSearchEngine (Obsidian grep, PDF, ChromaDB) | [x] |
| B.3 — ExternalSearchEngine (web, arxiv, sci-bot, scholar, researchgate, ГОСТы) | [x] |
| B.4 — StructuredInputAnalyzer (LLM-анализ + поиск + синтез FactPack) | [x] |
| B.5 — Интеграция: run_triz_cycle, main.py, api.py, kanban | [x] |
| B.6 — Тесты (40 input + интеграция) | [x] ✅ 125/125 |

**Вход:** `task_query = "как улучшить code review"`  
**Выход:** `FactPack(domain="разработка ПО", entities=[...], sources=[...])`  
**Архитектура:** `raw_text → StructuredInputAnalyzer(LLM→LocalSearch→ExternalSearch→LLM) → FactPack → run_triz_cycle`

---

## Фаза C — Ступенчатый и вложенный АРИЗ ✅

**Цель:** многоуровневый АРИЗ: 8 шагов (база) × 3 уровня глубины (Level 0/1/2) + рекурсивная вложенность.

**Длительность:** 4–6 дней. **Ядро агента.**

**Подробный план:** `docs/plans/2026-07-10-phase-c-ariz-layered.md`

- [x] C.1 — base.py: ArizLevel, ArizState, ArizStep, 8 шагов, TRANSITIONS
- [x] C.2 — core.py: ArizFSM с поддержкой уровней
- [x] C.3 — tree.py: ArizTree + рекурсивная вложенность (шаги 4, 6)
- [x] C.4 — validator.py: LevelValidator (3 уровня валидации)
- [x] C.5 — prompts.py: промпты для Level 0/1/2
- [x] C.6 — steps/ (шаги 1-8): обработчики с поддержкой уровней
- [x] C.7 — step_6 ветвление + вложенные АРИЗ (ключевой)
- [x] C.8 — Интеграция: run_triz_cycle → ArizFSM, старый код → fallback
- [x] C.9 — Тесты (272 ariz + 125 profile-wide) + consistency checker

**Вход:** `run_triz_cycle` = цикл gen→crit→prov  
**Выход:** дерево АРИЗ с 3 уровнями глубины и рекурсивными подзадачами

---

## Фаза D — Исследователь (Researcher Agent) ✅

**Цель:** внешний поиск материалов по теме задачи: arXiv, Sci-Hub, Semantic Scholar, веб, патенты. Подача найденного в шаги 1-2 АРИЗ.

**Оценка:** ~3.5 дня (5 подфаз, ~13 файлов, ~40 тестов). ✅ DDG Search работает, не требуется настройка ключей.

**Подробный отчёт:** `docs/plans/2026-07-11-phase-d-complete.md`

| Задача | Статус | Дней | Файлов | Тестов |
|--------|--------|------|--------|--------|
| D.0 — Аудит текущих поисковых модулей | [x] | 0.25 | 0 | 0 |
| D.1 — ResearchResult схема + интерфейс агента | [x] | 0.5 | 4 | 13 |
| D.2 — Поисковые модули (arXiv, Sci-Bot, **DDG Search ✅**) | [x] | 0.75 | 4 | 46 |
| D.3 — ResearcherAgent ядро (генерация запросов, синтез) | [x] | 1.0 | 3 | 20 |
| D.4 — Подача результатов в шаги 1-2 АРИЗ | [x] | 0.5 | 2 | 12 |
| D.5 — Интеграция в run_triz_cycle + E2E | [x] | 0.5 | 1 | 6 |

**Результат:** 97/97 тестов, 13 файлов в skills/researcher/. ResearcherAgent → ResearchBridge → ArizFSM шаги 1-2. Грациозная деградация при ошибке поиска.

**Вход:** только знания LLM  
**Выход:** реальные источники: статьи, патенты, аналоги, обогащающие АРИЗ

**Режимы работы:**
- `sufficiency` — без исследования (быстро, существующее поведение)
- `optimality` — полное исследование + АРИЗ
- `research` — только исследование, без АРИЗ (сбор источников)

**Архитектура:**
```
task_query → ResearcherAgent
    ├── arXiv (curl → export.arxiv.org)
    ├── Sci-Bot (API с credentials)
    ├── Semantic Scholar (curl → REST API)
    ├── Web search (delegate_task или curl)
    └── LocalSearchEngine (Obsidian + PDF + ChromaDB)
         ↓
    ResearchResult (статьи, патенты, аналоги)
         ↓
    context["research_summary"] → ArizFSM (шаги 1-2)
```

---

## Фаза E — Multi-agent

**Цель:** выделить специализированных агентов, запускать ветки параллельно.

**Длительность:** 2–3 дня. Параллельно с Фазой D.

- [ ] E.1 — AnalystAgent (из фазы B)
- [ ] E.2 — ResearcherAgent (из фазы D)
- [ ] E.3 — SolverAgent (из фазы C)
- [ ] E.4 — EvaluatorAgent (multi-criteria comparison)
- [ ] E.5 — SynthesizerAgent (отчёт)
- [ ] E.6 — Параллельный запуск веток через delegate_task
- [ ] E.7 — Внутренний канбан для rework-веток
- [ ] E.8 — Тесты

**Вход:** моноагент, последовательно  
**Выход:** multi-agent, параллельно

---

## Фаза F — Отчёт

**Цель:** из JSON → Markdown/HTML отчёт с таблицами, trade-off, рекомендацией.

**Длительность:** 1–2 дня.

- [ ] F.1 — ReportGenerator (Markdown)
- [ ] F.2 — Сравнительная таблица концепций (по критериям)
- [ ] F.3 — Trade-off анализ
- [ ] F.4 — Экспорт в Obsidian / HTML / JSON
- [ ] F.5 — CLI: `main.py report <task_id>`
- [ ] F.6 — API: GET /report/<task_id>
- [ ] F.7 — Тесты

**Вход:** FinalRecommendation → JSON  
**Выход:** Markdown-отчёт с таблицами и trade-off

---

## Фаза G — Самообучающаяся память (Memory Self-Learning) 🆕

**Цель:** превратить статический TRIZ/ARIZ_MEMORY в динамическую базу знаний.

**Длительность:** 3–5 дней.

**Предшествует:** Фаза A (завершена) — нужен RealLLMClient для записи опыта.

- [ ] G.1 — Experience Log (SQLite)
- [ ] G.2 — Pattern Analyzer (частотный анализ принципов)
- [ ] G.3 — Dynamic Matrix (расширение матрицы противоречий)
- [ ] G.4 — IKR Templates из опыта
- [ ] G.5 — Context Retriever (поиск похожих задач)
- [ ] G.6 — Метрики обучения (improvement_over_baseline, knowledge_coverage)
- [ ] G.7 — Интеграция с канбаном + автоматическая запись

**Вход:** статический TRIZ_MEMORY (hardcoded dict)  
**Выход:** динамическая память, растущая с каждой задачей

**Архитектура:**
```
run_triz_cycle
    ↓ DONE
experience_log.write(task_id, domain, concept, idealness, principles)
    ↓
pattern_analyzer.update() → stats by domain
    ↓
context_retriever.lookup(new_task) → top-3 похожих → prompt augmentation
```

---

## Легенда

```
Фаза A — инфраструктура (LLM) ✅
Фаза B — вход
Фаза C — ядро (АРИЗ)
Фаза D — поиск
Фаза E — архитектура (multi-agent)
Фаза F — вывод
Фаза G — память (self-learning) 🆕
```

Каждая фаза идёт строго после предыдущей, кроме D/E (параллельно).