# Researcher R3.5 Multidimensional Uncertainty Field Architecture

Status: IMPLEMENTED / EXERCISED (L1)  
Boundary: final R3 preparation layer before R4 Tribunal composition.

## 1. Purpose

R3.4 closes the execution/admission/relation feedback loop, but uncertainty remains distributed across numeric adapters, relation assessments, Gaps and Conflicts. R3.5 normalizes those unresolved conditions into a typed multidimensional field without collapsing them into one confidence number.

R3.5 answers two questions:

1. **What is uncertain, at what operational level, and why?**
2. **What must be assessed to dispose of that uncertainty?**

R3.5 deliberately does **not** answer who should perform the assessment. Specialist/panel composition belongs to R4.

```text
canonical knowledge objects
  ├─ RelationAssessment
  ├─ Gap
  ├─ Conflict
  └─ numeric uncertainty observation
        ↓
UncertaintyComponent[]
        ↓
UncertaintyProfile (UPR)
        ↓
ReviewWorkField (RWF)
        ↓
R4 TribunalCompositionPolicy
```

## 2. Why there is no scalar confidence

A single confidence value mixes different failure modes and obscures remediation. A scope mismatch, weak evidence, unknown method compatibility and an unresolved numeric interval are not interchangeable quantities.

R3.5 therefore keeps uncertainty as orthogonal axes. Aggregation is limited to operational readiness (`CLEAR`, `QUALIFIED`, `NEEDS_REVIEW`, `BLOCKED`) and dominant axes. It does not claim a probabilistic posterior.

## 3. Uncertainty axes

L1 vocabulary:

- `NUMERIC_MEASUREMENT`
- `EVIDENCE_SUFFICIENCY`
- `SOURCE_PROVENANCE`
- `SCOPE`
- `METHOD`
- `CONFLICT`
- `DERIVATION`
- `ASSUMPTION`
- `CAUSALITY`
- `EXTRAPOLATION`
- `FRESHNESS`

Not every axis is automatically populated at L1. Empty axes are not silently treated as resolved.

## 4. Operational levels

- `RESOLVED`: no current uncertainty requiring work on this axis.
- `QUALIFIED`: usable with an explicit limitation.
- `MATERIAL`: can change interpretation and needs assessment, but does not automatically block all reasoning.
- `BLOCKING`: prevents the intended inference/decision until disposed.
- `UNCHARACTERIZED`: insufficient information exists even to characterize the uncertainty correctly.

`UNCHARACTERIZED` is not a numeric severity above/below `BLOCKING`; it is a different epistemic condition. When the missing characterization is decision-critical the component may be marked `blocking=True`.

## 5. Evaluation methods

R3.5 carries methods, not specialists. Current vocabulary:

- interval overlap;
- cross-source comparison;
- provenance check;
- scope alignment;
- method compatibility;
- evidence-quality assessment;
- conflict analysis;
- derivation reproducibility;
- assumption audit;
- causal-alternative analysis;
- extrapolation check;
- freshness check;
- specialist review;
- experimental retest.

R4 maps these assessment needs plus research dimensions to concrete roles.

## 6. New contracts

### `UncertaintyComponent`
Embedded typed component containing axis, operational level, origin, blocking flag, reason codes, source refs, permissible assessment methods and completion checks.

### `UncertaintyProfile/1.0` (`UPR-*`)
A versioned profile for one target entity/revision. It contains multiple components, readiness and dominant axes. It is an audit/projection object, not a replacement for Claim/Gap/Conflict/RelationAssessment.

### `AssessmentNeed`
The normalized unit of work for review. It states what question must be answered, by which assessment methods, over which refs and what completion criteria close the need.

### `ReviewWorkField/1.0` (`RWF-*`)
The pre-Tribunal input field. It contains target refs, UPR refs, assessment needs, open gaps, conflicts, relation assessments and relevant evidence refs.

It contains **no specialist names or panel roles**.

## 7. Deterministic adapters implemented at L1

### RelationAssessment -> uncertainty
Current assessment signals are preserved in `RelationAssessment.metadata.signals` (`scope_match`, `directness`, `method_match`, `evidence_quality`). R3.5 derives METHOD, EVIDENCE_SUFFICIENCY and selected SCOPE components from these normalized signals and verdict/use state.

