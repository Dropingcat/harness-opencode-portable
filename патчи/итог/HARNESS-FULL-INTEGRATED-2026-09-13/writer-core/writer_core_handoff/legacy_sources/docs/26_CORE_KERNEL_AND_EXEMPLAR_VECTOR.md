# 26. Core Kernel: Exemplar Vector & Graph Recomposition

> Статус: **proposal / v0.3 core kernel** (зафиксировано 04.09.2026). Отвечает на вопрос: «как получить функцию/вектор из эталонов и как собрать/оптимизировать документ из черновиков под этот вектор».
>
> Это **ядро проекта** — всё остальное (RTT, dependency engine, release) обеспечивает его корректность. Принцип: **компилятор защищает, ядро формирует**.

---

## 1. Подтверждение постановки (ответ на «корректно ли описано?»)

**Да, две части ядра описаны корректно:**

1. **Обратное направление (эталоны → функция/вектор):**
   из статей/диссертаций/монографий → извлечение клаймов (на уровне researcher-фикстур) → построение **12 графов** → агрегация в **ExemplarFunctionVector**.

2. **Прямое направление (черновики → документ):**
   из черновиков автора → извлечение клаймов → построение **12 графов** → **оптимизация графа под целевой вектор** → компиляция в итоговый документ.

**Три уточнения (архитектурные, не опровергают схему, а до-определяют):**

- **У1. Вектор существует в нескольких разрезах, а не один.** Один «IDEAL-VECTOR» на жанр — самообман. Нужны: `FRAGMENT_VECTOR` (по типам фрагментов: абзац-результат, абзац-интерпретация), `SECTION_VECTOR`, `DOCUMENT_VECTOR`. Оптимизация идёт иерархически: абзац → раздел → документ (это наш же принцип суперпозиции).
- **У2. «Функция эталонов» — это не текст и не embedding-центроид.** Это **многомерный профиль дистрибуций** (типичные распределения), извлекаемый из графов, а не «среднее векторных эмбеддингов». См. §3.
- **У3. Оптимизация графа ≠ генерация текста.** Ядро перестраивает **структурную композицию** (какие claims, какие артефакты, в каком discourse-порядке, с какими связями). Текст генерируется уже после оптимизации, в пределах Writing Contract. Без этого «оптимизация под вектор» вырождается в prompting.

---

## 2. 12 графов (регистр, единый для эталонов и черновиков)

Используем регистр из `graph_registry.yaml` + дополнительные (итог — 12 проекций):

| # | Граф | Сущности | Authority | Роль в ядре |
|---|---|---|---|---|
| 1 | document_structure | Document/Section/Paragraph/Sentence/InlineNode | Writer | контейнерность |
| 2 | writing_decomposition | WritingObjective→…→RealizationUnitNeed | Writer | планирование |
| 3 | discourse | DiscourseMove/SectionIntent/ParagraphIntent/Transition | Writer | риторика |
| 4 | epistemic_argument | Claim/Evidence/Scope/Derivation/Gap/Conflict/… | **Researcher** | истина (read-only) |
| 5 | artifact_symbol | Quantity/Formula/Dataset/Table/Figure/Citation/Term | Writer+compute | объекты |
| 6 | citation_provenance | SentenceSpan→Claim→Evidence→Source | shared | трассировка |
| 7 | policy_constraint | Genre/Domain/Risk/Style/Numeric/CitationPolicy | static | правила |
| 8 | revision_dependency | DEPENDS_ON/INVALIDATES/REQUIRES_REVERIFY | Writer | инвалидация |
| 9 | execution | Run/Command/CapsuleRun/ValidatorRun/… | Writer | воспроизводимость |
| 10 | **vocabulary** (NEW) | Term/Symbol/Abbreviation (+domain jargon, slang) | Writer | терминосистема |
| 11 | **novelty_contribution** (NEW) | NoveltyClaim/ContributionNode/PriorArtCoverage | Writer+Researcher | новизна |
| 12 | **style_profile** (NEW) | StyleStats/ReferenceProfile/AuthorPersona | analytic (read-only) | стиль |

Графы 1–9 уже специфицированы в пакете; 10–12 добавляются для полноты «функции эталона».

---

## 3. ExemplarFunctionVector — как именно строится (ответ на «как?»)

**Вектор = кортеж нормированных дистрибуций**, каждая из которых извлекается детерминированно из 12 графов эталонов. НЕ среднее эмбеддингов.

### 3.1 Разрезы (dimensions)

