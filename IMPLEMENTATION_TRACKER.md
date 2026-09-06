# Implementation Tracker

Подробный трекер корректной реализации unified orchestration module.

## Workstreams

### WS-01 Core runtime import
- [x] Импортировать из `W:\server2` в модуль:
  - [x] `shared/code-factory-process.md`
  - [x] `scripts/code-factory/factory_ctl.py`
  - [x] `scripts/code-factory/contract_validator.py`
  - [x] `scripts/code-factory/code_factory_runner.py`
- [x] Проверить базовые зависимости скриптов (`py_compile`, `factory_ctl --help`, `init -> status`).
- [x] Убрать Linux hardcoded paths из imported runtime scripts (state path переведён на env/temp-based default).
- [x] Сделать runtime module-owned, а не reference-only.

### WS-02 Unified policy layer
- [x] `config/strictness_profiles.json`
- [x] `config/bucket_contracts.json`
- [x] `config/claim_state_machine.json`
- [x] `config/skills_registry.json`
- [x] `config/tech_debt.json`
- [ ] Формализовать guard degradation matrix and reason codes fully.

Статус: базовый machine-readable policy layer создан. Дальше нужна калибровка и привязка к plugin/runtime как source of truth.

### WS-03 Guard runtime
- [ ] Внедрить guard целиком.
- [ ] Прокинуть `DOC_GUARD_ENTRYPOINT` и `OPENCODE_SESSION_DB`.
- [ ] Проверить fail-closed hooks.

Статус: policy base усилен — добавлены `config/reason_codes.json`, guard/profile bindings и guard degradation matrix в `strictness_profiles.json`. Runtime wiring всё ещё не подключено.

### WS-04 Environment / portability
- [ ] Описать env contract для Windows/Linux.
- [ ] Нормализовать `OPENCODE_HARNESS_ROOT`, `OPENCODE_RUNS_DIR`, `.kanban.db`, state path.
- [ ] Заменить `/tmp/factory_state.json` и `/home/orangepi/...`.

### WS-04b Agent migration
 - [x] Перенести agents/shared в module-owned блок.
 - [x] Переписать pi-пути на env bindings.
 - [x] Синхронизировать agents/shared/scripts в live.
 - [x] Добавить RESEARCH_* vars в runtime policy.
 - [ ] Задать env vars в runtime перед live-запуском.

### WS-05 MCP perimeter
- [ ] Классифицировать MCP servers: core/optional/reference.
- [ ] Подготовить live config templates.
- [ ] Smoke-test каждый MCP standalone.

### WS-06 Skills module layer
- [ ] Построить реестр skills из `W:\server2\skills` (184 modules).
- [ ] Разбить на `core|optional|reference`.
- [ ] Связать skills с tools/MCP/routes.
- [ ] Не рекламировать весь skill corpus до нормализации registry.

Статус: server corpus уже собран в module-owned `skills/server2-corpus/` (184 skills). Следующий шаг — нормализация registry и capsule bindings.

### WS-07 Memory subsystem — строится ПОСЛЕ audit_graph (тем же капсульным способом)
 - [x] Собрать memory capsule на базе audit_graph, а не отдельно от него.
 - [x] L1 текучая / L2 под задачу / L3 глобальная — все триггеры привязаны к claim graph.
 - [x] Machine-readable lesson schema + policy gates для L2->L3 промоции.
 - [x] Создать deterministic scripts: scripts/memory/collect_l2.py, scripts/memory/promote_l2_to_l3.py.
 - [x] Подключить live OpenCode memory add/search к L3 registry (через детерминированный `scripts/memory/memory_bridge.py`, подключён 2026-09-01; L3 реестр — `config/memory_registry.json`; канал работает из HARNESS и LIVE-зеркала).

### WS-08 Unified architecture
 - [x] Собрать базовый audit_graph модуль на основе `malina_research_service_fixture.yaml` + R0.
 - [x] Добавить per-agent capsule категории `config/agent_categories/{code,research,writer,auditor,general}.json`.
 - [ ] Увязать Claim->Bucket->ExecutionCell->Audit->Snapshot с researcher-core terminology полностью.
 - [ ] Устранить duplication между docs/JSON/plugin constants.

### WS-11 Audit Graph Module
 - [x] Создать audit_graph каркас (domain/application/ports/infrastructure).
 - [x] Добавить module-owned snapshot schema/template: udit_graph/config/audit_graph_schema.json, 	ask_audit_template.json.
 - [x] Зафиксировать per-agent категории как капсулы (5 group + 15 per-agent JSON).
 - [x] Сделать модуль импортируемым: py_compile + import audit_graph + ClaimRegistry ok.
 - [ ] Доделать richer entities/projections/graph edges/gaps/conflicts до уровня researcher fixture.
 - [ ] Доделать sqlite persistence/runbook и first fixture replay.
 - Следующий шаг: память (WS-07) строится только на этой базе тем же капсульным способом.


