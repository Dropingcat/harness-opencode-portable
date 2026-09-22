# Researcher R4.1 — Deterministic Tribunal Composition Architecture

Status: IMPLEMENTED L1 candidate, acceptance/regression pending.
Date: 2026-09-13
Owner: Researcher orchestrator.

## 1. Block identity

**Name/version:** `R4.1 Deterministic Tribunal Composition / tribunal-composition-plan/1.0`.

**Implementation:**

- `scripts/researcher/researcher_core/tribunal_composition.py`
- `config/tribunal_composition.yaml`
- `tests/researcher/test_tribunal_composition.py`

**Public contracts:**

- `TribunalRoleSpec`
- `EvidenceViewPolicy`
- `TribunalLineageProfile`
- `AssessmentNeedRef`
- `AssessmentAssignment`
- `RoleBriefContract`
- `TribunalCompositionRequest`
- `TribunalCompositionPlan`
- `TribunalCompositionPolicy`

**Policy/config dependencies:**

- `config/tribunal_composition.yaml`
- `config/capabilities_authority.json`
- `config/logical_tools.json`

## 2. Purpose

R3.5 ends with a durable `ReviewWorkField` describing what remains uncertain, how it may be assessed and what blocks reasoning. R4.1 answers the next question only: **which closed, policy-admitted roles are required to assess each need, under which bounded evidence/tool contract?**

It does not run Tribunal dialogue, produce verdicts, mutate Claim/GraphEdge/Gap state, choose truth by majority, perform evidence slicing, or dispatch jobs.

## 3. Inputs / outputs

Input boundary:

```text
ReviewWorkField
+ ResearchDOM lineage
+ object/claim/relation profile tags
+ versioned TribunalCompositionPolicy
        ↓
TribunalCompositionPlan
```

`lineage_profile_from_research_dom()` uses structural `ResearchCardKind` boundaries. It does not scan arbitrary prose and invent disciplines/methods globally.

Output contains:

- policy-defined permanent roles;
- dynamically selected domain/method roles;
- AssessmentNeed assignments;
- role-specific EvidenceViewPolicy;
- allowed logical tools and capabilities;
- expected future typed output contract;
- inquiry depth/token budget contract;
- reason codes;
- policy hash/version;
- composition fingerprint.

## 4. Authority boundary

The compiler is authoritative only for **composition under a specific policy snapshot**. It has no write authority over ResearchDOM knowledge state, KnowledgeGraph truth, Claim status, GraphEdge lifecycle, Gap/Conflict lifecycle or RelationAssessment.

The LLM cannot materialize a new authoritative role. Missing expertise can later be proposed as a typed requirement, but admission into the role registry is a policy operation.

Central capability/tool authority remains `capabilities_authority.json` + `logical_tools.json`. Tribunal policy load fails closed if a role names a capability/tool absent from those registries.

## 5. Links to surrounding architecture

Upstream:

```text
R3.5 UncertaintyProfile
→ ReviewWorkField.assessment_needs
```

Composition inputs also consume the existing ResearchDOM lineage rather than introducing a second research taxonomy.

Downstream, but explicitly not executed in R4.1:

```text
TribunalCompositionPlan
→ R4.2 evidence-view compiler / evidence slices
→ R4.3 inquiry contracts / execution dispatch
→ later typed Tribunal findings / challenge feedback
```

Existing Job/Attempt runtime remains the only delegation substrate. R4 must not create a second scheduler.

## 6. Deterministic composition rules

1. Same `ReviewWorkField` + lineage + policy snapshot produces the same composition fingerprint.
2. Role taxonomy is closed by policy.
3. Permanent roles are policy data, not code constants.
4. Axis/method requirements activate explicit required roles.
5. Domain/method roles can additionally activate only through declared lineage tags and compatible axes/methods.
6. Synonymous role IDs are deduplicated by `equivalence_group`; `selection_priority`, then canonical role ID, breaks ties deterministically.
7. Every blocking need must have policy-compatible coverage or compilation fails `UNASSIGNED_NEED`.
8. Unsupported roles/capabilities/tools fail closed at policy load/compile time.
9. Fresh-context views cannot include previous conclusions.
10. Composition creates no authoritative knowledge-state transition.

## 7. AssessmentNeed identity seam

R3.5 `AssessmentNeed` is a frozen value object and currently has no entity ID. R4 needs durable assignment references.

R4.1 deliberately does **not** reopen the completed R3.5 contract. Instead it uses `AssessmentNeedRef`:

```text
ANR-<sha256-derived-content-key> + ordinal
```

The key is derived from `RWF id + canonical need content`; the ordinal disambiguates repeated identical needs in a concrete work field. This is independent of Python object identity and does not silently rely on array position alone.

A canonical versioned AssessmentNeed entity/ID remains TD-035.

## 8. Initial role policy

The L1 policy currently defines a permanent meta-panel:

- Critic
- Skeptic
- Methodologist
- Evidence Auditor

This is an explicit **policy choice**, not an architecture invariant. It can be versioned/replaced without editing compiler code.

Dynamic L1 roles include:

- Measurement Specialist
- Numerical Analyst
- Causal Critic
- Crystallographer
- XRD Specialist

The role registry is intentionally small. Domain-pack loading is deferred rather than encoding every scientific profession into a YAML bestiary.

### Legacy decisions preserved

From legacy Tribunal behavior, R4.1 preserves:

- adversarial/skeptical coverage as a distinct perspective;
- methodological review;
- asymmetric evidence views;
- fresh-context/blind first-pass capability;
- explicit tool boundaries;
- conflict as a reason for further inquiry rather than automatic failure.

### Legacy behavior intentionally not carried forward at R4.1

- one agent sequentially role-playing all judges;
- scalar judge confidence as authoritative state;
- majority voting as truth;
- hardcoded five-role prompt composition;
- aggregator verdict production;
- automatic Advocate inclusion;
- prompt-owned evidence selection.

Advocate is deferred until live dialectic exists and its defensive function can be represented as an inquiry contract. Aggregator is deferred until typed findings and aggregation semantics exist.

## 9. Evidence-view contract

R4.1 defines, but does not execute, these views:

- `FULL_RELEVANT`
- `CLAIM_PLUS_SUPPORT`
- `CLAIM_PLUS_COUNTEREVIDENCE`
- `FRESH_CONTEXT`
- `METHOD_ONLY`

The current Skeptic policy is `FRESH_CONTEXT` with both previous conclusions and provenance hidden. This is an L1 policy decision recorded in the decision log, not a universal rule. Actual ref selection/leakage prevention is R4.2.

## 10. Failure modes / fail-closed behavior

- unknown role in permanent/axis/method requirements → reject policy;
- unknown capability/tool → reject policy;
- invalid enum/view → reject policy;
- `FRESH_CONTEXT + include_previous_conclusions=true` → reject contract;
- blocking need without capable required role → `UNASSIGNED_NEED`;
- malformed budget/depth → reject contract;
- unknown/unadmitted role cannot be invented by LLM;
- composition never falls back to generic prose role for an explicitly required measurement/numeric specialist.

## 11. Current implementation limits

1. `AssessmentNeed` has no canonical R3 ID; R4 uses content-addressed `AssessmentNeedRef` (TD-035).
2. Domain role packs are static in one policy file; no plugin/admission lifecycle yet (TD-036).
3. Actual evidence-slice compilation is not implemented. R4.1 only produces `EvidenceViewPolicy` contracts (planned R4.2).
4. Runtime provider health/availability is not part of composition; policy validation checks registry existence, not live provider reachability (TD-037).
5. Role compatibility is exact typed axis/method plus normalized lineage tag intersection. No learned/fuzzy role ranking is allowed at L1.
6. Inquiry depth/token budget are policy parameters only. No execution occurs here.
7. Permanent panel roles may be listed even when a concrete need has no assignment for one of them; only roles with assigned work receive `RoleBriefContract` in L1. Cross-panel dialectic comes later.

## 12. Complexity ladder

- **L0:** closed static role list and direct axis mapping. Superseded by L1.
- **L1 (current):** typed contracts, versioned policy, deterministic axis/method/lineage routing, equivalence groups, authority validation, fail-closed coverage.
- **L2:** executable evidence-view compiler, domain role packs, provider-health-aware capability binding, canonical need identity.
- **L3:** typed inquiry contracts, independent first pass, Q/A/Q/A dialectic, adaptive recomposition between rounds.
- **L4:** aggregation/calibration from typed findings and historical role effectiveness without majority-truth authority.
- **L5:** learned ranking/calibration only after enough historical outcomes exist; reducers/policies remain authoritative.

## 13. Tests / acceptance gates

Implemented R4.1 tests currently cover:

- deterministic same-input composition;
- numeric blocking need selects Measurement Specialist;
- XRD + crystallography lineage selects XRD/Crystallography expertise;
- conflict receives Skeptic coverage;
- fresh-context hides prior conclusions/provenance under current policy;
- content-addressed AssessmentNeedRef;
- unsupported role policy rejection;
- no authoritative state fields in composition output;
- typed plan serialization;
- ResearchDOM lineage compilation;
- synonymous dynamic roles deduplicated by equivalence group.

Remaining acceptance before marking R4.1 DONE:

- full Researcher regression;
- compiler/static gates;
- representative R3.5 → R4.1 demo artifact;
- docs/tracker/debt reconciliation;
- Git boundary + package/recovery update.

## 14. Tech debt links

- TD-035 canonical AssessmentNeed identity.
- TD-036 domain role-pack registry/admission and richer taxonomy compatibility.
- TD-037 runtime capability availability and executable evidence slicing boundary.
- Existing TD-022/023/024/027/028/032/033/034 stay visible and are not opportunistically mixed into R4.1.

## 15. Recursive architecture ownership

Within the shared cycle:

```text
Object → Profile → Routing → Specialists/Tools/Skills → Processing → Validation → State/New Objects
```

R4.1 owns only **Routing → planned Specialists/Tools/Skills contracts**. It does not own processing, validation of expert findings, or state mutation.
