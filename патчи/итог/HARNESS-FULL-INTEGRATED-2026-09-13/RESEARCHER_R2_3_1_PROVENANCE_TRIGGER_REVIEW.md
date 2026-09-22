# RESEARCHER R2.3.1 — provenance dependency adapter and SourceCatalog trigger

Status: implemented and regression-tested on 2026-09-12.

## Purpose

Remove hand-authored dependency lists from the normal R2.3 path. Existing provenance is compiled into the deterministic dependency model, then a real Writer SourceCatalog semantic change can reach the existing Researcher impact/reopen reducer.

## Implemented block

`researcher_core/provenance_dependencies.py` adds:

- `SourceIdentityBinding`;
- `SourceCatalogSemanticChange`;
- `ProvenanceDependencyBuild`;
- `build_knowledge_dependencies()`;
- `source_catalog_change_from_writer()`;
- `resolve_catalog_change()`;
- `assess_source_catalog_change()`;
- `reopen_from_source_catalog_change()`.

The module is an adapter/orchestration boundary only. `invalidation.py` still owns impact semantics and historical reopen state mutation.

## Provenance mapping

- Source -> EvidenceSpan: HARD.
- Evidence/claim GraphEdge source -> EDG relation: HARD relation provenance.
- EDG -> target: typed relation dependency, with explicit group/quorum support.
- Challenge resolution evidence -> RRS: HARD justification.
- Challenge resolution claims -> RRS: CONTEXTUAL.
- VALIDATED ResearchTraceLinks can restore EVD/CLM -> RRS justification when the assessment artifact itself is not supplied.

## Source identity boundary

Writer SourceCatalog source IDs are not assumed to equal Researcher `SRC-*` IDs. `SourceIdentityBinding` is required. Missing, ambiguous, or stale-hash bindings fail closed.

This is intentionally stricter than matching by file name, DOI, title or path.

## Integration verification

A test executes the real Writer `scripts.writer.sources.source_catalog.upsert()` twice, changes both byte SHA and normalized text hash, observes `change_class=SEMANTIC`, maps the catalog source to a canonical Researcher Source and obtains `REOPEN_REQUIRED` for the dependent resolution.

A second E2E fixture continues through `reopen_from_impact`: resolved Gap -> REOPENED ResearchChallenge -> ACTIVE historical CHALLENGE card -> new ChallengeIteration.

## Limitations / development path

1. Identity binding is explicit and not yet a durable shared registry (TD-021).
2. EvidenceSpan-only semantic changes are not yet a first-class cross-orchestrator event.
3. GraphEdge state is not versioned/staled canonically yet; R2.3.3 remains open.
4. Dependency compilation is on demand, not a durable incremental index.
5. No learned dependency inference. Explicit provenance and deterministic relation rules remain authority.

Future complexity should grow in that order. Jumping directly to an ATMS/global learned graph would make provenance harder to audit before the simpler model is exhausted.

## Regression status

- R2.3.1 focused tests: 9/9 PASS.
- Combined R1/R1.1/R2/R2.1/R2.2/R2.3/R2.3.1 selected suite: 53/53 PASS.
- Full Researcher suite: 413 total, 409 PASS, same four pre-existing Guard/LocalCorpus failures tracked under TD-015.
- Runtime policy compiler: PASS, hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`.
- Capability policy compiler: PASS, hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`.
- compileall: PASS.
- git diff --check: PASS.

## Demo artifact

`artifacts/researcher_r2_3_1/source_catalog_reopen_demo.json` records a real Writer SourceCatalog semantic update, explicit catalog->SRC binding, compiled dependency path, impact state and historical challenge reopen.
