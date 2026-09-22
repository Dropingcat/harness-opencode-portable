# Tech Debt — отдельный учет для кодеров

> Техдолг ведется отдельно от фич. Смешение — главный источник "Fixes that Fail".

## 1. Принцип

- Техдолг — это контракт с Sunset Clause, а не TODO в голове. Нет записи в реестре → нет долга.
- Каждый долг имеет владельца (WP/агент), severity, триггер пересмотра и стоимость откладывания.
- Долг всегда привязан к конкретному противоречию или слабому месту из TRIZ/ARIZ (иначе это не долг, а хотелка).

## 2. Реестр: `config/tech_debt.json` (создать при первой записи)

```json
{
  "version": 1,
  "debts": [
    {
      "id": "TD-001",
      "title": "Хардкод /home/orangepi в mcp launchers",
      "area": "mcp/launchers/_runner.py, coder_router_server.py",
      "kind": "portability",
      "severity": "high",
      "introduced_in": "bundle pass 1",
      "contradiction": "portability vs speed — Linux paths ускоряли Pi, ломают Windows",
      "impact": "launchers не работают на Windows без env",
      "owner": "code-orchestrator",
      "created_at": "2026-08-31",
      "sunset_at": "2026-09-14",
      "review_trigger": "при подключении первого launcher в opencode.jsonc",
      "acceptance": "все paths через OPENCODE_BIN/OPENCODE_HARNESS_ROOT/OPENCODE_RUNS_DIR, py_compile + smoke pass",
      "cost_if_delayed": "блокирует сервис-делегаты и profile_config",
      "status": "open"
    }
  ]
}
```

Поля обязательны: `id`, `title`, `area`, `kind`, `severity`, `owner`, `sunset_at`, `acceptance`, `status`. `severity`: `critical|high|medium|low`.

## 3. Инвентарь на 2026-08-31 (из аудита bundle)

| ID | Долг | Area | Severity | Sunset | Владелец |
|---|---|---|---|---|---|
| TD-001 | Хардкод Linux путей | `mcp/launchers/_runner.py`, `mcp/coder_router_server.py`, `agents/*.md` | high | 2026-09-14 | code-orchestrator |
| TD-002 | Plugin hook не зарегистрирован в runtime | `plugins/tool-skill-contract-router.ts`, `opencode.jsonc` | high | 2026-09-07 | profile_config |
| TD-003 | Дублирование route данных (JSON vs TS) | `config/tool_skill_routes.json` vs `plugins/*.ts` | medium | 2026-09-14 | code-orchestrator |
| TD-004 | Guard env не прокинут (OPENCODE_SESSION_DB) | `config/guard_policy.json`, `plugins/*.ts` | high | 2026-09-07 | profile_config |
| TD-005 | Source-fetcher fallback не покрыт тестом | `agents/source-fetcher.md`, `mcp/academic_search_server.py` | medium | 2026-09-21 | code-tester |
| TD-006 | Отсутствует `config/tech_debt.json` файл | `config/` | low | 2026-09-07 | code-orchestrator |
| TD-007 | Нет единого `docs/` индекса (док-контроллер) | `README.md`, `MANIFEST.md`, `references/` | medium | 2026-09-14 | code-orchestrator |
| TD-008 | WP-0 контракты не сгенерированы как JSON Schema | `references/agent-kirpichik/CONTRACTS.md` | medium | 2026-09-21 | code-orchestrator |
| TD-009 | Runtime core не был импортирован в сам модуль | `shared/`, `scripts/code-factory/`, `W:\server2\scripts\code-factory` | critical | 2026-09-07 | code-orchestrator |
| TD-010 | Policy layer не доведен до machine-readable parity с researcher-core | `config/strictness_profiles.json`, `bucket_contracts.json`, `claim_state_machine.json`, `skills_registry.json` | high | 2026-09-07 | code-orchestrator |
| TD-011 | Router contracts дублируются между JSON/TS/docs | `config/*.json`, `plugins/tool-skill-contract-router.ts`, `ROUTER_HOOKS_AND_TEMPLATES.md` | high | 2026-09-14 | code-orchestrator |
| TD-012 | Memory policy не имеет schema/storage contract | `MEMORY_POLICY.md`, future memory registry | medium | 2026-09-21 | code-orchestrator |
| TD-013 | Guard degradation matrix не формализован по strictness profiles | `config/guard_policy.json`, future strictness profiles | high | 2026-09-14 | code-orchestrator |
| TD-014 | `MANIFEST.md` counts/critical inventory устаревают после каждой волны | `MANIFEST.md` | low | 2026-09-07 | code-orchestrator |

