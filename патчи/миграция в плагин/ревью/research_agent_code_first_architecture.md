# Research Agent: code-first архитектура исследовательского контура

## 1. Назначение

Research Agent должен быть не «LLM с поиском», а управляемой машиной уменьшения неопределённости.

Его цикл:

```text
QUESTION
→ DECOMPOSE
→ TARGET CLAIMS
→ EVIDENCE REQUIREMENTS
→ PLAN
→ SEARCH / RETRIEVE
→ SOURCE ADMISSION
→ EVIDENCE EXTRACTION
→ CLAIM GRAPH
→ VALIDATION
→ CONFLICTS / GAPS
→ PRIORITIZE NEXT RESEARCH
→ STOP CHECK
→ SYNTHESIS
→ WRITER
```

Главный принцип:

> Researcher добывает доказательства. Claim Graph хранит состояние знания. Код управляет исследовательским циклом. LLM выполняет локальные семантические операции.

---

## 2. Research Question как объект

Вопрос исследования не должен оставаться строкой prompt.

```yaml
id: RQ001
text: "..."
question_type: causal|descriptive|comparative|diagnostic|normative|methodological
scope:
  population: null
  geography: null
  time: null
  conditions: null
required_output:
  - factual_answer
risk_class: medium
status: active
```

Сложный вопрос декомпозируется в под-вопросы. LLM может предложить декомпозицию, но код ограничивает глубину, ширину, дубли и бюджет.

---

## 3. Target Claims до поиска

До активного поиска формируется набор утверждений, которые нужно установить.

```yaml
target_claims:
  - id: TC01
    role: central
    proposition: "X влияет на Y"
  - id: TC02
    role: magnitude
    proposition: "эффект имеет величину ..."
  - id: TC03
    role: boundary
    proposition: "эффект действует при условиях ..."
  - id: TC04
    role: limitation
    proposition: "эффект не подтверждён при ..."
```

Research завершается не когда найдено «достаточно текста», а когда центральные target claims получили допустимый статус или явно остались unresolved.

---

## 4. Hypothesis Set

Для неоднозначных задач:

```text
H1
H2
H3
```

хранятся одновременно.

```yaml
hypothesis_set:
  id: HS01
  hypotheses: [H1, H2, H3]
  status: unresolved
```

Planner должен искать discriminating evidence, то есть данные, различающие гипотезы, а не только подтверждающие одну из них.

---

## 5. Evidence Requirement

Каждый тип claim требует своего класса доказательств.

```yaml
claim_id: TC01
evidence_requirement:
  preferred:
    - controlled_experiment
  acceptable:
    - observational_study
    - systematic_review
  weak:
    - expert_guideline
```

Примеры кодовых правил:

```text
точное число → direct numeric provenance
causal claim → causal evidence
comparison → comparative evidence
recommendation → evidence + scope + risks + applicability
current-state claim → freshness requirement
```

---

## 6. Research Plan

```yaml
research_plan:
  id: RP01
  goals: [TC01, TC02, TC03]
  budgets:
    queries: 12
    sources: 20
    llm_calls: 15
  stop_policy: standard_research_v1
```

LLM не решает самостоятельно, сколько ещё искать.

---

## 7. Research Operations

Поиск является только одной операцией.

```text
SEARCH
OPEN_SOURCE
FOLLOW_CITATION
FIND_PRIMARY_SOURCE
EXTRACT_EVIDENCE
VERIFY_NUMBER
VERIFY_SCOPE
SEARCH_CONTRADICTION
COMPARE_SOURCES
RESOLVE_CONFLICT
CHECK_FRESHNESS
```

Все операции регистрируются через `ResearchOperationRegistry`.

```python
operation_registry.register(
    ResearchOperationDescriptor(
        id="search.contradiction",
        preconditions=["target_claim_exists"],
        executor=SearchContradiction,
    )
)
```

Controller работает с operation ID, не с конкретным provider.

---

## 8. Query Task вместо свободного search prompt

```yaml
query_task:
  target_claim: TC04
  goal: find_contradictory_evidence
  preferred_source_types:
    - primary_research
  scope:
    species: Rubus_idaeus
  exclude:
    species:
      - Fragaria
```

LLM может сформулировать поисковую строку, но не определяет исследовательскую цель.

---

## 9. Search diversification

Для центрального claim должны использоваться разные стратегии:

```text
direct
synonym
mechanism
primary-source
review
contradiction
negative-result
citation-chain
regional
methodological
```

Query fingerprint нужен для отсечения почти одинаковых запросов.

---

## 10. Search Trace

```yaml
query_id: Q19
target_claim: TC04
strategy: contradiction
query: "..."
results_seen: 10
results_opened: [S12, S14]
outcome:
  new_evidence: 2
  duplicate: 4
  irrelevant: 4
```

Это позволяет оценивать эффективность planner.

