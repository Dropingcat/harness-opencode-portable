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

## WS-28 RESEARCHER-R1-RESEARCH-DOM

- [x] Introduce immutable `ResearchCard`, `ResearchMap`, `ResearchDOM`, `ResearchPatch`.
- [x] Add `PlanningInquiryTurn`, `DecompositionSession`, and deterministic decomposition compiler.
- [x] Preserve multidimensional card metadata: directions, disciplines, question types, methods, capabilities.
- [x] Apply changes only through revision-checked reducer; reject missing parents, duplicates, cycles and stale revisions.
- [x] Validate on the BCC-lattice planning fixture.

## WS-29 RESEARCHER-R1.1-PLANNING-RUNTIME

- [x] Add policy-backed `PlanningGate` for executable leaves, depth, size and structural validity.
- [x] Persist and restore `ResearchDOM` through the existing SQLite/unit-of-work substrate.
- [x] Add event replay for planning-card history.
- [x] Add typed `ResearchTraceLink` between ResearchCards and knowledge entities (`Claim`, `Gap`, `Conflict`, etc.).
- [x] Preserve separation: ResearchDOM describes what is being done; KnowledgeGraph describes what is known.
- [x] Regression: new R1/R1.1 planning tests PASS; no new failures beyond pre-existing Guard/LocalCorpus baseline debt.
- [ ] Next: R2 KnowledgeGraph reconciliation and adaptive `Gap/Conflict -> ResearchChallenge -> CHALLENGE card` feedback.

## WS-30 Unified recursive object-processing principle

- [x] Treat task/goal/direction/question/claim/gap/evidence/paragraph/code-defect as typed information objects with stable identity and provenance.
- [x] Decompose only while decomposition increases executability, verifiability or information gain; no claim of an absolute computable Kolmogorov minimum.
- [x] Represent specialists, tools and skills as typed selectable entities with capabilities, constraints and history.
- [x] Use code-owned routing/ranking to select processors for each object; LLMs may propose semantics but do not mutate authority directly.
- [x] Preserve tree = decomposition/history/ownership, graph = semantic relations, routing history = why processors/tools were selected.
- [ ] Future: learn routing weights from accumulated outcomes after sufficient history exists; do not prematurely train on sparse decisions.

## WS-31 RESEARCHER-R2-KNOWLEDGE-RECONCILIATION

- [x] Keep canonical `Gap` and `Conflict` entities from `researcher_core.r1_entities`; do not duplicate knowledge nodes in planning.
- [x] Add `ResearchChallenge/1.0` as the typed request to investigate an admitted Gap/Conflict.
- [x] Add deterministic `Gap -> ResearchChallenge` and `Conflict -> ResearchChallenge` conversion.
- [x] Materialize a ResearchChallenge as a historical `CHALLENGE` ResearchCard through a revision-checked ResearchPatch.
- [x] Inherit planning dimensions from the full ResearchDOM lineage so Dn/discipline/method context survives feedback.
- [x] Add `ResearchTraceRelation.ADDRESSES` and allow `RCH` trace targets.
- [x] Add forward/reverse `ResearchKnowledgeProjection` over existing ResearchTraceLinks.
- [x] Persist ResearchChallenge and trace links through the existing SQLite/UnitOfWork substrate.
- [x] Validate adaptive feedback on the BCC/XRD residual-stress Gap fixture.
- [x] Regression: 6/6 R2 tests PASS; full Researcher suite has only the same 4 pre-existing Guard/LocalCorpus failures.
- [x] R2.1: feed CHALLENGE cards into the same PlanningDialectic compiler, compile local QUESTION/METHOD/TASK subtrees, gate them locally, and atomically activate the challenge card.
- [ ] Next R2.2: add conflict-specific decomposition and resolution-state projection.


## WS-32 RESEARCHER-R2.1-CHALLENGE-DECOMPOSITION

- [x] Add local `evaluate_planning_subtree_gate` so one pending feedback branch does not block another.
- [x] Add `expand_challenge_with_decomposition` over existing `DecompositionSession` + `ResearchCardProposal` contracts.
- [x] Require challenge-local proposal ancestry; reject cross-branch mutation.
- [x] Require at least one executable TASK/DELEGATION leaf before accepting challenge expansion.
- [x] Apply subtree creation and CHALLENGE `PLANNED/BLOCKED -> ACTIVE` transition in one revision-checked patch.
- [x] Reuse the same decomposition compiler as root planning; no second semantic planner introduced.
- [x] Validate BCC/XRD `residual_stress_not_excluded` feedback as Q1/A1/Q2/A2 -> QUESTION/METHOD/TASK subtree.
- [x] Regression: 6/6 R2.1 tests PASS; combined R1/R1.1/R2/R2.1 selected suite 30/30 PASS.
- [x] Full Researcher suite: 389 tests total, only the same 4 pre-existing Guard/LocalCorpus failures.
- [ ] Next R2.2: conflict-specific decomposition, resolution-state projection, and close/reopen semantics for ResearchChallenge/CHALLENGE cards.

## WS-33 RESEARCHER-R2.2-CHALLENGE-RESOLUTION

- [x] Add typed `ChallengeResolutionAssessment/1.0` with evidence/claim refs, rationale and optimistic expected challenge revision.
- [x] Add explicit outcomes: `RESOLVED`, `STILL_OPEN`, `BLOCKED`, `REOPENED`.
- [x] Project resolution onto canonical `Gap/Conflict`, `ResearchChallenge`, and historical CHALLENGE card without duplicating knowledge entities.
- [x] Distinguish conflict resolution modes, including `SCOPE_MISMATCH`, from substantive agreement.
- [x] Reject `INSUFFICIENT_EVIDENCE` as a resolving conflict verdict.
- [x] Add close/block/reopen semantics for Gap/Conflict and Challenge/Card lifecycles.
- [x] Synchronize R2.1 activation so successful challenge decomposition can advance `ResearchChallenge` to `ACTIVE` with revision increment.
- [x] Persist resolution assessments through the existing SQLite/UoW substrate.
- [x] Record resolution evidence and source entity via ResearchTraceLinks.
- [ ] Next R2.3: resolution-driven subtree completion/replanning and source/evidence invalidation that can reopen resolved challenges automatically.
- [ ] Tech debt tracked separately as TD-015..TD-017; do not hide baseline failures or routing/duplicate-core debt inside feature completion.

## WS-34 ARCHITECTURE-DOCUMENTATION-AND-LEGACY-RECONCILIATION

- [x] Add `ARCHITECTURE_BLOCK_DOCUMENTATION_STANDARD.md`; architecture documentation is part of block completion.
- [x] Reconcile supplied `doc_AI_ReWriter.zip` legacy concepts against current Researcher design.
- [x] Record legacy lineage for topics tree, dynamic experts, tribunal, local escalation, OPEN cutter, search validation and accumulated domain map.
- [x] Record intentional non-reuse of orangepi shell/runtime/provider coupling.
- [x] Pre-document R2.3 authority boundary, failure behavior, limitations and complexity ladder before implementation.
- [ ] Maintain the block-card standard for every subsequent R2.3+ implementation review.

