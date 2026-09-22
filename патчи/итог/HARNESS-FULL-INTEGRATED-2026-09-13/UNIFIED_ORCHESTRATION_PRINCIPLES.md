# Unified Orchestration Principles

Единый слой принципов для researcher-core и code-factory: **одни и те же инварианты, разная степень строгости по risk/domain/task class**. Этот документ нужен, чтобы не изобретать вторую архитектуру для кодеров, а опираться на уже оформленный researcher runtime из `E:\барахло\Documents\Default Project`.

## 1. Общий инвариант

Для обоих контуров:

> **LLM производит предложения и свидетельства; код принимает решения.**

## 2. Общая архитектурная формула

```text
task
-> claim/proposal decomposition
-> typed registry / routing / buckets
-> deterministic runtime operations
-> validators / guards / policy gates
-> audited state
-> selective rework or finalize
```

## 3. Что researcher уже формализовал и что надо переиспользовать

### R0 core contracts

Из `03-r0-core-contracts.md`:

- dry, offline, boring core first;
- stable IDs and enums as wire API;
- command/event envelopes;
- state transitions only through typed requests;
- canonical JSON;
- idempotency and monotonic revisions;
- no adapter-owned domain mutation.

### Claim validation pipeline

Из `05-claim-validation-pipeline.md`:

- lifecycle entities instead of ad hoc statuses;
- many small validators, not one giant judge;
- conflict/gap/risk stored separately;
- recommendation gate separated from descriptive claims;
- reason codes are stable machine API.

### Deterministic runtime

Из `06-runtime-orchestration.md`:

- `RunController`, `Planner`, `Scheduler`, `BudgetManager`, `StopController`, `ContextBuilder`, `PromptRenderer`, `PolicyEngine`, registries.

Для code-factory это маппится так:

- `factory_ctl.py` = RunController facade;
- `code_factory_runner.py` = StopController + budget/state runtime;
- `tool-skill-contract-router.ts` = ContextBuilder + PromptRenderer hook layer;
- `config/*.json` = PolicyEngine source;
- `contract_validator.py` + guard + tests = validator registry.

### Policy config and heuristics

Из `12-policy-config-and-heuristics.md`:

> все эвристики, лимиты, веса, stop conditions и thresholds MUST жить в versioned policy config, а не в prompt-ах и не в коде.

## 4. Разница не в принципах, а в строгости

| Профиль | Для чего | Что усиливается |
|---|---|---|
| `soft` | локальный harness, дешёвый цикл, draft | больше noAgents, меньше агентов, partial ok |
| `standard` | обычная production-like работа | worker+reviewer+tester, guard обязателен для untrusted input |
| `strict` | high-risk research/security | full guard, more validators, tribunal/human review |

Что не меняется:

- typed claims/proposals;
- code-owned stop controller;
- explicit `PARTIAL/BLOCKED/UNRESOLVABLE` semantics;
- separation of evidence and confidence;
- no hidden hardcoded heuristics.

## 5. Единая модель claim/task/bucket

Researcher pattern переносится в code-factory без новой философии:

```text
task text
-> task claim proposals
-> admitted task claims
-> bucket assignment
-> execution operations
-> validations/audit
-> integrated result
```

`bucket` = **policy-scoped execution cell**, а не обязательно отдельный агент.

## 6. Единая модель графов

- **Knowledge graph** — claim/dependency/component/evidence graph;
- **Audit graph** — statuses, gaps, conflicts, findings, guard verdicts, test outcomes;
- **Integration snapshot** — то, что поднимается наверх глобальному orchestrator.

## 7. Единый stop semantics

Из researcher runtime:

- budget exhaustion => `PARTIAL`, не fake success;
- provider failure != evidence absence;
- no accessible capability/source => `UNRESOLVABLE` или `BLOCKED`;
- stop reason typed, not free-text.

Для code-factory:

- test budget exhausted != code correct;
- missing MCP != task solved;
- reviewer silence != approve;
- timeout != merge-ready.

## 8. Практическое правило для модуля

Если новый слой code-factory нарушает researcher-core принципы, считать это smell по умолчанию.

Проверочный список:

1. Где versioned policy config?
2. Где typed reason codes?
3. Где deterministic runtime owner?
4. Где idempotency/replay story?
5. Где explicit PARTIAL/BLOCKED semantics?
6. Где bucket/cell contract?
7. Где guard boundary?
8. Где noAgents fallback?

Если ответа нет — мы уже изобретаем велосипед.

## Sources

- `E:\барахло\Documents\Default Project\README(1).md`
- `E:\барахло\Documents\Default Project\03-r0-core-contracts.md`
- `E:\барахло\Documents\Default Project\05-claim-validation-pipeline.md`
- `E:\барахло\Documents\Default Project\06-runtime-orchestration.md`
- `E:\барахло\Documents\Default Project\12-policy-config-and-heuristics.md`
