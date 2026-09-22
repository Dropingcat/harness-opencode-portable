# Claim Graph Layer для исследовательского агента

## 1. Назначение

Этот документ описывает модуль `Claim Graph Layer` для интеграции в исследовательского агента. Его задача не в том, чтобы заставить LLM «лучше проверять себя», а в том, чтобы перенести контроль происхождения утверждений, допустимых переходов, чисел, областей применимости, конфликтов и рекомендаций в код.

Главный принцип:

> **LLM предлагает семантическую интерпретацию. Код определяет допустимые состояния, связи, переходы и права на использование результата.**

LLM может извлечь предполагаемый claim, предложить тип связи, описать scope или указать возможное противоречие. Но LLM не должна самостоятельно решать, что claim считается доказанным, что рекомендация разрешена, что число валидно или что зависимый вывод после изменения родительского утверждения остаётся пригодным.

Таким образом, слой должен давать системе ответы не через новый промпт, а через программные методы:

```text
Что утверждается?
На каком evidence это основано?
Это direct claim, inference или extrapolation?
Какие предположения используются?
Каков scope?
Какие узлы от него зависят?
Что станет невалидным при его удалении?
Можно ли использовать его в synthesis?
Можно ли на его основе давать recommendation?
Можно ли на его основе выполнять tool action?
Что нужно исследовать следующим?
```

---

## 2. Место в архитектуре

Рекомендуемый поток:

```text
User request
    ↓
Task / intent decomposition
    ↓
Research planner
    ↓
Retriever
    ↓
Sources
    ↓
Evidence extraction
    ↓
Claim proposals
    ↓
Claim Graph transaction
    ↓
Deterministic validation
    ↓
Conflict / gap / dependency analysis
    ↓
Targeted research
    ↓
Graph update
    ↓
Recommendation / Action gates
    ↓
WriterContextBuilder
    ↓
Writer
    ↓
Citation renderer
```

Markdown researcher-отчёт можно и нужно сохранять как человекочитаемый слой. Но он не должен быть единственным состоянием исследования.

Вместо линейной передачи:

```text
researcher → validator → writer
```

лучше иметь общее состояние:

```text
researcher → Claim Graph
validator  → Claim Graph
planner    ← Claim Graph
writer     ← Claim Graph
```

---

## 3. Основные сущности

Для MVP достаточно семи типов:

```text
SOURCE
EVIDENCE
CLAIM
ASSUMPTION
RECOMMENDATION
CONFLICT
GAP
```

Позже можно добавить `ENTITY`, `EVENT`, `MEASUREMENT`, `METHOD`, `ACTION`, `DECISION`, но не стоит начинать с онтологии размером с министерство. Сначала нужен рабочий provenance DAG.

---

## 4. SOURCE

`SOURCE` описывает документ, API-ответ, страницу, локальный файл или иной объект, из которого получено evidence.

```yaml
id: S002
type: source

title: "Nitrogen uptake in red raspberry"
source_type: primary_research
url: "..."
retrieved_at: "2026-08-28T10:20:00Z"

quality:
  peer_reviewed: true
  primary: true
  retracted: false
  authority_score: 0.85

scope:
  species: Rubus_idaeus
  geography: null
  environment: field

status: active
```

Ключевой запрет:

```text
CLAIM → SOURCE
```

не является достаточной доказательственной связью.

Правильная цепочка:

```text
SOURCE
  ↓ contains
EVIDENCE
  ↓ supports
CLAIM
```

Источник может содержать сотни утверждений. Сам факт наличия citation не доказывает соседний текст.

---

## 5. EVIDENCE

`EVIDENCE` — конкретный фрагмент или структурированный результат источника.

```yaml
id: E014
type: evidence
source_id: S002

location:
  page: 7
  section: Results
  paragraph: 3

text_span: "Nitrogen uptake ranged from ..."

normalized_data:
  variable: nitrogen_application
  lower: 40
  upper: 80
  unit: kg_N_per_ha

scope:
  species: Rubus_idaeus
  environment: field

verification:
  span_exists: true
  numeric_match: true
```

Direct claim должен ссылаться на `evidence_id`, а не только на `source_id`.

---

## 6. CLAIM

Claim должен быть атомарным.

```yaml
id: C037
type: claim
text: "В исследовании применялась норма азота 40–80 кг N/га."
claim_class: source
status: supported

subject: raspberry
predicate: nitrogen_application_rate
object:
  lower: 40
  upper: 80
  unit: kg_N_per_ha

scope:
  species: Rubus_idaeus
  environment: field

scores:
  evidence_strength: 0.95
  source_quality: 0.84
  scope_match: 0.90
  convergence: 0.60
  derivation_quality: 1.0
```

### 6.1 Атомарность

Фраза:

```text
Гуматы повышают эффективность удобрений на 15–30 %, стимулируют корни и повышают стрессоустойчивость.
```

должна быть разложена минимум на:

```text
C101: гуматы повышают эффективность удобрений
C102: величина эффекта составляет 15–30 %
C103: гуматы стимулируют развитие корней
C104: гуматы повышают стрессоустойчивость
```

Потому что статусы могут быть разными:

```text
C101 supported
C102 unsupported
C103 supported
C104 partially_supported
```

Один красивый абзац для человека не должен превращаться в один нечитаемый машинный claim.

---

