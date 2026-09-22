# Researcher R4.1 Pipeline Audit

Date: 2026-09-13
Scope: R3.5 → R4.1 composition boundary.

## 1. Pipeline under audit

```text
canonical Claim/Relation/Evidence state
→ R3.5 UncertaintyProfile
→ ReviewWorkField.assessment_needs
→ ResearchDOM lineage profile
→ Tribunal composition policy snapshot
→ deterministic TribunalCompositionPlan
→ [STOP R4.1]
```

## 2. Authority audit

### R3.5
Owns the characterization of unresolved work: axes, levels, blocking flag, methods and completion criteria.

### R4.1
Owns only deterministic composition under a policy snapshot.

### Not owned by R4.1

- Claim truth/status;
- GraphEdge lifecycle;
- Gap/Conflict resolution;
- evidence admission;
- role execution;
- dialogue;
- votes/verdicts;
- aggregation;
- scheduler/job lifecycle.

Result: **PASS**. No direct authority inversion found in the new module.

## 3. Input adequacy audit

RWF supplies the target/question/method/level/blocking information required for composition. ResearchDOM supplies structural direction/discipline/question/method context. Object profile is an explicit input, not inferred from arbitrary corpus prose.

One gap found and surfaced: AssessmentNeed has no canonical ID. R4-local content-addressed identity is used; TD-035 records the migration path.

Result: **PASS WITH EXPLICIT DEBT**.

## 4. Role taxonomy audit

Roles are closed and versioned. Unknown role references fail policy load. Synonyms can be grouped by equivalence group and deterministically deduplicated. LLM cannot create a new authoritative role.

Result: **PASS L1**.

Open scaling path: modular admitted domain role packs (TD-036).

## 5. Capability/tool audit

Every role-declared logical tool/capability is validated against the existing central authority files. R4 introduces no parallel capability registry.

Result: **PASS for registry identity**.

Provider health/runtime availability is not checked by composition and is correctly deferred to TD-037/R4.2.

## 6. Evidence-view audit

The contract supports FULL_RELEVANT, CLAIM_PLUS_SUPPORT, CLAIM_PLUS_COUNTEREVIDENCE, FRESH_CONTEXT and METHOD_ONLY. FRESH_CONTEXT structurally forbids previous conclusions.

The current policy also hides provenance from Skeptic first pass. This is deliberately recorded as experimental rather than smuggled in as architectural truth.

Actual evidence slicing/leakage proof is absent.

Result: **CONTRACT PASS / EXECUTION NOT YET IMPLEMENTED**.

## 7. Determinism / replay audit

Determinism inputs are:

- concrete RWF;
- normalized structural lineage tags;
- versioned policy;
- deterministic role ordering/equivalence priority.

Output records policy hash and composition fingerprint. Same input/policy test passes.

Result: **PASS**.

## 8. Minimal-sufficiency audit

R4.1 avoids free-form panel expansion and selects explicit required/domain roles only. Equivalence groups remove synonymous duplicates. It does not yet run a generic weighted set-cover optimizer across large overlapping role packs.

For the current small closed taxonomy this is acceptable; introducing optimisation before real overlap data would add algorithmic ceremony without evidence of value.

Result: **PASS L1, future extension documented**.

## 9. Legacy Tribunal audit

Useful legacy concepts preserved:

- adversarial perspective;
- method critique;
- asymmetric views;
- fresh/blind first pass;
- unresolved disagreement as research seed.

Legacy coupling rejected:

- prompt hardcodes panel;
- same LLM impersonates all roles;
- prompt selects evidence;
- majority voting decides truth;
- aggregator changes epistemic state.

Result: **PASS; semantic salvage without authority inheritance**.

## 10. Regression audit

Full Researcher suite after R4.1: **499 total, 495 PASS, 4 known TD-015 failures**. This exactly preserves the known Guard/LocalCorpus baseline failure count while adding the R4.1 tests.

Runtime/capability compiler hashes remain unchanged.

Result: **NO NEW REGRESSION CLASS**.

## 11. Exit criterion

R4.1 can be considered L1 complete when:

- docs/tracker/debt reflect final state;
- static gates are rerun after final edits;
- commit/package/recovery boundary is created.

Next boundary is R4.2 executable evidence slicing. Live Tribunal dialogue remains out of scope.


## Post-R4.2 audit addendum — plan integrity

Executable evidence slicing exposed that a downstream consumer must be able to detect a composition plan whose materialized role brief was altered after compilation. The current R4.1 plan fingerprint and validator now cover evidence view, capabilities/tools, expected output contract and inquiry budgets in addition to assignments. R4.2 validates this before slicing. This closes an authority-integrity gap discovered only when the next layer became executable.
