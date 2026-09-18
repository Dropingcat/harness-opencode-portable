# Harness Glossary — portable v1

Дата: 2026-09-18. Автосбор: scripts/glossary/gen_api_index.py + render_glossary.py.
«По принципу Python-библиотек»: контур → модуль → публичные функции/классы с сигнатурами.

## Полный список функций по контурам
- `code-factory`: 51 публичных функций (файлы: scripts/code-factory/code_factory_runner.py, scripts/code-factory/contract_validator.py, scripts/code-factory/factory_ctl.py и др.)
- `glossary`: 10 публичных функций (файлы: scripts/glossary/call_graph.py, scripts/glossary/compare_trees.py, scripts/glossary/gen_api_index.py и др.)
- `guard`: 17 публичных функций (файлы: guard/src/adversarial_build.py, guard/src/guard_runner.py, guard/src/semantic_layer.py и др.)
- `jobs`: 12 публичных функций (файлы: scripts/jobs/job_ctl.py)
- `mcp`: 32 публичных функций (файлы: mcp/academic_search_server.py, mcp/coder_router_server.py, mcp/doc_extract_server.py и др.)
- `orchestration`: 22 публичных функций (файлы: scripts/orchestration/character_sheet.py, scripts/orchestration/delegation_score.py, scripts/orchestration/idle_tasks.py и др.)
- `plugin`: 5 публичных функций (файлы: packages/opencode-harness-plugin/core/bridge_peer.py, packages/opencode-harness-plugin/core/doctor.py, packages/opencode-harness-plugin/core/install_plugin.py и др.)
- `researcher`: 224 публичных функций (файлы: scripts/researcher/researcher_core/__init__.py, scripts/researcher/researcher_core/artifact.py, scripts/researcher/researcher_core/artifact_builder.py и др.)
- `router`: 57 публичных функций (файлы: scripts/router/build_skill_graph.py, scripts/router/build_task_plan.py, scripts/router/capability_escalation.py и др.)
- `scripts`: 43 публичных функций (файлы: scripts/add_skill.py, scripts/fix_paths.py, scripts/health_check.py и др.)
- `writer-core`: 166 публичных функций (файлы: scripts/writer-core/consolidation.py, scripts/writer-core/corpus_runner.py, scripts/writer-core/digest_builder.py и др.)

## Code Factory

### `scripts/code-factory/code_factory_runner.py`

- `create_state(task_id: str, task_name: str, iteration_limit: int = DEFAULT_ITERATION_LIMIT, max_cost_rub: float = DEFAULT_MAX_COST_RUB, required_gates: list[str] | None = None) -> dict` — — [строка 52]
- `load_state(path: str) -> dict` — — [строка 66]
- `save_state(state: dict, path: str) -> str` — — [строка 75]
- `start(state: dict, path: str) -> str` — — [строка 89]
- `register_artifact(state: dict, file_path: str, path: str, *, origin: str, tool_id: str | None = None, source_ref: str | None = None, media_type: str | None = None, metadata: dict | None = None, artifact_id: str | None = None) -> str` — — [строка 95]
- `guard_artifact(state: dict, artifact_id: str, verdict: str, path: str, *, guard_id: str = 'manual_guard', findings: dict | None = None, guard_policy_hash: str | None = None) -> str` — — [строка 105]
- `sanitize_artifact(state: dict, source_artifact_id: str, sanitized_file: str, path: str, *, sanitizer_id: str = 'manual_sanitizer', artifact_id: str | None = None, notes: str | None = None) -> str` — — [строка 117]
- `submit_evidence(state: dict, agent_type: str, module: str, data: dict, path: str, *, output_file: str | None = None, artifact_refs: list[str] | None = None) -> str` — — [строка 144]
- `add_budget(state, steps, cost_rub, path)` — — [строка 173]
- `auditor_block(state, path)` — — [строка 174]
- `finalize(state, path)` — — [строка 175]
- `validate(state)` — — [строка 179]
- `replay(state)` — — [строка 190]
- `resume(state)` — — [строка 195]

### `scripts/code-factory/contract_validator.py`

- `validate_worker(data: dict) -> list[str]` — — [строка 27]
- `validate_reviewer(data: dict) -> list[str]` — — [строка 38]
- `validate_tester(data: dict) -> list[str]` — — [строка 81]
- `validate_auditor(data: dict) -> list[str]` — — [строка 98]
- `validate_experimenter(data: dict) -> list[str]` — — [строка 124]
- `validate(agent_type: str, data: dict) -> list[str]` — — [строка 155]
- `main() -> int` — — [строка 168]

### `scripts/code-factory/factory_ctl.py`

- `cmd_init(a)` — — [строка 20]
- `cmd_submit(a)` — — [строка 53]
- `cmd_artifact_register(a)` — — [строка 66]
- `cmd_artifact_guard(a)` — — [строка 72]
- `cmd_artifact_sanitize(a)` — — [строка 78]
- `cmd_budget(a)` — — [строка 84]
- `cmd_auditor_block(a)` — — [строка 86]
- `cmd_finalize(a)` — — [строка 88]
- `cmd_status(a)` — — [строка 91]
- `cmd_replay(a)` — — [строка 94]
- `main()` — — [строка 99]

### `scripts/code-factory/provenance.py`

- `canonical(obj: Any) -> str` — — [строка 19]
- `sha256_bytes(data: bytes) -> str` — — [строка 23]
- `sha256_file(path: str | Path) -> str` — — [строка 27]
- `sha256_json(obj: Any) -> str` — — [строка 36]
- `load_policy(path: str | Path | None = None) -> dict` — — [строка 40]
- `policy_hash(policy: dict | None = None) -> str` — — [строка 45]
- `origin_spec(origin: str, policy: dict | None = None) -> dict` — — [строка 49]
- `artifact_from_file(artifact_id: str, path: str | Path, *, origin: str, tool_id: str | None = None, source_ref: str | None = None, media_type: str | None = None, metadata: dict | None = None, source_artifact_id: str | None = None, policy: dict | None = None) -> dict` — — [строка 57]
- `artifact_admissibility(record: dict, guards: list[dict], policy: dict | None = None) -> tuple[bool, str]` — — [строка 81]
- `verify_artifact_file(record: dict, path: str | Path | None = None) -> tuple[bool, str]` — — [строка 96]

### `scripts/code-factory/semantic_transport.py`

- `classify_purpose(purpose: str) -> str` — Map a Coder purpose to its default permission_profile. [строка 127]
- `resolve_transport(*, explicit: str | None = None) -> str` — Resolve the transport to use (M3a explicit transport selection). [строка 312]
- `execute_coder_semantic(request: dict, *, transport: str | None = None, plugin_side: object | None = None) -> dict` — Execute (transport) a SemanticExecutionRequest/1.0 for the Coder agent. [строка 619]
- `build_coder_request(*, execution_id: str, purpose: str, bounded_input: dict, expected_output: dict, worktree: str, timeout_ms: int = 180000, model_policy: dict | None = None) -> dict` — Build a valid SemanticExecutionRequest/1.0 dict for the Coder agent. [строка 690]

### `scripts/code-factory/state_reducer.py`

- `canonical(obj: Any) -> str` — — [строка 31]
- `event_hash(event_without_hash: dict) -> str` — — [строка 35]
- `load_policy(path: str | Path | None = None) -> dict` — — [строка 39]
- `verify_event_chain(events: list[dict]) -> list[str]` — — [строка 44]
- `reduce_events(events: list[dict], policy: dict | None = None) -> dict` — — [строка 159]

## Glossary

### `scripts/glossary/call_graph.py`

- `scan_call_graph(root: str | Path, include_tests: bool = False) -> dict[str, Any]` — Return {nodes: {qname: {...}}, edges: [{src, dst, confidence}]}. [строка 92]

### `scripts/glossary/compare_trees.py`

- `load_index(path: str | Path) -> dict[str, Any]` — Read a function_index.json registry (utf-8). [строка 29]
- `compute_delta(base_index: dict[str, Any], target_index: dict[str, Any]) -> dict[str, Any]` — Compute per-contour module/function deltas between two registries. [строка 78]
- `render_delta(delta: dict[str, Any]) -> str` — Render the delta dict as the PORTABLE_DELTA.md markdown document. [строка 161]
- `main(argv: list[str] | None = None) -> int` — — [строка 220]

### `scripts/glossary/gen_api_index.py`

- `scan_tree(root: str | Path, label: str = 'workspace', include_tests: bool = False) -> dict` — Scan the tree and return the registry dict (see module docstring for the schema). [строка 298]
- `main(argv: list[str] | None = None) -> int` — — [строка 367]

### `scripts/glossary/render_glossary.py`

- `render_glossary(index: dict[str, Any], label: str) -> str` — Render the full GLOSSARY.md document for a registry and label. [строка 75]
- `main(argv: list[str] | None = None) -> int` — — [строка 130]

### `scripts/glossary/stub_detect.py`

- `scan_stubs(root: str | Path, include_tests: bool = False) -> dict[str, Any]` — — [строка 127]

## Guard

### `guard/src/adversarial_build.py`

- `make_db(name, parts)` — parts: list of (session_id, part_type, tool, output). [строка 20]
- `run(db)` — — [строка 41]

### `guard/src/guard_runner.py`

- `harness_root() -> Path` — — [строка 43]
- `p0_path() -> Path` — — [строка 47]
- `p2_path() -> Path` — — [строка 54]
- `default_config() -> Path` — — [строка 58]
- `run_p0(db: str, session: str | None) -> dict` — — [строка 65]
- `run_p2(db: str, provider: str, session: str | None, config: str | None) -> dict` — — [строка 79]
- `guard(db: str, provider: str = 'cloud', session: str | None = None, config: str | None = None) -> dict` — Run P0 then P2; compose verdict. Fail-closed. [строка 107]
- `main() -> int` — — [строка 133]

### `guard/src/semantic_layer.py`

- `load_config(path)` — Загружает JSON-конфиг из `path`. Возвращает dict. [строка 67]
- `analyze(db_path, session_id = None, provider = 'cloud', model = None, limit = 50, budget = None, config = None, api_key = None)` — Гибридный P0+P2 анализ. Возвращает dict-результат. [строка 524]
- `human_report(result)` — Человекочитаемый вывод. [строка 710]
- `main()` — — [строка 762]
- `ConfigError(Exception)` — Конфиг не загружен (graceful, без traceback). [строка 63]
- `LocalClassifier()` — ollama qwen2.5:0.5b, temperature=0 seed=42. Бесплатный (cost=0). [строка 175]
  - `classify(self, text)` — Один вызов. Возвращает (verdict, cost_rub). verdict: YES|NO|None.
- `CloudClassifier()` — OpenAI-compatible cloud (polza). cost_rub из usage.cost_rub. [строка 208]
  - `classify(self, text)` — Один вызов. Возвращает (verdict, cost_rub).
- `Budget()` — Счётчик стоимости cloud-вызовов с порогами warn/max. [строка 277]
  - `add(self, cost)` — Учесть cost вызова.
  - `remaining(self)` — —
  - `exhausted(self)` — —
  - `to_dict(self)` — —
- `ClassifierChain()` — Очередь провайдеров для P2-вызовов с учётом бюджета. [строка 329]
  - `run(self, text)` — Классифицирует text по цепочке. Возвращает dict:

### `guard/src/session_guard.py`

- `analyze(db_path, session_id = None)` — Возвращает dict-результат анализа. [строка 336]
- `human_report(result)` — Человекочитаемый вывод. [строка 461]
- `main()` — — [строка 490]
- `OpenDBError(Exception)` — Не удалось открыть/прочитать файл БД (graceful, без traceback). [строка 332]

## Jobs

### `scripts/jobs/job_ctl.py`

- `now()` — — [строка 10]
- `sha(obj)` — — [строка 11]
- `atomic_write(path: Path, obj)` — — [строка 12]
- `load(p)` — — [строка 19]
- `save(s, p)` — — [строка 20]
- `event(s, typ, payload)` — — [строка 21]
- `contract_hash(contract)` — — [строка 24]
- `attempt_by(s, aid)` — — [строка 25]
- `child_by(s, cid)` — — [строка 29]
- `create(job_id, contract, stages)` — — [строка 34]
- `reconcile(s)` — — [строка 39]
- `main()` — — [строка 47]

## MCP

### `mcp/academic_search_server.py`

- `list_tools() -> list[Tool]` — — [строка 95]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 125]
- `main()` — — [строка 147]

### `mcp/coder_router_server.py`

- `handle_coder_run(arguments: dict[str, Any]) -> list[TextContent]` — — [строка 111]
- `list_tools() -> list[Tool]` — — [строка 213]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 236]
- `main() -> None` — — [строка 244]

### `mcp/doc_extract_server.py`

- `list_tools() -> list[Tool]` — — [строка 144]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 162]
- `main()` — — [строка 179]

### `mcp/launchers/_runner.py`

- `run_with_contract(launcher_name: str, task: str, contract: str, model: str = 'ollama-cloud/glm-5.2', timeout: int = 300, read_only_paths: list[str] | None = None) -> dict[str, Any]` — Run opencode run --pure with a contract prompt in an isolated run directory. [строка 23]

### `mcp/launchers/opencode_code_worker.py`

- `list_tools() -> list[Tool]` — — [строка 54]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 73]
- `main()` — — [строка 89]

### `mcp/launchers/opencode_profile_configurator.py`

- `list_tools() -> list[Tool]` — — [строка 61]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 80]
- `main()` — — [строка 96]

### `mcp/launchers/opencode_research_academic.py`

- `list_tools() -> list[Tool]` — — [строка 57]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 76]
- `main()` — — [строка 92]

### `mcp/launchers/opencode_research_web.py`

- `list_tools() -> list[Tool]` — — [строка 53]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 72]
- `main()` — — [строка 85]

### `mcp/launchers/opencode_service_task.py`

- `list_tools() -> list[Tool]` — — [строка 61]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 80]
- `main()` — — [строка 96]

### `mcp/launchers/opencode_tribunal_role.py`

- `list_tools() -> list[Tool]` — — [строка 48]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 65]
- `main() -> None` — — [строка 83]

### `mcp/searxng_search_server.py`

- `list_tools() -> list[Tool]` — — [строка 47]
- `call_tool(name: str, arguments: Any) -> list[TextContent]` — — [строка 71]
- `main()` — — [строка 92]

## Orchestration

### `scripts/orchestration/character_sheet.py`

- `build(root: Path) -> dict` — — [строка 68]
- `to_markdown(cs: dict) -> str` — — [строка 208]
- `main() -> int` — — [строка 227]

### `scripts/orchestration/delegation_score.py`

- `cmd_record(args: argparse.Namespace) -> int` — — [строка 82]
- `cmd_board(args: argparse.Namespace) -> int` — — [строка 119]
- `cmd_stats(args: argparse.Namespace) -> int` — — [строка 141]
- `cmd_reset(args: argparse.Namespace) -> int` — — [строка 169]
- `main() -> int` — — [строка 177]

### `scripts/orchestration/idle_tasks.py`

- `build(root: Path) -> dict` — — [строка 48]
- `to_markdown(d: dict) -> str` — — [строка 169]
- `main() -> int` — — [строка 181]

### `scripts/orchestration/kanban_report.py`

- `register_agent(agent_id: str, db_path: str = DB_PATH) -> None` — — [строка 88]
- `report(agent_id: str, task_id: Optional[str] = None, task_name: str = '', status: str = 'WORKING', phase: Optional[str] = None, progress: str = '', message: str = '', db_path: str = DB_PATH) -> int` — Опубликовать статус агента в глобальный канбан (с резолвом секции). [строка 105]
- `board(group_name: Optional[str] = None, agent_id: Optional[str] = None, limit: int = 20, db_path: str = DB_PATH) -> list[dict]` — Доска с секциями: JOIN agents -> group_name; фильтр по группе/агенту. [строка 130]
- `summary(groups: Optional[list[str]] = None, db_path: str = DB_PATH) -> str` — Сводка по секциям (group_name) — разведённые секции канбана. [строка 151]

### `scripts/orchestration/project_context.py`

- `board(kb: Path, limit: int = 8)` — — [строка 13]
- `tech_debt(root: Path)` — — [строка 40]
- `tracker(root: Path)` — Извлекает открытые задачи из IMPLEMENTATION_TRACKER.md (checkbox - [ ]). [строка 53]
- `memory_lessons(root: Path, limit: int = 5)` — — [строка 75]
- `factory_state(root: Path)` — — [строка 92]
- `portal_refs(root: Path)` — — [строка 104]
- `main()` — — [строка 109]

## Plugin

### `packages/opencode-harness-plugin/core/bridge_peer.py`

- `main() -> int` — — [строка 260]
- `BridgeServer()` — — [строка 51]
  - `serve(self) -> None` — —

### `packages/opencode-harness-plugin/core/doctor.py`

- `harness_root() -> Path` — — [строка 14]
- `main() -> int` — — [строка 21]

### `packages/opencode-harness-plugin/core/install_plugin.py`

- `harness_root() -> Path` — — [строка 19]
- `main() -> int` — — [строка 48]

## Researcher

### `scripts/researcher/researcher_core/__init__.py`


### `scripts/researcher/researcher_core/artifact.py`

