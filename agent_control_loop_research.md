# Контур управления ИИ-агентом: исследовательский пакет

Дата локальной проверки: 2026-09-12.

## Метод

Материал собран из актуальной документации, конфигурации, runtime-кода, тестов и tracker проекта `doc_Opencode_agern-new`. Legacy и backup-копии не считались независимыми источниками. Для каждого паттерна различаются три статуса: `IMPLEMENTED/EXERCISED`, `DOCUMENTED POLICY`, `PROPOSED/BACKLOG`. Внешние публикации Anthropic, OpenAI и OWASP используются только для сопоставления терминов.

## Основные выводы

1. Локальный инвариант «LLM предлагает — код решает» передаёт детерминированному слою владение контрактами, переходами, gate verdicts и остановкой. Это `DOCUMENTED POLICY`, а не универсальный закон.
2. В code-factory реализованы два контура: вероятностный work plane создаёт evidence, а reducer строит authoritative state из append-only hash-chained events и frozen policy snapshot. Статус: `IMPLEMENTED/EXERCISED`.
3. Успех вычисляется по GateSet текущей попытки. Отдельный reviewer approval, tester PASS или молчание отсутствующего gate не означают завершения. Статус: `IMPLEMENTED/EXERCISED`.
4. Worker, reviewer, tester и process auditor разделены контрактами, однако полная capability-level изоляция auditor от кода подтверждена не полностью. Статус: `DOCUMENTED POLICY`.
5. Run state и L3 memory имеют разных владельцев: память хранит отобранные ретроспективные lessons, но не определяет текущий статус. Статус: `IMPLEMENTED/EXERCISED`.
6. Router работает claim-first: splitter назначает kind, bucket и stable ID, после чего строится grouped execution plan. Полный claim-level runtime остаётся незавершённым.
7. Routing policy компилируется в проверяемый snapshot с priorities, candidates, reason codes и policy hash. Это устраняет зависимость от порядка regex.
8. Минимально достаточная автономность остаётся эвристикой выбора: direct для одной перспективы, workflow/NoAgents для известного пути, single-agent для ограниченной неопределённости, fan-out для независимых ветвей, adversarial team для конкурирующих гипотез.
9. Fan-out требует независимости ветвей и явного evidence-aware merge. Текущий `/ship` artifact и отдельный merge validator не найдены, поэтому это пока policy.
10. Evidence before verdict реализован через artifact ID, hash, provenance и guard admission. Guard PASS означает допуск, а не истинность.
11. Dispatch retry ограничен одной и той же операцией и завершается возвратом управления пользователю; конкретные интервалы — локальная эвристика.
12. Writer-core обрывает repair loop при отсутствии изменения artifact. Аналогичный detector в code-factory не найден.
13. Retry, selective rework, replan и escalation — разные переходы. В code-factory непосредственно обкатаны attempt-local rework и tribunal trigger; unified REPLAN FSM нет.
14. Полная typed stop semantics пока является целью: policy требует `PARTIAL/BLOCKED/UNRESOLVABLE`, но inspected reducer использует неполный словарь.
15. Thread ritual восстанавливает архитектурную нить через snapshot, а не через бесконечное накопление prompt history. Его причинный эффект на качество не измерен.
16. Guard снижает риск, но локальная threat model сохраняет semantic, multi-hop, taint-loss и compaction blind spots.
17. `attempt_limit` имеет конфликтующий контракт между документацией/config и runtime tests; точное число попыток нельзя публиковать как согласованное.
18. Human-driven lifecycle и bounded autonomous run, fail-closed и optimistic checks, fixed pipeline и adaptive replan, end-state и trajectory evaluation должны подаваться как trade-offs.

## Паттерны, выведенные из практики

| Паттерн | Проблема | Механизм | Stop/failure mode | Зрелость |
|---|---|---|---|---|
| LLM предлагает — код решает | Модель принимает output за выполненное решение | Typed requests, validators, reducer | Invalid evidence не меняет state | DOCUMENTED POLICY |
| Два контура | Worker становится собственным судьёй | Work plane + deterministic control plane | Broken event chain блокирует replay | IMPLEMENTED/EXERCISED |
| GateSet before success | Reviewer silence превращается в fake success | Все gates текущего attempt должны дать PASS | PENDING, REWORK, FAILED, BLOCKED | IMPLEMENTED/EXERCISED |
| Evidence before verdict | Summary принимается без provenance | Hash, origin, guard verdict, evidence refs | Inadmissible artifact rejected | IMPLEMENTED/EXERCISED |
| Selective rework | Один дефект перезапускает всю задачу | Новый attempt только для failed scope | Attempt limit или escalation | IMPLEMENTED/EXERCISED частично |
| Bounded retry ladder | Provider failure вызывает вечный цикл | Same-operation retry с лимитом | Возврат пользователю | DOCUMENTED POLICY |
| No-progress cut-off | Repair ничего не меняет | Сравнение before/after | `no_progress` | IMPLEMENTED/EXERCISED в writer-core |
| Typed stop semantics | Timeout смешивается с успехом | Typed terminal states/reasons | Словарь реализован не полностью | PROPOSED/BACKLOG |
| Thread ritual | Orchestrator теряет roadmap и scope | Context snapshot на старте и закрытии | Reset при tunnel vision | IMPLEMENTED/EXERCISED |
| NoAgents fallback | LLM применяется к известному алгоритму | Rule-based route + validators | Escalate при недостижении acceptance | PROPOSED/BACKLOG как цельная ветка |
| Independent fan-out + explicit merge | Последовательность медленна, shared state создаёт гонки | Независимые reports и один merge owner | Fallback при зависимости ветвей | DOCUMENTED POLICY |
| Fresh-context challenge | Ранняя фиксация на первой гипотезе | Независимые контексты и опровержение | Не применять к routine verdict | DOCUMENTED POLICY |
| Memory is projection | Summary drift становится истиной | Promotion только с evidence/reason codes | Reject missing provenance | IMPLEMENTED/EXERCISED |
| Compiled routing policy | Порядок regex становится скрытой policy | Snapshot, priorities, candidates, hash | Escalate no-match/invalid mode | IMPLEMENTED/EXERCISED |
| Trust gate, not truth oracle | Prompt injection и untrusted output | Admission gate перед reuse/side effect | Fail closed с известными blind spots | IMPLEMENTED/EXERCISED |

