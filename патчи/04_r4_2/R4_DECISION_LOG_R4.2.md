# R4 Discussion / Decision / Pattern Log

Status: ACTIVE. This file is a session-migration artifact and MUST be updated with each meaningful R4 design change.

## Record format

Each record contains: ID, status, date, question, decision/pattern, rationale, rejected alternatives, consequences, revisit trigger.

Statuses: `ACCEPTED`, `REJECTED`, `OPEN`, `SUPERSEDED`, `EXPERIMENTAL_POLICY`.

---

## R4-D001 — R3/R4 authority boundary

**Status:** ACCEPTED
**Date:** 2026-09-13

**Question:** Should Tribunal determine what is uncertain?

**Decision:** No. `ReviewWorkField` is the R3→R4 boundary. R3 owns characterization of uncertainty and AssessmentNeeds; R4 owns composition of assessors and work contracts.

**Rationale:** prevents Tribunal from inventing its own problem statement and keeps uncertainty analysis separately testable.

**Rejected:** prompt-only Tribunal that first decides what to investigate.

**Revisit:** only if an R4 acceptance test proves RWF structurally insufficient; do not reopen R3.5 for convenience.

## R4-D002 — Composition before dialogue

**Status:** ACCEPTED

**Decision:** R4.1 stops at `TribunalCompositionPlan`. No live judges, attacks, votes or aggregate verdicts.

**Rejected:** port legacy `tribunal-judge.md` directly into the new runtime.

**Reason:** composition must be deterministic/testable before LLM dialogue exists.

## R4-D003 — Closed/versioned role taxonomy

**Status:** ACCEPTED

**Decision:** authoritative roles come from `config/tribunal_composition.yaml`. LLM may later propose missing expertise but cannot create an authoritative role at runtime.

**Rejected:** free-form role names generated from the prompt.

**Consequence:** unsupported role requests fail closed.

## R4-D004 — Permanent panel is policy, not architecture

**Status:** EXPERIMENTAL_POLICY

**Current policy:** Critic + Skeptic + Methodologist + Evidence Auditor.

**Reason:** retains independent meta-review coverage while removing legacy hardcoded five-role prompt.

**Rejected as architecture invariant:** fixed permanent panel compiled into Python.

**Revisit:** after R4.3/R4.4 empirical role utility and duplication data.

## R4-D005 — Advocate handling

**Status:** OPEN / DEFERRED

**Decision for R4.1:** Advocate is not permanent and is not yet instantiated.

**Reason:** without live dialectic, “defend the claim” is not a meaningful composition function and risks systematic confirmation bias.

**Candidate later rule:** activate Advocate conditionally after a typed attack/challenge exists, with bounded evidence and explicit defense contract.

## R4-D006 — Aggregator handling

**Status:** ACCEPTED FOR R4.1

**Decision:** no Aggregator role in composition L1.

**Reason:** there are no typed Tribunal findings to aggregate yet. Majority-vote truth from legacy is explicitly rejected.

**Revisit:** R4/L4 aggregation semantics.

## R4-D007 — AssessmentNeed identity seam

**Status:** ACCEPTED TEMPORARY BRIDGE

**Problem:** R3.5 `AssessmentNeed` has no EntityId although R4 assignments require stable need references.

**Decision:** use R4-local content-addressed `AssessmentNeedRef(ANR-hash, ordinal)` without mutating the completed R3.5 contract.

**Rejected:** silently use list index as identity; opportunistically redesign R3.5 during R4.1.

**Debt:** TD-035 canonical AssessmentNeed identity.

## R4-D008 — Evidence asymmetry belongs to code contract

**Status:** ACCEPTED

**Decision:** `EvidenceViewPolicy` is compiled by R4; role prompts may not widen it.

**Preserved legacy pattern:** asymmetric views reduce correlated failures.

**Rejected legacy mechanism:** `judge_brief.py`/prompt owns final slicing semantics.

## R4-D009 — Fresh-context provenance visibility

**Status:** EXPERIMENTAL_POLICY

**Current policy:** Skeptic `FRESH_CONTEXT`, `include_previous_conclusions=false`, `include_provenance=false`.

**Reason:** strongest independence from prior verdict/source-prestige anchoring at first pass.

**Risk:** hiding provenance may prevent source-quality critique.

**Revisit:** R4.2 should test two-stage fresh pass: blind first pass followed by provenance reveal.