- `check_artifact_dict(data: Any) -> list[ArtifactFinding]` — — [строка 52]
- `check_artifact_text(text: str) -> list[ArtifactFinding]` — — [строка 124]
- `build_report(path: Path, findings: Sequence[ArtifactFinding]) -> dict` — — [строка 149]
- `main(argv: Sequence[str] | None = None) -> int` — — [строка 163]
- `ArtifactFinding()` — — [строка 44]

### `scripts/researcher/researcher_core/artifact_builder.py`

- `build_minimal_service_artifact(snapshot: Snapshot, state: Mapping[str, Claim | Quantity | Source | EvidenceSpan | GraphEdge], title: str, policy: Any | None = None, relation_assessments: tuple[RelationAssessment, ...] = (), uncertainty_profiles: tuple[UncertaintyProfile, ...] = (), review_work_fields: tuple[ReviewWorkField, ...] = ()) -> dict[str, Any]` — — [строка 24]
- `render_artifact_yaml(artifact: Mapping[str, Any]) -> str` — Prod YAML renderer via ``yaml.safe_dump`` — handles all escaping and unicode. [строка 196]
- `write_artifact_atomic(path: Path, artifact: Mapping[str, Any]) -> None` — Atomic write: temp file + fsync + rename, as in legacy writer_server. [строка 202]
- `render_minimal_yaml(value: Any, indent: int = 0) -> str` — Small YAML renderer for generated dependency-free fixtures. [строка 224]

### `scripts/researcher/researcher_core/budget.py`

- `TokenBudget()` — — [строка 22]
  - `from_policy(cls, policy: Policy) -> TokenBudget` — —
- `BudgetExhausted(RuntimeError)` — Raised when a hop/node/token budget would be exceeded. [строка 41]
- `TokenMeter()` — — [строка 46]
  - `check_hop(self) -> None` — —
  - `check_node(self, additional: int = 1) -> None` — —
  - `check_tokens(self, additional: int) -> None` — —
  - `add_hop(self) -> None` — —
  - `add_nodes(self, count: int) -> None` — —
  - `add_tokens(self, count: int) -> None` — —
  - `remaining_tokens(self) -> int` — —
  - `is_exhausted(self) -> bool` — —

### `scripts/researcher/researcher_core/capsules.py`

- `assert_capsule_observation_is_untrusted(observation: CapsuleObservation) -> None` — Marker gate: capsule output is observation/proposal only, never state. [строка 120]
- `SideEffectClass(str, Enum)` — — [строка 19]
- `CapsuleDescriptor()` — — [строка 26]
- `CapsuleRequest()` — — [строка 51]
- `CapsuleObservation()` — — [строка 69]
- `Capsule(Protocol)` — — [строка 92]
  - `run(self, request: CapsuleRequest) -> CapsuleObservation` — —
- `InMemoryCapabilityRegistry()` — Deterministic provider selection for bubble tests and early adapters. [строка 98]
  - `register(self, capsule: Capsule) -> None` — —
  - `provider_for(self, capability: str) -> Capsule` — —
  - `capabilities(self) -> Mapping[str, str]` — —

### `scripts/researcher/researcher_core/challenge_planning.py`

- `expand_challenge_with_decomposition(*, dom: ResearchDOM, session: DecompositionSession, proposals: Sequence[ResearchCardProposal], id_factory: EntityIdFactory, actor: ActorRef, timestamp, causation_id: EntityId, correlation_id: EntityId, challenge: ResearchChallenge | None = None) -> ChallengePlanningResult` — Compile and atomically activate one local CHALLENGE decomposition. [строка 54]
- `ChallengePlanningError(ValueError)` — — [строка 39]
- `ChallengePlanningResult()` — — [строка 44]

### `scripts/researcher/researcher_core/challenge_resolution.py`

- `reconcile_challenge_resolution(*, dom: ResearchDOM, challenge: ResearchChallenge, source_entity: Gap | Conflict, assessment: ChallengeResolutionAssessment, challenge_card_id: EntityId, patch_id: EntityId, actor: ActorRef, id_factory: EntityIdFactory, timestamp, causation_id: EntityId, correlation_id: EntityId) -> ChallengeResolutionResult` — Project a typed assessment onto knowledge, challenge and ResearchDOM. [строка 102]
- `challenge_resolution_to_dict(value: ChallengeResolutionAssessment) -> dict[str, Any]` — — [строка 261]
- `challenge_resolution_from_dict(raw: Mapping[str, Any]) -> ChallengeResolutionAssessment` — — [строка 288]
- `ResolutionOutcome(StrEnum)` — — [строка 36]
- `ConflictResolutionMode(StrEnum)` — — [строка 43]
- `ChallengeResolutionAssessment()` — — [строка 52]
- `ChallengeResolutionResult()` — — [строка 89]
- `ChallengeResolutionError(ValueError)` — — [строка 98]
- `ChallengeResolutionRepository()` — — [строка 314]
  - `save(self, assessment: ChallengeResolutionAssessment) -> None` — —
  - `load(self, assessment_id: EntityId) -> ChallengeResolutionAssessment | None` — —

### `scripts/researcher/researcher_core/debt.py`

- `iter_files(root: Path, suffixes: set[str] | None = None, excluded_files: frozenset[str] | None = None, excluded_dirs: frozenset[str] | None = None) -> Iterable[Path]` — — [строка 51]
- `scan_python_numbers(path: Path, text: str, root: Path) -> list[DebtFinding]` — — [строка 75]
- `scan_text(path: Path, text: str, root: Path) -> list[DebtFinding]` — — [строка 115]
- `scan_paths(paths: Sequence[Path], root: Path) -> list[DebtFinding]` — — [строка 145]
- `build_report(root: Path, findings: Sequence[DebtFinding]) -> dict` — — [строка 166]
- `main(argv: Sequence[str] | None = None) -> int` — — [строка 179]
- `DebtFinding()` — — [строка 42]

### `scripts/researcher/researcher_core/execution_admission.py`

- `compile_local_execution_admission(*, result: TaskExecutionResult, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> ExecutionAdmissionProposal` — Compile a successful structured CapsuleObservation into typed proposals. [строка 81]
- `compile_peer_execution_admission(*, result: TaskExecutionResult, batch: ProposalBatch, adapter_id: str, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, provenance: Mapping[str, Any] | None = None) -> ExecutionAdmissionProposal` — Compile explicit typed adapter output for a successful peer artifact. [строка 106]
- `preflight_execution_proposal(proposal: ExecutionAdmissionProposal) -> tuple[tuple[str, str, tuple[str, ...]], ...]` — Run deterministic admission-shape validators before the registry mutation boundary. [строка 131]
- `admit_execution_proposal(*, dom: ResearchDOM, proposal: ExecutionAdmissionProposal, registry: InMemoryClaimRegistry, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, causation_id: EntityId, correlation_id: EntityId) -> tuple[ExecutionAdmissionReceipt, CommandResult, tuple[ResearchTraceLink, ...]]` — Revision-check TASK lineage, admit via R0 registry, and project TASK provenance. [строка 157]
- `execution_admission_proposal_to_dict(proposal: ExecutionAdmissionProposal) -> dict[str, Any]` — — [строка 252]
- `execution_admission_receipt_to_dict(receipt: ExecutionAdmissionReceipt) -> dict[str, Any]` — — [строка 270]
- `ExecutionAdmissionError(ValueError)` — — [строка 27]
- `ExecutionAdmissionProposal()` — — [строка 32]
- `ExecutionAdmissionReceipt()` — — [строка 58]
- `ExecutionAdmissionAuditRepository()` — Audit projection for proposals/receipts; canonical KG remains in ClaimRegistry. [строка 281]
  - `save_proposal(self, proposal: ExecutionAdmissionProposal) -> None` — —
  - `save_receipt(self, receipt: ExecutionAdmissionReceipt) -> None` — —

### `scripts/researcher/researcher_core/execution_linking.py`

- `build_admission_identity_map(*, proposal: ExecutionAdmissionProposal, receipt: ExecutionAdmissionReceipt, registry: InMemoryClaimRegistry, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> AdmissionIdentityMap` — — [строка 104]
- `admit_semantic_relations(*, proposal: ExecutionAdmissionProposal, identity: AdmissionIdentityMap, relation_proposals: Sequence[SemanticRelationProposal], registry: InMemoryClaimRegistry, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, causation_id: EntityId, correlation_id: EntityId) -> tuple[SemanticLinkReceipt, CommandResult, tuple[ResearchTraceLink, ...]]` — — [строка 165]
- `admission_identity_map_to_dict(identity: AdmissionIdentityMap) -> dict[str, Any]` — — [строка 215]
- `semantic_relation_proposal_to_dict(proposal: SemanticRelationProposal) -> dict[str, Any]` — — [строка 225]
- `semantic_link_receipt_to_dict(receipt: SemanticLinkReceipt) -> dict[str, Any]` — — [строка 236]
- `ExecutionLinkingError(ValueError)` — — [строка 27]
- `EndpointRefKind(StrEnum)` — — [строка 31]
- `RelationEndpointRef()` — — [строка 37]
- `AdmissionIdentityMap()` — — [строка 47]
- `SemanticRelationProposal()` — — [строка 66]
- `SemanticLinkReceipt()` — — [строка 88]
- `ExecutionLinkingAuditRepository()` — Audit projection for R3.2 linking artifacts; GraphEdge authority remains ClaimRegistry. [строка 247]
  - `save_identity_map(self, identity: AdmissionIdentityMap) -> None` — —
  - `save_relation_proposals(self, proposals: Sequence[SemanticRelationProposal]) -> None` — —
  - `save_receipt(self, receipt: SemanticLinkReceipt) -> None` — —

### `scripts/researcher/researcher_core/formulas.py`

- `detect_formula(text: str) -> str | None` — — [строка 34]
- `check_constant(formula_name: str, text: str) -> str` — — [строка 43]
- `list_formulas() -> tuple[str, ...]` — — [строка 55]
- `FormulaMarker()` — — [строка 20]

### `scripts/researcher/researcher_core/guard.py`

- `scan_text(text: str, field: str = 'text', provenance: str = 'untrusted', tool: str = 'webfetch') -> GuardReport` — Scan a single text value for injection signatures (P0 only). [строка 141]
- `scan_state(state: Mapping[str, Any], provenance: str = 'untrusted', tool: str = 'webfetch') -> GuardReport` — Scan all string values in a state dict (e.g., EvidenceSpan exact_text). [строка 171]
- `scan_opencode_db(db_path: str | Path, session_id: str | None = None) -> GuardReport` — Scan opencode.db via doc_guard P0 analyze (if available). [строка 190]
- `is_safe_text(text: str, provenance: str = 'untrusted') -> bool` — Convenience: True if no high-suspicion injection. [строка 215]
- `scan_text_with_p2(text: str, field: str = 'text', provenance: str = 'untrusted', tool: str = 'webfetch', use_p2: bool = False, config_path: str | Path | None = None, budget_rub: float | None = None) -> GuardReport` — P0 + optional P2 (polza) — P2 is tie-breaker for untrusted low/no-match. [строка 221]
- `scan_opencode_db_with_p2(db_path: str | Path, session_id: str | None = None, use_p2: bool = False, config_path: str | Path | None = None) -> GuardReport` — Full DB scan: P0 via session_guard, optionally P2 via polza for untrusted low. [строка 323]
- `GuardFinding()` — — [строка 123]
- `GuardReport()` — — [строка 133]

### `scripts/researcher/researcher_core/harness.py`

- `compare_trace_event_types(audit_events: Sequence[AuditEvent], reference_event_types: Sequence[str]) -> set[str]` — Return reference event types missing from the audit trace. [строка 71]
- `AuditEvent()` — — [строка 18]
- `InvariantViolation()` — — [строка 32]
- `TraceAuditor()` — Passive sidecar-style observer over an immutable event trace. [строка 38]
  - `events(self) -> tuple[AuditEvent, ...]` — —
  - `record(self, event_type: str, correlation_id: str, payload: Mapping[str, Any] | None = None) -> 'TraceAuditor'` — —
  - `require_input_output_pairs(self, input_event: str = 'input', output_event: str = 'output') -> list[InvariantViolation]` — —

### `scripts/researcher/researcher_core/invalidation.py`

- `assess_dependency_impact(*, changed_entity_ids: Sequence[EntityId], dependencies: Sequence[KnowledgeDependency], target_resolution_id: EntityId | None, meta: EntityMeta, max_nodes: int = 128) -> DependencyImpactAssessment` — Bounded deterministic propagation across explicit dependency records. [строка 134]
- `reopen_from_impact(*, dom: ResearchDOM, challenge: ResearchChallenge, source_entity: Gap | Conflict, resolution: ChallengeResolutionAssessment, impact: DependencyImpactAssessment, challenge_card_id: EntityId, prior_iterations: Sequence[ChallengeIteration], patch_id: EntityId, actor: ActorRef, id_factory: EntityIdFactory, timestamp, causation_id: EntityId, correlation_id: EntityId) -> InvalidationResult` — Project only a critical complete impact into an existing historical branch. [строка 199]
- `dependency_to_dict(v: KnowledgeDependency) -> dict[str, Any]` — — [строка 250]
- `impact_to_dict(v: DependencyImpactAssessment) -> dict[str, Any]` — — [строка 254]
- `iteration_to_dict(v: ChallengeIteration) -> dict[str, Any]` — — [строка 258]
- `DependencyStrength(StrEnum)` — — [строка 29]
- `DependencyState(StrEnum)` — — [строка 35]
- `ImpactState(StrEnum)` — — [строка 40]
- `IterationState(StrEnum)` — — [строка 48]
- `KnowledgeDependency()` — — [строка 55]
- `DependencyImpactAssessment()` — — [строка 77]
- `ChallengeIteration()` — — [строка 99]
- `InvalidationResult()` — — [строка 121]
- `InvalidationError(ValueError)` — — [строка 130]
- `InvalidationRepository()` — — [строка 262]
  - `save(self, *values) -> None` — —
  - `iterations_for_challenge(self, challenge_id: EntityId) -> tuple[Mapping[str, Any], ...]` — —

### `scripts/researcher/researcher_core/knowledge_reconciliation.py`

- `challenge_from_gap(gap: Gap, request_id: EntityId, meta: EntityMeta, *, dimensions: Mapping[str, Any] | None = None) -> ResearchChallenge` — — [строка 99]
- `challenge_from_conflict(conflict: Conflict, request_id: EntityId, meta: EntityMeta, *, dimensions: Mapping[str, Any] | None = None) -> ResearchChallenge` — — [строка 125]
- `materialize_challenge_card(dom: ResearchDOM, challenge: ResearchChallenge, *, parent_card_id: EntityId, card_id: EntityId, patch_id: EntityId, actor: ActorRef, id_factory: EntityIdFactory, timestamp: datetime, causation_id: EntityId, correlation_id: EntityId) -> KnowledgeFeedbackResult` — Insert one historical CHALLENGE card and link it to knowledge entities. [строка 156]
- `build_research_knowledge_projection(links: Sequence[ResearchTraceLink]) -> ResearchKnowledgeProjection` — — [строка 267]
- `research_challenge_to_dict(challenge: ResearchChallenge) -> dict[str, Any]` — — [строка 279]
- `research_challenge_from_dict(raw: Mapping[str, Any]) -> ResearchChallenge` — — [строка 304]
- `ResearchChallengeKind(StrEnum)` — — [строка 38]
- `ResearchChallengeStatus(StrEnum)` — — [строка 43]
- `ResearchChallenge()` — A planning request created from an admitted knowledge problem. [строка 54]
- `KnowledgeFeedbackResult()` — — [строка 91]
- `ResearchKnowledgeProjection()` — — [строка 258]
- `ResearchChallengeRepository()` — — [строка 327]
  - `save(self, challenge: ResearchChallenge) -> None` — —
  - `load(self, challenge_id: EntityId) -> ResearchChallenge | None` — —

### `scripts/researcher/researcher_core/local_capsules.py`

- `observation_to_proposal_batch(observation: CapsuleObservation) -> ProposalBatch` — — [строка 131]
- `observation_to_source_evidence(observation: CapsuleObservation) -> tuple[tuple[Source, ...], tuple[EvidenceSpan, ...]]` — — [строка 141]
- `LocalTextClaimExtractionCapsule()` — Deterministic offline capsule that extracts one simple numeric claim. [строка 23]
  - `run(self, request: CapsuleRequest) -> CapsuleObservation` — —
- `LocalDocumentExtractionCapsule()` — Deterministic offline capsule that extracts a local document source and exact evidence span. [строка 80]
  - `run(self, request: CapsuleRequest) -> CapsuleObservation` — —

### `scripts/researcher/researcher_core/local_corpus.py`

- `LocalCorpusCapsule()` — — [строка 22]
  - `run(self, request: CapsuleRequest) -> CapsuleObservation` — —
  - `search(self, query: str, limit: int) -> tuple[dict[str, object], ...]` — —
  - `sources(self, topics: object, limit: int) -> tuple[dict[str, object], ...]` — —

### `scripts/researcher/researcher_core/model_routing.py`

