# ДОПОЛНЕНИЕ К ПЛАНУ РЕФАКТОРИНГА — РЕВЬЮ 2026-09-30

**Дата:** 2026-09-30
**Статус:** КРИТИЧЕСКИЙ АУДИТ + РАСШИРЕНИЕ (интегрировано в REFACTOR_PLAN_2026-09-22)
**Автор ревью:** архитектурная сессия (владелец проекта)
**GitHub:** ветка `refactor-v2` запушена (2026-09-22) — `https://github.com/Dropingcat/harness-opencode-portable/pull/new/refactor-v2`

---

## 1. Критические пробелы исходного плана (исправлены)

| Пробел | Исправление |
|---|---|
| Нет Definition of Done | ДОПОЛНЕНИЕ §2 (DoD для Этапов 0-2) |
| Нет плана тестирования | ДОПОЛНЕНИЕ §3 (unit/integration/regression) |
| Нет стратегии миграции | ДОПОЛНЕНИЕ §4 (Feature Flags + Parallel Run + Gradual Rollout) |
| Нет Pydantic-контрактов для блокеров | ДОПОЛНЕНИЕ §5 (contracts.py, debt_cycle.py, trace_store.py) |
| Нет рисков/митигаций | ДОПОЛНЕНИЕ §6 |
| Нет интеграции с гейтами | ДОПОЛНЕНИЕ §7 (GateAdapter) |
| Нет плана отката | ДОПОЛНЕНИЕ §4.2 |
| Нет семантики «что хорошо/плохо» | ДОПОЛНЕНИЕ §8 (варгейминг, MEAL, антипаттерны) |

---

## 2. Definition of Done (DoD) по этапам

### Этап 0 (V8 Trace + GitHub) — DONE 2026-09-22
- [x] Все коммиты запушены в GitHub (ветка refactor-v2, 146 коммитов)
- [ ] Создан `scripts/meta/trace_store.py` (TraceEntry, TraceStore)
- [ ] Существующие скрипты (citation_trace/draft_loop/verify_claims) логируют ≥1 TraceEntry
- [ ] `reconstruct_state(version_id)` воспроизводит runtime_snapshot
- [ ] Тест `tests/test_trace/test_reconstruct.py` проходит

### Этап 1 (V2 Debt-Driven Cycle)
- [ ] `scripts/meta/contracts.py` (AcademicParagraph, SectionDebt, StateDelta, StateSnapshot, MergeRequest)
- [ ] `scripts/meta/debt_cycle.py` (run_debt_driven_cycle: Draft→Gates→Debt→Surgery→ReGate, max_iter=3)
- [ ] Интеграция с draft_loop.py (расширяет, не ломает)
- [ ] Тест `tests/test_controller/test_debt_cycle.py` (≤3 итерации, монотонный спад долга, гейты PASS)
- [ ] Механизм отката (возврат последнего валидного + нерешённые долги)

### Этап 2 (V1+V3)
- [ ] runtime_snapshot → state_manifest.json (version_id, timestamp, variables, error_vector, active_tactics_ttl)
- [ ] Promotion Tactic→Policy (success_count ≥ 3)
- [ ] `scripts/meta/meta_validator.py` (LLM-критик не галлюцинирует: precision ≥ 0.95)
- [ ] Q-вектор (ErrorVector) после каждого прогона
- [ ] state_manifest обратно совместим с runtime_snapshot

---

## 3. План тестирования

**Уровень 1 — Unit (на ветку):** V1 Promotion/StateVariable; V2 DebtCycle/атомарность/откат; V3 meta-validator/Q-вектор; V4 изоляция; V5 рендер/версии; V6 поиск/GC; V7 движок/память; V8 TraceStore/reconstruct.

**Уровень 2 — Integration:** полный цикл S_t→Generate→Filter→Debt→Resolve→S_{t+1}; изоляция параллельных прогонов; Negative Knowledge блокирует повторы.

