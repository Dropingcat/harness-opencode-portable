# WRITER-UNIFY-001 migration status

The executable source of truth is `config/writer_migration_manifest.json`.

## Completed boundaries

- P1: migration inventory and fail-closed manifest.
- P2: one public Writer CLI facade.
- P3: extractor experiment and canonical deterministic extractor.
- P4/P5 implementation work: semantic runtime and drafting/citation gates consolidated under `scripts/writer/` with compatibility preserved during transition.
- P6A: external agent/config/skill/provider bindings point to canonical Writer; recursive sync support is present.

## Current boundary

### P6B semantic handoff

Acceptance requires:

- Researcher verification is consumed read-only and the source DOM hash cannot change;
- imported handoff contracts/fixtures are hash-bound and byte-identical;
- `EVIDENCE`, `TRACEABILITY`, and `SEMANTIC_ROUNDTRIP` are independent gates;
- aggregate release is fail-closed;
- full Writer regression is green.

### P6C immutable archive

Starts only after `archive_readiness.py --require-archive-ready` returns READY. The superseded runtime and current handoff unit are moved as complete trees with a fresh inventory and rollback mapping. No selective pruning is permitted in the archive commit.

## Next

P7 performs live deployment verification, not semantic refactoring: dry-run recursive sync, capability preflight, health check and live mirror audit.
