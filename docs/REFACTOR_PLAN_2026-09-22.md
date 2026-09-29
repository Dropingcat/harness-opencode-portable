# ПЛАН РЕФАКТОРИНГА HARNESS — Мета-Цикл (V1-V8)

**Дата:** 2026-09-22
**Статус:** УТВЕРЖДЁН К ИСПОЛНЕНИЮ
**Автор:** research-orchestrator (по архитектурному черновику автора)
**Принцип:** LLM = стохастический семантический сопроцессор; Harness = детерминированный контроллер. Эволюция = изменение внешнего состояния `S_t`, не весов модели.
**Расположение:** единый harness (portable), коммиты в GitHub.

---

## 0. Связанные ресурсы

- **Токен GitHub:** сохранён в `GITHUB_TOKEN` (harness `.env` + проект `.env`, оба gitignored). Использовать как `$env:GITHUB_TOKEN`.
- **Рабочий DOM (истина):** `09_LITERATURE/datasets/nkr_ch1_dom.yaml` (58 клаймов C-101…C-511).
- **Мой ошибочный DOM:** `research_verification/ch1_dom.json` (291 клайм) — LEGACY, консолидируется в Фазе 1.
- **Существующие гейты:** `scripts/writer/citation_trace.py`, `draft_loop.py`, `scripts/researcher/verify_claims.py`, `scripts/writer_core_handoff/docs/01_INVARIANTS.md`.
- **Фаза 2 (циклический пайплайн главы 1):** у другого агента — этот план НЕ дублирует, а задаёт архитектуру, на которую Фаза 2 опирается.

---

## 1. Целевая архитектура (8 веток)

```
┌─────────────┐
│ [V8] TRACE  │ ← сквозная ось аудита
└──────┬──────┘
       ▼
┌───────────┐  ┌───────────────┐  ┌────────────┐
│ [V1] STATE│◄─│ [V2] EVOLUTION│─►│ [V7] EXEC  │
│  ONTOLOGY │  │  CONTROLLER   │  │  ENGINE    │
└─────┬─────┘  └───────┬───────┘  └─────┬──────┘
      ▼                ▼                ▼
┌───────────┐  ┌───────────────┐  ┌────────────┐
│ [V3] FILT │  │ [V4] EXPERIM. │  │ [V5] PROMPT│
│ & VALIDAT │  │  INFRASTRUCT  │  │  TEMPLATE  │
└─────┬─────┘  └───────┬───────┘  └────────────┘
      └────────┬───────┘
               ▼
      ┌────────────────┐
      │ [V6] NEGATIVE  │
      │ KNOWLEDGE ARCH │
      └────────────────┘
```

**Принцип:** V1,V2,V3,V4,V6,V8 — детерминированный Harness; V5,V7 — конкуренция Harness+LLM.

---

## 2. Маппинг на текущее состояние harness

| Ветка | Что уже есть | Что добавить | Приоритет |
|---|---|---|---|
| **V1 State** | `runtime_snapshot.json` (routes/tool_contracts/policy_hash/source_hashes); `nkr_ch1_dom.yaml` | Promotion Tactic→Policy; версии StateVariable; миграция версий | HIGH |
| **V2 Controller** | `citation_trace.py`, `draft_loop.py`, `verify_claims.py`, `factory_gate_policy.json` | Debt-Driven Cycle (Драфт→Гейты→Debt→Хирургия→Перегейт); MergeRequest; Flashback | **BLOCKER** |
| **V3 Filter** | `01_INVARIANTS.md` (12+9); гейты writer/researcher | meta-validator (LLM-критик не галлюцинирует); Q-вектор; Cross-Encoder reranker цитат | HIGH |
| **V4 Experiment** | `*-runner.md` обёртки (26 агентов) | Изоляция (seed/cache/reset); ветки; статистика; параллелизм | MEDIUM |
| **V5 Prompt** | `skills/`, `agents/*.md`, `config/` | Рендер `G(S_t)` в текст; версии шаблонов; кэш рендеров | MEDIUM |
| **V6 Negative** | `_AGENT_TECH/tech_debt_nkr.json` (73 TD), `legacy_archive` | FailurePattern (signature); embedding-поиск; garbage collection | HIGH |
| **V7 Execution** | MCP (searxng, sci-bot, downloader, gost_collector); model env | Единый LLMExecutionEngine (Pydantic-контракты, изоляция); DialogMemory | MEDIUM |
| **V8 Trace** | git-коммиты; `ARTIFACT_MAP.md`; hashes | TraceStore (TransitionRecord/ExperimentRunLog/FailureLog); reconstruct_state; GitHub | **BLOCKER** |

---

## 3. Порядок сборки (зависимости)

```
ЭТАП 0 (BLOCKER): V8 Trace + GitHub remote → git remote add + push
   ↓
ЭТАП 1 (BLOCKER): V2 Controller (Debt-Driven Cycle поверх существующих гейтов)
   ↓
ЭТАП 2 (HIGH):    V1 State (runtime_snapshot расширить) + V3 Filter (meta-validator)
   ↓
ЭТАП 3 (MEDIUM):  V4 Experiment (изоляция) + V7 Execution (единый движок)
   ↓
ЭТАП 4 (MEDIUM):  V5 Prompt (рендер S_t)
   ↓
ЭТАП 5 (HIGH):    V6 Negative Knowledge (паттерны + embedding)
```

