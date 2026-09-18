# Harness Glossary — что реализовано и как называется в коде

Дата: 2026-09-17. Назначение: единая карта «контур → функция → сигнатура → назначение → как вызвать»,
чтобы развивать функционал, не переписывая его. См. IMPLEMENTATION_STATUS.md (статусы) и README_DEVELOPER.md.

## ROUTER

### resolve
- **Сигнатура:** `resolve(task_text: str, hints: dict|None=None) -> dict`
- **Назначение:** Детерминированная маршрутизация: task -> route_id/bucket. hints: route_id/preferred_profile.

### match_routes
- **Сигнатура:** `match_routes(task_text: str, routes: dict) -> list[(route_id, route, match_len)]`
- **Назначение:** Сопоставление task с regex-паттернами всех маршрутов.

## RESEARCHER

### TribunalCompositionPlan
- **Сигнатура:** `compile_tribunal_composition(...)`
- **Назначение:** План состава трибунала из ReviewWorkField.

### AssessmentAssignment
- **Сигнатура:** `AssessmentAssignment(need_ref, role_ids, reasons)`
- **Назначение:** Назначение специалистов на AssessmentNeed.

### TribunalEvidenceSlice
- **Сигнатура:** `compile_evidence_slice(...)`
- **Назначение:** Детерминированный срез evidence по роли.

### compile_role_instruction_pack
- **Сигнатура:** `compile_role_instruction_pack(role_id, variant, handbook, policy) -> RoleInstructionPack`
- **Назначение:** Инструкция роли из handbook.

### decide_dialectic_control
- **Сигнатура:** `decide_dialectic_control(observation, policy) -> DialecticControlDecision`
- **Назначение:** Решение о продолжении/остановке диалектики (Q1A1..Q3A3, лимиты, новизна).

### compile_execution_envelope
- **Сигнатура:** `compile_execution_envelope(binding, disclosure, question_contract, ...) -> TribunalExecutionEnvelope`
- **Назначение:** Envelope с bounds для семантического исполнителя.

### execute_question
- **Сигнатура:** `execute_question(parent_state_path, binding, envelope, transport, ...) -> (InquiryTurn, Receipt)`
- **Назначение:** Выполнение Q через провайдер-транспорт.

### execute_answer
- **Сигнатура:** `execute_answer(...) -> (ArgumentArtifact, Receipt)`
- **Назначение:** Выполнение A1.

### verify_claim
- **Сигнатура:** `verify_claim(claim, source_text, policy) -> dict`
- **Назначение:** Верификация claim против источника.

### run_pipeline
- **Сигнатура:** `run_pipeline(query, out_dir, max_extract=2) -> dict`
- **Назначение:** Детерминированный пайплайн: search 3ch -> relevance -> extract -> verdict.

## WRITER

### wc_cli extract
- **Сигнатура:** `wc_cli extract --doc --out`
- **Назначение:** Гибридная экстракция (claims/objects/digest/links).

### wc_cli dom
- **Сигнатура:** `wc_cli dom --template --plan --claims --graphs --out`
- **Назначение:** DOM нового документа из plan+claims+graphs.

### wc_cli uncertainty
- **Сигнатура:** `wc_cli uncertainty --dom --out`
- **Назначение:** Долг неопределённости (PROVISIONAL + research_requests).

### wc_cli register
- **Сигнатура:** `wc_cli register --draft`
- **Назначение:** Контроль регистра: R1 референс/R2 вектор/R3 лексика/R4 тропы.

### wc_cli draftcheck
- **Сигнатура:** `wc_cli draftcheck --draft --contract`
- **Назначение:** RTT-дифф черновика против контракта.

## PLUGIN

### resolve_transport
- **Сигнатура:** `resolve_transport(explicit: str|None=None) -> 'plugin'|'cli'|'auto'`
- **Назначение:** Выбор транспорта semantic execution.

### execute_coder_semantic
- **Сигнатура:** `execute_coder_semantic(request) -> SemanticExecutionResult/1.0`
- **Назначение:** Coder semantic transport через plugin bridge (fail-closed).

### _execute_via_plugin_bridge
- **Сигнатура:** `_execute_via_plugin_bridge(request, timeout_s=30) -> dict`
- **Назначение:** Реальный reverse-вызов через bridge peer (plugin-side consumer).

### bridge_peer.harness.run
- **Сигнатура:** `harness.run {task, route?, profile?} -> route/bundle`
- **Назначение:** Детерминированный роутинг через bridge (task обязателен, иначе BAD_REQUEST).

## Полный список функций по контурам (автосбор)

- `router`: 15 публичных функций (файлы: scripts/router/resolve_bundle.py, scripts/router/resolve_route.py и др.)
- `researcher-tribunal`: 131 публичных функций (файлы: scripts/researcher/researcher_core/tribunal_argument_graph.py, scripts/researcher/researcher_core/tribunal_composition.py, scripts/researcher/researcher_core/tribunal_dialectic.py и др.)
- `researcher-verify`: 8 публичных функций (файлы: scripts/researcher/verify_claims.py и др.)
- `researcher-pipeline`: 5 публичных функций (файлы: scripts/researcher/run_pipeline.py и др.)
- `writer`: 24 публичных функций (файлы: scripts/writer-core/writer_core/cli.py, scripts/writer-core/writer_core/uncertainty_bridge.py и др.)
- `plugin`: 45 публичных функций (файлы: packages/opencode-harness-plugin/core/bridge_peer.py, scripts/code-factory/semantic_transport.py и др.)

## Правила именования
- `resolve*` / `compile*` / `execute*` / `decide*` / `verify*` / `run_*` — детерминированные операции.
- `_private` — внутренние хелперы, не для внешнего вызова (кроме отмеченных в KEY).
- `cmd_*` (writer-core/cli.py) — subcommand'ы CLI `wc_cli`.
- TS-плагин: `harness_status` / `harness_run` (tools), bridge `harness-bridge-rpc/1.0`.
