# Writer Traceability Contract — прослеживаемость и неопределённость как первичная структура

> Shared-контракт для writer-контура (writing-orchestrator, article-writer) при создании
> научных и инженерных произведений: **диссертаций, монографий, учебной литературы**.
>
> **Принцип:** Прослеживаемость (каждое утверждение → источник/цитата) и неопределённость
> (степень подтверждённости) — НЕ свойства прозы. Они первичны и живут в **DOM YAML** —
> структурном файле литературного объекта. Проза — только выходной формат этого DOM.

## 1. Иерархия истины

```
DOM YAML (источник истины: structure + claims + graphs + traceability + uncertainty)
   ↓
Готовый текст (один из многих выходов; прослеживаемость в тексте = `[Sxx]`/`[Cxx]` ссылки)
```

Правила:
1. Writer пишет текст, но НЕ выдумывает факты — каждый фактический клайм уже есть в DOM.
2. Если в прозе появилось утверждение, которого нет в DOM — это ошибка. Writer обязан
   сначала добавить claim в DOM (с источником), потом писать.
3. Если DOM-claim не подтверждён (UNSUPPORTED/OPEN) — в тексте это маркируется
   неопределённостью, а не подаётся как факт.

## 2. Формат DOM YAML (литературный объект)

```
product:
  id: PROD-001
  kind: dissertation | monograph | textbook | paper   # шаблон, выбранный после постановки задачи
  title: ...
  status: drafted | editing | review | done

structure:                     # базовая структура из шаблона
  chapters:
    - id: CH-01
      title: ...
      sections:
        - id: SEC-01-01
          title: ...
          paragraphs:
            - id: PAR-01-01-01
              claims: [C-001, C-002]      # какие клаймы этот параграф выражает
              text: ""                     # заполняется черновиком

claims:                        # реестр утверждений (совместим с research-контуром)
  - id: C-001
    text: "гуматы повышают эффективность удобрений на 15–30%"
    kind: factual | derived | assumed | recommendation
    evidence:
      - source_id: S-012
        span: "p.47, §3.2: «...»"          # ТОЧНАЯ цитата, не пересказ
    verification:
      verdict: SUPPORTED | CONTRADICTED | UNSUPPORTED | AMBIGUOUS | OPEN   # от fact-checker
      confidence: 0.8                        # 0.0–1.0
      numeric_comparison: {...}              # если число, прошло numeric_comparator
      verified_at: ...

graphs:                        # базовые графы связей между клаймами
  - id: GRAPH-01
    kind: derivation | support | conflict | citation_chain
    edges:
      - from: C-001
        to: C-002
        relation: derived_from | supports | contradicts | depends_on

uncertainty:                   # неопределённость — первичное поле, не послесловье
  C-001: { level: established | inferred | assumed | disputed, note: "..." }
  C-002: { level: assumed, note: "экстраполяция из C-001" }

sources:                       # реестр источников
  - id: S-012
    ref: "Author. Title. Journal, year, p.47"
    doi: ...
    url: ...
    kind: primary | secondary
    accessed: ...
```

## 3. Рабочий цикл

1. **Постановка задачи** → выбор шаблона (`kind`: dissertation/monograph/textbook/paper).
2. **Создать DOM YAML** из шаблона: базовая структура (главы/секции) + **уже известные
   объекты как клаймы** + базовые графы (известные утверждения и их связи).
3. **Добавление черновиков**: каждый черновик заполняет `paragraphs[].text`; для новых
   утверждений Writer создаёт claim и **запрашивает источники** (через research-контур /
   source-fetcher), а не пересказывает.
4. **Когда параграф заполнен** → **стилистический синтез**: итеративно, используя
   **референсные работы из академических источников** (которые ТОЖЕ разбиты на клаймы и
   графы — их claim-структура загружается в `graphs` как модели стиля/структуры).
5. **Гейт прослеживаемости** (детерминированный, до выдачи): каждое фактическое утверждение
   в тексте → claim в DOM → source + span + verdict. Неопределённость явная.
6. **Выход**: сгенерированный текст из DOM (markdown/latex) + сам DOM как артефакт.

## 4. Референсные работы как клаймы

Для стилистического синтеза используются академические работы-образцы. Они разбираются
как обычные тексты: `claim-parser` → клаймы → графы. Writer загружает их claim-структуру
как **модель стиля/аргументации** (как открывают главу, как связывают секции, где
цитируют), но НЕ копирует содержание.

## 5. Гейт «нельзя выдать»

Гейт — детерминированный скрипт `${OPENCODE_HARNESS_ROOT}/scripts/writer/citation_trace.py`
(WS-18). Он сам проверяет (модель-агностично):

- есть фактическое утверждение без claim_id в DOM → `orphan_claim`;
- есть claim без source/span → `dangling_claim` / `dangling_source`;
- есть claim с verdict=UNSUPPORTED/AMBIGUOUS/OPEN или level=assumed/disputed,
  поданный без маркера неопределённости → `masked_uncertainty`;
- есть `[Sxx]`-ссылка в тексте, не резолвящаяся в `sources` → `dangling_source`;
- числовой claim без `numeric_comparison` → `numeric_unverified`;
- внутренняя перекрёстная ссылка `[§N]` на несуществующую секцию → `dangling_section`;
- claim с `derived_from` без перекрёстной ссылки на источник вывода → `missing_crossref` (warn).

Запуск перед выдачей:
```
python "${OPENCODE_HARNESS_ROOT}/scripts/writer/citation_trace.py" --text <draft.md> --dom <slug>-dom.yaml [--strict]
```
exit 0 = PASS (можно выдавать), exit 1 = FAIL (править и перезапускать).

## 6. Интеграция с research-контуром

- `claims[].verification.verdict` — приходит из fact-checker (тот же словарь: SUPPORTED/
  CONTRADICTED/UNSUPPORTED/AMBIGUOUS/OPEN).
- `claims[].verification.numeric_comparison` — из numeric_comparator.
- Источники — из source-fetcher / локального корпуса.
- Writer НЕ ведёт верификацию сам — он **потребляет** её из DOM.

## 7. Совместимость

- Этот контракт — расширение `writing-orchestration-process.md` для научных/инженерных жанров.
- `ai-slop-avoidance` — вторичный стилистический гейт поверх прослеживаемости, не заменяет её.
- Готовый текст несёт `[Sxx]`/`[Cxx]`/`[§N]` ссылки — они проверяются детерминированным
  цитатным аудитом (см. `scripts/writing/citation_trace.py`, WS-18).