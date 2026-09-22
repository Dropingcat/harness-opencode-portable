# README FIRST — R3.5 → R4 Tribunal handoff

Date: 2026-09-13

This archive is the continuation point for the Writer/Researcher/Coder harness. It is intentionally a recovery + context package, not merely a patch collection.

## Canonical boundary

Current Researcher HEAD:

`fe57c88312755d01e91a1ff1357481f577b71945`

`researcher: model multidimensional uncertainty before tribunal`

R3.5 is complete. The next session may begin directly with **R4 Tribunal Composition**.

The architectural split to preserve is:

```text
R3 / ReviewWorkField
  what is uncertain?
  why?
  how material or blocking is it?
  how can it be assessed?
  what counts as closure?

R4 / TribunalCompositionPlan
  who should assess it?
  which independent perspectives are needed?
  what evidence slice does each role see?
  what tools/capabilities are allowed?
  what inquiry contract and budget apply?
```

Tribunal must not invent its own problem statement when R3 already supplied typed AssessmentNeeds.

## Read in this order

1. `SESSION_HANDOFF(1).md`
2. `CONTEXT_PATTERNS_FROM_SESSION_AND_MEMORY(1).md`
3. `R4_NEXT_PHASE_PLAN(1).md`
4. `harness/handoff/RESEARCHER_R3_5_UNCERTAINTY_FIELD_ARCHITECTURE.md`
5. `harness/handoff/RESEARCHER_R3_5_TRIBUNAL_INPUT_AUDIT.md`
6. `harness/handoff/CONTEXT_AND_QA_R4_TRIBUNAL.md`
7. `harness/handoff/LEGACY_TRIBUNAL_CONTEXT_EXTRACT.md`
8. `harness/handoff/R4_OPEN_DECISIONS_REGISTER.md`
9. `harness/repo/IMPLEMENTATION_TRACKER.md`
10. `harness/repo/TECH_DEBT.md`

## Repository/recovery

The archive contains a full Git checkout under `harness/repo/` including `.git`.

Expected checkout state:

```text
HEAD   fe57c88312755d01e91a1ff1357481f577b71945
status clean
```

Recovery bundles:

- `harness/recovery/HARNESS-R3.5-COMPLETE-2026-09-13.bundle`
- `harness/recovery/HARNESS-R3-COMPLETE-2026-09-13.bundle`

Milestone packages R0 → R3.5 are under `harness/packages/`.

Four architecture/research review documents are under `harness/source_reviews/`.

## First R4 implementation boundary

Do not start with live Tribunal dialogue.

First implement a deterministic, typed composition layer:

```text
ReviewWorkField.assessment_needs
+ ResearchDOM lineage dimensions
+ Claim/Relation profile
+ policy snapshot
        ↓
TribunalCompositionPlan
```

Expected plan contents:

- permanent roles;
- dynamic roles;
- assignments to AssessmentNeed IDs;
- evidence-view policy;
- role contracts;
- allowed capabilities/tools;
- inquiry budget/depth;
- reason codes;
- policy version/hash.

Composition may prepare work. It must not mutate Claim, GraphEdge, Gap, Conflict or truth state.

## Hard invariants

- LLM proposes/argues; code owns authoritative transitions.
- Observation != admission != semantic relation != relation assessment != claim truth.
- ResearchDOM is historical/execution structure; KnowledgeGraph is semantic knowledge.
- Challenge branches are historical and iterative, not destructively replaced.
- Relation is a first-class versioned information object.
- Uncertainty is multidimensional; absent information is not silently RESOLVED.
- Specialized agents remain specialized; no god-agent.
- Peer delegation reuses the existing Job/child runtime; no second scheduler.
- Every new architecture block must document authority boundary, contracts, limitations, fail-closed behavior, tests, debt and complexity ladder.

The rest is in the handoff files. Humans do love hiding state in conversations, so this archive tries to undo that particular tradition.
