# Researcher R4.2 Implementation Review — Executable Tribunal Evidence Slicing

Date: 2026-09-13
Status: DONE (L1); executable validation, milestone package and recovery boundary complete.

## 1. What was implemented

R4.2 turns the R4.1 `EvidenceViewPolicy` from metadata into an executable, deterministic per-role evidence projection.

New/changed artifacts:

- `scripts/researcher/researcher_core/tribunal_evidence.py`
- `scripts/researcher/researcher_core/tribunal_composition.py` — one shared R4 AssessmentNeedRef bridge
- `tests/researcher/test_tribunal_evidence.py`
- `tests/researcher/test_r4_2_evidence_slicing_e2e.py`
- `scripts/researcher/demo_r4_2_evidence_slicing.py`
- `artifacts/researcher_r4_2/r4_2_evidence_slicing_e2e_demo.json`
- `RESEARCHER_R4_2_EVIDENCE_SLICING_ARCHITECTURE.md`
- updates to R4 decision log, tracker and tech debt.

## 2. Resulting contract

R4.2 compiles:

```text
ReviewWorkField
+ TribunalCompositionPlan
+ canonical state
        ↓
TribunalEvidenceBundle
  └─ TribunalEvidenceSlice(role)
```

Each slice records:

- role and assigned AssessmentNeed refs;
- concrete view kind;
- bounded target projections;
- evidence excerpts and typed polarity projection;
- source projections when permitted;
- optional prior-review artifacts when permitted;
- missing refs;
- READY/PARTIAL/BLOCKED status;
- deterministic fingerprint and control metadata.

No role execution occurs.

## 3. E2E-first result

The most useful validation was not a unit assertion but the real nearest-chain E2E:

```text
RelationAssessment
→ R3.5 uncertainty/RWF
→ R4.1 composition
→ R4.2 evidence bundle
```

The first run exposed a real contract seam: R3.5 `AssessmentNeed.target_refs` can contain `RAS-*` control refs. The first slicer implementation incorrectly treated those refs as missing canonical evidence and downgraded a valid XRD slice to `PARTIAL`.

The fix was architectural, not test-specific:

- projectable evidence/semantic namespaces are handled separately;
- control/lineage refs are retained explicitly as nonprojected metadata;
- target GraphEdges can structurally expose their canonical endpoints;
- missing evidence remains fail-closed, but control refs are not mislabeled as absent evidence.

This is the strongest practical argument so far for TD-038 cross-layer traceability.

## 4. Evidence-view behavior

### FULL_RELEVANT

Provides bounded relevant RWF/direct-relation evidence and allowed provenance.

### CLAIM_PLUS_SUPPORT

Uses typed active SUPPORTS relations. Counter-only evidence does not leak into the support view.

### CLAIM_PLUS_COUNTEREVIDENCE

Uses typed active CONTRADICTS relations. Support-only evidence does not leak into the counter view.

### FRESH_CONTEXT

Current Skeptic policy produces a structurally blind projection:

- no SourceProjection;
- no source ID/locator on evidence items;
- no previous conclusions;
- support/counter polarity becomes `UNLABELED`;
- selection reasons are neutralized to `ASSIGNED_RELEVANCE`;
- GraphEdge/Source target projections hide relation/provenance semantics.

This prevents a superficially blind view that still tells the Skeptic which excerpts the previous system considered support. It does not redact provenance words embedded inside the exact excerpt itself; TD-039 records that remaining boundary.

### METHOD_ONLY

The implementation is intentionally narrower than legacy keyword routing. It uses explicit assigned-need evidence and source endpoints of assigned target relations. No free-text “looks methodological” classifier is authoritative.

## 5. Post-green hardening findings

Manual code audit after the first green E2E/regression pass found two authority weaknesses not covered by the initial tests:

1. `FULL_RELEVANT/FRESH_CONTEXT` could consume the aggregate `RWF.evidence_refs`, potentially leaking evidence from an AssessmentNeed not assigned to that role. R4.2 now scopes evidence to assigned needs plus their typed target relations.
2. the original R4.1 composition fingerprint covered role selection/assignments and policy hash but not the materialized role-brief fields themselves. R4.1 now fingerprints briefs, capabilities/tools, evidence policy and inquiry budget; R4.2 verifies plan integrity before slicing. An inconsistently altered brief fails closed. The fingerprint is an integrity checksum, not an authenticity signature; authoritative plan provenance still belongs to the control plane/TD-038.

Both cases received regression tests. This is why branch review remains useful **after** E2E rather than being replaced by it. E2E finds shape/integration failures; post-green audit can still find authority coverage holes.

## 6. Missing evidence / bounding

R4.2 removed the legacy-style fallback that could silently fill an empty role view with generally trusted sources.

Instead:

- a missing canonical ref required by a blocking assignment (or an otherwise empty executable package) -> `BLOCKED`;
- truncated/bounded or non-blocking incomplete slice -> `PARTIAL`;
- target-only blocking work can still be `READY`, allowing the future reviewer to emit `MissingEvidence` rather than having R4.2 confuse epistemic incompleteness with slice-compilation failure;
- a role cannot widen the slice itself;
- selection remains deterministic under repeated compilation.

This makes an inadequate work package visible instead of producing a polished but irrelevant context bundle.

## 7. Legacy Tribunal reconciliation

The library/legacy review confirms that Tribunal evolved through several distinct functions:

1. internal skeptical discussion;
2. Advocate for important/vulnerable claims;
3. broader Tribunal escalation;
4. later dialectical design `Q1 -> A1 -> Q2(on A1) -> A2` rather than vote-as-truth.