```text
V = (
  # A. Дистрибуция claim-типов (epistemic_argument)
  claim_type_distribution,        # {OBSERVATIONAL: d1, INTERPRETIVE: d2, RECOMMENDATION: d3, ...}
  # B. Дистрибуция эпистемических статусов
  evidence_state_distribution,    # {SUPPORTED: d4, PARTIALLY_SUPPORTED: d5, DERIVED: d6, ...}
  # C. Плотность артефактов (artifact_symbol)
  artifact_density,               # {numbers_per_claim, formulas_per_1000w, tables_per_1000w, citations_per_claim}
  # D. Дискурс-шаблон (discourse) — чаще всего встречающаяся цепочка moves
  discourse_flow_profile,         # e.g. [STATE_OF_ART, GAP, METHOD, RESULT, INTERPRETATION, LIMITATION] + доли переходов
  # E. Аргументные схемы (epistemic + discourse)
  argument_scheme_frequency,      # {observation->interpretation->limitation: f1, definition->example: f2, ...}
  # F. Структура абзаца (document_structure)
  paragraph_signature,            # {avg_sentences, avg_claims_per_paragraph, claims_per_sentence}
  # G. Стиль (style_profile)
  style_vector,                   # {avg_sentence_len, passive_ratio, hedging_ratio, term_density, readability}
  # H. Терминосистема (vocabulary)
  term_concentration,             # {unique_terms_per_1000w, domain_jargon_density}
  # I. Графовая сигнатура (execution/epistemic структуры)
  graph_signature,                # {avg_degree, clustering, longest_path, bridge_density}
)
```

### 3.2 Алгоритм построения

```text
1. Корпус эталонов (жанр+domen filter): N отдельных работ.
2. Для каждой работы: Researcher-style claim extraction (см. §4) → rebuild 12 графов (в проекции Writer).
3. По каждому графу считаем детерминированные статистики (п. 3.1).
4. Агрегация: для каждого компонента — не среднее, а **МЕДИАНА + IQR** (устойчивая оценка типичного).
5. Кластеризация эталонов (по V^полному): получаем 1..k режимов жанра
   (e.g. «эмпирика-большинство», «теоретическая диссертация», «обзор большой»).
6. Итог: ExemplarFunctionVector_<genre>_<domain>_<regime> — версионируется, лежит в реестре.
```

**Калибровка (обязательно, как ADR-005b):** вектор валиден, только если отделяет «хорошие» эталоны от «заведомо плохих» (по метрике разделения in-distribution vs out-distribution). Иначе — диагностически бесполезен.

---

## 4. Извлечение клаймов из эталонов (глядя на researcher-фикстуры)

Опираемся на формат `malina_research_service_fixture.yaml` — он уже идеально подходит:

```text
source_registry   → S1..S17 (типы, роли, admission)
claims            → C_XXX_001 (proposition, claim_type, scope, status, evidence_refs,
                               source_refs, quantities, gaps, writer_policy)
quantities        → Q001 (attached_to, semantic, lower/upper/value, unit, provenance)
evidence_spans    → E001 (source_ref, report_location, relation, target_claims)
derivations       → D001 (output_claim, input_claims, operation, epistemic_status)
graph_edges       → {from, to, relation, status}
conflicts         → CF001 (members, observations, status, blocks, resolution_requirements)
gaps              → G001 (type, severity, status, need, blast_radius)
writer_context    → allowed/qualified/forbidden
research_queue    → priority, target_gap, operation, reason
```

**Значит, извлечение из эталонов = researcher claim extraction path (R1-staged: selection → disambiguation → decomposition → projection), выдающий тот же контракт.** Он уже спроектирован в researcher-архитектуре; для ядра Writer он **только читается** (read-only проекция, как ADR-004).

Заимствованный инструмент: **FActScore/SAFE/VeriScore/RefChecker** (см. §6) именно как подход к атомизации — но вывод типизированный, как в researcher-фикстурах.

---

## 5. Прямое направление: сборка из черновиков, оптимизация графа под вектор

### 5.1 Поток

