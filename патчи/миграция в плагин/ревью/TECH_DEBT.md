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
