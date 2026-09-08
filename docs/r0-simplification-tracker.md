# R0 simplification tracker

This file records intentional simplifications that are allowed only in the
current local micro-slice. They are not hidden debt markers in source code; they
are tracked here with closure gates.

## Active simplifications — scope упрощения ↓, надёжность ↑ (рациональная оптимизация, не сужение качества)

| ID | Area | Simplification | Why allowed now | Closure gate |
|---|---|---|---|---|
| R0-S002 | Registry rejection model | `InMemoryClaimRegistry` persists `rejections` via `UnitOfWork.put_rejection` + `REJECTION_RECORDED` event + `rejection.recorded` outbox, but still lacks policy-backed partial validation for dependency-closed batches | Keeps durable rejection graph while preserving all-or-nothing | Add policy-backed `ValidationReport` for dependency-closed partial batches |
| R0-S006 | Time | Registry uses deterministic millisecond clock for IDs and UTC-ish event/meta timestamps | Enough for replay/idempotency bubble tests | Inject a single `Clock` abstraction for both IDs and timestamps |
| R0-S009 | Capsules | `InMemoryCapabilityRegistry` + `LocalCorpusCapsule` JSONL adapter exist, but no real MCP/runtime search execution yet | Lets core define trust boundary before restoring server tools | Wrap full local corpus + claim-extraction adapter with provenance and page-span tests |
| R0-S008 | State machine | Claim status transitions cover only the first documented R0 paths | Keeps transition boundary small before validators exist | Add full status matrix with validator-produced reasons and evidence checks |
| R0-S010 | Local extraction | `LocalTextClaimExtractionCapsule` uses a single regex for percentages | Provides offline capsule→proposal→registry flow with no model/network | Replace with LocalCorpus/LLM extraction adapter that still emits only proposals |
| R0-S013 | Document extraction | `LocalDocumentExtractionCapsule` emits one whole-document evidence span, not parsed page/line subspans | Provides deterministic offline source/evidence flow with hashes and no dependencies | Add structured document parser that emits multiple stable locator spans |
| R0-S015 | Ports | Ports and composition root exist, but enforcement is runtime/bubble-test only, not static CI/type-check gated | Prevents double refactoring while keeping dependency-free local loop | Add static type check or adapter contract tests for SQLite/MCP/YAML implementations |


## Current soft-gate commands

```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
$env:PYTHONPATH='src'; python -m researcher_core.debt . --json debt-report.json --fail-on none
$env:PYTHONPATH='src'; python -m researcher_core.artifact malina_research_service_fixture.yaml --json artifact-gap-report.json
$env:PYTHONPATH='src'; python -m researcher_core.artifact artifacts/malina_research_service_artifact_target.yaml --fail-on-gap
```

## Closed simplifications

