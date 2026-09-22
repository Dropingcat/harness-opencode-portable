# WRITER-UNIFY-001: handoff reconciliation

## Decision

The versioned handoff package is specification/provenance, not runtime authority. Only contracts and fixtures that define currently executable Writer boundaries are copied into the canonical subsystem. The historical unit itself remains byte-preserved until the archive commit and is then moved as one unit.

## Integrated byte-identical contracts

Canonical destination: `scripts/writer/contracts/specs/`.

- writing contract schema
- RTT result schema
- build manifest schema
- blocker schema
- uncertainty schema
- review issue schema

These files are copied byte-for-byte. Source and destination SHA-256 values are recorded in `scripts/writer/migration/handoff_integration.json`.

## Integrated byte-identical fixtures

Canonical destination: `scripts/writer/fixtures/handoff/`.

- paragraph writing contract
- build manifest
- missing-evidence blocker
- reviewer conflict

They exercise active contract boundaries without importing the handoff package at runtime.

## Already consumed elsewhere

The active linguistic registries were previously moved into `scripts/writer/assets/linguistics/` during semantic-runtime consolidation. They are not copied again here because duplicate runtime authorities would be worse than the problem this migration is trying to remove.

## Retained as provenance, not runtime

Architecture documents, OSINT design, historical decisions, catastrophic-scenario catalog, source skeleton and other unexecuted specifications remain only inside the versioned handoff unit. They are useful history but do not become production dependencies merely because someone once wrote YAML about them.

## Historical manifest caveat

`MANIFEST_v0.3.md` explicitly states that it describes the original handoff package and that selected payloads had already been consumed or removed before this migration. Therefore P6 archives the current versioned handoff checkout byte-for-byte and records a fresh tree inventory; it does not pretend to reconstruct an earlier package from missing historical files.

## Runtime boundary added in this phase

`Researcher -> Writer` is now explicit:

1. `scripts/writer/research/verify_claims_adapter.py` invokes the canonical Researcher verifier read-only.
2. Writer creates an in-memory verification projection for citation checking.
3. `scripts/writer/release/gate.py` independently evaluates evidence, traceability and semantic RTT.
4. Release is allowed only when all required gates pass.

No Researcher verdict is authored, upgraded or persisted by Writer.