## 7. Классы claims

```python
class ClaimClass(str, Enum):
    SOURCE = "source"
    SYNTHESIS = "synthesis"
    INFERENCE = "inference"
    EXTRAPOLATION = "extrapolation"
    PRACTICE = "practice"
    ASSUMPTION = "assumption"
    RECOMMENDATION = "recommendation"
```

### SOURCE
Прямо содержится в evidence. Обязан иметь evidence.

### SYNTHESIS
Обобщает несколько уже поддержанных claims без существенного нового логического скачка.

### INFERENCE
Новый вывод агента. Обязан иметь `derived_from` и явные assumptions, если они есть.

### EXTRAPOLATION
Перенос результата между scope: культура, популяция, климат, версия ПО, юрисдикция, лаборатория/поле и т.д.

### PRACTICE
Практическая рекомендация или устоявшееся правило без сильной первичной доказательной базы.

### ASSUMPTION
Предпосылка, на которой строятся другие claims. Она должна быть полноценным узлом, чтобы можно было вычислить её downstream impact.

### RECOMMENDATION
Предписание или выбор действия. К ней применяются более строгие правила, чем к описательному claim.

---

## 8. Рёбра графа

```python
class EdgeType(str, Enum):
    CONTAINS = "contains"
    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    ASSUMES = "assumes"
    GENERALIZES = "generalizes"
    EXTRAPOLATES_FROM = "extrapolates_from"
    CAUSES = "causes"
    CORRELATES_WITH = "correlates_with"
    JUSTIFIES = "justifies"
    REQUIRES = "requires"
    APPLIES_IF = "applies_if"
    INVALIDATES = "invalidates"
```

Ребро само должно иметь состояние:

```yaml
id: EDGE-029
from: C037
to: C038
type: derived_from
confidence: 0.64

validation:
  status: needs_review
  rules_passed:
    - source_exists
  rules_failed:
    - derivation_not_declared
```

Это критично: два корректных claims могут быть соединены некорректным логическим переходом.

---

## 9. Почему проверять надо рёбра

Допустим:

```text
C1: В исследовании применяли 40–80 кг N/га.
C2: Бедные почвы хуже удерживают питательные вещества.
```

Оба claim могут быть поддержаны.

Но вывод:

```text
C3: Поэтому на бедной почве нужно 60–100 кг N/га.
```

не становится автоматически доказанным.

Проблема находится в переходе:

```text
C1 + C2 --derived_from--> C3
```

Следовательно validator проверяет не только nodes, но и edge semantics.

---

## 10. Числа как объекты первого класса

Числовые значения лучше хранить отдельно.

```python
@dataclass
class Quantity:
    id: str
    value: float | None
    lower: float | None
    upper: float | None
    unit: str
    semantic: str
    scope: dict
    evidence_id: str | None
    derivation_id: str | None
    exact: bool = False
    approximate: bool = False
```

Жёсткое правило:

```python
if quantity.evidence_id is None and quantity.derivation_id is None:
    quantity.status = "unsupported"
```

Точная цифра не должна появляться в финальном тексте просто потому, что LLM написала её уверенным тоном, этим старым человеческим трюком убеждения без доказательств.

---

## 11. Derivation Object

Для вычисляемого вывода создаётся отдельный объект:

```yaml
id: D019
type: arithmetic

inputs:
  - C037
  - A017

operation:
  expression: "baseline * multiplier"

parameters:
  multiplier:
    lower: 1.5
    upper: 2.0

output:
  claim_id: C038

validation:
  executable: true
  result_reproduced: true
```

Если вывод арифметический, код обязан воспроизвести его. LLM может предложить формулу, но итог вычисляет deterministic executor.

---

## 12. Статусы

Не использовать одно поле `confidence` как универсальную истину.

```python
class ClaimStatus(str, Enum):
    NEW = "new"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONFLICTING = "conflicting"
    NEEDS_VERIFICATION = "needs_verification"
    NEEDS_RESEARCH = "needs_research"
    BLOCKED = "blocked"
    REJECTED = "rejected"
```

Отдельно хранить измерения:

```yaml
scores:
  evidence_strength: 0.91
  source_quality: 0.84
  scope_match: 0.72
  convergence: 0.55
  derivation_quality: 1.0
  contradiction_risk: 0.10
  action_risk: 0.20
```

---

## 13. State machine

LLM не должна напрямую менять статус claim.

```python
ALLOWED_TRANSITIONS = {
    "new": {
        "needs_verification",
        "unsupported",
        "partially_supported",
        "supported",
    },
    "unsupported": {
        "needs_research",
        "rejected",
        "supported",
    },
    "supported": {
        "conflicting",
        "partially_supported",
        "rejected",
    },
    "conflicting": {
        "needs_research",
        "supported",
        "rejected",
    },
}
```

Изменение выполняется только через `ClaimStateMachine.transition()` с reason/event.

---

## 14. Claim Registry

Researcher, validator и writer не должны напрямую мутировать JSON.

```python
class ClaimRegistry:
    def create_claim(self, claim): ...
    def update_claim(self, claim_id, patch): ...
    def add_evidence(self, claim_id, evidence_id): ...
    def add_dependency(self, parent, child, relation): ...
    def set_status(self, claim_id, status, reason): ...
    def get_dependencies(self, claim_id): ...
    def get_dependents(self, claim_id): ...
    def invalidate_subgraph(self, claim_id): ...
```

