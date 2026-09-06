# TODO — ТРИЗ-агент (next-gen)

> **Текущая фаза:** Phase D ✅ — ResearcherAgent завершён (97 тестов, 13 файлов).
> **Следующая:** Phase E (Multi-agent) → Phase F (Отчёт).

---

## Условные обозначения

- [x] — выполнено
- [~] — в работе
- [ ] — в плане
- [!] — блокировано

---

## Phase A — Боевой LLM (завершена ✅)

**Цель:** заменить MockLLMClient на RealLLMClient, E2E smoke test с реальным LLM.

- [x] A.1 — Унификация LLM-интерфейса
- [x] A.2 — RealLLMClient (OpenAI SDK, profile.yaml)
- [x] A.3 — Интеграция в навыки (generator, critic, provisor)
- [x] A.4 — Интеграция в main.py + api.py
- [x] A.5 — E2E smoke-тест (deepseek-v4-flash, 204s)
- [x] A.6 — Документация

**Результат:** 16 тестов llm, E2E пройден, реальная концепция *Spatial-Time Decoupled KVCache* (idealness 8.2).

---

## Phase B — Структурированный вход (завершена ✅)

**Цель:** заменить сырой `task_query: str` на структурированный `FactPack`.

- [x] B.1 — FactPack dataclass (11 полей, сериализация)
- [x] B.2 — LocalSearchEngine (Obsidian, PDF, ChromaDB)
- [x] B.3 — ExternalSearchEngine (web, arxiv, sci-bot, scholar)
- [x] B.4 — StructuredInputAnalyzer (LLM→поиск→LLM синтез)
- [x] B.5 — Интеграция в run_triz_cycle + main.py + api.py
- [x] B.6 — 40 input-тестов + 125 profile-wide

---

## Phase C — Настоящий АРИЗ (завершена ✅)

**Цель:** конечный автомат по 8 шагам АРИЗ, 3 уровня глубины, рекурсивная вложенность.

### C.1 — FSM (базовые 8 шагов)
- [x] **ariz/base.py** — ArizState, ArizLevel, ArizStep, TRANSITIONS (43 теста)
- [x] **ariz/core.py** — ArizFSM (state, step, run, handlers) (43 теста)
- [x] **ariz/ariz_fsm_integration.py** — run_ariz_fsm() адаптер
- [x] **Step handlers** — 8 шагов в ariz/steps/ (31 тест)
- [x] **Step validator** — 3 уровня валидации (59 тестов)
- [x] **Prompts** — промпты для 8 шагов × 3 уровня (22 теста)

### C.2 — Ступенчатость (Level 0/1/2)
- [x] ArizLevel enum — QUICK / DETAILED / EXPERT
- [x] 3 варианта промптов и валидации

### C.3 — Вложенность (ArizTree)
- [x] ArizTree — дерево решений (21 тест)
- [x] Рекурсия на шагах 4 и 6
- [x] Ветвление на шаге 6 (13 тестов)

### C.4 — Гибридный режим
- [x] hybrid_router.py — маршрутизация по сложности шага
- [x] 3 группы: economy / standard / responsible
- [x] Fallback-цепочка Llama 3B → Mistral Nemo → Qwen 30B

**Результат:** 272 теста ariz + 125 profile-wide — все ✅. ArizFSM интегрирован в run_triz_cycle.

---

## Phase D — Researcher Agent (завершена ✅)

> Подробный отчёт: `docs/plans/2026-07-11-phase-d-complete.md`

**Цель:** внешний поиск материалов для АРИЗ: arXiv, Sci-Hub, веб (DDG), патенты.

- [x] D.0 — Аудит поисковых модулей
- [x] D.1 — ResearchResult схема + ResearcherAgent (13 тестов schemas)
- [x] D.2 — Поисковые адаптеры:
  - [x] ArxivSearchAdapter — реальный API (17 тестов)
  - [x] DdgSearchAdapter — DDG скрипт (9 тестов)
  - [x] SciBotSearchAdapter — Sci-Bot API (20 тестов)
- [x] D.3 — ResearcherAgent ядро (генерация запросов, синтез) (20 тестов)
- [x] D.4 — ResearchBridge → контекст в шаги 1-2 АРИЗ (12 тестов)
- [x] D.5 — Интеграция в run_triz_cycle (6 E2E тестов)