## Реконструкция управляющего цикла

Это синтез нескольких подсистем, а не одна полностью реализованная FSM:

```text
goal → classify claims → scope risk/capabilities → contract
     → dispatch → register artifacts/provenance → verify gates
     → reduce events → decide
     → DONE | RETRY | SELECTIVE_REWORK | REPLAN | PARTIAL | BLOCKED | UNRESOLVABLE | ESCALATED
```

### Владение решениями

| Сущность | Модель предлагает | Код решает |
|---|---|---|
| Route | candidate и decomposition | допустимый bucket/profile/mode |
| Artifact | реализацию/observation | hash, origin, admission, schema validity |
| Review | findings | gate outcome |
| Tests | набор проверок | факт исполнения и соответствие acceptance |
| Run state | ничего напрямую | reducer projection |
| Memory | candidate lesson | promotion/rejection |
| Stop | рекомендацию | retry/rework/replan/block/finalize |

## Decision table

| Сигнал | Выбор | Обязательная защита |
|---|---|---|
| Один artifact и одна перспектива | Direct invocation | Acceptance/schema по риску |
| Полностью известный маршрут | Workflow / NoAgents | Validator, test, policy gate |
| Маршрут меняется в одной области ответственности | Single-agent loop | Tool guards, budget, stop controller |
| Независимые ветви | Fan-out/fan-in | Per-branch contract и explicit merge |
| Разные проверки одного artifact | Worker + reviewer + tester + auditor | Current-attempt GateSet |
| Конкурирующие гипотезы | Adversarial team | Hypothesis ledger и convergence rule |
| Permission gap или high-impact ambiguity | Human escalation | Revised contract или explicit approval |

## Failure stories

1. **Premature success:** reviewer APPROVE раньше переводил задачу в PASSED до tester gate. Reducer изменён так, чтобы ждать все required gates текущей попытки.
2. **Regex как скрытая policy:** first-match routing неверно классифицировал overlapping routes. Приоритеты перенесены в config, а candidates сохранены в результате.
3. **Ошибка единиц timeout:** значение в миллисекундах было передано API, ожидающему секунды, превращая защитный timeout почти в 50 часов.
4. **Раздувание ре-ревью:** передача всей истории вместо текущего module, diff и unresolved findings дала локально зафиксированный объём 293k tokens; введён delta-only re-review. Это observation проекта, не benchmark.
5. **Потеря runtime envelope:** `project_context.py` потребовал UTF-8 на Windows, показывая, что даже control-plane ritual зависит от корректной среды исполнения.

## Пробелы и запреты на преувеличение

- Нет единого executable controller для всей цепочки goal → decide; статья должна называть схему реконструкцией.
- Нет unified code-factory `REPLAN` transition.
- `PARTIAL` и `UNRESOLVABLE` отсутствуют в inspected reducer.
- Не подтверждены current `/ship`, evidence-aware merge validator и full NoAgents switch.
- Live guard wiring имеет противоречивый статус между runbook и tracker.
- Нельзя универсализировать retry intervals, iteration limits, monetary budgets, tribunal thresholds и 293k-token observation.
- Guard PASS нельзя превращать в factual correctness verdict.

## Главные локальные источники

- `UNIFIED_ORCHESTRATION_PRINCIPLES.md`
- `STATE_REDUCER_ARCHITECTURE.md`
- `STAGE2_ATTEMPT_GATESET_STATE_REDUCER_2026-09-06.md`
- `CLAIM_ROUTING_ARCHITECTURE.md`
- `MEMORY_POLICY.md`
- `DYNAMIC_HEURISTICS.md`
- `NO_AGENTS.md`
- `CODER_DESIGN_PRINCIPLES.md`
- `DEEP_REVIEW_2026-09-06.md`
- `shared/orchestration-patterns.md`
- `shared/orchestration-thread-process.md`
- `shared/dispatch-retry.md`
- `shared/code-factory-process.md`
- `agents/code-orchestrator.md`
- `scripts/code-factory/state_reducer.py`
- `scripts/code-factory/code_factory_runner.py`
- `tests/test_runtime_core.py`
- `guard/docs/THREAT_MODEL.md`
- `guard/docs/ARCHITECTURE.md`

Внешнее сопоставление: Anthropic “Building effective agents”, OpenAI “A practical guide to building agents”, OWASP LLM06:2025 Excessive Agency.