## WS-35 RESEARCHER-R2.3-INVALIDATION-AND-HISTORICAL-REOPEN

- [x] Add `DependencyImpactAssessment/1.0`.
- [x] Add explicit HARD/SOFT/CONTEXTUAL dependency semantics for the initial supported relation set.
- [x] Add selective resolution invalidation and relation-level stale markers.
- [x] Reopen the existing ResearchChallenge rather than creating an unrelated replacement challenge.
- [x] Preserve previous resolution as immutable historical iteration through `ChallengeIteration/1.0`.
- [x] Add bounded dependency traversal with fan-out/cycle diagnostics and fail-closed `INCOMPLETE`.
- [x] Validate redundant-evidence, sole-evidence, relation-only, scope-context, stale-revision and unrelated-branch fixtures.
- [x] Persist multiple challenge iterations in the existing SQLite/UoW substrate.
- [x] Update `RESEARCHER_R2_3_INVALIDATION_ARCHITECTURE.md` with actual implementation limits after the first slice.
- [x] R2.3.1: derive `KnowledgeDependency` automatically from canonical Source/EvidenceSpan, ResearchTraceLink, GraphEdge and resolution provenance (TD-018 closed).
- [x] R2.3.2 first bridge slice: real Writer `SourceCatalog` SEMANTIC change -> explicit source identity binding -> R2.3 impact/reopen; BYTE_ONLY stays no-impact (TD-019 closed).
- [ ] Follow-up: first-class shared EvidenceSpan semantic-change event and common Source identity (TD-021).
- [x] R2.3.3: version/stale canonical `GraphEdge` relations implemented with replayable `EDGE_STATE_CHANGED`, endpoint-safe invalidation, artifact visibility and lifecycle-aware dependency compilation.
- [ ] Tech debt: remove SQLite ResourceWarnings (TD-020); retain TD-015..TD-017.


### R2.3.3 relation lifecycle boundary

- [x] `GraphEdgeState`: ACTIVE/STALE/SUPERSEDED/INVALIDATED.
- [x] Optimistic revision-checked relation transitions.
- [x] Impact `stale_relation_ids` -> canonical EDG reducer.
- [x] Legacy event-record compatibility and event replay.
- [x] Artifact rendering includes relation state/revision.
- [x] Provenance dependency compiler excludes terminal edges and marks stale-edge dependencies stale.
- [x] Full Researcher regression: only TD-015 baseline failures remain.
- [ ] TD-022: dedicated durable relation-state/history projector/index.


## WS-36 RESEARCHER-R3-TASK-EXECUTION-AND-PEER-DELEGATION

- [x] Freeze R2.x as stable planning/knowledge base; document non-blocking future directions in `RESEARCHER_R2_BRANCH_FUTURE_DIRECTIONS.md`.
- [x] Add `RESEARCHER_R3_TASK_EXECUTION_ARCHITECTURE.md` before implementation with authority, failure semantics and complexity ladder.
- [x] Add typed `TaskExecutionPlan/1.0`, `DelegationRequest/1.0`, `TaskExecutionResult/1.0`.
- [x] Compile only executable leaf TASK/DELEGATION cards; reject non-leaf/stale/missing-provider cases fail-closed.
- [x] Execute Researcher-owned local capabilities through existing CapsuleRegistry and preserve output as untrusted observation.
- [x] Reuse existing `scripts/jobs/job_ctl.py` parent/child semantics for peer delegation; do not create a second scheduler.
- [x] Preserve required/optional child reconciliation semantics from existing Job runtime.
- [x] Revision-check ResearchCard transitions `PLANNED/READY -> ACTIVE -> COMPLETED/BLOCKED`.
- [x] Add SQLite/UoW audit persistence for execution plans, delegation requests and terminal results.
- [x] Verify execution completion does not directly admit Claim/Evidence truth.
- [x] R3 targeted tests: 10/10 PASS; selected R1→R3: 71/71 PASS.
- [x] Full Researcher: 431 tests, 427 PASS, same four TD-015 Guard/LocalCorpus failures.
- [x] R3.1: typed admission bridge from successful execution outputs to ClaimProposal/QuantityProposal/Source/EvidenceSpan via deterministic preflight + existing ClaimRegistry + ResearchTraceLink provenance.
- [ ] R3.2 next: explicit post-admission semantic edge compiler and dependency-closed Derivation/Assumption admission; no inferred SUPPORTS/QUANTIFIES edges.
- [ ] R3.x later: live Coder/Writer transport, retries/checkpoint/resume policy binding, persistent child/outbox orchestration.


## WS-37 RESEARCHER-R3.1-EXECUTION-OUTPUT-ADMISSION

- [x] Document R3.1 authority and fail-closed boundary before code in `RESEARCHER_R3_1_EXECUTION_ADMISSION_ARCHITECTURE.md`.
- [x] Add `ExecutionAdmissionProposal/1.0` (`EAP-*`) and `ExecutionAdmissionReceipt/1.0` (`EAR-*`).
- [x] Compile only successful typed CapsuleObservation payloads; reject empty/untyped outputs.
- [x] Require explicit typed `ProposalBatch` adapter output for peer artifacts; no generic JSON/text admission.
- [x] Revision-check the completed source TASK before admission.
- [x] Run deterministic Atomicity/Numeric/Source/Evidence preflight before registry mutation.
- [x] Reuse canonical R0 ClaimRegistry with ALL_OR_NOTHING commit; no second registry introduced.
- [x] Add `QTY` as a ResearchTrace target and project `PRODUCED` links from TASK to every admitted canonical entity.
- [x] Add SQLite/UoW audit projection for admission proposal/receipt identity and provenance.
- [x] R3.1 tests 11/11 PASS; selected R1→R3.1 regression 82/82 PASS.
- [x] Full Researcher: 442 tests, 438 PASS, same four TD-015 Guard/LocalCorpus failures.
- [ ] R3.2: declared post-admission relation compilation, temp-ID mapping and Derivation/Assumption admission.
- [ ] R3.x: policy-selected validator bundles, NEEDS_REVIEW/QUARANTINED routes, human/Tribunal admission review.

### WS-38 — Researcher R3.2 explicit semantic linking
Status: DONE (L1)
- Added `AdmissionIdentityMap/1.0`, `SemanticRelationProposal/1.0`, `SemanticLinkReceipt/1.0`.
- Explicit-only post-admission `GraphEdge` creation; no co-occurrence inference.
- L1 shapes: EVD->CLM SUPPORTS/CONTRADICTS, QTY->CLM QUANTIFIES, CLM->CLM DERIVED_FROM.
- Added EDG as ResearchTraceLink target.
- Cross-admission linking intentionally deferred.
- Architecture: `RESEARCHER_R3_2_SEMANTIC_LINKING_ARCHITECTURE.md`.
- [x] R3.2 targeted 10/10 PASS; selected R1→R3.2 regression 85/85 PASS.
- [x] Full Researcher: 452 tests, 448 PASS, same four TD-015 Guard/LocalCorpus failures; TD-020 ResourceWarnings remain.
- [ ] Next R3.3: relation/derivation assessment or cross-admission endpoint authorization, chosen after architecture review; do not conflate edge admission with epistemic verdict.