**Фаза 1 (сведение DOM)** идёт параллельно Этапу 0-1 (не блокируется).

---

## 4. Техдолг по убыванию (блокеры → косметика)

### 🔴 БЛОКЕРЫ (нельзя выпускать без решения)

| ID | Ветка | Долг | Влияние |
|---|---|---|---|
| TD-REF-01 | V8 | **GitHub remote не настроен** — коммиты не пушатся, нет резерва | Блокирует всё |
| TD-REF-02 | V2 | **Нет Debt-Driven Cycle** — правки текста вручную, гейты не замыкают цикл | Блокирует эволюцию |
| TD-REF-03 | V2 | **Нет атомарности merge** (нет rollback при сбое) | Риск порчи состояния |
| TD-REF-04 | V8 | **Нет reconstruct_state** — нельзя воспроизвести `S_{t-1}+Δ→S_t` | Неверифицируемость |
| TD-REF-05 | V1 | **Нет Promotion Tactic→Policy** — правила не «взрослеют» | Стагнация |
| TD-REF-06 | V3 | **LLM-критик может галлюцинировать ошибки** (ложные срабатывания) | Каскад ложных экспериментов |

### 🟠 ВЫСОКИЕ

| ID | Ветка | Долг |
|---|---|---|
| TD-REF-07 | V3 | Cross-Encoder reranker для цитат не интегрирован |
| TD-REF-08 | V6 | Semantic search по архиву — нет калибровки порога |
| TD-REF-09 | V6 | Garbage collection не реализован (архив растёт) |
| TD-REF-10 | V1 | Нет версионирования StateVariable |
| TD-REF-11 | V2 | Статистический тест значимости merge — заглушка |
| TD-REF-12 | V5 | Рендер Negative Knowledge перегружает контекст |
| TD-REF-13 | V4 | Контроль источников корреляции (кэш/stateful) — частично |

### 🟡 СРЕДНИЕ

| ID | Ветка | Долг |
|---|---|---|
| TD-REF-14 | V2 | Pareto-проверка при merge — упрощена |
| TD-REF-15 | V4 | Нет параллельного запуска веток (async) |
| TD-REF-16 | V5 | Нет версионирования шаблонов (ломает старые ветки) |
| TD-REF-17 | V5 | Few-shot не отбираются адаптивно |
| TD-REF-18 | V7 | DialogMemory без компрессии |
| TD-REF-19 | V7 | Retry policy не различает rate-limit vs validation |
| TD-REF-20 | V3 | Нет калибровки порогов (τ для осей) |
| TD-REF-21 | V1 | Causal DAG захардкожен |
| TD-REF-22 | V8 | Нет hash-подписи состояния |

### 🟢 КОСМЕТИКА (LOW)

| ID | Ветка | Долг |
|---|---|---|
| TD-REF-23 | V8 | Нет UI для визуализации trace |
| TD-REF-24 | V4 | Нет визуализации графа веток |
| TD-REF-25 | V7 | Нет локального кэша одинаковых tool-calls |
| TD-REF-26 | V7 | Нет мониторинга latency/cost |
| TD-REF-27 | V5 | Нет кэша рендеров |
| TD-REF-28 | V6 | Нет экспорта архива |
| TD-REF-29 | V8 | Нет экспорта trace для рецензента |
| TD-REF-30 | V4 | Cherry-pick Delta между ветками |

---

## 5. Сводка по веткам

| Ветка | Blockers | High | Medium | Low | Итого |
|---|---|---|---|---|---|
| V1 State | 1 | 1 | 1 | 0 | 3 |
| V2 Controller | 3 | 1 | 1 | 0 | 5 |
| V3 Filter | 1 | 1 | 1 | 0 | 3 |
| V4 Experiment | 0 | 1 | 1 | 1 | 3 |
| V5 Prompt | 0 | 1 | 1 | 1 | 3 |
| V6 Negative | 0 | 2 | 0 | 1 | 3 |
| V7 Execution | 0 | 0 | 2 | 2 | 4 |
| V8 Trace | 2 | 0 | 1 | 1 | 4 |
| **ИТОГО** | **7** | **7** | **8** | **6** | **28** |

---

## 6. План действий (ближайшие шаги)

1. **Этап 0**: `git remote add origin <github-url>` + `git push` (нужен URL репо — см. вопрос).
2. **Этап 1**: создать `scripts/meta/contracts.py` (Pydantic: AcademicParagraph, SectionDebt, StateDelta, StateSnapshot, MergeRequest) + `scripts/meta/debt_cycle.py` (Драфт→Гейты→Debt→Хирургия→Перегейт) — **поверх существующих гейтов**.
3. **Фаза 1 (параллельно)**: сведение DOM (`nkr_ch1_dom_v2.yaml`) — как согласовано ранее.
4. **Этап 2**: расширить runtime_snapshot → state_manifest; meta-validator для V3.

---

## 7. Открытые вопросы (нужны решения)

1. **URL GitHub-репозитория** для `git remote add` (личный? название?). Токен есть.
2. **V2 глубина**: Debt-Driven Cycle (рекомендую) или сразу полный Evolutionary (Multi-Armed Bandit/статистика)?
3. **Суб-агенты**: (а) runner-обёртки сейчас + V7 позже, или (б) сразу единый ExecutionEngine?
4. **Что включить в GitHub-репо**: код+конфиг+scripts (рекомендую), исключить `патчи/легаси`/большие PDF?