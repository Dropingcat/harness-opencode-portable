# RESEARCHER R2.3 — invalidation, dependency impact and historical reopen

Status: IMPLEMENTED FIRST SLICE (L0/L1), 2026-09-12. Architecture was fixed before implementation and updated after tests.

## 1. Purpose

R2.3 closes the negative feedback loop of Researcher knowledge. R2.0-R2.2 can create a knowledge problem, decompose it, work on it and resolve/block/reopen it manually. R2.3 must make a resolved branch react correctly when the source/evidence/relation used by that resolution becomes stale.

Target flow:

`Source/EvidenceSpan changed -> ImpactAssessment -> dependent resolution stale -> Gap/Conflict re-opened if necessary -> existing ResearchChallenge REOPENED -> new historical iteration in the same CHALLENGE branch`.

## 2. Inputs

- source version change / evidence-span invalidation event;
- existing `ResearchTraceLink` / knowledge edges;
- resolution assessments from R2.2;
- current `ResearchChallenge` revision/state;
- current CHALLENGE card revision/state.

## 3. Outputs

Planned new/extended artifacts:

- `DependencyImpactAssessment/1.0`;
- stale markers for selected knowledge relations/assessments;
- resolution invalidation event;
- new challenge iteration record;
- revision-checked transitions for Gap/Conflict, ResearchChallenge and CHALLENGE card.

## 4. Authority boundary

No source-update handler may mutate claim/gap/conflict/challenge state directly.

Authority flow:

`change event -> impact computation -> reducer -> state transitions/events`.

`DependencyImpactAssessment` is evidence for a transition, not the transition itself.

## 5. Dependency model

R2.3 starts with three dependency strengths:

- `HARD`: target cannot retain the current assessment if source relation is invalidated;
- `SOFT`: target may remain usable but requires revalidation/stale annotation;
- `CONTEXTUAL`: change matters only if scope/method context overlaps.

Initial relations in scope:

- EvidenceSpan -> Claim assessment;
- Claim/Assessment -> Argument/Resolution;
- Evidence/Claim -> `SUPPORTS`, `CONTRADICTS`, `RESOLVES` relations;
- ResolutionAssessment -> Gap/Conflict state;
- Gap/Conflict -> ResearchChallenge.

R2.3 intentionally does not attempt a universal truth-maintenance system in the first iteration.

## 6. Selective reopen policy

A changed evidence item MUST NOT automatically reopen an entire branch.

Examples:

- one of several redundant evidence spans stale -> `SUPPORTED_WITH_STALE_EVIDENCE`, challenge may stay resolved;
- sole critical evidence stale -> resolution invalidated, challenge reopened;
- only a causal relation loses support while both endpoint claims remain valid -> stale the relation, not both claims;
- scope metadata changes -> `CONTEXTUAL` impact and targeted reassessment.

## 7. Historical iteration semantics

Reopen does not create a new independent challenge.

Example:

`CH-17 / iteration 1 -> RESOLVED`

later:

`source update -> iteration 1 stale -> CH-17 iteration 2 -> REOPENED/ACTIVE`.

Old assessment/evidence remain immutable historical records.

## 8. Failure / fail-closed behavior

- stale expected challenge revision -> reject transition;
- dependency graph incomplete -> mark impact `INCOMPLETE`, do not auto-close/reopen beyond safe subset;
- ambiguous dependency strength -> default to revalidation request, not destructive invalidation;
- missing old evidence artifact -> preserve previous state as historical but mark provenance gap;
- cycle in dependency traversal -> stop at visited-set/budget and emit diagnostic gap;
- excessive fan-out -> stop at configured node budget and produce `IMPACT_SCOPE_TRUNCATED`.

## 9. Complexity ladder

### L0 — deterministic direct dependencies

Trace exact evidence/source -> assessment -> gap/conflict/challenge links already recorded. Reopen only on exact HARD dependencies.

### L1 — typed relation strengths

Add HARD/SOFT/CONTEXTUAL semantics and selective stale/reopen rules.

### L2 — relation-level truth maintenance

Version `SUPPORTS/CONTRADICTS/RESOLVES` edges and invalidate relations independently from endpoint entities.

### L3 — incremental TMS/ATMS-like propagation

