# writer-core — Architecture

> Зафиксировано: 2026-09-03. Цель: Writer-Orchestrator для академических текстов ВАК-уровня(диссертации, монографии, научные отчёты, longreads). Принцип: **текст как код** (doc-as-code, из docops-hq/learnapidoc-ru), но глубже: единицы информации с версиями, провенансом и рецензированием.



## 1. Ключевая идея: «гит для документа, но глубже»

| Git (файлы) | writer-core (units) | Что глубже |
|---|---|---|
| файл | WriterUnit (абзац/утверждение/объект) | гранулярность меньше файла |
| commit | WriterTransaction (атомарное изменение N юнитов) | атомарность на уровне юнитов |
| tag | WriterSnapshot (именованное состояние документа) | + эпистемический статус каждого юнита |
| blame | ревизия юнита WUT_001@1 → @2 | история per-unit, не per-file |
| diff | unit-level diff (текст/статус/провенанс) | diff не строками, а смысловыми единицами |
| — | провенанс юнита (какой claim/evidence) | git этого не знает |
| — | review-статус юнита (DRAFT→SELF_CHECKED→REVIEWED→APPROVED) | git этого не знает |



## 2. Симметрия с researcher-core

```
researcher-core (эпистемика)          writer-core (текст)
─────────────────────────────         ─────────────────────────────
Claim / Quantity / Source             WriterUnit (абзац/утверждение/объект)
GraphEdge (supports/derived_from)     UnitRelation (chapter→section→paragraph,
                                       supports, cites)
GraphTransaction                      WriterTransaction
event log (append-only)               writer event log
revision C001@1→@2                    revision WUT_001@1→@2
Snapshot                              WriterSnapshot (именованный)
R1/R3 validators                      writer validators (атомарность,
                                       провенанс, цитирование, стиль,
                                       консистентность)
WriterEligibility                     WriterUnitStatus
```

И главное: **юниты ссылаются на claims** из researcher-core (`unit.provenance → [CLM_..., EVD_...]`)。Это закрывает петлю: исследование → текст → проверка текста против исследования.С



## 3. Модель данных (финальная, по решениям пользователя)

```
WriterDocument (title, genre, spec_vak, ГОСТ-параметры)
 └── WriterUnit
      ├── type: section | paragraph | assertion | object
      ├── text (для section/paragraph/assertion)
      ├── object_payload (для object: value, unit, formula, citation)
      ├── status: DRAFT→SELF_CHECKED→REVIEWED→APPROVED | BLOCKED | SUPERSEDED
      ├── order (канонический порядок в документе)
      ├── provenance: [CLM_..., EVD_...] (для assertions)
      ├── review: checklist + verdict + reviewer
      └── revisions: WUT_001@1 → @2 (текст+мета+объект)
```

**Object-юниты** (ключевая фишка, решение пользователя):
- `number` — число + единица + размерность (Decimal, unit через pint)
- `formula` — LaTeX/математическая формула + переменные + диапазоны
- `citation` — библиографическая ссылка (ГОСТ Р 7.0.5)
- `term` — определение термина

Проверяются **детерминированно**: число/размерность/формула/ГОСТ — без LLM. Это делает ядро проверяемым, а не «модель уверена».



## 4. Статусы юнитов

```
DRAFT → SELF_CHECKED → REVIEWED → APPROVED
   ↑          │              │
   └── BLOCKED (нарушает запрет/стиль/ГОСТ)
   └── SUPERSEDED (заменён новым юнитом)
```



## 5. Цикл письма с рецензированием

```
dissertation_framer → скелет документа (главы/разделы как пустые юниты)
  → writer_context.json (allowed/qualified/forbidden claims — из researcher-core)
  → Hermes adapter пишет юниты (cells → юниты, главы по плану)
  → ДЕТЕРМИНИРОВАННЫЕ валидаторы на каждый юнит:

      • UnitAtomicity    (утверждение атомарно)
      • UnitProvenance   (нет claim-без-источника; выводы помечены как свои)
      • UnitCitation     (ссылки резолвятся, ГОСТ Р 7.0.5)
      • UnitStyle        (канцелярит/пассив/читаемость — proselint-правила)
      • UnitConsistency  (нет противоречащих юнитов)
      • WriterEligibility(юнит не содержит forbidden claims)
  → SELF-CHECK райтером (по чеклисту, статус per-unit)
  → опционально рецензент(человек/субагент) → REVIEWED/APPROVED
  → WriterSnapshot перед каждым экспортом(откат в любой момент)
  → экспорт: юниты → Markdown (канонический порядок) → Pandoc → DOCX/PDF ГОСТ
```