### WS-15 Runtime Integration
 - [x] Описать runtime integration capsule architecture.
 - [x] Добавить config/runtime_integration_policy.json, config/opencode_plugin_config.json, config/mcp_lifecycle_config.json, config/path_resolution_map.json.
 - [x] Создать deterministic scripts: register_plugin.py, start_mcp_servers.py, validate_env.py, fix_paths.py, health_check.py.
 - [x] Интегрировать runtime-integration в capsule_registry/hierarchy как active.
 - [ ] Запуск live integration: plugin registration, MCP startup, env validation, path fixing.

### WS-14 MCP capsule
 - [x] Описать MCP capsule architecture.
 - [x] Добавить config/mcp_registry.json, config/mcp_capsule_policy.json, config/mcp_graph.json.
 - [x] Создать deterministic resolver scripts/router/resolve_mcp_capsule.py.
 - [x] Интегрировать mcp capsule в capsule_registry/hierarchy как active.

### WS-13 Tool capsule
 - [x] Описать tool capsule architecture.
 - [x] Добавить config/tool_families.json, config/tool_capsule_policy.json, config/tool_graph.json.
 - [x] Создать deterministic resolver scripts/router/resolve_tool_capsule.py.
 - [ ] Интегрировать 	ool capsule в capsule_registry/hierarchy как active.
 - [ ] Добавить richer tool contracts/anti-contracts.

### WS-15 Runtime Integration
 - [x] Описать runtime integration capsule architecture.
 - [x] Добавить config/runtime_integration_policy.json, config/opencode_plugin_config.json, config/mcp_lifecycle_config.json, config/path_resolution_map.json.
 - [x] Создать deterministic scripts: register_plugin.py, start_mcp_servers.py, validate_env.py, fix_paths.py, health_check.py.
 - [x] Интегрировать runtime-integration в capsule_registry/hierarchy как active.
 - [ ] Запуск live integration: plugin registration, MCP startup, env validation, path fixing.

### WS-14 MCP capsule
 - [x] Описать MCP capsule architecture.
 - [x] Добавить config/mcp_registry.json, config/mcp_capsule_policy.json, config/mcp_graph.json.
 - [x] Создать deterministic resolver scripts/router/resolve_mcp_capsule.py.
 - [x] Интегрировать mcp capsule в capsule_registry/hierarchy как active.

### WS-13 Tool capsule
 - [x] Описать tool capsule architecture.
 - [x] Добавить config/tool_families.json, config/tool_capsule_policy.json, config/tool_graph.json.
 - [x] Создать deterministic resolver scripts/router/resolve_tool_capsule.py.
 - [ ] Интегрировать 	ool capsule в capsule_registry/hierarchy как active.
 - [ ] Добавить richer tool contracts/anti-contracts.

### WS-12 Capsule hierarchy
 - [x] Описать иерархическую капсульную архитектуру.
 - [x] Добавить config/capsule_registry.json и config/capsule_route_hierarchy.json.
 - [x] Добавить deterministic resolver scripts/router/resolve_capsules.py.
 - [ ] Подключить будущие tool capsule и mcp capsule к этому же иерархическому слою.

### WS-10 Router core
 - [x] Описать router core architecture.
 - [x] Добавить base configs: `profile_routes.json`, `route_resolution_policy.json`, `execution_modes.json`.
 - [x] Создать deterministic resolver script: `scripts/router/resolve_route.py`.
 - [x] Добавить skill routing graph builder: `scripts/router/build_skill_graph.py` -> `config/skills_graph.json`.
 - [x] Добавить claim kind taxonomy: `config/claim_kinds.json` + `config/claim_bucket_rules.json`.
 - [x] Добавить claim splitter + grouped execution plan: `scripts/router/split_claims.py` + `scripts/router/build_task_plan.py`.
 - [ ] Привязать plugin/runtime к router configs как source of truth.

Статус: router core base создан; graph-backed route plan и grouped claim/bucket plan проходят dry-run.

## Current blockers before continuing major development

- [x] WS-01 closed at module level: runtime core imported into `shared/` and `scripts/code-factory/`.
- [ ] WS-02 partially done: base registries exist, but guard matrix/reason-code calibration and runtime wiring are still missing.
- [ ] WS-03 not done: guard mandatory semantics are defined, but deployment matrix is not.
- [ ] WS-06 not done: 184 server skills are not yet normalized into a runtime registry.

### WS-09 Live OpenCode integration
- [ ] Подготовить plugin registration plan.
- [ ] Подготовить `mcp` section templates.
- [ ] Проверить `Tab -> code-orchestrator` и соседние primary agents.

## Rule

Любая новая идея должна попадать либо в policy/config, либо в runtime script, либо в skill/tool template, либо в debt item, либо в tracker workstream.