| ID | Area | Closed by |
|---|---|---|
| R0-S003 | IDs | `EntityId.new` now accepts only a Clock-like object with `now_ms()`; raw integer timestamps raise `TypeError`. Production callers already pass injected clocks and `tests/test_ids.py` covers deterministic clock generation plus integer rejection. Closure evidence: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` and `$env:PYTHONPATH='src'; python -m researcher_core.debt . --json debt-report.json --fail-on none`. |
| R0-S004 | Policy parsing | Schema-backed loader in `src/researcher_core/policy.py` (`load_policy`, `Policy`, `Heuristic`, `ReasonCodeMeta`, `policy_hash`) validates `schema_version/policy_id/policy_version/reason_codes/heuristics` with required fields and computes `sha256:` hash via `yaml.safe_load` + canonical JSON. `load_bootstrap_policy` delegates to it. Closure evidence: `$env:PYTHONPATH='src'; python -m unittest tests.test_policy -v` and debt `0`. |
| R0-S005 | Artifact checker | Schema-backed YAML checker in `src/researcher_core/artifact.py` (`check_artifact_dict`, `check_artifact_text` via `yaml.safe_load`, `claims` list/dict handling, `claims_not_mapping` + per-claim forbidden/legacy). Malina fixture now 98 gaps (36 high/62 medium) vs 8 without list handling — точнее. Closure evidence: `python -m unittest tests.test_artifact_schema -v` and debt `0`. |
| R0-S011 | Artifact builder | Schema-backed writer in `src/researcher_core/artifact_builder.py` (`build_minimal_service_artifact` with `policy`→`policy_hash`, `render_artifact_yaml` via `yaml.safe_dump`, `write_artifact_atomic` temp+fsync+rename). Legacy `render_minimal_yaml` kept for bubble tests. Closure evidence: `python -m unittest tests.test_artifact_writer -v` and debt `0`. |
| R0-S001 | Persistence | `r0/sqlite_store.py` prod `SqliteUnitOfWork` + `SqliteIdempotencyStore` (WAL, state/events/outbox/idempotency) wired via `UnitOfWorkPort` + `build_sqlite_runtime(db_path)` (7 tests). `InMemory` kept as fallback. Closure evidence: `python -m unittest tests.test_sqlite_store tests.test_runtime_sqlite -v` and debt `0`. |
| R0-S016 | Numeric comparison | `numeric.py` + `formulas.py` + `uncertainty.py` + `qualifier.py` + `numeric_source_runner.py` now cover deterministic unit conversion, scalar/range comparison, formula constant checks, uncertainty overlap, qualifier mismatch, and source JSON comparison without legacy shell runner copy. Closure evidence: `python -m unittest tests.test_numeric tests.test_formulas tests.test_uncertainty tests.test_qualifier tests.test_numeric_source_runner -v` and debt `0`. |
| R0-S007 | Projection | `rebuild_state_from_sqlite(conn)` in `r0/sqlite_store.py` rehydrates ISO `created_at` and `Decimal` values from normalized event JSON, and `build_sqlite_runtime()` now uses `SqliteEventProjectorAdapter` instead of the in-memory projector. Closure evidence: `python -m unittest tests.test_projection_sqlite tests.test_runtime_sqlite -v` and debt `0`. |
| R0-S014 | Pipeline | `ProposalBatch` now carries prebuilt `Source`/`EvidenceSpan`; `InMemoryClaimRegistry.execute` commits them via `InMemoryUnitOfWork`, emits `SOURCE_ADMITTED`/`EVIDENCE_ADMITTED`, and `OfflineResearchPipeline` builds artifacts from registry state only. |
| R0-S012 | Source/evidence | `LocalDocumentExtractionCapsule` emits `Source`/`EvidenceSpan` with exact text and `sha256:` hashes; `OfflineResearchPipeline` admits them through `InMemoryClaimRegistry`, and `tests/test_offline_pipeline.py::OfflinePipelineBubbleTests.test_artifact_source_evidence_records_are_hash_tagged_and_registry_admitted` proves artifact `evidence_spans[*].source_id` matches a `source_registry` key and registry admission state/events exist. Closure evidence: `$env:PYTHONPATH='src'; python -m unittest discover -s tests -v` and `$env:PYTHONPATH='src'; python -m researcher_core.debt . --json debt-report.json --fail-on none`. |

## Non-negotiable invariants already under bubble tests

- IDs are typed as `<PREFIX>_<ULID>`.
- Command payloads and event payloads are snapshot-immutable.
- Canonical JSON rejects non-string mapping keys.
- Reason codes are checked through config-backed registry where provided.
- Idempotency replay adds no state/events.
- Same idempotency key with different request hash is a conflict.
- UnitOfWork rollback leaves no partial state/events/outbox.
- Claim records reject authoritative relation keys; relations live in `GraphEdge`.
- Event-log projection rebuilds the same dry-run state as the registry snapshot.
- Claim status changes go through `TransitionRequest` and emit status-change events.
- Malina fixture gaps against target YAML artifact are machine-visible.
- Capsules produce observations/proposals only and cannot claim authoritative state.
- Current dry-run registry admits prebuilt `Source`, `EvidenceSpan` and `GraphEdge` records, validates batch shape, duplicate IDs, prebuilt run scope and source/edge references through typed issue codes, and emits admission events. Tradeoff: invalid batches fail atomically with a report instead of creating durable rejection graph nodes.
- Offline pipeline can produce target-shape artifact YAML from local document text using committed registry state for Source/Evidence/Claim/Quantity.
- Numeric comparisons can normalize core unit aliases, convert length/temperature/energy/pressure/fraction values, reject dimension mismatches as `not_comparable`, and report scalar/range `match`, `mismatch`, or `partial_overlap` without network access.
- Policy loading is schema-backed: `config/research_policy.yaml` parsed via `yaml.safe_load`, validated for required `reason_codes/heuristics` metadata, and hashed as `sha256:` canonical JSON for artifact provenance; `load_bootstrap_policy` is a thin projection.
- Artifact checking is schema-backed: YAML dict validation via `yaml.safe_load` + `claims` list/dict handling, `policy_hash` ready, 98 Malina gaps machine-visible.
- Model routing + token budget are policy-driven: `research.model.*`, `research.budget.*`, `research.cache.*` etc. in policy, `ModelRouting` with fallback/NoAgent and `TokenMeter` fail-closed before LLM.
- Rejections are durable: invalid `ProposalBatch` persisted via `UnitOfWork.put_rejection` (InMemory + SQLite `rejections` table, 2 tests), not just raised.
- Formulas are deterministic adapter: `researcher_core.formulas` ports legacy `formulas.py` (scherrer etc.) behind typed boundary, 3 tests.

## Path to capsules

1. Keep R0 core deterministic: command, event, entity, edge, transition, registry,
   projection, transaction.
2. Introduce capsule contracts as perimeter-only observations.
3. Restore first offline capsule from local corpus/document extraction.
4. Convert capsule output to proposals or prebuilt Source/Evidence batches at the registry boundary.
5. Let `ClaimRegistry` decide admission through transactions and state-machine.
6. Replace simplifications R0-S001..R0-S009 one by one, each with a closure test.