**Результат:** 97 тестов, 13 файлов в skills/researcher/, грациозная деградация.

---

## Phase E — Multi-agent (в плане)

**Цель:** выделить специализированных агентов, параллельный запуск веток.

- [ ] E.1 — AnalystAgent (из фазы B)
- [ ] E.2 — ResearcherAgent (из фазы D — реализован как модуль, не как автономный агент)
- [ ] E.3 — SolverAgent (из фазы C)
- [ ] E.4 — EvaluatorAgent (multi-criteria comparison)
- [ ] E.5 — SynthesizerAgent (отчёт)
- [ ] E.6 — Параллельный запуск веток через delegate_task
- [ ] E.7 — Внутренний канбан для rework-веток
- [ ] E.8 — Тесты

---

## Phase F — Отчёт (в плане)

- [ ] F.1 — ReportGenerator (Markdown/HTML)
- [ ] F.2 — Сравнительная таблица концепций
- [ ] F.3 — Trade-off анализ
- [ ] F.4 — Экспорт в Obsidian / HTML / JSON
- [ ] F.5 — CLI: `main.py report <task_id>`
- [ ] F.6 — API: GET /report/<task_id>
- [ ] F.7 — Тесты

---

## Phase G — Самообучающаяся память (в плане)

- [ ] G.1 — Experience Log (SQLite)
- [ ] G.2 — Pattern Analyzer
- [ ] G.3 — Dynamic Matrix
- [ ] G.4 — IKR Templates из опыта
- [ ] G.5 — Context Retriever
- [ ] G.6 — Метрики обучения
- [ ] G.7 — Интеграция с канбаном

---

## Известные проблемы

### 🟡 ExternalSearchEngine prod-режим
ExternalSearchEngine существует как абстракция, но не подключён к реальным API.
main.py/api.py передают `external_engine=None`.

### 🟡 Google Custom Search
Ожидает API_KEY и CX (настройка отложена).

---

## 🔴 CRITICAL: Research (Phase D) — Нерелевантный поиск

**Симптом:** Во всех e2e-прогонах (v4–v6) Research возвращает одни и те же статьи по физике высоких энергий (hep-ph, hep-ex, astro-ph.HE, gr-qc) независимо от задачи — железобетон, нейросеть+CLIPS.

**Корень:** ArxivSearchAdapter не использует domain/task_query для построения запроса, а DdgSearchAdapter и SciBotSearchAdapter не вызываются.

**Подзадачи:**
- [ ] ~~D-RESEARCH-1:~~ ArxivSearchAdapter — привязать domain к arXiv category (software → cs.AI, mechanics → physics.class-ph, physics → physics.gen-ph и т.д.)
- [ ] ~~D-RESEARCH-2:~~ DdgSearchAdapter — подключить веб-поиск через ddg-search.py (преобразует domain+task_query в поисковую фразу)
- [ ] ~~D-RESEARCH-3:~~ SciBotSearchAdapter — подключить научно-технический поиск по sci-bot.ru
- [ ] ~~D-RESEARCH-4:~~ Агрегатор результатов — дедуплицировать, объединять, сортировать по релевантности
- [ ] ~~D-RESEARCH-5:~~ Critic-фильтр результатов — LLM проверяет каждый результат на релевантность, отбрасывает мусор
- [ ] ~~D-RESEARCH-6:~~ E2E тест Research на 2 реальных задачах (железобетон, нейросеть+CLIPS) — ожидается 0 совпадений с hep-ph/hep-ex

**Приоритет:** HIGH — блокирует выход осмысленных концепций

---

## 🔴 CRITICAL: Report generator e2e — формат routing устарел

**Симптом:** В e2e v4 все 8 шагов АРИЗ показаны как `None`/`N/A`/`0.0 сек`.

**Корень:** Формат routing изменился после внедрения hybrid_router, report generator не синхронизирован.

**Подзадачи:**
- [ ] ~~RPT-1:~~ Привести report generator к актуальному формату routing (step_name, model, elapsed из routing[].context)
- [ ] ~~RPT-2:~~ Добавить fallback-форматирование — если routing пустой или не парсится, выводить "недоступно" вместо None
- [ ] ~~RPT-3:~~ E2E тест report generator на реальном прогоне — проверка, что все 8 шагов валидные

