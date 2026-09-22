# R4 Next Phase Plan — after R4.4 L2a branching argument graph + conditional Advocate

Date: 2026-09-13
Status: structural branching/defense contracts implemented; generic disclosure and live bounded dialogue remain follow-on.

## Completed chain

```text
R3.5 ReviewWorkField
-> R4.1 TribunalCompositionPlan
-> R4.2 role-specific EvidenceSlice
-> R4.3 RoleInstructionPack + InquiryContract
-> independent child Job / Attempt
-> InquiryTurn + ArgumentArtifact
-> R4.4 L1 DialecticObservation / ControlDecision
-> R4.4 L2a ArgumentRelation + ArgumentGraphProjection
-> conditional Advocate activation
-> branch-local DialecticDisclosureContract
-> AdvocateDefenseContract
-> Advocate ArgumentArtifact + REPLIES_TO / optional DEFENDS
-> existing DialecticObserver
-> cross-exam | local research | control return | OPEN
```

## R4.4 L2a completed boundary

- [x] `ArgumentRelation/1.0` (`ARL-*`) is first-class and versioned.
- [x] `ATTACKS / UNDERCUTS / REPLIES_TO / DEFENDS` relation vocabulary.
- [x] `ArgumentGraphProjection/1.0` (`AGP-*`) with graph revision/fingerprint.
- [x] branch roots/heads reconstructed deterministically.
- [x] relation endpoint/run/AssessmentNeed validation.
- [x] attack/undercut source-position validation.
- [x] graph cycle rejection.
- [x] Advocate admitted in policy but excluded from ordinary composition.
- [x] handbook `advocate/defense` variant.
- [x] material branch-specific Advocate activation.
- [x] branch-local `DialecticDisclosureContract/1.0` (`DDC-*`).
- [x] `AdvocateDefenseContract/1.0` (`ADC-*`).
- [x] outcomes `DEFEND / QUALIFY / CONCEDE_LOCAL_POINT / REQUEST_EVIDENCE / OPEN`.
- [x] explicit downstream action from Advocate response.
- [x] sibling attack branch remains hidden from Advocate.
- [x] `REQUEST_EVIDENCE -> DialecticObserver -> Gap -> ResearchChallenge` E2E.
- [x] `DEFEND -> REPLIES_TO + DEFENDS` graph E2E.
- [x] TD-044 expanded with future Writer claim/facet decomposition + RTT reuse path.

## Important boundary

This does **not** close full R4.4 L2.

TD-043 remains open because current DDC compilation is defense-specific. A generic challenger/questioner/cross-exam disclosure compiler must exist before live multi-role dialogue can claim one coherent disclosure model.

TD-037 also remains open. Fixture/deterministic semantic artifacts prove contract topology, not production model quality or provider health.

## Next hard boundary — R4.4 L2b generic disclosure + question targeting

Minimum goals:

1. Extract a generic `DialecticDisclosurePolicy/Compiler` from the Advocate-specific path.
2. Support purposes at least `CHALLENGE`, `DIRECT_QUESTION`, `QUESTION_ON_ANSWER`, `DEFENSE`.
3. Bind each disclosure to one argument-graph branch/issue surface and explicitly list hidden sibling branches.
4. Add `DialecticQuestionContract` with:
   - questioner role;
   - target Argument/Turn/Issue refs;
   - exact disclosed prior artifacts;
   - expected closure surface;
   - allowed evidence/target refs;
   - max response/follow-up budget;
   - policy/handbook fingerprints.
5. Ensure Q2 can target only a typed new surface admitted from A1; no free prompt-level branch jumping.
6. Add replay/integrity validation for DDC + question contracts.
7. Add branching E2E where two attacks exist, only one enters Q/A, and the sibling remains untouched.
8. Resume a returned ResearchChallenge result into the exact unresolved branch/issue lineage rather than a new conversation.
9. Keep no-majority/no-truth-mutation invariants.
10. Add branch-scoped dialectic history/replay (TD-045) so independent graph heads do not share progress counters or issue lifecycle.
11. Only after these structural tests pass, run post-E2E review.

## R4.4 L3 — live bounded dialogue / provider binding

After L2b contracts stabilize:

1. close or materially narrow TD-037 using shared provider-health/capability runtime;
2. execute live challenger/questioner/answerer/Advocate roles through existing Job/Attempt lifecycle;
3. run one real `challenge -> Q1 -> A1 -> Q2(on A1) -> A2` branch;
4. run a second role-family variation;
5. distinguish timeout/provider failure/budget exhaustion from semantic OPEN/no-progress;
6. calibrate interaction-only observer proposals (TD-042);
7. verify returned research can continue the same argument branch;
8. post-E2E review/audit only after the live chain runs.

## Advocate policy questions still open

- Which challenge kinds require independent defense versus direct question only?
- Should causal/method disputes have lower activation thresholds than evidence/provenance disputes?
- When can one defended argument receive a second independent Advocate/defense branch?
- Can a non-Advocate specialist create a `DEFENDS` edge after cross-exam? Current graph model permits it; activation policy is Advocate-specific.
- When does `CONCEDE_LOCAL_POINT` resolve a dialectic issue versus merely qualify the attacked argument?
- When does a defense expose enough new surface to justify Q2 rather than another challenger?
- How is Advocate effectiveness later calibrated without rewarding unconditional SUPPORT?

These stay explicit policy questions, not prompt defaults.

## TD-044 / Writer semantic reuse path

Future issue identity work should investigate reuse of Writer semantic decomposition:

```text
EmergentIssue + bounded local context
-> Writer-style claim/proposition splitting
-> small local graph + ClaimFacetProposal[]
-> semantic round-trip check
-> equivalence candidates
-> Researcher scope/provenance validation
-> explicit admission
```

Writer proposals never directly merge issue signatures or change dialogue progress.

## Role model growth path

`ROLE_CARD_PORTABLE_DOM_FUTURE.md` remains the future exchange direction:

```text
RoleReference
+ RoleCard
+ RoleVariantCard
+ RoleParameterGraph
+ RoleEvaluationSnapshot
-> PortableRoleDOM YAML
```

Portable semantics never carry local runtime authority. Domain role packs remain TD-036.

## Explicitly deferred

- TD-036 admitted modular domain role packs;
- TD-037 live provider binding until L2b contracts stabilize;
- TD-038 universal traceability substrate except where exact branch replay exposes a blocker;
- TD-039 semantic provenance anonymization;
- TD-041 PortableRoleDOM implementation;
- TD-042 live interaction-observer calibration;
- TD-044 semantic issue facet/equivalence implementation;
- TD-045 branch-scoped dialectic history/replay;
- learned role ranking/effectiveness;
- majority/quorum truth;
- human expert insertion until automated disclosure/inquiry contracts are stable.
