# RESEARCHER-R1.1 Planning Runtime Review

Date: 2026-09-12
Scope: planning gate, durable ResearchDOM, event replay, first card-to-knowledge trace links.

## Boundary

R1.1 deliberately does **not** add search, tribunal logic, semantic claim verification, or peer delegation. It makes the R1 planning tree safe to execute and safe to connect to the knowledge layer in R2.

Implemented path:

`ResearchDOM -> PlanningGate -> SQLite snapshot/event persistence -> replay -> ResearchTraceLink`

## 1. PlanningGate

`research_planning_runtime.py` adds a deterministic gate that checks execution readiness rather than scientific truth.

Current checks:

- at least one `DIRECTION`;
- every authoritative leaf is executable (`TASK`/`DELEGATION` with capability/delegation target);
- duplicate sibling cards are rejected;
- maximum card count;
- maximum tree depth.

Limits are policy-backed through `config/research_policy.yaml`:

- `research.planning.max_cards = 80`;
- `research.planning.max_depth = 8`.

These are explicitly heuristic policy values, not hidden constants. Scientific coverage remains the responsibility of PlanningDialectic and later expert/tribunal stages.

## 2. Persistence

`ResearchDOMRepository` uses the existing R0 `SqliteUnitOfWork`; no second storage system was introduced.

A saved snapshot contains the complete authoritative planning state:

- DOM revision;
- root card;
- all cards;
- card revisions/statuses;
- dimensions;
- provenance (`created_from`);
- applied patch ids.

Round-trip equality is tested.

## 3. Event replay

`RESEARCH_CARD_ADDED` now carries a replayable immutable card payload. `replay_research_dom(initial_dom, events)` reconstructs the planning aggregate using:

- `RESEARCH_CARD_ADDED`;
- `RESEARCH_CARD_STATE_CHANGED`;
- `RESEARCH_PATCH_APPLIED`.

The event log and saved snapshot therefore form two independent recovery paths.

## 4. Card-to-knowledge trace links

Introduced `ResearchTraceLink` with relations:

- `PRODUCED`;
- `DISCOVERED`;
- `CREATED_CHALLENGE`;
- `RESOLVED_BY`;
- `VALIDATED`.

The link keeps ResearchDOM and KnowledgeGraph separate. A task card may produce a claim or discover a gap without embedding those graph entities inside the card itself.

Example chain now representable:

`RCD task -> PRODUCED -> CLM claim`

`RCD task -> DISCOVERED -> GAP gap`

In R2 this becomes the bridge for `Gap/Conflict -> new CHALLENGE card` while preserving provenance.

`ResearchTraceRepository` persists trace links through the same SQLite state substrate.

## 5. BCC demo

Artifact: `artifacts/researcher_r1/bcc_lattice_r1_1_persistence_trace_demo.json`.

Observed:

- 7-card planning DOM;
- 2 directions;
- 2 executable leaves;
- max depth 4;
- PlanningGate PASS;
- snapshot round-trip equality = true;
- event replay equality = true;
- task card linked to one claim and one gap.

## 6. Tests

New R1.1 tests: 7/7 PASS.

Full Researcher suite after R1.1:

- 378 total;
- 374 PASS;
- same 4 pre-existing failures as clean baseline/R1:
  - `test_guard.GuardBlockTests.test_p0_internal_weak_ru_is_low`;
  - `test_guard_integration.GuardIntegrationTests.test_local_evidence_with_discussion_is_allowed`;
  - `test_local_corpus.LocalCorpusCapsuleTests.test_search_local_hits`;
  - `test_local_corpus.LocalCorpusCapsuleTests.test_sources_local_ranked`.

No new failures were introduced.

Additional gates:

- `python -m compileall -q scripts/researcher/researcher_core` PASS;
- `python scripts/router/compile_runtime.py --check` PASS;
- `git diff --check` PASS.

## 7. Design decisions

### Kept separate

ResearchDOM is still the answer to **what are we doing?**. KnowledgeGraph remains the answer to **what do we know?**. `ResearchTraceLink` connects them without collapsing them into one giant graph.

### No scientific scoring in PlanningGate

The gate intentionally does not decide that a branch is scientifically sufficient. A tree can be structurally executable and scientifically incomplete. The latter should create another PlanningDialectic/Gap cycle, not a magic gate score.

### Snapshot plus replay

Keeping both is intentional. Snapshot gives cheap restart; events give audit/reconstruction and allow later projections.

## 8. Next boundary: R2

R2 should reconcile existing researcher_core knowledge entities with planning cards:

1. canonical `Claim/Source/EvidenceSpan/Gap/Conflict/Scope/Assumption/Derivation` identity;
2. `ResearchTraceLink` admission/events;
3. deterministic projection `ResearchCard <-> KnowledgeGraph`;
4. `Gap/Conflict -> ResearchChallenge -> CHALLENGE card` feedback;
5. stale/invalidation propagation through trace links;
6. no search yet beyond fixtures until the knowledge bridge is stable.