Track justifications/nogoods and recompute only affected belief contexts. Legacy `36-master-plan.md` explicitly pointed toward TMS/ATMS; this is a future option, not an R2.3 requirement.

### L4 — learned impact/routing heuristics

Use accumulated histories to prioritize which stale branches need immediate reassessment. Never let learned ranking replace deterministic dependency ownership.

## 10. Current limitations expected after first R2.3 slice

- dependency strengths will initially be explicit/hand-authored, not inferred globally;
- cross-document semantic identity may still be incomplete;
- old legacy evidence edges may lack enough provenance for precise impact calculation;
- no automatic Tribunal rerun yet: R2.3 reopens/plans work, later stages execute Tribunal/Search;
- large cyclic knowledge graphs will use bounded traversal, not full ATMS reasoning.

## 11. Acceptance gates

Minimum E2E fixtures:

1. redundant evidence changes -> no full reopen;
2. sole evidence changes -> challenge reopens;
3. relation-only invalidation -> endpoint claims remain intact;
4. resolved scope-mismatch conflict source changes -> targeted conflict reassessment;
5. second stale event with old expected revision -> rejected;
6. replay reconstructs both historical iterations;
7. no unrelated ResearchDOM branch changes.

## 12. Legacy lineage

Restores and strengthens concepts from `36-master-plan.md` local escalation/cutter/domain-map sections and the staged architecture in `38-implementation-plan.md`.

Difference: legacy logic mainly escalated unresolved claims forward; R2.3 additionally supports backwards invalidation of previously resolved knowledge while retaining complete history.

## 13. Implemented first-slice block card

### Block identity

- owner: `Researcher` peer orchestrator;
- implementation: `scripts/researcher/researcher_core/invalidation.py`;
- tests: `tests/researcher/test_invalidation.py`;
- public contracts: `KnowledgeDependency/1.0`, `DependencyImpactAssessment/1.0`, `ChallengeIteration/1.0`;
- ID namespaces added: `KDP`, `DIA`, `RIT`.

### Actual authority boundary

`KnowledgeDependency` and `DependencyImpactAssessment` are immutable evidence about dependency/impact. They do not mutate knowledge state. `reopen_from_impact()` is the reducer boundary for the first slice and only mutates a previously `RESOLVED` challenge when impact is complete and `REOPEN_REQUIRED`.

A stale/redundant source may yield `REVALIDATION_REQUIRED` without changing Gap/Conflict/Challenge state. Relation-only invalidation may stale an `EDG` relation without invalidating endpoint claims.

### Current implementation limits

- Dependencies are explicit records supplied by upstream code. Automatic extraction from all existing `ResearchTraceLink`/`GraphEdge`/Writer source-dependency structures is not implemented yet.
- SourceCatalog changes are not yet wired directly into R2.3; the first slice accepts already-normalized changed entity IDs.
- HARD redundancy is expressed by `group_key + min_active_in_group`; this is deterministic but intentionally simple.
- CONTEXTUAL dependencies currently use explicit `metadata.scope_overlap`; no semantic scope comparator is invoked here.
- Traversal is bounded by `max_nodes`; fan-out truncation returns `INCOMPLETE` and cannot mutate challenge state.
- Relation-level invalidation is represented as `stale_relation_ids`; versioned `GraphEdge` state is a later block.
- The first slice reopens a historical branch but does not automatically execute Search/Tribunal after reopening.
- Persistence stores dependency/impact/iteration artifacts in the existing SQLite UoW, but there is no global dependency index yet.

### Failure / fail-closed behaviour verified

- stale current-resolution revision: reject;
- incomplete impact: reject state mutation;
- non-resolved challenge: reject automatic reopen;
- scope non-overlap: no impact;
- unrelated ResearchDOM branch: untouched;
- redundant evidence: revalidation only, no branch reopen.

### Complexity status

- L0 direct deterministic dependencies: implemented.
- L1 typed HARD/SOFT/CONTEXTUAL dependencies and selective reopen: implemented first slice.
- L2 versioned relation-level truth maintenance: only stale relation projection exists.
- L3 TMS/ATMS justification contexts: not implemented.
- L4 learned impact prioritisation: not implemented and must not replace deterministic ownership.

### Acceptance status

