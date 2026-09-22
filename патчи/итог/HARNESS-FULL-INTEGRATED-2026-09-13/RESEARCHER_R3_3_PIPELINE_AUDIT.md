# Researcher R3.3 full pipeline audit

Date: 2026-09-13
Status: IMPLEMENTED / EXERCISED

## Scope

This audit checks the behavior of the existing Researcher architecture after inserting relation assessment between explicit semantic linking and reasoning/dependency use.

Pipeline exercised:

`TASK execution -> R3.1 admission -> R3.2 explicit GraphEdge -> R3.3 RelationAssessment -> R2.3.3 relation lifecycle -> strict provenance dependencies -> service artifact`.

## Authority invariants observed

- `TaskExecutionResult` is not knowledge.
- admitted Claim/Evidence objects remain separate from relation proposals.
- `GraphEdge(SUPPORTS)` is a declared canonical relation, not a support verdict.
- `RelationAssessment(ACCEPTED)` makes the edge eligible for relation-level reasoning but does not set `ClaimStatus.SUPPORTED`.
- rejected relation invalidates only the EDG relation; endpoint Claim/Evidence entities are not mutated.

## Three-way fixture

Three SUPPORTS edges were admitted from one completed TASK:

1. `scope=MATCH`, `method=MATCH`, `evidence=ADEQUATE` -> `ACCEPTED / ELIGIBLE / ACTIVE`.
2. same relation with unknown evidence quality -> `INCONCLUSIVE / BLOCKED / ACTIVE`.
3. disjoint scope -> `REJECTED / BLOCKED`, then relation lifecycle projects `ACTIVE -> INVALIDATED`.

Strict dependency compilation produced only the first EDG->CLM semantic dependency. All three Claims remained OPEN.

Representative artifact: `artifacts/researcher_r3_3/r3_3_full_pipeline_demo.json`.

## What surfaced

### 1. Strict reasoning is currently opt-in

`build_knowledge_dependencies()` preserves backward compatibility unless `require_relation_assessment=True` is supplied. R3.3-aware reasoning is correct, but a legacy caller can still compile active EDG relations without RAS. This is TD-029 and must be removed before relation assessment can be called a mandatory runtime gate.

### 2. Lifecycle write path is split

`RelationAssessment(REJECTED)` can deterministically produce an R2.3.3 `EDGE_STATE_CHANGED` transition to INVALIDATED. The R0 dry-run ClaimRegistry only owns admission and has no update command for revised EDG state. The event/reducer contract is correct, but one canonical persistence/application path is still missing. This is TD-030 and overlaps operationally with TD-022.

### 3. Blocked relation has no automatic research feedback yet

`INCONCLUSIVE` correctly blocks semantic use, but there is no reducer yet that converts a blocked relation assessment into a `Gap -> ResearchChallenge -> CHALLENGE subtree`. This is TD-031. The system is fail-closed, but not yet self-healing at relation level.

### 4. Kind-specific epistemic validators are asymmetric

SUPPORTS/CONTRADICTS have scope/directness/method/evidence checks. QUANTIFIES has only L1 scope/method/evidence policy. DERIVED_FROM intentionally returns INCONCLUSIVE because reproducibility and assumption contracts are not wired. This is TD-032.

### 5. Artifact observability was incomplete and is now repaired

Before the audit, service artifacts exposed EDG lifecycle but not relation assessment. R3.3 now adds a separate `relation_assessments` section. It intentionally does not rewrite Claim state or `graph_edges.state`.

### 6. Claim-level release remains downstream

The minimal service artifact still has coarse fixture-oriented writer context. It must not be interpreted as a scientific claim verdict. Claim evidence aggregation / Tribunal / Writer release gates remain later stages.

## Regression result

R3.3 targeted 15/15 and selected R1->R3.3 117/117 pass. Full Researcher is 467 total / 463 PASS with only the four known TD-015 Guard/LocalCorpus baseline failures and TD-020 SQLite ResourceWarnings. No new full-suite regression class was introduced.

## Recommended next boundary

Do not jump directly into Tribunal role orchestration yet. First close the relation feedback loop:

`INCONCLUSIVE/REJECTED RAS -> typed relation Gap/Challenge -> local planning decomposition`, while making strict assessed-relation use mandatory in the R3 reasoning path.

This can be a small R3.4 integration boundary before the larger R4 Tribunal composition phase.