### WS-39 — Researcher R3.3 canonical relation assessment
Status: DONE (L1)
- [x] Document R3.3 authority before implementation.
- [x] Add `RelationAssessmentProposal/1.0` (`RAP-*`) and `RelationAssessment/1.0` (`RAS-*`).
- [x] Separate edge kind, edge lifecycle and reasoning eligibility.
- [x] Deterministically assess SUPPORTS/CONTRADICTS using scope/directness/method/evidence signals.
- [x] Add basic QUANTIFIES assessment; keep DERIVED_FROM explicitly INCONCLUSIVE at L1.
- [x] Emit `ResearchTraceLink(VALIDATED -> EDG)` with assessment provenance.
- [x] REJECTED relation can project to R2.3.3 `INVALIDATED` without mutating endpoints.
- [x] Strict dependency compilation excludes unassessed/inconclusive/rejected semantic use and keeps ACCEPTED/QUALIFIED.
- [x] Service artifact exposes relation assessments separately from graph edge lifecycle.
- [x] Full pipeline fixture verifies execution -> admission -> linking -> assessment -> lifecycle -> strict dependency -> artifact.
- [x] R3.3 targeted 15/15 PASS; selected R1->R3.3 117/117 PASS; full Researcher 467 total / 463 PASS with the same four TD-015 baseline failures.
- [ ] R3.4: make assessed-relation gate mandatory in the live R3 reasoning path and feed blocked relation assessments back into Gap/ResearchChallenge.
- [ ] TD-029..TD-032 track integration and kind-specific validator gaps.


### WS-40 — Researcher R3.4 control-loop closure
Status: DONE (L1)
- [x] Add strict R3 reasoning facade; assessed relation use is mandatory on the new R3 path.
- [x] Compile `INCONCLUSIVE/BLOCKED` RelationAssessment into typed blocking Gap.
- [x] Reuse existing `challenge_from_gap` + CHALLENGE materialization; no second planner.
- [x] Enforce one ResearchChallenge per RelationAssessment identity.
- [x] Persist relation-generated Gap + ResearchChallenge atomically via existing SQLite/UoW.
- [x] Expand relation challenge through existing PlanningDialectic to executable TASK and local PlanningGate PASS.
- [x] Add canonical ClaimRegistry GraphEdge update path for revisioned `EDGE_STATE_CHANGED`.
- [x] Keep REJECTED relation lifecycle separate from research-gap generation.
- [x] R3.4 targeted 10/10 PASS; selected R1→R3.4 117/117 PASS.
- [x] Full Researcher 477 total / 473 PASS; same four TD-015 baseline failures; TD-020 warnings remain.
- [x] Close TD-029/TD-030/TD-031.
- [ ] R3 future, non-blocking for R4: TD-032 richer DERIVED_FROM/QUANTIFIES validators; TD-027/028 identity/cross-admission linking; TD-022 relation history index.
- [ ] Next major phase: R4 deterministic Tribunal composition over Direction/Discipline/QuestionType/MethodView/ClaimProfile.

### WS-41 — Researcher R3.5 multidimensional uncertainty field
Status: DONE (L1)
- [x] Add `UncertaintyProfile/1.0` (`UPR-*`) as a multidimensional derived projection, not a scalar confidence.
- [x] Add operational levels `RESOLVED/QUALIFIED/MATERIAL/BLOCKING/UNCHARACTERIZED` and separate `blocking` semantics.
- [x] Add typed uncertainty axes and assessment-method vocabulary.
- [x] Preserve normalized relation-assessment signals (scope/directness/method/evidence) for downstream uncertainty projection.
- [x] Derive L1 uncertainty components from RelationAssessment, Gap, Conflict and explicit numeric uncertainty observations.
- [x] Reuse existing Decimal interval-overlap semantics; do not invent universal percentage thresholds.
- [x] Add `ReviewWorkField/1.0` (`RWF-*`) that defines what must be assessed without selecting Tribunal specialists.
- [x] Add durable SQLite/UoW projection for UPR/RWF.
- [x] Expose `uncertainty_profiles` and `review_work_fields` in service artifacts.
- [x] Add pre-Tribunal E2E fixture with qualified method/evidence, blocking evidence, admitted Gap/Conflict and decision-critical numeric uncertainty.
- [x] R3.5 targeted uncertainty/regression slice 88/88 PASS.
- [x] Full Researcher 488 total / 484 PASS; same four TD-015 baseline failures; TD-020 warnings remain.
- [ ] TD-033: typed automatic adapters for provenance/freshness/causality/assumption/extrapolation + typed Gap taxonomy.
- [ ] TD-034: canonical Quantity uncertainty model instead of explicit projection-only numeric uncertainty.
- [ ] Next major phase R4: map RWF assessment needs + ResearchDOM dimensions to deterministic permanent/dynamic Tribunal composition.

### WS-42 — Researcher R4.1 deterministic Tribunal composition
Status: DONE (L1)
- [x] Preserve R3.5 `ReviewWorkField` as the what-to-assess boundary.
- [x] Add typed Tribunal composition contracts and deterministic compiler.
- [x] Add versioned closed role policy; permanent meta-panel is policy-defined.
- [x] Add exact axis/method + structural ResearchDOM lineage routing.
- [x] Add content-addressed R4 `AssessmentNeedRef` bridge because R3.5 AssessmentNeed has no EntityId.
- [x] Add `equivalence_group + selection_priority` for deterministic synonym-role deduplication.
- [x] Validate declared capabilities/tools against central authority registries.
- [x] Add evidence-view contracts including fail-closed FRESH_CONTEXT semantics.
- [x] Add policy hash and composition fingerprint.
- [x] Add 11 R4.1 unit tests; targeted R4.1 currently 11/11 PASS.
- [x] Targeted R3.5 + R4.1 slice currently 22/22 PASS.
- [x] Full Researcher: 499 total / 495 PASS / same four TD-015 failures; runtime/capability compiler hashes unchanged; compileall/diff checks PASS.
- [x] Add R3.5 -> R4.1 BCC/XRD demo artifact, implementation review and pipeline audit.
- [x] Reconcile architecture docs, decision log, tech debt and current-state documentation.
- [x] Create Git commit, milestone package and recovery bundle.
- [x] Post-R4.2 hardening: composition fingerprint now covers RoleBrief authority fields; plan integrity validator + 1 regression test added (current R4.1 test file: 12 tests).
- [ ] R4.2 next: executable asymmetric evidence slicing; no live dialogue yet until leakage/authority gates are proven.