Правило: каждый новый TD должен ссылаться на источник (аудит, ревью, FMEA, triz_critic).

## 4. Workflow

Статус на 2026-08-31: TD-009 частично снят на уровне bundle — runtime импортирован в `doc_Opencode_agern/shared` и `doc_Opencode_agern/scripts/code-factory`, но live OpenCode ещё не переключён на module-owned runtime.

1. **Создать** долг: code-orchestrator или code-reviewer добавляет запись в `config/tech_debt.json` + пишет в Global Kanban (`phase=tech_debt`).
2. **Оценить** `cost_if_delayed`: что ломается, если откладывать (блок фичи, рост coupling, риск инъекции).
3. **Запланировать** `sunset_at` или `review_trigger` — что наступит раньше, то и триггер.
4. **Отработать**: воркер правит по `acceptance`, тестер прогоняет acceptance command, ревьюер проверяет.
5. **Закрыть**: статус `done` + запись в `GLOBAL_TASK_CONTROLLER.md` / kanban + пост-анализ: почему долг возник (архетип).

Запрещено: закрывать долг без acceptance команды; держать `critical` дольше одного спринта без эскалации.

## 5. Связь с трекерами

- **Global Kanban** (`references/global-kanban/global_kanban.py`) — оперативный статус: `gk.report('code-factory','TD-001','tech_debt','WORKING','fix','1/3','патч _runner.py')`.
- **WP-0…WP-4** (`references/agent-kirpichik/wp-*.md` + `workspace/агент кодер`) — структурные долги фундамента (WP-0) блокируют все остальные WP.
- **TRIZ** — долги с kind `architecture|contradiction` обязательно проходят через `triz_critic` 6 чеков.
- **Guard** — долги с kind `security` не закрываются без `doc_guard` PASS.

## 6. Definition of Done для техдолга

Долг считается закрытым только если:

- [ ] `acceptance` команда выполнена (py_compile / schema check / smoke test) с логом.
- [ ] Нет хардкодов/секретов в измененных файлах (secret scan).
- [ ] Обновлены `MANIFEST.md`, `TOOL_SKILL_CONTRACT_AUDIT.md` если менялся контракт.
- [ ] Запись в kanban переведена в `DONE` с сообщением.
- [ ] Пост-анализ: добавлен пункт в `references/agent-kirpichik/ARIZ_LIGHT_METHOD.md` или `CODER_DESIGN_PRINCIPLES.md` если паттерн повторяется.

## 7. Команды

```powershell
$harness = $env:OPENCODE_HARNESS_ROOT   # ASCII junction E:\opencode_harness

# создать реестр если нет
if (-not (Test-Path (Join-Path $harness "config\tech_debt.json"))) { New-Item -ItemType File -Path (Join-Path $harness "config\tech_debt.json") }

# проверить долги с просроченным sunset
python -c "import json,datetime,pathlib,os; p=pathlib.Path(os.environ['OPENCODE_HARNESS_ROOT'])/'config'/'tech_debt.json'; d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {'debts':[]}; print([x['id'] for x in d['debts'] if x['status']=='open'])"

# отчитаться в kanban
python -c "import sys,os; sys.path.insert(0, os.environ['OPENCODE_HARNESS_ROOT'] + os.sep + r'references\global-kanban'); from global_kanban import GlobalKanban; gk=GlobalKanban(db_path=os.environ['OPENCODE_HARNESS_ROOT'] + os.sep + '.kanban.db'); gk.report('code-factory','TD-001','tech_debt','WORKING','fix','1/1','патч путей')"
```

## 8. Researcher refactor debt added 2026-09-12

| ID | Долг | Area | Severity | Sunset | Владелец |
|---|---|---|---|---|---|
| TD-015 | Старые Guard/LocalCorpus baseline failures | `tests/researcher` / environment fixtures | medium | 2026-09-19 | researcher-orchestrator |
| TD-016 | Дубликат canonical `researcher_core` в корневом `resercher-core` | repository layout/import authority | medium | 2026-09-21 | researcher-orchestrator |
| TD-017 | `evidence.verify` перекрывается code-factory provider priority | capability/provider routing | high | 2026-09-16 | researcher-orchestrator |

