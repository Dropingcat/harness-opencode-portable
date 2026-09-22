# Scalable architecture seams

We avoid double refactoring by introducing ports before adding heavier
infrastructure.

## Stable ports

Implemented in `src/researcher_core/ports.py`:

- `ClockPort`
- `IdFactoryPort`
- `CommandHandlerPort`
- `UnitOfWorkPort`
- `EventProjectorPort`
- `CapabilityRegistryPort`
- `CapsuleRunnerPort`
- `ArtifactBuilderPort`

Current adapters are in-memory and dependency-free, but prod SQLite is ready.

Implemented prod adapters (2026-08-31):
- `r0/sqlite_store.py` → `SqliteUnitOfWork` + `open_sqlite` behind `UnitOfWorkPort` (WAL, state/events/outbox, 4 tests)
- `policy.py` → `Policy` with `policy_hash` + 13 consumption heuristics
- `budget.py` / `model_routing.py` → `TokenMeter`/`ModelRouting` (fallback/NoAgent) behind policy
- `artifact.py` / `artifact_builder.py` → schema-backed YAML dict validation + `policy_hash` + atomic write

## Current composition root

`src/researcher_core/runtime.py` provides `build_in_memory_runtime()`:

```text
SequenceClock + CycleRandom
→ EntityIdFactory
→ InMemoryClaimRegistry (still InMemory UoW — SQLite not yet wired)
→ InMemoryCapabilityRegistry
→ MinimalArtifactBuilderAdapter (now wraps yaml.safe_dump + policy_hash)
→ InMemoryEventProjectorAdapter
```

Wiring via ports (next):
- `build_sqlite_runtime(db_path)` will swap `SqliteUnitOfWork` for `InMemoryClaimRegistry` without domain rewrite
- MCP/skill adapters register behind `CapabilityRegistryPort`
- repository-backed projector replaces `InMemoryEventProjectorAdapter`

## Rule

New functionality must enter through a port or create a new port. It should not
reach directly into in-memory internals unless a simplification is explicitly
registered in `docs/r0-simplification-tracker.md`.