- `ModelRouting()` — — [строка 33]
  - `from_policy(cls, policy: Policy) -> ModelRouting` — —
  - `is_no_agent(self, capability: str) -> bool` — —
  - `resolve(self, capability: str) -> str | None` — Return model_id or None for NoAgent. Uses tier if present, else fallback.
  - `resolve_with_fallback(self, capability: str, primary_failed: bool = False) -> str | None` — If primary_failed, always return fallback (or None if fallback is also NoAgent).
  - `should_use_no_agent_dynamic(self, capability: str, payload_chars: int, tokens_remaining: int) -> bool` — Dynamic heuristic: trivial payload or budget pressure → NoAgent where safe.

### `scripts/researcher/researcher_core/numeric.py`

- `normalize_unit(unit: str | None) -> str` — Normalize a unit through the default registry. [строка 217]
- `dimension(unit: str | None) -> str` — Return a unit dimension through the default registry. [строка 223]
- `convert(value: NumberLike, from_unit: str | None, to_unit: str | None) -> Decimal` — Convert a value through the default registry. [строка 229]
- `compare_numeric(claim: NumericValue, evidence: NumericValue, tolerance_relative: NumberLike = DEFAULT_RELATIVE_TOLERANCE, registry: UnitRegistry | None = None) -> NumericComparisonResult` — Compare claim and evidence values after unit normalization. [строка 235]
- `UnitConversionError(ValueError)` — Raised when units are unknown or have incompatible dimensions. [строка 47]
- `UnitDefinition()` — Linear or affine mapping from one canonical unit to a dimension base. [строка 52]
- `UnitRegistry()` — Small deterministic registry for units needed by the core chain. [строка 62]
  - `normalize_unit(self, unit: str | None) -> str` — Return the canonical unit name, treating a missing unit as a ratio.
  - `dimension(self, unit: str | None) -> str` — Return the semantic dimension for a unit.
  - `convert(self, value: NumberLike, from_unit: str | None, to_unit: str | None) -> Decimal` — Convert a numeric value between compatible units.
- `NumericComparisonStatus(str, Enum)` — Comparison statuses emitted by :func:`compare_numeric`. [строка 134]
- `NumericValue()` — A scalar or closed numeric interval with an optional unit. [строка 144]
  - `is_range(self) -> bool` — —
  - `as_interval(self) -> tuple[Decimal, Decimal]` — —
  - `converted_to(self, unit: str | None, registry: UnitRegistry | None = None) -> NumericValue` — —
- `NumericComparisonResult()` — Result of a deterministic comparison between two numeric values. [строка 203]

### `scripts/researcher/researcher_core/numeric_source_runner.py`

- `numeric_value_from_json(data: Mapping[str, Any]) -> NumericValue | None` — — [строка 35]
- `compare_claim_sources_json(claim_data: Mapping[str, Any], sources_data: Sequence[Mapping[str, Any]], tolerance_relative: str | Decimal = '0.01') -> dict[str, Any]` — — [строка 49]

### `scripts/researcher/researcher_core/offline_pipeline.py`

- `OfflinePipelineResult()` — — [строка 33]
- `OfflineResearchPipeline()` — Small orchestrator for local document smoke tests. [строка 41]
  - `run_document(self, *, run_id: EntityId, operation_id: EntityId, correlation_id: EntityId, actor: ActorRef, title: str, text: str, locator: str) -> OfflinePipelineResult` — —

### `scripts/researcher/researcher_core/policy.py`

- `load_policy(root: Path) -> Policy` — — [строка 107]
- `load_bootstrap_policy(root: Path) -> BootstrapPolicy` — — [строка 133]
- `lint_policy_text(text: str) -> None` — — [строка 143]
- `compute_policy_hash_for_text(text: str) -> str` — — [строка 153]
- `BootstrapPolicy()` — — [строка 41]
- `ReasonCodeMeta()` — — [строка 49]
- `Heuristic()` — — [строка 57]
- `Policy()` — — [строка 71]
  - `debt_fail_on(self) -> str` — —
  - `debt_excluded_files(self) -> frozenset[str]` — —
  - `debt_excluded_dirs(self) -> frozenset[str]` — —
- `PolicyConfigurationError(RuntimeError)` — Raised when policy is missing or structurally invalid. [строка 103]

### `scripts/researcher/researcher_core/ports.py`

- `ClockPort(Protocol)` — — [строка 20]
  - `now_ms(self) -> int` — —
- `IdFactoryPort(Protocol)` — — [строка 25]
  - `new(self, prefix: str) -> EntityId` — —
- `CommandHandlerPort(Protocol)` — — [строка 30]
  - `execute(self, command: CommandEnvelope) -> CommandResult` — —
- `UnitOfWorkPort(Protocol)` — — [строка 35]
  - `put_state(self, entity_id: EntityId, row: Mapping[str, Any]) -> None` — —
  - `append_event(self, event: EventEnvelope) -> None` — —
  - `enqueue_outbox(self, message: OutboxMessage) -> None` — —
  - `put_rejection(self, command_id: EntityId, report: Any) -> None` — —
  - `commit(self) -> None` — —
  - `rollback(self) -> None` — —
- `EventProjectorPort(Protocol)` — — [строка 47]
  - `rebuild_state(self, events: Sequence[EventEnvelope]) -> Mapping[str, ProjectableEntity]` — —
- `CapabilityRegistryPort(Protocol)` — — [строка 52]
  - `register(self, capsule: Capsule) -> None` — —
  - `provider_for(self, capability: str) -> Capsule` — —
  - `capabilities(self) -> Mapping[str, str]` — —
- `CapsuleRunnerPort(Protocol)` — — [строка 59]
  - `run(self, request: CapsuleRequest) -> CapsuleObservation` — —
- `ArtifactBuilderPort(Protocol)` — — [строка 64]
  - `build(self, snapshot: Snapshot, state: Mapping[str, ProjectableEntity], title: str) -> Mapping[str, Any]` — —
  - `render(self, artifact: Mapping[str, Any]) -> str` — —

### `scripts/researcher/researcher_core/provenance_dependencies.py`

- `source_catalog_change_from_writer(result: Mapping[str, Any]) -> SourceCatalogSemanticChange` — Normalize the public ``source_catalog.upsert`` result without importing Writer. [строка 87]
- `resolve_catalog_change(change: SourceCatalogSemanticChange, bindings: Sequence[SourceIdentityBinding]) -> tuple[EntityId, ...]` — Return changed canonical Source ids for semantic changes only. [строка 120]
- `build_knowledge_dependencies(*, sources: Sequence[Source] = (), evidence_spans: Sequence[EvidenceSpan] = (), graph_edges: Sequence[GraphEdge] = (), trace_links: Sequence[ResearchTraceLink] = (), resolutions: Sequence[ChallengeResolutionAssessment] = (), relation_assessments: Sequence[RelationAssessment] = (), require_relation_assessment: bool = False, id_factory: EntityIdFactory, actor: ActorRef, run_id: EntityId, created_at) -> ProvenanceDependencyBuild` — Compile canonical provenance into R2.3 dependency records. [строка 145]
- `assess_source_catalog_change(*, catalog_result: Mapping[str, Any], bindings: Sequence[SourceIdentityBinding], dependencies: Sequence[KnowledgeDependency], target_resolution_id: EntityId | None, impact_meta: EntityMeta, max_nodes: int = 128) -> DependencyImpactAssessment` — SourceCatalog result -> canonical changed Source -> R2.3 impact. [строка 302]
- `reopen_from_source_catalog_change(*, catalog_result: Mapping[str, Any], bindings: Sequence[SourceIdentityBinding], dependencies: Sequence[KnowledgeDependency], dom, challenge, source_entity, resolution: ChallengeResolutionAssessment, challenge_card_id: EntityId, prior_iterations, patch_id: EntityId, impact_meta: EntityMeta, actor: ActorRef, id_factory: EntityIdFactory, timestamp, causation_id: EntityId, correlation_id: EntityId, max_nodes: int = 128)` — End-to-end shared SourceCatalog change -> selective historical reopen. [строка 343]
- `SourceIdentityBinding()` — Explicit bridge between shared-library/catalog identity and Researcher Source. [строка 41]
- `SourceCatalogSemanticChange()` — Normalized semantic change emitted by SourceCatalog-facing adapters. [строка 58]
- `ProvenanceDependencyBuild()` — — [строка 77]
- `ProvenanceDependencyError(ValueError)` — — [строка 83]

### `scripts/researcher/researcher_core/qualifier.py`

- `extract_qualifier(text: str) -> tuple[str, ...]` — — [строка 24]
- `compare_qualifiers(claim_quals: tuple[str, ...] | list[str], source_quals: tuple[str, ...] | list[str]) -> str` — — [строка 33]

### `scripts/researcher/researcher_core/r0/__init__.py`


### `scripts/researcher/researcher_core/r0/commands.py`

- `ActorRef()` — — [строка 16]
- `CommandEnvelope()` — — [строка 28]
  - `request_hash(self) -> str` — Deterministic hash used by idempotency records.
- `CommandResult()` — — [строка 80]

### `scripts/researcher/researcher_core/r0/entities.py`

- `EntityMeta()` — — [строка 25]
- `ClaimProposal()` — — [строка 46]
- `QuantityProposal()` — — [строка 67]
- `Claim()` — — [строка 89]
- `Quantity()` — — [строка 114]
- `Source()` — — [строка 133]
- `EvidenceSpan()` — — [строка 152]

### `scripts/researcher/researcher_core/r0/enums.py`

- `ClaimKind(_StrictStrEnum)` — — [строка 15]
- `EdgeKind(_StrictStrEnum)` — — [строка 34]
- `ClaimStatus(_StrictStrEnum)` — — [строка 44]
- `Verifiability(_StrictStrEnum)` — — [строка 54]
- `AdmissionStatus(_StrictStrEnum)` — — [строка 61]
- `EvidenceState(_StrictStrEnum)` — — [строка 70]
- `DerivationState(_StrictStrEnum)` — — [строка 80]
- `ExtrapolationState(_StrictStrEnum)` — — [строка 87]
- `ConflictState(_StrictStrEnum)` — — [строка 94]
- `GapState(_StrictStrEnum)` — — [строка 101]
- `WriterEligibility(_StrictStrEnum)` — — [строка 107]
- `ReviewState(_StrictStrEnum)` — — [строка 114]
- `ValidationResult(_StrictStrEnum)` — — [строка 120]
- `CommitPolicy(_StrictStrEnum)` — — [строка 130]

### `scripts/researcher/researcher_core/r0/events.py`

- `ReasonCode()` — Machine-readable reason, for example ``DEPENDS_ON_UNSUPPORTED_ASSUMPTION``. [строка 40]
  - `namespace(self) -> str` — —
- `ReasonCodeRegistry()` — Config-backed allowlist for stable reason codes. [строка 58]
  - `validate(self, reason_code: ReasonCode) -> None` — —
  - `validate_all(self, reason_codes: tuple[ReasonCode, ...]) -> None` — —
- `EventEnvelope()` — Audit event wrapper used by validation and state-change records. [строка 73]

### `scripts/researcher/researcher_core/r0/graph.py`

- `GraphEdgeState(StrEnum)` — Lifecycle state of a semantic relation. [строка 16]
- `GraphEdge()` — Authoritative relation between graph entities. [строка 31]
- `InMemoryGraphRepository()` — Tiny edge store used by bubble tests before SQLite repositories exist. [строка 53]
  - `add_edge(self, edge: GraphEdge) -> None` — —
  - `replace_edge(self, edge: GraphEdge, *, expected_revision: int) -> None` — —
  - `edges_for_source(self, source_id: EntityId) -> tuple[GraphEdge, ...]` — —
  - `edge_view(self) -> Mapping[EntityId, GraphEdge]` — —

### `scripts/researcher/researcher_core/r0/idempotency.py`

- `IdempotencyConflict(RuntimeError)` — — [строка 11]
- `InMemoryIdempotencyStore()` — Small deterministic stand-in for the future SQLite idempotency table. [строка 18]
  - `replay_if_recorded(self, command: CommandEnvelope) -> CommandResult | None` — —
  - `record_or_replay(self, command: CommandEnvelope, result: CommandResult) -> CommandResult` — —

### `scripts/researcher/researcher_core/r0/ids.py`

- `RandomSource(Protocol)` — — [строка 17]
  - `randrange(self, stop: int) -> int` — —
- `Clock(Protocol)` — — [строка 21]
  - `now_ms(self) -> int` — —
- `EntityIdFactory()` — Injectable ID factory port implementation for runtime wiring. [строка 26]
  - `new(self, prefix: str) -> 'EntityId'` — —
- `EntityId()` — Immutable R0 entity id, e.g. ``CLM_01J7K6Y5T4D3R2A1B0C9E8F7G6``. [строка 37]
  - `namespace(self) -> str` — —
  - `new(cls, prefix: str, clock: Clock, random_source: RandomSource) -> 'EntityId'` — Create a deterministic-testable ULID-like id from injected time/random.

### `scripts/researcher/researcher_core/r0/projections.py`

- `entity_to_event_record(entity: ProjectableEntity) -> EventRecord` — Return a stable, dataclass-free event payload record for an admitted entity. [строка 23]
- `entity_from_event_record(record: Mapping[str, Any]) -> ProjectableEntity` — Rebuild an entity from a stable event payload record. [строка 88]
- `rebuild_state_from_events(events: Sequence[EventEnvelope]) -> dict[str, ProjectableEntity]` — — [строка 158]
- `make_snapshot(snapshot_id: EntityId, events: Sequence[EventEnvelope], state: Mapping[EntityId, ProjectableEntity]) -> Snapshot` — — [строка 203]
- `Snapshot()` — — [строка 144]

### `scripts/researcher/researcher_core/r0/registry.py`

- `make_numeric_dry_run_batch(extraction_run_id: EntityId, proposition: str = 'The measured indicator increased by 12%.') -> ProposalBatch` — — [строка 295]
- `ProposalBatch()` — — [строка 30]
- `SequenceClock()` — — [строка 45]
  - `now_ms(self) -> int` — —
- `CycleRandom(RandomSource)` — — [строка 55]
  - `randrange(self, stop: int) -> int` — —
- `InMemoryClaimRegistry()` — Small application write boundary for R0 dry-run tests. [строка 65]
  - `execute(self, command: CommandEnvelope) -> CommandResult` — —
  - `admit(self, batch: ProposalBatch, policy: CommitPolicy, command: CommandEnvelope) -> CommandResult` — —
  - `state_snapshot(self) -> dict[str, Claim | Quantity | Source | EvidenceSpan | GraphEdge]` — —
  - `update_graph_edge(self, edge: GraphEdge, event: EventEnvelope, *, expected_revision: int) -> GraphEdge` — Durably replace one canonical GraphEdge after a lifecycle reducer.

### `scripts/researcher/researcher_core/r0/serialization.py`

- `canonical_json(obj: Any) -> str` — Return stable compact JSON for dataclasses, enums, ids, and datetimes. [строка 17]

### `scripts/researcher/researcher_core/r0/sqlite_store.py`

- `init_sqlite_schema(conn: sqlite3.Connection) -> None` — — [строка 64]
- `rebuild_state_from_sqlite(conn: sqlite3.Connection) -> dict[str, Any]` — Normalized projector: rebuild state from SQLite events table. [строка 237]
- `open_sqlite(path: Path | str = ':memory:') -> sqlite3.Connection` — — [строка 286]
- `SqliteUnitOfWork()` — Prod SQLite implementation of UnitOfWorkPort. [строка 70]
  - `put_state(self, entity_id: EntityId, row: Mapping[str, Any]) -> None` — —
  - `append_event(self, event: EventEnvelope) -> None` — —
  - `put_rejection(self, command_id: EntityId, report: Any) -> None` — —
  - `enqueue_outbox(self, message: OutboxMessage) -> None` — —
  - `commit(self) -> None` — —
  - `rollback(self) -> None` — —
  - `state_view(self) -> Mapping[str, Mapping[str, Any]]` — —
  - `events_view(self) -> list[Mapping[str, Any]]` — —
  - `outbox_view(self) -> list[Mapping[str, Any]]` — —
- `SqliteIdempotencyStore()` — SQLite-backed idempotency store — same semantics as InMemory, durable. [строка 176]
  - `replay_if_recorded(self, command: CommandEnvelope) -> CommandResult | None` — —
  - `record_or_replay(self, command: CommandEnvelope, result: CommandResult) -> CommandResult` — —

### `scripts/researcher/researcher_core/r0/state_machines.py`

- `transition_claim_status(claim: Claim, request: TransitionRequest, actor: ActorRef, event_id: EntityId, causation_id: EntityId, correlation_id: EntityId, timestamp, reason_registry: ReasonCodeRegistry | None = None) -> TransitionResult` — — [строка 74]
- `TransitionRequest()` — — [строка 37]
- `RevisionConflict(RuntimeError)` — Raised when expected revision does not match current entity revision. [строка 60]
- `InvalidTransition(RuntimeError)` — Raised when a status transition is not allowed by R0 state machine. [строка 64]
- `TransitionResult()` — — [строка 69]

### `scripts/researcher/researcher_core/r0/transactions.py`