Эти пункты не считаются частью R2.2 feature-completion и должны закрываться отдельными acceptance gates.

## 9. Researcher R2.3 invalidation debt added 2026-09-12

| ID | Долг | Area | Severity | Sunset | Владелец |
|---|---|---|---|---|---|
| TD-018 | Dependency records пока задаются явно, без канонического адаптера из provenance graph | `researcher_core/invalidation.py`, ResearchTraceLink/GraphEdge | medium | 2026-09-20 | researcher-orchestrator |
| TD-019 | `SourceCatalog` semantic change пока не порождает typed R2.3 invalidation trigger | Writer SourceCatalog -> Researcher bridge | high | 2026-09-18 | researcher-orchestrator |
| TD-020 | Full Researcher suite показывает SQLite `ResourceWarning` на незакрытые соединения | researcher repositories/tests | low | 2026-09-25 | researcher-orchestrator |

R2.3 feature-completion не закрывает TD-018..TD-020. Эти долги нужны именно потому, что первый slice намеренно ограничен детерминированной explicit-dependency моделью.


## Researcher debt update — R2.3.1

- **TD-018 DONE**: `provenance_dependencies.py` now derives `KnowledgeDependency` records from canonical `Source/EvidenceSpan`, `GraphEdge`, `ResearchTraceLink` and `ChallengeResolutionAssessment` provenance.
- **TD-019 DONE**: real Writer `SourceCatalog.upsert()` semantic updates feed typed Researcher impact and can selectively reopen the existing challenge branch; BYTE_ONLY updates do not reopen.
- **TD-021 OPEN**: Writer SourceCatalog still uses free-string source IDs while Researcher uses typed `SRC-*`; `SourceIdentityBinding` is an explicit fail-closed bridge until shared canonical identity/binding persistence is implemented.

## Researcher debt update — R2.3.3

- **TD-022 OPEN**: `GraphEdge` is now a versioned canonical relation with event-replayable lifecycle, but there is not yet a dedicated durable relation-state/history index. Current persistence can reuse generic event/state UoW; a relation-specific SQLite projector/query adapter is required before large-graph operational use.


## Researcher debt update — R3-L1

- **TD-023 OPEN**: restore/recovery is not yet a single automated acceptance command. During R3 start, the extracted working snapshot lacked `.git`; history was successfully reconstructed from the stored Git bundle plus ordered R2 patch chain. Add a restore verifier that checks `.git`, expected boundary/tree hashes and patch lineage before development resumes.
- **TD-024 OPEN**: peer delegation currently reuses `job_ctl` JSON child lifecycle but does not yet invoke live Coder/Writer orchestrator transport or a durable outbox/dispatch adapter. Domain contracts are ready; transport is deferred to R3-L4.
- **TD-025 PLANNED FEATURE BOUNDARY**: R3-L1 execution results are intentionally not canonical Claim/Evidence. R3.1 must add an admission bridge with validators/reducers rather than treating task success as epistemic success.


## Researcher debt update — R3.1

- **TD-025 DONE**: execution success is no longer the end of the epistemic boundary; R3.1 now provides typed proposal admission through deterministic validators and the canonical ClaimRegistry.
- **TD-026 OPEN**: legacy `LocalDocumentExtractionCapsule` emits `source_type=local_document` plus `sha256:`-prefixed content/text hashes, while current Source/Evidence admission validators accept the closed source vocabulary and raw 64-hex hashes. Do not silently rewrite legacy evidence. Reconcile the capsule output contract or validator vocabulary explicitly, with migration tests.
- **R3.2 PLANNED, not hidden debt**: post-admission SUPPORTS/QUANTIFIES/DERIVED_FROM edges and Derivation/Assumption admission are intentionally deferred until temp-ID/canonical-ID dependency mapping is explicit.

### TD-027 — R3.2 identity map depends on R0 accepted-ID ordering
**State:** OPEN
`AdmissionIdentityMap` reconstructs generated CLM/QTY temp->canonical identity from the deterministic grouping/order of `CommandResult.accepted_ids`. Correct for the current registry, but this is an implementation coupling.
**Target:** registry-native proposal-temp -> canonical-ID mapping in admission events/results with migration tests.

### TD-028 — Cross-admission semantic linking has no authorization contract
**State:** OPEN
R3.2 L1 only links endpoints admitted in the same `ExecutionAdmissionReceipt`. New Evidence cannot yet explicitly link to an older canonical Claim without broadening trust scope.
**Target:** typed external endpoint binding with run/scope/policy authorization, provenance and stale-revision checks.

