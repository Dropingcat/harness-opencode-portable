# Researcher R4.3 Pipeline Audit — Independent Role Execution

Date: 2026-09-13
Scope: R3.5 -> R4.1 -> R4.2 -> R4.3 first-pass role execution.

## 1. Audited pipeline

```text
canonical knowledge / RelationAssessment
-> UncertaintyProfile / ReviewWorkField
-> TribunalCompositionPlan / RoleBrief
-> role-specific EvidenceSlice
-> RoleInstructionPack
-> InquiryContract
-> child Job / Attempt
-> role worker draft
-> validated InquiryTurn + ArgumentArtifact
-> optional controlled PriorReview projection
-> [STOP]
```

Audit performed after executable single-role and multi-role E2E runs, targeted acceptance and full regression.

## 2. Authority ownership

R3.5 owns what remains uncertain and how it may be assessed.
R4.1 owns admitted role selection/assignment, capability/tool authority, evidence-view policy and budgets.
R4.2 owns concrete visibility projection.
R4.3 owns execution envelope and typed non-authoritative role output.

R4.3 does not own Claim truth, GraphEdge lifecycle, Gap/Conflict resolution, source/evidence admission, role admission or evidence widening.

**Result: PASS.**

## 3. Input-containment audit

The worker receives exactly:

- fingerprinted InquiryContract;
- bound role EvidenceSlice;
- fingerprinted semantic RoleInstructionPack.

The admission layer verifies cited evidence/targets and discovery/evidence-request refs against the visible slice and assigned needs. An invalid hidden-evidence citation is rejected in E2E.

**Result: PASS.**

## 4. Runtime-state audit

One role runs as one child Job with one first-pass Attempt in the existing `job_ctl` substrate. Parent/child/attempt/stage states reach COMPLETED on valid output. Validation failure produces child `FAILED_NO_OUTPUT` and FAILED Attempt/parent-child record.

No second Tribunal scheduler was added.

**Result: PASS L1.**

Caveat: adapter code currently uses low-level job_ctl state primitives because no consolidated child-attempt API exists.

## 5. Epistemic/runtime separation audit

Valid bounded scientific insufficiency is `ArgumentPosition.OPEN`.
Worker/provider/contract failure is runtime failure and does not create semantic OPEN.

This separation is tested.

**Result: PASS.**

## 6. Output-state mutation audit

E2E verifies Claim status and GraphEdge revision remain unchanged after valid and invalid role attempts. `ArgumentArtifact` contains no authority to mutate them.

**Result: PASS.**

## 7. Multi-role independence audit

The same composition plan executes at least two independently selected roles:

- `xrd_specialist` with METHOD_ONLY view;
- `crystallographer` with CLAIM_PLUS_SUPPORT view.

They have separate EvidenceSlice fingerprints, RoleInstruction fingerprints, child Jobs/Attempts and ArgumentArtifact IDs. First-pass outputs are not automatically injected into the other role's slice.

**Result: PASS.**

## 8. Handbook authority audit

Handbook loader rejects non-admitted roles and authority-bearing fields such as tools/capabilities/evidence-view/supported-axis policy. Semantic guidance compiles into a fingerprinted instruction pack.

Common stop conditions are now included in the instruction fingerprint.

**Result: PASS.**

## 9. Handbook-fill audit

When a selected admitted role lacks an entry or required semantic variant, code emits a deterministic `RoleHandbookFillRequest` containing assigned-need, axis, assessment-method, lineage and policy snapshot context. Skeleton generation is explicitly `PROPOSAL_ONLY` and contains no authority fields.

This does not admit new domain roles. TD-036 remains intact.

**Result: PASS / admission deliberately deferred.**

## 10. Variant/phase audit

Handbook variants can produce different semantic instruction packs. R4.3 L1 runtime nevertheless accepts only `FIRST_PASS` under `INDEPENDENT_FIRST_PASS` contracts.

Therefore challenger/cross-exam wording cannot silently change the current inquiry phase.

**Result: PASS L1.**

## 11. Downstream compatibility audit

`ArgumentArtifact` can be projected to R4.2 `PriorReviewArtifact`, but disclosure remains controlled by a later EvidenceViewPolicy. This gives future challenge/cross-examination a typed previous-position carrier without automatic broadcast.

Discoveries and additional evidence requests are typed and remain proposals; they can later feed ResearchChallenge/retrieval admission rather than searching implicitly.

**Result: PASS for boundary compatibility; execution deferred.**

## 12. Legacy Tribunal-stage audit

Legacy semantics are reconciled as staged behavior:

```text
independent assessment
-> challenge / conditional Advocate defense
-> cross-examination
-> Q1/A1/Q2(on A1)/A2
-> typed discovery extraction
-> reducer / ResearchChallenge feedback
```

R4.3 correctly stops after independent assessment. Vote-as-truth and aggregator override remain rejected.

**Result: PASS.**

## 13. Provider/capability audit

The structural adapter uses deterministic fixture workers. It has not yet proved live provider health, tool binding, model availability or actual token-budget enforcement.

**Result: OPEN TD-037, non-blocking for structural R4.3 L1 but blocking before claiming live role execution.**

## 14. Traceability audit

R4.3 artifact payloads carry contract/slice/instruction fingerprints, attempt ID and worker ID. This improves local observability but does not replace TD-038 universal lineage.

Required future trace should connect source/evidence revisions through relation assessment, RWF, composition, slice, inquiry contract, attempt, turn and argument under one queryable non-authoritative substrate.

**Result: PASS WITH EXPLICIT HIGH-PRIORITY DEBT TD-038.**

## 15. Acceptance/reproducibility audit

Repository-owned acceptance runner now bootstraps Researcher import paths:

- `r4`: 52/52 PASS;
- full: 529 total / 525 PASS / only four unchanged TD-015 failures;
- runtime compiler: PASS, unchanged hash;
- capability compiler: PASS, unchanged hash;
- compileall: PASS.

Post-documentation reproduction confirms these results and closes TD-040.

## 16. Audit verdict

**R4.3 L1: ACCEPTABLE TO FREEZE after final post-doc acceptance and recovery packaging.**

The branch proves the role execution boundary, not live scientific-agent quality. The next implementation should bind the same contract to a healthy authorized provider and extend multi-role first-pass execution under real runtime constraints before introducing adversarial dialogue.
