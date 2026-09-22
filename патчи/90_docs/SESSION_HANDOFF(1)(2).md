# SESSION HANDOFF — Writer/Researcher/Coder Harness

Date: 2026-09-13

## 1. Current state

The current Researcher boundary is R3.5 L1, commit:

`fe57c88312755d01e91a1ff1357481f577b71945`
`researcher: model multidimensional uncertainty before tribunal`

Working tree was clean when this handoff was built.

R3 is considered base-complete for transition into R4. It contains:

- R1/R1.1 ResearchMap + ResearchDOM + planning dialectic + planning gate + persistence/replay/trace.
- R2/R2.1/R2.2 KnowledgeGraph reconciliation, Gap/Conflict feedback, challenge decomposition and resolution lifecycle.
- R2.3/R2.3.1/R2.3.3 selective invalidation, provenance-triggered reopen and versioned relation lifecycle.
- R3-L1 TASK execution + local capability execution + peer child-job delegation contracts.
- R3.1 typed execution-output admission into canonical knowledge registry.
- R3.2 explicit semantic linking, no co-occurrence inference.
- R3.3 relation assessment separated from relation kind and lifecycle.
- R3.4 strict assessed-relation reasoning + relation feedback into Gap/ResearchChallenge + canonical edge update.
- R3.5 multidimensional uncertainty field and pre-Tribunal ReviewWorkField.

Writer v1 remains frozen/stable and is a peer orchestrator, not a Researcher submodule. Coder is likewise a peer orchestrator. Shared Job/Attempt runtime is reused for delegation.

## 2. R3.5 result

R3.5 deliberately rejects a scalar confidence score. It models orthogonal uncertainty axes with operational levels and explicit assessment methods.

Current axes include:

- NUMERIC_MEASUREMENT
- EVIDENCE_SUFFICIENCY
- SOURCE_PROVENANCE
- SCOPE
- METHOD
- CONFLICT
- DERIVATION
- ASSUMPTION
- CAUSALITY
- EXTRAPOLATION
- FRESHNESS

Operational levels:

- RESOLVED
- QUALIFIED
- MATERIAL
- BLOCKING
- UNCHARACTERIZED

Core contracts:

- `UncertaintyComponent`
- `UncertaintyProfile/1.0` (`UPR-*`)
- `AssessmentNeed`
- `ReviewWorkField/1.0` (`RWF-*`)

R3.5 answers **what is uncertain, why, how it can be assessed and what blocks reasoning**. It does not select specialists. Specialist/panel composition is the R4 boundary.

## 3. What goes into R4

R4 receives:

`ReviewWorkField + ResearchDOM lineage dimensions + canonical target/evidence objects`

Relevant ResearchDOM dimensions include:

- ResearchDirection
- DisciplinaryView
- QuestionType
- MethodView
- Claim/relation profile

R4 should produce deterministic permanent + dynamic Tribunal composition, role-specific briefs, evidence slices and inquiry contracts.

R4 must not mutate truth directly. Tribunal participants emit typed arguments/questions/challenges; reducers/admission policies remain authoritative.

## 4. Core design invariants

1. LLM proposes/argues; code decides authoritative transitions.
2. Work plane and control plane are separated.
3. Observation != admission != semantic relation != relation assessment != claim truth.
4. ResearchDOM is historical/execution structure; KnowledgeGraph is semantic knowledge; provenance/trace joins them.
5. Challenge branches are historical and iterative, never destructively replaced.
6. Relation itself is a first-class versioned information object.
7. Uncertainty is multidimensional; absent axis is not silently RESOLVED.
8. Specialized agents stay specialized. No god-agent.
9. Peer delegation reuses existing Job child runtime; do not create a second scheduler.
10. New architecture blocks must be documented with purpose, authority boundary, contracts, limitations, fail-closed behavior, tests, debt and complexity ladder.

## 5. Known open debt that remains relevant

High/important items to keep visible:

- TD-015: four known Guard/LocalCorpus baseline failures.
- TD-017: `evidence.verify` provider-priority conflict.
- TD-020: SQLite ResourceWarnings.
- TD-021: Writer SourceCatalog free-string IDs vs Researcher canonical `SRC-*` identity.
- TD-022: no dedicated relation history/state index for large graphs.
- TD-023: restore/recovery needs a single automated verifier; `.git` loss recurred twice.
- TD-024: live Coder/Writer transport/outbox not implemented yet.
- TD-026: legacy LocalDocumentExtractionCapsule source/hash vocabulary mismatch.
- TD-027: AdmissionIdentityMap currently coupled to accepted-ID ordering.
- TD-028: cross-admission semantic linking authorization not implemented.
- TD-032: DERIVED_FROM and richer QUANTIFIES validators incomplete.
- TD-033: automatic uncertainty adapters incomplete for provenance/freshness/causality/assumption/extrapolation; Gap taxonomy still partly string-family based.
- TD-034: numeric uncertainty is projection-only; canonical Quantity/Measurement uncertainty model is still missing.

Do not opportunistically fix unrelated debt inside R4 unless it blocks an acceptance gate.

## 6. Latest validation status

From R3.5 implementation review:

- R3.5 new tests: 11/11 PASS.
- Targeted uncertainty/R3 integration slice: 88/88 PASS.
- Full Researcher: 488 total, 484 PASS, same four TD-015 Guard/LocalCorpus failures.
- Runtime policy compiler: PASS, hash unchanged.
- Capability compiler: PASS, hash unchanged.
- compileall: PASS.
- git diff --check: PASS.

## 7. Immediate next action

Start R4 by writing the architecture document before implementation. First slice should be deterministic Tribunal composition only. Do not yet implement full Tribunal dialogue.

Recommended R4 first boundary:

`ReviewWorkField.assessment_needs + ResearchDOM dimensions + Claim/Relation profile -> TribunalCompositionPlan`

The plan should select:

- permanent panel roles;
- dynamic roles;
- role rationale/reason codes;
- assigned AssessmentNeed IDs;
- allowed tools/capabilities;
- evidence-view policy (including asymmetric views);
- expected typed output contract;
- budget/depth constraints.

Composition must be deterministic from policy and typed fields. The LLM may not invent arbitrary authoritative roles.

## 8. Files to read first

- `CURRENT_ARCHITECTURE_STATE_2026-09-12.md`
- `IMPLEMENTATION_TRACKER.md`
- `TECH_DEBT.md`
- `RESEARCHER_R3_5_UNCERTAINTY_FIELD_ARCHITECTURE.md`
- `RESEARCHER_R3_5_IMPLEMENTATION_REVIEW.md`
- `RESEARCHER_R3_5_TRIBUNAL_INPUT_AUDIT.md`
- `LEGACY_RESEARCHER_RECONCILIATION_2026-09-12.md`
- `ARCHITECTURE_BLOCK_DOCUMENTATION_STANDARD.md`
- `R4_NEXT_PHASE_PLAN.md`