R3.2 debt source: `RESEARCHER_R3_2_IMPLEMENTATION_REVIEW.md` and `RESEARCHER_R3_2_SEMANTIC_LINKING_ARCHITECTURE.md`. TD-027/TD-028 are explicit L1 limitations, not hidden feature-completion gaps.

## Researcher debt update — R3.3

- **TD-029 OPEN**: assessed-relation use is not yet mandatory in every dependency/runtime path. `build_knowledge_dependencies(... require_relation_assessment=True)` is fail-closed, but the compatibility default can still admit legacy ACTIVE edges into reasoning when the caller does not opt in. Target: an R3 reasoning facade/policy makes assessed relation use mandatory while legacy R2 fixtures stay explicitly legacy.
- **TD-030 OPEN**: rejected assessment produces a valid `EDGE_STATE_CHANGED` lifecycle transition, but the R0 dry-run ClaimRegistry has no canonical update-command path for applying revised EDG state after admission. Target: one reducer/repository application path for relation revisions and event persistence (coordinate with TD-022).
- **TD-031 OPEN**: `INCONCLUSIVE/BLOCKED` relation is excluded from reasoning but does not automatically create a typed Gap/ResearchChallenge. Target: relation-assessment feedback compiler creates a bounded challenge branch without duplicating the edge or Claim.
- **TD-032 OPEN**: relation assessment signals are still supplied explicitly and kind-specific semantic validators are incomplete. DERIVED_FROM lacks reproducibility/assumption validation; QUANTIFIES has only L1 policy. Target: typed method/derivation/measurement validators plus explicit specialist/Tribunal signal adapters.


## Researcher debt update — R3.4

- **TD-029 DONE**: new R3 reasoning facade always compiles dependencies with current relation assessment required. The low-level permissive flag remains only for explicit R2/legacy compatibility.
- **TD-030 DONE (L1)**: `ClaimRegistry.update_graph_edge()` now applies reducer-produced relation revisions through one optimistic-concurrency checked canonical write path and persists `EDGE_STATE_CHANGED`. Large-graph relation indexing remains TD-022.
- **TD-031 DONE**: `INCONCLUSIVE/BLOCKED` relation assessment deterministically creates one blocking Gap/ResearchChallenge, persists Gap+Challenge atomically, and reuses the existing CHALLENGE planning loop to reach executable work.
- **TD-032 OPEN**: DERIVED_FROM and richer QUANTIFIES semantics still require typed reproducibility/assumption/measurement validators and validated specialist/Tribunal signal adapters.
- **TD-023 remains OPEN, evidence strengthened**: missing `.git` recurred at R3.4 start. Recovery from the stored bundle + ordered patch chain was tree-equivalent, but this must become one automated restore-verification command.

### TD-033 — R3.5 uncertainty field has incomplete automatic axis adapters
- **Area:** `researcher_core/uncertainty_field.py`, Gap taxonomy, source/provenance adapters
- **Severity:** medium
- **Status:** open
- **Problem:** L1 automatically projects METHOD/EVIDENCE/SCOPE from relation assessment and maps Gap/Conflict/numeric observations, but SOURCE_PROVENANCE, FRESHNESS, CAUSALITY, ASSUMPTION and EXTRAPOLATION do not yet have complete typed automatic adapters. Gap-to-axis mapping is conservative string-family logic.
- **Acceptance:** typed canonical adapters populate those axes from validated source/claim/derivation artifacts; Gap types are a closed typed vocabulary; tests prove absent axes are not silently treated as resolved.

### TD-034 — Numeric uncertainty is projection-only, not canonical Quantity state
- **Area:** `researcher_core/uncertainty.py`, `r0/entities.py::Quantity`, `uncertainty_field.py`
- **Severity:** medium
- **Status:** open
- **Problem:** numeric uncertainty can be evaluated through explicit Decimal interval observations, but R0 `Quantity` stores only value/unit/property and cannot carry uncertainty model, coverage factor, distribution or measurement conditions canonically.
- **Acceptance:** versioned numeric/measurement uncertainty contract attaches to Quantity or a dedicated canonical measurement entity; interval/distribution/coverage semantics are explicit and R3.5 consumes them without fixture-only adapters.

## Researcher debt update — R4.1

