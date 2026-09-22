# R4 Next Phase Plan — R4.3 typed inquiry and independent first pass

Date: 2026-09-13
Status: R4.2 DONE (L1). Next hard boundary: R4.3 typed inquiry contracts + independent first-pass execution.

## Boundary

```text
R3.5 ReviewWorkField
+ R4.1 TribunalCompositionPlan
+ canonical Claim/Quantity/Source/EvidenceSpan/GraphEdge state
+ optional prior-review context
        ↓
R4.2 TribunalEvidenceBundle
  per-role TribunalEvidenceSlice[]
```

R4.2 controls **what each selected role can see**. It does not run a judge, search for new evidence, call tools, mutate Claim/GraphEdge/Gap/uncertainty state or aggregate a verdict.

## R4.2 tracker

### A. Typed contracts
- [x] `TribunalEvidenceRequest`.
- [x] `TribunalEvidenceBundle`.
- [x] `TribunalEvidenceSlice`.
- [x] `EvidenceItemProjection` with bounded provenance fields.
- [x] `SourceProjection` and non-authoritative `TargetProjection`.
- [x] temporary `PriorReviewArtifact` envelope for visibility testing until canonical Inquiry/Argument contracts exist.
- [x] deterministic serialization/fingerprints.

### B. View compiler
- [x] `FULL_RELEVANT`: bounded RWF/direct-relation evidence with provenance according to policy.
- [x] `CLAIM_PLUS_SUPPORT`: typed SUPPORTS evidence; known counterevidence excluded.
- [x] `CLAIM_PLUS_COUNTEREVIDENCE`: typed CONTRADICTS evidence; known support excluded.
- [x] `FRESH_CONTEXT`: provenance, previous conclusions, support/counter polarity, selection reasons and GraphEdge/Source target semantics are structurally hidden when policy forbids them.
- [x] `METHOD_ONLY`: explicit need refs + evidence that is source of an assigned target relation; no keyword inference over corpus prose.
- [x] deterministic `max_refs` truncation with visible PARTIAL status.
- [x] no role/prompt-owned view widening API.

### C. Fail-closed / missing-input behavior
- [x] plan/RWF mismatch rejected.
- [x] cross-run canonical state rejected.
- [x] missing canonical refs on a blocking assignment become `BLOCKED`; no legacy top-3/trust fallback. Target-only executable work may remain `READY`.
- [x] missing/truncated non-empty view is `PARTIAL`.
- [x] unknown control-plane refs such as `RAS/GAP/CNF` are not misclassified as missing registry evidence; they remain explicit nonprojected control refs pending richer adapters/traceability.
- [x] slicing is read-only over canonical state.

### D. E2E-first acceptance
- [x] unit/contract tests for asymmetry, leakage, max refs, missing evidence, determinism and authority boundaries.
- [x] real nearest-chain E2E: `RelationAssessment -> UncertaintyProfile -> ReviewWorkField -> TribunalCompositionPlan -> TribunalEvidenceBundle`.
- [x] E2E found and repaired R3.5 mixed target/control-ref seam instead of papering over it in review.
- [x] scientific BCC/XRD demo artifact generated from the same chain.
- [x] run R3.5 + R4.1 + R4.2 targeted regression after documentation freeze (40/40 PASS).
- [x] run full Researcher + compiler/static gates (517 total / 513 PASS / same four TD-015; compiler hashes unchanged; compileall/diff PASS).
- [x] implementation review/pipeline audit after executable tests and post-green code audit.
- [x] feature Git commit + milestone package created (`RESEARCHER-R4.2-EVIDENCE-SLICING-001.zip`, SHA256 `dab5a998af72c6b479b88ae0360eb760511327fc3d7b70536e6e9adf23610a88`); recovery/handoff finalized immediately after boundary commit.

## Legacy Tribunal reconciliation retained for R4.3/R4.4

Legacy evolved through several functions that must not be collapsed:

```text
independent/skeptical first assessment
→ optional Advocate / FOR-vs-AGAINST defense when triggered
→ cross-examination / discussion
→ Q1 -> A1 -> Q2(on A1) -> A2 (bounded depth, typically 2–4)
→ typed discoveries (Gap/Conflict/MissingEvidence/etc.)
→ existing ResearchChallenge/reducer loop
```

Earlier majority-vote/Aggregator truth semantics remain rejected. Aggregation may later mean coverage/round completion/calibration, never `3/5 -> Claim=true`.

## Next hard boundary after R4.2

### R4.3 — typed inquiry contract + independent first-pass execution

Planned minimum:
- canonical `InquiryContract` / `InquiryTurn` / `ArgumentArtifact` boundaries;
- execute independent first pass using existing Job/Attempt child runtime;
- consume only R4.2 EvidenceSlice, never raw whole corpus;
- typed request for additional evidence instead of view self-widening;
- runtime capability/provider-health binding (remaining TD-037);
- no Advocate yet unless a typed attack/challenge exists and policy explicitly activates defense.

### R4.4 — dialectical loop
- FOR/AGAINST/Advocate semantics as typed contracts, not persona folklore;
- `Q1 -> A1 -> Q2(on A1) -> A2`, repeat only under bounded depth/novelty policy;
- cross-role disclosure schedule;
- extract Gap/Conflict/Scope/Method/Causality/Numeric discoveries;
- feed unresolved discoveries into existing ResearchChallenge loop;
- adaptive recomposition is historical/versioned, not silent panel drift.

## Explicitly deferred / tech debt

- TD-036 admitted/versioned domain role packs.
- TD-037 live provider health/binding.
- TD-038 general cross-layer traceability/lineage substrate.
- TD-033/034 richer uncertainty adapters/canonical measurement uncertainty.
- TD-022 relation history index; TD-024 live peer transport; TD-027/028 identity/linking improvements.