- `OutboxMessage()` — — [строка 14]
- `UnitOfWorkStateError(RuntimeError)` — Raised when a transaction operation is used outside its lifecycle. [строка 24]
- `InMemoryUnitOfWork()` — Atomic in-memory stand-in for SQLite-backed UnitOfWork. [строка 28]
  - `put_state(self, entity_id: EntityId, row: Mapping[str, Any]) -> None` — —
  - `append_event(self, event: EventEnvelope) -> None` — —
  - `enqueue_outbox(self, message: OutboxMessage) -> None` — —
  - `put_rejection(self, command_id: EntityId, report: Any) -> None` — —
  - `commit(self) -> None` — —
  - `rollback(self) -> None` — —
  - `state_view(self) -> Mapping[EntityId, Mapping[str, Any]]` — —

### `scripts/researcher/researcher_core/r0/validation.py`

- `ValidationIssue()` — Single machine-readable registry admission problem. [строка 38]
- `ValidationReport()` — Immutable collection of validation issues. [строка 58]
  - `is_valid(self) -> bool` — —
  - `issue_codes(self) -> tuple[str, ...]` — —
- `RegistryValidationError(ValueError)` — Raised when a proposal batch violates registry invariants before commit. [строка 84]
- `RegistryValidator()` — Dependency-free validator for the registry write boundary. [строка 92]
  - `validate(self, batch: object, command: CommandEnvelope, existing_state: Mapping[EntityId, RegistryEntity]) -> ValidationReport` — —

### `scripts/researcher/researcher_core/r1_entities.py`

- `Scope()` — Typed research scope for a domain with its comparison dimensions. [строка 45]
- `Derivation()` — Arithmetic or logical derivation from input claims to an output claim. [строка 61]
- `Assumption()` — An admitted or candidate assumption that may back a claim. [строка 90]
- `Recommendation()` — A practical recommendation tied to supporting or blocking claims. [строка 110]
- `Gap()` — A knowledge gap: full graph node, not a validator-output string. [строка 134]
- `Conflict()` — A recorded conflict between claims and their supporting evidence. [строка 166]
- `EdgeProposal()` — Candidate graph edge between two entities, awaiting admission. [строка 193]

### `scripts/researcher/researcher_core/r3_validators.py`

- `GapDescriptor()` — — [строка 132]
- `ConflictDescriptor()` — — [строка 142]
- `StructuralRiskReport()` — — [строка 151]
- `RecommendationDecision()` — — [строка 163]
- `ValidationOutcome()` — — [строка 170]
- `SourceAdmissionValidator()` — Whether a document is an admissible source (identity + type + hash shape). [строка 338]
  - `evaluate(self, source: Any) -> ValidationOutcome` — —
- `EvidenceAdmissionValidator()` — Whether a specific span is an admissible evidence for a claim. [строка 372]
  - `evaluate(self, evidence: Any) -> ValidationOutcome` — —
- `AtomicityValidator()` — Whether a claim proposition is atomic rather than composite. [строка 414]
  - `evaluate(self, claim: Any) -> ValidationOutcome` — —
- `NumericValidator()` — Whether a Quantity is well-formed; warns on missing provenance. [строка 437]
  - `evaluate(self, quantity: Any) -> ValidationOutcome` — —
- `ScopeValidator()` — Whether a relation/claim scope match is admissible for writer/runtime use. [строка 490]
  - `evaluate(self, subject: Any) -> ValidationOutcome` — —
- `EdgeValidator()` — Whether an edge proposal/relation has a supported shape and endpoint pairing. [строка 518]
  - `evaluate(self, edge: Any) -> ValidationOutcome` — —
- `GraphCycleValidator()` — Whether the structural graph contains a directed cycle in dependency-like edges. [строка 585]
  - `evaluate(self, graph: Any) -> ValidationOutcome` — —
- `GapBuilder()` — Deterministically derives open gap descriptors from quantities/derivations. [строка 643]
  - `evaluate(self, snapshot: Any) -> tuple[GapDescriptor, ...]` — —
- `ConflictBuilder()` — Deterministically derives conflict descriptors from graph relations/claim snapshots. [строка 718]
  - `evaluate(self, snapshot: Any) -> tuple[ConflictDescriptor, ...]` — —
- `StructuralRiskAnalyzer()` — Computes deterministic structural-risk factors for a snapshot. [строка 773]
  - `evaluate(self, snapshot: Any) -> StructuralRiskReport` — —
- `RecommendationGate()` — Computes writer eligibility for a recommendation-like snapshot. [строка 846]
  - `evaluate(self, recommendation: Any) -> RecommendationDecision` — —

### `scripts/researcher/researcher_core/relation_assessment.py`

- `assess_relation(*, edge: GraphEdge, proposal: RelationAssessmentProposal, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[RelationAssessment, ResearchTraceLink]` — — [строка 214]
- `lifecycle_transition_from_assessment(*, edge: GraphEdge, assessment: RelationAssessment, actor: ActorRef, id_factory: EntityIdFactory, timestamp, causation_id: EntityId, correlation_id: EntityId) -> RelationTransitionResult | None` — — [строка 279]
- `latest_assessment_by_edge(assessments: Sequence[RelationAssessment]) -> Mapping[EntityId, RelationAssessment]` — Choose one deterministic L1 assessment per edge. [строка 309]
- `relation_assessment_proposal_to_dict(value: RelationAssessmentProposal) -> dict[str, Any]` — — [строка 328]
- `relation_assessment_to_dict(value: RelationAssessment) -> dict[str, Any]` — — [строка 341]
- `RelationAssessmentError(ValueError)` — — [строка 30]
- `RelationAssessmentVerdict(StrEnum)` — — [строка 34]
- `RelationUseState(StrEnum)` — — [строка 41]
- `MethodMatch(StrEnum)` — — [строка 47]
- `EvidenceQuality(StrEnum)` — — [строка 54]
- `RelationAssessmentProposal()` — — [строка 63]
- `RelationAssessment()` — — [строка 96]
  - `reasoning_eligible(self) -> bool` — —
- `RelationAssessmentAuditRepository()` — — [строка 354]
  - `save_proposal(self, proposal: RelationAssessmentProposal) -> None` — —
  - `save_assessment(self, assessment: RelationAssessment) -> None` — —

### `scripts/researcher/researcher_core/relation_feedback.py`

- `gap_from_inconclusive_relation(*, edge: GraphEdge, assessment: RelationAssessment, gap_id: EntityId) -> Gap` — Convert one current INCONCLUSIVE/BLOCKED relation into a typed Gap. [строка 44]
- `materialize_relation_assessment_feedback(*, dom: ResearchDOM, edge: GraphEdge, assessment: RelationAssessment, existing_challenges: Sequence[ResearchChallenge], id_factory: EntityIdFactory, actor: ActorRef, timestamp, causation_id: EntityId, correlation_id: EntityId) -> RelationGapFeedbackResult` — Create one Gap→ResearchChallenge→CHALLENGE card feedback branch. [строка 87]
- `relation_gap_to_dict(gap: Gap) -> dict[str, object]` — — [строка 161]
- `relation_gap_from_dict(raw) -> Gap` — — [строка 174]
- `RelationFeedbackError(ValueError)` — — [строка 33]
- `RelationGapFeedbackResult()` — — [строка 38]
- `RelationFeedbackRepository()` — Atomic durable projection for relation-generated Gap + Challenge. [строка 186]
  - `save(self, gap: Gap, challenge: ResearchChallenge) -> None` — —
  - `load_gap(self, gap_id: EntityId) -> Gap | None` — —

### `scripts/researcher/researcher_core/relation_lifecycle.py`

- `transition_relation_state(edge: GraphEdge, request: RelationTransitionRequest, *, actor: ActorRef, event_id: EntityId, timestamp, causation_id: EntityId, correlation_id: EntityId) -> RelationTransitionResult` — — [строка 65]
- `project_stale_relations_from_impact(*, impact: DependencyImpactAssessment, graph_edges: Sequence[GraphEdge], expected_revisions: Mapping[EntityId, int], actor: ActorRef, id_factory: EntityIdFactory, timestamp, causation_id: EntityId, correlation_id: EntityId, fail_on_missing: bool = True) -> RelationImpactProjection` — Project DIA.stale_relation_ids onto canonical GraphEdge lifecycle. [строка 113]
- `RelationLifecycleError(ValueError)` — — [строка 30]
- `RelationTransitionRequest()` — — [строка 35]
- `RelationTransitionResult()` — — [строка 52]
- `RelationImpactProjection()` — — [строка 58]

### `scripts/researcher/researcher_core/research_planning.py`

- `create_initial_dom(request: ResearchRequest, root_card: ResearchCard, dom_id: EntityId) -> ResearchDOM` — — [строка 279]
- `apply_research_patch(dom: ResearchDOM, patch: ResearchPatch, actor: ActorRef, id_factory: EntityIdFactory, timestamp, causation_id: EntityId, correlation_id: EntityId) -> PlanningReduceResult` — — [строка 306]
- `build_research_map(meta: EntityMeta, request_id: EntityId, candidate_cards: Sequence[ResearchCard]) -> ResearchMap` — Build a compact multidimensional ResearchMap from candidate cards. [строка 428]
- `compile_decomposition_proposals(*, session: DecompositionSession, dom: ResearchDOM, proposals: Sequence[ResearchCardProposal], id_factory: EntityIdFactory, actor: ActorRef, created_at) -> PlanningCompileResult` — Compile a planning dialectic result into cards + map + atomic patch. [строка 591]
- `ResearchCardKind(StrEnum)` — — [строка 23]
- `ResearchCardStatus(StrEnum)` — — [строка 35]
- `PlanningTurnKind(StrEnum)` — — [строка 46]
- `PlanningRole(StrEnum)` — — [строка 51]
- `ResearchRequest()` — — [строка 59]
- `ResearchCard()` — — [строка 73]
- `ResearchMap()` — — [строка 104]
- `PlanningInquiryTurn()` — — [строка 125]
- `DecompositionSession()` — — [строка 147]
- `ResearchDOM()` — — [строка 166]
  - `children_of(self, card_id: EntityId) -> tuple[ResearchCard, ...]` — —
  - `lineage(self, card_id: EntityId) -> tuple[ResearchCard, ...]` — —
- `AddCardOperation()` — — [строка 219]
- `SetCardStatusOperation()` — — [строка 224]
- `ResearchPatch()` — — [строка 240]
- `ResearchPlanningError(RuntimeError)` — — [строка 261]
- `ResearchDOMRevisionConflict(ResearchPlanningError)` — — [строка 265]
- `ResearchPatchConflict(ResearchPlanningError)` — — [строка 269]
- `PlanningReduceResult()` — — [строка 274]
- `ResearchCardProposal()` — Non-authoritative card proposed by PlanningDialectic or another planner. [строка 551]
- `PlanningCompileResult()` — — [строка 581]
- `PlanningCompileError(ResearchPlanningError)` — — [строка 587]

### `scripts/researcher/researcher_core/research_planning_runtime.py`

- `planning_gate_policy_from_policy(policy) -> PlanningGatePolicy` — Build PlanningGatePolicy from config/research_policy.yaml heuristics. [строка 71]
- `evaluate_planning_gate(dom: ResearchDOM, policy: PlanningGatePolicy = PlanningGatePolicy()) -> PlanningGateReport` — Evaluate structural executability, not scientific truth or completeness. [строка 87]
- `evaluate_planning_subtree_gate(dom: ResearchDOM, root_card_id: EntityId, policy: PlanningGatePolicy = PlanningGatePolicy(require_direction=False)) -> PlanningGateReport` — Evaluate executability of one local ResearchDOM subtree. [строка 151]
- `research_trace_link_to_dict(link: ResearchTraceLink) -> dict[str, Any]` — — [строка 296]
- `research_trace_link_from_dict(raw: Mapping[str, Any]) -> ResearchTraceLink` — — [строка 310]
- `research_dom_to_dict(dom: ResearchDOM) -> dict[str, Any]` — — [строка 344]
- `research_dom_from_dict(raw: Mapping[str, Any]) -> ResearchDOM` — — [строка 355]
- `replay_research_dom(initial_dom: ResearchDOM, events: Sequence[EventEnvelope]) -> ResearchDOM` — Rebuild ResearchDOM from planning events after the known initial root snapshot. [строка 367]
- `card_to_event_payload(card: ResearchCard) -> Mapping[str, Any]` — — [строка 403]
- `PlanningGateState(StrEnum)` — — [строка 27]
- `PlanningGateIssue()` — — [строка 34]
- `PlanningGateReport()` — — [строка 49]
- `PlanningGatePolicy()` — — [строка 60]
- `ResearchTraceRelation(StrEnum)` — — [строка 242]
- `ResearchTraceLink()` — — [строка 252]
- `ResearchDOMRepository()` — Small durable adapter over the existing R0 SQLite UnitOfWork. [строка 276]
  - `save(self, dom: ResearchDOM, events: Sequence[EventEnvelope] = ()) -> None` — —
  - `load(self, dom_id: EntityId) -> ResearchDOM | None` — —
- `ResearchTraceRepository()` — — [строка 323]
  - `save(self, links: Sequence[ResearchTraceLink]) -> None` — —
  - `all(self) -> tuple[ResearchTraceLink, ...]` — —
  - `for_card(self, card_id: EntityId) -> tuple[ResearchTraceLink, ...]` — —

### `scripts/researcher/researcher_core/runtime.py`

- `build_in_memory_runtime() -> RuntimeServices` — — [строка 64]
- `build_sqlite_runtime(db_path: str | Path = ':memory:') -> RuntimeServices` — — [строка 77]
- `MinimalArtifactBuilderAdapter()` — — [строка 24]
  - `build(self, snapshot: Snapshot, state: Mapping[str, ProjectableEntity], title: str) -> Mapping[str, Any]` — —
  - `render(self, artifact: Mapping[str, Any]) -> str` — —
- `SqliteArtifactBuilderAdapter()` — — [строка 33]
  - `build(self, snapshot: Snapshot, state: Mapping[str, ProjectableEntity], title: str) -> Mapping[str, Any]` — —
  - `render(self, artifact: Mapping[str, Any]) -> str` — —
- `InMemoryEventProjectorAdapter()` — — [строка 42]
  - `rebuild_state(self, events)` — —
- `SqliteEventProjectorAdapter()` — — [строка 48]
  - `rebuild_state(self, events)` — —
- `RuntimeServices()` — — [строка 56]

### `scripts/researcher/researcher_core/strict_reasoning.py`

- `build_strict_reasoning_dependencies(*, sources: Sequence[Source] = (), evidence_spans: Sequence[EvidenceSpan] = (), graph_edges: Sequence[GraphEdge] = (), trace_links: Sequence[ResearchTraceLink] = (), resolutions: Sequence[ChallengeResolutionAssessment] = (), relation_assessments: Sequence[RelationAssessment] = (), id_factory: EntityIdFactory, actor: ActorRef, run_id: EntityId, created_at) -> ProvenanceDependencyBuild` — — [строка 20]

### `scripts/researcher/researcher_core/task_execution.py`

- `compile_task_execution_plan(*, dom: ResearchDOM, card_id: EntityId, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, local_capabilities: Sequence[str] = ()) -> TaskExecutionPlan` — Compile one authoritative leaf card into a deterministic execution plan. [строка 158]
- `start_task_execution(*, dom: ResearchDOM, plan: TaskExecutionPlan, id_factory: EntityIdFactory, actor: ActorRef, timestamp: datetime, causation_id: EntityId, correlation_id: EntityId)` — Revision-checked source-card transition into ACTIVE. [строка 238]
- `execute_local_task(*, plan: TaskExecutionPlan, active_card_revision: int, registry: InMemoryCapabilityRegistry, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> TaskExecutionResult` — — [строка 263]
- `build_delegation_request(*, plan: TaskExecutionPlan, parent_job_id: str, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> DelegationRequest` — — [строка 293]
- `finish_task_execution(*, dom: ResearchDOM, plan: TaskExecutionPlan, result: TaskExecutionResult, id_factory: EntityIdFactory, actor: ActorRef, timestamp: datetime, causation_id: EntityId, correlation_id: EntityId)` — Project terminal execution into ResearchDOM card state only. [строка 423]
- `task_execution_plan_to_dict(plan: TaskExecutionPlan) -> dict[str, Any]` — — [строка 473]
- `task_execution_plan_from_dict(raw: Mapping[str, Any]) -> TaskExecutionPlan` — — [строка 483]
- `delegation_request_to_dict(request: DelegationRequest) -> dict[str, Any]` — — [строка 493]
- `delegation_request_from_dict(raw: Mapping[str, Any]) -> DelegationRequest` — — [строка 503]
- `task_execution_result_to_dict(result: TaskExecutionResult) -> dict[str, Any]` — — [строка 533]
- `task_execution_result_from_dict(raw: Mapping[str, Any]) -> TaskExecutionResult` — — [строка 543]
- `TaskExecutionError(ValueError)` — — [строка 43]
- `ExecutionOwner(StrEnum)` — — [строка 47]
- `ExecutionMode(StrEnum)` — — [строка 53]
- `DelegationMode(StrEnum)` — — [строка 58]
- `TaskExecutionStatus(StrEnum)` — — [строка 64]
- `TaskExecutionPlan()` — — [строка 71]
- `DelegationRequest()` — — [строка 102]
- `TaskExecutionResult()` — — [строка 131]
- `JobCtlDelegationAdapter()` — Thin infrastructure adapter over the existing JSON Job/Child runtime. [строка 327]
  - `child_state_path(self, child_job_id: str) -> Path` — —
  - `start(self, *, parent_state_path: str | Path, request: DelegationRequest) -> Path` — —
  - `finish(self, *, parent_state_path: str | Path, request: DelegationRequest, child_status: str, active_card_revision: int, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, artifact_refs: Sequence[str] = ()) -> TaskExecutionResult` — —
