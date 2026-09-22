# Implementation Tracker

## WS-24 Writer unification

- [x] Phase 1: executable migration map. No runtime moved.
- [x] Phase 2: public CLI facade.
- [x] Phase 3: extractor consolidation experiment and accepted canonical boundary.
- [x] Phase 4/5 implementation: semantic runtime and Writer-owned gates consolidated under `scripts/writer/`.
- [x] Phase 6A: external bindings and recursive sync use canonical Writer.
- [x] Phase 6B.1: select and hash-bind runtime-relevant handoff contracts/fixtures.
- [x] Phase 6B.2: add read-only Researcher verification adapter.
- [x] Phase 6B.3: add independent evidence/traceability/semantic aggregate release gate.
- [x] Phase 6B.4: independent reviewer/tester gate and Git boundary.
- [x] Phase 6C.1: archive-readiness READY proof.
- [x] Phase 6C.2: byte-for-byte archive of superseded runtime and complete handoff unit.
- [x] Phase 6C.3: post-archive full regression, inventory/hash check and reviewer gate.
- [ ] Phase 7: live deployment dry-run, capability/health verification and final runbook.

Rule: an archive is a move with provenance and rollback, not a cleanup opportunity.

## WS-25 REFERENCE-TRACE-001

- [x] Add graph digest to `ReferenceBundle` profile from canonical Writer graph artifacts.
- [x] Add `ReferenceFragment/1.0` with source hash, locator, section role, style features and graph digest.
- [x] Add deterministic `reference.select` with hard role/kind/language/section filters before ranking.
- [x] Add universal `EvidenceSpan/1.1` for text spans and artifact locators.
- [x] Extend document inspection / local corpus to PDF, DOCX, ODT, DJVU (degraded when extractor unavailable), MD/text and existing table/image locators.
- [x] Add `SourceCatalog/1.1` with source version history.
- [x] Add `SearchMemory/1.0` and `library.search` over local FTS + source catalog.
- [x] Add `library.ingest` for persistent electronic-library indexing.
- [x] Add `DraftRequest/1.0` separating style references from evidence references.
- [x] Add concrete `ValidationPlan -> ResearchDispatchContract` routing without exposing backend names to Writer.
- [x] Add DOM source -> claim -> paragraph dependency graph and deterministic source-change invalidation.
- [x] Add ChangeLedger -> Job event/provenance bridge.
- [x] Run six-document role-swapping benchmark and one end-to-end source-update scenario.
- [x] Full regression and policy compiler gates green.
- [ ] Deferred to Researcher hardening: canonical textual entailment, uncertainty/justification tribunal, source identity resolution beyond path/sha, external provider live activation, semantic search recall.

## WS-26 WRITER-COMPOSE-001

- [x] C1.1 Add `DocumentCard/1.0` and derived-artifact store keyed by source/version.
- [x] C1.2 Add fragment-local language detection (`ru/en/de/mixed/unknown`).
- [x] C1.3 Add lazy per-fragment graph fingerprint with source locator/hash propagated to graph nodes and edges.
- [x] C1.4 Add two-stage style reference selection: hard filters -> cheap shortlist -> graph enrichment/rerank.
- [x] C2.1 Add `WritingPolicy/1.0` between reference preparation and claim loading.
- [x] C2.2 Add lexical-safe `StyleInstructionArtifact/1.0`; reference excerpts are not forwarded as style instructions.
- [x] C3.1 Extend `DraftRequest/1.0` with policy/style artifacts.
- [x] C3.2 Add `WriterAgentDispatchContract/1.0` without backend/provider names.
- [x] C3.3 Add `DraftArtifact/1.0` authorization check and research-debt signal for unauthorized claims.
- [x] C3.4 Add optimistic-concurrency `writer_dom_patch/1.0` with base/paragraph hash conflict detection.
- [x] C4.1 Extend ChangeLedger to nested real DOM paragraphs and touched source/claim propagation.
- [x] C4.2 Distinguish byte-only source changes from semantic changes using normalized content hash.
- [x] C4.3 Add reducer transition to `PENDING_REVALIDATION` / `SUPPORTED_WITH_STALE_EVIDENCE`.
- [x] C4.4 Add `RepairRequest/1.0` for selective paragraph repair only.
- [x] C4.5 Add invalidation artifact -> Job event bridge.
- [x] Add explicit `writing-policy` route stage and capability/provider bindings.
- [x] Five-document lazy-enrichment benchmark and full compose/source-update scenario.
- [x] Full regression / runtime compiler / capability compiler / `git diff --check` gates green.
- [ ] Deferred: live invocation of external OpenCode writer-agent; current boundary is a deterministic dispatch/output contract.
- [ ] Deferred: semantic identity reconciliation for renamed/duplicate library sources.
- [ ] Deferred: embeddings as secondary recall only after deterministic FTS/search-memory behavior stabilizes.

## WS-27 WRITER-V1-FREEZE-001

- [x] Replace language hard-reject for STYLE with tiered authority: same-language `FULL`, cross-language `STRUCTURE_ONLY`.
- [x] Ensure cross-language references cannot drive lexical/syntactic surface style or hedging density.
- [x] Add `claim_evidence_selection/1.0` and per-claim evidence mapping in DraftRequest.
- [x] Add `ProposedClaim/1.0`; DraftArtifact blocks unregistered new propositions and exposes research debt.
- [x] Split verification process state, evidence verdict and epistemic state while preserving legacy verdict compatibility.
- [x] Make DOM paragraph claim bindings authoritative after patch; rendered `[C-*]` markers are checked projections.
- [x] Add authority-binding failure into traceability release without changing the three top-level release gates.
- [x] Separate source invalidation claim state from evidence verdict; preserve deterministic reducer ownership.
- [x] Update article-writer, writing-orchestrator and shared Writer contracts to forbid direct search/provider knowledge from prose Writer.
- [x] Add `reference.evidence.select` capability/provider/stage routing and rebuild capability snapshot.
- [x] Regression: 117/117 tests PASS; runtime/capability compilers, compileall and diff checks PASS.
- [ ] Deferred to Researcher refactor: semantic textual entailment, evidence-quality tribunal, source identity resolver, external provider live activation.
- [ ] Deferred environment-dependent check: live invocation of the external OpenCode `article-writer` agent against WriterAgentDispatchContract.
