# WRITER-UNIFY-001 — Phase 6B/6C review

## Verdict

**ACCEPT** for semantic handoff integration and immutable archive. P7 live deployment remains separate and has not been claimed complete.

## What changed

### Semantic handoff

Writer now has an explicit read-only Researcher boundary:

- `scripts/writer/research/verify_claims_adapter.py` invokes the canonical Researcher verifier without `--apply`;
- the adapter hashes the DOM before and after invocation and fails if bytes change;
- only the controlled verdict vocabulary is accepted;
- Writer does not author, upgrade, or persist Researcher verdicts.

The public CLI now exposes `research-adapt` and `release-check`.

### Aggregate release gate

`scripts/writer/release/gate.py` evaluates three independent gates:

1. `EVIDENCE` — Researcher authority;
2. `TRACEABILITY` — canonical citation trace;
3. `SEMANTIC_ROUNDTRIP` — canonical deterministic RTT.

Release is conjunctive. Any failed gate blocks release. Researcher results are projected into a temporary in-memory DOM for traceability only. The source DOM is not modified.

Citation identifiers are stripped only from the temporary RTT input. This prevents digits in `[C-*]` and `[S-*]` from being interpreted as scientific numeric values while preserving the original draft unchanged.

### Handoff integration

Six runtime-relevant schemas and four fixtures were copied byte-identically into canonical Writer paths. Every source/target pair is bound by SHA-256 in `scripts/writer/migration/handoff_integration.json`.

The historical handoff manifest already states that the original v0.3 package had been partially consumed before this migration. The archive therefore preserves the current tracked handoff checkout as the actual versioned provenance unit; it does not fabricate missing historical payloads.

### Archive

After `archive_readiness` returned `READY`, two superseded trees were moved as whole tracked units:

- `scripts/writer-core` → `легаси/writer/writer-core-pre-unification`
- `scripts/writer_core_handoff` → `легаси/writer/writer_core_handoff-v0.3.0`

Pre-move tracked inventories are stored in `scripts/writer/migration/archive_inventory.json`.

Inventory:

- writer-core: 54 tracked files, tree SHA-256 `db73a630e65cd114fe87698158e3c7ab1f8f1a40b23b22ae92ebf9c772cc13da`
- handoff v0.3.0: 120 tracked files, tree SHA-256 `e1e0b5993c087683b21b3369e4a0ecc6eaccdb6f1219ec0a3cefa7af08bb4583`

Generated caches are not treated as provenance authority.

## Defects found during review

1. Citation IDs were initially visible to RTT and produced false `NUMERIC_DRIFT`. Fixed by removing citation markers from the temporary semantic comparison input only.
2. `citation_trace` initially could not see fresh numerical verification because the adapter correctly refused to mutate DOM. Fixed with an in-memory projection of Researcher results.
3. The restored migration-manifest test and actual manifest had diverged. The manifest was normalized to schema `writer-migration-manifest/1.1`; tests now match the actual list-based source model and archive lifecycle.
4. Four tests still used the old runtime as a post-migration oracle. They failed immediately after archive and were rewritten to validate the canonical runtime or immutable archive provenance instead.

These findings are considered evidence that the post-archive test was doing useful work rather than merely blessing the patch.

## Gates

Before archive:

- semantic handoff tests: 7/7 PASS;
- focused migration/archive/binding tests: 24/24 PASS;
- complete root test discovery: 86/86 PASS;
- core runtime-boundary suite: 7/7 PASS;
- archive readiness: READY;
- base runtime compiler: PASS;
- capability runtime compiler: PASS;
- compileall: PASS;
- git diff check: PASS.

After archive:

- complete root test discovery: 86/86 PASS after retiring four invalid legacy-oracle tests;
- core runtime-boundary suite: 7/7 PASS;
- archive inventory/hash verification: PASS;
- archive readiness: ARCHIVED with zero blockers;
- base runtime compiler: PASS;
- capability runtime compiler: PASS;
- compileall: PASS;
- git diff check: PASS.

## Authority after Phase 6

- public Writer command surface: `scripts/writer/cli.py`;
- Writer semantic runtime: `scripts/writer/**`;
- Research scientific verification: `scripts/researcher/verify_claims.py` and `researcher_core`;
- old runtime and handoff: provenance/rollback only under `легаси/writer/`;
- router/factory/jobs/memory/orchestration remain shared and unmoved.

## Remaining work

P7 is deployment verification, not another semantic refactor. It must prove that the live mirror receives the complete nested canonical Writer tree, capability/provider probes resolve the canonical CLI, health checks remain green, and rollback from the pre-deploy backup works.