- `TaskExecutionRepository()` — Durable audit store for R3 plans, delegations and terminal results. [строка 554]
  - `save_plan(self, plan: TaskExecutionPlan) -> None` — —
  - `save_delegation(self, request: DelegationRequest) -> None` — —
  - `save_result(self, result: TaskExecutionResult) -> None` — —
  - `load_plan(self, entity_id: EntityId) -> TaskExecutionPlan | None` — —
  - `load_delegation(self, entity_id: EntityId) -> DelegationRequest | None` — —
  - `load_result(self, entity_id: EntityId) -> TaskExecutionResult | None` — —

### `scripts/researcher/researcher_core/tribunal_advocate.py`

- `decide_advocate_activation(*, graph: ArgumentGraphProjection, arguments: Mapping[EntityId, ArgumentArtifact], challenge_relation: ArgumentRelation, composition_policy: TribunalCompositionPolicy, policy: AdvocateActivationPolicy = AdvocateActivationPolicy()) -> AdvocateActivationDecision` — — [строка 192]
- `compile_advocate_disclosure(*, activation: AdvocateActivationDecision, graph: ArgumentGraphProjection, arguments: Mapping[EntityId, ArgumentArtifact], id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> DialecticDisclosureContract` — — [строка 250]
- `validate_disclosure_contract_integrity(disclosure: DialecticDisclosureContract) -> None` — — [строка 293]
- `compile_advocate_defense_contract(*, activation: AdvocateActivationDecision, disclosure: DialecticDisclosureContract, composition_policy: TribunalCompositionPolicy, instruction: RoleInstructionPack, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, token_budget: int | None = None) -> AdvocateDefenseContract` — — [строка 300]
- `materialize_advocate_draft(*, contract: AdvocateDefenseContract, disclosure: DialecticDisclosureContract, draft: AdvocateWorkerDraft, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> AdvocateResponse` — — [строка 376]
- `admit_advocate_response_to_argument_graph(*, graph: ArgumentGraphProjection, arguments: Mapping[EntityId, ArgumentArtifact], disclosure: DialecticDisclosureContract, response: AdvocateResponse, actor: ActorRef, created_at: datetime) -> tuple[ArgumentGraphProjection, dict[EntityId, ArgumentArtifact], DialecticBranchRef]` — Admit a validated Advocate response without changing epistemic state. [строка 501]
- `validate_advocate_contract_integrity(contract: AdvocateDefenseContract, disclosure: DialecticDisclosureContract) -> None` — — [строка 541]
- `disclosure_contract_to_dict(contract: DialecticDisclosureContract) -> dict[str, Any]` — — [строка 611]
- `advocate_defense_contract_to_dict(contract: AdvocateDefenseContract) -> dict[str, Any]` — — [строка 615]
- `advocate_response_to_dict(response: AdvocateResponse) -> dict[str, Any]` — — [строка 643]
- `TribunalAdvocateError(RuntimeError)` — — [строка 55]
- `AdvocateOutcome(StrEnum)` — — [строка 59]
- `AdvocateNextAction(StrEnum)` — — [строка 67]
- `AdvocateActivationPolicy()` — — [строка 75]
- `AdvocateActivationDecision()` — — [строка 87]
- `AdvocateDefenseContract()` — — [строка 106]
- `AdvocateWorkerDraft()` — — [строка 153]
- `AdvocateResponse()` — — [строка 176]

### `scripts/researcher/researcher_core/tribunal_argument_graph.py`

- `build_argument_graph(*, meta: EntityMeta, arguments: Sequence[ArgumentArtifact], relations: Sequence[ArgumentRelation]) -> ArgumentGraphProjection` — — [строка 87]
- `validate_argument_graph_integrity(graph: ArgumentGraphProjection, arguments: Sequence[ArgumentArtifact]) -> None` — — [строка 142]
- `append_argument_branch(*, graph: ArgumentGraphProjection, new_meta: EntityMeta, arguments: Sequence[ArgumentArtifact], new_relations: Sequence[ArgumentRelation]) -> ArgumentGraphProjection` — — [строка 155]
- `relation_targets(graph: ArgumentGraphProjection, argument_id: EntityId) -> tuple[ArgumentRelation, ...]` — — [строка 178]
- `relation_sources(graph: ArgumentGraphProjection, argument_id: EntityId) -> tuple[ArgumentRelation, ...]` — — [строка 185]
- `argument_relation_to_dict(relation: ArgumentRelation) -> dict[str, Any]` — — [строка 192]
- `argument_graph_to_dict(graph: ArgumentGraphProjection) -> dict[str, Any]` — — [строка 207]
- `TribunalArgumentGraphError(RuntimeError)` — — [строка 22]
- `ArgumentRelationKind(StrEnum)` — — [строка 26]
- `ArgumentRelationState(StrEnum)` — — [строка 33]
- `ArgumentRelation()` — — [строка 40]
- `ArgumentGraphProjection()` — — [строка 66]

### `scripts/researcher/researcher_core/tribunal_composition.py`

- `load_tribunal_composition_policy(path: Path) -> TribunalCompositionPolicy` — — [строка 228]
- `lineage_profile_from_research_dom(dom: ResearchDOM, card_id: EntityId, *, object_profile: Sequence[str] = ()) -> TribunalLineageProfile` — Compile the structural R1 lineage into the typed R4 routing profile. [строка 303]
- `assessment_need_refs_for_work_field(field: ReviewWorkField) -> tuple[AssessmentNeedRef, ...]` — Public R4 bridge for deterministic references to R3.5 AssessmentNeeds. [строка 338]
- `tribunal_composition_plan_to_dict(plan: TribunalCompositionPlan) -> dict[str, Any]` — — [строка 348]
- `compile_tribunal_composition(request: TribunalCompositionRequest, policy: TribunalCompositionPolicy) -> TribunalCompositionPlan` — — [строка 420]
- `validate_tribunal_composition_plan_integrity(plan: TribunalCompositionPlan) -> None` — Fail closed if a persisted/transferred plan was altered after compilation. [строка 522]
- `TribunalCompositionError(RuntimeError)` — — [строка 26]
- `EvidenceViewKind(StrEnum)` — — [строка 30]
- `TribunalRoleKind(StrEnum)` — — [строка 38]
- `CompositionReason(StrEnum)` — — [строка 44]
- `EvidenceViewPolicy()` — — [строка 54]
- `TribunalRoleSpec()` — — [строка 68]
- `TribunalLineageProfile()` — — [строка 99]
  - `tags(self) -> frozenset[str]` — —
- `AssessmentNeedRef()` — R4-local stable reference because R3.5 AssessmentNeed has no entity id. [строка 124]
- `AssessmentAssignment()` — — [строка 143]
- `RoleBriefContract()` — — [строка 156]
- `TribunalCompositionRequest()` — — [строка 175]
- `TribunalCompositionPlan()` — — [строка 181]
- `TribunalCompositionPolicy()` — — [строка 203]

### `scripts/researcher/researcher_core/tribunal_dialectic.py`

- `new_branch_history(branch: DialecticBranchRef) -> DialecticBranchHistory` — — [строка 311]
- `dialectic_branch_history_to_dict(value: DialecticBranchHistory) -> dict[str, Any]` — — [строка 315]
- `restore_dialectic_branch_history(payload: Mapping[str, Any]) -> DialecticBranchHistory` — — [строка 336]
- `validate_branch_history_integrity(value: DialecticBranchHistory) -> None` — — [строка 363]
- `observe_branch_dialectic_step(*, branch: DialecticBranchRef, argument: ArgumentArtifact, turn: InquiryTurn, branch_history: DialecticBranchHistory, visible_refs: Sequence[EntityId] = (), issue_proposals: Sequence[DialecticIssueProposal] = (), issue_resolutions: Sequence[DialecticIssueResolutionProposal] = (), chain_turn_count: int | None = None, token_cost: int = 0, policy: DialecticPolicy = DialecticPolicy()) -> BranchDialecticStepResult` — — [строка 374]
- `level_for_turn(kind: InquiryTurnKind) -> DialecticLevel` — — [строка 414]
- `branch_resume_dimensions(branch: DialecticBranchRef, issue_signature: str) -> dict[str, Any]` — — [строка 425]
- `validate_branch_resume_dimensions(*, dimensions: Mapping[str, Any], branch: DialecticBranchRef, issue_signature: str) -> None` — — [строка 441]
- `compile_research_resume_anchor(*, research_challenge_id: EntityId, source_gap_id: EntityId, branch_history: DialecticBranchHistory, issue_signature: str, challenge_dimensions: Mapping[str, Any]) -> DialecticResearchResumeAnchor` — — [строка 453]
- `validate_research_resume_anchor(*, anchor: DialecticResearchResumeAnchor, research_challenge_id: EntityId, source_gap_id: EntityId, branch_history: DialecticBranchHistory, issue_signature: str) -> None` — — [строка 489]
- `observe_dialectic_step(*, level: DialecticLevel, argument: ArgumentArtifact, turn: InquiryTurn, history: DialecticHistory, visible_refs: Sequence[EntityId] = (), issue_proposals: Sequence[DialecticIssueProposal] = (), issue_resolutions: Sequence[DialecticIssueResolutionProposal] = (), chain_turn_count: int | None = None, token_cost: int = 0, policy: DialecticPolicy = DialecticPolicy()) -> DialecticStepResult` — Observe one admitted semantic response and choose the next bounded action. [строка 527]
- `decide_dialectic_control(*, observation: DialecticObservation, argument: ArgumentArtifact, policy: DialecticPolicy) -> DialecticControlDecision` — — [строка 648]
- `emergent_issue_from_capability_gap(*, statement: str, need_refs: Sequence[AssessmentNeedRef], source_argument_id: EntityId, source_turn_id: EntityId, metadata: Mapping[str, Any] | None = None) -> EmergentIssue` — — [строка 717]
- `validate_dialectic_turn_chain(turns: Sequence[InquiryTurn]) -> None` — Validate a bounded linear Q/A chain without assigning semantic truth. [строка 738]
- `gap_from_emergent_issue(*, issue: EmergentIssue, target_claim_ids: Sequence[EntityId], gap_id: EntityId) -> Gap` — Project an actionable Tribunal issue into the existing canonical Gap path. [строка 765]
- `dialectic_observation_to_dict(observation: DialecticObservation) -> dict[str, Any]` — — [строка 795]
- `dialectic_decision_to_dict(decision: DialecticControlDecision) -> dict[str, Any]` — — [строка 822]
- `TribunalDialecticError(RuntimeError)` — — [строка 33]
- `DialecticLevel(IntEnum)` — Process depth, not scientific confidence or truth. [строка 37]
- `EmergentIssueKind(StrEnum)` — — [строка 48]
- `DialecticAction(StrEnum)` — — [строка 63]
- `DialecticIssueDisposition(StrEnum)` — — [строка 77]
- `DialecticPolicy()` — — [строка 96]
- `EmergentIssue()` — — [строка 122]
- `DialecticIssueProposal()` — Typed semantic proposal from a bounded turn-observer role. [строка 152]
- `DialecticIssueResolutionProposal()` — — [строка 179]
- `DialecticObservation()` — — [строка 190]
- `DialecticControlDecision()` — — [строка 224]
- `DialecticHistory()` — Minimal history needed by the control observer. [строка 237]
- `DialecticStepResult()` — — [строка 256]
- `DialecticBranchHistory()` — Branch-scoped wrapper around the local dialectic control history. [строка 263]
- `BranchDialecticStepResult()` — — [строка 284]
- `DialecticResearchResumeAnchor()` — — [строка 291]

### `scripts/researcher/researcher_core/tribunal_disclosure.py`

- `compile_branch_ref(*, graph: ArgumentGraphProjection, arguments: Mapping[EntityId, ArgumentArtifact], anchor_argument_id: EntityId, head_argument_id: EntityId | None = None, anchor_relation_id: EntityId | None = None, issue_signature: str = '') -> DialecticBranchRef` — — [строка 226]
- `refresh_branch_ref(*, branch: DialecticBranchRef, graph: ArgumentGraphProjection, arguments: Mapping[EntityId, ArgumentArtifact], head_argument_id: EntityId) -> DialecticBranchRef` — — [строка 275]
- `compile_dialectic_disclosure(*, role_id: str, purpose: DisclosurePurpose, branch: DialecticBranchRef, graph: ArgumentGraphProjection, arguments: Mapping[EntityId, ArgumentArtifact], assigned_need_refs: Sequence[AssessmentNeedRef], id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, focus_argument_id: EntityId | None = None, focus_relation_id: EntityId | None = None, focus_turn_id: EntityId | None = None, focus_issue_signature: str = '', base_evidence_refs: Sequence[EntityId] = (), base_target_refs: Sequence[EntityId] = (), policy: DialecticDisclosurePolicy = DialecticDisclosurePolicy()) -> DialecticDisclosureContract` — — [строка 295]
- `validate_disclosure_contract_integrity(disclosure: DialecticDisclosureContract, *, graph: ArgumentGraphProjection | None = None) -> None` — — [строка 408]
- `compile_question_contract(*, purpose: QuestionPurpose, role_id: str, answer_role_id: str, disclosure: DialecticDisclosureContract, instruction: RoleInstructionPack, parent_turn_id: EntityId, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, policy_version: str, policy_hash: str, target_argument_id: EntityId | None = None, target_turn_id: EntityId | None = None, target_issue_signature: str = '', admitted_new_issue_signatures: Sequence[str] = (), expected_closure_surface: Sequence[str] = (), max_response_tokens: int = 1800, max_followups: int = 1) -> DialecticQuestionContract` — — [строка 443]
- `validate_question_contract_integrity(contract: DialecticQuestionContract, disclosure: DialecticDisclosureContract) -> None` — — [строка 561]
- `materialize_question_turn(*, contract: DialecticQuestionContract, disclosure: DialecticDisclosureContract, question: str, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> InquiryTurn` — — [строка 598]
- `validate_answer_against_question_contract(*, contract: DialecticQuestionContract, disclosure: DialecticDisclosureContract, question_turn: InquiryTurn, answer_turn: InquiryTurn, answer_argument: ArgumentArtifact) -> None` — — [строка 634]
- `disclosure_contract_to_dict(contract: DialecticDisclosureContract) -> dict[str, Any]` — — [строка 676]
- `question_contract_to_dict(contract: DialecticQuestionContract) -> dict[str, Any]` — — [строка 702]
- `disclosure_contract_from_dict(payload: Mapping[str, Any]) -> DialecticDisclosureContract` — — [строка 733]
- `question_contract_from_dict(payload: Mapping[str, Any]) -> DialecticQuestionContract` — — [строка 764]
- `branch_ref_to_dict(branch: DialecticBranchRef) -> dict[str, Any]` — — [строка 801]
- `branch_ref_from_dict(payload: Mapping[str, Any]) -> DialecticBranchRef` — — [строка 815]
- `TribunalDisclosureError(RuntimeError)` — — [строка 35]
- `DisclosurePurpose(StrEnum)` — — [строка 39]
- `DialecticBranchRef()` — Stable branch identity plus the graph snapshot currently being viewed. [строка 48]
- `DialecticDisclosurePolicy()` — Small deterministic policy for prior-artifact disclosure. [строка 80]
  - `policy_hash(self) -> str` — —
- `DialecticDisclosureContract()` — — [строка 112]
  - `argument_graph_id(self) -> EntityId` — —
  - `graph_fingerprint(self) -> str` — —
- `QuestionPurpose(StrEnum)` — — [строка 167]
- `QuestionTargetKind(StrEnum)` — — [строка 172]
- `DialecticQuestionContract()` — — [строка 178]

### `scripts/researcher/researcher_core/tribunal_evidence.py`

- `compile_tribunal_evidence_bundle(request: TribunalEvidenceRequest) -> TribunalEvidenceBundle` — — [строка 182]
- `tribunal_evidence_bundle_to_dict(bundle: TribunalEvidenceBundle) -> dict[str, Any]` — — [строка 225]
- `tribunal_evidence_slice_to_dict(slice_: TribunalEvidenceSlice) -> dict[str, Any]` — — [строка 236]
- `TribunalEvidenceError(RuntimeError)` — — [строка 37]
- `EvidenceSliceStatus(StrEnum)` — — [строка 41]
- `EvidencePolarity(StrEnum)` — — [строка 47]
- `EvidenceSelectionReason(StrEnum)` — — [строка 53]
- `EvidenceItemProjection()` — — [строка 65]
- `SourceProjection()` — — [строка 83]
- `TargetProjection()` — — [строка 96]
- `PriorReviewArtifact()` — Non-authoritative prior review context offered to the slicer. [строка 106]
- `TribunalEvidenceSlice()` — — [строка 126]
- `TribunalEvidenceBundle()` — — [строка 157]
- `TribunalEvidenceRequest()` — — [строка 172]

### `scripts/researcher/researcher_core/tribunal_inquiry.py`

