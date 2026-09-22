# Researcher Core: code-first ядро, граф клаймов и модульная стыковка блоков

## 0. Назначение документа

Этот документ фиксирует архитектуру будущего `researcher`-ядра для opencode. Цель — не заменить текущий подробный Markdown-отчёт, а добавить под ним машинно-проверяемый слой:

```text
raw_report.md
  ↓
claims.json
  ↓
epistemic/provenance graph
  ↓
deterministic validators
  ↓
targeted research tasks
  ↓
writer_context.json
  ↓
final_answer.md
```

Главный принцип:

> LLM предлагает семантические изменения состояния. Код принимает, отклоняет, валидирует и хранит состояние.

Текущий researcher/research-orchestrator используется как стартовая оболочка и генератор подробного prose-отчёта. Новое ядро строится рядом, модульно, без разрушения работающего прототипа.

---

## 1. Что именно строим

Строим не просто `claim_graph`, а два логически разных, но связанных графа.

### 1.1 Epistemic Graph — что мы знаем

Узлы:

```text
Question
ClaimProposal
Claim
Quantity
Source
Evidence
Derivation
Gap
Conflict
Assumption
Recommendation
```

Этот граф отвечает на вопросы:

```text
Какие утверждения есть?
Чем они подтверждены?
Какие числа контролируются?
Где есть пробелы?
Какие рекомендации заблокированы?
Какие claims зависят от слабого предположения?
```

### 1.2 Execution / Provenance Graph — как мы к этому пришли

Узлы:

```text
ResearchOperation
SearchQuery
ExtractionRun
ValidationEvent
Snapshot
WriterDecision
```

Этот граф отвечает на вопросы:

```text
Кто/что создало claim?
Каким источником был получен evidence span?
Какой validator изменил статус?
Почему фраза попала в финальный ответ?
Какая операция была запущена из-за gap?
```

### 1.3 Связи между графами

```text
Operation ─produced→ ClaimProposal
Operation ─produced→ Evidence

Evidence ─supports→ Claim
Evidence ─partially_supports→ Claim
Evidence ─contradicts→ Claim

Claim ─depends_on→ Claim
Claim ─derived_from→ Claim
Claim ─creates→ Gap

ValidatorRun ─changed_status_of→ Claim
ValidatorRun ─created→ Gap
ValidatorRun ─created→ Conflict

Gap ─triggered→ ResearchOperation
Claim ─included_in→ WriterContext
WriterContext ─produced→ FinalAnswer
```

Физически это может быть одна SQLite-база и один graph API. Логически разделение обязательно: один слой хранит знание, второй — историю появления знания.

---

## 2. Инварианты ядра

Эти правила важнее конкретных классов.

### 2.1 Source не равен Evidence

Найденный источник ещё не является доказательством.

```text
Source = документ / страница / статья / книга / запись корпуса
Evidence = конкретный span внутри Source
```

Статья может быть качественной, но конкретный фрагмент может не подтверждать claim.

### 2.2 Evidence не равен support

Evidence связывается с claim через typed edge:

```text
supports
partially_supports
contradicts
background
not_relevant
```

Качество источника, качество evidence и сила поддержки claim — разные вещи.

### 2.3 Число всегда контролируемый объект, но не всегда Claim

Нельзя автоматически превращать каждое число в отдельный claim.

```text
"Метод X повышает точность на 12%"
```

Правильно:

```text
Claim C1: "Метод X повышает точность"
Quantity Q1: effect_size = 12%, provenance = E17
```

Отдельный numeric claim создаётся только если сама величина является утверждением:

```text
"Средний эффект составляет 12%"
```

### 2.4 Claim не хранит parent/child массивы

Никаких `parent_claims` и `child_claims` внутри claim. Все зависимости вычисляются из `GraphEdge`.

Иначе появится второй источник истины.

### 2.5 Универсальный `confidence: float` запрещён

У разных отношений разные критерии качества. Вместо общего float используется:

```text
relation_type
status
validation_flags
typed metadata
```