```text
1. Черновики автора (текст, наброски, идеи, цифры)
   → ClaimProposal extraction (та же R1-машинерия)
   → 12 графов автора (в проекции Writer, с provenance к исходному черновику).

2. Выбор целевого режима: ExemplarFunctionVector (жанр+домен+режим).
   (Пользователь выбирает жанр/домен/«стиль-образцы»; вектор выбирается из реестра.)

3. Gap/Excess-анализ (детерминированный, по §3.1 компонентам):
   - чего не хватает по сравнению с вектором (deficit: нет RECOMMENDATION, мало citations, слабый discourse-шаблон);
   - чего избыточно (excess: слишком много ASSUMPTION без sources).
   Каждый deficit/excess → typed WriterGap / ExcessNote.

4. Оптимизация композиции (не текст!):
   - restructuring: переупорядочить абзацы/разделы под discourse_flow_profile;
   - selection: выбрать claims для слотов (кто лучше закрывает slot-профиль);
   - binding: привязать артефакты (числа/формулы/цитаты из авторских материалов);
   - tension: если вектор требует INTERPRETIVE, а evidence только OBSERVATIONAL — вернуть WriterGap (не галлюцинировать!);
   - global: собрать Section Interfaces (provides/requires), чтобы glued документ компилировался.

5. Realization: текст генерируется по Writing Contract для каждой ячейки (как обычно).

6. RTT + dependency + review + release (не меняются).
```

### 5.2 Ключевой инвариант прямой части

**Оптимизация НЕ повышает доказательную силу.**
- Вектор не может превратить `OBSERVATIONAL` в `CAUSAL` или `ASSOCIATION` в `MECHANISM` (запрещено semantic type system, docs/12).
- Если вектор требует эффект-класс, которого нет в черновике и нет в allowed projection → **WriterGap → RESEARCH_REQUEST**, а не LLM-доводки.
- Стилевой профиль может влиять только на realization (лексика/порядок), не на claim bindings (property test: «changing style profile cannot change claim binding set»).

---

## 6. Заимствования с GitHub (что именно берём)

| Компонент ядра | GitHub-инструмент | Что берём | Как встраиваем |
|---|---|---|---|
| claim extraction (эталоны/черновики) | FActScore, SAFE, VeriScore, RefChecker | атомизация, separate verifiability, triplets as projection | staged extractor (Selection→Decomposition→Projection) в researcher-стиле |
| дискурс-связанность | DiscoRST / ATT-RST (RST parsing) | rhetorical structure → discourse flow profile | candidate signals для discourse_flow_profile (english, затем RU-адаптация) |
| графовая сигнатура | graph2vec, WL-kernel, networkx | граф→вектор/сигнатура | graph_signature компонента (диагностическая, не gate) |
| стилевой вектор | bge-m3, sentence-transformers | RU/EN embedding для style/text proximity | style_vector (read-only диагностика) |
| линейно-AES-качество | BARTScore, UniEval | reference-based quality axes | QualityLens (не компилятор; диагностика, см. ADR-005) |
| оценка coverage/summary | QuestEval | question-based fidelity | вспомогательно для RTT-X |
| argument schemes | Argdown, Carneades | аргументные карты и схемы | argument_scheme_frequency |
| факт-проверочные бенчмарки | RAGChecker, SciFact | recall/precision компоненты | верификация качества extraction |

Правило (из researcher-обзора): все перечисленные — **atomic solutions за антикоррупционными адаптерами**, не core dependency, не авторитет состояния.

---

## 7. Симуляция прохода (прогон по архитектуре)

### 7.1 Сценарий: диссертация ВАК по материаловедению, 30 эталонов

**Обратное направление:**
```
30 диссертаций/статей (материаловедение, RU)
→ parsing (GROBID+Docling) → claim extraction (R1) → 12 графов на каждую
→ агрегация (§3.2) → ExemplarFunctionVector_materials_dissertation@v1
  (медиана±IQR по claim_type_distribution, artifact_density, discourse_flow, style, graph_sig)
→ кластеризация → 2 режима: «оригинальное исследование» vs «компилятивный обзор»
```

**Прямое направление:**
```
Черновик автора (50 стр. набросков: результаты опытов, таблицы, ссылки)
→ claim extraction → 12 графов черновика
→ выбор режима «оригинальное исследование»
→ Gap-анализ:
    deficit: нет INTERPRETATION после каждого RESULT; 0.3 formula/1000 слов (нужно 0.6);
    excess: 40% ASSUMPTION без sources (целевой 15%);
    discourse: черновик прыгает RESULT→CONCLUSION без INTERPRETATION;
→ Оптимизация: переупорядочение + привязка артефактов + WriterGap-запросы на недостающие интерпретации
→ Realization → RTT → ревью → release
```

### 7.2 Где это будет ломаться — фиксация предсказываемых ошибок