Registry становится единственной точкой записи.

---

## 15. Dynamic code вместо предметного hardcode

Плохая архитектура:

```python
if claim.domain == "agriculture":
    ...
elif claim.domain == "medicine":
    ...
elif claim.domain == "software":
    ...
```

Она быстро превращается в хрупкий комбайн.

Core rules должны зависеть от свойств claims:

```text
has_numeric_value
is_recommendation
is_extrapolation
has_direct_evidence
has_scope_shift
has_causal_language
has_conflicting_evidence
has_unresolved_assumption
```

Пример:

```python
class Rule:
    id: str
    severity: str

    def applies(self, claim, graph) -> bool:
        ...

    def check(self, claim, graph):
        ...
```

```python
class NumericRequiresProvenance(Rule):
    id = "numeric_requires_provenance"

    def applies(self, claim, graph):
        return bool(claim.quantities)

    def check(self, claim, graph):
        return all(
            q.evidence_id or q.derivation_id
            for q in claim.quantities
        )
```

Новые rules регистрируются динамически.

---

## 16. Declarative rules

Часть поведения лучше вынести в YAML:

```yaml
rules:
  - id: numeric_requires_provenance
    applies_if:
      has_quantity: true
    require_any:
      - quantity.evidence_id
      - quantity.derivation_id
    on_fail:
      status: needs_verification
      severity: error

  - id: recommendation_requires_support
    applies_if:
      claim_class: recommendation
    require:
      incoming_edges:
        type:
          - justifies
          - supports
        min_count: 1
    on_fail:
      status: blocked
      severity: error
```

Код интерпретирует декларацию. Политика меняется без переписывания validator.

---

## 17. Слои правил

Разделить:

```text
schema rules
эпистемические rules
domain rules
action rules
```

`schema` проверяют целостность структуры.

`epistemic` проверяют provenance, inference, scope, числа и зависимости.

`domain` подключаются skill/plugin-модулями.

`action` решают, можно ли превращать knowledge node в рекомендацию или действие.

---

## 18. Recommendation Gate

```python
def recommendation_gate(rec, graph):
    parents = graph.incoming(
        rec.id,
        relations={"supports", "justifies", "derived_from"},
    )

    if not parents:
        return BLOCK("no_support")

    if any(p.status in {"unsupported", "blocked", "rejected"}
           for p in parents):
        return BLOCK("invalid_parent")

    if graph.has_unresolved_assumption(rec.id):
        return REVIEW("unresolved_assumption")

    if graph.has_scope_mismatch(rec.id):
        return REVIEW("scope_mismatch")

    return ALLOW()
```

Рекомендация должна иметь непрерывный justification path до evidence.

---

## 19. Risk-aware policy

Порог зависит от риска действия:

```yaml
action_policy:
  low:
    require:
      evidence_strength: 0.40

  medium:
    require:
      evidence_strength: 0.65
      unresolved_conflicts: 0

  high:
    require:
      evidence_strength: 0.80
      unresolved_conflicts: 0
      unsupported_assumptions: 0
      unmarked_extrapolation: false
```

Описательное предложение и опасный tool action не должны проходить один и тот же gate.

---

## 20. Propagation Engine

Если родительский узел меняется, зависимые узлы должны автоматически стать dirty.

```python
def invalidate_descendants(graph, node_id):
    queue = [node_id]
    visited = set()

    while queue:
        current = queue.pop(0)

        for child in graph.children(current):
            if child.id in visited:
                continue

            visited.add(child.id)
            graph.mark_dirty(
                child.id,
                reason=f"dependency_changed:{current}",
            )
            queue.append(child.id)
```

Пример:

```text
A17 rejected
 ↓
C31 dirty
 ↓
C32 dirty
 ↓
R04 blocked pending validation
```

---

## 21. Incremental validation

Не перевалидировать весь граф после каждого события.

Каждый node:

```yaml
validation:
  dirty: true
  last_validated_at: null
  validator_version: null
```

Алгоритм:

```text
new evidence
 ↓
changed node
 ↓
mark descendants dirty
 ↓
topological sort dirty subgraph
 ↓
validate parents before children
 ↓
commit statuses
```

---

## 22. DAG и циклы

Эпистемические зависимости желательно держать DAG.

```text
C1 → C2 → C1
```

обычно означают круговое обоснование.

При добавлении `supports`, `derived_from`, `justifies`, `assumes`:

```python
if graph.would_create_cycle(edge):
    reject(edge)
```

Отношения `related_to` или `correlates_with` могут жить в отдельном semantic graph и не участвовать в dependency DAG.

---

## 23. Scope

Scope должен быть структурой, а не примечанием в prose.

```yaml
scope:
  entity:
    type: crop
    species: Rubus_idaeus

  geography:
    country: Poland

  environment:
    field: true
    greenhouse: false

  soil:
    type: sandy_loam

  time:
    season: growing
```

Для parent/child вычисляется `scope_delta`.

```yaml
delta:
  species:
    from: strawberry
    to: raspberry
severity: major
```

Если `scope_delta != empty`, а claim не помечен `EXTRAPOLATION`, validator создаёт ошибку.

---

## 24. Evidence convergence

Три ссылки не всегда равны трём независимым подтверждениям.