### TD-035 — AssessmentNeed has no canonical durable identity
**Area:** `researcher_core/uncertainty_field.py`, `tribunal_composition.py`
**Severity:** medium
**Status:** open

R3.5 `AssessmentNeed` is a value object without EntityId. R4.1 uses a deterministic content-addressed `AssessmentNeedRef` scoped to a ReviewWorkField plus ordinal disambiguation. This is safe for composition/replay but is not a canonical versioned knowledge object.

**Acceptance:** add a canonical/versioned need identity (entity or explicit stable key in R3 contract), migration/serialization tests and compatibility with existing RWF data; R4 assignments no longer need the bridge.

### TD-036 — Domain Tribunal role packs are static policy, not admitted modular packs
**Area:** `config/tribunal_composition.yaml`, role taxonomy
**Severity:** medium
**Status:** open

R4.1 has a deliberately small closed role registry. It supports equivalence groups and deterministic lineage matching but not dynamically installed/versioned domain packs, compatibility declarations or organization-specific expert catalogs.

**Acceptance:** typed role-pack schema + admission/versioning + conflict/equivalence validation + tests proving an installed pack cannot widen tool/evidence authority outside central policy.

### TD-037 — Runtime provider health / execution binding remains unresolved
**Area:** Tribunal capabilities/evidence views
**Severity:** medium
**Status:** partial / open

R4.1 validates that role-declared capabilities/tools exist in central authority registries. R4.2 now compiles executable per-role evidence slices and proves current no-leak/view behavior. What remains unresolved is live capability/provider availability and execution binding: a valid logical capability/tool name does not prove that a healthy authorized provider exists when R4.3 tries to execute an inquiry.

**Remaining acceptance:** before live R4.3 capability-dependent inquiry, resolve required logical capabilities through existing runtime bindings/health state and fail closed or recompose/escalate when a required capability has no healthy authorized provider. Do not create a Tribunal-specific provider registry.

## Researcher debt update — R4.2

### TD-038 — No universal cross-layer traceability/lineage substrate
**Area:** R0 identity, ResearchTraceLink, AdmissionIdentityMap, RWF/AssessmentNeed, Tribunal plans/slices, Job/Attempt provenance
**Severity:** high
**Status:** open

R4.1 exposed the local `AssessmentNeed` identity seam; R4.2 E2E exposed the broader issue that control refs, semantic refs and evidence refs cross phase boundaries with different ownership and projection semantics. Existing `ResearchTraceLink`, entity metadata, dependency records and local identity bridges provide pieces, but there is no single queryable/versioned substrate for tracing an object and all transformations that consumed/produced it across Writer/Researcher/Coder and R0→R4+.

**Target direction:** define a non-authoritative traceability layer (candidate `TraceabilityLink/1.0` + lineage/index projection) that records `subject/ref revision -> transformation/attempt/policy hash -> produced refs`, alias/bridge mappings, and causation across Job/Attempt/ResearchCard. It must support replay, selective invalidation and "why/how did this artifact exist?" queries without becoming a truth registry or mutable god-object.

**Acceptance:** architecture + typed contracts; migration/adapters from ResearchTraceLink/AdmissionIdentityMap/AssessmentNeedRef; deterministic replay/query tests; one E2E trace from source/evidence through relation assessment -> RWF -> TribunalCompositionPlan -> EvidenceSlice -> later Inquiry artifact; no semantic state transition owned by traceability itself.

### TD-036 remains OPEN — Domain Tribunal role packs
R4.2 intentionally does not add role-pack loading/admission. Keep the existing TD-036 boundary intact until inquiry/evidence authority contracts are stable.


### TD-039 — FRESH_CONTEXT has structural but not semantic provenance blindness
**Area:** R4.2 EvidenceSlice / future blind-review projection
**Severity:** medium
**Status:** open / non-blocking for R4.2 L1

R4.2 removes structured provenance, previous conclusions, SUPPORT/COUNTER polarity, relation-kind leaks and source target metadata from FRESH_CONTEXT. However, `EvidenceSpan.exact_text` is intentionally preserved. An excerpt may itself name an author, journal, DOI, institution or conclusion source, defeating source-prestige blindness at the semantic-content level.

**Acceptance:** before claiming strong blind review, define a separate deterministic `BlindEvidenceProjection`/redaction contract with reversible traceability to canonical evidence, tests for common provenance-bearing text patterns, explicit scientific-fidelity constraints and a staged reveal policy. Do not mutate the canonical EvidenceSpan text.