## R4-D010 — Role synonym handling

**Status:** ACCEPTED

**Decision:** roles have `equivalence_group` and `selection_priority`; compiler keeps one canonical candidate per equivalence group.

**Rejected:** string-name dedup only.

## R4-D011 — Lineage routing semantics

**Status:** ACCEPTED L1

**Decision:** role activation uses structural ResearchDOM lineage card kinds and declared dimension/title tags. No unrestricted semantic inference over arbitrary prose.

**Reason:** reproducibility and inspectable routing.

**Future:** typed domain vocabularies / admitted role packs, not opaque learned routing first.

## R4-D012 — Capability/tool authority

**Status:** ACCEPTED

**Decision:** Tribunal role policy may only name capabilities/tools present in central registries. Policy load fails closed otherwise.

**Rejected:** separate Tribunal-only tool registry.

## R4-D013 — Inquiry depth and token budget

**Status:** EXPERIMENTAL_POLICY

**Current values:** depth=2, token budget=6000 per assigned role.

**Meaning in R4.1:** contract metadata only; no execution.

**Revisit:** before R4.3 live inquiry. Values must be calibrated, not fossilized from one fixture.

## R4-D014 — Decision/history tracking

**Status:** ACCEPTED

**Decision:** this log is a required session-handoff artifact. Accepted, rejected, superseded and open patterns must be recorded alongside implementation tracker, tech debt and implementation review.

**Reason:** future sessions need the reasoning lineage, not only the final code state.

## R4-D015 — E2E-first acceptance for architectural capsules

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** every new capsule/block should, where technically possible, be exercised through the nearest real end-to-end chain before branch review/audit is considered sufficient.

**Reason:** static review can verify contracts while still missing boundary-shape errors. The first R4.2 E2E immediately exposed that R3.5 `AssessmentNeed.target_refs` may contain control refs such as `RAS-*` because source refs are folded into the need target tuple.

**Rejected:** treating unit coverage + document audit as sufficient evidence that a new boundary composes correctly.

**Consequence:** branch close order is `implementation -> targeted/E2E execution -> defect repair -> full regression -> review/audit/docs`.

## R4-D016 — Legacy Tribunal levels are preserved as staged inquiry, not one monolith

**Status:** ACCEPTED DIRECTION / EXECUTION DEFERRED
**Date:** 2026-09-13

**Recovered legacy sequence:** internal skeptical discussion -> Advocate for important/vulnerable claims -> Tribunal escalation. Later design evolved further toward independent views followed by dialectical `Q1 -> A1 -> Q2(on A1) -> A2` rather than majority voting.

**Decision:** preserve these functions as separate future inquiry stages/contracts:

1. independent evidence-conditioned first pass;
2. adversarial FOR/AGAINST or challenge/defense stage when policy triggers it;
3. bounded question/answer/question-on-answer chain;
4. typed discovery extraction and reducer-controlled disposition/escalation.

R4.2 implements only the evidence-control prerequisite. It does not instantiate Advocate or run discussion.

**Rejected:** porting the legacy five-role prompt and aggregator directly as one Tribunal worker.

**Revisit:** R4.3/R4.4 inquiry contract design.

## R4-D017 — Cross-layer traceability must become a first-class substrate

**Status:** ACCEPTED REQUIREMENT / OPEN DESIGN
**Date:** 2026-09-13

**Problem:** the temporary `AssessmentNeedRef` bridge is one symptom of a wider identity/lineage problem. Objects, derived projections, decisions, evidence slices, attempts and later inquiry turns need a queryable chain explaining what produced what, under which version/policy/run/attempt and which object revision was consumed.

**Decision:** design a general traceability substrate rather than patch each R3->R4 seam with local hashes. Candidate concepts are a versioned `TraceabilityLink` / `LineageEnvelope` plus a query/index layer. It must record identity and derivation, not become a semantic or truth authority.

**Required scope:** entity version lineage; produced-from/consumed-by; transformation step; policy/config hash; Job/Attempt/ResearchCard provenance; cross-layer aliases/bridges; selective invalidation/replay queries.

**Rejected:** one mutable god-object that "owns" every entity; ad-hoc string IDs independently invented by each phase.

**Debt:** TD-038.

## R4-D018 — R4.2 evidence selection uses canonical typed refs, not legacy trust/keyword fallback

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** executable evidence slicing is derived from `AssessmentNeed` refs, RWF evidence pool and canonical active `GraphEdge` SUPPORTS/CONTRADICTS relations. No free-text method-source classifier and no automatic top-N trust fallback are authoritative.