**Приоритет:** HIGH

---

## 🟡 Концепции — нет привязки к принципам ТРИЗ

**Симптом:** В e2e v5 (железобетон) концепции — общеинженерные банальности без ТРИЗ-терминологии: «Использование более прочного бетона», «Локальное армирование», «Комбинирование материалов». Нет ссылок на принципы (дробление, матрёшка, динамичность), нет ИКР-обоснования.

**Корень:** Промпты шагов 6-8 не форсируют использование принципов ТРИЗ и ИКР-шаблонов.

**Подзадачи:**
- [ ] ~~CONCEPT-1:~~ Обновить промпты шага 6 (Приёмы ТРИЗ): требовать для каждого решения указывать номер принципа Altshuller и обоснование
- [ ] ~~CONCEPT-2:~~ Обновить промпты шага 7 (Синтез): требовать привязки каждой концепции к минимум 2 принципам + ИКР-ссылка
- [ ] ~~CONCEPT-3:~~ E2E тест: концепции содержат ссылки на принципы

**Приоритет:** MEDIUM

---

## 🟡 Флешбек (итеративное улучшение) не работает

**Симптом:** В гибридном expert-прогоне флешбек: "1 цикл, improvement=False, всего 1 концепция". Причина останова — "достигнут максимум идеальности" с оценкой 7.4/10.

**Корень:** improvement_threshold=0.3 — LLM не может улучшить концепцию на 0.3 за одну итерацию, либо метрика improvement не релевантна.

**Подзадачи:**
- [ ] ~~FLASHBACK-1:~~ Проанализировать код метрики improvement_delta — адекватно ли она считает прирост
- [ ] ~~FLASHBACK-2:~~ Снизить improvement_threshold или сделать адаптивным (зависит от текущей оценки)
- [ ] ~~FLASHBACK-3:~~ Увеличить число итераций флешбека для sufficiency до 2, для optimality до 4
- [ ] ~~FLASHBACK-4:~~ E2E тест флешбека: iteration > 1 при low quality

**Приоритет:** MEDIUM

---

## 🟡 Отчёт e2e v5/v6 — шаги линеаризации обрезаны

**Симптом:** Шаги концепций в e2e v5 показаны как `{'step': 1, 'action': 'Провести анализ...`, обрезано. В v6 JSON шагов обрезан на 120 символах.

**Корень:** Форматирование в отчёте использует str(...)[:120], что режет структурированные данные.

**Подзадачи:**
- [ ] ~~TRUNC-1:~~ Заменить обрезку на многострочный вывод (каждый шаг с новой строки)
- [ ] ~~TRUNC-2:~~ E2E тест: в разделе "Шаги концепции" нет обрезанных полей

**Приоритет:** LOW

---

## 🟡 Время выполнения >2 мин — медленно для sufficiency

**Симптом:** v4: 195.5с, v5: 135.1с, v6: 173.1с. Гибридный expert: 299.7с.

**Корень:** Mistral Nemo на Orange Pi ARM64 медленная (18-40 сек на шаг), плюс 8 последовательных LLM-вызовов.

**Подзадачи:**
- [ ] ~~PERF-1:~~ Замерить время каждого шага, выявить самого медленного 
- [ ] ~~PERF-2:~~ Перевести economy-шаги (0,5,7) на Llama 3.2 3B (локальный Ollama) — для шагов без JSON
- [ ] ~~PERF-3:~~ Параллелизовать шаги 5-6 (оперативная зона + приёмы)
- [ ] ~~PERF-4:~~ E2E тест: sufficiency < 60 сек, optimality < 180 сек

**Приоритет:** LOW

---

## 🔴 Дефект: Sci-Bot адаптер не возвращает результаты

**Симптом:** SciBotSearchAdapter.search() возвращает 0 токенов, хотя curl показывает 2.8M токенов. Api_bot не дожидается завершения индексации.

**Подзадачи:**
- [ ] ~~SCI-BOT-1:~~ Debug polling-механизма в SciBotSearchAdapter — увеличить таймауты, добавить retry
- [ ] ~~SCI-BOT-2:~~ E2E тест: Sci-Bot поиск по DOI возвращает >0 результатов

**Приоритет:** MEDIUM