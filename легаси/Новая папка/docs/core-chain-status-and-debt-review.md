# Core chain status and simplification review

This document is the checkpoint after the first validator/capsule iterations.

## 1. Implemented architecture chain

```text
Local document text
  ↓
LocalDocumentExtractionCapsule
  → Source / EvidenceSpan observation with sha256 hashes
  ↓
LocalTextClaimExtractionCapsule
  → ClaimProposal / QuantityProposal observation
  ↓
CommandEnvelope + ProposalBatch
  ↓
RegistryValidator
  → typed ValidationReport / RegistryValidationError before commit
  ↓
InMemoryClaimRegistry
  → Source / EvidenceSpan / Claim / Quantity / GraphEdge admission
  ↓
InMemoryUnitOfWork
  → state + events + outbox atomically visible after commit
  ↓
EventEnvelope log
  → stable entity_type/entity_record payload, no embedded dataclass objects
  ↓
Projection / Snapshot
  ↓
ArtifactBuilderPort
  → minimal research-service-artifact/0.2 YAML shape
```

## 2. What changed in the last increments

| Change | Why | Good | Bad / remaining risk |
|---|---|---|---|
| `RegistryValidator` extracted | Inline checks were becoming hidden policy | Typed issue codes, no side effects before invalid commit, easier to port to SQLite | Still not full domain validation; no severity/policy ownership per validation code |
| `EntityId.new` requires `Clock` | Raw int timestamp was a second API | Single deterministic ID seam | Tests/adapters must provide clock object |
| Source/Evidence admitted through registry | Pipeline previously merged them outside write boundary | Core owns authoritative state | Prebuilt entities still bypass rich extractor validation |
| Event payloads use stable records | Embedded dataclasses were not storage-safe | Event log is closer to persistence boundary | Rebuild still in-memory and records are not schema-versioned per entity type |
| YAML scalar escaping hardened | Minimal renderer could misrepresent text | Quotes/backslashes/newlines covered by bubble tests | Still not a real YAML parser/schema-backed writer |
| Ports/composition root added | Avoid double refactor when adding SQLite/MCP | Future adapters swap behind ports | Enforcement is by bubble tests, not static type/CI yet |
| `preprint/` excluded by policy | Workspace contains unrelated publication artifacts | Debt scanner returns to core scope | If real core moves under excluded dir, scanner could miss it; policy review required |
| Deterministic numeric adapter added | First bounded legacy port without runner coupling | Dependency-free unit registry, Decimal conversion, scalar/range comparison covered by bubble tests | No text tokenizer, uncertainty model, qualifier alignment, or source runner |
| Schema-backed policy loader prod | Bootstrap text parser replaced — now `yaml.safe_load` + full shape validation + `sha256:` hash | Immutable `Policy/Heuristic/ReasonCodeMeta`, single source for debt/artifact policy, `load_bootstrap_policy` delegates, 4 bubble tests | Requires `PyYAML`; hash changes on any policy edit (expected) — must be frozen in artifact manifest |
| Token budget prod + model routing | `research.budget.*` + 13 новых consumption heuristics (7 пунктов) вынесены в `research_policy.yaml` с комментариями; `TokenBudget/TokenMeter` + `ModelRouting` с fallback/NoAgent | Все токен-лимиты/tiers/NoAgent из policy, оркестратор на high tier, рутина без LLM, fallback `gpt-5.5`, динамическая эвристика заложена | Новые heuristics меняют `policy_hash` (ожидаемо); router пока не подключен к реальным LLM вызовам |
| Schema-backed artifact checker/writer | `artifact.py` → `yaml.safe_load` dict-валидация + `claims` list/dict, `artifact_builder.py` → `yaml.safe_dump` + `policy_hash` + atomic write | Проверка 98 gaps Malina, писатель с `policy_hash`, 4+4 bubble теста | Writer ещё не пишет `source_versions`/`document_registry` полностью |
| SQLite UnitOfWork prod | `r0/sqlite_store.py` + `open_sqlite` за `UnitOfWorkPort` (WAL, FK, `state/events/outbox/idempotency/rejections`) | Rollback/commit/idempotency/rejection-ready, 6+3 теста, debt 0 | Registry теперь принимает `uow_factory`+`idempotency_store`, `build_sqlite_runtime()` прод |
| Guard (doc_guard) целиком | `guard.py` P0+P2 `polza` `l3-lunaris-8b` + `offline_pipeline` block, `research.guard.*` 4 heuristics | `P0` 50% bypass, `P2` ~10%, `scan_text_with_p2` tie-breaker, `offline_pipeline` фильтрует `evidence_span` до `admit`, 9 тестов | `P2` требует `guard_config.json`/`POLZA_API_KEY`, без него degrade к P0 |
| Durable rejections | `r0/transactions`+`sqlite_store` `put_rejection` + `REJECTION_RECORDED` event + `rejection.recorded` outbox | Invalid `ProposalBatch` теперь `persist` до `raise`, `registry` bubble tests updated | Still lacks policy-backed partial validation |
| Formulas / uncertainty / qualifier adapters | `formulas.py` + `uncertainty.py` + `qualifier.py` ports legacy deterministic logic | Formula detection, `K=0.9/1.0`, `±`/range overlap, qualifier mismatch rules, 13 new tests | Still missing `source JSON runner` |
| SQLite projector | `rebuild_state_from_sqlite(conn)` rehydrates ISO datetimes + Decimal values from normalized event JSON; `build_sqlite_runtime()` now uses `SqliteEventProjectorAdapter` | `state_snapshot()` and SQLite rebuild match on admitted entities, 2 projector tests + runtime wiring test | In-memory runtime still exists as explicit fallback |
| LocalCorpus capsule | `local_corpus.py` JSONL read-only adapter inspired by `literature_index/server` | Local search/source selection without MCP/network, 3 tests, registered via `InMemoryCapabilityRegistry` | Still no page-span extraction or MCP runtime |

