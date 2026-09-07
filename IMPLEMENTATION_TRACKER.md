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
- [x] **`run_research.sh` помечен Linux-only (2026-09-06):** hardcoded `/home/orangepi/*` + bash-зависимости — на Windows НЕ запускать, не чинить, не переносить. Для Windows использовать python-контур (numeric_comparator.py, synthesizer.py, judge_brief.py) + пути из `path_resolution_map.json`. Файл оставлен как Linux-артефакт для Pi, `RESEARCH_RUNNER_SH` на Windows неактивен.
- [x] **`mcp/doc_extract_server.py` деактивирован (2026-09-06):** `auto_start: false` в `mcp_lifecycle_config.json`. Причина: пакеты pypdfium2/docx/markdownify/openpyxl не установлены, ядро фабрики не зависит. Включить после `pip install -r requirements-mcp-doc.txt` в `.venv` + вернуть `auto_start: true`. Код и requirements оставлены.

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

### WS-16 Repatriation: утраченные артефакты с диска W (когда W будет доступен)

Дыры, найденные ревью связности (2026-09-06). Диск W (`W:\server2`) сейчас **не подключён** — перенести, когда появится.

- [ ] Перенести `agents/security-auditor.md` (ссылка из `shared/orchestration-patterns.md` → `agents/security-auditor.md`, файл отсутствует).
- [ ] Перенести `agents/test-engineer.md` (ссылка из `shared/orchestration-patterns.md` → `agents/test-engineer.md`, файл отсутствует).
- [ ] Сверить `shared/code-factory-process.md` с `W:\server2\shared\code-factory-process.md` (текущая ссылка на этот архивный путь; актуализировать API/пути под HARNESS).
- [ ] Проверить прочие битые ссылки на `W:\server2\*` по всему HARNESS (rg-скан agents/shared/scripts) и восстановить отсутствующие.
- [ ] Research-исполнительный слой (если найден на W/Z/claimeai-service): `numeric_comparator.py` требует `units.py`, `uncertainty.py`, `formulas.py`; конвейер `run_research.sh` требует `verdict_schemas.py`, `cascade.py`, `circularity.py`, `content_verdict.py`, `factcheck_guard.py`, `merge_numeric.py`, `evidence_contract.py`, `post_processor.py`, `justification_check.py`, `escalation.py` — ВСЕ отсутствуют в HARNESS.
- [ ] После переноса: перезапустить audit-скан `.md`-ссылок (agents/shared) + `health_check.py` + smoke-запуск `resolve_route.py`/`project_context.py`.

Блокировано: диск `W:` не подключён (проверка: `Test-Path W:\server2`).

### WS-17 Researcher-core вертикаль (Default Project → HARNESS)

Источник вектора: `E:\барахло\Documents\Default Project\16-development-vector.md` (аудит researcher-core, 360 тестов OK). Ядро R0–R3 зрелое, но не вызывается реальным исследованием.

- [ ] **P1 Strangler**: реализовать `HermesLegacyAdapter` (CLI-контракт: input schema, output schema, timeout, audit) поверх `research-orchestrator` + legacy scripts.
- [ ] **P1 HARNESS**: запитать HARNESS research-контур от `researcher_core` (units/uncertainty/formulas → numeric_comparator), закрыть WS-16 research-часть без диска W.
- [ ] **P2 legalize**: признать rule-based extraction reference (ADR); не возвращать LLM-claim-parser как обязательный.
- [ ] **P2 guard**: вынести `doc_guard` path из `guard.py` в config/env (порт); убрать Windows-hardcode.
- [ ] **P3 ResearchQueue**: + Gap/Conflict-driven targeted operations (Resolve A17, не «ищи по теме»).
- [ ] **P4 clean**: обновить `malina_research_service_fixture.yaml` до схемы 0.2 → artifact-check зелёный.
- [ ] **P4 clean**: причесать `runtime.py` (дубли-адаптеры, `rebuild_state_from_events`).
- [ ] **Критерий**: research-orchestrator доводит документ до WriterContext через runtime; artifact-check 0 high; HARNESS импортирует researcher_core.

### WS-18 Writer: прослеживаемость и неопределённость как первичная структура (DOM YAML)

Цель: научные/инженерные произведения (диссертация, монография, учебная литература) строятся на **прослеживаемости** (утверждение → цепочка цитат) и **неопределённости** (степень подтверждённости) — которые живут в DOM YAML, а не в прозе. Проза = выходной формат DOM.