### WS-43 — Researcher R4.2 executable Tribunal evidence slicing
Status: DONE (L1)
- [x] Compile R4.1 `EvidenceViewPolicy` into typed per-role `TribunalEvidenceSlice`.
- [x] Add FULL_RELEVANT / SUPPORT / COUNTER / FRESH_CONTEXT / METHOD_ONLY executable view semantics.
- [x] Enforce FRESH_CONTEXT structural leakage controls for provenance, prior conclusions, support/counter polarity, selection reasons and GraphEdge/Source target metadata.
- [x] Use canonical typed refs/GraphEdges; no legacy keyword/trust fallback.
- [x] Fail closed for missing canonical refs on blocking assignments and cross-run/plan mismatches; target-only executable blocking work is not falsely rejected.
- [x] Add deterministic max-ref bounding, READY/PARTIAL/BLOCKED status and fingerprints.
- [x] Reuse one R4-wide `AssessmentNeedRef` bridge instead of recomputing private IDs.
- [x] Separate projectable semantic/evidence refs from nonprojected control refs discovered by E2E.
- [x] Add nearest-chain E2E `RelationAssessment -> RWF -> composition -> EvidenceSlice`; first run found and drove repair of the RAS/control-ref seam.
- [x] Add 17 R4.2 local/E2E tests; 17/17 PASS.
- [x] Targeted R3.5 + R4.1 + R4.2: 40/40 PASS.
- [x] Full Researcher: 517 total / 513 PASS / same four TD-015 failures.
- [x] Runtime/capability compiler hashes unchanged; compileall/diff checks PASS; executable demo PASS.
- [x] Add architecture, implementation review, pipeline audit, decision-log and debt updates after executable validation.
- [x] Create feature Git commit and milestone ZIP `RESEARCHER-R4.2-EVIDENCE-SLICING-001.zip` (SHA256 `dab5a998af72c6b479b88ae0360eb760511327fc3d7b70536e6e9adf23610a88`); finalize recovery/handoff at boundary commit.
- [x] Revalidate frozen R4.2 checkout after packaging: targeted 40/40 PASS, full 513/517 with unchanged TD-015 only, compilers/compileall/demo/diff PASS; package and recovery checksums verified.
- [ ] TD-040: replace remembered `PYTHONPATH=scripts/researcher` setup with one repository-owned Researcher test/E2E acceptance command.
- [ ] R4.3 next: typed Inquiry/Argument contracts + independent first-pass execution over slices using existing Job/Attempt runtime; resolve remaining TD-037 provider-health binding first.
- [ ] R4.4 later: conditional Advocate/FOR-vs-AGAINST + bounded `Q1 -> A1 -> Q2(on A1) -> A2` and typed discovery feedback.

## WS-44 RESEARCHER-R4.3-INDEPENDENT-ROLE-EXECUTION

Date: 2026-09-13
Status: L1 DONE; feature implementation, validation/review and milestone package complete. Recovery/handoff boundary finalizing.

- [x] Write `RESEARCHER_R4_3_INDEPENDENT_ROLE_EXECUTION_ARCHITECTURE.md` before branch close.
- [x] Add typed `InquiryContract/1.0`, `InquiryTurn/1.0` and `ArgumentArtifact/1.0` contracts.
- [x] Bind one admitted role to one exact R4.2 EvidenceSlice using plan/slice/instruction fingerprints and assigned AssessmentNeed refs.
- [x] Validate worker citations/discoveries/additional-evidence requests against the bound slice and assigned needs; fail closed on widening.
- [x] Distinguish semantic `OPEN` from runtime/validation failure (`FAILED_NO_OUTPUT`).
- [x] Reuse existing `scripts/jobs/job_ctl.py` child Job/Attempt lifecycle; no second scheduler.
- [x] Prove vertical XRD E2E: `RelationAssessment -> UncertaintyProfile -> ReviewWorkField -> TribunalCompositionPlan -> EvidenceSlice -> InquiryContract -> child Job/Attempt -> InquiryTurn + ArgumentArtifact`.
- [x] Verify downstream seam by projecting `ArgumentArtifact` into controlled `PriorReviewArtifact` for later view-policy disclosure.
- [x] Add fail-closed E2E for a worker attempting to cite hidden evidence.
- [x] Add semantic Role Handbook separate from authority policy.
- [x] Add first-pass/challenger/cross-exam role variants as semantic instruction modes; R4.3 L1 runtime permits only first-pass.
- [x] Bind common handbook stop conditions into RoleInstructionPack fingerprint.
- [x] Add deterministic code-owned `RoleHandbookFillRequest` + proposal-only skeleton generation for missing selected-role guidance/variants.
- [x] Keep domain role-pack admission explicitly deferred under TD-036.
- [x] Prove multi-role independent execution with distinct views/instructions (`xrd_specialist` METHOD_ONLY; `crystallographer` CLAIM_PLUS_SUPPORT) and separate child Jobs/Arguments.
- [x] Add repository-owned `scripts/run_researcher_acceptance.py` test/gate bootstrap; closes TD-040 after full/gate reproduction.
- [x] R4 targeted acceptance: 52/52 PASS.
- [x] Full Researcher pre-doc freeze: 529 total / 525 PASS / same four TD-015 failures.
- [x] Runtime/capability compiler gates: PASS with unchanged hashes; compileall PASS.
- [x] Post-documentation freeze re-run + `git diff --check`: R4 52/52 PASS; full 529 total / 525 PASS / same four TD-015; compiler/static gates PASS.
- [x] Implementation review + pipeline audit after observed E2E.
- [x] Feature commit `b435c943d524f430c349bf390ce7b70f7c8968c5` and milestone ZIP `RESEARCHER-R4.3-INDEPENDENT-ROLE-001.zip` created; SHA256 `3a4f87332d1ecf909321a6f426d8780c867aa394fe1716d4eaadf4b78f442cfb`.
- [x] Complete Git recovery bundle/session handoff workflow prepared; final bundle/handoff is regenerated on the canonical closure HEAD immediately after this commit.

### R4.3 follow-on, deliberately not folded into L1

- live provider/tool binding and health for role workers (TD-037);
- persisted/queryable cross-layer traceability substrate (TD-038);
- admitted modular domain role packs (TD-036);
- production scientific role-worker quality/calibration;
- staged blind -> provenance/polarity reveal;
- Advocate/FOR-vs-AGAINST activation and Q1/A1/Q2/A2 dialogue, which belong to the next inquiry stage rather than first-pass execution.


## WS-45 RESEARCHER-R4.4-L1-DIALECTIC-OBSERVATION

Date: 2026-09-13
Status: L1 control substrate IMPLEMENTED; live dialogue workers/provider binding remain follow-on.