```text
blog A → review X
blog B → review X
article C → review X
```

Фактически корень один.

Минимум хранить:

```yaml
source:
  primary_origin_id: S001
  source_family: F014
```

Convergence считать по независимым roots, а не по количеству URL.

---

## 25. Conflict Object

```yaml
id: CF019
type: conflict
claims:
  - C014
  - C027
conflict_type: numeric
status: unresolved
```

Порядок разрешения:

```text
1. scope
2. units
3. time/version
4. definitions
5. source quality
6. primary/secondary lineage
7. реальное substantive contradiction
```

Нельзя просто выбрать claim с большим `confidence`.

---

## 26. Gap Object

Отсутствие знания тоже должно быть узлом состояния.

```yaml
id: G019
type: gap
question: "Подтверждено ли увеличение дозы N на бедной почве?"
blocks:
  - C038
  - R004
status: open
```

Это лучше, чем затерявшееся в отчёте «нужно уточнить».

---

## 27. Research Queue

Из gaps строится очередь доисследования.

```yaml
research_queue:
  - gap_id: G019
    query_goal: >
      Найти прямые данные о корректировке нормы N
      при низкой обеспеченности почвы.
    expected_impact:
      claims: 7
      recommendations: 3
    priority: 0.89
```

Практическая функция приоритета:

```text
priority =
    uncertainty
  × downstream_impact
  × action_risk
  × task_relevance
  / estimated_research_cost
```

То есть researcher ищет не «ещё статьи», а тот кусок знания, который сильнее всего изменит граф.

---

## 28. Blast radius

Для слабого узла вычислять:

```yaml
blast_radius:
  descendant_claims: 14
  recommendations: 6
  actions: 2
```

Слабый claim с большим downstream impact исследуется раньше локального спорного факта.

---

## 29. Derivation depth

```text
E1 → C1               depth 1
E1 → C1 → C2          depth 2
E1 → C1 → C2 → C3     depth 3
```

Большая глубина не означает ложность, но повышает риск накопления преобразований и может повышать требования validator.

---

## 30. Deduplication и fingerprint

Claim fingerprint желательно строить по нормализованным полям:

```text
subject
predicate
object
scope
```

```python
fingerprint = hash(
    canonical_subject
    + predicate
    + canonical_object
    + normalized_scope
)
```

Embedding similarity можно использовать как candidate generator, но окончательное merge выполнять deterministic logic после unit/entity normalization.

---

## 31. Normalization layer

Registry нормализаторов:

```text
units
dates
entities
versions
geography
species
chemical names
software packages
```

```python
class NormalizerRegistry:
    def normalize_entity(self, value): ...
    def normalize_quantity(self, value, unit): ...
    def normalize_date(self, value): ...
    def normalize_scope(self, scope): ...
```

Domain skill регистрирует дополнительные normalizers, не меняя core.

---

## 32. LLM только как Proposal Engine

Правильный путь:

```text
raw evidence
 ↓
deterministic parsers
 ↓
known quantities/entities/dates
 ↓
LLM proposes semantic claims/relations
 ↓
Pydantic / JSON Schema
 ↓
pre-commit validators
 ↓
graph transaction
```

LLM не пишет напрямую в graph store.

---

## 33. ClaimProposal != Claim

```python
class ClaimProposal(BaseModel):
    text: str
    claim_class: ClaimClass
    subject: str | None
    predicate: str | None
    object: Any | None
    evidence_ids: list[str]
    parent_claim_ids: list[str]
    quantities: list[QuantityProposal]
    scope: Scope
    assumptions: list[str]
```

После проверки:

```text
ClaimProposal
    ↓ schema
    ↓ provenance
    ↓ numeric check
    ↓ scope check
    ↓ cycle check
Claim
```

Это важное разделение между «модель предложила» и «система приняла».

---

## 34. Transactional Graph Commit

```python
proposal = llm_extract(evidence)

tx = graph.begin()
tx.add_claims(proposal.claims)
tx.add_edges(proposal.edges)

errors = precommit_validator.validate(tx)

if errors:
    tx.reject()
else:
    tx.commit()
```

В граф не должен попадать полупроверенный мусор.

---

## 35. Validator Pipeline

Не один гигантский `validate_everything()`.

```text
SchemaValidator
 ↓
EvidenceValidator
 ↓
NumericValidator
 ↓
ScopeValidator
 ↓
DerivationValidator
 ↓
ConflictValidator
 ↓
RecommendationValidator
```

Каждый validator возвращает events, а не переписывает состояние произвольно.

---

## 36. Validation Event

```yaml
id: VE019
validator: numeric_validator
target: C038
severity: error
code: NUMERIC_WITHOUT_PROVENANCE
message: "Числовой диапазон не связан с evidence или derivation."
suggested_action:
  type: research
```

State reducer затем применяет event к графу.

---

## 37. Event-driven layer

Полезные события:

```text
SourceCreated
SourceInvalidated
EvidenceCreated
ClaimProposed
ClaimCommitted
EdgeCreated
ClaimChanged
ConflictDetected
GapOpened
GapResolved
RecommendationBlocked
```

Handlers подписываются через event bus.

```python
event_bus.subscribe("ClaimCommitted", numeric_validator.handle)
event_bus.subscribe("ClaimChanged", dependency_propagator.handle)
```

Это уменьшает сцепление модулей.