**Уровень 3 — Regression:** прогнать `nkr_ch1_dom.yaml` (58 клаймов) через Debt-Driven Cycle; сравнить с draft_loop (не хуже по гейтам, ≤3 итерации, техдолг структурирован).

---

## 4. Стратегия миграции

**Feature Flags** (`config/feature_flags.json`): `debt_driven_cycle_enabled`, `trace_store_enabled`, `meta_validator_enabled` — все false.

**Parallel Run:** новая система параллельно со старой (draft_loop), сравнение метрик гейтов.

**Gradual Rollout:** 10% → 50% → 100% задач.

**Откат:** при сбое → флаг false → вернуться к draft_loop → анализ логов V8 → исправить → повторить.

---

## 5. Pydantic-контракты (ключевые)

### contracts.py (ядро)
```python
class DebtType(str, Enum):
    CITATION_MISSING, CITATION_MISMATCH, CLAIM_UNVERIFIED, LOGIC_GAP, STYLE_VIOLATION
class DebtSeverity(str, Enum): CRITICAL, MEDIUM, LOW
class SectionDebt(BaseModel):
    debt_id: str; paragraph_index: int; debt_type: DebtType
    severity: DebtSeverity; description: str; gate_source: str; suggested_fix: str|None
class AcademicParagraph(BaseModel):
    paragraph_index: int; text: str; claims: list[str]
    citations: list[str]; debts: list[SectionDebt]; version: int = 1
class DraftSection(BaseModel):
    section_id: str; paragraphs: list[AcademicParagraph]
    iteration: int = 0; max_iterations: int = 3
    @property critical_debts -> list[SectionDebt]
    @property is_approved -> bool  # critical_debts == []
```

### debt_cycle.py
```python
class DebtDrivenCycle:
    def __init__(self, gates: list[Callable], resolver: Callable): ...
    def run(self, task, initial_draft: DraftSection) -> DraftSection:
        for iteration in range(max_iter):
            for gate in gates: gate(draft)         # добавляет долги
            if draft.is_approved: break
            for debt in draft.critical_debts: draft = resolver(draft, debt)
            # очистка решённых CRITICAL
        return draft
```

### trace_store.py
```python
class TraceEntry(BaseModel):
    entry_id, timestamp, source_branch, event_type, payload, related_state_version, related_branch_id
class TransitionRecord(BaseModel):
    from_version, to_version, delta, evidence, metrics_before, metrics_after, timestamp
class TraceStore:
    append(entry); reconstruct_state(version_id)  # replay S_0 + Δ_1..Δ_n
    verify_transition(from_v, to_v) -> bool
```

---

## 6. Риски и митигации

| Риск | Вер. | Влияние | Митигация |
|---|---|---|---|
| DebtCycle не сходится за 3 итер. | Выс | Сред | Откат к последнему валидному |
| LLM-критик галлюцинирует | Выс | Крит | meta-validator (precision ≥0.95) |
| reconstruct не воспроизводит | Сред | Крит | тест на всех снимках |
| Медленнее старой | Сред | Сред | кэш, параллелизм |
| Миграция ломает сценарии | Сред | Крит | Feature Flags + Rollout |
| V6 архив растёт | Выс | Сред | garbage collection |
| NK перегружает промпт | Сред | Выс | top-k=3 по релевантности |

---

## 7. Интеграция с гейтами (GateAdapter)

```python
class GateAdapter:
    def __init__(self, gate_function, gate_name): ...
    def __call__(self, draft):  # прогон гейта → SectionDebt → draft.debts
```
Маппинг типов: missing_citation→CITATION_MISSING, citation_mismatch→CITATION_MISMATCH, unverified_claim→CLAIM_UNVERIFIED.

---

## 8. Варгейминг, MEAL, антипаттерны

### Принципы (инварианты нулевого уровня)
- П1 «Простейшее — сложнее всего»: инварианты > политики > тактики.
- П2 «Меньше ошибок»: цель = argmin E(S_t), не max Quality.
- П5 Flashback = откат состояния, не текста.
- П6 AAR: каждый провал → error_pattern → corrective_rule.
- П8 Фильтр не генерирует; контроллер не критикует — разделение ролей.

