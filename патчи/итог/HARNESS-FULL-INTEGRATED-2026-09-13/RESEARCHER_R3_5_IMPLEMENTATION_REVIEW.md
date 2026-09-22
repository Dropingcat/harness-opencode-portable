# Researcher R3.5 Multidimensional Uncertainty Field — Implementation Review

Date: 2026-09-13  
Status: DONE (L1)

## Scope

R3.5 prepares a typed pre-Tribunal work field. It does not select Tribunal roles and does not mutate Claim truth. The implementation intentionally avoids a scalar confidence score.

## Implemented

- `UncertaintyComponent` with axis, operational level, origin, blocking flag, reason codes, source refs, assessment methods and completion checks.
- `UncertaintyProfile/1.0` (`UPR-*`) with target/revision, readiness and dominant axes.
- `AssessmentNeed` as normalized review work unit.
- `ReviewWorkField/1.0` (`RWF-*`) as the R4 input boundary.
- L1 axes: numeric measurement, evidence sufficiency, source provenance, scope, method, conflict, derivation, assumption, causality, extrapolation, freshness.
- Operational levels: `RESOLVED`, `QUALIFIED`, `MATERIAL`, `BLOCKING`, `UNCHARACTERIZED`.
- Assessment methods include interval overlap, cross-source comparison, provenance, scope, method, evidence quality, conflict, derivation, assumption, causality, extrapolation, freshness, specialist review and experimental retest.
- RelationAssessment now retains normalized proposal signals in metadata for downstream uncertainty projection.
- Deterministic adapters from RelationAssessment, Gap, Conflict and explicit numeric uncertainty observations.
- Numeric path reuses existing Decimal interval-overlap semantics; no universal percentage thresholds were introduced.
- `UncertaintyFieldRepository` persists UPR/RWF through existing SQLite/UoW.
- Service artifact exposes `uncertainty_profiles` and `review_work_fields` separately.

## What reaches R4

A durable `ReviewWorkField` containing targets, unresolved axes, levels, blocking semantics, questions, allowed assessment methods, completion criteria, canonical refs, open gaps/conflicts and relation assessments. Specialist names are intentionally absent.

The demo work field contains six assessment needs:

1. METHOD / QUALIFIED
2. EVIDENCE_SUFFICIENCY / QUALIFIED
3. EVIDENCE_SUFFICIENCY / BLOCKING
4. METHOD / BLOCKING
5. CONFLICT / BLOCKING
6. NUMERIC_MEASUREMENT / BLOCKING

Overall readiness: `BLOCKED`.

## Pipeline behavior

R3.5 is a projection/control artifact, not a truth reducer:

```text
canonical state
→ uncertainty projection
→ review work field
→ R4 composition
```

It does not:

- set `ClaimStatus`;
- alter `GraphEdge.state`;
- resolve Gap/Conflict;
- choose permanent/dynamic specialists;
- infer an aggregate probability of truth.

## Tests

- New R3.5 tests: 11/11 PASS.
- Targeted uncertainty/R3 integration slice: 88/88 PASS.
- Full Researcher: 488 total, 484 PASS; same four TD-015 Guard/LocalCorpus baseline failures only.
- TD-020 SQLite ResourceWarnings remain.
- Runtime policy compiler: PASS, hash unchanged.
- Capability compiler: PASS, hash unchanged.
- `compileall`: PASS.
- `git diff --check`: PASS.

## New debt

- TD-033: incomplete automatic adapters for source provenance/freshness/causality/assumption/extrapolation and typed Gap taxonomy.
- TD-034: numeric uncertainty is not canonical Quantity state.

## R4 boundary

R4 should map:

```text
ReviewWorkField.assessment_needs
+ ResearchDOM Direction/Discipline/QuestionType/MethodView
+ Claim/Relation profile
→ permanent + dynamic Tribunal roles
```

R3 says what must be assessed. R4 says who should assess it.