---

## 38. Reducer и audit log

```python
new_state = reduce(old_state, event)
```

Все изменения логируются:

```yaml
timestamp: "..."
claim_id: C037
event:
  type: status_changed
from: needs_verification
to: supported
reason:
  evidence_added: E014
actor:
  type: validator
  id: evidence_validator_v2
```

Для отладки это полезнее внутреннего монолога LLM: есть воспроизводимая история машинных решений.

---

## 39. Storage

Для первой версии достаточно SQLite.

Таблицы:

```text
sources
evidence
claims
edges
quantities
derivations
conflicts
gaps
events
snapshots
```

Graph traversal можно выполнять через adjacency maps в памяти.

Neo4j на старте не нужен. Нет смысла заводить графовую СУБД раньше, чем появился граф, достойный такого пафоса.

---

## 40. Repository layer

```python
class ClaimRepository(Protocol):
    def get(self, id): ...
    def save(self, claim): ...
    def query(self, filter): ...
```

Реализации:

```text
MemoryClaimRepository
SQLiteClaimRepository
PostgresClaimRepository
```

Бизнес-логика не зависит от storage.

---

## 41. Capability Registry

Динамическое расширение:

```python
registry.register_validator(...)
registry.register_normalizer(...)
registry.register_rule(...)
registry.register_scope_dimension(...)
registry.register_action_policy(...)
```

Новый domain skill регистрирует возможности. Core не делает `if domain == ...`.

---

## 42. Hooks

Полезные hooks:

```text
before_claim_commit
after_claim_commit
before_edge_commit
after_edge_commit
before_validation
after_validation
before_recommendation_release
before_action_release
```

Пример:

```python
hooks.register(
    "before_recommendation_release",
    domain_safety_gate,
)
```

---

## 43. Контракт Researcher → Graph

Researcher должен возвращать не только prose:

```yaml
research_result:
  query_id: Q001
  sources: [...]
  evidence: [...]
  claim_proposals: [...]
  unresolved: [...]
  search_trace: [...]
  human_report:
    markdown: "..."
```

`human_report` сохраняется для человека. Машина работает с первыми полями.

---

## 44. Контракт Validator

```yaml
validation_result:
  events:
    - target: C037
      rule: numeric_requires_provenance
      result: pass

    - target: C038
      rule: extrapolation_scope
      result: fail
```

Validator не должен возвращать переписанный граф целиком.

---

## 45. WriterContextBuilder

Writer не получает raw graph dump.

```text
Claim Graph
 ↓
WriterContextBuilder
 ↓
WriterContext
 ↓
LLM Writer
```

```yaml
writer_context:
  allowed:
    - claim_id: C001
      wording_policy: assertive

    - claim_id: C017
      wording_policy: qualified

  forbidden:
    - C031

  recommendations:
    - id: R04
      status: blocked

  gaps:
    - G019
```

---

## 46. Wording policy

Код определяет допустимый режим формулировки:

```text
SUPPORTED
→ assertive

PARTIALLY_SUPPORTED
→ qualified

EXTRAPOLATION
→ explicit_extrapolation

CONFLICTING
→ uncertainty_required

UNSUPPORTED
→ forbidden_as_fact
```

Writer выбирает естественный язык внутри разрешённого режима.

---

## 47. Citation renderer

Writer временно пишет ссылки на claim IDs:

```text
... [[C037]]
```

Затем renderer строит:

```text
claim_id
 ↓
evidence_ids
 ↓
source_ids
 ↓
formatted citations
```

LLM не должна сама управлять bibliography binding.

---

## 48. Evidence-to-Action invariant

Для любого действия должна существовать цепочка:

```text
Action
 ← Recommendation
 ← Claims
 ← Evidence
 ← Source
```

Если цепочка разорвана, action блокируется.

---

## 49. Жёсткие инварианты

Минимальный набор:

```text
1. Direct claim не существует без evidence.
2. Evidence не существует без source.
3. Numeric claim не содержит числа без evidence или derivation.
4. Inference имеет parent claims.
5. Extrapolation имеет явный scope delta.
6. Recommendation имеет justification path.
7. Blocked/rejected claim не поддерживает разрешённую recommendation.
8. Invalidated source делает зависимые узлы dirty.
9. Изменение parent делает descendants dirty.
10. Dependency DAG не содержит циклов.
```

Это должны быть программные ограничения, а не пожелания в prompt.

---

## 50. Failure modes, которые граф должен ловить

### Citation laundering
Одна citation визуально приклеивается к нескольким утверждениям. В графе невозможно, если citation идёт через evidence.

### Numeric hallucination
Точная цифра без provenance.

### Scope drift
Клубника → малина, мыши → человек, США → Германия, v1.2 → v3.0.

### Causal inflation
`correlates_with` превращается в `causes`.

### Recommendation collapse
Несколько гипотез → агент выбирает одну → сразу предлагает действие.

### Unsupported generalization
Один эксперимент → универсальная норма.

---

## 51. Causal edge validator

Для `causes` требования выше, чем для `correlates_with`.

```python
if edge.type == EdgeType.CAUSES:
    require_stronger_evidence(edge)
```

Какие именно evidence types достаточны, задаёт domain skill.

---

## 52. Hypothesis Set

Когда есть альтернативные объяснения:

```yaml
id: HS01
candidates:
  - C101
  - C102
  - C103
status: unresolved
```

До появления discriminating evidence нельзя тихо выбрать один вариант только потому, что он удобнее для ответа.

Planner должен создавать вопросы, различающие гипотезы:

```yaml
question:
  id: Q17
  discriminates:
    - C101
    - C102
  expected_information_gain: 0.72
```

---

## 53. Targeted research

```yaml
research_task:
  target_claim: C038
  goal: verify
  required_evidence:
    type:
      - primary_research
  scope:
    crop: raspberry
    soil: nutrient_poor
  reject_scope:
    - strawberry
    - hydroponics
```

Research loop становится адресным.

---

## 54. Stop conditions

Поиск не должен бесконечно искать подтверждение желаемому выводу.

```text
stop if:
  enough independent evidence
  and scope match sufficient
  and no major unresolved conflict
```

или:

```text
stop if budget exhausted
```

или:

```text
stop if expected information gain < threshold
```

---

## 55. Трёхзначная логика правил

Использовать:

```text
PASS
FAIL
UNKNOWN
```

`UNKNOWN` не равно `FAIL`.

Отсутствие evidence означает «не установлено», а не автоматически «ложно».

Это особенно важно для research agent под open-world assumption.

---

## 56. Temporal validity

Для изменяемой информации:

```yaml
temporal:
  observed_at: "..."
  valid_from: "..."
  valid_until: null
  freshness_required: true
```

Если freshness policy нарушена, claim становится `needs_verification`.

---

## 57. Source invalidation

```text
SourceInvalidated(S12)
 ↓
E17 dirty
 ↓
C22 dirty
 ↓
C23 dirty
 ↓
R04 blocked pending validation
```

Это должно происходить кодом автоматически.

---

## 58. Versioning и snapshots

Claim:

```yaml
id: C037
revision: 4
```

Для итогового ответа сохраняется snapshot:

```yaml
snapshot:
  id: GS20260828-001
  graph_version: 182
  claims:
    - C001@2
    - C037@4
    - C081@1
```

Так можно воспроизвести, на каком состоянии был построен ответ.

---

## 59. Структура проекта

```text
claim_graph/

    models/
        source.py
        evidence.py
        claim.py
        edge.py
        quantity.py
        scope.py
        conflict.py
        gap.py

    registry/
        claim_registry.py
        rule_registry.py
        capability_registry.py

    graph/
        graph.py
        traversal.py
        dependency.py
        propagation.py

    validation/
        base.py
        schema.py
        evidence.py
        numeric.py
        scope.py
        derivation.py
        conflict.py
        recommendation.py

    rules/
        core.yaml
        epistemic.yaml
        recommendation.yaml

    events/
        events.py
        bus.py
        reducer.py

    research/
        gap_planner.py
        priority.py
        research_queue.py

    writer/
        context_builder.py
        citation_renderer.py
        wording_policy.py

    storage/
        repository.py
        sqlite.py

    hooks/
        registry.py

    adapters/
        llm_claim_extractor.py
        llm_relation_proposer.py

    tests/
        ...
```

---

## 60. Core не знает LLM

`claim_graph/core` не должен импортировать конкретный SDK модели.

LLM находится в adapter:

```python
class ClaimExtractor(Protocol):
    async def extract(
        self,
        evidence: list[Evidence],
    ) -> ClaimProposalBatch:
        ...
```

Реализации могут быть разными:

```text
OpenAIClaimExtractor
LocalClaimExtractor
RuleBasedClaimExtractor
```

Граф и validator тестируются без модели.

---

## 61. Deterministic first

Предпочтительный порядок:

```text
regex/parser
 ↓
normalizer
 ↓
known rules
 ↓
LLM only if semantic ambiguity remains
```

Например, числа, единицы и даты разумнее сначала извлекать кодом.

```python
quantities = quantity_parser.extract(text)
entities = entity_normalizer.resolve(text)

claim_proposals = await llm.extract(
    text=text,
    known_quantities=quantities,
    known_entities=entities,
)
```

---

## 62. Проверка LLM proposal

После ответа модели код проверяет:

```text
1. schema valid
2. referenced evidence exists
3. quoted span exists
4. numbers match evidence or derivation
5. units normalize
6. parent IDs exist
7. edge type allowed
8. no dependency cycle
9. scope structure valid
```

Только после этого commit.

---

## 63. Span verification

Если модель предлагает offsets:

```yaml
start: 120
end: 183
```

код проверяет совпадение с source text. Допустима нормализация whitespace, но не фантазия.

---

## 64. Claim split validator

Сигналы слишком составного claim:

```text
несколько независимых predicates
несколько quantities
несколько причинных глаголов
соединение независимых тезисов через "и", "а также"
```

Код может поставить `NEEDS_SPLIT`, а LLM вызывается только для локальной декомпозиции.

---

## 65. Малые semantic jobs для LLM

Вместо:

```text
Вот 400 строк. Проверь всё.
```

задачи вида:

```text
Does E17 support C12?
Is C14 stronger causally than E22?
Does C31 extend beyond scope of E31?
Should sentence X be split into multiple claims?
```

Модель решает маленькую семантическую неопределённость. Код сохраняет решение только после policy checks.

---

## 66. Testing

Большинство тестов не требуют LLM.

