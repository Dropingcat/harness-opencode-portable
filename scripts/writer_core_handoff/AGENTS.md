# AGENTS.md — нормативная инструкция агентам разработки

## 1. Миссия

Разрабатывать Writer Core 2 как **typed, auditable, dependency-aware semantic document build system**.

Нельзя подменять архитектурный контракт «умным промтом». Нельзя давать LLM права, которых нет у typed operation. Нельзя объявлять документ корректным только потому, что он выглядит профессионально.

## 2. Неподвижные инварианты

1. LLM не имеет прямой записи в authoritative state.
2. Document containment, writing decomposition, discourse, argumentation, epistemics, artifacts, provenance, policies, dependencies, execution и forensics — разные модели.
3. `Section`, `Paragraph`, `Sentence` не являются epistemic claims.
4. Argument role не меняет truth-state claim.
5. Source != Evidence. Summary != Evidence. Citation != entailment.
6. Writer не повышает доказательную силу, причинность, scope, precision или certainty claim без новой derivation/research admission.
7. Любая содержательная realization/rewriting/compression/expansion проходит Round-Trip Semantic Validation (RTT).
8. Числа, uncertainty, формулы, таблицы, рисунки, datasets, scripts, citations и cross-references имеют stable IDs и provenance.
9. Изменение upstream dependency переводит downstream в `STALE`/`REVERIFY_REQUIRED`; система не молча переписывает truth-dependent текст.
10. Шаблон = versioned executable pattern с pre/postconditions; не prompt fragment.
11. Один scalar confidence запрещён вместо typed assessments.
12. Hard validator fail-closed.
13. Любой automatic repair повторно проходит RTT.
14. `STALE != INVALID`; freshness и validity ортогональны.
15. Raw data immutable; derived artifacts rebuildable; approved/frozen content требует explicit authority transition.
16. Release невозможен при открытом `RELEASE_BLOCKING Blocker`.
17. Merge двух веток обязан проходить semantic validation, а не только text diff.
18. Abstract/conclusion/novelty/defense-position claims должны трассироваться к body claims и evidence.
19. Forensics/OSINT не имеет права изменять Writer/Researcher truth-state.
20. Attribution verdict в open-world режиме имеет право быть `INCONCLUSIVE`/`UNKNOWN_AUTHOR`.

## 3. Архитектурные права записи

- Researcher Core: Claim/Evidence/Scope/Derivation/Conflict truth-state.
- WriterRegistry: Document/Discourse/Argument-instance/Artifact-binding/Revision/Review/Blocker state.
- Computation adapters: только proposal/derived artifacts; commit через registry.
- Policies/Templates: Git-reviewed static registry.
- Human/expert: explicit approval decisions according to policy.
- Forensics: analytical projections only.

## 4. Перед любой реализацией

Агент обязан создать implementation note:

```yaml
operation:
  goal:
  reads:
  writes:
  authority_required:
  invariants_touched:
  deterministic_part:
  model_assisted_part:
  failure_modes:
  blocker_types_created:
  dependency_edges_created:
  tests:
  migration_impact:
```

Если невозможно назвать `reads`, `writes`, `authority_required` и postconditions, операция ещё не декомпозирована.

## 5. Запрещённые shortcuts

- universal `Node(type,payload,edges)` как доменная модель;
- hidden mutation внутри LLM callback;
- prompt-only business rules;
- reviewer-agent auto-approve;
- raw reference prose как executable template;
- corpus reference как factual evidence target-документа без Researcher admission;
- global rebuild вместо dependency closure без причины;
- один enum для lifecycle/review/validation/freshness;
- одно similarity/confidence число как quality verdict;
- автоматическое исправление raw data;
- свободная LLM-генерация DOI, чисел, формул, стандартов, bibliographic identity;
- silent migration schema;
- обход release gate вручную без Decision record.

## 6. Handoff между агентами

Каждый task оставляет:

- modified files;
- automated tests;
- at least one positive and one negative fixture;
- decision record при архитектурном выборе;
- known gaps and generated Blockers;
- dependency/migration note;
- exact next executable operations.

`works on my machine`, `LLM считает корректным` и `похоже на ожидаемое` не являются acceptance evidence.

## 7. Как выбирать следующую работу

Не «что хочется написать», а:

```text
ProjectState
→ unresolved blockers
→ dependency closure
→ critical path
→ ready operations
→ policy priority
```

Оркестратор выдаёт typed operation. Агент не придумывает себе следующий этап, если он не разрешён plan/gate.
## v0.3 mandatory rule for agents
Do not convert a semantic preference into a deterministic branch merely because it worked in one fixture. Classify control as HARD_INVARIANT, CONSTRAINT, SIGNAL or LEARNED_PREFERENCE. For semantic choices request/use an AffordanceSet and submit a typed proposal. Linguistic workers must use LinguisticDigest/IR and tier escalation; weak models must not be fed raw global graph dumps by default. Auditor observations have no authority over epistemic truth.
