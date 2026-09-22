# Future architecture — response ownership, Defender/Advocate arbitration and multidisciplinary Claim fork/join

Date: 2026-09-13
Status: future-growth architecture note; not an executable R4.4 L3 contract.

## 1. Why `answer_role_id` is necessary but insufficient

R4.4 L3 makes one bounded dialogue turn reproducible by separating:

```text
questioner role
!= addressed answer role
!= runtime provider
```

This prevents accidental self-dialogue and allows provider binding to target the intended semantic role. It does **not** yet decide the larger ownership problem:

- who is responsible for answering a particular aspect of a Claim;
- whether the original argument author, a facet specialist, or an Advocate should answer;
- how responsibility changes after a METHOD/CAUSAL/EVIDENCE challenge;
- how one multidisciplinary Claim splits into parallel review branches;
- how those branches rejoin without majority voting or loss of provenance.

The missing abstraction is therefore larger than `answer_role_id`.

## 2. Separate role, party and response function

Do not model every conversational function as a new permanent role.

Three concepts should remain orthogonal:

```text
Role
  semantic competence/perspective
  e.g. crystallographer, statistician, skeptic

Review party / ownership
  who currently owns responsibility for a facet/position

Response function
  what must be done in this turn
  EXPLAIN | DEFEND | QUALIFY | CONCEDE | REFER | REQUEST_EVIDENCE
```

### Advocate

Advocate remains a conditional adversarial role. Its job is to test whether an already challenged argument remains defensible from admitted support.

### Defender / respondent

`Defender` should not yet become a permanent role. A defense function may be performed by:

- the original facet owner;
- the original argument author;
- a more suitable admitted domain/method specialist;
- the conditional Advocate;
- later, a human expert.

The control plane should choose the responder through a typed assignment rather than infer it from prose or from the target ARG author.

Candidate future contract:

```text
ResponseAssignment/1.0
  case_id
  facet_id
  branch_key
  question_contract_id
  questioner_role_id
  addressed_role_id
  addressed_party_kind
  original_position_role_id
  response_mode
  advocate_activation_id?
  candidate_role_ids[]
  selected_role_id
  reason_codes[]
  policy_version/hash
```

A DQC should consume one admitted `ResponseAssignment`, not become the global ownership registry itself.

## 3. Suggested responder decision order

For one question:

```text
1. identify exact target surface
   ARG justification | emergent issue | method gap | evidence gap | cross-facet dependency

2. identify facet ownership
   which ReviewFacet and current position this target belongs to

3. derive response obligation
   EXPLAIN | DEFEND | QUALIFY | CONCEDE | REFER | REQUEST_EVIDENCE

4. derive eligible semantic roles

5. decide whether conditional Advocate is useful

6. provider binding selects a runtime executor only after semantic ownership is fixed
```

Fail closed when the target has no responsible admitted role. Do not silently route to a generic critic.

## 4. When should Advocate appear?

Working hypothesis, to be calibrated with live traces:

- evidence request or missing measurement -> normally return to facet owner / Researcher, not Advocate;
- method-specific undercut -> normally method/facet specialist answers first;
- factual/domain clarification -> domain facet owner answers;
- explicit attack on an already justified position -> Advocate may be activated;
- cross-facet contradiction -> neither side's Advocate owns integration; open an integration/reconciliation branch.

Advocate is therefore **not the default respondent**.

Possible later combined pattern:

```text
specialist respondent
    answers scientific content

Advocate
    tests whether the specialist's defended position survives the attack
```

This may create two sequential or parallel artifacts but must not duplicate the same authority.

## 5. Multidisciplinary Claim review case

One canonical Claim may require several disciplinary views without being destructively split into unrelated claims.

Candidate top-level object:

```text
ClaimReviewCase/1.0
  case_id
  root_claim_id
  root_claim_revision
  source ReviewWorkField / AssessmentNeed refs
  facets[]
  cross_facet_relations[]
  required_join_conditions[]
  state
```

A `ReviewFacet` is a review projection, not automatically a new canonical Claim:

```text
ReviewFacet
  facet_id
  root_claim_id
  proposition/span projection
  discipline_views[]
  method_views[]
  question_types[]
  AssessmentNeed refs[]
  required role families[]
  dependencies[]
  blocking
```

Possible example:

```text
CLM-1: "Treatment changes lattice state and thereby accelerates nitride formation."

facet F1: crystallographic interpretation
facet F2: kinetic/causal interpretation
facet F3: statistical/measurement adequacy
```