**Preserved legacy idea:** asymmetric views and blind first pass.

**Rejected legacy mechanism:** if a role-specific slice is empty, silently give top-3 high-trust sources. Missing blocking evidence remains visible as `BLOCKED` instead.

## R4-D019 — FRESH_CONTEXT hides semantic polarity as well as provenance/current conclusions

**Status:** ACCEPTED L1 POLICY
**Date:** 2026-09-13

**Decision:** a fresh-context slice may receive the selected evidence texts, but SUPPORT/COUNTER labels are projected as `UNLABELED`; source title/locator/source ID and prior review artifacts remain hidden when policy forbids them.

**Reason:** hiding the preliminary verdict while labeling every excerpt "support" or "counter" would be independence theater.

**Revisit:** R4.3 two-stage blind -> provenance/polarity reveal experiments.

## R4-D020 — Domain role packs remain explicit debt during R4.2

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** do not implement dynamic/admitted domain role packs inside evidence slicing. Keep TD-036 open until the evidence and inquiry contracts are stable enough to define pack authority safely.


## R4-D021 — Evidence slices are assignment-scoped, not RWF-global

**Status:** ACCEPTED
**Date:** 2026-09-13

**Problem:** the first FULL_RELEVANT/FRESH_CONTEXT implementation could include aggregate `ReviewWorkField.evidence_refs`, including evidence that belonged only to another AssessmentNeed/branch.

**Decision:** role evidence is scoped to that role's assigned AssessmentNeeds plus structurally related canonical GraphEdges/endpoints. Aggregate RWF evidence is not an automatic visibility grant.

**Rejected:** interpreting FULL_RELEVANT as “dump every evidence ref in the work field”.

**Reason:** Tribunal independence and branch-local review require need-level visibility boundaries; otherwise evidence slicing becomes a prettier giant-context prompt.

## R4-D022 — CompositionPlan is an integrity-checked authority artifact

**Status:** ACCEPTED
**Date:** 2026-09-13

**Problem:** the first R4.1 composition fingerprint represented role selection and assignments but did not directly cover materialized RoleBrief authority fields. R4.2 would therefore trust a transferred plan whose evidence view/capabilities/budget could theoretically be modified while retaining the old fingerprint.

**Decision:** composition fingerprint covers assignments plus RoleBrief evidence policy, capabilities, tools, expected output contract and inquiry budgets. R4.2 validates fingerprint and brief↔assignment consistency before slicing. The hash is an integrity checksum, not a signature; admitted-plan provenance remains a separate control-plane/traceability requirement.

**Rejected:** assuming all in-memory/dataclass plans are trusted forever and deferring integrity until persistence exists.

**Reason:** the plan is a control-plane authority object and will cross persistence/session/runtime boundaries; integrity needs to be part of the contract before live worker execution.


## R4-D023 — FRESH_CONTEXT blindness is enforced across all structural leak channels

**Status:** ACCEPTED L1 + EXPLICIT LIMIT
**Date:** 2026-09-13

**Finding:** hiding SourceProjection and setting `polarity=UNLABELED` was insufficient. Selection reason codes could still say SUPPORT/COUNTER, and a target GraphEdge could still expose `edge_kind=SUPPORTS/CONTRADICTS`.

**Decision:** FRESH_CONTEXT also neutralizes selection reasons and masks GraphEdge relation semantics/endpoints plus Source target provenance/type metadata.

**Limit:** exact evidence text is preserved and may itself contain author names, DOI/journal strings or other provenance. R4.2 does not silently rewrite scientific quotations to achieve anonymity. This residual semantic-leak problem is TD-039.

## R4-D024 — EvidenceSlice status describes compilation executability, not epistemic resolution

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** `READY/PARTIAL/BLOCKED` on an EvidenceSlice describes whether the bounded role package can be compiled, not whether the AssessmentNeed is epistemically solved. A blocking numeric need with a valid QTY target and no EVD may be READY so the future specialist can return `MissingEvidence` or a qualification. Missing canonical refs required by a blocking assignment still fail closed as BLOCKED.

**Rejected:** `blocking need + zero EvidenceSpan -> BLOCKED` as a universal rule. That conflates evidence packaging with the Tribunal's future assessment.
