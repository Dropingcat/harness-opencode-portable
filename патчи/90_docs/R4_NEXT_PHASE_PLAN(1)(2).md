# R4 NEXT PHASE PLAN — Deterministic Tribunal Composition

Status: PLANNED
Start boundary: R3.5 complete, ReviewWorkField available.

## Objective

R4 must answer **who should assess each unresolved need and under which contract**. It must not redefine the uncertainty model and must not directly decide Claim truth.

Input:

```text
ReviewWorkField
+ ResearchDOM lineage dimensions
+ canonical Claim/Relation/Evidence refs
+ policy snapshot
```

Output target:

```text
TribunalCompositionPlan
  permanent_roles[]
  dynamic_roles[]
  assignments[]
  evidence_view_policy
  role_briefs/contracts
  allowed_capabilities/tools
  inquiry_depth/budget
  reason_codes
  policy_version/hash
```

## R4.1 proposed first slice: composition contracts and policy

Implement typed contracts before any live Tribunal dialogue:

- `TribunalRoleSpec`
- `TribunalCompositionRequest`
- `TribunalCompositionPlan`
- `AssessmentAssignment`
- `EvidenceViewPolicy`
- `RoleBriefContract`

Permanent panel should be policy-defined, likely preserving the legacy conceptual core:

- Critic
- Skeptic
- Methodologist
- Evidence Auditor

Exact permanent set is a policy decision and should be versioned, not baked into prompts.

Dynamic role selection should derive from:

- AssessmentNeed.axis/methods/level/blocking
- ResearchDirection
- DisciplinaryView
- QuestionType
- MethodView
- Claim/Relation profile

Examples of dynamic role families:

- physicist of metals
- crystallographer
- XRD specialist
- TEM specialist
- statistician/numerical analyst
- causal critic
- measurement specialist

## Deterministic composition rules

- Role taxonomy is closed/versioned in L1.
- LLM may propose missing expertise as a typed requirement, but may not materialize an authoritative new role without policy admission.
- Every selected role must have reason codes tied to input dimensions or AssessmentNeeds.
- Every blocking AssessmentNeed must be assigned to at least one capable role or fail closed as `UNASSIGNED_NEED`.
- Avoid duplicate synonymous roles unless policy explicitly requests independent perspectives.
- Composition should prefer minimal sufficient panel, not maximal headcount.

## Evidence-view policy

Preserve useful legacy behavior: asymmetric evidence views can encourage genuinely independent challenges rather than five agents paraphrasing the same summary.

L1 should support at least:

- FULL_RELEVANT
- CLAIM_PLUS_SUPPORT
- CLAIM_PLUS_COUNTEREVIDENCE
- FRESH_CONTEXT
- METHOD_ONLY

The evidence-view compiler, not the role prompt, decides which refs are visible.

## Output contract boundary

R4 composition chooses roles and assignments only. It does not yet run the Tribunal.

Later R4.x/R5 dialogue agents should emit typed artifacts such as:

- `Argument`
- `InquiryQuestion`
- `Challenge`
- `Qualification`
- `MissingEvidence`
- `PossibleCounterexample`
- `MethodLimitation`

Reducers/admission layers decide what changes authoritative state.

## Tests for R4.1

At minimum:

1. Same RWF + same policy -> identical composition.
2. Blocking numeric uncertainty selects measurement/numeric capability, not generic prose role only.
3. XRD METHOD uncertainty + crystallography lineage selects relevant dynamic expertise.
4. CONFLICT need includes skeptical/adversarial coverage.
5. All blocking needs assigned or fail closed.
6. Unsupported role request rejected.
7. Duplicate synonyms deduplicated deterministically.
8. Fresh-context evidence slice does not leak disallowed evidence refs.
9. Policy hash/version recorded.
10. No Claim/GraphEdge/Gap mutation occurs during composition.

## Later R4/R5 development ladder

L1: deterministic panel composition and role briefs.
L2: capability/tool assignment and asymmetric evidence slicing.
L3: claim-specific inquiry contracts and permanent/dynamic panel evolution between rounds.
L4: Q1/A1/Q2/A2 dialectical loops with typed discoveries feeding ResearchChallenge.
L5: aggregation/quorum/calibration using historical effectiveness, without giving LLM outputs direct authority.

## Non-blocking R3 improvements to retain

Do not lose the following while moving into R4:

- TD-032 richer DERIVED_FROM/QUANTIFIES validators.
- TD-033 richer automatic uncertainty-axis adapters.
- TD-034 canonical measurement uncertainty model.
- TD-022 relation history index.
- TD-027/028 identity and cross-admission linking.
- TD-024 live peer transport.

These remain valid expansion paths, but should not be mixed into R4.1 unless an acceptance test requires them.
