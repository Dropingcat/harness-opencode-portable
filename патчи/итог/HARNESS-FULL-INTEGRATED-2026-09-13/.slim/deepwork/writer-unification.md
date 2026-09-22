# Writer unification

## Goal

Create one canonical writer subsystem under `scripts/writer/` with one public CLI and specialized agent roles for orchestration, research/fact-checking, article/chapter drafting, editing, semantic review, and release checks.

## Confirmed boundaries

- Keep specialized agents; do not create one universal writer agent.
- Keep active shared runtimes (`router`, `code-factory`, `capsules`, `jobs`, `memory`, `orchestration`) in place.
- Move only superseded or duplicate writer branches to `легаси/writer/`.
- Extract accepted contracts and fixtures before archiving `scripts/writer_core_handoff/` as one immutable versioned unit.
- Use incremental Git commits and independent review at every module-boundary change.
- Use experimenter only when alternatives have an explicit metric and benchmark.

## Accepted discovery

- Canonical semantic runtime: `scripts/writer-core/`.
- Canonical draft/citation gates: `scripts/writer/`.
- Research verification boundary: `scripts/researcher/verify_claims.py` plus `researcher_core`.
- `scripts/writer_core_handoff/` is specification/provenance, not runtime.
- Both extractor trees currently have active callers; three corresponding modules are byte-identical and two diverge.
- `sync_to_live.py` does not deploy the full writer subsystem recursively.

## Planned phases and gates

1. Migration map and tracker. Owner: documentation worker. Gate: reviewer checks completeness and no false legacy classification.
2. Unified public CLI facade in `scripts/writer/` without moving internals. Owner: runtime worker. Gate: reviewer + tester; proves compatibility first.
3. Canonical package boundary and extractor comparison. Owner: runtime worker; experimenter only for behavior/performance comparison with fixtures. Gate: reviewer + tester.
4. Researcher-to-writer contract adapter and aggregate release gate. Owner: integration worker. Gate: reviewer + tester.
5. Move semantic runtime into canonical writer package and update all authorities/agents/tests. Owner: migration worker. Gate: reviewer + structure scan + tester.
6. Archive handoff and proven dormant writer branches under `легаси/writer/`. Owner: archive worker. Gate: reviewer + tracked-reference scan + full writer suite.
7. Live deployment sync, final audit, and runbook. Owner: integration worker. Gate: reviewer + tester + health check.

Each phase must leave the repository runnable and independently revertible. No phase advances with unresolved material findings.

## Verification path

- Import and CLI compatibility tests for every old and new entrypoint during migration.
- Capability snapshot/preflight and writing-stage bundle resolution.
- Writer boundary, draft loop, claim verification, citation trace, and route tests.
- Recursive tracked-reference and forbidden-path scans before every move.
- `git diff --check`, compile/import smoke, environment validation, and health check.

## Current status

P6A external binding cleanup is complete in the reviewed migration branch: public Writer CLI is the external command surface, provider/env bindings point at `scripts/writer/`, and nested Writer deployment planning is recursive. Combined migration regression is 81/81 PASS.

P6B archive remains fail-closed BLOCKED until accepted `writer_core_handoff` contracts/fixtures are integrated into canonical Writer and old compatibility-test references are retired. No archive has been performed.

P6B semantic handoff implemented in migration branch: Researcher verification is read-only/hash-checked; selected handoff contracts/fixtures are byte-identical and provenance-bound; aggregate release has independent EVIDENCE/TRACEABILITY/SEMANTIC_ROUNDTRIP gates. Pending independent full gate and archive commit.

P6C archive completed in migration branch after READY proof: superseded writer-core and the complete tracked handoff v0.3.0 unit moved under легаси/writer with pre-move SHA-256 inventory. Post-archive writer regression and inventory checks are green. P7 live deployment verification remains.