- [x] **Контракт** `shared/writer-traceability-contract.md` — иерархия истины, формат DOM, рабочий цикл, гейт «нельзя выдать», интеграция с research (verdict/confidence/numeric_comparison). (2026-09-06)
- [x] **Шаблон** `templates/writer-dom-dissertation.yaml` — structure (главы/секции/параграфы), claims[], graphs[], uncertainty{}, sources[]. (2026-09-06)
- [x] **Интеграция в процессы** — `writing-orchestration-process.md` (Goal+DOM-блок), `article-writing-process.md` (ссылка), `writing-orchestrator.md` (Phase 3.5: создать DOM после brief, до research). (2026-09-06)
- [x] **Детерминированный цитатный аудит** `scripts/writer/citation_trace.py` — проверяет: каждое факт. утверждение → claim_id; каждый `[Sxx]` резолвится в sources; нет бесхозных/нерезолвленных ссылок; внутренние `[§N]` валидны; verdict=UNSUPPORTED не подан как факт. Использует дет-ядро декомпозиции (перенесено из writer-core legacy: `scripts/writer/extractor/`). (2026-09-06)
- [x] **Ядро декомпозиции перенесено в HARNESS** — `scripts/writer/extractor/` (clean stdlib, без pymupdf/pymorphy2/LLM): span_locate даёт абсолютные start/end, graph_builder — rel_pos + abs_span. (2026-09-06)
- [x] **Цикл черновиков** — `scripts/writer/draft_loop.py` (WS-18): декомпозиция абзаца (extractor) → матчинг с DOM (known/new, new → needs_source) → полнота параграфа → стилистический синтез по референс-работам (граф-сигнатуры). `--apply` заполняет paragraph.text, добавляет новые claims (temp id + needs_source), пишет draft_log. (2026-09-06)
- [x] **Гейт в оркестраторе** — Phase 5.5 + article-writer шаг 8: `citation_trace.py` перед handoff; не PASS → не выдавать. (2026-09-06)
- [x] **Модель-агностичность** — обвязка работает на любой модели (отладка на DeepSeek, прод на GPT 5/6): вся логика прослеживаемости в коде (citation_trace + extractor), не в промпте. Тесты: `tests/test_citation_trace.py` (8 кейсов PASS/FAIL). (2026-09-06)

### WS-19 Researcher Core в HARNESS + мост писатель↔ресерчер

Цель: заставить работать в паре писателя и ресерчера. Детерминированное ядро researcher_core переносится в HARNESS и питает верификацию claims писателя.

- [x] **Перенос пакета** `scripts/researcher/researcher_core/` (36 модулей, stdlib+PyYAML) из Default Project. (2026-09-06)
- [x] **Перенос policy** `config/research_policy.yaml` + **тесты** `tests/researcher/` (37 файлов). (2026-09-06)
- [x] **360/360 тестов OK** на изолированном .venv в HARNESS. (2026-09-06)
- [x] **Мосты research-скриптов**: `scripts/research/{units,uncertainty,formulas}.py` → researcher_core (чинит падение numeric_comparator.py на `ModuleNotFoundError`). Проверено: `numeric_comparator` импортируется и даёт MATCH на реальных данных. (2026-09-06)
- [x] **Мост писатель↔ресерчер** `scripts/researcher/verify_claims.py`: берёт writer DOM YAML (claims+evidence), прогоняет numeric/guard/formula/qualifier через researcher_core, возвращает verification (verdict/confidence/numeric_comparison) совместимо с DOM. `--apply` пишет verification в DOM. (2026-09-06)
- [x] **Нормализация единиц** (кириллица→латиница: МПа→mpa и т.д.) в verify_claims. (2026-09-06)
- [x] **Тесты** `tests/test_verify_claims.py` (6 кейсов: MATCH/CONTRADICTED/formula conflict/guard/no-source/apply). (2026-09-06)
- [ ] **Интеграция в процессы**: `writing-orchestration-process.md` + `article-writer.md` — шаг «verify claims через researcher_core» в цикле черновиков (после draft_loop, перед citation_trace).
- [ ] **Env**: `RESEARCH_CORE_ROOT`, `RESEARCH_VERIFY_CLAIMS` в setup_env.ps1/sh + validate_env.

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