- [x] Add explicit `DialecticLevel` process ladder L0 independent -> L1 challenge -> L2 direct Q/A -> L3 question-on-answer -> L4 local research escalation -> L5 external escalation reserved.
- [x] Keep dialectic depth separate from epistemic confidence/truth.
- [x] Add multidimensional `EmergentIssueKind` vocabulary instead of scalar dialogue-complexity score.
- [x] Reuse typed R4.3 `InquiryDiscovery` / `AdditionalEvidenceRequest` as primary observed signals.
- [x] Add bounded `DialecticIssueProposal` for interaction-specific signals such as answer evasion, contradiction and capability gap; validate need/ref scope in code.
- [x] Add deterministic content-addressed issue signatures and repetition tracking.
- [x] Add progress observation from new typed issue, evidence-frontier change or position change.
- [x] Add explicit local issue lifecycle (`DialecticIssueResolutionProposal`: RESOLVED/STILL_OPEN) so convergence can close tracked dialogue problems without mutating Claim truth.
- [x] Add no-progress cutoff independent of nominal token/turn budget.
- [x] Add explicit full-chain turn counting support so questions consume process budget.
- [x] Add deterministic control actions for challenge, Q/A, Q-on-answer, local research, recomposition and stop boundaries.
- [x] Add depth/turn/Q-A-pair/token policy limits.
- [x] Validate historical linear turn chain `FIRST_PASS -> CHALLENGE -> QUESTION -> ANSWER -> QUESTION_ON_ANSWER -> REBUTTAL`.
- [x] Add explicit `EmergentIssue -> Gap` projection helper; observer itself remains non-authoritative.
- [x] Prove E2E: first-pass XRD issue -> Q1/A1 -> new assumption -> Q2(on A1)/A2 -> blocking evidence request -> L4 local research -> existing `ResearchChallenge`.
- [x] Add future-growth `ROLE_CARD_PORTABLE_DOM_FUTURE.md` for RoleCard/RoleReference/parameter graph/YAML DOM exchange while keeping runtime authority local.
- [x] Add new R4.4 tests to repository-owned R4 acceptance runner.
- [x] R4 targeted acceptance after post-E2E hardening: 67/67 PASS.
- [x] Full Researcher: 544 total / 540 PASS / same four TD-015 failures.
- [x] Runtime/capability compiler gates + compileall PASS with unchanged policy hashes.
- [x] Write post-E2E implementation review and pipeline audit.
- [x] Feature commit `e79e2d59e166a8d39642603f66112d4dc01f0fd3` (`researcher: bound r4 dialectic observation`).
- [x] Milestone ZIP `RESEARCHER-R4.4-DIALECTIC-OBSERVATION-001.zip`, SHA256 `330d79a9df87e8a13c66a3606e0d8a3d2b6cc4069e7d1efe9419cfa209258fd0`.
- [ ] Live challenger/questioner/answerer workers through shared provider binding (TD-037).
- [ ] Compiled cross-role disclosure contract and branching argument graph (TD-043).
- [ ] Calibrate interaction-only semantic observer proposals on real dialogue traces (TD-042).

## WS-46 RESEARCHER-R4.4-L2A-BRANCHING-ARGUMENT-GRAPH-ADVOCATE
Status: DONE (structural L2a; live provider execution deferred)

- [x] Add first-class versioned `ArgumentRelation/1.0` (`ARL-*`).
- [x] Add relation vocabulary `ATTACKS / UNDERCUTS / REPLIES_TO / DEFENDS`.
- [x] Add `ArgumentGraphProjection/1.0` (`AGP-*`) with roots, branch heads, revision/fingerprint and cycle checks.
- [x] Keep argument graph separate from KnowledgeGraph/Claim truth authority.
- [x] Admit `advocate` in local role policy without making it permanent or normally composable.
- [x] Add handbook `advocate/defense` semantic variant.
- [x] Add deterministic `AdvocateActivationDecision` gated by material admitted challenge and visible support.
- [x] Add branch-local `DialecticDisclosureContract/1.0` (`DDC-*`) for Advocate.
- [x] Add `AdvocateDefenseContract/1.0` (`ADC-*`) with policy/instruction/disclosure fingerprints and bounded refs.
- [x] Add Advocate outcomes `DEFEND / QUALIFY / CONCEDE_LOCAL_POINT / REQUEST_EVIDENCE / OPEN`.
- [x] Route Advocate output to cross-exam/control/local-research/open without truth mutation.
- [x] Add E2E with two branches where Advocate sees only one branch and hidden sibling evidence cannot leak.
- [x] Add E2E `Advocate REQUEST_EVIDENCE -> DialecticObserver -> Gap -> ResearchChallenge`.
- [x] Add E2E `Advocate DEFEND -> REPLIES_TO + DEFENDS` relations.
- [x] Keep TD-043 open until disclosure is generic across challenger/questioner/cross-exam, not defense-only.
- [x] Expand TD-044 with bounded future Writer claim/facet decomposition + round-trip reuse path.
- [x] Feature commit `910c2f98879278bb391ece71cd92287b8a913137` (`researcher: branch r4 argument graph with conditional advocate`).
- [x] Milestone ZIP `RESEARCHER-R4.4-L2A-ARGUMENT-GRAPH-ADVOCATE-001.zip`, SHA256 `c109e04fe658307a57a965ba7017a0d4963e17bf9f7423ef6f620ba5f5fe8107`.
- [x] Post-package acceptance: R4 76/76 PASS; full Researcher 553 total / 549 PASS / same four TD-015; compiler/static/JSON/YAML gates PASS.
- [ ] TD-037: execute live challenger/questioner/Advocate workers through shared provider-health binding.
- [ ] R4.4 L2b: generic disclosure compiler + typed question-target contract.
- [ ] Resume returned ResearchChallenge evidence into the exact unresolved argument branch/replay lineage.

## WS-47 RESEARCHER-R4.4-L2B-GENERIC-DISCLOSURE-BRANCH-HISTORY
Status: DONE (structural L2b; live provider execution deferred)

- [x] Extract generic `DialecticDisclosureContract/1.1` compiler from Advocate-specific path.
- [x] Preserve Advocate behavior through compatibility wrapper over generic DDC compiler.
- [x] Support disclosure purposes `CHALLENGE / DIRECT_QUESTION / QUESTION_ON_ANSWER / DEFENSE` plus reserved `CROSS_EXAM`.
- [x] Add stable `DialecticBranchRef` with graph snapshot/head separated from stable branch key.
- [x] Add `DialecticQuestionContract/1.0` (`DQC-*`) with typed target kind, parent/target refs, exact closure surface and policy/handbook fingerprints.
- [x] Enforce Q2 only against a newly admitted issue surface from prior answer observation.
- [x] Validate both `InquiryTurn.cited_refs` and `ArgumentArtifact` refs against DDC/DQC to prevent hidden-ref smuggling.
- [x] Add branch-scoped `DialecticBranchHistory` with independent no-progress/issues/Q-A count/token state.
- [x] Add branch history checkpoint serialize/restore/fingerprint validation.
- [x] Add DDC/DQC serialization round-trip and integrity validation.
- [x] Add exact `DialecticResearchResumeAnchor` for `Gap -> ResearchChallenge -> same branch/issue` continuation.
- [x] Add two-branch E2E: branch A Q1/A1/Q2/A2/local research while sibling B stays hidden/independent and can start later on latest AGP revision.
- [x] Keep Claim/GraphEdge/Gap truth mutation outside Tribunal contracts.
- [x] Add new L2b tests to repository-owned R4 acceptance runner.
- [x] TD-037 structural slice: execute bounded dialogue through shared provider-health binding (completed in R4.4 L3A); production semantic-provider E2E remains TD-037 partial.
- [ ] TD-044: semantic issue facet/equivalence with bounded Writer proposal bridge.
- [ ] TD-038: universal cross-layer traceability substrate beyond local branch anchors.
- [x] L2b architecture document + post-E2E implementation review + pipeline audit.
- [x] Pre-freeze acceptance: R4 82/82 PASS; full Researcher 559 total / 555 PASS / same four TD-015 failures; compiler/static/JSON/YAML gates PASS.
- [x] TD-043 closed by generic DDC/DQC branch disclosure acceptance.
- [x] TD-045 closed by branch-scoped history/replay + research resume acceptance.
- [x] Feature commit `8fc635160d9f3f90583d5e8e44a3206f4e7366ad` (`researcher: generalize r4 dialectic disclosure`).
- [x] Milestone ZIP `RESEARCHER-R4.4-L2B-DISCLOSURE-BRANCH-HISTORY-001.zip`, SHA256 `e83a12e7d666a5f2d3e2183164a620e50bac3c5b6939e1553c70f8458fcaaf61`.
- [x] Freeze acceptance: R4 82/82 PASS; full Researcher 559 total / 555 PASS / same four TD-015 failures; runtime/capability compiler + compileall + JSON/YAML + `git diff --check` PASS.