- `characterize_response_grounding(items: Sequence[ResponseGroundingItem]) -> ResponseGroundingState` — — [строка 116]
- `compile_inquiry_contract(*, plan: TribunalCompositionPlan, evidence_slice: TribunalEvidenceSlice, work_field: ReviewWorkField, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, role_instruction_id: str, role_instruction_fingerprint: str) -> InquiryContract` — — [строка 307]
- `validate_inquiry_contract_integrity(contract: InquiryContract) -> None` — — [строка 386]
- `materialize_role_worker_draft(*, contract: InquiryContract, evidence_slice: TribunalEvidenceSlice, draft: RoleWorkerDraft, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> InquiryExecutionArtifacts` — — [строка 408]
- `prior_review_artifact_from_argument(argument: ArgumentArtifact) -> PriorReviewArtifact` — Project a canonical R4.3 argument into the R4.2 prior-review visibility envelope. [строка 457]
- `inquiry_contract_to_dict(contract: InquiryContract) -> dict[str, Any]` — — [строка 480]
- `inquiry_turn_to_dict(turn: InquiryTurn) -> dict[str, Any]` — — [строка 503]
- `argument_artifact_to_dict(argument: ArgumentArtifact) -> dict[str, Any]` — — [строка 517]
- `TribunalInquiryError(RuntimeError)` — — [строка 36]
- `InquiryPhase(StrEnum)` — — [строка 40]
- `InquiryTurnKind(StrEnum)` — — [строка 44]
- `ArgumentPosition(StrEnum)` — — [строка 53]
- `DiscoveryKind(StrEnum)` — — [строка 60]
- `ResponseGroundingKind(StrEnum)` — — [строка 72]
- `ResponseGroundingState(StrEnum)` — — [строка 82]
- `ResponseGroundingItem()` — — [строка 92]
- `InquiryContract()` — — [строка 137]
- `InquiryDiscovery()` — — [строка 178]
- `AdditionalEvidenceRequest()` — — [строка 197]
- `RoleWorkerDraft()` — — [строка 215]
- `InquiryTurn()` — — [строка 236]
- `ArgumentArtifact()` — — [строка 260]
- `InquiryExecutionArtifacts()` — — [строка 302]

### `scripts/researcher/researcher_core/tribunal_live_dialogue.py`

- `compile_execution_envelope(*, binding: RoleProviderBinding, disclosure: DialecticDisclosureContract, question_contract: DialecticQuestionContract, instruction: RoleInstructionPack, argument_payloads: Mapping[EntityId | str, Mapping[str, Any]], turn_payloads: Mapping[EntityId | str, Mapping[str, Any]], ref_payloads: Mapping[EntityId | str, Mapping[str, Any]], question_turn: InquiryTurn | None = None, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> TribunalExecutionEnvelope` — — [строка 434]
- `validate_execution_envelope_integrity(envelope: TribunalExecutionEnvelope) -> None` — — [строка 585]
- `execution_envelope_to_dict(envelope: TribunalExecutionEnvelope) -> dict[str, Any]` — — [строка 590]
- `execution_envelope_from_dict(payload: Mapping[str, Any]) -> TribunalExecutionEnvelope` — — [строка 621]
- `compile_advocate_execution_envelope(*, binding: RoleProviderBinding, disclosure: DialecticDisclosureContract, contract: AdvocateDefenseContract, instruction: RoleInstructionPack, argument_payloads: Mapping[EntityId | str, Mapping[str, Any]], turn_payloads: Mapping[EntityId | str, Mapping[str, Any]], ref_payloads: Mapping[EntityId | str, Mapping[str, Any]], id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> TribunalExecutionEnvelope` — — [строка 650]
- `validate_provider_execution_receipt_integrity(receipt: ProviderExecutionReceipt) -> None` — — [строка 765]
- `provider_execution_receipt_to_dict(receipt: ProviderExecutionReceipt) -> dict[str, Any]` — — [строка 770]
- `provider_execution_receipt_from_dict(payload: Mapping[str, Any]) -> ProviderExecutionReceipt` — — [строка 781]
- `materialize_live_answer(*, contract: DialecticQuestionContract, disclosure: DialecticDisclosureContract, question_turn: InquiryTurn, answer_role_id: str, provider_payload: Mapping[str, Any], id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[InquiryTurn, ArgumentArtifact]` — — [строка 888]
- `admit_live_answer_to_argument_graph(*, graph: ArgumentGraphProjection, arguments: Mapping[EntityId, ArgumentArtifact], branch: DialecticBranchRef, question_contract: DialecticQuestionContract, answer_argument: ArgumentArtifact, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[ArgumentGraphProjection, dict[EntityId, ArgumentArtifact], DialecticBranchRef, ArgumentRelation]` — Admit one already validated live answer into the historical argument graph. [строка 949]
- `TribunalLiveDialogueError(RuntimeError)` — — [строка 77]
- `TribunalLiveDialogueTimeout(TribunalLiveDialogueError)` — — [строка 81]
- `ProviderExecutionStatus(StrEnum)` — — [строка 85]
- `TribunalExecutionEnvelope()` — — [строка 93]
- `ProviderExecutionReceipt()` — — [строка 140]
- `TribunalProviderTransport(Protocol)` — — [строка 167]
  - `invoke(self, *, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, timeout_seconds: float) -> Mapping[str, Any]` — —
- `LogicalToolProviderTransport()` — Adapter from RoleProviderBinding to the harness logical-tool runtime. [строка 171]
  - `invoke(self, *, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, timeout_seconds: float) -> Mapping[str, Any]` — —
- `SubprocessJsonProviderTransport()` — Real process boundary used by E2E and local adapters. [строка 196]
  - `invoke(self, *, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, timeout_seconds: float) -> Mapping[str, Any]` — —
- `PluginBridgeProviderTransport()` — Native OpenCode plugin transport for Tribunal. [строка 234]
  - `invoke(self, *, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, timeout_seconds: float) -> Mapping[str, Any]` — —
- `JobCtlLiveDialogueAdapter()` — — [строка 1000]
  - `execute_question(self, *, parent_state_path: str | Path, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, current_preflight: Mapping[str, Any], transport: TribunalProviderTransport, contract: DialecticQuestionContract, disclosure: DialecticDisclosureContract, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[InquiryTurn, ProviderExecutionReceipt]` — —
  - `execute_answer(self, *, parent_state_path: str | Path, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, current_preflight: Mapping[str, Any], transport: TribunalProviderTransport, contract: DialecticQuestionContract, disclosure: DialecticDisclosureContract, question_turn: InquiryTurn, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[InquiryTurn, ArgumentArtifact, ProviderExecutionReceipt]` — —
  - `execute_defense(self, *, parent_state_path: str | Path, binding: RoleProviderBinding, envelope: TribunalExecutionEnvelope, current_preflight: Mapping[str, Any], transport: TribunalProviderTransport, contract: AdvocateDefenseContract, disclosure: DialecticDisclosureContract, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> tuple[AdvocateResponse, ProviderExecutionReceipt]` — —

### `scripts/researcher/researcher_core/tribunal_provider_binding.py`

- `load_provider_binding_policy(path: Path) -> TribunalProviderBindingPolicy` — — [строка 163]
- `compile_role_provider_binding(*, contract_id: EntityId, run_id: EntityId, expected_role_id: str, requested_role_id: str | None, execution_kind: RoleExecutionKind, composition_policy: TribunalCompositionPolicy, binding_policy: TribunalProviderBindingPolicy, providers_authority: Mapping[str, Any], runtime_bindings: Mapping[str, Any], preflight: Mapping[str, Any], capability_policy_hash: str, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime, requested_provider_id: str | None = None, requested_executor_count: int = 1) -> RoleProviderBinding` — — [строка 204]
- `compile_question_provider_binding(*, contract: DialecticQuestionContract, requested_role_id: str | None, **kwargs: Any) -> RoleProviderBinding` — — [строка 375]
- `compile_answer_provider_binding(*, contract: DialecticQuestionContract, target_argument: ArgumentArtifact, requested_role_id: str | None, **kwargs: Any) -> RoleProviderBinding` — — [строка 391]
- `compile_defense_provider_binding(*, contract: AdvocateDefenseContract, requested_role_id: str | None, **kwargs: Any) -> RoleProviderBinding` — — [строка 411]
- `compile_first_pass_provider_binding(*, contract: InquiryContract, requested_role_id: str | None, **kwargs: Any) -> RoleProviderBinding` — — [строка 427]
- `validate_role_provider_binding_integrity(binding: RoleProviderBinding) -> None` — — [строка 443]
- `assert_binding_execution_ready(binding: RoleProviderBinding, current_preflight: Mapping[str, Any]) -> None` — — [строка 474]
- `role_provider_binding_to_dict(binding: RoleProviderBinding) -> dict[str, Any]` — — [строка 485]
- `role_provider_binding_from_dict(payload: Mapping[str, Any]) -> RoleProviderBinding` — — [строка 518]
- `TribunalProviderBindingError(RuntimeError)` — — [строка 32]
- `RoleExecutionKind(StrEnum)` — — [строка 36]
- `ProviderBindingStatus(StrEnum)` — — [строка 43]
- `ProviderBindingReason(StrEnum)` — — [строка 51]
- `TribunalProviderBindingPolicy()` — — [строка 67]
- `RoleProviderBinding()` — — [строка 83]

### `scripts/researcher/researcher_core/tribunal_role_handbook.py`

- `load_role_handbook(path: Path, policy: TribunalCompositionPolicy) -> TribunalRoleHandbook` — — [строка 145]
- `compile_role_instruction_pack(*, role_id: str, variant: RoleVariantKind, handbook: TribunalRoleHandbook, policy: TribunalCompositionPolicy) -> RoleInstructionPack` — — [строка 213]
- `validate_role_instruction_pack_integrity(pack: RoleInstructionPack) -> None` — — [строка 266]
- `role_instruction_pack_to_dict(pack: RoleInstructionPack) -> dict[str, Any]` — — [строка 286]
- `handbook_fill_requests_for_plan(*, plan: TribunalCompositionPlan, work_field: ReviewWorkField, lineage: TribunalLineageProfile, handbook: TribunalRoleHandbook, policy: TribunalCompositionPolicy, required_variant: RoleVariantKind = RoleVariantKind.FIRST_PASS) -> tuple[RoleHandbookFillRequest, ...]` — — [строка 306]
- `draft_handbook_entry_skeleton(request: RoleHandbookFillRequest) -> dict[str, Any]` — Generate a non-admitted YAML-ready skeleton from code-owned facts. [строка 353]
- `TribunalRoleHandbookError(RuntimeError)` — — [строка 31]
- `RoleVariantKind(StrEnum)` — — [строка 35]
- `RoleVariantSpec()` — — [строка 43]
- `RoleHandbookEntry()` — — [строка 55]
- `TribunalRoleHandbook()` — — [строка 77]
- `RoleInstructionPack()` — — [строка 89]
- `RoleHandbookFillRequest()` — — [строка 122]

### `scripts/researcher/researcher_core/tribunal_role_runtime.py`

- `TribunalRoleRuntimeError(RuntimeError)` — — [строка 39]
- `TribunalRoleWorker(Protocol)` — — [строка 43]
  - `execute(self, *, contract: InquiryContract, evidence_slice: TribunalEvidenceSlice, instruction: RoleInstructionPack) -> RoleWorkerDraft` — —
- `TribunalRoleExecutionResult()` — — [строка 50]
- `JobCtlTribunalRoleAdapter()` — Execute one role as one child Job with one first-pass Attempt. [строка 65]
  - `child_state_path(self, child_job_id: str) -> Path` — —
  - `execute(self, *, parent_state_path: str | Path, contract: InquiryContract, evidence_slice: TribunalEvidenceSlice, worker: TribunalRoleWorker, instruction: RoleInstructionPack, id_factory: EntityIdFactory, actor: ActorRef, created_at: datetime) -> TribunalRoleExecutionResult` — —

### `scripts/researcher/researcher_core/uncertainty.py`

- `parse_uncertainty(text: str) -> tuple[Decimal, Decimal] | None` — — [строка 16]
- `values_overlap(a_val: Decimal, a_unc: Decimal, b_val: Decimal, b_unc: Decimal) -> bool` — — [строка 32]
- `compare_with_uncertainty(claim_val: Decimal, claim_unc: Decimal | None, source_val: Decimal, source_unc: Decimal | None) -> str` — — [строка 43]

### `scripts/researcher/researcher_core/uncertainty_field.py`

- `components_from_relation_assessment(assessment: RelationAssessment) -> tuple[UncertaintyComponent, ...]` — Project typed uncertainty axes from one canonical relation assessment. [строка 229]
- `component_from_numeric_uncertainty(*, target_id: EntityId, value: Decimal, uncertainty: Decimal | None, reference_value: Decimal | None = None, reference_uncertainty: Decimal | None = None, required_for_decision: bool = False) -> UncertaintyComponent` — Project numeric uncertainty without inventing universal percentage thresholds. [строка 319]
- `component_from_gap(gap: Gap) -> UncertaintyComponent` — — [строка 379]
- `component_from_conflict(conflict: Conflict) -> UncertaintyComponent` — — [строка 409]
- `build_uncertainty_profile(*, target_id: EntityId, target_revision: int | None, components: Sequence[UncertaintyComponent], id_factory: EntityIdFactory, actor: ActorRef, run_id: EntityId, created_at, metadata: Mapping[str, Any] | None = None) -> UncertaintyProfile` — — [строка 425]
- `build_review_work_field(*, request_id: EntityId, profiles: Sequence[UncertaintyProfile], gaps: Sequence[Gap] = (), conflicts: Sequence[Conflict] = (), relation_assessments: Sequence[RelationAssessment] = (), id_factory: EntityIdFactory, actor: ActorRef, run_id: EntityId, created_at, metadata: Mapping[str, Any] | None = None) -> ReviewWorkField` — — [строка 472]
- `uncertainty_profile_to_dict(profile: UncertaintyProfile) -> dict[str, Any]` — — [строка 554]
- `uncertainty_profile_from_dict(raw: Mapping[str, Any]) -> UncertaintyProfile` — — [строка 580]
- `review_work_field_to_dict(field: ReviewWorkField) -> dict[str, Any]` — — [строка 605]
- `review_work_field_from_dict(raw: Mapping[str, Any]) -> ReviewWorkField` — — [строка 635]
- `UncertaintyFieldError(ValueError)` — — [строка 33]
- `UncertaintyAxis(StrEnum)` — — [строка 37]
- `UncertaintyLevel(StrEnum)` — — [строка 51]
- `UncertaintyOrigin(StrEnum)` — — [строка 59]
- `AssessmentMethod(StrEnum)` — — [строка 66]
- `ReviewReadiness(StrEnum)` — — [строка 83]
- `UncertaintyComponent()` — — [строка 91]
- `UncertaintyProfile()` — — [строка 119]
- `AssessmentNeed()` — — [строка 141]
- `ReviewWorkField()` — — [строка 167]
- `UncertaintyFieldRepository()` — Durable audit projection for profiles and review work fields. [строка 664]
  - `save_profile(self, profile: UncertaintyProfile) -> None` — —
  - `save_work_field(self, field: ReviewWorkField) -> None` — —
  - `load_profile(self, profile_id: EntityId) -> UncertaintyProfile | None` — —
  - `load_work_field(self, field_id: EntityId) -> ReviewWorkField | None` — —

### `scripts/researcher/run_pipeline.py`

- `run_pipeline(query: str, out_dir: Path, max_extract: int = 2) -> dict` — — [строка 69]
- `main() -> int` — — [строка 153]
- `PipelineLogger()` — — [строка 34]
  - `log(self, action: str, result: str, note: str = '') -> None` — —

## Router

### `scripts/router/build_skill_graph.py`

- `build() -> dict` — — [строка 7]
- `main() -> int` — — [строка 11]

### `scripts/router/build_task_plan.py`

- `repo_root() -> Path` — — [строка 10]
- `build_task_plan(task_text: str) -> dict` — — [строка 25]
- `main() -> int` — — [строка 65]

### `scripts/router/capability_escalation.py`

- `main()` — — [строка 6]

### `scripts/router/capability_preflight.py`

- `repo_root() -> Path` — — [строка 10]
- `load_json(rel: str) -> dict` — — [строка 13]
- `probe_provider(provider: dict, network: bool = True) -> dict` — — [строка 65]
- `snapshot(network: bool = True) -> dict` — — [строка 82]
- `main() -> int` — — [строка 103]

### `scripts/router/compile_capability_runtime.py`

- `root() -> Path` — — [строка 6]
- `read(rel)` — — [строка 7]
- `canon(x)` — — [строка 8]
- `validate(base, caps, prov, stages, tools)` — — [строка 10]
- `main() -> int` — — [строка 60]

### `scripts/router/compile_runtime.py`

- `repo_root() -> Path` — — [строка 18]
- `read_json(path: Path) -> dict` — — [строка 22]
- `canonical_bytes(obj: Any) -> bytes` — — [строка 26]
- `sha256_obj(obj: Any) -> str` — — [строка 30]
- `load_sources(root: Path | None = None) -> tuple[dict, dict[str, dict]]` — — [строка 38]
- `validate_sources(s: dict[str, dict]) -> list[str]` — — [строка 50]
- `build_graph(snapshot: dict) -> dict` — — [строка 146]
- `build_snapshot(s: dict[str, dict]) -> dict` — — [строка 212]
- `compatibility_artifacts(snapshot: dict) -> dict[str, dict]` — — [строка 249]
- `compile_runtime(root: Path | None = None, write: bool = True) -> dict` — — [строка 280]
- `main() -> int` — — [строка 298]

