# Researcher R4.2 — Executable Tribunal Evidence Slicing Architecture

Status: DONE (L1); executable/E2E validation, milestone package and recovery boundary complete.
Date: 2026-09-13
Owner: Researcher orchestrator.

## 1. Block identity

**Name/version:** `R4.2 Executable Tribunal Evidence Slicing / tribunal-evidence-bundle/1.0`.

**Implementation:**

- `scripts/researcher/researcher_core/tribunal_evidence.py`
- `tests/researcher/test_tribunal_evidence.py`
- `tests/researcher/test_r4_2_evidence_slicing_e2e.py`
- `scripts/researcher/demo_r4_2_evidence_slicing.py`

**Public contracts:**

- `TribunalEvidenceRequest`
- `TribunalEvidenceBundle`
- `TribunalEvidenceSlice`
- `EvidenceItemProjection`
- `SourceProjection`
- `TargetProjection`
- `PriorReviewArtifact` (temporary visibility envelope)
- `EvidenceSliceStatus`
- `EvidencePolarity`

R4.2 also exposes one R4-wide identity bridge from R4.1:

- `assessment_need_refs_for_work_field()`

All R4.x consumers must use that bridge until TD-035 is replaced by canonical AssessmentNeed identity.

## 2. Purpose

R4.1 determines **who** should assess each `AssessmentNeed` and issues an `EvidenceViewPolicy`. R4.2 makes that policy executable by compiling bounded, typed, role-specific evidence slices from canonical Researcher entities.

The block answers only:

> Which canonical targets/evidence/source projections may this admitted role see for this concrete assignment under this composition/policy?

It does not:

- run an LLM/judge;
- search for missing evidence;
- call tools/providers;
- widen a view because a role asks for more context;
- mutate Claim, GraphEdge, Gap, Conflict, RelationAssessment or uncertainty state;
- execute Advocate/discussion/Q&A;
- aggregate a verdict.

## 3. Boundary

```text
ReviewWorkField
+ TribunalCompositionPlan
+ canonical Claim/Quantity/Source/EvidenceSpan/GraphEdge state
+ optional non-authoritative prior-review artifacts
        ↓
TribunalEvidenceBundle
  └─ TribunalEvidenceSlice per role brief
```

The compiler consumes the `EvidenceViewPolicy` already frozen into the R4.1 plan. The work-plane role has no API for replacing the requested view kind or increasing `max_refs`.

Before slicing, R4.2 also calls `validate_tribunal_composition_plan_integrity()`. R4.1 composition fingerprints now cover assignments **and the authority-bearing role brief content**: evidence view, capabilities, tools, expected output contract, inquiry depth and token budget. A transferred/persisted plan whose brief was altered without recomputing the plan fails closed. This fingerprint is a deterministic integrity checksum, not a cryptographic signature or authentication boundary; provenance of the admitted policy/plan remains a traceability/control-plane concern (TD-038).

## 4. Authority model

R4.2 is authoritative only for **visibility projection under the current composition plan**.

The evidence compiler may:

- resolve canonical refs;
- follow admitted active semantic edges;
- classify evidence polarity from typed `GraphEdge.kind`;
- remove fields prohibited by view policy;
- bound/truncate output;
- mark a slice `READY`, `PARTIAL` or `BLOCKED`.

It may not:

- decide claim truth;
- infer a new semantic relation from textual co-occurrence;
- admit a missing source/evidence object;
- perform retrieval;
- change the RWF to fit available evidence;
- silently substitute unrelated evidence when the requested evidence is absent.

This preserves the existing chain:

```text
observation != admission != relation != relation assessment
!= uncertainty characterization != evidence view != Tribunal argument != truth
```

## 5. Canonical inputs

R4.2 currently projects these canonical namespaces:

- `CLM` Claim
- `QTY` Quantity
- `SRC` Source
- `EVD` EvidenceSpan
- `EDG` GraphEdge

The canonical state is run-checked. Cross-run entities are rejected rather than merged into a convenient but unreplayable evidence bundle.

### Control/lineage refs

The first real R4.2 E2E exposed an important boundary fact: R3.5 `AssessmentNeed.target_refs` can contain control refs such as `RAS-*` because relation-assessment source refs are folded into the need target tuple.

R4.2 therefore distinguishes:

```text
projectable semantic/evidence refs
!=
control/lineage refs
```

Refs such as `RAS/GAP/CNF/...` are retained as explicit `nonprojected_control_refs` metadata and are **not** treated as missing evidence simply because they are absent from the canonical claim/evidence registry projection.

