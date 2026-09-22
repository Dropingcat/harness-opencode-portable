# Researcher R3.4 Control-loop Closure Architecture

Status: IMPLEMENTED / EXERCISED (L1)  
Boundary: closes the base R3 loop before R4 Tribunal composition.

## 1. Purpose

R3.3 could identify a semantic relation that was `INCONCLUSIVE/BLOCKED`, exclude it from strict reasoning, and invalidate a rejected relation. It did not yet ensure that uncertainty produced new bounded work, that new R3 reasoning could not accidentally use an unassessed edge, or that a lifecycle transition became the canonical registry state.

R3.4 closes those three control-plane gaps.

```text
RelationAssessment
  ├─ ACCEPTED/QUALIFIED -> strict reasoning eligible
  ├─ INCONCLUSIVE/BLOCKED -> Gap -> ResearchChallenge -> CHALLENGE -> PlanningDialectic -> TASK
  └─ REJECTED -> GraphEdge lifecycle reducer -> canonical registry update
```

## 2. New blocks

### StrictReasoningFacade
`strict_reasoning.build_strict_reasoning_dependencies()` is the R3 reasoning entry point. It always calls the provenance compiler with `require_relation_assessment=True`. The lower-level compatibility API remains available for R2/legacy fixtures only.

### RelationFeedbackProjector
`relation_feedback.py` converts only a current `INCONCLUSIVE + BLOCKED` `RelationAssessment` into a canonical blocking `Gap`, then uses the existing R2 `challenge_from_gap()` and `materialize_challenge_card()` path. No second challenge planner exists.

The assessment ID is the idempotency key for this projection. Reusing the same assessment to create a second challenge is rejected.

### RelationFeedbackRepository
The newly created `Gap` and `ResearchChallenge` are persisted atomically through the existing SQLite/UoW substrate. This avoids a durable challenge whose `source_entity_id` existed only in memory.

### CanonicalEdgeUpdate
`InMemoryClaimRegistry.update_graph_edge()` is the canonical L1 write boundary for a revised `GraphEdge` produced by the relation lifecycle reducer. It optimistic-concurrency checks the current revision, forbids endpoint/kind mutation, persists the supplied `EDGE_STATE_CHANGED` event, updates the canonical state and creates a snapshot.

## 3. Authority boundaries

- LLM/specialist may propose assessment signals or planning decomposition.
- `assess_relation()` owns deterministic L1 assessment classification.
- `RelationFeedbackProjector` owns deterministic creation of a relation Gap/challenge request.
- Existing PlanningDialectic owns semantic decomposition of the challenge into executable work.
- `transition_relation_state()` owns transition legality.
- ClaimRegistry owns canonical edge mutation/persistence.
- Claim truth remains separate. No R3.4 path changes `ClaimStatus` merely because an edge is accepted, blocked, or invalidated.

## 4. Stop and loop behavior

R3.4 does not recursively create work from every non-success state.

- `ACCEPTED/QUALIFIED`: no feedback branch.
- `INCONCLUSIVE/BLOCKED`: exactly one challenge per assessment.
- `REJECTED`: lifecycle invalidation only; no automatic research branch at L1.
- Challenge subtree must pass the existing local PlanningGate and terminate in executable TASK/DELEGATION leaves.
- Reassessment must be produced by a later execution/evidence revision; the original assessment cannot create a second branch.

This prevents `assessment -> challenge -> same assessment -> challenge ...` loops.

## 5. Current limitations

1. The R3 strict facade is new; low-level R2 compatibility calls still exist and must remain explicitly legacy.
2. Relation-generated Gap persistence is implemented, but there is still no single general-purpose repository abstraction for every R1 Gap/Conflict producer.
3. `REJECTED` does not automatically create a challenge; policy may later choose a bounded contradiction investigation for selected relation kinds.
4. DERIVED_FROM and richer QUANTIFIES assessment remain limited by TD-032.
5. Tribunal aggregation/quorum is not present; R3.3 deterministic latest-assessment selection remains L1 policy.
6. Restore verification is still manual (TD-023), now observed twice.

## 6. Complexity ladder

L1 (implemented): strict R3 facade, one-assessment-one-challenge feedback, canonical edge update, atomic Gap+Challenge projection.

L2: shared knowledge-issue repository, typed policies deciding which REJECTED relations warrant research, richer measurement/derivation validators.

L3: Tribunal-produced multi-opinion relation assessments with deterministic aggregation/quorum and explicit disagreement objects.

L4: justification sets/nogoods and incremental TMS/ATMS-style retraction/reinstatement over relation assessments and challenge outcomes.

## 7. Acceptance evidence

- R3.4 targeted tests: 10/10 PASS.
- Selected R1→R3.4 regression: 117/117 PASS.
- Full Researcher: 477 total, 473 PASS; same four TD-015 Guard/LocalCorpus failures only.
- Policy compilers unchanged; compileall and `git diff --check` pass.
