# LEGACY: АУДИТОР HARNESS — ДОКУМЕНТАЦИЯ (для исследования)

**Дата:** 2026-09-30
**Статус:** LEGACY-документация (архив для исследования аудиторских механизмов)
**Относится к:** TD-163 (ReAct-валидатор), TD-164 (Meta-Cycle), V3 Filter, V-1 Health Monitor

---

## 1. Назначение документа

Зафиксировать **механизмы аудита** в Harness как единый слой, отделённый от генерации.
Это «легаси»-справочник: что делает аудитор, как он устроен, как подключается,
какие rule_id/паттерны использует, как интегрирован с ReAct-циклом и git-слиянием.

---

## 2. Слои аудита (как реализовано)

| Слой | Модуль | Что проверяет | Возвращает |
|---|---|---|---|
| **Гейты текста** | `writer/citation_trace.py`, `researcher/verify_claims.py` | Цитаты, клаймы, хеджи | PASS/FAIL |
| **ReAct-аудитор** | `meta/react_auditor.py` | Слоты (claim/warrant/modality) через tools | Observation (PASS/NEW/PERSISTENT) |
| **Физический аудитор** | `meta/health_monitor.py` (PhysicsValidator) | Размерности, числа, физика | DriftSignal |
| **Merge-аудитор** | `meta/merge_protocol.py` | Regression, инварианты, health при слиянии | MergeResult |
| **Монитор V-1** | `meta/health_monitor.py` | HP, тренды, демедж | HealthReport |

---

## 3. ReAct-аудитор (TD-163) — детали

### Принцип
LLM (Repair-агент) НЕ редактирует JSON напрямую. Она вызывает строго типизированные
инструменты внешнего аудитора, каждый из которых **детерминированно** валидирует.

### Инструменты (реализовано в `react_auditor.py`)
```python
tools = ReactAuditorTools(instance, validator_fn, max_iterations=5)
tools.modify_slot(slot_name, entity_id, modality)  # изменить слот
tools.add_slot(slot_name, entity_id, modality)     # добавить отсутствующий (warrant)
tools.submit_final()                               # финальная проверка
```
Каждый вызов возвращает `Observation`:
- `PASS` — ошибок нет
- `VALIDATION FAILED` + список `[severity] engine (rule_id): message`
- `MAX_ITERATIONS ... FAILED_REPAIR` — цикл не сошёлся → техдолг + human_override

### История (replay_history)
Каждый шаг `Thought → Action → Observation` сохраняется.
При сбое MERGE можно точно указать, на каком шаге ReAct-агент ошибся.

---

## 4. Правила/rule_id (паттерны аудита)

| rule_id | Движок | Смысл |
|---|---|---|
| RULE_CMP_01 | Completeness | Обязательный слот отсутствует (warrant) |
| RULE_REL_04 | RelationGraph | Data не может 'prove' Claim (несовместимость) |
| RULE_EPI_02 | EpistemicModality | Косвенное свидетельство не может 'proves' |
| AP-M03 | Physics (dimensional) | Размерностная ошибка |
| AP-S05 | Citation | Цитата-призрак (yaml_id не существует) |
| AP-S02 | Structure | Голые данные (evidence без analysis) |
| AP-T01 | Style | Вода (фразы-заполнители) |

Полный каталог антипаттернов: `docs/REFACTOR_REVIEW_2026-09-30.md` §8.

---

## 5. Интеграция с git-слиянием (TD-164)

Цикл: Baseline → Cycle → ErrorSet → RootCause → Branch → Repair(ReAct) → Merge → CleanReplay → Commit.

```
1. СОН (главная ветка): задача → черновик
2. ДЕМЕДЖ: аудитор (V-1 + гейты) → HP падает
3. СМЕРТЬ при HP < 50: DeathCertificate + AAR (причины = root causes)
4. ПОДЦИКЛЫ = git-ветки: каждая причина → fix-ветка (рефлексия)
5. REPAIR: в ветке ReAct-аудитор чинит слоты (modify/add/submit)
6. MERGE: MergeProtocol (three-way + regression + health + invariants) → main
7. ПРОСЫПАНИЕ: main обновлён, цикл продолжается (S_{t+1})
```

---

## 6. Трассируемость

- **TraceStore**: каждая ошибка аудитора, каждый ReAct-шаг, каждый merge — запись.
- **LegacyArchive**: провалы → паттерны → semantic search (не решать заново).
- **Вопрос «почему этот абзац так?»**: цепочка S_42 → failure → delta → experiment → merge.

---

## 7. Использование для исследования

Этот документ — отправная точка для изучения:
- как детерминированный аудит ограничивает генеративную LLM (принцип «код констрейн»);
- как ReAct-цикл превращает валидацию в верифицируемый диалог;
- как git-методики (three-way merge, cherry-pick, rebase) управляют эволюцией состояния.

**Связанные модули:** `scripts/meta/` (react_auditor, health_monitor, merge_protocol,
debt_cycle, trace_store, legacy, orchestrator).