---

## 11. Source Admission Gate

Найденный URL не является автоматически источником доказательства.

Проверяются:

```text
identity
author/date
source type
primary/secondary
duplicate
retraction/correction when applicable
scope
accessibility
```

Статусы:

```text
ADMITTED
WEAK
DUPLICATE
REJECTED
NEEDS_INSPECTION
```

---

## 12. Source identity и lineage

Для identity:

```text
DOI
PMID
ISBN
canonical URL
document hash
title + authors + year
```

Для lineage:

```text
Blog A → Review B → Study C
```

Если три вторичных источника повторяют Study C, независимый evidence root один, а не три.

---

## 13. Evidence как конкретный span

```yaml
id: E101
source_id: S12
location:
  page: 8
  section: Results
text: "..."
evidence_type: measured_result
scope: {...}
normalized: {...}
```

Direct claim без evidence span:

```text
NEEDS_VERIFICATION
```

---

## 14. Deterministic extraction first

До LLM код извлекает:

```text
numbers
units
dates
DOI
headings
tables
references
known entities
```

LLM получает уже структурированные элементы.

---

## 15. Числовая provenance

Любое число должно иметь:

```text
value
unit
semantic
scope
source span
```

или:

```text
derivation
formula
inputs
```

Если нет ни evidence, ни derivation, число нельзя использовать как установленную норму.

---

## 16. ClaimProposal != Claim

LLM выдаёт:

```text
ClaimProposal
```

Затем:

```text
schema validation
span verification
numeric verification
scope normalization
edge validation
```

и только после этого код создаёт `Claim`.

То же относится к связям:

```text
RelationProposal != Edge
```

---

## 17. Evidence Linker

Типы отношения evidence к claim:

```text
DIRECT
PARTIAL
INDIRECT
CONTRADICTORY
BACKGROUND
```

Высокое качество источника не означает автоматически, что он поддерживает конкретный claim.

---

## 18. Semantic validation jobs

LLM следует давать маленькие задачи:

```text
Does E17 support C12?
Is C14 stronger than the source statement?
Does C31 exceed source scope?
Split this sentence into atomic claims.
```

Не:

```text
"Проверь всё исследование целиком."
```

---

## 19. Scope Engine

Scope должен быть first-class:

```yaml
scope:
  population: ...
  species: ...
  geography: ...
  environment: ...
  treatment: ...
  time: ...
  software_version: ...
```

Код сравнивает:

```python
scope_delta(evidence.scope, claim.scope)
```

Результат:

```text
MATCH
PARTIAL
MAJOR_SHIFT
UNKNOWN
```

`MAJOR_SHIFT` требует явной `EXTRAPOLATION`.

---

## 20. Claim classes

```text
SOURCE
SYNTHESIS
INFERENCE
EXTRAPOLATION
PRACTICE
ASSUMPTION
HYPOTHESIS
RECOMMENDATION
```

---

## 21. Claim status

```text
NEW
SUPPORTED
PARTIALLY_SUPPORTED
UNSUPPORTED
CONFLICTING
NEEDS_RESEARCH
BLOCKED
REJECTED
```

Критическое правило:

> `UNSUPPORTED` не означает `FALSE`.

---

## 22. Conflict Detector

Ищет:

```text
opposite polarity
different numeric ranges
different causal direction
incompatible recommendations
```

Но до объявления реального конфликта сравнивает scope, метод, population, endpoint и период.

---

## 23. Gap Builder

Gap создаётся, если:

```text
target claim unsupported
missing primary source
numeric provenance missing
scope unresolved
conflict unresolved
required evidence type missing
```

Типы:

```text
MISSING_EVIDENCE
MISSING_PRIMARY_SOURCE
MISSING_NUMERIC_PROVENANCE
SCOPE_GAP
CONFLICT
CAUSAL_GAP
TEMPORAL_GAP
METHODOLOGICAL_GAP
```

---

## 24. Research Priority

На первом этапе лучше lexicographic policy, а не псевдоточная формула:

```text
1. gap блокирует центральный ответ?
2. блокирует рекомендацию?
3. связан с high-risk действием?
4. имеет большой blast radius?
5. дёшево ли его разрешить?
```

Позже можно добавить score.

---

## 25. Blast Radius

```text
weak claim
↓
7 derived claims
↓
3 recommendations
```

Такой узел исследуется раньше слабого периферийного claim.

---

## 26. Обязательный adversarial search

Для central/high-impact claims planner должен иметь минимум:

```text
support search
contradiction search
boundary-condition search
```

Это кодовое средство против confirmation bias.

---

## 27. Primary Source Recovery

Если значимый claim найден во вторичном тексте:

```text
secondary source
→ citation
→ primary source
```

Вторичный источник остаётся background, первичный становится evidence root.

---

## 28. Recommendation Gate

