# R4 Next Phase Plan — after R4.4 L3A provider binding + executable bounded dialogue

Date: 2026-09-13
Status: provider/runtime contracts and process-level bounded Q/A are implemented; production semantic execution is next.

## Completed through L3A

```text
R3.5 ReviewWorkField
-> R4.1 TribunalCompositionPlan
-> R4.2 EvidenceSlice
-> R4.3 RoleInstructionPack + independent InquiryContract
-> R4.4 L1 DialecticObserver / bounded control
-> R4.4 L2a ArgumentGraph + conditional Advocate
-> R4.4 L2b generic DDC + DQC + branch history/replay
-> R4.4 L3A DQC/1.1(questioner + answer role)
-> RoleProviderBinding (RPB)
-> TribunalExecutionEnvelope (TEX)
-> child Job / Attempt
-> ProviderExecutionReceipt (PER)
-> IQT / ARG
-> ArgumentGraph admission
-> observer/control
```

## L3A acceptance complete

- [x] explicit addressed answer role; no inference from target ARG author;
- [x] current bounded dialogue rejects questioner=self-answerer;
- [x] shared provider/capability/runtime authority, no Tribunal provider registry;
- [x] provider compatibility by capability + role kind + contract namespace + health + runtime binding;
- [x] zero provider / wrong provider / multiple providers / executor overflow tests;
- [x] stale provider recheck before child Job;
- [x] bounded JSON-safe TEX;
- [x] durable PER on success/failure/timeout/rejection;
- [x] hidden sibling output rejected;
- [x] live answer must be admitted to ArgumentGraph before observation;
- [x] Q1/A1/Q2/A2 process-boundary E2E;
- [x] second DOMAIN-role family E2E;
- [x] RPB/TEX/PER round-trip integrity tests;
- [x] R4 104/104 PASS;
- [x] full Researcher 581 total / 577 PASS / only TD-015 baseline failures;
- [x] runtime/capability compiler + compileall gates PASS.

## Next hard boundary — R4.4 L3B production semantic dialogue + live conditional Advocate

### A. Production semantic provider

1. Run current shared preflight in an environment where one authorized semantic provider is truly `available`.
2. Bind DQC questioner and answerer through RPB.
3. Execute one real Q1/A1 branch using TEX only.
4. Persist PER + IQT/ARG and prove graph admission/observer continuity.
5. Continue Q2 only when A1 yields an admitted new issue surface.
6. Compare runtime/provider failure semantics with process fixture results.

Current environment blocker: `existing.opencode_tribunal_role` is implemented but unavailable (`missing:opencode`).

### B. Live conditional Advocate

After one production Q/A vertical passes:

1. material ATTACKS/UNDERCUTS branch activates Advocate by existing policy;
2. compile branch-local DDC/ADC;
3. bind Advocate provider through the same shared RPB/TEX/PER path;
4. validate `DEFEND / QUALIFY / CONCEDE_LOCAL_POINT / REQUEST_EVIDENCE / OPEN`;
5. verify `REPLIES_TO` vs `DEFENDS` topology;
6. verify no hidden sibling/evidence widening;
7. observe whether defense creates a valid new Q2 surface or should stop/return to Researcher.

## Architecture debt intentionally not folded into L3B

### TD-046 response ownership / Defender-Advocate arbitration

`answer_role_id` solves one question. Future policy must model who owns a Claim facet/position and which response function is required. Prefer typed `ResponseAssignment` over a permanent Defender persona until live traces justify otherwise.

### TD-047 multidisciplinary Claim fork/join

A single Claim may need crystallography + causality/kinetics + measurement/statistics review. Future `ClaimReviewCase` should fork into independent typed facets/branches and rejoin by coverage/dependency/conflict state, not majority vote. See `RESEARCHER_R4_4_FUTURE_RESPONSE_OWNERSHIP_MULTIDISCIPLINARY_REVIEW.md`.

## Other open debt

- TD-036 domain role-pack admission;
- TD-038 universal cross-layer traceability/index;
- TD-039 semantic blind-provenance projection;
- TD-041 PortableRoleDOM;
- TD-042 live observer calibration;
- TD-044 semantic issue facet/equivalence + Writer proposal bridge.

## Stop rule

Do not implement full multidisciplinary join, learned responder selection or human expert insertion before production semantic Q/A + live Advocate use the existing bounded contracts successfully. Those features need real traces, not architecture fan fiction.