Each facet may produce its own independent argument branch:

```text
ClaimReviewCase CLM-1
  |
  +-- F1 crystallography -> branch DBR-A
  |
  +-- F2 causal/kinetics -> branch DBR-B
  |
  +-- F3 measurement/statistics -> branch DBR-C
```

Every branch retains `root_claim_id + case_id + facet_id + branch_key` so the Claim cannot get lost during review.

## 6. Cross-facet graph

The facet layer needs explicit relations such as:

```text
REQUIRES
CONDITIONS
SHARES_ASSUMPTION
SHARES_EVIDENCE
CONFLICTS_WITH
QUALIFIES
INTEGRATES_WITH
```

These are review-case relations, not KnowledgeGraph truth edges.

Example:

```text
F2 causal conclusion
REQUIRES
F1 structural interpretation
```

If F1 becomes BLOCKING, F2 cannot be joined as resolved even if its own local dialogue appears complete.

## 7. Join must not be voting

The future join object should be deterministic and coverage-oriented:

```text
ClaimReviewJoinProjection
  root_claim_id
  required_facets[]
  facet_states[]
  unresolved_facets[]
  cross_facet_conflicts[]
  integration_gaps[]
  blocking_dependencies[]
  readiness
  proposed_qualifications[]
```

Possible readiness semantics:

- READY_FOR_REDUCER
- QUALIFIED_READY
- BLOCKED
- CROSS_FACET_CONFLICT
- INCOMPLETE_COVERAGE
- NEEDS_INTEGRATION_REVIEW

No `2 of 3 experts agree => Claim true` rule.

The join layer does not mutate Claim truth. It produces a typed review projection for the existing assessment/reducer authority.

## 8. Integration specialist is conditional, not an aggregator

If branches disagree because they answer different aspects, code may join them directly.

If reconciliation itself requires semantic reasoning, create an **integration review branch** with an admitted specialist/profile chosen from the actual cross-facet conflict.

This role must receive:

- explicit facet outputs;
- exact conflict/dependency refs;
- bounded disclosure;
- no permission to overwrite branch findings.

This is different from the rejected legacy Aggregator that produced a final verdict from votes.

## 9. Relationship to Writer decomposition

Writer's claim/facet decomposition and round-trip validation can later help propose `ReviewFacet` boundaries, especially for linguistically composite Claims.

But:

```text
Writer facet proposal
!= canonical Claim split
!= review ownership decision
```

Researcher must admit facets against Claim scope, provenance and AssessmentNeeds.

This connects naturally to TD-044 and avoids building another semantic splitter.

## 10. Traceability target

A future trace should support:

```text
CLM
 -> ClaimReviewCase
 -> ReviewFacet
 -> TribunalComposition assignment
 -> DBR
 -> DDC
 -> DQC
 -> ResponseAssignment
 -> RPB
 -> TEX
 -> Job / Attempt
 -> PER
 -> IQT / ARG
 -> facet state
 -> ClaimReviewJoinProjection
 -> ClaimAssessment reducer input
```

At every point it should remain possible to answer:

- why this role was asked;
- which facet it represented;
- which exact question it answered;
- which provider actually executed it;
- what evidence it was allowed to see;
- which branch/facet the answer changed;
- why the overall Claim is still open/qualified/blocked.

This is a concrete future workload for TD-038 universal traceability.

## 11. E2E acceptance for the future block

Before considering this architecture implemented, require at least:

1. one Claim with three independent facets;
2. three different role families selected deterministically;
3. one facet resolves, one qualifies, one blocks;
4. no cross-branch history/budget leakage;
5. one explicit cross-facet dependency;
6. one cross-facet conflict creates an integration branch rather than a vote;
7. original Claim ID survives every artifact;
8. facet result cannot mutate Claim truth directly;
9. a missing facet owner fails closed;
10. unavailable runtime provider remains runtime failure, not facet OPEN;
11. conditional Advocate activates only on the intended branch;
12. final join projection exactly explains why the Claim is or is not reducer-ready.

## 12. Scope boundary for current R4.4 L3

Do **not** implement full ClaimReviewCase fork/join inside provider binding work.

Current L3 should finish:

```text
explicit questioner + answer role
provider/runtime binding
bounded live Q/A
runtime failure semantics
RPB/TEX/PER replay
second role family E2E
```

Response ownership and multidisciplinary fork/join are next-layer architecture/debt informed by live traces.
