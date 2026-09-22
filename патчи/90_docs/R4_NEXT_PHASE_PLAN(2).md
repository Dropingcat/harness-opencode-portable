# R4 Next Phase Plan — updated after R4.1 implementation start

Date: 2026-09-13
Status: R4.1 DONE (L1). Next boundary: R4.2 executable evidence slicing.

## Boundary

```text
R3.5 ReviewWorkField
+ ResearchDOM lineage
+ object profile
+ Tribunal composition policy snapshot
        ↓
R4.1 TribunalCompositionPlan
```

R4.1 must not run Tribunal dialogue or mutate knowledge state.

## R4.1 work tracker

### A. Architecture / contracts
- [x] Define `TribunalRoleSpec`.
- [x] Define `TribunalCompositionRequest`.
- [x] Define `TribunalCompositionPlan`.
- [x] Define `AssessmentAssignment`.
- [x] Define `EvidenceViewPolicy`.
- [x] Define `RoleBriefContract`.
- [x] Define `TribunalLineageProfile` and ResearchDOM lineage compiler.
- [x] Define R4-local stable `AssessmentNeedRef` bridge.

### B. Policy / registry
- [x] Versioned closed role registry in `config/tribunal_composition.yaml`.
- [x] Permanent panel is policy-defined, not hardcoded in Python.
- [x] Axis→required-role rules.
- [x] AssessmentMethod→required-role rules.
- [x] Domain/method lineage tag activation.
- [x] Role synonym/equivalence deduplication.
- [x] Validate role capabilities/tools against central authorities.
- [ ] Domain role-pack loading/admission lifecycle (defer; TD-036).

### C. Composition algorithm
- [x] Deterministic composition.
- [x] Blocking need coverage or `UNASSIGNED_NEED`.
- [x] Numeric blocking need requires measurement specialist.
- [x] Conflict gets skeptical coverage.
- [x] XRD/crystallography lineage can activate domain expertise.
- [x] Stable policy hash and composition fingerprint.
- [x] Typed serialization.
- [ ] Stronger set-cover optimisation across many needs/roles (defer until actual role packs justify complexity).

### D. Evidence/tool contract
- [x] Evidence-view kinds defined.
- [x] Per-role view/capability/tool contract compiled.
- [x] Fresh-context cannot include previous conclusions.
- [ ] Execute evidence slice and prove no ref leakage (R4.2).
- [ ] Runtime provider-health binding (R4.2/TD-037).

### E. Acceptance
- [x] New R4.1 unit tests.
- [x] R3.5 + R4.1 targeted slice green.
- [x] Full Researcher regression: 499 total / 495 PASS / same four TD-015 failures.
- [x] runtime/capability compiler gates; hashes unchanged.
- [x] `compileall` + `git diff --check`.
- [x] R3.5→R4.1 scientific demo artifact.
- [x] implementation review + pipeline audit.
- [x] update current architecture state / tracker / tech debt + decision log.
- [x] Git commit boundary + milestone package + recovery bundle.

## Explicitly deferred after R4.1

1. R4.2 executable evidence slicing and leakage tests.
2. R4.3 typed inquiry contract / first-pass execution using existing Job/Attempt runtime.
3. R4.4 Q1/A1/Q2/A2 dialectic and typed discoveries feeding ResearchChallenge.
4. Later aggregation/calibration without majority truth.
5. Learned role ranking only after historical resolution data exists.

## Non-blocking legacy debt

TD-022/023/024/027/028/032/033/034 remain visible. Do not fold them into R4.1 unless an acceptance gate proves they block composition.