This is a local compatibility rule, not the final identity architecture. TD-038 tracks a general cross-layer traceability substrate.

## 6. View semantics

### 6.1 `FULL_RELEVANT`

Includes bounded evidence explicitly named by the work field/needs and relevant evidence reached through active typed semantic relations. Provenance fields are included only if the policy permits them.

### 6.2 `CLAIM_PLUS_SUPPORT`

Includes evidence connected through typed active `SUPPORTS` relations and explicit need evidence. Evidence known only through `CONTRADICTS` is excluded from the support-specific projection.

### 6.3 `CLAIM_PLUS_COUNTEREVIDENCE`

Includes typed active `CONTRADICTS` evidence and explicit counter-relevant need evidence. Known support-only evidence is excluded from the counter-specific projection.

### 6.4 `FRESH_CONTEXT`

Implements the independent/blind first-pass idea recovered from legacy Tribunal behavior.

Under the current Skeptic policy:

- evidence text may be visible;
- prior conclusions are hidden;
- Source IDs/titles/locators are hidden;
- evidence source IDs/locators are hidden;
- SUPPORT/COUNTER polarity is projected as `UNLABELED`;
- SUPPORT/COUNTER selection reason codes are replaced with neutral `ASSIGNED_RELEVANCE`;
- GraphEdge target projections hide edge kind/endpoints; Source target projections hide source type/identity metadata.

Hiding a verdict while retaining `polarity=SUPPORT`, `selection_reason=SUPPORT_RELATION` or `edge_kind=SUPPORTS` would be independence theater, so all three structural leak paths are masked. This is **structural metadata blindness**, not semantic redaction of the evidence text itself; TD-039 tracks content-embedded provenance leakage.

### 6.5 `METHOD_ONLY`

L1 is deliberately conservative. It includes:

- evidence explicitly referenced by assigned AssessmentNeeds;
- evidence that is the source endpoint of an assigned target semantic relation.

It does **not** scan arbitrary corpus prose for words such as “XRD”, “method”, or “calibration”. The current canonical graph does not yet express a sufficiently rich typed relation “this evidence validates this method assumption”, so guessing from text would recreate the co-occurrence inference R3 deliberately removed.

## 7. Selection and ordering

Evidence is scoped to the role's **assigned AssessmentNeeds and their structurally related canonical relations**, not to the entire aggregate `ReviewWorkField.evidence_refs` pool. This prevents a FULL_RELEVANT or FRESH_CONTEXT role from silently receiving evidence belonging only to another branch/need.

Evidence selection is deterministic from:

- concrete `ReviewWorkField`;
- R4.1 role assignment/brief;
- canonical active relations;
- `EvidenceViewPolicy`;
- stable canonical IDs.

The compiler uses deterministic ordering before applying `max_refs`. If bounding removes otherwise eligible items, the slice records `truncated=true` and becomes `PARTIAL`.

No legacy “empty role slice -> give top-N trusted sources” fallback exists.

## 8. Fail-closed behavior

- composition plan for another RWF -> reject;
- canonical state contains another run -> reject;
- a canonical ref required by a blocking assignment is missing, or the compiled package has no visible payload -> `BLOCKED`;
- bounded/truncated view or missing refs on a non-blocking assignment -> `PARTIAL`;
- a blocking need may still receive `READY` when its target-only payload is executable; epistemic insufficiency is for the later reviewer to report, not for the slicer to prejudge;
- empty blocking view is not backfilled with arbitrary sources;
- view policy cannot be widened by role/request text;
- FRESH_CONTEXT prohibited provenance/conclusion fields are physically absent from the projection;
- slicing is read-only over canonical state.

`READY` means the requested visibility contract could be compiled from currently available canonical objects. It does **not** mean the claim is supported or the AssessmentNeed is resolved.

## 9. Legacy Tribunal reconciliation

R4.2 preserves the useful legacy behavior from `judge_brief.py` and late Tribunal design:

- asymmetric evidence by role;
- genuinely fresh Skeptic first pass;
- later controlled disclosure rather than one shared giant context;
- evidence-conditioned criticism instead of role labels alone.

It rejects the legacy mechanisms that no longer fit the current authority model:

- string/keyword source routing as authoritative selection;
- `trust` score fallback as an automatic substitute for missing task-specific evidence;
- role prompt deciding what it may see;
- one LLM sequentially seeing every role’s context;
- preliminary verdict leakage into independent first pass.

The wider legacy Tribunal sequence remains downstream:

