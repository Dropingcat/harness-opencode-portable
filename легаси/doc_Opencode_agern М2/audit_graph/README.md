# Audit Graph Module

Единый машиночитаемый модуль аудита для всех агентов (coder/researcher/writer/auditor). Основа — `malina_research_service_fixture.yaml` + R0 из `Default Project` (03-r0-core-contracts, 05-claim-validation-pipeline, 06-runtime-orchestration).

Этот модуль — **source of truth** для задач. Память (L1/L2/L3) строится **поверх него** тем же капсульным способом — без хард-промптов и хард-кода, только проекции графа.

## Структура

```
audit_graph/
  src/audit_graph/
    domain/{ids,enums,entities,commands,events,state_machines,value_objects}
    application/{claim_registry,transactions}
    ports/{repositories}
    infrastructure/sqlite/
  config/audit_graph_schema.json
  config/agent_categories/*.json (20 файлов: 5 group + 15 per-agent капсул)
```

## Следующий шаг: память на этой базе

После фиксации audit_graph, память делается так же модульно:

- `memory_l2` = заполненный экземпляр `task_audit_template` по `run_id`
- `memory_l3` = recurring lessons из разных `audit snapshots`, прошедшие `recurring_count + evidence_ref` гейт

Детали — в `IMPLEMENTATION_TRACKER.md` WS-11.

## Принцип

Задача → разбивается на элементарные единицы (claims) → марируется → отслеживается перемещение по графу → аудит фиксирует каждый переход → память = проекция того же шаблона.
