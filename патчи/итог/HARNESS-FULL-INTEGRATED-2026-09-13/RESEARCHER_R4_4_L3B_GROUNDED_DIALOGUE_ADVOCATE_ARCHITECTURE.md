# Researcher R4.4 L3B — grounded semantic dialogue and live conditional Advocate

Date: 2026-09-13
Status: structural/runtime slice implemented and E2E-tested; production OpenCode semantic execution remains environment-blocked because `opencode` is unavailable.

## 1. Why this layer exists

L3A proved that a semantic role can be addressed explicitly, bound to one authorized provider, receive one bounded TEX envelope and return IQT/ARG through Job/Attempt/PER. L3B addresses a deeper scientific problem: a fluent answer is not evidence merely because a specialist role produced it.

The system must distinguish:

```text
what is grounded in disclosed evidence
what is grounded only in the current canonical target/context
what follows from a prior visible argument/turn
what is an explicit assumption
what is a derivation from visible material
what is only model prior / remembered training knowledge
```

This distinction is required before live dialogue can be interpreted as scientific review rather than role-play.

## 2. Response grounding model

`ArgumentArtifact` now carries typed `ResponseGroundingItem[]` and a deterministic `ResponseGroundingState`.

Grounding kinds:

```text
DISCLOSED_EVIDENCE
DISCLOSED_TARGET
PRIOR_ARGUMENT
PRIOR_TURN
EXPLICIT_ASSUMPTION
MODEL_PRIOR
DERIVATION_FROM_VISIBLE
```

Operational states:

```text
DOCUMENTED
MIXED
VISIBLE_CONTEXT_ONLY
MODEL_PRIOR_ONLY
UNGROUNDED
UNCHARACTERIZED
```

`MODEL_PRIOR` is explicitly permitted as a hypothesis source but never becomes evidence by naming it confidently. It carries no fake source refs.

## 3. Research coupling rule

If a live semantic answer attempts a material non-OPEN position while its grounding is only `MODEL_PRIOR_ONLY` or `UNGROUNDED`, deterministic admission adds:

- blocking `MISSING_EVIDENCE`;
- typed `AdditionalEvidenceRequest` asking for an external source, measurement or reproducible derivation.

The argument is retained historically because it may be scientifically useful as a hypothesis. It cannot close the branch merely because the model remembers a similar statement.

This creates the desired boundary:

```text
semantic idea
!= evidence

semantic idea
+ research request
+ admitted evidence/derivation
-> potentially usable scientific support
```

Evidence itself remains traceable through canonical EVD/SRC provenance rather than through the role label.

## 4. Live conditional Advocate

Advocate remains admitted-but-conditional. It is not a default respondent and no permanent Defender role is introduced.

The live path is now:

```text
material ATTACKS/UNDERCUTS
-> AdvocateActivationDecision
-> branch-local DDC
-> ADC
-> RoleProviderBinding(DEFENSE)
-> Advocate TEX
-> Job / Attempt
-> PER
-> AdvocateWorkerDraft
-> AdvocateResponse
-> IQT + ARG
-> REPLIES_TO
-> optional DEFENDS
-> ArgumentGraph admission
-> dialectic control / research
```

A live Advocate provider uses exactly the same provider/runtime authority as ordinary roles.

## 5. Defense grounding rule

A provider may propose `DEFEND`, but a defense without disclosed evidence is not materialized as a successful `DEFENDS` branch.

If a live Advocate proposes `DEFEND` while grounding is `MODEL_PRIOR_ONLY`, `UNGROUNDED`, or only visible context without evidence, the deterministic parser converts the semantic outcome to `REQUEST_EVIDENCE`.

Result:

```text
REPLIES_TO challenge
no DEFENDS edge
REQUEST_LOCAL_RESEARCH
```

A documented `QUALIFY` or `DEFEND` may create both:

```text
REPLIES_TO challenge
DEFENDS defended argument
```

This prevents rhetorical defense from being mistaken for evidence-backed defense.

## 6. Visibility and traceability