R4.2 intentionally does not merge these levels into evidence slicing. It establishes the prerequisite for real independence: different roles can now receive different enforceable evidence projections.

The downstream direction remains:

```text
independent first pass
→ typed attack/challenge
→ optional Advocate/FOR-vs-AGAINST response
→ bounded Q/A/Q-on-A chain
→ typed discoveries
→ existing ResearchChallenge/reducer path
```

## 8. Validation results

### R4.2 local + E2E

`test_tribunal_evidence.py + test_r4_2_evidence_slicing_e2e.py`: **17/17 PASS**.

Coverage includes:

- support/counter asymmetry;
- FRESH_CONTEXT provenance/conclusion/polarity hiding;
- METHOD_ONLY non-widening;
- FULL_RELEVANT projection;
- deterministic fingerprints;
- missing blocking evidence / no backfill;
- plan/RWF mismatch rejection;
- cross-run rejection;
- deterministic max-ref bounding;
- prior-review visibility policy;
- serialization/authority boundary;
- read-only canonical state;
- real R3.3/R3.5/R4.1/R4.2 E2E.

### R3.5 + R4.1 + R4.2 targeted

**40/40 PASS**.

### Full Researcher

**517 total / 513 PASS / 4 known baseline failures.**

The four failures are unchanged TD-015:

- 2 Guard expectations;
- 2 LocalCorpus fixture/index expectations.

No R4.2 regression class appeared.

### Compiler/static gates

- runtime compiler `--check`: PASS, hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`;
- capability compiler `--check`: PASS, hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`;
- `compileall`: PASS;
- `git diff --check`: PASS;
- R4.2 executable demo: PASS.

## 9. Demo result

The BCC/XRD demo composes R3.5 uncertainty into an R4.1 panel and then compiles role-specific R4.2 slices.

Observed slice behavior includes:

- Critic receives counterevidence view;
- Skeptic receives blind fresh evidence without provenance/polarity labels;
- Methodologist/XRD Specialist receive narrow method evidence;
- Crystallographer receives support view;
- Claim status remains OPEN;
- GraphEdge revision remains unchanged;
- no dialogue is executed.

Artifact: `artifacts/researcher_r4_2/r4_2_evidence_slicing_e2e_demo.json`.

## 10. Weak points not hidden by green tests

1. `AssessmentNeedRef` remains a compatibility bridge rather than canonical identity (TD-035).
2. The mixed control/semantic/evidence ref shape demonstrates need for a general traceability substrate (TD-038), not more local hashes.
3. `METHOD_ONLY` cannot yet use a rich typed method-evidence ontology; current behavior is intentionally conservative.
4. `PriorReviewArtifact` is temporary. R4.3 needs canonical Inquiry/Argument artifacts before previous conclusions can be disclosed safely.
5. Runtime provider health is still unresolved (remaining TD-037). A declared capability is not proof of an executable healthy provider.
6. Domain role packs remain deliberately deferred (TD-036).
7. Exact source-quality/trust semantics are absent from canonical Source; R4.2 does not revive legacy trust heuristics as hidden authority.
8. `EvidenceSelectionReason.MAX_REFS_TRUNCATED` exists in the vocabulary but truncation is currently represented at slice level by `truncated/PARTIAL`; per-item reason is not necessary for L1 and should either gain concrete semantics later or be removed.
9. R4.2 does not yet implement staged reveal (blind pass -> provenance/polarity reveal); it only makes the first-stage contract enforceable.
10. Evidence relation polarity is only as complete as canonical GraphEdges. Unlinked relevant evidence is not magically classified.
11. FRESH_CONTEXT does not semantically redact provenance embedded in exact evidence text (TD-039). Structural blindness is enforced; semantic anonymization needs a separately testable projection/redaction design.
12. `max_refs` bounds evidence excerpts only; total serialized slice size is not yet a hard token/context budget.

## 11. Recommendation

R4.2 is frozen at its L1 Git/package/recovery boundary.

The next hard boundary should be **R4.3 typed inquiry contract + independent first-pass execution**, not Advocate or full debate immediately. R4.3 should consume only R4.2 slices, bind role capabilities through the existing runtime/Job/Attempt substrate, emit typed `InquiryTurn/ArgumentArtifact`, and leave all state mutation to reducers/admission.

Only after that execution path is E2E-proven should R4.4 add Advocate/FOR-vs-AGAINST and `Q1 -> A1 -> Q2(on A1) -> A2` dialectics.


## 12. Closure revalidation after milestone packaging

The frozen R4.2 checkout was re-executed rather than trusted from the earlier review record:

- R3.5 + R4.1 + R4.2 targeted chain: **40/40 PASS**;
- full Researcher: **517 total / 513 PASS / the same four TD-015 failures**;
- runtime compiler `--check`: PASS, hash unchanged;
- capability compiler `--check`: PASS, hash unchanged;
- `compileall`: PASS;
- executable R4.2 demo: PASS;
- `git diff --check`: PASS;
- milestone ZIP SHA256 matches its stored checksum;
- R4.2 recovery bundle verifies as complete history at the frozen boundary.

One operational weakness was observed during this revalidation: invoking `python -m pytest tests/researcher` directly from repository root fails collection because `researcher_core` is not on the default import path. The verified command requires `PYTHONPATH=scripts/researcher`. This does not change R4.2 semantics, but it is now tracked as TD-040 because E2E-first development should be reproducible from a repository-owned command rather than remembered shell state.