| # | Ошибка | Фаза | Причина | Мера |
|---|---|---|---|---|
| O1 | extractor-шум: неатомарные claims из эталонов | обратная | LLM не дробит корректно (FActScore-проблема) | staged extraction + decomposition eval (калибровочный корпус) |
| O2 | потеря scope/модальности при извлечении | обратная | «12.5 µm при 640°C» → «12.5 µm» | QuantityView + ScopeExtraction обязательны (docs/12, fixture malina) |
| O3 | жанровая каша: статья смешана с диссертацией | обратная | вектор считался без жанр-фильтра | жанр+домен обязательный фильтр (§3.2); иначе ExclusionRule |
| O4 | «эффект среднего»: медиана никуда не ведёт | обратная | один вектор на всё | кластеризация режимов (§3.2 шаг 5); пользователь выбирает режим |
| O5 | оптимизация пытается усилить epistemic | прямая | вектор требует CAUSAL, есть только OBSERVATIONAL | semantic type checker блокирует (docs/12), не «подгоняем» |
| O6 | перекомпоновка ломает RTT (смысл абзаца меняется) | прямая | discourse-перестройка затрагивает claim bindings | разделение структурной композиции и realization; RTT обязателен после перестроя |
| O7 | провенанс-смешение: чужой claim из эталона стал фактом чужих | прямая | retrieval вернул чужой claim как основу | корпус-референс никогда не входит в factual provenance (docs/07, 15, 25) |
| O8 | стилевой вектор дрейфует (RU/EN, жанр) | обе | embedding чувствителен к регистру/длине | style_profile версионируется; калибровка OOD (osint/07 паттерн) |
| O9 | вектор недостижимо амбициозен (диссертация за 2 дня) | прямая | не учли budget/источники | BudgetBlocker + realizeable-plan; вектор = guidance, не приговор |
| O10 | cost-взрыв: 30 эталонов × extract × 12 графов | обратная | тяжёлая индексация | батчинг, кэш фикстур, инкрементальная перестройка только stale-частей |

### 7.3 Ошибки, которые РЕАЛЬНО возникают быстрее всего (прогноз по приоритету)

1. **O1 + O2** (шумы извлечения) — убьют весь вектор, если не начать с калибровочного корпуса (50 ручных claims → измерить extractor precision/recall). Без этого весь «вектор идельного текста» — эхо шума.
2. **O4** («эффект среднего») — второй по времени: один вектор на жанр породит «безжизненную середину». Кластеризация режимов — не опция, а необходимость.
3. **O5** (epistemic усиление) — система попытается «дорисовать» выводы. Семантический тип-чекер и WriterGap обязательны до любой оптимизации.
4. **O7** (провенанс-смешение) — самый опасный для научной честности. Даётся инвариантом: reference никогда не факт.

---

## 8. Гейты ядра (порядок не менять)

1. **G-1 Calibration extractor:** ручной корпус 50 claims → extractor precision/recall ≥ порога (по fragment class). Без G-1 нельзя строить вектор.
2. **G-2 Vector sanity:** правильный корпус 30 эталонов vs «деревянные» кандидаты — разделение замерено (silhouette/separability). Один вектор на всё — fail.
3. **G-3 One-paragraph compile:** реальный мини-сценарий «черновик+вектор→оптимизация→RTT PASS». M1 + ядро вместе.
4. **G-4 Provenance:** ни один factual claim текста не происходит из reference-корпуса (инвариант, тест навязываемый).
5. **G-5 Budget/cost:** cost идёт в BuildManifest; вектор не позволяет превысить budget.

---

## 9. Следующие конкретные шаги

1. Зафиксировать этот документ как `docs/26_CORE_KERNEL_AND_EXEMPLAR_VECTOR.md` (сделано выше — он и есть этот файл).
2. Дописать ADR-016: «ExemplarVector — diagnostic, никогда не усиливает epistemics».
3. Создать `schemas/exemplar_vector.schema.yaml` (структура V из §3.1) + `schemas/kernel_report.schema.yaml`.
4. Построить калибровочный корпус claims (минимум 50) и прогон G-1 на extractor-кандидате.
5. Подключить `graph2vec`/WL-kernel сигнатуру как `graph_signature` компоненту (read-only).
6. Встроить вектор в `WriterRegistry` как read-only projection (не authoritive state).

> **Резюме для вас:** постановка ядра верна. Ключевые добавки к ней: (а) вектор = многомерный профиль дистрибуций из 12 графов (не embedding-среднее); (б) оптимизация = перестройка композиции и привязка артефактов, но НЕ повышение доказательной силы; (в) начинать с калибровки extractor, иначе весь вектор будет эхо шума извлечения.