## WS-48 RESEARCHER-R4.4-L3A-PROVIDER-BINDING-EXECUTABLE-DIALOGUE

Date: 2026-09-13
Status: implementation + process-E2E complete; production semantic provider execution remains environment-blocked.

- [x] Restore work on canonical R4.4 L2b Git checkout; do not continue from orphaned non-Git partial directory.
- [x] Add `RoleProviderBinding/1.0` (`RPB-*`) using shared provider/capability/runtime authority.
- [x] Add `TribunalExecutionEnvelope/1.0` (`TEX-*`) as exact bounded provider input.
- [x] Add `ProviderExecutionReceipt/1.0` (`PER-*`) durable on completed/failed/timed-out/rejected paths.
- [x] Separate semantic Role, Provider and Runtime Tool identities.
- [x] Upgrade DQC to `dialectic-question-contract/1.1` with explicit `answer_role_id`; reject legacy 1.0 replay rather than guessing responder.
- [x] Reject accidental `questioner == answer_role` under current bounded cross-examination contract.
- [x] Bind providers by capability + role kind + execution-contract namespace + live probe + current health + runtime binding.
- [x] Enforce one executor per contract at current policy; deterministic provider priority/id tie-break for multiple healthy candidates.
- [x] Recheck provider health before child-job creation; stale RPB cannot execute.
- [x] Register shared capability/tool/provider/runtime source for `tribunal.role.execute` / `tribunal_role` / OpenCode launcher.
- [x] Observe real shared preflight state: production provider implemented but degraded/unavailable here because `opencode` executable is absent.
- [x] Add subprocess process-boundary Q1/A1/Q2/A2 E2E through existing Job/Attempt runtime.
- [x] Require live answer graph admission before DialecticObserver.
- [x] Add edge cases: wrong role, wrong provider, wrong role-kind, wrong contract namespace, zero healthy providers, multiple candidates, too many requested executors, stale provider, timeout, invalid JSON, hidden sibling evidence.
- [x] Add second DOMAIN role-family E2E proving role compatibility outranks higher METHOD-provider priority.
- [x] Add RPB/TEX/PER serialization round-trip + fingerprint checks.
- [x] Add L3 tests to repository-owned R4 acceptance runner.
- [x] Add future architecture/TD-046 for response ownership and Defender/Advocate arbitration.
- [x] Add future architecture/TD-047 for multidisciplinary ClaimReviewCase fork/join.
- [x] R4 targeted: 104/104 PASS.
- [x] Full Researcher: 581 total / 577 PASS / same four TD-015 failures.
- [x] Runtime compiler PASS, policy hash `8910fd61122b450212d5bc459cdb52acdc02aa3cf6d87a37c5eaa3778e3cdfef`.
- [x] Capability compiler PASS, policy hash `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`.
- [x] `compileall` PASS.
- [x] Write architecture, post-E2E implementation review and pipeline audit.
- [x] Feature commit `8b15c1384c5d73774e59be0a9258b1b11d7e1fb9` (`researcher: bind bounded tribunal dialogue providers`).
- [x] Milestone ZIP `RESEARCHER-R4.4-L3A-PROVIDER-BINDING-DIALOGUE-001.zip`, SHA256 `f1c3c831e3d6e34206d166fa77571512738acb8ab7ea2d4f10511d37bfeed221`.
- [ ] Run an actually available production semantic provider through the same RPB/TEX/PER path.
- [x] Execute conditional Advocate through shared live provider binding at process level (L3B structural); production semantic Advocate remains blocked with production provider.
- [ ] Calibrate interaction semantic observer on live traces (TD-042).
- [ ] TD-046/TD-047 remain future architecture; do not fold full response-ownership/fork-join into L3A.


## WS-49 RESEARCHER-R4.4-L3B-GROUNDED-DIALOGUE-LIVE-ADVOCATE

Date: 2026-09-13
Status: structural/process slice implemented; production semantic provider still environment-blocked.

- [x] Add typed response grounding kinds/states to `ArgumentArtifact`.
- [x] Distinguish disclosed evidence/target/prior argument/turn/derivation/assumption from `MODEL_PRIOR`.
- [x] Model-prior-only non-OPEN specialist answer creates blocking MISSING_EVIDENCE + typed research request.
- [x] Bump live answer envelope to `tribunal-answer-draft/1.1` grounding-aware schema while retaining structural 1.0 compatibility.
- [x] Add conditional Advocate provider binding via the same `RoleProviderBinding` authority (`DEFENSE`, ADC).
- [x] Add bounded Advocate TEX + Job/Attempt/PER execution.
- [x] Add live Advocate documented QUALIFY path: REPLIES_TO + DEFENDS.
- [x] Add live Advocate model-prior DEFEND hardening: deterministic REQUEST_EVIDENCE, no DEFENDS edge.
- [x] Add hidden sibling grounding rejection.
- [x] Add Advocate response admission to ArgumentGraph revision.
- [x] Add specialist model-prior vs documented-evidence grounding tests.
- [x] Add L3B tests to repository-owned R4 acceptance runner.
- [x] Document single-Claim multidisciplinary subbranch/join direction with conflict + synergy semantics (TD-047).
- [x] Freeze pre-production feature checkpoint `8204ce6bcbca56c42d6e4fb5ec458c2e1d71e99e` (`researcher: ground live tribunal dialogue and advocate`).
- [x] Create pre-production milestone ZIP `RESEARCHER-R4.4-L3B-PREPROD-GROUNDED-DIALOGUE-001.zip`, SHA256 `1ba3840813ccec2709288470c10852b4e9837a6b025ac157b0f2a9c35cf7bcf1`.
- [ ] Run an actually available production semantic provider through DQC/ADC using the same grounding-aware contracts.
- [ ] Calibrate hallucinated refs, false closure, model-prior honesty, Q2 novelty and Advocate rationalization on production traces (TD-042).

