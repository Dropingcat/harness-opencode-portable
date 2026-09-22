# Researcher R3.5 Pre-Tribunal Input Audit

Status: L1 implemented, pipeline audit pending final regression numbers.

## Question

What should reach Tribunal after the R3 base is complete?

## Answer

Not a prose summary and not a scalar confidence score. The boundary object is `ReviewWorkField/1.0` backed by canonical refs and one or more `UncertaintyProfile/1.0` objects.

The field describes the **object of expert work**:

- which canonical target is under review;
- which uncertainty axes are unresolved;
- whether each is qualified/material/blocking/uncharacterized;
- why the uncertainty exists (reason codes + source refs);
- what evaluation methods are appropriate;
- what completion criteria dispose of the uncertainty;
- which Gaps/Conflicts/RelationAssessments already exist;
- which evidence/source/relation refs are already available.

It deliberately does not choose `Critic`, `Skeptic`, `Crystallographer`, `XRD specialist`, etc. That mapping belongs to R4 `TribunalCompositionPolicy`.

## Expected R4 consumption

```text
ReviewWorkField
+ ResearchDOM lineage dimensions
+ canonical target/evidence objects
        ↓
R4 deterministic composition policy
        ↓
per-role briefs / asymmetric evidence slices / inquiry contracts
```

This creates a clean distinction:

- **R3**: prepare what is uncertain and what must be assessed.
- **R4**: decide who should assess each need and how to compose the panel.

## Key non-goals

- no aggregate probability of truth;
- no majority vote;
- no specialist selection in R3;
- no automatic ClaimStatus mutation from uncertainty profile;
- no assumption that an absent axis is resolved.