### MEAL-структура абзаца (инварианты V1)
M=Topic(INVARIANT), E=Evidence(INVARIANT), A=Analysis(POLICY), L=Link(POLICY), C=Citations(INVARIANT).
Формальный: `∀p ∈ paragraphs: p.evidence != '' ∧ p.citations != []` и `¬(evidence=='') ∧ (analysis=='')`.

### Антипаттерны (каталог V6)
- **Структурные (CRITICAL):** AP-S01 пустой тезис, AP-S02 голые данные, AP-S03 голый анализ, AP-S04 разорванная связка, AP-S05 цитата-призрак.
- **Семантические (CRITICAL):** AP-M01 ложная каузальность, AP-M02 подмена понятий, AP-M03 размерностная ошибка, AP-M04 экстраполяция, AP-M05 устаревшие данные.
- **Стилистические (TACTICAL):** AP-T01 вода, AP-T02 ложная скромность, AP-T03 научпоп, AP-T04 повторение, AP-T05 перегруженность.
- Каталог: `config/anti_patterns_catalog.yaml` (детектор + corrective_rule).

---

## 9. Новые техдолги (интеграция в сводный реестр)

| ID | Ветка | Долг | Приоритет |
|---|---|---|---|
| V1-TD-NEW-01 | V1 | Закодировать MEAL-инварианты в 01_INVARIANTS.md | Critical |
| V1-TD-NEW-02 | V1 | Словарь filler_patterns («вода») | High |
| V1-TD-NEW-03 | V1 | Словарь физических терминов (AP-M02) | High |
| V2-TD-NEW-01 | V2 | Иерархия угроз (4 уровня) в DebtCycle | Critical |
| V2-TD-NEW-02 | V2 | SURGERY с Flashback | Critical |
| V2-TD-NEW-03 | V2 | CatastrophicFailure exception (Level 0) | High |
| V3-TD-NEW-01 | V3 | Детекторы антипаттернов AP-S01..AP-T05 | Critical |
| V3-TD-NEW-02 | V3 | Code Interpreter dimensional analysis (pint/sympy) | High |
| V3-TD-NEW-03 | V3 | Temporal check устаревших данных | Medium |
| V5-TD-NEW-01 | V5 | Шаблон SURGERY (антипаттерн + corrective rule) | Critical |
| V5-TD-NEW-02 | V5 | Инжекция антипаттернов в EXECUTION | High |
| V5-TD-NEW-03 | V5 | Few-shot «хороший vs плохой» параграф | Medium |
| V6-TD-NEW-01 | V6 | Каталог антипаттернов как FailurePattern | Critical |
| V6-TD-NEW-02 | V6 | Маппинг провал→антипаттерн | High |
| V6-TD-NEW-03 | V6 | Promotion: AP > 5 раз → Policy | Medium |

**Итого:** +15 новых TD → сводный реестр: 28 (план) + 15 (ревью) = **43 TD**.

---

## 10. Обновлённая сводка приоритетов

| Приоритет | Кол-во | Ключевые |
|---|---|---|
| 🔴 Блокеры | 12 | V8-Trace, V2-DebtCycle, V2-Flashback, V3-meta-validator, V1-Promotion, V2-NEW-01/02, V3-NEW-01, V5-NEW-01, V6-NEW-01 |
| 🟠 Высокие | 12 | V3-reranker, V6-semantic, V6-GC, V1-versions, V2-stat, V4-isolation, NEW-02 |
| 🟡 Средние | 12 | V2-pareto, V4-async, V5-templates, V7-memory, V3-calibration, NEW-03 |
| 🟢 Косметика | 7 | V8-UI, V4-graph, V7-cache, V7-monitor, V5-cache, V6-export, V8-export |
| **Итого** | **43** | |

---

**Статус:** ИНТЕГРИРОВАНО. Следующий шаг — Этап 0 (TraceStore, TD-REF-04/V8).