### Gap -> uncertainty
Gap type deterministically maps to an initial axis family. Gap severity/state controls whether the component is blocking. Resolution requirements become completion criteria.

### Conflict -> uncertainty
Unresolved Conflict becomes a CONFLICT component with conflict analysis + scope alignment + cross-source comparison methods.

### Numeric uncertainty -> uncertainty
The legacy Decimal interval-overlap semantics are reused. R3.5 does not invent universal relative-error thresholds. If no reference/decision contract exists, the uncertainty is `UNCHARACTERIZED`; if the numeric result is explicitly decision-critical, it may be blocking.

## 8. Authority boundary

- Existing canonical knowledge objects remain authoritative for their own semantics.
- R3.5 is a derived audit/work projection.
- LLM/human/specialist signals may later contribute typed inputs, but they cannot set authoritative Claim/Relation state through UPR/RWF.
- R3.5 may describe a blocking need; it does not resolve the need.
- R4 may choose specialists for an `AssessmentNeed`; R4 composition does not rewrite the uncertainty profile by itself.

## 9. Persistence and observability

`UncertaintyFieldRepository` persists UPR/RWF through the existing SQLite/UoW substrate.

`build_minimal_service_artifact()` exposes separate `uncertainty_profiles` and `review_work_fields` sections. This makes the R4 input observable without smuggling it through prompt-only context.

## 10. What enters R4 Tribunal

R4 should receive a `ReviewWorkField` plus the canonical refs it names. Minimal input semantics:

```text
ReviewWorkField
  target_refs
  readiness
  assessment_needs[]
    axis
    level
    blocking
    question
    assessment_methods[]
    completion_criteria[]
    source_refs[]
    reason_codes[]
  open_gap_ids[]
  conflict_ids[]
  relation_assessment_ids[]
  evidence_refs[]
```

R4 composition should use this field together with ResearchDOM lineage dimensions (`Direction`, `Discipline`, `QuestionType`, `MethodView`, claim/relation profile) to select permanent and dynamic roles.

## 11. Fail-closed behavior

- Unknown axis/method/level enum: reject contract construction.
- `BLOCKING` with `blocking=False`: reject.
- Cross-run profiles in one work field: reject.
- Assessment need without targets, question or method: reject.
- Missing numeric comparison contract does not become a guessed percentage-based rating.
- Empty/unpopulated axis is not silently declared `RESOLVED`.

## 12. Current limitations

1. Source provenance, freshness, causality, assumption and extrapolation axes have vocabulary but no complete automatic adapters yet.
2. Gap-type -> axis mapping is intentionally conservative string-family mapping at L1; richer typed Gap taxonomy is preferable.
3. Numeric uncertainty is not stored canonically on R0 `Quantity`; R3.5 accepts an explicit numeric uncertainty observation/projection.
4. Work-field aggregation currently keeps assessment needs independently; no probabilistic fusion or inter-axis covariance model exists.
5. RelationAssessment signal normalization was added in R3.5 but older persisted RAS records may lack `metadata.signals`; fallback remains reason-code based/incomplete.
6. No specialist selection occurs here. That is the R4 boundary.

## 13. Complexity ladder

**L1 implemented**: multidimensional axes, operational levels, deterministic adapters for relation/gap/conflict/numeric uncertainty, durable profiles/work fields, artifact visibility.

**L2**: typed source/freshness/causal/assumption/extrapolation adapters; canonical Quantity uncertainty model; typed Gap taxonomy; cross-axis dependency links.

**L3**: calibration datasets and domain-specific uncertainty policies; correlated uncertainties and sensitivity/decision-impact analysis; contradiction clusters across claims/relations.

**L4**: Tribunal-generated competing uncertainty assessments with aggregation/quorum; justification sets/nogoods and TMS/ATMS propagation.

**L5**: learned routing/calibration from historical resolution effectiveness, while authority remains policy/reducer based.

## 14. R3 completion criterion

R3 is ready to hand off to R4 when the system can produce a durable ReviewWorkField that says what remains uncertain, why, how it can be assessed, what blocks reasoning, and what evidence/issues are involved, without selecting specialists or assigning epistemic truth.