### TD-040 — Researcher test invocation requires manual import-path bootstrap
**Area:** Researcher developer/test runtime
**Severity:** low
**Status:** open / non-blocking

A direct `python -m pytest tests/researcher` from repository root currently fails during collection because `researcher_core` lives under `scripts/researcher` and the import root is not bootstrapped automatically. The verified invocation is `PYTHONPATH=scripts/researcher python -m pytest ...`. This is an operational/test-harness seam, not an R4.2 semantic failure, but it weakens reproducibility of E2E-first acceptance across sessions and machines.

**Acceptance:** provide one repository-owned command/script/target that sets the required import path and can run targeted Researcher E2E/regression plus compiler/static gates reproducibly without session-specific shell setup. Keep the command independent of Tribunal semantics.

## Researcher debt update — R4.3 independent role execution

### TD-036 remains OPEN — Domain Tribunal role packs
R4.3 introduces a semantic handbook for roles already admitted by composition policy, plus typed code-generated requests when semantic guidance is missing. This is **not** a domain role-pack admission mechanism. Domain pack loading/versioning/equivalence/authority admission remains deferred and must not be smuggled through handbook auto-fill.

### TD-037 — Live role provider health/binding remains OPEN
**Status:** partial / open

R4.3 now proves the structural role execution path through the real Job/Attempt runtime with deterministic fixture workers. It does not yet bind an admitted role to a live authorized LLM/tool provider or verify provider health at execution time. The existing acceptance therefore proves control-plane/runtime composition, not production scientific reviewer quality or provider availability.

**Acceptance remains:** resolve contract-required logical capabilities through shared runtime binding/health state; fail closed/recompose/escalate if no healthy authorized provider exists; E2E one real role invocation without creating a Tribunal-specific provider registry.

### TD-038 remains HIGH — Universal cross-layer traceability/lineage substrate
R4.3 adds another concrete lineage chain (`EvidenceSlice -> InquiryContract -> Job/Attempt -> InquiryTurn -> ArgumentArtifact`) and carries fingerprints/attempt IDs in artifacts, but these are still local links. The planned non-authoritative traceability substrate must eventually index this chain together with R3/R4 predecessors and support replay/invalidation/"why does this exist?" queries.

### TD-040 — Researcher test invocation bootstrap
**Status:** DONE in R4.3

Implemented `scripts/run_researcher_acceptance.py` with repository-owned import bootstrap and `r4/full/gates/all` modes. R4 targeted, full regression and compiler/static gates now run without session-specific `PYTHONPATH` shell setup.

**Closed by:** R4.3 independent-role execution.

### Non-blocking improvement — Job/Attempt adapter API
`JobCtlTribunalRoleAdapter` deliberately reuses the existing Job state/event model, but it currently performs a small amount of attempt/stage mutation through `job_ctl` primitives because there is no single reusable programmatic "execute child attempt" helper. If more peer role/runtime adapters appear, extract that shared helper rather than duplicating lifecycle mutation. This does not block R4.3 L1 and is not grounds for a second scheduler.

## Researcher debt update — R4.4 dialectic observation / future role interchange

### TD-041 — Portable RoleCard / RoleReference / RoleParameterGraph interchange is not implemented
**Area:** Tribunal role handbook/composition, future module/user exchange
**Severity:** medium
**Status:** open / future-growth

Current R4 roles are split correctly across composition authority, semantic handbook, case-specific RoleBrief/RoleInstruction and runtime history, but there is no canonical portable DOM for exporting/decomposing/comparing/recombining role semantics between modules/users.

**Target direction:** `RoleReference + RoleCard + RoleVariantCard + RoleParameterGraph + RoleEvaluationSnapshot` inside a versioned `PortableRoleDOM` YAML interchange envelope. Imported semantics must never carry executable tool/capability/evidence authority; local policy must re-admit/rebind them.

**Acceptance:** typed schema + graph relation vocabulary + round-trip semantic validation + import/export tests + authority-stripping tests + compatibility/equivalence diff; connect to domain role-pack proposals without silently closing TD-036.

### TD-042 — Interaction-specific dialectic issue proposals need live calibration
**Area:** R4.4 `DialecticIssueProposal`, future live turn observer
**Severity:** medium
**Status:** open / non-blocking for deterministic L1

R4.4 L1 can carry typed `ANSWER_EVASION`, `CONTRADICTION` and `ROLE_CAPABILITY_GAP` proposals, but fixture tests do not establish that a live semantic observer detects them reliably or consistently.

