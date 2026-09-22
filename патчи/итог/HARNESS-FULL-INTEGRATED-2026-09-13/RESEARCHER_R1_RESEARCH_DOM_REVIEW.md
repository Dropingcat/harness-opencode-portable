# RESEARCHER-R1-RESEARCH-DOM-001 — implementation review

## Scope

R1 implements the first authoritative planning slice for Researcher Core without changing retrieval, tribunal, semantic verification, or peer-agent delegation.

The boundary is:

`ResearchRequest -> PlanningDialectic history -> ResearchCard proposals -> ResearchMap -> ResearchPatch -> ResearchDOM reducer`

The LLM-facing side may propose structure. It cannot mutate ResearchDOM directly.

## Reused foundations

R1 deliberately reuses existing researcher_core contracts instead of creating a second runtime:

- `EntityId` / `EntityIdFactory` for typed deterministic IDs;
- `EntityMeta` for immutable entity revision metadata;
- `ActorRef` for actor provenance;
- `EventEnvelope` for event-sourced planning mutations;
- existing policy/reason-code loading;
- existing harness runtime compiler remains unchanged and passes.

New ID namespaces: `RRQ`, `RCD`, `RMP`, `RDM`, `DCS`, `PIT`, `RPT`.

## New contracts

### ResearchRequest
Root research objective and constraints.

### ResearchCard
Immutable historical card. Kinds:

- OBJECTIVE
- DIRECTION
- DISCIPLINARY_VIEW
- QUESTION
- METHOD_VIEW
- TASK
- CHALLENGE
- TRIBUNAL_SESSION
- DELEGATION

Cards keep parent ancestry plus orthogonal dimensions such as disciplines, question types, methods and capability hints.

### ResearchMap
A non-authoritative multidimensional projection over candidate cards. Current axes:

- directions
- disciplines
- question_types
- methods

ResearchMap does not mutate the executable tree.

### PlanningInquiryTurn / DecompositionSession
Stores the historical Q/A planning chain. The target can be the root objective or any existing ResearchCard, allowing recursive/local decomposition later for Gap/Conflict/Challenge branches.

### ResearchCardProposal
Non-authoritative proposed planning node. Parent references may point to an existing ResearchCard or another proposal temp-id from the same batch.

### ResearchPatch / ResearchDOM
ResearchDOM is immutable and revisioned. All mutations go through an atomic patch with `expected_dom_revision`. Current operations are `AddCardOperation` and revision-checked `SetCardStatusOperation`.

## Deterministic compiler

`compile_decomposition_proposals()` performs no semantic invention. It:

1. validates the DecompositionSession target;
2. rejects empty batches, duplicate temp IDs and duplicate sibling proposals;
3. allocates authoritative RCD IDs;
4. resolves nested temp-parent references;
5. validates tree connectivity and cycles;
6. builds ResearchMap;
7. emits one atomic ResearchPatch tied to the source DecompositionSession.

This enforces the project principle: LLM proposes semantics, code owns authoritative state mutation.

## Reducer behavior

`apply_research_patch()` fails closed on:

- request mismatch;
- stale DOM revision;
- duplicate patch replay;
- duplicate card ID;
- missing parent;
- stale card revision;
- disconnected/cyclic tree.

Successful mutation emits `RESEARCH_CARD_ADDED`, optional `RESEARCH_CARD_STATE_CHANGED`, then `RESEARCH_PATCH_APPLIED`.

## BCC lattice planning fixture

The deterministic demo uses the objective:

> Исследовать утверждение: параметр ОЦК-решётки стали уменьшается под действием легирующих элементов.

Two planning Q/A rounds produce four directions:

1. composition of BCC matrix vs lattice parameter;
2. redistribution of alloying elements into secondary phases;
3. residual stress and microstrain;
4. metrological correctness of lattice-parameter measurement.

The resulting ResearchMap contains disciplinary views including physics of metals, crystallography, materials science, physical metallurgy and metrology; methods include XRD, TEM, SAED, EDS and EPMA.

The resulting DOM contains 12 cards total: one objective root plus 11 inserted cards. All 11 additions are committed in one patch from DOM revision 1 to 2.

Artifact: `artifacts/researcher_r1/bcc_lattice_planning_demo.json`.

## Tests

Clean imported harness baseline:

- 360 researcher tests total;
- 4 pre-existing failures/errors: two Guard cases and two LocalCorpus cases.

R1 snapshot:

- 371 researcher tests total;
- 11 new R1 tests PASS;
- the same 4 pre-existing Guard/LocalCorpus failures remain;
- therefore 367 tests pass and no new regression is observed in the full suite.

Additional gates:

- `python scripts/router/compile_runtime.py --check` PASS;
- `python -m compileall scripts/researcher/researcher_core` PASS;
- `git diff --check` PASS.

The four baseline failures are intentionally not repaired in R1 because they are unrelated to ResearchDOM and changing them would contaminate the planning boundary.

## What R1 does not yet do

R1 intentionally does not:

- call an LLM to generate decomposition turns;
- score completeness of a decomposition;
- prune branches by information gain;
- execute TASK cards;
- link cards to Claim/Gap/Conflict graph nodes;
- compose tribunal roles;
- delegate TASK cards to Writer/Coder;
- persist ResearchDOM through the main SQLite repository.

These are subsequent slices, not hidden TODOs inside the reducer.

## Recommended next slice

R1.1 should add `PlanningGate` and persistence/replay before retrieval:

- coverage / duplication / operationality / dependency checks;
- explicit executable leaf capability contract;
- serialization + SQLite/event replay for ResearchDOM;
- local decomposition of an existing card or Gap-derived Challenge;
- machine trace links `ResearchCard -> produced Claim/Gap/Conflict` without yet implementing tribunal.

After that, R2 can reconcile ResearchDOM with the existing researcher_core knowledge graph without changing either side's authority.