Recommendation не создаётся просто потому, что базовый claim supported.

Нужны:

```text
evidence
scope applicability
conditions
risks
alternatives
uncertainty
```

При unresolved critical parent:

```text
RECOMMENDATION = BLOCKED / CONDITIONAL
```

---

## 29. Planner code-first

Planner не задаёт LLM вопрос:

```text
"What should we research next?"
```

Он получает:

```text
open gaps
central claims
conflicts
blast radius
remaining budget
```

и строит допустимые candidate operations.

LLM нужна преимущественно для формулировки query и локальной семантики.

---

## 30. ResearchPlanner contract

```python
class ResearchPlanner:
    def next_operation(
        self,
        state,
        graph,
        budget,
    ) -> ResearchOperation:
        ...
```

---

## 31. Research State Machine

```text
INITIAL
→ DECOMPOSED
→ SEARCHING
→ EVIDENCE_ACCUMULATION
→ CONFLICT_RESOLUTION
→ SATURATION_CHECK
→ SYNTHESIS_READY
```

Разрешены циклы между research states, но только по contract.

---

## 32. Stop Controller

Без отдельного Stop Controller researcher либо заканчивает слишком рано,
либо роет дальше просто потому, что web ещё содержит страницы.

Stop conditions:

```text
central target claims resolved
no high-impact gaps
no unresolved major conflicts
minimum evidence diversity reached
evidence saturation reached
budget exhausted
```

---

## 33. Evidence saturation

После каждой research iteration считать:

```text
new independent evidence
new central claims
new conflicts
new scope dimensions
```

Пример:

```python
if (
    last_3_iterations.new_independent_evidence == 0
    and last_3_iterations.new_central_claims == 0
):
    stop_reason = "evidence_saturation"
```

---

## 34. Budget exhaustion != complete

Если budget исчерпан:

```text
status = PARTIAL
```

и открытые gaps сохраняются.

Не следует превращать техническое окончание бюджета в эпистемическую уверенность.

---

## 35. Research completeness

Диагностические показатели:

```yaml
coverage:
  central_claims: 0.95
  boundary_claims: 0.62
  conflicts_resolved: 0.80
  numeric_provenance: 0.90
```

Это метрики покрытия, а не вероятность истины.

---

## 36. Writer не исследует

Writer:

```text
не вызывает search
не создаёт evidence
не повышает claim status
не придумывает числа
не выбирает citation по памяти
```

Если информации не хватает, writer возвращает missing claims.

---

## 37. Writer Context

```yaml
writer_context:
  allowed_claims: [...]
  qualified_claims: [...]
  conflicting_claims: [...]
  forbidden_claims: [...]
  recommendations: [...]
  gaps: [...]
  citation_map: {...}
```

---

## 38. Citation Renderer

Writer может ссылаться на:

```text
[[C014]]
```

Renderer выполняет:

```text
C014 → E3,E4 → S1,S2
```

LLM не управляет bibliography binding.

---

## 39. Research State и Report разделены

Хранить:

```text
research_state.json
research_report.md
```

Markdown является проекцией для человека, не источником состояния runtime.

---

## 40. Snapshot

```yaml
snapshot_id: RS20260828-01
graph_version: 140
claims:
  - C14@3
  - C22@1
open_gaps:
  - G9
stop_reason: saturation
```

Так можно воспроизвести, на каком состоянии был построен ответ.

---

## 41. Revalidation

При:

```text
source retracted
law changed
software version changed
new evidence appeared
```

выполняется:

```text
SourceInvalidated
→ Evidence dirty
→ Claim dirty
→ dependent recommendations blocked/revalidated
```

---

## 42. Domain Skills

Research Core не должен знать предметную область.

Domain skill регистрирует:

```text
scope dimensions
evidence taxonomy
quality rules
risk thresholds
normalizers
preferred source types
```

То есть:

```text
Hardcode invariants.
Configure research policy.
Declare domain requirements.
Register implementations.
```

---

## 43. Research capabilities

Skills должны требовать capability:

```text
search.web
search.scholar
source.fetch
citation.follow
metadata.resolve
retraction.check
```

а не конкретный Google/OpenAlex/PubMed provider.

---

## 44. Failure semantics

Критически различать:

```text
search returned no results
source inaccessible
no evidence found within budget
evidence of absence
```

Это четыре разных состояния.

Tool failure не становится epistemic conclusion.

---

## 45. Research events

```text
RESEARCH_STARTED
QUESTION_DECOMPOSED
SOURCE_DISCOVERED
SOURCE_ADMITTED
EVIDENCE_EXTRACTED
CLAIM_CREATED
CLAIM_INVALIDATED
CONFLICT_OPENED
GAP_OPENED
GAP_RESOLVED
RESEARCH_OPERATION_COMPLETED
SATURATION_REACHED
RESEARCH_STOPPED
SNAPSHOT_CREATED
```