## 6. Фазы сборки

| Фаза | Модуль | Что делает | Тесты | Статус |
|---|---|---|---|---|
| A | writer-core R0 | Unit/Transaction/Snapshot/event-log + SQLite | да | ⏳ скелет, 15 тестов OK |
| B | writer validators | атомарность, провенанс, стиль, консистентность, object-проверка (число/формула/ГОСТ) | да | ❌ не начато |
| C | Dissertation Framer | скелет ВАК + аппарат (ГОСТ Р 7.0.11) | да | ❌ не начато |
| D | WriterContext bridge | из researcher-core (allowed/qualified/forbidden — уже есть `writer_context` в artifact_builder.py) | да | ⚠️ частично есть в researcher |
| E | Hermes adapter | patch_planner → юниты; reverify → перепроверка | да | ❌ не начато |
| F | Style-profiler | эталонные профили из F:\AnalisysDataSet\pdfs | да | ❌ не начато |
| G | Экспорт MD + Pandoc | юниты → MD → DOCX/PDF ГОСТ | да | ❌ не начато |
| H | Рецензент-субагент | REVIEWED/APPROVED для спорных | интеграция | ❌ не начато |
| I | Интеграция + отчёт | writing-orchestrator + полные тесты | да | ❌ не начато |

Каждый модуль — через фабричный цикл «воркер→ревьюер→тестер».



##  ​7. Факты из существующего кода (Hermes writer на Z:)

- **patch_planner**: `plan_patches(verdicts, questions, author_answers, topics_tree, patterns)` → plan; `_grow_cells(...)` — растёт cells и групп; `plan_to_sexpr/plan_to_json` — выход.
- **state_machine**: `create_state/advance_phase/start_new_iteration/finalize/recover/validate` — фазовая машина писателя (схема `WriterStateModel` в schemas.py,pydantic)。
- **writer_orchestrator**: `_writer_system()`, `_writer_user(claim_text, issue, answer, gi)`, роли: `_critic_task`, `_proofreader_task`, `_editor_task`, `_extract_reviewer` — конвейер ролей для правок.

- **Вход Hermes writer**: `verdicts_processed.json` (из verification-pipeline, не из researcher-core）。
- **Окружение**: Python 3.12 + pydantic (schemas.py), без pint.



##  ​8. Ключевые решения (зафиксировано с пользователем)

1. **Отдельный проект** writer-core (рядом с researcher, `E:\Documents\Документы\writer-core`。
2. **Гранулярность**: абзацы + утверждения + **объекты** (значения, единицы измерения, формулы, термины)。
3. **Рецензирование**: авто + self-check + субагент-рецензент。

4. **Окружение**: Python 3.12 + **pydantic** + **pint** (для объектов)。
5. **Формат выхода**: Markdown + **Pandoc** (ГОСТ Р 7.0.5 / Р  ​​​​​​​7.0.11) → DOCX/PDF。



6. **Язык/стандарт**: русский академический, **ГОСТ**。
7. **Корпус эталонов**: `F:\AnalisysDataSet\pdfs` (~400 PDF, включая реальные диссертации/авторефераты; есть дубликаты, подлежат дедупу)。
8. **Старт**: с Фазы A (R0, уже скелет→ доделать registry/snapshot/diff), затем B (валидаторы), C (фреймер)。



##  ​9. Следующий шаг (рекомендация)

1. **Фаза A завершить**: registry (полный CRUD юнитов/документов/снапшотов), snapshot/diff (детерминированные, per-unit)。 2. **Фаза B**: writer validators (UnitAtomicity, UnitProvenance, UnitCitation(ГОСТ), UnitStyle, UnitConsistency, ObjectValidator(number/formula/citation/term))。
 3. **Фаза C**: Dissertation Framer (скелет ВАК: введение, главы, заключение + научный аппарат)。
 4. **Фаза D**: WriterContext bridge (переиспользовать `artifact_builder.writer_context` из researcher-core)。
 5. **Фаза E**: Hermes adapter (patch_planner → юниты, state_machine → фазы, reverify → перепроверка)。
 6. Затем F/G/H/I (style-profiler, экспорт, рецензент, интеграция)。
```