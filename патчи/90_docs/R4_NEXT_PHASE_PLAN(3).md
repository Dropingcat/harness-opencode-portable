# R4 Next Phase Plan — after R4.3 independent role execution

Date: 2026-09-13
Status: R4.3 L1 DONE; feature/milestone package complete, recovery/handoff boundary finalizing.

## Completed boundary

```text
R3.5 ReviewWorkField
-> R4.1 TribunalCompositionPlan
-> R4.2 TribunalEvidenceSlice
-> R4.3 RoleInstructionPack + InquiryContract
-> existing child Job / Attempt
-> bounded independent role worker
-> InquiryTurn + ArgumentArtifact
```

R4.3 now proves both one deep vertical role path and two-role independent first-pass variation. It also introduces a semantic-only Role Handbook and deterministic handbook-fill requests for missing admitted-role guidance.

## R4.3 completion checklist

- [x] typed InquiryContract/InquiryTurn/ArgumentArtifact;
- [x] exact plan/slice/need/instruction fingerprint binding;
- [x] existing Job/Attempt child execution;
- [x] out-of-slice citation rejection;
- [x] semantic OPEN != runtime failure;
- [x] XRD vertical E2E from RelationAssessment through role output;
- [x] downstream controlled prior-review projection;
- [x] semantic Role Handbook separated from authority policy;
- [x] common stop conditions fingerprinted into RoleInstructionPack;
- [x] first-pass/challenger/cross-exam semantic variants;
- [x] R4.3 L1 runtime rejects non-first-pass variants;
- [x] deterministic code-generated RoleHandbookFillRequest + proposal-only skeleton;
- [x] multi-role independent first pass with distinct slices/instructions/artifacts;
- [x] repository-owned Researcher acceptance runner, TD-040 closed;
- [x] R4 targeted 52/52 PASS;
- [x] full Researcher 529 total / 525 PASS / same four TD-015 failures;
- [x] compiler/static gates PASS before documentation freeze;
- [x] post-E2E implementation review and pipeline audit;
- [x] final post-doc acceptance: R4 52/52 PASS; full 529 total / 525 PASS / same four TD-015; compiler/static gates and diff PASS.
- [x] feature Git commit `b435c943d524f430c349bf390ce7b70f7c8968c5` + milestone package `RESEARCHER-R4.3-INDEPENDENT-ROLE-001.zip` SHA256 `3a4f87332d1ecf909321a6f426d8780c867aa394fe1716d4eaadf4b78f442cfb`.
- [x] final boundary metadata committed; complete recovery/handoff is regenerated from the resulting canonical HEAD.

## Next hard boundary — R4.3.1 live role binding + production first-pass envelope

Before starting adversarial dialogue, bind the existing structural contract to one real authorized semantic provider path.

Minimum goals:

1. Resolve role-required logical capabilities/tools through the existing shared runtime binding/health state, not a Tribunal-specific provider registry.
2. Fail closed or explicitly recompose/escalate when a required provider is unavailable (TD-037).
3. Execute at least one real role under the exact R4.2 slice + RoleInstructionPack + InquiryContract envelope.
4. Preserve the same output admission: only typed ArgumentArtifact/InquiryTurn; no direct state mutation.
5. Exercise actual budget/timeout/error behavior and keep runtime failure distinct from epistemic OPEN.
6. Execute at least two role families where feasible and confirm no implicit cross-disclosure.
7. Persist enough attempt/provider lineage for later TD-038 integration without inventing a second provenance registry.
8. Keep domain role packs TD-036; live binding must work for current admitted core roles first.

## Handbook evolution during R4.3.1

The handbook may evolve from observed code requests, but only through an explicit request/review/admission lifecycle:

```text
composition selects admitted role
-> code detects missing semantic entry/variant
-> RoleHandbookFillRequest
-> deterministic proposal skeleton
-> semantic completion/review
-> versioned handbook update
-> loader validation + tests
```

Do not auto-merge generated skeletons and do not allow handbook updates to grant tools/capabilities/evidence visibility.

## Following boundary — R4.4 typed adversarial/dialectical inquiry

Only after production first-pass execution is stable:

```text
independent ARG(s)
-> policy trigger selects challenge / FOR-AGAINST / Advocate defense
-> Q1 -> A1 -> Q2(on A1) -> A2
-> novelty/depth/budget stop policy
-> typed MissingEvidence/Method/Scope/Causality/etc. discoveries
-> existing ResearchChallenge / retrieval / reducer path
```

Required R4.4 properties:

- parent-turn links are historical/versioned;
- cross-role disclosure is compiled, not prompt-selected;
- Advocate is conditional, not a permanent truth-defender;
- no majority-vote truth;
- `OPEN` remains legitimate;
- panel recomposition is explicit and historical;
- new research requests go through existing planner/Job runtime.

## Explicitly deferred

- TD-036 domain role packs;
- TD-038 universal cross-layer traceability implementation, unless a live-binding acceptance gate makes a minimal substrate blocking;
- TD-039 semantic anonymization of provenance-bearing evidence text;
- learned role ranking/effectiveness;
- aggregation/quorum as truth;
- human-expert insertion until automated inquiry contracts are stable.