```text
test_numeric_without_evidence_is_blocked
test_scope_shift_requires_extrapolation
test_invalid_parent_blocks_recommendation
test_source_invalidation_propagates
test_dependency_cycle_is_rejected
test_only_dirty_nodes_are_revalidated
```

Golden fixtures:

```text
tests/fixtures/
    supported_chain.yaml
    broken_numeric_chain.yaml
    extrapolation.yaml
    conflict.yaml
```

Полезны property-based tests на инварианты и replay tests по event log.

---

## 67. Observability

Минимальные метрики:

```text
claims_total
claims_supported
claims_unsupported
claims_conflicting
claims_extrapolated
recommendations_allowed
recommendations_blocked
numeric_claims_without_provenance
open_gaps
research_queue_size
max_blast_radius
average_dependency_depth
```

---

## 68. Debug view

```text
C038 [NEEDS_RESEARCH]
"На бедной почве использовать 60–100 кг N/га"

Parents:
  C037 [SUPPORTED]
  A017 [UNSUPPORTED]

Quantities:
  60–100 kg N/ha
  provenance: derivation D019

Blocked recommendations:
  R004

Blast radius:
  7 claims
  3 recommendations
```

Это должен уметь печатать обычный CLI без LLM.

---

## 69. Связь с ReAct

Claim Graph не должен жить внутри текстового scratchpad.

```text
Thought
 ↓
Tool call
 ↓
Observation
 ↓
Evidence ingestion
 ↓
Claim Graph update
 ↓
Policy engine
 ↓
Next allowed actions
```

Graph является частью environment state.

LLM получает только релевантный slice через ContextBuilder.

---

## 70. Context Builder и rerank

Не передавать модели весь граф.

```python
context = graph_context_builder.build(
    task=current_task,
    max_nodes=40,
    include={"parents", "conflicts", "gaps"},
)
```

Реранк узлов:

```text
relevance_to_task
× uncertainty
× downstream_impact
× action_impact
```

Так граф естественно соединяется с общей системой динамического контекста агента.

---

## 71. Память != Claim Graph

Разделить:

```text
episodic memory
user memory
working memory
research evidence
claim graph
```

Claim Graph хранит эпистемическое состояние исследования или проекта, а не всю память агента.

На первом этапе лучше сделать graph project-scoped.

---

## 72. Action Gate

Если claim используется для tool action:

```text
claim → recommendation → action
```

нужен отдельный gate.

```python
def action_gate(action, graph):
    path = graph.justification_path(action.id)

    if not path:
        return BLOCK

    if path.has_blocked_node:
        return BLOCK

    if action.risk == "high":
        require_strict_policy(path)

    return ALLOW
```

LLM не должна получать возможность выполнить опасное действие только потому, что сама же убедилась в своей рекомендации.

---

## 73. Распределение ответственности

| Задача | Код | LLM |
|---|---:|---:|
| ID и ссылки | основной | нет |
| Graph mutations | основной | proposal |
| State transitions | основной | нет |
| Cycle checks | основной | нет |
| Unit normalization | основной | assist |
| Numeric provenance | основной | extraction |
| Scope comparison | основной | extraction assist |
| Semantic claim extraction | validate | основной |
| Relation proposal | validate | основной |
| Recommendation decision | gate | proposal |
| Writer wording | constraints | основной |
| Citation binding | основной | нет |
| Research priority | формула | semantic inputs |

Коротко:

> **LLM отвечает за семантическую неопределённость. Код отвечает за архитектурную определённость.**

---

## 74. Практический полный цикл

```text
1. Retriever получает документ.
2. Source Registry создаёт Source.
3. Evidence Extractor выделяет spans/data.
4. Parsers извлекают числа, единицы, даты, известные entities.
5. LLM Claim Extractor создаёт ClaimProposalBatch.
6. Proposal Validator проверяет schema/span/numbers/references.
7. Claim Registry создаёт узлы.
8. Relation proposer предлагает связи.
9. Graph validator проверяет типы рёбер, scope и циклы.
10. Rule Engine запускает применимые правила.
11. State Reducer обновляет статусы.
12. Dependency Propagator помечает descendants dirty.
13. Gap Builder создаёт gaps.
14. Research Prioritizer считает impact.
15. Planner создаёт targeted research tasks.
16. Новые evidence обновляют граф.
17. Recommendation Gate разрешает или блокирует рекомендации.
18. Action Gate отдельно проверяет tool actions.
19. WriterContextBuilder создаёт разрешённый context slice.
20. Writer пишет prose.
21. CitationRenderer привязывает claims к evidence/source.
22. Snapshot фиксирует состояние графа для ответа.
```

---

## 75. Рекомендуемый порядок реализации

### Phase 1. Provenance core

Сущности:

```text
Source
Evidence
Claim
Edge
Quantity
```

Функции:

```text
create
link
parents
children
ancestors
descendants
```

Validators:

```text
schema
evidence
numeric
dependency
cycle
```

### Phase 2. Epistemic semantics

Добавить:

```text
Scope
Assumption
Inference
Extrapolation
Recommendation
```

Validators:

```text
scope delta
derivation
recommendation gate
```

### Phase 3. Research control

Добавить:

```text
Gap
Conflict
ResearchQueue
BlastRadius
DirtyNodes
Propagation
```

После этой фазы граф начинает управлять следующим поиском.