### `scripts/router/resolve_bundle.py`

- `root() -> Path` — — [строка 6]
- `read(rel)` — — [строка 7]
- `load_module(path, name)` — — [строка 8]
- `choose_stage(route_cfg: dict, text: str, requested: str | None) -> str` — — [строка 11]
- `resolve_bundle(task: str, route_id = None, stage = None, profile = None, preflight_path = None)` — — [строка 39]
- `main() -> int` — — [строка 77]

### `scripts/router/resolve_capsules.py`

- `root() -> Path` — — [строка 11]
- `load(name: str) -> dict` — — [строка 15]
- `resolve(route_id: str) -> dict` — — [строка 19]
- `main() -> int` — — [строка 39]

### `scripts/router/resolve_mcp_capsule.py`

- `root() -> Path` — — [строка 11]
- `load(name: str) -> dict` — — [строка 15]
- `resolve(route_id: str) -> dict` — — [строка 19]
- `main() -> int` — — [строка 32]

### `scripts/router/resolve_route.py`

- `repo_root() -> Path` — — [строка 9]
- `load_snapshot() -> dict` — — [строка 13]
- `match_routes(task_text: str, routes: dict) -> list[tuple[str, dict, int]]` — — [строка 23]
- `resolve(task_text: str, hints: dict | None = None) -> dict` — — [строка 53]
- `main() -> int` — — [строка 143]

### `scripts/router/resolve_tool_capsule.py`

- `root() -> Path` — — [строка 11]
- `load(name: str) -> dict` — — [строка 15]
- `resolve(route_id: str) -> dict` — — [строка 19]
- `main() -> int` — — [строка 41]

### `scripts/router/split_claims.py`

- `repo_root() -> Path` — — [строка 10]
- `load_json(name: str) -> dict` — — [строка 14]
- `split_units(text: str) -> list[str]` — — [строка 18]
- `detect_kind(text: str, claim_kinds: dict) -> tuple[str, list[str]]` — Return highest-priority matching kind and all matches for auditability. [строка 24]
- `make_claim_id(index: int) -> str` — — [строка 36]
- `split_claims(task_text: str) -> dict` — — [строка 40]
- `main() -> int` — — [строка 67]

## Scripts

### `scripts/add_skill.py`

- `repo_root() -> Path` — — [строка 31]
- `read_json(p: Path) -> dict` — — [строка 35]
- `write_json(p: Path, data: dict) -> None` — — [строка 39]
- `normalize_name(raw: str) -> str` — — [строка 43]
- `find_skill_dir(root: Path, name: str) -> Path | None` — — [строка 47]
- `validate_skill(skill_dir: Path, name: str) -> list[str]` — — [строка 55]
- `add_to_registry(reg: dict, name: str, cls: str) -> bool` — — [строка 71]
- `add_to_capsule(caps: dict, name: str, capsule: str) -> bool` — — [строка 86]
- `add_to_route_map(route_map: dict, route: str, name: str) -> bool` — — [строка 99]
- `run_graph_build(root: Path) -> bool` — — [строка 112]
- `run_route_check(root: Path, route: str | None) -> bool` — — [строка 122]
- `sync_live(root: Path, name: str) -> None` — — [строка 138]
- `main() -> int` — — [строка 150]

### `scripts/fix_paths.py`

- `load_json(path: Path) -> dict` — — [строка 13]
- `resolve_env(value: str) -> str` — Resolve ${VAR} patterns. [строка 17]
- `scan_files(root: Path, extensions: list, exclude_dirs: list) -> list[Path]` — — [строка 25]
- `fix_file(filepath: Path, mappings: list, dry_run: bool = True, backup: bool = True) -> tuple[bool, int]` — — [строка 35]
- `main() -> int` — — [строка 61]

### `scripts/health_check.py`

- `harness_root() -> Path` — — [строка 13]
- `check_plugin_loaded() -> tuple[bool, str]` — — [строка 34]
- `check_mcp_definitions() -> tuple[bool, str]` — — [строка 62]
- `check_guard_running() -> tuple[bool, str]` — — [строка 72]
- `check_db_accessible() -> tuple[bool, str]` — — [строка 83]
- `main() -> int` — — [строка 98]

### `scripts/register_plugin.py`

- `harness_root() -> Path` — — [строка 14]
- `register() -> int` — — [строка 44]
- `unregister() -> int` — — [строка 57]
- `main() -> int` — — [строка 67]

### `scripts/run_researcher_acceptance.py`

- `env() -> dict[str, str]` — — [строка 41]
- `run(argv: list[str]) -> int` — — [строка 51]
- `main() -> int` — — [строка 56]

### `scripts/start_mcp_servers.py`

- `load_json(path: Path) -> dict` — — [строка 19]
- `resolve_env(value: str) -> str` — — [строка 23]
- `validate_server(name: str, cfg: dict) -> tuple[bool, str]` — — [строка 41]
- `main() -> int` — — [строка 63]

### `scripts/sync_to_live.py`

- `repo_root() -> Path` — — [строка 27]
- `live_root() -> Path` — — [строка 31]
- `plan_copy(src_root: Path, dst_root: Path, rel: str, pattern: str, dst_rel: str | None = None) -> list[tuple[Path, Path]]` — — [строка 35]
- `main() -> int` — — [строка 47]

### `scripts/validate_env.py`

- `load_json(path: Path) -> dict` — — [строка 11]
- `validate_writer_core(repo_root: Path) -> list[str]` — Validate native Writer Core locations without importing optional packages. [строка 21]
- `validate_env() -> int` — — [строка 79]
- `main() -> int` — — [строка 122]

## Writer Core

### `scripts/writer-core/consolidation.py`

- `collect_version(path: str, max_paragraphs: int = 100) -> dict` — Одна версия -> агрегаты для эволюционного отчёта. [строка 162]
- `collect_corpus(version_files: list[dict], max_paragraphs: int = 100) -> list[dict]` — Все версии из version_files=[{"version","path"}, ...] -> list[dict]. [строка 329]
- `discover_versions(versions_dir: str) -> dict` — Найти версии Автореферата в каталоге. [строка 382]
- `compute_evolution(versions: list[dict]) -> dict` — Эволюция корпуса версий: попарные дельты + суммарный тренд. [строка 550]
- `version_similarity(versions: list[dict]) -> dict` — Попарный cosine между средними векторами версий. [строка 588]
- `write_report(evolution: dict, versions: list[dict]) -> None` — Сохранить эволюционный отчёт: evolution_report.json + evolution_summary.md. [строка 800]

### `scripts/writer-core/corpus_runner.py`

- `extract_document(path: str) -> str` — Extract plain text from a document. Raises on unsupported/unreadable files. [строка 60]
- `run_corpus(paths: list[str], max_sentences: int = 200, use_llm: bool = False, report_path: str | None = None) -> dict` — Run the full corpus pipeline over `paths`. [строка 121]

### `scripts/writer-core/digest_builder.py`

- `build_digest(text: str) -> LinguisticDigest` — — [строка 35]
- `affordance_set_for(sentence: str) -> AffordanceSet` — Adaptive control hook: build AffordanceSet from digest issues. [строка 153]

### `scripts/writer-core/graph_builder_hybrid.py`