Например для `SUPPORTS`:

```yaml
directness: DIRECT | PARTIAL | INDIRECT
scope_match: MATCH | PARTIAL | MAJOR_SHIFT | UNKNOWN
methodological_relevance: HIGH | MEDIUM | LOW
```

Для `DERIVED_FROM`:

```yaml
inference_type: arithmetic | causal | analogical | extrapolation
derivation_id: D17
```

### 2.6 Writer не исследует

Writer получает `writer_context.json`, а не свободу искать и придумывать.

```text
allowed_claims
qualified_claims
forbidden_claims
blocked_recommendations
citation_map
```

### 2.7 Markdown не является state store

`raw_report.md` и `final_answer.md` — человеческие проекции. Источник истины — graph repository + snapshots + validation events.

---

## 3. Базовые объекты R0-R3

### 3.1 ClaimProposal

LLM/extractor не создаёт claim напрямую. Он создаёт proposal.

```python
ClaimProposal:
    id
    proposition
    proposed_type
    proposed_scope
    source_context
    source_span_ref
    created_by
    created_at
```

Путь:

```text
LLM / extractor
  ↓
ClaimProposal
  ↓
Admission / normalization / atomicity validation
  ↓
Claim
```

### 3.2 Claim

```python
Claim:
    id
    proposition
    claim_type
    scope_id
    status
    provenance
    created_at
    revision
```

`atomicity` — не постоянное поле, а результат validator-а:

```text
ATOMIC
SUSPECT_COMPOSITE
COMPOSITE
```

### 3.3 Quantity

```python
Quantity:
    id
    claim_id
    semantic
    value
    lower
    upper
    unit
    normalized_value
    normalized_unit
    provenance_evidence_id
    derivation_id
    status
```

Используется для контроля чисел, диапазонов, единиц, процентов, дозировок, сроков, площадей и т.д.

### 3.4 Source

```python
Source:
    id
    title
    source_type
    primary_secondary
    peer_reviewed
    authority_type
    publication_date
    correction_status
    retraction_status
    identity
    canonical_url
    doi
    pmid
    isbn
    document_hash
    metadata
```

Нет `trust_level`. Оценка источника делается через source admission, а релевантность — через evidence relation.

### 3.5 Evidence

```python
Evidence:
    id
    source_id
    location
    text
    evidence_type
    extracted_quantities
    scope_id
    admission_status
    provenance
```

Evidence обязан быть конкретным span, а не ссылкой на весь документ.

### 3.6 Scope

```python
Scope:
    id
    domain
    dimensions
```

Core не знает заранее все dimensions. Доменные skills регистрируют их через `ScopeRegistry`.

Core умеет:

```text
normalize
compare
inherit
calculate_delta
```

### 3.7 GraphEdge / EdgeProposal

```python
EdgeProposal:
    id
    from_node
    to_node
    proposed_relation_type
    proposed_metadata
    created_by

GraphEdge:
    id
    from_node
    to_node
    relation_type
    status
    provenance
    created_by
    validation_flags
    metadata
```

Типы ребра:

```text
supports
partially_supports
contradicts
derived_from
generalizes
extrapolates_from
causes
correlates_with
justifies
depends_on
assumes
supersedes
included_in
produced
changed_status_of
triggered
```

### 3.8 Derivation

```python
Derivation:
    id
    output_claim_id
    input_claim_ids
    input_quantity_ids
    output_quantity_ids
    operation
    formula
    parameters
    implementation_version
    computation_status
    justification_status
```

Разделяет:

```text
арифметика корректна
```

и:

```text
вывод обоснован evidence
```

### 3.9 Gap

```python
Gap:
    id
    gap_type
    target_claim_id
    severity
    blocks
    resolution_requirements
    status
```

Gap — полноценный узел, а не строка в validator output.

### 3.10 Conflict

```python
Conflict:
    id
    member_claims
    member_evidence
    conflict_type
    scope_comparison
    resolution_requirements
    status
```

Важно: claim может оставаться `SUPPORTED`, а конфликт жить отдельно:

```text
C1 SUPPORTED
C2 SUPPORTED
CF1 UNRESOLVED
```

---

## 4. Event-based история

Не храним огромную историю внутри claim. Используем append-only события и materialized state.

```python
ValidationEvent:
    id
    target_id
    validator_id
    validator_version
    previous_status
    result
    reason_codes
    related_nodes
    timestamp
```

Примеры событий:

```text
CLAIM_PROPOSED
CLAIM_CREATED
EDGE_PROPOSED
EDGE_CREATED
SOURCE_DISCOVERED
SOURCE_ADMITTED
EVIDENCE_EXTRACTED
EVIDENCE_ADMITTED
EVIDENCE_LINKED
QUANTITY_CREATED
DERIVATION_CREATED
SCOPE_MISMATCH_DETECTED
GAP_CREATED
CONFLICT_CREATED
CLAIM_STATUS_CHANGED
SNAPSHOT_CREATED
WRITER_DECISION_CREATED
```

Состояние получается reducer-ом:

```text
events + repository → materialized graph state
```

---

## 5. GraphTransaction

LLM/extractor часто возвращает пачку claims и edges. Нельзя коммитить их по одному.

```python
GraphTransaction:
    id
    proposals
    validations
    accepted_mutations
    rejected_mutations
    status
```

Правило:

```text
либо transaction структурно согласована и коммитится,
либо отклоняется целиком / частично по явно описанным reason_codes.
```

Особенно важно для atomic splitting:

```text
CompositeClaim
  → C1
  → C2
  → C3
```

---

## 6. Repository и snapshots

### 6.1 ResearchState != KnowledgeState

`research_state.json` хранит runtime, а не весь граф.

```yaml
run_id: ...
question_id: ...
graph_snapshot_id: ...
current_phase: ...
active_operations: []
budgets: ...
open_priority_gaps: []
status: ...
```

А claims/sources/evidence/edges/events живут в repository.

### 6.2 Snapshot

Snapshot фиксирует воспроизводимое состояние графа:

```yaml
snapshot_id: RS20260828-01
graph_version: 140
claims:
  - C14@3
  - C22@1
open_gaps:
  - G9
stop_reason: null
```

---

## 7. Валидационный слой

Вместо `VerificationBlock` используется `Validator`.

```python
Validator:
    id
    version
    triggers

    def evaluate(context) -> list[ValidationEvent]:
        ...
```

Триггеры:

```text
CLAIM_PROPOSED
CLAIM_CREATED
EDGE_PROPOSED
EDGE_CREATED
SOURCE_ADMITTED
EVIDENCE_ADMITTED
EVIDENCE_LINKED
SCOPE_CHANGED
QUANTITY_CREATED
DERIVATION_CREATED
SNAPSHOT_CREATED
```

### 7.1 Базовые validators R3

```text
SourceAdmissionValidator
EvidenceAdmissionValidator
AtomicityValidator
NumericValidator
ScopeValidator
EdgeValidator
GraphCycleValidator
GapBuilder
ConflictBuilder
StructuralRiskAnalyzer
```

### 7.2 Source Admission и Evidence Admission

Разделяются два уровня:

```text
SourceAdmission: можно ли считать документ допустимым источником?
EvidenceAdmission: можно ли считать конкретный span evidence для конкретного claim?
```

Source admission проверяет:

```text
identity
author/date
source type
primary/secondary
duplicate
retraction/correction
scope
accessibility
```

Evidence admission проверяет:

```text
span exists
span is not just title/abstract unless allowed
span relates to claim
span has location
numbers have local provenance
scope is extractable or unknown explicitly
```

---

## 8. Structural Risk

Граф должен находить не только плохие claims, но и структурно опасные узлы.

Пример:

```text
A17 unsupported assumption
  ↓
14 claims
  ↓
6 recommendations
```

Такой узел получает высокий research priority.

Planner должен формулировать задачу не так:

```text
ищи ещё источники про малину
```

а так:

```text
Resolve A17.
Expected downstream impact: 14 claims, 6 recommendations.
```

---

## 9. Подробный Markdown-отчёт сохраняем

Не ужимаем `raw_report.md`. Подробный prose нужен человеку.

Проблему контроля решаем вторым представлением:

```text
raw_report.md — человеку читать
claims.json / graph.sqlite — машине валидировать
validation_report.json — человеку и машине видеть слабые места
```

Writer запускается только после стабилизации графа и получает ограничения.

---

## 10. Артефакты одного research run

Минимальный набор:

```text
raw_report.md
claims.json
graph.sqlite или graph_snapshot.json
validation_report.json
research_state.json
```

Позже:

```text
writer_context.json
final_answer.md
search_trace.jsonl
events.jsonl
```

### 10.1 claims.json

Плоское машинное разложение raw report.

```yaml
report_id: RPT001
claims:
  - id: CP001
    proposition: "Гуматы повышают эффективность удобрений"
    source_span:
      file: raw_report.md
      section: "11.4 Гуматы"
      paragraph: 1
    proposed_type: direct
    proposed_scope: {}

quantities:
  - id: QP001
    attached_to: CP001
    value: 15
    upper: 30
    unit: "%"
    semantic: fertilizer_efficiency_increase
    provenance: null
```

### 10.2 validation_report.json

```yaml
summary:
  supported: 0
  partially_supported: 0
  unsupported: 0
  missing_numeric_provenance: 0
  weak_causal_edges: 0
  blocked_recommendations: 0

findings:
  - target: R001
    severity: high
    reason: blocked_by_unsupported_assumption
    path:
      - R001
      - C002
      - A017
```

---

## 11. Пример на отчёте про малину

Файл fixture:

```text
C:\Users\Arhys\Downloads\malina-srednyaya-polosa-agrotehnika-2026-08-25 (1).md
```

### 11.1 Бедная почва

Цепочка:

```text
S2 подтверждает 40–80 кг N/га
  ↓
C001: базовая норма 40–80 кг N/га
  ↓ derived/extrapolated
C002: на бедной почве 60–100 кг N/га
  ↓ depends_on
A001: бедная почва требует 1.5× питания
```

Ожидаемая диагностика:

```text
C001 supported
A001 weak/unsupported unless evidence found
C002 derived but weakly_supported
R001 conditional or needs_research
```

### 11.2 Гнилая древесина

Опасный веер:

```text
C101: малина растёт на опушках/вырубках
  ↓ generalizes
C102: гниющая древесина часть эволюционной ниши
  ↓ extrapolates/causes
C103: улучшает питание
C104: подавляет Botrytis
C105: подавляет Phytophthora
C106: полив сокращается в 2–3 раза
```

Validator должен показать:

```text
много claims зависит от одного слабого перехода
```

### 11.3 Гуматы

```text
C201: гуматы повышают эффективность удобрений
Q201: 15–30%
C203: гуматы стимулируют развитие корней
C204: гуматы повышают стрессоустойчивость
```

Если `Q201.provenance = null`, повторный research должен идти именно по числу, а не по всему тезису о гуматах.

---

## 12. Блоки, которые будем стыковать

### 12.1 Claim extraction blocks

Зачем:

```text
разбивать вопрос, текст или raw report на ClaimProposal и QuantityProposal
```

Что подключать:

```text
текущий opencode claim-parser
серверный open-source claim splitter, если появится в Z:\server
детерминированный fallback extractor
LLM-assisted atomic splitter
```

Как стыковать:

```text
ExtractorAdapter.extract(text|report) -> ClaimExtractionRun
ClaimExtractionRun -> ClaimProposal[] + QuantityProposal[] + EdgeProposal[]
GraphTransaction -> validators -> accepted Claims/Quantities/Edges
```

Почему так:

```text
extractor может ошибаться, но не имеет права напрямую менять graph state
```

### 12.2 Search / retrieval blocks

Зачем:

```text
искать источники под конкретные gaps, claims, assumptions, quantities
```

Capabilities:

```text
search.academic
search.academic_ru
search.scholar_like
search.web
search.local
source.fetch
metadata.resolve
citation.follow
retraction.check
```

Первые адаптеры:

```text
OpenAlex — search.academic, metadata.resolve
Crossref — metadata.resolve
PubMed — search.academic, metadata.resolve
arXiv — search.academic
CyberLeninka — search.academic_ru, source.fetch
LocalCorpus — search.local, source.fetch
Seer server — search.web/search.scholar_like/source.fetch, по фактическим возможностям
Web — search.web, source.fetch
```

Как стыковать:

```text
Gap/Claim/Quantity -> QueryTask
QueryTask -> CapabilityRegistry
CapabilityRegistry -> AdapterRegistry
Adapter -> SourceCandidate[]
SourceAdmission -> Source
SourceFetcher -> SourceContent
EvidenceExtractor -> EvidenceSpan[]
EvidenceAdmission -> Evidence
```

Почему так:

```text
ядро не зависит от OpenAlex/Google Scholar/CyberLeninka;
можно заменить реализацию без изменения graph logic;
не строим архитектуру вокруг чужого HTML.
```

### 12.3 Verification / validation blocks

Зачем:

```text
проверять допустимость узлов и ребер, а не оценивать весь текст целиком
```

Блоки:

```text
AtomicityValidator
SourceAdmissionValidator
EvidenceAdmissionValidator
EvidenceClaimRelationValidator
NumericValidator
ScopeValidator
DerivationValidator
EdgeValidator
ConflictBuilder
GapBuilder
StructuralRiskAnalyzer
RecommendationGate
```

Как стыковать:

```text
Graph event -> ValidatorRegistry -> Validator.evaluate(context) -> ValidationEvent[]
ValidationEvent[] -> Reducer -> materialized graph state
```

Почему так:

```text
validator работает по маленьким проверяемым объектам;
замечания становятся falsifiable;
можно тестировать deterministic fixtures.
```

### 12.4 Numeric blocks

Зачем:

```text
числа, дозы, проценты, диапазоны, единицы и формулы — частый источник галлюцинаций
```

Что подключать:

```text
новый Quantity parser/normalizer
legacy numeric_comparator.py из Z:\server, если появится
units.py / uncertainty.py / formulas.py, если появятся
```

Как стыковать:

```text
QuantityProposal -> Quantity
Quantity -> NumericValidator
EvidenceSpan -> extracted quantities
Derivation -> DerivationValidator
```

Почему так:

```text
можно повторно исследовать конкретное число, не весь claim;
можно отделить correct computation от justified inference.
```

### 12.5 Writer / synthesis blocks

Зачем:

```text
создавать читаемый ответ из валидированного графа
```

Как стыковать:

```text
GraphSnapshot + ValidationReport -> WriterContextBuilder
WriterContext -> Writer
WriterDecision[] -> FinalAnswer
```

Writer получает:

```text
allowed_claims
qualified_claims
forbidden_claims
blocked_recommendations
citation_map
```

Почему так:

```text
writer не исследует;
writer не повышает статус claim;
writer не выбирает citations по памяти.
```

### 12.6 Legacy Hermes/server scripts from Z:\server

Зачем:

```text
переиспользовать уже работающие блоки: numeric, evidence, postprocess, runner, synthesizer
```

Как стыковать:

```text
Core stable interface
  ↓
HermesLegacyAdapter
  ↓
script from Z:\server
```

Почему не напрямую:

```text
старые скрипты могут иметь Linux paths, старые схемы, provider drift, hidden assumptions;
ядро не должно наследовать legacy coupling.
```

---

## 13. Порядок реализации

### R0 — фундамент

```text
IDs
enums
contracts
repository abstractions
serialization
event model
GraphTransaction
```

Результат R0:

```text
можно создать пустой run, question, event log, snapshot;
нельзя создать объект с невалидным id/status/type.
```

### R1 — эпистемическая модель