---

## 46. Observability

Полезные метрики:

```text
sources_discovered
sources_admitted
primary_sources
independent_evidence_roots

claims_supported
claims_conflicting
numeric_claims_without_provenance

open_high_impact_gaps
queries_per_resolved_gap
new_evidence_per_query

research_iterations
stop_reason
```

---

## 47. Debug View

```text
Research Question RQ1

Central:
C1 SUPPORTED
C2 CONFLICTING
C3 NEEDS_RESEARCH

Highest-priority gap:
G7 SCOPE_GAP

Why:
blocks 4 recommendations

Next operation:
SEARCH_PRIMARY / VERIFY_SCOPE
```

Это гораздо полезнее скрытого монолога модели.

---

## 48. Graph Slice для LLM

LLM получает только локальный slice:

```yaml
current_job:
  verify_claim: C22
parents: [C14]
evidence: [E31, E44]
scope_delta: {...}
conflicts: [CF7]
```

Не весь research history.

---

## 49. Synthesis только после стабилизации графа

Не нужно писать красивый итог после каждой поисковой итерации.

Сначала стабилизируется research state.

Потом выполняется synthesis.

Иначе ранний текст начинает диктовать последующий поиск.

---

## 50. Repository layout

```text
agent/
└── research/
    ├── runtime/
    │   ├── controller.py
    │   ├── state.py
    │   └── stop_controller.py
    ├── questions/
    ├── planning/
    ├── operations/
    ├── sources/
    ├── evidence/
    ├── conflicts/
    ├── gaps/
    ├── validation/
    ├── synthesis/
    ├── writer_context/
    └── tests/
```

Claim Graph лучше использовать общий с основным Agent Runtime.

---

## 51. ResearchRequest

```yaml
question: ...
scope: ...
risk_class: ...
budget: ...
required_output: ...
```

## 52. ResearchResult

```yaml
status: complete|partial|failed
snapshot_id: ...
central_claims: [...]
conflicts: [...]
gaps: [...]
recommendations: [...]
writer_context_ref: ...
```

Не возвращать только Markdown.

---

## 53. MVP

Первая версия должна уметь:

```text
1. ResearchQuestion
2. TargetClaim
3. EvidenceRequirement
4. Source
5. EvidenceSpan
6. ClaimProposal
7. Claim Graph
8. Numeric provenance
9. Scope validation
10. Conflict
11. Gap
12. Research Queue
13. Stop Controller
14. Writer Context
```

Операции MVP:

```text
SEARCH
OPEN
EXTRACT
VERIFY_CLAIM
SEARCH_CONTRADICTION
FOLLOW_PRIMARY
```

---

## 54. Порядок реализации

### R0 Contracts

```text
ResearchRequest
ResearchQuestion
TargetClaim
EvidenceRequirement
ResearchOperation
ResearchResult
```

### R1 Source / Evidence

Source Registry, Admission Gate, Evidence Span, numeric parser.

### R2 Claim Graph

ClaimProposal, Evidence Linker, typed edges, status.

### R3 Scope / Conflict / Gap

Scope Validator, Conflict Detector, Gap Builder.

### R4 Planner

Research Queue, priority, operation registry, budgets.

### R5 Stop Controller

Coverage, saturation, budget exhaustion.

### R6 Writer Context

Allowed claims, qualifiers, citation map, unresolved gaps.

### R7 Domain Skills

Подключаемые evidence/policy правила предметных областей.

---

## 55. Главные инварианты Research Agent

```text
1. Source не равен evidence.
2. Evidence привязано к конкретному span.
3. Direct claim не существует без evidence.
4. Число требует provenance или derivation.
5. LLM создаёт proposal, не authoritative state.
6. Scope shift маркируется явно.
7. Unsupported не означает false.
8. Central claim проходит adversarial search.
9. Recommendation имеет justification path.
10. Search failure не считается evidence of absence.
11. Writer не исследует.
12. Stop condition определяет код.
13. Budget exhaustion создаёт partial result.
14. Claim status меняется через validator/state reducer.
15. Research report не является state store.
```

---

## 56. Итоговая ответственность

```text
LLM
    semantic extraction
    claim splitting
    relation proposal
    scope proposal
    query wording

CODE
    state ownership
    provenance
    validation
    graph transitions
    research priority
    budgets
    stop conditions
    recommendation gates

TOOLS
    retrieval
    source access
    metadata
    external observations

CLAIM GRAPH
    epistemic state

WRITER
    projection of validated state
```

Главный сдвиг заключается в том, что researcher перестаёт быть моделью,
которая «поищет, подумает и напишет».

Он становится детерминированно управляемым исследовательским runtime,
где LLM используется ровно там, где требуется семантика, а не там, где
обычный код способен принять более проверяемое решение.
