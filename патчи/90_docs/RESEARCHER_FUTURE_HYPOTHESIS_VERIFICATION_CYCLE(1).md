# Future architecture — Hypothesis verification, revision and evidence-grounded research cycles

Date: 2026-09-13
Status: future-growth architecture note; discussion/design checkpoint, not executable authority.

## 1. Why add a hypothesis layer

The current Researcher/Tribunal stack can already represent Claims, evidence, uncertainty, ReviewWorkField, argument branches, bounded Q/A, research challenges and grounded specialist responses. The next missing scientific abstraction is a historical object that represents **an explanation under test**, not merely a proposition with a status.

A useful research loop is:

```text
Observation / Gap / Conflict / unexplained result
        ↓
Hypothesis H0
        ↓
explicit scope + assumptions + predictions + alternatives
        ↓
VerificationPlan
        ↓
search / measurement / computation / source inspection
        ↓
Evidence + counterevidence + derivations
        ↓
independent review / Tribunal branches
        ↓
HypothesisAssessment
        ↓
retain | qualify | revise | split | reject | keep OPEN
        ↓
H1 / next historical revision
        ↓
new bounded verification cycle
```

The objective is not to automate a declaration of truth. The objective is to make it possible to reconstruct **why a hypothesis existed, what could have falsified it, what was actually checked, what evidence changed it, and why a new revision was created**.

## 2. Authority boundary

Keep these distinctions explicit:

```text
Hypothesis
!= Claim
!= Evidence
!= Argument
!= ClaimAssessment
!= model prior
```

A `Claim` is a proposition admitted into the canonical knowledge layer.

A `HypothesisCase` is the historical research process around one explanatory candidate or family of candidates.

A hypothesis statement may be represented by or linked to a canonical Claim, but not every Claim is a hypothesis and a hypothesis must not overwrite Claim truth directly.

Tribunal roles, Writer, Coder and semantic models may propose hypothesis changes. Admission/reducers own canonical state transitions.

## 3. Candidate object model

Do not implement all objects immediately. This is the target decomposition to test with virtual E2E first.

### 3.1 HypothesisCase

```text
HypothesisCase/1.0
  case_id
  root_problem_refs[]
  root_claim_refs[]
  current_revision_id
  revision_ids[]
  competing_hypothesis_refs[]
  verification_iteration_ids[]
  review_case_refs[]
  state
  policy_version/hash
```

The case is stable across revisions.

### 3.2 HypothesisRevision

```text
HypothesisRevision/1.0
  hypothesis_revision_id
  case_id
  parent_revision_id?
  statement
  scope
  assumptions[]
  predicted_observations[]
  discriminating_predictions[]
  falsification_conditions[]
  competing_explanations[]
  change_reason_codes[]
  changed_because_refs[]
  revision
  fingerprint
```

A changed scientific formulation creates a new revision. It does not silently rewrite the previous statement.

### 3.3 HypothesisVerificationPlan

```text
HypothesisVerificationPlan/1.0
  hypothesis_revision_id
  questions[]
  required_observations[]
  discriminating_tests[]
  methods[]
  evidence_requirements[]
  alternative_hypothesis_refs[]
  stop_conditions[]
  research_challenge_refs[]
  budgets
```

The key field is `discriminating_tests`: the system should prefer work that distinguishes alternatives rather than merely collecting more support for the favored explanation.

### 3.4 HypothesisEvidenceLink

```text
HypothesisEvidenceLink/1.0
  hypothesis_revision_id
  evidence_ref
  source_ref
  relation
    SUPPORTS
    LIMITS
    COUNTERS
    CONDITIONS
    FAILS_TO_DISCRIMINATE
  scope
  independence_group?
  digest_ref?
  assessment_refs[]
```

This is a hypothesis-specific projection over canonical Evidence/Source objects. It does not duplicate evidence storage.

### 3.5 EvidenceDigest

A concise source digest should be derived from an exact canonical locator:

```text
EvidenceSpan / exact locator
        ↓
EvidenceDigest
  what this span directly supports
  what it does not support
  conditions/scope
  method/population/material/system
  important caveat
        ↓
HypothesisEvidenceLink
```

The digest is for inspection and routing. It must preserve the exact underlying EvidenceSpan/Source references so a user can always open the original material.

### 3.6 HypothesisAssessment

Avoid a single confidence scalar.

Suggested axes:

```text
HypothesisAssessment
  evidential_support
  contradictory_evidence
  method_adequacy
  scope_validity
  assumption_status
  alternative_explanations
  evidence_independence
  replication_status
  uncertainty_profile
  unresolved_research_debt[]
```

A convenient operational projection may expose states such as:

```text
PROPOSED
UNDER_TEST
PARTIALLY_SUPPORTED
SUPPORTED_WITH_LIMITS
CONTESTED
REVISED
REJECTED
OPEN
```