## WS-50 FUTURE-HYPOTHESIS-VERIFICATION-CYCLE-DESIGN

Date: 2026-09-13
Status: DESIGN CHECKPOINT / future-growth; no canonical runtime implementation yet.

- [x] Define `HypothesisCase` as historical research process rather than scalar Claim status.
- [x] Define append-only `HypothesisRevision` direction with parent/change-cause lineage.
- [x] Separate hypothesis statement/scope/assumptions/predictions/falsification conditions from current assessment.
- [x] Define `HypothesisVerificationPlan` around discriminating tests rather than support accumulation only.
- [x] Define future `HypothesisEvidenceLink` projection over canonical Evidence/Source objects.
- [x] Define source-bounded `EvidenceDigest` direction with explicit supports/does-not-support/scope/caveat semantics.
- [x] Preserve `MODEL_PRIOR -> HypothesisProposal` while forbidding `MODEL_PRIOR -> Evidence`.
- [x] Define competing-hypothesis peer semantics and non-discriminating evidence case.
- [x] Define evidence independence/dependency problem; source count must not equal independent confirmation count.
- [x] Link hypothesis verification iterations to existing ResearchChallenge/ResearchDOM/Job runtime rather than a second scheduler.
- [x] Link Writer as proposal-only semantic decomposition/round-trip/digest helper and Coder as typed computation delegate.
- [x] Keep one canonical Claim with multidisciplinary review subbranches under one `ClaimReviewCase` / future hypothesis linkage.
- [x] Define cross-facet conflict and synergy/prerequisite semantics for future join.
- [x] Specify 20-case virtual E2E suite before canonical hypothesis implementation.
- [x] Add TD-048 canonical HypothesisCase/revision/verification lifecycle.
- [x] Add TD-049 evidence independence/dependency groups.
- [x] Add TD-050 hypothesis-specific EvidenceDigest/support-limit-counter projection.
- [ ] Run virtual E2E corpus for TD-048/049/050 and refine contracts before implementation.
- [ ] Implement H1 HypothesisCase/HypothesisRevision only after virtual E2E stabilizes identity/revision semantics.
- [ ] Defer automatic multidisciplinary join until TD-047 dependencies/conflicts are explicit.
- [ ] Defer learned hypothesis ranking/calibration until historical outcomes exist.

Reference: `RESEARCHER_FUTURE_HYPOTHESIS_VERIFICATION_CYCLE.md`.

## WS-51 R4.4-L3B-PRODUCTION-SEMANTIC-TRACE-HANDOFF

Date: 2026-09-13
Status: DESIGNED / external execution gate open.

- [x] Document exact OpenCode CLI contract used by Harness (`opencode run --pure --model ... --dir ...`).
- [x] Record current sandbox platform: Linux x86_64 / glibc 2.41 / Node 22.16 / no Bun/Ollama/OpenCode.
- [x] Record current environment limitation: no external DNS/network, so cloud semantic execution cannot complete here even after adding only the OpenCode binary.
- [x] Define preferred portable Linux x86_64 OpenCode artifact for direct CLI/runtime verification.
- [x] Define two-build strategy when production is ARM64: production ARM64 artifact + same-version x86_64 artifact for sandbox execution.
- [x] Define sanitized model/provider configuration requirements; secrets never enter trace package.
- [x] Define remote production trace-pack workflow for cloud providers.
- [x] Define returned trace artifacts and minimum reproducibility metadata/hashes.
- [x] Define production semantic negative/edge cases, not only happy path.
- [ ] Receive OpenCode executable/distribution and version/build metadata.
- [ ] Verify `opencode --version` and exact `run --pure --model --dir` CLI compatibility.
- [ ] If cloud-only, generate first signed/hash-stable trace pack for execution on user production server.
- [ ] Admit returned production trace through unchanged RPB/TEX/PER/IQT/ARG path.
- [ ] Calibrate TD-042/044/046 using real specialist/Advocate traces.

Reference: `OPENCODE_PRODUCTION_SEMANTIC_TRACE_HANDOFF.md`.

## WS-52 R4.4-L3B-REMOTE-PRODUCTION-ACCEPTANCE-PACKAGE

Date: 2026-09-13
Status: IMPLEMENTED / local fake-OpenCode E2E verified; real user-host production run pending.

- [x] Inspect supplied OpenCode Windows installer and record FileVersion/ProductVersion `1.18.30`.
- [x] Record installer SHA256 `dcf723272c930f5dfa73a8561818ae4ad1a346384a859111ffeb554e19ce6567`.
- [x] Add remote acceptance environment collector with secret-presence-only reporting.
- [x] Add direct OpenCode JSON worker that uses isolated run directories and returns machine-clean provider JSON.
- [x] Add full remote acceptance runner for deterministic baseline + real semantic bounded chain + prior-only case.
- [x] Add exact generated Q1/Q2 to ANSWER TEX; bump execution envelope serialization to `tribunal-execution-envelope/1.1`.
- [x] Add machine-readable `output_contract` to Q/A/Advocate TEX and fingerprint it.
- [x] Move provider behavioural contract into shared `config/tribunal_role_provider_contract.md`.
- [x] Add regression tests for materialized-question visibility and embedded output contract.
- [x] Add operator protocol, OpenCode-agent instruction, report template and YAML test matrix.
- [x] Run fake OpenCode CLI through the same remote worker path: bounded Q1/A1/Q2/A2 + Advocate + prior-only all completed; dirty-repo guard was the only expected package-level failure during development.
- [ ] Run package on user production host with real OpenCode 1.18.30-compatible CLI/model.
- [ ] Return `production_001` trace archive plus three variability runs.
- [ ] Review real grounding honesty, Q2 novelty, Advocate rationalization, false closure and provider variability; feed findings to TD-042/044/046.
- [ ] Decide whether production trace is PASS / PASS_WITH_FINDINGS / FAIL_CONTRACT / FAIL_RUNTIME / FAIL_REGRESSION.

References:
- `REMOTE_ACCEPTANCE_README_FIRST.md`
- `REMOTE_OPENCODE_AGENT_INSTRUCTION.md`
- `REMOTE_OPENCODE_ACCEPTANCE_PROTOCOL.md`
- `REMOTE_OPENCODE_ACCEPTANCE_REPORT_TEMPLATE.md`
- `config/remote_acceptance/test_matrix.yaml`


## WS-53 FULL-HARNESS-WRITER-RESEARCHER-CODER-INTEGRATION-001

Date: 2026-09-13
Status: INTEGRATION / ACCEPTANCE / PACKAGING