`tests/researcher/test_invalidation.py`: 7/7 PASS.

Combined planning/knowledge/challenge/invalidation selected suite after R2.3: 44/44 PASS. Full Researcher suite: 404 total, 400 PASS, same pre-existing 4 Guard/LocalCorpus failures tracked by TD-015.

### Tech debt

- TD-018: build canonical dependency records automatically from trace/graph provenance.
- TD-019: bridge `SourceCatalog` semantic changes and EvidenceSpan invalidation into R2.3 trigger objects.
- TD-020: remove SQLite ResourceWarnings visible in full Researcher regression.


## 14. R2.3.1 provenance-derived dependencies and SourceCatalog trigger

Status: IMPLEMENTED, 2026-09-12.

### Block identity

- implementation: `scripts/researcher/researcher_core/provenance_dependencies.py`;
- tests: `tests/researcher/test_provenance_dependencies.py`;
- contracts: `SourceIdentityBinding`, `SourceCatalogSemanticChange`, `ProvenanceDependencyBuild`;
- reuses R2.3 `KnowledgeDependency`, `DependencyImpactAssessment`, and `reopen_from_impact()`;
- does not introduce another knowledge graph or another state reducer.

### Inputs and deterministic mapping

The adapter compiles existing canonical provenance into R2.3 dependencies:

- `Source -> EvidenceSpan`: HARD containment dependency;
- `GraphEdge.source -> GraphEdge(EDG)`: HARD relation provenance;
- admitted `GraphEdge -> target`: typed HARD/SOFT dependency according to relation/attributes;
- `ChallengeResolutionAssessment.evidence_refs -> RRS`: HARD justification dependency with explicit quorum;
- `claim_refs -> RRS`: CONTEXTUAL dependency;
- `ResearchTraceLink(VALIDATED)` can reconstruct an `EVD/CLM -> RRS` dependency when the serialized assessment object is unavailable.

Duplicate semantic dependencies are collapsed deterministically so duplicate provenance records cannot accidentally alter quorum.

### SourceCatalog integration

Writer `SourceCatalog` remains the current shared-library version detector. Its public upsert result is normalized to `SourceCatalogSemanticChange`.

- `BYTE_ONLY` / unchanged changes produce no changed Researcher source IDs and cannot reopen a knowledge branch;
- `SEMANTIC` changes are resolved through an explicit `SourceIdentityBinding`;
- missing, ambiguous, or stale bindings fail closed;
- `reopen_from_source_catalog_change()` performs the orchestration sequence `catalog change -> impact -> existing R2.3 reducer`, preserving authority separation.

The adapter does not import Writer internals for semantic decisions; integration accepts the public SourceCatalog result shape. A real Writer `source_catalog.upsert()` integration test is included.

### Current limitations

- Writer catalog IDs are free strings while Researcher Source IDs are typed `SRC-*`; therefore `SourceIdentityBinding` is currently explicit.
- Binding persistence/catalog reconciliation is not yet centralized.
- Evidence-span semantic change independent of a whole-source change is not yet emitted as a first-class shared event.
- GraphEdge relation state is still reported through R2.3 `stale_relation_ids`; canonical versioned/stale GraphEdge state remains R2.3.3.
- Dependency strength defaults are deliberately conservative and explainable; semantic/learned dependency inference is out of scope.
- The adapter compiles a dependency view on demand; a durable global dependency index is not yet present.

### Complexity ladder after R2.3.1

- L1a: canonical provenance -> deterministic dependency compilation: implemented.
- L1b: Writer SourceCatalog semantic change -> Researcher impact/reopen trigger: implemented.
- L1c: shared canonical Source identity without bridge bindings: deferred.
- L2: first-class EvidenceSpan semantic-change events and versioned relation state: deferred.
- L3: durable incremental dependency index / TMS-like justification maintenance: future.

### Verified failure behaviour

- no catalog-to-SRC binding -> reject;
- multiple canonical SRC bindings for one catalog ID -> reject;
- catalog old SHA inconsistent with bound source version -> reject;
- BYTE_ONLY update -> `NO_IMPACT`;
- semantic sole-evidence source update -> exact existing challenge branch reopens;
- canonical resolution assessment takes precedence over duplicate trace-derived fallback dependency.

