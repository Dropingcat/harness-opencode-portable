# Researcher R4.3 Implementation Review — Independent Tribunal Role Execution

Date: 2026-09-13
Status: DONE (L1 implementation); reviewed after executable E2E, final packaging pending.

## 1. Scope actually implemented

R4.3 proves the first executable Tribunal role boundary rather than starting with a whole-panel dialogue:

```text
R3.5 ReviewWorkField
-> R4.1 TribunalCompositionPlan / RoleBrief
-> R4.2 TribunalEvidenceSlice
-> R4.3 InquiryContract
-> existing child Job / Attempt
-> bounded role worker
-> InquiryTurn + ArgumentArtifact
```

New implementation:

- `scripts/researcher/researcher_core/tribunal_inquiry.py`;
- `scripts/researcher/researcher_core/tribunal_role_runtime.py`;
- `scripts/researcher/researcher_core/tribunal_role_handbook.py`;
- `config/tribunal_role_handbook.yaml`;
- `scripts/run_researcher_acceptance.py`;
- `tests/researcher/test_tribunal_inquiry.py`;
- `tests/researcher/test_tribunal_role_handbook.py`;
- `tests/researcher/test_r4_3_role_execution_e2e.py`;
- `tests/researcher/test_r4_3_multi_role_first_pass_e2e.py`.

The composition policy output contract is now `ArgumentArtifact/1.0` for admitted roles.

## 2. Canonical role output boundary

R4.3 introduces:

- `InquiryContract/1.0` (`IQC-*`);
- `InquiryTurn/1.0` (`IQT-*`);
- `ArgumentArtifact/1.0` (`ARG-*`);
- typed `InquiryDiscovery`;
- typed `AdditionalEvidenceRequest`.

`ArgumentArtifact` is explicitly non-authoritative. It may support later reducers/inquiry, but it does not mutate Claim status, GraphEdge lifecycle, Gap/Conflict state or ReviewWorkField resolution.

The contract fingerprint binds role, assigned needs, composition fingerprint, EvidenceSlice fingerprint, allowed capabilities/tools, output contract, inquiry budget and semantic role-instruction fingerprint.

## 3. First vertical E2E result

The strongest test is a real adjacent-layer chain rather than `worker(input) -> output` in isolation:

```text
GraphEdge
-> RelationAssessment
-> UncertaintyProfile
-> ReviewWorkField
-> TribunalCompositionPlan
-> TribunalEvidenceBundle
-> xrd_specialist EvidenceSlice
-> RoleInstructionPack
-> InquiryContract
-> child Job / Attempt
-> deterministic XRD role worker
-> InquiryTurn + ArgumentArtifact
-> controlled PriorReviewArtifact projection
```

Observed output is a `QUALIFY` argument with a typed `METHOD_LIMITATION` and typed request for stress-sensitive XRD or independent composition/phase evidence. The worker sees only its bounded slice and semantic instruction.

The same E2E also runs an invalid worker that attempts to cite a hidden `EVD-*`. Admission rejects the draft; the child Job becomes `FAILED_NO_OUTPUT`, while the epistemic state is not converted into `OPEN`.

Claim remains OPEN and GraphEdge revision remains unchanged in both paths.

## 4. Multi-role variation E2E

A second executable test validates role variation before dialogue:

```text
one RWF / one composition plan
├─ xrd_specialist -> METHOD_ONLY slice -> xrd first-pass instruction -> child Job -> ARG
└─ crystallographer -> CLAIM_PLUS_SUPPORT slice -> crystallography first-pass instruction -> child Job -> ARG
```

The two roles have distinct EvidenceSlice fingerprints and distinct RoleInstruction fingerprints. They execute as separate child Jobs/Attempts and produce distinct ArgumentArtifacts. Neither role automatically receives the other's first-pass argument.

This proves that role variation is not merely a role-name switch inside one generic prompt.

## 5. Role Handbook design and observed behavior

The Role Handbook is deliberately semantic-only.

It may define:

- mission;
- mandatory checks;
- forbidden reasoning moves;
- first-pass stop conditions;
- expected discovery classes;
- phase-specific semantic variants (`first_pass`, `challenger`, `cross_exam`, later `defense`);
- question lenses.

It may not define:

- role admission;
- allowed tools/capabilities;
- EvidenceView;
- supported axes/method authority;
- permanent-panel status.

Those remain composition/control-plane concerns.

Common stop semantics such as valid `OPEN` and typed request for more evidence are now part of `RoleInstructionPack` and its fingerprint rather than prose-only handbook decoration.

## 6. Code-generated handbook fill workflow

R4.3 implements a conservative fill algorithm:

```text
selected admitted role
+ assigned AssessmentNeeds
+ methods/axes
+ ResearchDOM lineage
+ expected output contract
+ policy version/hash
        ↓
missing handbook entry/variant?
        ↓ yes
RoleHandbookFillRequest (RHR-*)
        ↓
PROPOSAL_ONLY YAML-ready skeleton
```

The skeleton deliberately omits tools, capabilities and evidence visibility. It cannot admit a role or widen authority. A later maintainer/admission workflow can review and merge semantic guidance.

This solves "code says what handbook guidance it needs" without turning runtime execution into self-modifying policy. Domain role packs remain TD-036.

## 7. Role variants and current execution gate

Variants are semantic modes of an admitted role, not separate authorities.

The handbook currently contains examples of:

- independent `first_pass`;
- `challenger`;
- `cross_exam`;
- vocabulary slot for future `defense`.

