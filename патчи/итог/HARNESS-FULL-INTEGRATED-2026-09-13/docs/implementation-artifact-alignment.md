# Implementation ↔ target artifact alignment

## Target artifact reference

Passing reference fixture:

```text
artifacts/malina_research_service_artifact_target.yaml
```

It currently passes:

```powershell
$env:PYTHONPATH='src'; python -m researcher_core.artifact artifacts/malina_research_service_artifact_target.yaml --fail-on-gap
```

## What the implemented block does now

```yaml
implemented_block:
  layer: "R0 core + first offline capsule boundary"
  can_do:
    - validate typed IDs
    - create immutable command/event envelopes
    - create immutable claim/quantity proposals
    - create immutable claim/quantity entities
    - keep authoritative links in GraphEdge, not Claim
    - run in-memory dry-run registry for claim + quantity admission
    - enforce idempotency replay/no-duplicate events
    - perform in-memory unit-of-work rollback checks
    - rebuild dry-run state from event log
    - create snapshot metadata
    - run status transition state-machine
    - run a local text extraction capsule that emits proposals only
    - admit capsule proposals through registry, not through capsule authority
    - build a minimal target-shape artifact dictionary/YAML from registry snapshot
    - represent Source and EvidenceSpan as separate entities
    - run an offline document→capsules→registry→artifact pipeline smoke path
   cannot_do_yet:
    - persist registry via SQLite (UoW exists as `r0/sqlite_store.py` but registry not yet wired)
    - validate full YAML reference graph (checker is dict-level, writer now yaml+policy_hash)
    - process real Malina fixture into v0.2 artifact (98 gaps remain, down from text-level noise)
    - run real MCP/search/LLM tools (model routing + NoAgent ready, fallback via policy)
    - perform full evidence/source validation (evidence_contract still in inventory)
```

## Mapping to target artifact fields

| Target artifact field | Current producer | Status |
|---|---|---|
| `artifact_manifest` | target skeleton + `artifact_builder` | partial |
| `policy` | `config/research_policy.yaml` + skeleton | partial |
| `source_versions` | skeleton | partial |
| `document_registry` | none | missing |
| `source_registry` | `Source` entity + `artifact_builder` | partial |
| `report_spans` | none | missing |
| `evidence_spans` | `EvidenceSpan` entity + `artifact_builder` | partial |
| `claims` | `Claim` entity + registry state snapshot + `artifact_builder` | partial |
| `quantities` | `Quantity` entity + registry state snapshot + `artifact_builder` | partial |
| `graph_edges` | `GraphEdge` contract only | partial |
| `gaps` | checker only | missing |
| `writer_context` | skeleton only | missing runtime producer |
| `service_summary` | skeleton only | missing runtime producer |

## Simplifications under control

Authoritative tracker: `docs/r0-simplification-tracker.md`.

Most important simplifications before real capsules (скачок 2026-08-31):

- registry/UoW: `InMemoryUnitOfWork` still default, but `r0/sqlite_store.py` prod (WAL, state/events/outbox, 4 tests) — осталось проводка в registry;
- entity payload embedded in events for local projection (R0-S007 still in-memory);
- regex local extractor instead of LLM/MCP extraction (R0-S010/S013);
- artifact checker/writer: теперь schema-backed YAML (`R0-S005/S011` closed), осталось `source_versions`/`document_registry`/`gaps` runtime;
- source/evidence distinction есть как контракты + deterministic `numeric`/`policy_hash`/`budget`/`ModelRouting` (fallback/NoAgent) — token 7 пунктов в policy.

## Next implementation direction (сверено с tracker 2026-08-31)

1. ~~Move Source/Evidence admission into registry~~ — done (R0-S012/S014) + offline pipeline.
2. ~~Schema-backed checker/writer~~ — done (R0-S005/S011) + `policy_hash` + atomic write.
3. Проводка SQLite: `SqliteUnitOfWork` уже prod — подключить к `InMemoryClaimRegistry` через `UnitOfWorkPort` фабрику и закрыть R0-S001 (добавить idempotency таблицу).
4. Затем `R0-S007` projection → SQLite-backed projector.
5. Только после — `LocalCorpus`/`DocumentExtraction` капсулы из `15-migration...` (local-first, NoAgent для hashes).
