# Researcher R4.1 Implementation Review — Deterministic Tribunal Composition

Date: 2026-09-13
Status: L1 implementation complete; pre-commit acceptance review.

## 1. What was implemented

R4.1 now compiles a typed `TribunalCompositionPlan` from the R3.5 `ReviewWorkField`, structural ResearchDOM lineage and a versioned Tribunal policy.

Implemented artifacts:

- `scripts/researcher/researcher_core/tribunal_composition.py`
- `config/tribunal_composition.yaml`
- `tests/researcher/test_tribunal_composition.py`
- `artifacts/researcher_r4_1/r4_1_tribunal_composition_demo.json`
- `RESEARCHER_R4_1_TRIBUNAL_COMPOSITION_ARCHITECTURE.md`
- `R4_DECISION_LOG.md`
- updated `R4_NEXT_PHASE_PLAN.md`, tracker, tech debt and architecture state.

## 2. Contract result

R4.1 provides:

- closed/versioned role registry;
- policy-defined permanent meta-panel;
- deterministic dynamic role activation from uncertainty axis, assessment method and structural lineage tags;
- stable R4-local references to R3.5 AssessmentNeeds;
- assignments with reason codes;
- role evidence-view contracts;
- allowed capability/tool contracts;
- expected typed result-contract name for later execution;
- inquiry budget/depth metadata;
- policy hash and composition fingerprint.

No live Tribunal agent is invoked.

## 3. Important implementation decisions

### 3.1 AssessmentNeed identity

R3.5 `AssessmentNeed` lacks EntityId. R4.1 therefore uses content-addressed `AssessmentNeedRef` scoped to the RWF plus ordinal disambiguation. This preserves the completed R3.5 boundary and is explicitly tracked as TD-035 rather than hidden behind array indexes.

### 3.2 Permanent roles

The initial policy uses Critic, Skeptic, Methodologist and Evidence Auditor. These are data in `tribunal_composition.yaml`, not Python constants. Changing the permanent core changes policy hash rather than compiler code.

### 3.3 Legacy Advocate/Aggregator

Neither is blindly ported from the legacy five-role prompt. Advocate is deferred until an actual typed attack/defense dialectic exists. Aggregator is deferred until typed Tribunal findings and non-majority aggregation semantics exist.

### 3.4 Evidence views

R4.1 compiles view contracts only. Actual evidence refs are not sliced yet. The current Skeptic policy is a strong `FRESH_CONTEXT` first pass with provenance and previous conclusions hidden. This is recorded as experimental policy and must be tested in R4.2.

### 3.5 Synonymous roles

`equivalence_group + selection_priority` prevents multiple policy names for the same specialist family from entering the panel simultaneously. This is deterministic and tested.

## 4. Legacy reconciliation

Legacy `agents/tribunal-judge.md` contains valuable patterns but mixed several authority layers inside one prompt: role selection, evidence slicing, per-role judgment, attacks, voting, aggregation and escalation.

R4.1 preserves the useful semantic patterns:

- independent perspectives;
- Skeptic/adversarial coverage;
- Methodologist role;
- asymmetric evidence views;
- fresh/blind context;
- escalation as future research rather than simple failure.

It intentionally rejects/defers:

- one LLM sequentially impersonating every judge;
- prompt-owned evidence selection;
- confidence scalar as authoritative state;
- 3:1 majority truth;
- suspicious-unanimity rules as a truth reducer;
- aggregator verdict at composition time.

## 5. Validation results

### R4.1 tests

`tests/researcher/test_tribunal_composition.py`: **11/11 PASS**.

Coverage includes deterministic replay, numeric-specialist selection, XRD/crystallography routing, skeptical conflict coverage, fresh-context restrictions, AssessmentNeedRef, unknown-role rejection, state-boundary checks, serialization, ResearchDOM lineage compilation and synonym-role deduplication.

### Targeted R3.5 + R4.1

`test_uncertainty_field.py + test_tribunal_composition.py`: **21/21 PASS**.

### Full Researcher

**499 total / 495 PASS / 4 known baseline failures.**

The four failures are unchanged TD-015:

- 2 Guard expectations;
- 2 LocalCorpus fixture/index expectations.

No R4.1 regression class appeared.

### Compiler/static gates

- runtime compiler `--check`: PASS, hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`;
- capability compiler `--check`: PASS, hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`;
- `compileall researcher_core`: PASS;
- `git diff --check`: PASS after Markdown whitespace cleanup.

## 6. Scientific routing demo

The BCC/XRD demo starts from three needs:

1. blocking METHOD uncertainty;
2. blocking NUMERIC_MEASUREMENT uncertainty;
3. material CAUSALITY uncertainty.

Lineage declares crystallography / physics of metals and XRD.

The composition deterministically adds:

- Crystallographer;
- XRD Specialist;
- Measurement Specialist;
- Causal Critic;

on top of the policy-defined permanent panel. The output contains three assignments and no knowledge-state mutation.

Artifact: `artifacts/researcher_r4_1/r4_1_tribunal_composition_demo.json`.

## 7. Weak points not hidden by green tests

1. Canonical AssessmentNeed entity identity is missing (TD-035).
2. Domain role registry is a single static L1 policy, not modular admitted packs (TD-036).
3. Evidence view is still a contract, not a compiled reference slice; runtime provider availability is not checked (TD-037/R4.2).
4. Exact tag matching is intentionally conservative. It will miss undeclared synonyms rather than guess them.
5. Current role coverage does not yet solve global weighted set-cover optimisation. Required-role policy plus equivalence dedup is sufficient for the small L1 taxonomy; optimise only when real packs create meaningful overlap.
6. Permanent roles can remain listed even if a concrete AssessmentNeed is not assigned to them. This is intentional separation between panel membership and need-specific work; later dialectic may give panel-level duties.
7. Inquiry depth=2 and token budget=6000 are uncalibrated policy defaults because R4.1 does not execute inquiry.

## 8. Recommendation

R4.1 is suitable to freeze as the deterministic composition boundary after final Git/package/recovery creation. The next implementation should be R4.2 evidence slicing, not live Tribunal dialogue.

R4.2 should prove that `EvidenceViewPolicy` compiles to actual ref sets without leakage, especially for `FRESH_CONTEXT`, and should bind declared capabilities to existing runtime providers without creating a new scheduler.


## 9. Post-R4.2 hardening note

R4.2 executable slicing turned the composition plan into an authority-bearing runtime input and therefore tightened one R4.1 invariant. Current code now fingerprints the complete materialized role brief authority surface and exposes `validate_tribunal_composition_plan_integrity()`. The original R4.1 milestone metrics above remain the historical freeze metrics; one additional R4.1 integrity test was added during R4.2, bringing the current R4.1 test file to 12 tests.

This is recorded as downstream hardening, not a retroactive claim that the original milestone had already tested this property.
