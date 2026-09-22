# 09. Implementation Master Plan

## Principle

Build from semantics and invariants outward. No graph-mining fireworks until the one-paragraph compiler is reliable.

## Phase 0 — Freeze contracts

Deliverables:
- terminology registry;
- graph/entity registry;
- reason-code registry;
- ADR: YAML static / SQLite runtime authority;
- migration mapping from current WriterUnit.

Gate: schemas compile and fixtures validate.

## Phase 1 — Domain IR

Implement:
- stable IDs;
- Document Tree;
- Discourse entities;
- Artifact/Symbol entities;
- relation types;
- orthogonal statuses;
- event/revision base.

Gate: CRUD + referential integrity + snapshot/diff tests.

## Phase 2 — Writing Contract Bridge

Implement Researcher projection adapter and `ClaimWritingContract`.

Gate: fixture can map Researcher claim statuses/scopes/evidence into a lossless Writer contract.

## Phase 3 — One-paragraph decomposition

Implement:
- WritingObjective;
- ParagraphIntent;
- ArgumentNeed;
- ClaimSlot/ArtifactSlot;
- minimal pattern registry.

Gate: deterministic plan from fixture without prose generation.

## Phase 4 — Structured Realization

Implement inline AST:
`TextNode`, `ClaimSpan`, `QuantityRef`, `FormulaRef`, `CitationRef`, `CrossRef`, `TermRef`.

Gate: render to plain text/Markdown; quantity/citation updates require no LLM rewrite.

## Phase 5 — RTT v1

Implement:
- back-extraction schema;
- claim alignment;
- scope/modality/causality/numeric checks;
- reason codes;
- repair loop.

Gate: golden fixtures catch all hard failures in `examples/roundtrip/`.

### Milestone M1

**Academic paragraph compiler** is production-usable in CLI.

Do not continue if M1 is not reliable.

## Phase 6 — Dependency Engine

Implement dependency edges, impact closure, freshness states, selective rebuild.

Gate: changing one quantity invalidates exactly affected units/figures/conclusions.

## Phase 7 — Section/document composition

Add section templates, macro RTT and cross-section consistency.

Gate: abstract/conclusion claims trace to body claims; stale propagation crosses section boundaries.

## Phase 8 — Policy system

Implement genre/domain/risk/institution/style/numeric/citation policies and precedence/conflict handling.

Gate: same semantic input renders under two distinct policy profiles without changing epistemic content.

## Phase 9 — Human review projection

Claim-table + argument/discourse/artifact trace view.

Gate: reviewer can identify source, evidence and dependencies for any final factual span.

## Phase 10 — Corpus learning

Only now:
- corpus admission;
- dedup;
- discourse/argument pattern extraction;
- style profiling;
- pattern promotion lifecycle;
- retrieval.

Gate: reference text cannot enter factual provenance of target document unless independently admitted by Researcher.

## Phase 11 — Advanced comparison

Evaluate WL kernels/GED/subgraph mining only against measured tasks. Similarity stays a diagnostic vector, not a universal quality score.

## Phase 12 — Export and production hardening

Pandoc/CSL, DOCX/PDF, reproducible builds, packaging, observability, migrations.

## Parallel agent tracks

After Phase 1, parallelism is allowed only where schemas are frozen:

```text
Track A: Contract bridge
Track B: Artifact engine
Track C: Template registry
Track D: CLI/event store
```

RTT waits for A + core realization schema.