- `load_graph_registry(path: str | None = None) -> dict[str, dict]` — Загрузить graph_registry.yaml v0.3 -> {graph_id: {topology, [строка 56]
- `validate_against_registry(graphs_dict: dict, registry: dict) -> list[dict]` — Проверка всех узлов/рёбер против реестра. Возвращает список нарушений. [строка 787]
- `build_paragraph_graphs(artifact: dict, registry: dict | None = None) -> dict` — Построить графы реестра v0.3 из гибридного артефакта параграфа. [строка 807]
- `graph_stats(graphs_dict: dict) -> dict` — По каждому графу: число узлов/рёбер (для отчёта). [строка 844]
- `to_sqlite(graphs_dict: dict, conn: sqlite3.Connection) -> None` — Сохранить узлы/рёбра в SQLite (таблицы graph_nodes, graph_edges). [строка 857]

### `scripts/writer-core/graph_vector.py`

- `vector_schema() -> list[str]` — Порядок фичей в числовом векторе (CONTRACT: фиксирован, dim = 89). [строка 187]
- `extract_graph_features(paragraph_artifact: dict) -> dict[str, float]` — Артефакт/графы параграфа -> dict {feature_name: float}. [строка 376]
- `vectorize(paragraph_artifact: dict) -> list[float]` — Артефакт/графы -> числовой вектор длины len(vector_schema()). [строка 485]
- `cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float` — Стандартный косинус. 0.0 для нулевых векторов. [строка 495]
- `paragraph_similarity(a: dict, b: dict) -> float` — Схожесть двух артефактов/графов параграфа: vectorize -> cosine. [строка 512]
- `dynamic_metrics(artifact_old: dict, artifact_new: dict) -> dict` — Разница метрик двух версий одного параграфа (new - old). [строка 533]
- `section_profile_match(paragraph_artifact: dict, etalon_stats: dict) -> dict` — Сопоставить параграф с эталонными профилями секций. [строка 613]
- `compute_etalon_profiles(etalon: Any, out_path: str | None = None, exclude_idx: int | None = None) -> dict` — Средние векторы по секциям из diag/etalon_sections.json. [строка 661]
- `loo_section_accuracy(etalon: Any) -> dict` — Честный leave-one-out: точность матчинга параграф->секция. [строка 750]

### `scripts/writer-core/hybrid_extract.py`

- `hybrid_extract_paragraph(text: str, para_id: str, page: int | None = None) -> dict` — Гибридный артефакт параграфа: v2-детэкстракция + v0.3-дайджест. [строка 311]
- `hybrid_extract_document(path: str, max_paragraphs: int = 50, clean_md: bool = True) -> dict` — Документ → список гибридных артефактов по параграфам. [строка 445]

### `scripts/writer-core/md_clean.py`

- `clean_md(text: str) -> str` — Очистить markdown-автореферат от служебных блоков. [строка 173]
- `split_paragraphs_clean(text: str, min_chars: int = _MIN_PARAGRAPH_CHARS) -> list[str]` — Очищенный текст -> параграфы (по пустым строкам). [строка 219]

### `scripts/writer-core/polza_light.py`

- `list_models() -> list[str]` — Real polza model IDs (GET /api/v1/models). Fail-closed: [] on any error. [строка 85]
- `light_parse_term(text: str) -> dict[str, Any]` — Extract terms + definitions from a sentence. Fail-closed. [строка 277]
- `light_parse_formula(text: str) -> dict[str, Any]` — Extract formulas / numeric constructs from a sentence. Fail-closed. [строка 292]
- `light_guard_verdict(text: str) -> dict[str, Any]` — Guard gate: PASS / NEEDS_REVIEW / BLOCK. Fail-closed -> BLOCK. [строка 307]

### `scripts/writer-core/registry_loader.py`

- `get_registries() -> Registries` — — [строка 80]
- `Registries()` — — [строка 50]
  - `search(self, entry: str) -> tuple[str, str]` — First matching lexicon expression contained in entry.

### `scripts/writer-core/rtt_compare.py`

- `compare(source: str, candidate: str) -> RTTResult` — — [строка 20]
- `compare_contract(contract_claim: dict, candidate: str) -> RTTResult` — Compare one handoff-style claim contract with its realization. [строка 108]

### `scripts/writer-core/session_memory.py`

- `default_memory() -> dict` — Свежая дефолтная структура (глубокая копия — вызывающий может мутировать). [строка 71]
- `load(path: str = MEMORY_PATH) -> dict` — Вернуть память как dict. Если файла нет — вернуть дефолтную структуру. [строка 76]
- `save(mem: dict, path: str = MEMORY_PATH) -> dict` — Записать память в JSON (utf-8, ensure_ascii=False) и обновить updated_at. [строка 88]
- `add_entry(key: str, value, path: str = MEMORY_PATH) -> dict` — Дозапись в mem['entries'] под ключом '<дата>:<секция>' + сохранение. [строка 102]
- `get(key_section: str, mem: dict | None = None, path: str = MEMORY_PATH)` — Вернуть последнюю запись секции (dict/list) или None. [строка 122]

### `scripts/writer-core/structure_annotator.py`

- `classify_heading(text: str) -> str | None` — Тип секции по заголовочной сигнатуре (regex по эталону). [строка 292]
- `classify_content(text: str, claims: list[dict] | None = None, objects: list[dict] | None = None) -> tuple[str, float] | None` — Эвристика типа секции по содержимому параграфа (без заголовка). [строка 309]
- `classify_paragraph(text: str, claims: list[dict] | None = None, objects: list[dict] | None = None) -> tuple[str, float]` — Тип секции произвольного параграфа. [строка 324]
- `build_document_tree(doc_artifact: dict) -> dict` — G1-дерево документа: Document -> Section -> Paragraph. [строка 349]
- `build_writing_plan(tree: dict) -> dict` — G2-Writing Decomposition DAG для секций дерева. [строка 429]
- `fill_slots(tree: dict, doc_artifact: dict) -> dict` — Сверка фактического содержания секций со слотами плана. [строка 585]
- `annotate_document(path: str, max_paragraphs: int = 100) -> dict` — Полный пайплайн разметки: extract -> tree -> plan -> slots. [строка 684]
- `compare_with_etalon(tree: dict, etalon_path: str | None = None) -> dict` — Сверка размеченного дерева с эталонной структурой. [строка 770]

### `scripts/writer-core/t0_ru.py`

- `analyze_sentence(text: str) -> T0Sentence` — — [строка 191]
- `split_sentences(text: str) -> list[str]` — — [строка 250]
- `build_scope_field(s: T0Sentence) -> dict[str, Any]` — Scope structure per LinguisticDigest schema (dict payload). [строка 254]
- `T0Sentence()` — — [строка 135]
  - `force_rank(self) -> int` — —

### `scripts/writer-core/v2_extractor/c1_c2_structure.py`

- `classify_block(text: str, first_line: str = '') -> str` — Типизация блока по содержанию (контентный классификатор, не layout). [строка 84]
- `extract_blocks_reading_order(path: Path) -> list[CanonicalBlock]` — Блоки в порядке чтения: top-to-bottom, left-to-right по bbox. [строка 101]
- `build_canonical(path: Path, doc_id: str) -> CanonicalDocument` — — [строка 189]
- `init_db(conn: sqlite3.Connection) -> None` — — [строка 252]
- `store_canonical(doc: CanonicalDocument, conn: sqlite3.Connection) -> None` — — [строка 257]
- `run(path: Path, db_path: Path | None, doc_id: str) -> dict` — — [строка 278]
- `CanonicalBlock()` — — [строка 22]
- `CanonicalDocument()` — — [строка 33]

### `scripts/writer-core/v2_extractor/c5_number.py`

- `extract_quantities(sentences: list[str]) -> list[Quantity]` — — [строка 90]
- `extract_from_sentences(sentences: list[str]) -> list[dict]` — — [строка 151]
- `Quantity()` — — [строка 46]

### `scripts/writer-core/v2_extractor/claim_qa.py`

- `span_grounded(claim_text: str, source_text: str, threshold: float = 0.7) -> bool` — Проверка: ядро claim-текста реально присутствует в источнике. [строка 120]
- `span_locate(claim_text: str, source_text: str, threshold: float = 0.7) -> dict` — Найти ТОЧНЫЙ span (start/end) claim в источнике + способ (exact|fuzzy|none). [строка 126]
- `classify_claim(text: str, fallback_kind: str = 'OBSERVATIONAL') -> dict` — Детерминированная типизация claims (не полагаемся на LLM). [строка 183]
- `qa_claims(claims: list[dict], source_text: str) -> tuple[list[QAVerdict], list[dict]]` — Пропустить claims через QC. Вернуть (verdicts, keep_only_grounded). [строка 216]
- `qa_objects(objects: list[dict], source_text: str) -> list[dict]` — QC объектов: каждый raw обязан присутствовать в тексте (нормализованно). [строка 240]
- `to_yaml(verdicts: list[QAVerdict], keep: list[dict]) -> str` — — [строка 256]
- `QAVerdict()` — — [строка 205]

### `scripts/writer-core/v2_extractor/context_analyzer.py`

- `get_context(text: str, start: int, end: int, window: int = 5) -> Context` — Собрать окрестность span (как context_before/after в EvidenceSpan). [строка 34]
- `has_marker_in_window(ctx: Context, markers: tuple[str, ...], window: int = 5) -> str | None` — Есть ли источник/маркер в ОКРЕСТНОСТИ (before+after слова, не всё предложение). [строка 81]
- `is_rhetorical_repetition(word: str, sentence: str, ctx: Context) -> bool` — Проверить, реальный ли риторический повтор ИМЕННО этого слова (не чужой). [строка 104]
- `evidence_is_supported(ctx: Context, has_number: bool) -> bool` — Evidence-часть ХРИИ обоснована, если рядом источник (не просто число). [строка 129]
- `infer_case_from_context(word: str, ctx: Context) -> str | None` — Падеж по предлогу/следующему слову в окрестности (согласование), не по суффиксу. [строка 148]
- `connector_clean(ctx: Context, marker: str) -> bool` — Проверить, что маркер связки — настоящее слово (не внутри «карбидов»). [строка 159]
- `Context()` — Окрестность вокруг span: слова/токены до и после. [строка 25]
- `ContextVerdict()` — — [строка 169]

### `scripts/writer-core/v2_extractor/extraction_engine.py`

- `extract_object_b(text: str, para_id: str, si: int) -> list[dict]` — — [строка 87]
- `extract_discourse_c(text: str) -> list[dict]` — — [строка 134]
- `extract_style_d(text: str) -> list[dict]` — — [строка 155]
- `extract_claims_a(text: str, para_id: str = 'PAR_000') -> list[dict]` — Грубая эвристика claim-кандидатов (уровень A). Полная — LLM-капсула. [строка 175]
- `extract_all(text: str, para_id: str = 'PAR_000', page: int | None = None) -> ExtractionResult` — — [строка 218]
- `to_yaml(res: ExtractionResult) -> str` — — [строка 256]
- `ExtractionResult()` — — [строка 72]

### `scripts/writer-core/v2_extractor/graph_builder.py`

- `build_graphs(extraction: dict, philology: dict, para_id: str = 'PAR_000') -> dict` — — [строка 48]
- `store_graphs(conn, graphs: dict, para_id: str) -> None` — Сохранить узлы/рёбра в SQLite (таблицы graph_nodes, graph_edges). [строка 177]
- `to_yaml(graphs: dict) -> str` — — [строка 192]
- `GNode()` — — [строка 26]
- `GEdge()` — — [строка 34]

### `scripts/writer-core/v2_extractor/linguo_harness.py`

- `pos_of(word: str) -> str` — Определить часть речи по суффиксам (русский, научный корпус). [строка 44]
- `padezh(word: str) -> str | None` — Определить падеж существительного по суффиксу (грубо, научный корпус). [строка 62]
- `detect_connector(text: str) -> list[dict]` — Детерминированный словарь связок: (marker, type, span). [строка 85]
- `harness_analyze(text: str) -> LinguoHarnessResult` — — [строка 113]
- `to_dict(res: LinguoHarnessResult) -> dict` — — [строка 129]
- `LinguoHarnessResult()` — — [строка 106]

### `scripts/writer-core/v2_extractor/llm_contracts.py`

- `validate_item(item: Any, kind: str) -> dict | None` — Проверить один элемент контракта. Вернуть элемент (если ОК) или None. [строка 63]
- `validate_collection(raw: Any, kind: str) -> list[dict]` — Провалидировать массив элементов контракта (fail-closed). [строка 81]
- `validate_claims(raw: Any) -> list[dict]` — — [строка 93]
- `validate_scope(raw: Any) -> list[dict]` — — [строка 96]
- `validate_objects(raw: Any) -> list[dict]` — — [строка 99]
- `validate_figures(raw: Any) -> list[dict]` — — [строка 102]
- `validate_chreia(raw: Any) -> list[dict]` — — [строка 105]
- `validate_emphasis(raw: Any) -> list[dict]` — — [строка 108]
- `validate_llm_response(raw: dict) -> dict` — Валидировать полный ответ LLM (все секции). Fail-closed. [строка 116]
- `build_prompt(task: str, text: str, extra_context: str = '') -> str` — Собрать промпт для LLM по типу задачи (единый фасад). [строка 175]

### `scripts/writer-core/v2_extractor/llm_extractor.py`

- `extract_claims_llm(text: str, max_tokens: int = 1500) -> list[dict]` — — [строка 73]
- `extract_scope_llm(text: str, max_tokens: int = 800) -> list[dict]` — — [строка 86]
- `extract_objects_llm(text: str, max_tokens: int = 800) -> list[dict]` — — [строка 99]
- `enrich(text: str) -> dict` — — [строка 112]

### `scripts/writer-core/v2_extractor/llm_philology.py`

- `extract_language_llm(text: str, harness_context: dict | None = None, max_tokens: int = 1200) -> dict` — gemma с контрактом + few-shot через build_prompt; harness как справка. [строка 30]
- `validate_language_llm(raw: dict, text: str) -> dict` — QC-подтверждение: только exact-цитаты (фигура = точная цитата). [строка 45]
- `enrich_language(text: str, harness_context: dict | None = None) -> dict` — — [строка 66]

### `scripts/writer-core/v2_extractor/philologcal_layer.py`

- `analyze(text: str) -> PhilologicalResult` — — [строка 224]
- `to_yaml(res: PhilologicalResult) -> str` — — [строка 237]
- `PhilologicalResult()` — — [строка 216]

### `scripts/writer-core/v2_extractor/unified.py`

- `unified_extract(text: str, para_id: str = 'PAR', page: int | None = None, use_llm: bool = True) -> dict` — Полный конвейер: детерминированный + LLM + QC → графы. [строка 59]
- `to_yaml(result: dict) -> str` — — [строка 271]

### `scripts/writer-core/wc_cli.py`


### `scripts/writer-core/weak_llm.py`

- `reload_default_threshold() -> float` — Re-read the calibration file and refresh DEFAULT_THRESHOLD in place. [строка 47]
- `propose_variants(source: str) -> list[dict[str, str]]` — Return validated variants. Fail-closed: on any failure returns a single [строка 167]
- `ground_span(source: str, variant: str | dict[str, str], threshold: float | None = None) -> dict[str, Any]` — Span grounding: CODE computes overlap, never the LLM. [строка 189]

### `scripts/writer-core/writer_core/__init__.py`


### `scripts/writer-core/writer_core/canon.py`

- `split_dom(dom: dict) -> dict` — DOM -> {canon_data, canon_knowledge} (детерминированно). [строка 28]
- `canon_brief(dom: dict) -> dict` — Сводка канонов для брифа article-writer (что нельзя менять / что можно писать). [строка 106]

### `scripts/writer-core/writer_core/cli.py`

- `cmd_plan(args: argparse.Namespace) -> int` — plan: (--doc | --bundle) -> structure_plan.json (G1+G2+slots+gaps). [строка 85]
- `cmd_draftcheck(args: argparse.Namespace) -> int` — draftcheck: draft.md + writing_contract.json -> rtt_report.json. [строка 165]
- `cmd_live_cycle(args: argparse.Namespace) -> int` — live-cycle: весь контур кодекра bundle->contract->draft->rtt->repair. [строка 193]
- `cmd_extract(args: argparse.Namespace) -> int` — extract: doc -> artifact.json (hybrid_extract_document). [строка 220]
- `cmd_graphs(args: argparse.Namespace) -> int` — graphs: artifact -> graphs.json (+ sqlite). [строка 234]
- `cmd_annotate(args: argparse.Namespace) -> int` — annotate: doc -> structure_plan.json (structure_annotator). [строка 292]
- `cmd_consolidate(args: argparse.Namespace) -> int` — consolidate: versions dir -> evolution_report.json/.md. [строка 322]
- `cmd_vectorsim(args: argparse.Namespace) -> int` — vectorsim: --a --b -> cosine + dynamic_metrics. [строка 360]
- `cmd_dom(args: argparse.Namespace) -> int` — dom: plan/claims/графы writer_core -> DOM YAML для citation_trace. [строка 434]
- `cmd_review(args: argparse.Namespace) -> int` — review: --draft --contract [--plan] [--dom] -> review_report.json. [строка 511]
- `cmd_uncertainty(args: argparse.Namespace) -> int` — uncertainty: --dom -> research debt (PROVISIONAL/tentative_only + requests). [строка 545]
- `cmd_register(args: argparse.Namespace) -> int` — register: контроль научного регистра (R1-R4). [строка 569]
- `build_parser() -> argparse.ArgumentParser` — — [строка 599]
- `main(argv: list[str] | None = None) -> int` — — [строка 731]

### `scripts/writer-core/writer_core/contracts.py`

- `content_sha256(content: str | bytes) -> str` — sha256 содержимого (детерминированный хэш для версионирования). [строка 145]
- `research_bundle_from_artifact(artifact: dict) -> ResearchBundleLA` — Гибридный артефакт (документ {paragraphs:[...]} или параграф) -> ResearchBundleLA. [строка 200]
- `writer_contract_from_claim(claim: dict, digest: dict | None = None, default_scope: str = '', default_modality: str = 'assertive', default_causal: str = 'none') -> WriterContract` — claim (+digest из hybrid_extract) -> WriterContract. [строка 262]
- `SourceRef(BaseModel)` — Источник ResearchBundle: uri + человекочитаемый title. [строка 35]
- `BundleClaim(BaseModel)` — Утверждение ResearchBundle: proposition + происхождение (span/источник). [строка 42]
- `ResearchBundleLA(BaseModel)` — Упрощённый ResearchBundle (по образцу full ResearchBundleLA). [строка 52]
  - `to_contract_claims(self, default_scope: str = '', default_modality: str = 'assertive', default_causal: str = 'none') -> list['WriterContract']` — Каждый claim бандла -> WriterContract (для draftcheck/планирования).
- `WriterContract(BaseModel)` — Контракт на ОДНО утверждение (маппится из LinguisticDigest/claims). [строка 92]
- `Span(BaseModel)` — Абсолютный span в тексте черновика. [строка 118]
- `Defect(BaseModel)` — Дефект семантического RTT-диффа. [строка 125]
- `VersionedArtifact(BaseModel)` — Версионируемый артефакт: id + version + content_hash + created_at. [строка 156]
  - `create(cls, artifact_id: str, version: str, content: str | bytes, created_at: str | None = None) -> 'VersionedArtifact'` — Фабрика: считает content_hash из content (контрактно).

### `scripts/writer-core/writer_core/doc_com.py`

- `available() -> bool` — Есть ли Word COM (win32com) в среде. [строка 21]
- `extract_doc_text(path: str, timeout_s: int = 60) -> str` — Извлечь текст из .doc через Word COM (Content.Text -> str). [строка 30]
- `try_extract_doc_text(path: str) -> Optional[str]` — fail-closed версия: вернуть текст или None (без исключения наружу). [строка 68]

### `scripts/writer-core/writer_core/dom_builder.py`

- `load_template(template_path: str) -> dict` — YAML DOM-шаблон -> dict (копия-источник для build_dom). [строка 87]
- `plan_to_dom(plan: dict) -> dict` — structure_plan.json (наш plan --topic) -> DOM structure. [строка 115]
- `claims_to_dom(claims: list[dict]) -> list[dict]` — Наши claims (hybrid_extract: {text, qa_status, span}) -> DOM claims[]. [строка 204]
- `graphs_to_dom(graphs: dict) -> list[dict]` — Наши графы (graph_builder_hybrid G3-G15) -> DOM graphs[]. [строка 282]
- `uncertainty_provenance(source_kind: str) -> dict` — Неопределённость ПО ПРОИСХОЖДЕНИЮ источника -> {level, note, provenance}. [строка 328]
- `build_dom(template_path: str, plan: dict | None = None, claims: list[dict] | None = None, graphs: dict | None = None, source_kinds: list[str] | None = None, qwen_extra: dict | None = None, out_path: str | None = None) -> dict` — Собрать DOM YAML по контракту из нашего слоя и (опц.) сохранить. [строка 370]
- `validate_dom(dom: dict) -> list[str]` — Самопроверка DOM по контракту (product, structure.chapters, id уникальны). [строка 456]
- `qwen_to_dom(yaml_paths: list[str]) -> dict` — Qwen_yaml карточки статей -> DOM-блоки {sources, claims, graphs, uncertainty}. [строка 512]
- `qa_uncertainty(qa_text: str, claims: list[dict]) -> dict` — Q&A автореферата (маркировка автора) -> override uncertainty для claims. [строка 575]

### `scripts/writer-core/writer_core/factory_process.py`

- `extract_draft_claims(draft_text: str, max_paragraphs: int = 100) -> dict` — Re-extraction черновика: claims с ГЛОБАЛЬНЫМИ span'ами. [строка 108]
- `match_contract_claims(contract_claims: list[dict], draft_claims: list[dict]) -> list[dict]` — Каждый contract claim -> лучший draft claim по пересечению токенов. [строка 155]
- `draftcheck(draft_text: str, contract_claims: list[dict]) -> dict` — Полный RTT-дифф черновика против контракта. [строка 203]
- `apply_span_repair(text: str, start: int, end: int, defect_type: str) -> str` — Применить правила ремонта ТОЛЬКО внутри [start, end) текста. [строка 329]
- `apply_constrained_repair(draft_text: str, defects: list[dict]) -> dict` — Ремонт ТОЛЬКО span'ов дефектов (defect_type + claim_id + span). [строка 350]
- `run_writer_cycle(draft_text: str, contract_claims: list[dict], max_iterations: int = 3) -> dict` — Цикл фабрики письма: draft -> draftcheck -> constrained repair -> ... [строка 393]
- `load_contract_claims(contract: Any) -> list[dict]` — Нормализация writing_contract.json -> list[dict] WriterContract-полей. [строка 438]

### `scripts/writer-core/writer_core/linguistic_models.py`

- `Impact(str, Enum)` — — [строка 10]
- `LinguisticIssue(_StrictModel)` — — [строка 21]
- `AffordanceSet(_StrictModel)` — — [строка 30]
- `LinguisticDigest(_StrictModel)` — — [строка 40]

### `scripts/writer-core/writer_core/live_cycle.py`

- `research_bundle_from_path(version_path: str, max_paragraphs: int = 100) -> 'ResearchBundleLA'` — Документ (docx/pdf/md) -> ResearchBundleLA (роль v1 в контуре). [строка 97]
- `writer_contract_from_path(version_path: str, max_paragraphs: int = 100) -> list['WriterContract']` — Документ-эталон -> list[WriterContract] (роль v8: разрешённые claims). [строка 126]
- `select_section_registry(topic: str) -> tuple[dict, str]` — Выбор SECTION_REGISTRY по теме (детерминированно). [строка 152]
- `plan_from_topic(topic: str, section_order: list[str] | None = None) -> dict` — Тема -> structure_plan.json (каркас «дерева для заполнения блоками»). [строка 165]
- `run_live_cycle(bundle: Any, contract_path: Any, draft_text: str, max_contract_claims: int | None = 40, repair: bool = False) -> dict` — Полный «живой» цикл фабрики письма -> отчёт (dict). [строка 333]
- `write_report(report: dict, out_path: str) -> None` — Отчёт -> live_cycle_report.json (UTF-8, ensure_ascii=False). [строка 451]

### `scripts/writer-core/writer_core/register_control.py`

- `check_reference_pickup(text: str, dom: dict) -> list[dict]` — R1: числа и claims в тексте против DOM. Каждое число -> есть [C-]/[S-] в предложении. [строка 43]
- `check_register_vector(text: str, section: str | None, etalon_profiles: dict | None) -> list[dict]` — R2: 89-dim сходство текста с эталоном секции. [строка 70]
- `check_lexicon(text: str) -> list[dict]` — R3: канцелярит/причастность/разговорные против научной нормы. [строка 90]
- `check_tropes(text: str) -> list[dict]` — R4: отсутствие публицистических фигур/тропов в научной прозе. [строка 127]
- `register_check(text: str, dom: dict | None = None, etalon_profiles: dict | None = None) -> dict` — Полный register-control: 4 оси -> {verdict, issues_by_axis}. [строка 142]

### `scripts/writer-core/writer_core/review.py`

- `L1_PROOFREAD(text: str) -> list[dict]` — Микро-ревью (детерминированно): повторы, канцелярит, терминология, длина. [строка 302]
- `L2_EDITOR(plan_or_dom: Any, paragraphs: Any) -> list[dict]` — Мезо-ревью: gaps плана (незаполненные слоты), отсутствующие секции, [строка 444]
- `L3_REVIEWER(draft_text: str, contract_claims: Any, dom: Any = None) -> dict` — Макро-ревью: RTT-дифф (draftcheck) + traceability (citation_trace). [строка 620]
- `run_review_levels(draft_text: str, contract_claims: Any, plan: Any = None, dom: Any = None) -> dict` — L1 + L2 + L3 ПАРАЛЛЕЛЬНО -> {"L1": [...], "L2": [...], "L3": {...}}. [строка 684]
- `write_review_report(report: dict, out_path: str) -> None` — Отчёт -> review_report.json (UTF-8, ensure_ascii=False). [строка 780]
- `REVIEW_CYCLE(draft_path: str, contract_claims: Any, plan: Any = None, dom: Any = None, max_iterations: int = 3, max_contract_claims: int | None = None, out_path: str | None = None) -> dict` — Цикл ревью: draft -> L1/L2/L3 (параллельно) -> constrained repair -> ... [строка 789]

### `scripts/writer-core/writer_core/rtt.py`

- `RTTReason(StrEnum)` — — [строка 10]
- `RTTResult(BaseModel)` — Stable JSON-serializable sentence RTT result. [строка 36]

### `scripts/writer-core/writer_core/uncertainty_bridge.py`

- `analyze_uncertainty(dom: dict) -> dict` — DOM -> {status_map, research_requests, tentative_phrases} (детерминированно). [строка 46]
- `report_uncertainty(dom: dict, out_path: str | None = None) -> dict` — Обёртка: анализ + (опц.) сохранение JSON-отчёта. [строка 103]