## 15. R2.3.3 canonical relation lifecycle

Status: IMPLEMENTED, 2026-09-12.

### Block identity

- implementation: `scripts/researcher/researcher_core/r0/graph.py`, `relation_lifecycle.py`;
- integration: `r0/projections.py`, `artifact_builder.py`, `provenance_dependencies.py`;
- tests: `tests/researcher/test_relation_lifecycle.py`, `tests/researcher/test_provenance_dependencies.py`;
- canonical relation contract: `GraphEdge` with versioned `GraphEdgeState`;
- event: `EDGE_STATE_CHANGED`.

### Purpose

R2.3.3 makes a semantic relation an information object with its own lifecycle. A source/evidence change may invalidate or stale the relation `SUPPORTS`, `CONTRADICTS`, `DEPENDS_ON`, etc. without declaring either endpoint entity false.

### Lifecycle

`ACTIVE -> STALE -> ACTIVE` after successful revalidation.

`STALE -> SUPERSEDED` when a newer relation replaces the old justification.

`ACTIVE|STALE -> INVALIDATED` after explicit deterministic rejection of the relation.

`SUPERSEDED` and `INVALIDATED` are terminal in the current slice.

### Authority boundary

`DependencyImpactAssessment.stale_relation_ids` is evidence that relation state should change. It does not mutate the graph.

`transition_relation_state()` / `project_stale_relations_from_impact()` are the deterministic relation reducer boundary. Endpoint Claims/Sources/EvidenceSpans are not mutated by relation lifecycle transitions.

Every transition:

- requires expected relation revision;
- increments `EntityMeta.revision`;
- emits `EDGE_STATE_CHANGED` with full replayable relation record;
- preserves the same EDG identity and original creation metadata.

### Persistence/replay

Event projection serializes relation state. Legacy `GraphEdge` records without a state field are read as `ACTIVE`, preserving backward compatibility.

Service artifacts now expose relation `state` and `revision` so stale graph semantics cannot disappear during rendering/export.

Current generic state/event persistence is sufficient for correctness. Dedicated efficient relation-history queries remain TD-022.

### Dependency integration

When canonical provenance is recompiled:

- `ACTIVE` GraphEdge emits ACTIVE `KnowledgeDependency` records;
- `STALE` GraphEdge emits STALE dependency records and therefore does not participate as current active justification;
- `SUPERSEDED` / `INVALIDATED` relations are excluded from active dependency compilation with explicit diagnostics.

This closes the previous gap where `stale_relation_ids` existed only in an impact report.

### Fail-closed behavior

- missing canonical EDG referenced by impact: reject projection by default;
- missing expected relation revision: reject;
- stale expected revision: reject;
- invalid state transition: reject;
- already STALE relation with matching revision: idempotent unchanged result;
- terminal relation states are not silently reactivated.

### Current limitations

- no dedicated SQLite latest-relation/history index yet (TD-022);
- relation revalidation is explicit, not yet automatically driven by Tribunal verdicts;
- relation supersession does not yet carry an explicit `superseded_by_edge_id` field;
- no justification-set/nogood contexts yet; this remains below TMS/ATMS complexity;
- edge confidence is still metadata, not a calibrated typed assessment;
- relation lifecycle currently covers canonical `GraphEdge`; higher-order Argument/Tribunal relations will reuse this pattern later.

### Complexity ladder after R2.3.3

- L0 exact entity dependencies: implemented;
- L1 HARD/SOFT/CONTEXTUAL selective invalidation: implemented;
- L2 versioned relation-level truth maintenance: implemented first slice;
- L2.1 dedicated persistent relation history/index + supersession links: next infrastructure option;
- L3 justification contexts / TMS-ATMS-like local recomputation: future;
- L4 learned prioritization of stale relation review: future and advisory only.

### Acceptance status

- legacy edge event records restore as ACTIVE;
- ACTIVE -> STALE is versioned and event-replayable;
- stale relation leaves endpoints unchanged;
- STALE -> ACTIVE revalidation works;
- STALE/ACTIVE -> INVALIDATED works under transition policy;
- provenance compiler treats STALE dependencies as stale and terminal relations as excluded;
- full Researcher regression returns only the four already tracked Guard/LocalCorpus baseline failures.