### Phase 4. Reliability

Добавить:

```text
events
audit log
snapshots
versioning
replay
```

### Phase 5. Extension

Добавить:

```text
domain skills
dynamic rules
semantic validators
writer context builder
citation renderer
action gate
```

---

## 76. Что не делать в первой версии

Не начинать с:

```text
Neo4j cluster
гигантской онтологии
полного Bayesian network
multi-agent tribunal
пяти LLM validators
формальной логики первого порядка на всё подряд
```

Сначала нужны работающие provenance, dependency DAG, propagation и gates. Иначе получится великолепный собор архитектуры, внутри которого всё ещё лежит один JSON и молится, чтобы модель не соврала.

---

## 77. Минимальный Python skeleton

```python
from dataclasses import dataclass, field
from enum import Enum


class ClaimStatus(str, Enum):
    NEW = "new"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    NEEDS_RESEARCH = "needs_research"
    CONFLICTING = "conflicting"
    BLOCKED = "blocked"
    REJECTED = "rejected"


class EdgeType(str, Enum):
    SUPPORTS = "supports"
    DERIVED_FROM = "derived_from"
    CONTRADICTS = "contradicts"
    ASSUMES = "assumes"
    JUSTIFIES = "justifies"
    EXTRAPOLATES_FROM = "extrapolates_from"


@dataclass
class Claim:
    id: str
    text: str
    claim_class: str
    status: ClaimStatus = ClaimStatus.NEW
    scope: dict = field(default_factory=dict)
    quantities: list[str] = field(default_factory=list)
    dirty: bool = True


@dataclass
class Edge:
    source: str
    target: str
    type: EdgeType


class ClaimGraph:
    def __init__(self):
        self.claims = {}
        self.outgoing = {}
        self.incoming = {}

    def add_claim(self, claim):
        self.claims[claim.id] = claim

    def add_edge(self, edge):
        if self.would_create_cycle(edge):
            raise ValueError("epistemic cycle")

        self.outgoing.setdefault(edge.source, []).append(edge)
        self.incoming.setdefault(edge.target, []).append(edge)
        self.mark_descendants_dirty(edge.target)

    def parents(self, claim_id):
        return [
            self.claims[e.source]
            for e in self.incoming.get(claim_id, [])
            if e.source in self.claims
        ]

    def children(self, claim_id):
        return [
            self.claims[e.target]
            for e in self.outgoing.get(claim_id, [])
            if e.target in self.claims
        ]

    def mark_descendants_dirty(self, claim_id):
        queue = [claim_id]
        visited = set()

        while queue:
            current = queue.pop(0)
            if current in visited:
                continue

            visited.add(current)
            claim = self.claims.get(current)

            if claim:
                claim.dirty = True

            for edge in self.outgoing.get(current, []):
                queue.append(edge.target)

    def would_create_cycle(self, edge):
        # DFS/BFS implementation
        return False
```

---

## 78. Rule Engine skeleton

```python
class RuleResult:
    def __init__(self, rule_id, result, severity="error", message=None):
        self.rule_id = rule_id
        self.result = result  # PASS / FAIL / UNKNOWN
        self.severity = severity
        self.message = message


class Rule:
    id = "base"

    def applies(self, claim, graph):
        return True

    def check(self, claim, graph):
        raise NotImplementedError


class RecommendationSupportRule(Rule):
    id = "recommendation_requires_support"

    def applies(self, claim, graph):
        return claim.claim_class == "recommendation"

    def check(self, claim, graph):
        parents = graph.parents(claim.id)

        if not parents:
            return RuleResult(
                self.id,
                "FAIL",
                message="Recommendation has no support",
            )

        invalid = [
            p for p in parents
            if p.status in {
                ClaimStatus.UNSUPPORTED,
                ClaimStatus.BLOCKED,
                ClaimStatus.REJECTED,
            }
        ]

        if invalid:
            return RuleResult(
                self.id,
                "FAIL",
                message="Recommendation depends on invalid claims",
            )

        return RuleResult(self.id, "PASS")
```

---

## 79. Validation Engine skeleton

```python
class ValidationEngine:
    def __init__(self, rules):
        self.rules = rules

    def validate_claim(self, claim, graph):
        results = []

        for rule in self.rules:
            if not rule.applies(claim, graph):
                continue

            results.append(
                rule.check(claim, graph)
            )

        return results
```

Не стоит зашивать state transition непосредственно внутрь каждого rule. Rule сообщает результат. Reducer решает, что он означает для состояния.

---

## 80. Критерий успешной интеграции

Слой можно считать встроенным правильно, если система программно, без отдельного «умного промпта», умеет:

```text
1. показать evidence chain для любого claim;
2. отличить source claim от inference;
3. показать assumptions;
4. показать scope и scope delta;
5. найти неподтверждённые числа;
6. обнаружить слабое causal/generalization edge;
7. вычислить downstream dependents;
8. автоматически инвалидировать зависимые узлы;
9. блокировать recommendation при разрыве цепочки;
10. превратить unresolved gap в targeted research task;
11. ранжировать gaps по downstream impact;
12. сформировать writer context только из разрешённых claims;
13. восстановить решение из event log/snapshot.
```

Это и есть переход от «LLM старается быть аккуратной» к системе, где аккуратность частично обеспечивается конструкцией самого вычислительного процесса.