- [x] Confirm one Git checkout contains canonical Writer, Researcher, Coder/code-factory, shared router/jobs/capsules/orchestration, configs, agents, skills and MCP/launcher periphery.
- [x] Add repository-owned Coder acceptance runner `scripts/run_coder_acceptance.py`.
- [x] Add Coder event-sourced E2E: worker -> reviewer -> tester -> auditor -> PASSED -> finalize + replay.
- [x] Add Coder provenance guard E2E for untrusted artifacts.
- [x] Add Coder repeated-review convergence/tribunal flag E2E.
- [x] Add Coder event-chain tamper detection E2E.
- [x] Fix code-factory implicit-CWD Git snapshot; require explicit `--workdir` / `OPENCODE_FACTORY_WORKDIR` (TD-051 DONE).
- [x] Add regression proving worker submit from Harness root cannot change repository HEAD.
- [x] Reconcile old TD-015: correct fallback Guard WEAK_RU/internal semantics and restore missing LocalCorpus fixture.
- [x] Full Researcher regression after TD-015 repair: 588/588 PASS.
- [x] Canonical Writer suite: 31 tests + 15 subtests PASS.
- [x] Canonical Coder suite: 5/5 PASS.
- [x] Add one-command `scripts/run_harness_acceptance.py` for Writer + Researcher + Coder + shared compiler/static gates.
- [x] Legacy/root compatibility sweep: 136/136 PASS in bounded groups; monolithic shell invocation is environment-timeout bound, not a test failure.
- [x] Shared runtime/capability compiler + compileall/JSON gates PASS; hashes recorded in full acceptance report.
- [x] Create `FULL_HARNESS_README_FIRST.md`, `FULL_HARNESS_INVENTORY.md`, `FULL_HARNESS_ACCEPTANCE_REPORT.md`; tracker/debt/decision records remain first-class release artifacts.
- [x] Feature commit `08cee15b664c94ce60f5daeb66a3920b4fa9cb9f` (`harness: integrate writer researcher coder acceptance`).
- [x] Code milestone `HARNESS-FULL-WRITER-RESEARCHER-CODER-001.zip`, SHA256 `3a33a41f21c6c0784493a697711b749ef19a5c968c3fa325eab0fc798b8b40ea`.
- [x] Superseded by WS-54 code-only portability hardening; final recovery/handoff must be generated from the post-TD-052 closure boundary.
- [ ] Production semantic OpenCode trace remains external acceptance, not a blocker for deterministic Harness packaging.


## WS-54 FULL-HARNESS-CODE-ONLY-ACCEPTANCE-PORTABILITY

Date: 2026-09-13
Status: DONE / release hardening.

- [x] Apply closure/governance patch to a fresh extraction of `HARNESS-FULL-WRITER-RESEARCHER-CODER-001.zip`.
- [x] Detect that Coder no-implicit-CWD regression incorrectly assumed the deployed Harness itself contained `.git`.
- [x] Replace the assumption with a disposable controller Git repository created inside the test.
- [x] Preserve the actual invariant: `factory_ctl submit worker` without explicit workspace cannot change process-CWD Git HEAD.
- [x] Verify Coder 5/5 PASS in canonical checkout.
- [x] Repackage integrated code milestone as `HARNESS-FULL-WRITER-RESEARCHER-CODER-002.zip` from feature commit `68582d3ef527826a4f35d53a362d627220afe9c6`; SHA256 `990aa3402e767e003fd990573e208257330f4c76be7642e0118947efca35b9b7`.
- [x] Record TD-052 DONE; deployment task tracker / agent upgrade patch are release-layer artifacts generated from the closure boundary.
- [ ] Execute production semantic OpenCode acceptance on the user host; remains an external gate.

## WS-55 OPENCODE-NATIVE-PLUGIN-BRIDGE-P1

Date: 2026-09-14
Status: IMPLEMENTED / HOSTLESS ACCEPTANCE PASS / LIVE OPENCODE INSTALLATION PENDING.

Objective: replace the legacy hook/CLI assumption with a maintainable OpenCode-native host adapter while preserving Writer/Researcher/Coder authority boundaries.

- [x] Re-check official OpenCode plugin/custom-tool/SDK guidance and exact v1.18.30 plugin types.
- [x] Declare `plugins/tool-skill-contract-router.ts` LEGACY / DEPRECATED; simultaneous native+legacy plugin loading is forbidden.
- [x] Add stable host DTOs: `HostContext/1.0`, `WorkspaceRef/1.0`, `SemanticExecutionRequest/1.0`, `SemanticExecutionResult/1.0`.
- [x] Add JSON schemas for the four host/semantic boundary contracts.
- [x] Add full-duplex `harness-bridge-rpc/1.0` over NDJSON stdio.
- [x] Prove reverse RPC while the parent request is still pending (`bridge.reverse_echo_test`).
- [x] Add native plugin package `packages/opencode-harness-plugin` with minimal tools only: `harness_status`, `harness_run`.
- [x] Use OpenCode custom-tool context only as normalized host metadata; no raw SDK objects cross into Harness Core.
- [x] Add OpenCode host probe using SDK `global.health()` and structured `client.app.log()` logging.
- [x] Add plugin-side `semantic.execute` adapter shape but keep production semantic execution disabled by default pending live certification.
- [x] Add project/global installer `scripts/install_opencode_native_plugin.py` using the official `.opencode/plugins/` / config plugin-directory mechanism.
- [x] Add standalone doctor `scripts/opencode_plugin_doctor.py`.
- [x] Add `config/host_integration_policy.json` (`harness-host-integration/2.0`).
- [x] Migrate `runtime_integration_policy.json`, setup scripts and health check so native-plugin mode no longer requires `OPENCODE_BIN` or `OPENCODE_SESSION_DB`.
- [x] Add exact v1.18.30 compatibility record with source-verified features and explicit `NOT_LIVE_CERTIFIED` semantic status.
- [x] Add `plugin` mode to integrated acceptance runner.
- [x] Hostless plugin tests: 9/9 Python PASS.
- [x] JS↔Python duplex bridge/fake-host tests: 3/3 PASS (including exact v1.18.30 flattened SDK call-shape fixture).
- [x] Plugin factory fake-host E2E: `harness_status` + code route through Python Core PASS.
- [x] Writer regression: 31/31 PASS.
- [x] Researcher regression: 588/588 PASS.
- [x] Coder regression: 5/5 PASS.
- [x] Runtime/capability compiler hashes unchanged (`8910fd...`, `60105d...`).
- [ ] Install generated native loader into a real OpenCode 1.18.30 project/global plugin directory.
- [ ] Confirm `harness_status` and `harness_run` are visible to a real OpenCode session.
- [ ] Capture live HostCapabilitySnapshot and certify v1.18.30 runtime behavior.
- [ ] Only after live P2 passes, enable a bounded read-only `semantic.execute` smoke.
- [ ] Only after semantic smoke passes, migrate Tribunal provider transport from CLI to plugin bridge.

References:
- `OPENCODE_NATIVE_PLUGIN_P1_ARCHITECTURE.md`
- `OPENCODE_NATIVE_PLUGIN_P1_RUNBOOK.md`
- `config/host_integration_policy.json`
- `compatibility/opencode/1.18.30.json`
