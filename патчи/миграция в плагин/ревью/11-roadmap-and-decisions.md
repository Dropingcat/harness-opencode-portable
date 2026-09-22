# Roadmap и журнал исходных архитектурных решений

## 1. Порядок вертикальных срезов

### R0 — contracts

IDs, enums, entities, commands, events, serialization, Registry, GraphTransaction, repository ports.

### R1 — epistemic model

Claim, Quantity, Source, Evidence, Scope, Edge, Derivation, Gap, Conflict, Assumption, Recommendation.

### R2 — persistence/provenance

SQLite, revisions, event log, outbox, snapshots, traversal, dirty propagation.

### R3 — validation

Admission, atomicity, numeric, scope, derivation, edges, cycles, gaps/conflicts, structural risk.

### R4 — operations

Planner, Scheduler, budgets, queue, leases, LocalCorpus task.

### R5 — adapters

Claim extractor, LocalCorpus, metadata resolver, один academic provider, ModelGateway.

### R6 — stop/recovery

Coverage, saturation, typed stop, checkpoint/resume.

### R7 — writer

WriterContext, citations, writer decisions, post-write audit.

### R8 — opencode/legacy integration

`research-orchestrator`, subagents и server scripts через adapters.

## 2. Gate между этапами

Следующий этап начинается только после acceptance предыдущего. Наличие красивого demo не заменяет invariants, recovery и golden tests.

## 3. Исходные ADR

### ADR-001: SQLite first

**Решение:** SQLite WAL до измеренной необходимости в PostgreSQL.  
**Причина:** один process, простая доставка, транзакции, backup, достаточно для fixtures и локального runtime.

### ADR-002: materialized state + append-only events

**Решение:** не использовать ни только CRUD, ни чистый event sourcing.  
**Причина:** быстрые graph queries плюс provenance/rebuild.

### ADR-003: ClaimRegistry — единственная application write boundary

**Решение:** adapters/agents/plugins не пишут state.  
**Причина:** единые transitions, validation и audit.

### ADR-004: proposals отделены от entities

**Решение:** LLM output всегда proposal.  
**Причина:** недоверенный семантический исполнитель не получает authority.

### ADR-005: Writer изолирован от research

**Решение:** Writer получает frozen WriterContext.  
**Причина:** исключить добавление неподтверждённых claims и citations.

### ADR-006: LocalCorpus — первый adapter

**Решение:** интеграционный research loop сначала offline.  
**Причина:** воспроизводимость и отсутствие provider noise.

### ADR-007: legacy через anti-corruption layer

**Решение:** `HermesLegacyAdapter`, никаких прямых imports/DB access.  
**Причина:** скрытые assumptions, Linux paths и schema drift не должны заражать core.

### ADR-008: без универсального confidence

**Решение:** typed statuses/metadata/reason codes.  
**Причина:** один score смешивает несопоставимые неопределённости.

## 4. Отложенные решения

До появления данных не выбираются:

- PostgreSQL;
- graph database;
- distributed queue;
- vector database как authoritative memory;
- container orchestration;
- сложный plugin sandbox;
- автоматический multi-model voting;
- универсальный ontology DSL.

## 5. Первый backlog

1. Создать package skeleton и CI.
2. Реализовать IDs/enums/canonical serializer.
3. Зафиксировать JSON schemas fixtures.
4. Реализовать SQLite UnitOfWork и migrations.
5. Реализовать ClaimRegistry и `ALL_OR_NOTHING` transaction.
6. Добавить idempotency и revision conflicts.
7. Создать R0 dry run.
8. Добавить property/crash tests.
9. Реализовать базовые epistemic entities.
10. Добавить synthetic golden fixture.
11. Добавить Atomicity/Numeric validators.
12. Только затем завернуть текущий `claim-parser` adapter-ом.

## 6. Architecture review cadence

ADR создаётся при изменении hard invariant, authoritative state, persistence, public contract, security boundary или технологии уровня runtime. Мелкие локальные решения остаются в component spec и PR.