R4.3 L1 runtime accepts only `first_pass` under `InquiryPhase.INDEPENDENT_FIRST_PASS`. Supplying challenger/cross-exam semantics to this runtime fails closed. Later Q/A/cross-examination phases need explicit phase/parent-turn contracts rather than reusing the first-pass stage with a different prompt.

## 8. Existing Job/Attempt integration

`JobCtlTribunalRoleAdapter` reuses the existing runtime rather than introducing another scheduler:

1. parent receives a required child record;
2. child Job is created with one `first_pass` stage;
3. one Attempt is started with external task id = InquiryContract id;
4. worker receives InquiryContract + EvidenceSlice + RoleInstructionPack;
5. output is validated and written as typed artifact;
6. Attempt/stage/child/parent terminal states are updated.

A small amount of attempt/stage state mutation is currently performed through `job_ctl` primitives because the old runtime lacks a single reusable programmatic child-attempt helper. This is a non-blocking extraction opportunity if more adapters appear; it is not justification for a second scheduler.

## 9. Legacy Tribunal reconciliation

Library/legacy review remains consistent with the implemented direction:

```text
independent first pass
-> typed attack/challenge
-> conditional Advocate / defense
-> Q1 -> A1 -> Q2(on A1) -> A2
-> typed discoveries
-> existing ResearchChallenge/reducer loop
```

R4.3 implements only the independent-first-pass execution substrate and semantic variant vocabulary. It intentionally does not run Advocate, cross-examination or majority aggregation.

## 10. E2E-first defects / useful findings

The branch produced several concrete findings before review:

1. role execution needed an explicit separation between semantic `OPEN` and runtime `FAILED_NO_OUTPUT`;
2. role semantic guidance needed a separate handbook rather than being mixed into authority policy;
3. YAML role questions containing `?` exposed a real parsing defect and were corrected before acceptance;
4. handbook stop conditions existed in config but were initially not compiled into the runtime instruction contract; they are now fingerprinted;
5. semantic variants existed, but without a runtime gate a later cross-exam instruction could have been used under first-pass execution. R4.3 now explicitly requires `first_pass`;
6. repository tests depended on remembered `PYTHONPATH`; the repository-owned acceptance runner closes TD-040.

These are precisely the kinds of boundary errors that a document-only review would have been poor at finding.

## 11. Validation

### R4 targeted

`python scripts/run_researcher_acceptance.py r4`

**52/52 PASS**.

This covers R3.5 uncertainty, R4.1 composition, R4.2 slicing, handbook, inquiry contracts, single-role vertical E2E and multi-role first-pass E2E.

### Full Researcher

**529 total / 525 PASS / 4 unchanged TD-015 failures.**

Known failures remain:

- 2 Guard baseline expectations;
- 2 LocalCorpus fixture/index expectations.

No R4.3 regression class appeared.

### Compiler/static gates

- runtime compiler: PASS, hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`;
- capability compiler: PASS, hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`;
- `compileall`: PASS.

Post-documentation reproduction completed: R4 targeted remains 52/52 PASS; full Researcher remains 529 total / 525 PASS with only the four known TD-015 failures; compiler/static gates and `git diff --check` PASS.

## 12. Weak points not hidden by green structural tests

1. Fixture workers prove architecture, not quality of production scientific reasoning. Live provider/tool binding and health remain TD-037.
2. Cross-layer lineage is still local fingerprints/IDs, not the universal traceability substrate required by TD-038.
3. Domain role-pack admission remains deliberately deferred under TD-036.
4. Handbook fill produces a proposal skeleton but does not implement an approval/version-merge workflow. This is intentional until role-pack/admission authority is designed.
5. No canonical persistence repository exists yet for InquiryTurn/ArgumentArtifact beyond execution artifacts. Traceability/persistence design should avoid another side registry.
6. `InquiryPhase` currently has only independent first pass. Challenger/cross-exam handbook variants are intentionally non-executable until typed dialogue contracts exist.
7. The JobCtl adapter touches low-level attempt/stage fields through existing primitives. A shared programmatic child-attempt helper would reduce future adapter drift.
8. Token budget is carried as authority metadata but fixture execution does not exercise actual model-token accounting.
9. Role effectiveness/calibration/history ranking is not implemented and should not be inferred from test success.

## 13. Review verdict

**R4.3 L1 is acceptable to freeze. Feature re-run and milestone package are complete; final recovery/handoff is the remaining closure step.**

It closes the first real executable role path and establishes a safe semantic handbook/fill mechanism without weakening the R4.1/R4.2 authority boundaries.

The next engineering boundary should be a **live authorized role binding / multi-role first-pass execution layer** before enabling Advocate or Q1/A1/Q2/A2 dialogue. Once a live role can execute under the same bounded contract and provider-health rules, the project can move to typed adversarial/cross-examination stages without hiding provider/runtime uncertainty inside Tribunal semantics.

## 14. Feature milestone boundary

Feature commit: `b435c943d524f430c349bf390ce7b70f7c8968c5` (`researcher: execute independent r4 tribunal roles`).

Milestone package: `RESEARCHER-R4.3-INDEPENDENT-ROLE-001.zip`.
SHA256: `3a4f87332d1ecf909321a6f426d8780c867aa394fe1716d4eaadf4b78f442cfb`.
ZIP integrity: PASS.

The complete recovery bundle is intentionally created after the final metadata boundary commit so that recovery HEAD includes these package/hash records.