```text
Question
ClaimProposal
Claim
Quantity
Source
Evidence
Scope
Derivation
GraphEdge
EdgeProposal
Gap
Conflict
Assumption
Recommendation
```

Результат R1:

```text
можно описать знание без поиска, LLM и writer-а.
```

### R2 — graph/provenance

```text
GraphRepository
ExecutionRepository
GraphTransaction commit
ValidationEvent log
Snapshot
revision model
dependency traversal
dirty propagation
```

Результат R2:

```text
можно ответить, откуда появился claim и почему у него такой статус.
```

### R3 — правила допуска

```text
SourceAdmission
EvidenceAdmission
Atomicity
Numeric
Scope
Edge validation
Graph cycle validation
GapBuilder
ConflictBuilder
StructuralRiskAnalyzer
```

Результат R3:

```text
можно прогнать synthetic golden fixture без интернета.
```

### R4 — planner / operations

```text
ResearchOperation
QueryTask
ResearchQueue
OperationRegistry
Priority policy
Budget model
```

### R5 — search adapters

```text
OpenAlex
Crossref
PubMed
arXiv
CyberLeninka
LocalCorpus
Seer
Web
scholar_like provider
```

### R6 — stop controller

```text
coverage
saturation
budget exhaustion -> PARTIAL
open high-impact gaps
unresolved conflicts
```

### R7 — writer context

```text
WriterContextBuilder
CitationRenderer
WriterDecision log
FinalAnswer projection
```

### R8 — opencode integration

```text
patch research-orchestrator.md
patch claim-parser/source-fetcher/fact-checker/synthesizer contracts
connect runtime runner
```

---

## 14. Golden fixtures

### 14.1 Synthetic fixture

Input:

```text
Исследования показывают, что метод X повышает точность на 12%, но только на малых выборках.

S1: В выборке n=24 метод X увеличил показатель с 70 до 78.4%.
S2: В выборке n=500 статистически значимого улучшения не обнаружено.
```

Expected graph:

```text
C1: Метод X повышает точность
Q1: effect_size = +12%
S1 admitted
S2 admitted
E1 supports C1 in small_sample scope
E2 contradicts/generalizes against C1 in larger_sample scope
CF1 scope-dependent conflict
G1 general applicability unresolved
```

### 14.2 Real fixture: malina report

Файл:

```text
C:\Users\Arhys\Downloads\malina-srednyaya-polosa-agrotehnika-2026-08-25 (1).md
```

Проверяем:

```text
бедная почва -> derived nutrient recommendations
гуматы -> split claims + numeric provenance
гнилая древесина -> weak transition with large downstream fan-out
хитозан -> extrapolation strawberry -> raspberry
сорта -> regional source gaps
```

---

## 15. Почему именно так

Эта архитектура выбрана потому что она:

1. не ломает текущий подробный researcher report;
2. добавляет машинно-проверяемый claims graph;
3. отделяет источник от evidence и evidence от support;
4. не даёт LLM напрямую менять state;
5. позволяет подключать разные поисковые блоки через capability registry;
6. позволяет переиспользовать legacy scripts через адаптеры;
7. делает рекомендации проверяемыми через dependency path;
8. даёт planner-у управлять бюджетом через gaps и structural risk;
9. позволяет валидировать систему на synthetic и real fixtures до подключения интернета.

Главная ценность — возможность ответить:

```text
Почему эта фраза появилась в финальном ответе?
Какие claims её поддерживают?
Какие assumptions висят в цепочке?
Где слабое causal/extrapolation ребро?
Что надо исследовать дальше с максимальным downstream impact?
```

---

## 16. Ближайший следующий шаг

Перед кодом нужно зафиксировать минимальную спецификацию R0 файлов:

```text
contracts.py
ids.py
enums.py
events.py
transactions.py
repository.py
serialization.py
```

После этого создать R0 skeleton и один dry-run тест, который создаёт:

```text
ResearchRun
Question
ClaimProposal
QuantityProposal
Source
Evidence
GraphTransaction
ValidationEvent
Snapshot
```

без интернета, без LLM, без writer-а.
