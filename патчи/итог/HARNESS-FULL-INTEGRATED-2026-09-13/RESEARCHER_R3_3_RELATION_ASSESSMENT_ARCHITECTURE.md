# Researcher R3.3: canonical relation assessment

Status: IMPLEMENTED / EXERCISED (L1)
Boundary: after R3.2 explicit semantic linking, before Tribunal / claim-level evidence verdicts.

## 1. Block identity

- Owner: Researcher
- Primary implementation: `scripts/researcher/researcher_core/relation_assessment.py`
- Existing authorities reused: `GraphEdge`, `GraphEdgeState`, `EdgeValidator`, `ScopeValidator`, `ResearchTraceLink`, `build_knowledge_dependencies()`
- New public contracts: `RelationAssessmentProposal/1.0`, `RelationAssessment/1.0`
- No new canonical graph registry is introduced.

## 2. Purpose

R3.3 separates a declared semantic relation from an assessed relation.

R3.2 proves only that an adapter explicitly declared a compatible relation and that the canonical graph admitted it. R3.3 decides whether that relation is currently eligible for reasoning, qualified, inconclusive, or rejected.

It explicitly does not decide Claim truth, close Gaps/Conflicts, or replace Tribunal review.

Core distinction:

`GraphEdge(kind) != RelationAssessment(verdict) != Claim evidence verdict`.

## 3. Inputs / outputs

Input:
- canonical `GraphEdge`;
- expected edge revision;
- typed assessment signals such as scope match, directness, method match and evidence quality;
- explicit supporting references and rationale.

Output:
- immutable `RelationAssessment` artifact;
- `ResearchTraceLink(VALIDATED -> EDG)`;
- optional relation lifecycle transition proposal for rejected relations;
- dependency-compiler eligibility signal.

No endpoint Claim/Quantity/Evidence state is mutated by assessment.

## 4. Authority boundary

- `RelationAssessmentProposal` is a work-plane proposal.
- deterministic policy compiles proposal + canonical edge into `RelationAssessment`.
- `GraphEdge` remains canonical relation authority.
- relation lifecycle reducer alone may transition `ACTIVE/STALE/SUPERSEDED/INVALIDATED`.
- Claim evidence/epistemic state remains owned by later claim-assessment/Tribunal logic.

A model or specialist may propose signals; code owns verdict mapping.

## 5. Links to surrounding architecture

Upstream:
`TASK -> TaskExecutionResult -> R3.1 admission -> R3.2 GraphEdge`.

R3.3:
`GraphEdge + typed signals -> RelationAssessment -> reasoning eligibility`.

Downstream:
- strict provenance dependency compilation consumes only eligible/qualified assessed relations;
- rejected relation may be invalidated through R2.3.3 lifecycle;
- Tribunal may later attach arguments/challenges to the same EDG and assessment lineage;
- Claim remains OPEN until separate evidence/claim assessment.

## 6. Current implementation limits

L1 intentionally uses a small deterministic policy:
- SUPPORTS/CONTRADICTS use scope, directness, method match and evidence quality;
- QUANTIFIES uses scope/method/evidence quality but no full measurement-model validator yet;
- DERIVED_FROM remains inconclusive until reproducibility/assumption contracts are integrated.
- no probabilistic confidence score;
- no cross-assessment aggregation or reviewer quorum;
- no Tribunal arguments in L1;
- no automatic extraction of method/scope signals from prose.

## 7. Failure modes / fail-closed behavior

Reject or block assessment on:
- stale expected edge revision;
- non-ACTIVE edge;
- assessment targeting the wrong EDG;
- malformed or unsupported signal vocabulary;
- missing mandatory support-relation signals;
- lineage/run mismatch.

`INCONCLUSIVE` is not coerced into PASS. In strict reasoning mode unassessed or inconclusive relations are excluded from active semantic support.

## 8. Complexity ladder

### L1: deterministic typed assessment
Current block. Closed vocabularies, deterministic verdict mapping, strict dependency eligibility.

### L2: specialized kind-specific validators
Measurement semantics for QUANTIFIES; reproducibility/assumption checks for DERIVED_FROM; method-specific support policies.

### L3: Tribunal arguments and challenge loop
Per-edge arguments, skeptic/methodologist review, Q/A refinement, explicit unresolved relation challenges.

### L4: calibrated scoring / history
Use historical assessment outcomes to rank reviewers/tools and calibrate confidence, without replacing hard gates.

### L5: justification sets / TMS
Multiple independent justifications, nogoods, relation-level quorum and selective invalidation.

## 9. Tests / acceptance gates

Required:
- accepted SUPPORTS relation remains ACTIVE and Claim remains OPEN;
- partial scope produces QUALIFIED;
- unknown/weak signals do not become ACCEPTED;
- disjoint scope / insufficient evidence rejects relation;
- stale revision fails closed;
- stale/terminal edge cannot be assessed as current;
- QUANTIFIES policy exercised;
- DERIVED_FROM remains explicit INCONCLUSIVE at L1;
- VALIDATED trace emitted to EDG;
- strict dependency compiler excludes unassessed/inconclusive/rejected edges;
- full execution->admission->linking->assessment fixture preserves all authority boundaries.

## 10. Tech debt links

Assigned after pipeline audit:
- TD-029: strict relation assessment is not yet mandatory in all live dependency-compilation paths.
- TD-030: rejected relation lifecycle projection is not yet committed through one unified canonical graph-state reducer/repository path.
- TD-031: INCONCLUSIVE relation does not yet generate a Gap/ResearchChallenge feedback branch automatically.
- TD-032: specialized DERIVED_FROM/QUANTIFIES validators and automatic typed signal extraction remain incomplete.

## 11. Legacy lineage

Preserves legacy Researcher concept that a relation/claim should be challenged by role-specific review rather than accepted from generation alone. Does not carry forward legacy free-form verdict override or persona authority.

## Recursive object-processing ownership

R3.3 owns:
`GraphEdge -> assessment profile -> deterministic validators -> RelationAssessment -> reasoning eligibility / lifecycle projection`.


## 12. Full-pipeline audit findings

Observed end-to-end fixture:

`execution -> admission -> explicit linking -> relation assessment -> lifecycle projection -> strict dependency compile -> service artifact`.

Results:
- ACCEPTED ACTIVE SUPPORTS is eligible and appears as EDG->CLM semantic dependency.
- INCONCLUSIVE ACTIVE SUPPORTS is preserved historically but excluded from strict reasoning.
- REJECTED SUPPORTS can transition to INVALIDATED without mutating Claim/Evidence endpoints.
- Claim status remains OPEN in all three cases; relation assessment is not claim truth.
- service artifact now exposes `relation_assessments` separately from `graph_edges`.

Architectural gaps surfaced by the audit:
1. `require_relation_assessment=True` is explicit, not yet globally wired into a live runtime path (TD-029).
2. Relation lifecycle transition is a canonical reducer/event contract, but the R0 dry-run ClaimRegistry has no update-command path for applying revised EDG state; fixtures must project the updated edge state separately (TD-030, related to TD-022).
3. INCONCLUSIVE/BLOCKED relation does not automatically become a Gap/ResearchChallenge; this feedback loop remains a later block (TD-031).
4. DERIVED_FROM is intentionally INCONCLUSIVE at L1; QUANTIFIES has only a basic scope/method/evidence policy (TD-032).
5. Minimal service artifact writer_context is not epistemic release authority; Claim-level eligibility remains a later claim assessment/Writer release concern.