**Acceptance:** bounded observer worker under the same evidence/disclosure authority; benchmark traces with positive/negative examples; inter-rater/calibration analysis; false-positive/false-negative tests; code remains authoritative for admission/continuation and never treats observer labels as truth.

### TD-043 — Generic dialectic disclosure is not canonical across all role phases yet
**Area:** R4.4 inquiry history, cross-role disclosure, argument attack/defense graph
**Severity:** high
**Status:** open / partially implemented in R4.4 L2a

R4.4 L2a now has canonical versioned `ArgumentRelation` objects plus `ArgumentGraphProjection` with explicit `ATTACKS / UNDERCUTS / REPLIES_TO / DEFENDS` edges, acyclicity checks, graph fingerprints and a branching E2E. It also has a typed `DialecticDisclosureContract` for the conditional Advocate path, and verifies that a sibling attack branch is hidden rather than broadcast automatically.

The debt remains open because disclosure is not yet compiled generically for challenger/questioner/cross-exam phases from one shared policy. Advocate disclosure is deliberately conservative and branch-local; it is not evidence that all cross-role disclosure paths are solved.

**Acceptance:** one generic disclosure compiler/policy for challenger, questioner, cross-exam and defense; canonical versioned argument relation objects/graph projection; replay/integrity tests; branching E2E with independent arguments -> selected challenge -> bounded disclosure -> Q/A -> Q-on-answer; no automatic cross-disclosure and no majority-vote truth.

### TD-044 — Dialectic issue semantic identity is text-sensitive at L1
**Area:** `researcher_core/tribunal_dialectic.py` issue signatures
**Severity:** medium
**Status:** open / non-blocking for R4.4 L1

Current `EmergentIssue.signature` includes normalized issue statement text plus kind/need/refs/blocking. Exact repeats are detected deterministically, but semantically equivalent paraphrases can receive different signatures and appear artificially novel.

**Target direction:** add a typed semantic facet/key or admitted equivalence relation that lets the semantic layer propose issue identity while code validates scope/provenance. Keep both structural/facet identity and statement-level revision history so genuinely different limitations on the same refs are not incorrectly collapsed.

A promising reuse path is the Writer semantic pipeline rather than creating a second paraphrase/decomposition stack inside Tribunal. Writer already performs claim extraction/splitting, graph-oriented reference/draft processing and round-trip semantic validation. A future bounded bridge may submit an emergent issue plus local context to a Writer-style semantic decomposition capsule and receive proposal-only artifacts such as atomic `ClaimFacetProposal[]`, a small local proposition/argument graph, and candidate equivalence links. Researcher code must then validate need/ref scope and explicitly admit any equivalence; Writer output must never mutate `EmergentIssue.signature`, dialogue progress, or authority directly.

This reuse should also preserve the original and all reformulations so the system can distinguish “same issue, different wording” from “same topic, different failure mode”. If the Writer bridge is unavailable, issue identity must degrade conservatively to the current text-sensitive behavior rather than guessing equivalence.

**Acceptance:** paraphrase/equivalence fixtures, distinct-facet fixtures, replay-safe issue revisions, and no-progress tests showing that rhetorical rewording alone cannot extend the dialogue; plus one bounded Researcher↔Writer decomposition/round-trip fixture proving that Writer-produced facet/equivalence proposals are non-authoritative and scope-checked before admission.

### TD-045 — DialecticHistory is not branch-scoped yet
**Area:** R4.4 branching argument graph, dialectic observation/replay
**Severity:** high
**Status:** open / non-blocking for structural L2a

`ArgumentGraphProjection` can now contain multiple independent branch heads, but `DialecticHistory` still represents one local sequential history/counter set. Running two cross-exam branches concurrently or interleaved must not share `no_progress_streak`, Q/A-pair count, token budget or issue lifecycle accidentally.

**Target direction:** introduce a typed branch identity/envelope bound to `AGP id + graph revision + root/focus argument/relation/issue`, and scope `DialecticHistory`/replay to that branch. Returned ResearchChallenge results must resume the exact branch rather than creating an unrelated dialogue history.

**Acceptance:** two-branch E2E with independent counters/issues; one branch can STOP/OPEN while the other continues; research escalation/resume preserves branch identity; replay reconstructs each branch deterministically without cross-branch no-progress or issue leakage.