```text
independent first pass
→ optional Advocate / FOR-vs-AGAINST stage
→ cross-examination
→ Q1 -> A1 -> Q2(on A1) -> A2
→ typed discoveries
→ existing ResearchChallenge/reducer loop
```

R4.2 implements only the evidence-control prerequisite.

## 10. E2E acceptance strategy

R4.2 was intentionally tested through the nearest real chain before writing its implementation review:

```text
GraphEdge
→ RelationAssessment
→ UncertaintyComponent
→ UncertaintyProfile
→ ReviewWorkField
→ ResearchDOM lineage
→ TribunalCompositionPlan
→ TribunalEvidenceBundle
```

This E2E found the mixed `AssessmentNeed.target_refs` / `RAS-*` seam that isolated unit review did not expose. The implementation was changed rather than weakening the test.

The E2E additionally proves that Claim status and GraphEdge revision are unchanged after slicing.

This E2E-first order is now recorded as R4-D015 for future capsules where technically possible.

## 11. Traceability seam

`AssessmentNeedRef` (TD-035) and the newly observed projectable-vs-control-ref distinction are symptoms of a broader requirement: cross-layer artifacts need a stable queryable derivation chain.

TD-038 therefore targets a non-authoritative traceability substrate, conceptually something like:

```text
TraceabilityLink / LineageEnvelope
  consumed ref + revision
  transformation/step
  Job/Attempt/ResearchCard
  policy/config hash
  produced refs + revisions
  alias/bridge mappings
```

It must answer “where did this artifact come from and what consumed it?” without becoming another truth registry or a mutable god-object.

R4.2 does not implement TD-038 opportunistically.

## 12. Current limitations

1. `AssessmentNeed` still lacks canonical entity identity; R4 uses the R4-wide bridge (TD-035).
2. Domain role packs remain static/deferred (TD-036).
3. Provider health/executable capability binding is not checked by slicing; the remaining TD-037 must be resolved before live inquiry can rely on a tool.
4. No universal traceability substrate yet (TD-038).
5. `METHOD_ONLY` is conservative because the canonical graph lacks rich method-applicability evidence relations.
6. `PriorReviewArtifact` is a temporary visibility envelope; R4.3 should replace it with canonical `ArgumentArtifact` / `InquiryTurn` contracts.
7. Current source projection has no general canonical source-quality/trust model. R4.2 intentionally does not reconstruct one from legacy heuristics.
8. Evidence polarity is limited to relations represented by the current edge vocabulary; absence of a support/counter edge is `UNLABELED`, not proof of neutrality.
9. Evidence slicing does not retrieve missing evidence. Missing inputs must remain visible or route back through Researcher capabilities later.
10. FRESH_CONTEXT structurally strips provenance/polarity metadata but does not redact author names, DOIs, journal names or other provenance that may already occur inside the exact evidence text (TD-039).
11. `max_refs` currently bounds evidence excerpts, not all target/source metadata projections; R4.3 token/context budgeting must treat the complete serialized slice.

## 13. Complexity ladder

- **L1 (current R4.2):** deterministic typed per-role slicing, asymmetric views, blind fresh-context projection, bounds/status/fingerprints, E2E proof.
- **L2:** richer typed evidence-purpose/method relations, traceability adapters, canonical prior-review artifacts, controlled staged reveal.
- **L3:** R4.3 inquiry contracts and independent worker execution over slices through existing Job/Attempt runtime; live provider-health binding.
- **L4:** R4.4 Advocate/FOR-vs-AGAINST and bounded Q1/A1/Q2/A2 cross-examination with typed discoveries and local challenge feedback.
- **L5:** historical calibration/utility ranking and adaptive recomposition, while policies/reducers retain authority.

## 14. Acceptance gates

Implemented/observed:

- 17 R4.2 unit + nearest-chain E2E tests PASS;
- R3.5 + R4.1 + R4.2 targeted integration: 40/40 PASS;
- full Researcher: 517 total / 513 PASS / same four TD-015 baseline failures;
- runtime compiler `--check`: PASS, unchanged policy hash;
- capability compiler `--check`: PASS, unchanged policy hash;
- `compileall`: PASS;
- `git diff --check`: PASS;
- executable BCC/XRD R4.2 demo generated successfully;
- no Claim/GraphEdge authoritative mutation in E2E.

Branch packaging/recovery is the remaining milestone-close operation.

## 15. Tech-debt links

- TD-035 canonical AssessmentNeed identity.
- TD-036 admitted/versioned domain Tribunal role packs.
- TD-037 live provider health and execution binding.
- TD-038 universal cross-layer traceability/lineage substrate.