Grounding refs are validated against the active DDC/ADC envelope.

A grounding item cannot cite:

- a hidden sibling argument;
- a hidden turn;
- evidence absent from the disclosure;
- a target outside the branch contract.

Live Advocate hidden-sibling grounding is rejected as runtime `REJECTED`, not epistemic `OPEN`.

The persisted output includes:

```text
RPB
TEX
PER
IQT
ARG
ArgumentArtifact.grounding_items
ArgumentArtifact.grounding_state
```

so later audit can distinguish "the model said this" from "the model cited EVD-X which traces to SRC-Y".

## 7. Defender is a response function, not currently a persona

Current architectural direction remains:

```text
ResponseAssignment
    facet/position ownership
    semantic respondent
    response function
        EXPLAIN
        DEFEND
        QUALIFY
        CONCEDE
        REFER
        REQUEST_EVIDENCE
    optional conditional Advocate
```

The scientific specialist normally owns explanation of its facet. Advocate tests whether an already challenged position can be defended under bounded evidence. Either participant may concede a local point.

A separate permanent Defender should not be introduced before live traces demonstrate a distinct stable responsibility that cannot be represented as response function + party/facet ownership.

## 8. Multidisciplinary Claim projection

One canonical `CLM-*` remains one Claim. Multidisciplinary review should not destructively split it into several canonical Claims merely because several disciplines inspect it.

Future target:

```text
CLM-X
└── ClaimReviewCase
    ├── ReviewFacet: crystallography
    │   └── independent Q/A + ARG branch
    ├── ReviewFacet: kinetics/causality
    │   └── independent Q/A + ARG branch
    └── ReviewFacet: measurement/statistics
        └── independent Q/A + ARG branch
```

Every branch retains:

- root Claim ID;
- facet ID;
- AssessmentNeed lineage;
- DDC/DQC/ARG/IQT lineage;
- provider/runtime lineage;
- independent branch history.

The branches remain independent during review but belong to one review case.

## 9. Join is composition, not voting

Future `ClaimReviewJoinProjection` should report:

- facet coverage;
- blocking/open/resolved facets;
- cross-facet dependencies;
- conflicts;
- synergy / prerequisite closure;
- whether an integration-review branch is needed;
- readiness for the authoritative reducer.

Example synergy:

```text
XRD branch establishes that a structural interpretation is only qualified
        ↓
causal branch may no longer assume unique phase attribution
        ↓
causal conclusion is automatically scope-limited
```

Example conflict:

```text
crystallography branch: interpretation A remains plausible
measurement branch: required precision cannot distinguish A/B
        ↓
integration state = unresolved, not 1:1 vote
```

The join never mutates Claim truth directly.

## 10. Current environment limit

The shared provider `existing.opencode_tribunal_role` is registered with DQC/ADC support but current preflight reports it unavailable because the `opencode` executable is absent.

Therefore current L3B tests prove:

- typed grounding semantics;
- production-shaped semantic envelopes;
- process-level live Q/A;
- live conditional Advocate execution;
- Job/Attempt/PER persistence;
- argument-graph admission;
- fail-closed visibility and model-prior handling.

They do **not** prove scientific quality of a production OpenCode/LLM provider.

## 11. Acceptance currently observed

- specialist `MODEL_PRIOR` answer remains traceable but creates blocking research debt;
- disclosed-evidence specialist answer is `DOCUMENTED`;
- live Advocate documented QUALIFY creates REPLIES_TO + DEFENDS;
- live Advocate prior-only DEFEND is converted to REQUEST_EVIDENCE and creates no DEFENDS edge;
- hidden sibling Advocate grounding is rejected;
- existing R4.1-L3A acceptance remains green.

## 12. Next execution gate

True production L3B completion requires an environment where at least one authorized semantic provider is execution-ready. Then rerun the same contracts unchanged against the real provider and evaluate:

- grounding honesty;
- hallucinated refs;
- quality of Q1/A1/Q2/A2;
- false issue novelty;
- false closure;
- Advocate rationalization tendency;
- convergence/no-progress behavior.