## 3. Current simplification status

Closed:

- R0-S003 IDs: raw timestamp API removed.
- R0-S004 Policy parsing: schema-backed loader with hash + 13 consumption heuristics (model routing/budget/cache/batch).
- R0-S005 Artifact checker: schema-backed YAML dict validation with list/dict claims, 98 Malina gaps (was 8 without list).
- R0-S011 Artifact writer: schema-backed `yaml.safe_dump` + atomic write + `policy_hash` in manifest/policy.
- R0-S012 Source/evidence boundary: source/evidence hash/link/admission covered.
- R0-S014 Pipeline merge: pipeline no longer bypasses registry for Source/Evidence.

Narrowed — scope упрощения ↓, надёжность ↑ (рациональная оптимизация без снижения качества):

- R0-S001 Persistence: `SqliteUnitOfWork`+`SqliteIdempotencyStore` прод `state/events/outbox/idempotency/rejections` + `build_sqlite_runtime()` 7 тестов — остаётся crash-recovery + `rejections`→`REJECTION_RECORDED` event
- R0-S002 Registry: `RegistryValidator` + durable `rejections` via `put_rejection` 2 теста, но нет `REJECTION_RECORDED` graph events и policy-backed partial
- R0-S006 Time: deterministic clock increments per use; no richer time service.
- R0-S008 State machine: partial status matrix.
- R0-S009 Capsules: `LocalCorpusCapsule` JSONL adapter exists, but no real MCP/runtime search execution yet.
- R0-S010/R0-S013 Extraction: regex/whole-document local parser only.
- R0-S015 Ports: ports exist, static enforcement missing.
- R0-S016 Numeric adapter: `numeric` + `formulas` + `uncertainty` + `qualifier` ported, остаётся `source JSON runner`

## 4. Why this is good now

- The core trust boundary is already explicit: capsules propose, registry decides.
- Invalid batches fail before idempotency recording and before commit.
- Tests exercise the full offline chain without network/LLM/API rate limits.
- Server dump components can be wrapped as adapters instead of copied into core.

## 5. Why this is still incomplete

- There is no durable database or crash recovery yet.
- The target Malina fixture still has controlled gaps against v0.2.
- No real literature/search/evidence-contract adapters are active; the numeric
  adapter is only a bounded deterministic subset.
- Policies from old `rules.yaml` are not yet migrated into versioned policy keys.

## 6. Recommended next sequence (сверено 2026-09-01)

1. ~~Schema-backed artifact checker/writer~~ — done (R0-S005/S011)
2. ~~SQLite + Guard целиком + Rejections~~ — done (R0-S001/S002 частично, `formulas`)
3. Расширить `LocalCorpus` до page-span/document parser (`R0-S009/S010/S013`)
4. Добавить policy-backed partial validation для `R0-S002`
5. Только затем `MCP`/`research_papers` капсулы (`R0-S015` static type)