These states are summaries of multidimensional assessment, not replacements for it.

## 4. Model prior may create a hypothesis but never evidence

L3B already distinguishes `MODEL_PRIOR` from disclosed evidence and visible derivation. Extend the same rule to hypothesis formation:

```text
MODEL_PRIOR
  → HypothesisProposal allowed
  → Search/ResearchChallenge allowed
  → Evidence status forbidden
```

Example:

```text
model prior:
  "residual stress could produce this peak/lattice shift"

allowed result:
  HYPOTHESIS_PROPOSAL
  + discriminating test request

forbidden result:
  "therefore residual stress is demonstrated"
```

A model prediction becomes scientifically useful when it creates a testable branch, not when the model cites its own training distribution as evidence.

## 5. Verification iteration

One iteration should be a first-class historical unit rather than an invisible loop counter.

Candidate:

```text
HypothesisVerificationIteration
  iteration_id
  hypothesis_revision_id
  verification_plan_id
  started_from_refs[]
  research_challenge_refs[]
  acquired_evidence_refs[]
  acquired_derivation_refs[]
  review_case_refs[]
  resulting_assessment_id
  stop_reason
  next_revision_id?
```

This allows replay of:

```text
H0.r1
  → iteration 1
  → source A + calculation C
  → METHOD BLOCKING
  → H0.r2 qualified
  → iteration 2
  → measurement M
  → competing explanation H1 created
```

## 6. Hypothesis revision semantics

Do not force binary confirm/refute.

Possible transitions:

```text
RETAIN
  wording/scope unchanged; evidence state changes

QUALIFY
  hypothesis remains but scope/assumptions become narrower

REVISE
  explanatory statement materially changes

SPLIT
  one hypothesis contained two separable mechanisms

REJECT
  discriminating evidence conflicts with essential prediction

OPEN
  current evidence cannot distinguish alternatives
```

Every material revision records:

- parent revision;
- triggering evidence/argument/research refs;
- changed fields;
- reason codes;
- unresolved competing explanations.

## 7. Competing hypotheses are peers, not negative labels

A good Researcher must be able to hold several explanatory candidates simultaneously:

```text
H1 composition change
H2 residual stress
H3 phase-mixture / peak-overlap artifact
```

The system should ask:

```text
what observation distinguishes H1 from H2?
what method distinguishes H2 from H3?
which evidence is compatible with all three and therefore non-discriminating?
```

Do not convert "supports H1" into "refutes H2" unless the evidence is actually discriminating.

Future relation vocabulary may include:

```text
COMPETES_WITH
NESTED_IN
SPECIALIZES
MUTUALLY_COMPATIBLE
DISTINGUISHED_BY
```

These are hypothesis-case relations, not automatic Claim truth edges.

## 8. Evidence quantity is not evidence independence

Three papers may repeat one primary experiment, dataset or citation chain. Treating them as three independent confirmations would be numerically tidy and scientifically silly.

Future evidence support must expose lineage groups such as:

```text
EVD-A <- source paper 1 <- dataset X
EVD-B <- review paper   <- cites paper 1
EVD-C <- article 3      <- reuses dataset X
```

All three may belong to one evidence-independence group.

This is a future dependency for hypothesis assessment and joins. It belongs with provenance/traceability, not with free-form LLM confidence.

## 9. Relationship to ClaimReviewCase and multidisciplinary branches

One canonical `CLM-*` remains the root identity.

A hypothesis or Claim may require independent disciplinary review facets:

```text
CLM-X / HYP-X
└── ClaimReviewCase
    ├── F1 crystallography
    │   └── Q/A + ARG branch
    ├── F2 kinetics/causality
    │   └── Q/A + ARG branch
    └── F3 measurement/statistics
        └── Q/A + ARG branch
```

Each branch must preserve:

```text
root_claim_id
hypothesis_case_id?
hypothesis_revision_id?
review_case_id
facet_id
branch_key
AssessmentNeed lineage
DDC/DQC/ResponseAssignment lineage
RPB/TEX/PER lineage
IQT/ARG lineage
```

Branches are independent in dialogue state but belong to one review block.

## 10. Cross-facet synergy and conflict

The future join must preserve both conflict and synergy.

Example synergy:

```text
F1 XRD branch
  establishes phase assignment
        ↓ REQUIRES / ENABLES
F2 kinetic branch
  can now interpret transformation rate
```

Example invalidation dependency:

```text
F3 measurement branch
  uncertainty too large
        ↓ UNDERCUTS PREREQUISITE
F2 causal branch
  can no longer close its inference
```

Therefore `ClaimReviewJoinProjection` should compute coverage/dependency readiness, not vote.

## 11. ResearchChallenge is the main iteration bridge

When dialogue discovers missing evidence:

```text
ARG / EmergentIssue
      ↓
Gap
      ↓
ResearchChallenge
      ↓
ResearchDOM local branch
      ↓
search / measurement / computation / inspection
      ↓
new canonical evidence/derivation
      ↓
resume exact review/hypothesis branch
```

Do not create a second "hypothesis search loop" scheduler. Reuse the existing ResearchChallenge/ResearchDOM/Job runtime.

## 12. Writer and Coder roles

### Writer

Writer may help with:

- decomposing a linguistically composite hypothesis into candidate facets;
- semantic round-trip comparison between revisions;
- detecting modality/scope/causality changes;
- producing human-readable EvidenceDigest summaries.

Writer output remains proposal-only for canonical hypothesis identity/revision/admission.

### Coder

Coder may execute discriminating calculations, simulations or numerical experiments through typed compute contracts.

Coder output becomes Derivation/Evidence only after the existing admission/validation path. "The script ran" is not equivalent to "the hypothesis is supported".

## 13. Stop and continuation rules

A hypothesis cycle should continue only while new information can reasonably change the assessment.

Potential deterministic stop reasons:

```text
DISCRIMINATING_EVIDENCE_OBTAINED
ESSENTIAL_PREDICTION_FAILED
SCOPE_QUALIFICATION_STABLE
NO_NEW_HIGH_QUALITY_EVIDENCE
ALTERNATIVES_NOT_DISTINGUISHABLE
METHOD_CAPABILITY_MISSING
BUDGET_EXHAUSTED
REPLICATION_REQUIRED
HUMAN_EXPERT_REQUIRED
```

No-progress must use state change, not token/message count.

## 14. Virtual E2E suite before implementation

At minimum test these cases before coding the canonical hypothesis layer:

1. hypothesis receives direct independent support;
2. one source supports and another contradicts;
3. several sources all derive from one primary dataset;
4. multiple papers repeat the same methodological error;
5. MODEL_PRIOR proposes a useful hypothesis but no source can be located;
6. evidence supports the hypothesis only under narrower scope;
7. a new experiment invalidates one assumption but not the full hypothesis;
8. multidisciplinary review: two facets resolve and one remains blocking;
9. one facet supplies a prerequisite for another (synergy);
10. one facet invalidates a prerequisite used by another;
11. a new alternative hypothesis appears during Q/A;
12. evidence is compatible with several alternatives and cannot discriminate;
13. revised hypothesis is a qualification rather than a new unrelated hypothesis;
14. hypothesis splits into two mechanisms;
15. source is later invalidated and affected hypothesis revisions become stale/reopened;
16. returned research resumes the exact hypothesis/review branch;
17. a persuasive specialist answer is grounded only in MODEL_PRIOR and cannot close the case;
18. Advocate rationalizes a favored hypothesis without evidence and is forced to REQUEST_EVIDENCE;
19. human expert assertion proposes a new test but remains independently checkable;
20. evidence digest is misleading while the underlying EvidenceSpan shows a scope caveat; round-trip validation must catch the mismatch.

## 15. Implementation blocks

Suggested future sequence:

```text
H0  virtual E2E + contract design
H1  HypothesisCase / HypothesisRevision identity and history
H2  VerificationPlan + iteration ledger
H3  HypothesisEvidenceLink + EvidenceDigest projection
H4  competing-hypothesis relation graph
H5  multidimensional HypothesisAssessment
H6  ClaimReviewCase linkage + facet fork/join
H7  evidence independence/dependency lineage
H8  live semantic calibration and human-expert integration
```

Do not implement H6/H7 by an LLM-only join. These layers affect scientific auditability and must be reducer/policy owned.

## 16. Relationship to existing technical debt

- TD-038: cross-layer traceability becomes critical for HYP revision/evidence/iteration lineage.
- TD-042: live semantic observer calibration informs when dialogue generates a real new hypothesis/issue.
- TD-044: Writer proposal bridge may provide semantic facet/equivalence decomposition.
- TD-046: response ownership determines who answers a facet-level hypothesis question.
- TD-047: multidisciplinary ClaimReviewCase provides the fork/join envelope.
- New TD-048: canonical HypothesisCase/revision/verification lifecycle is not implemented.
- New TD-049: evidence independence/dependency groups are not modeled for support aggregation.
- New TD-050: claim/hypothesis-specific EvidenceDigest + support/limit/counter link projection is not first-class.

## 17. Non-goals

- no scalar "hypothesis confidence" as epistemic authority;
- no source-count voting;
- no automatic confirmation from role consensus;
- no MODEL_PRIOR as evidence;
- no destructive rewriting of prior hypothesis versions;
- no separate scheduler for hypothesis loops;
- no automatic multidisciplinary join before dependencies/conflicts are explicit;
- no Writer/Advocate/provider direct mutation of hypothesis or Claim truth.
