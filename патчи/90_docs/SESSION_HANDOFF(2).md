# SESSION HANDOFF — Writer/Researcher/Coder Harness

Date: 2026-09-13

## 1. Current boundary

R4.3 Independent Tribunal Role Execution is DONE (L1). Canonical HEAD: `898f72b4342261f84b8781e4cda98ab30a5baf20` (`researcher: close r4.3 handoff boundary`). Working tree is clean at handoff construction.

R4.3 feature commit:

`b435c943d524f430c349bf390ce7b70f7c8968c5`
`researcher: execute independent r4 tribunal roles`

Milestone package:

`packages/RESEARCHER-R4.3-INDEPENDENT-ROLE-001.zip`
SHA256 `3a4f87332d1ecf909321a6f426d8780c867aa394fe1716d4eaadf4b78f442cfb`

## 2. What R4.3 now proves

The executable structural chain is:

```text
GraphEdge / RelationAssessment
-> R3.5 UncertaintyProfile + ReviewWorkField
-> R4.1 TribunalCompositionPlan / RoleBrief
-> R4.2 role-specific EvidenceSlice
-> R4.3 RoleInstructionPack + InquiryContract
-> existing child Job / Attempt
-> bounded semantic role worker
-> InquiryTurn + ArgumentArtifact
-> controlled PriorReview projection for later rounds
```

A role cannot cite hidden evidence/targets or widen assigned needs. Invalid output becomes runtime `FAILED_NO_OUTPUT`; valid scientific insufficiency is semantic `ArgumentPosition.OPEN`. Neither path mutates Claim/GraphEdge state.

## 3. E2E results

### Deep XRD vertical

A real nearest-chain E2E runs from RelationAssessment through uncertainty/composition/evidence slicing into `xrd_specialist`, then through a child Job/Attempt and back into typed `InquiryTurn/ArgumentArtifact`.

The deterministic XRD fixture returns QUALIFY + METHOD_LIMITATION + a typed additional-evidence request. This is a structural fixture, not a claim that a production scientific LLM has been validated.

A negative path attempts to cite hidden EVD and is rejected fail-closed.

### Multi-role variation

The same plan independently executes:

- `xrd_specialist` with METHOD_ONLY view;
- `crystallographer` with CLAIM_PLUS_SUPPORT view.

They receive different slice and instruction fingerprints, run as separate child Jobs/Attempts and produce distinct arguments. First-pass arguments are not automatically disclosed across roles.

## 4. Role Handbook

`config/tribunal_role_handbook.yaml` is semantic, not authoritative.

It may contain:

- mission;
- mandatory checks;
- forbidden reasoning moves;
- stop conditions;
- discovery focus;
- semantic variants `first_pass/challenger/cross_exam` and later `defense`;
- question lenses.

It may not grant role admission, tools/capabilities, EvidenceView or supported-axis/method authority.

R4.3 L1 runtime executes only `first_pass`. Challenger/cross-exam instructions under an independent-first-pass contract are rejected.

## 5. Handbook fill algorithm

When code selects an admitted role but the required handbook entry/variant is missing:

```text
RoleBrief + AssessmentNeeds + methods/axes + lineage + policy snapshot
-> RoleHandbookFillRequest (RHR-*)
-> deterministic PROPOSAL_ONLY skeleton
-> later semantic review/versioned handbook update
```

The generated skeleton has no tools/capabilities/evidence visibility and therefore cannot self-admit expertise. Domain role-pack admission stays TD-036.

## 6. Tribunal legacy/stage reconciliation

Retain:

```text
independent first pass
-> challenge / conditional Advocate defense
-> Q1 -> A1 -> Q2(on A1) -> A2
-> typed discoveries
-> existing ResearchChallenge / reducer path
```

Do not restore majority-vote truth, Aggregator override, one LLM impersonating the panel or prompt-owned evidence widening.

## 7. Validation baseline

Post-documentation reproduction:

- R4 targeted: 52/52 PASS;
- full Researcher: 529 total / 525 PASS / same four TD-015 failures;
- runtime compiler PASS, hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`;
- capability compiler PASS, hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`;
- compileall PASS;
- git diff --check PASS.

Repository-owned command: `python scripts/run_researcher_acceptance.py r4|full|gates|all`.

## 8. Open debt most relevant next

- TD-036 domain Tribunal role packs remain deferred.
- TD-037 live authorized provider/capability health binding remains open and is the next execution boundary.
- TD-038 general cross-layer traceability remains high priority. R4.3 now adds Slice -> IQC -> Job/Attempt -> IQT -> ARG lineage that the future substrate must absorb.
- TD-039 exact evidence text can still reveal semantic provenance in blind views.
- TD-040 is DONE via the repository-owned acceptance runner.

## 9. Immediate next action

Start R4.3.1 with one live authorized role provider, not with full Tribunal dialogue:

```text
RoleBrief authority
+ EvidenceSlice
+ RoleInstructionPack
+ InquiryContract
+ shared provider binding/health
        ↓
real first-pass execution
        ↓
validated InquiryTurn + ArgumentArtifact
```

Then repeat with at least one second role family if available. Only after the live first-pass envelope is stable should R4.4 implement Advocate/challenge and `Q1/A1/Q2/A2`.

## 10. Recovery boundary

- bundle: `recovery/HARNESS-R4.3-COMPLETE-2026-09-13.bundle`;
- SHA256: `32485a7706442b712a274c4f0d212d9bd922fcc8004e24d3ac8924a11a4b1e3a`;
- `git bundle verify`: PASS; complete history recorded.
