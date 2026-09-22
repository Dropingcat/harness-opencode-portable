# Researcher R2 branch: frozen base and future directions

Status: **stable base after R2.3.3; future work is non-blocking for R3**.

## What R2 now owns

R2 owns the planning↔knowledge feedback substrate: ResearchDOM/KnowledgeGraph reconciliation, Gap/Conflict→ResearchChallenge feedback, local challenge decomposition, resolution/reopen lifecycle, provenance-derived invalidation, SourceCatalog trigger bridge, and versioned relation lifecycle.

R2 does **not** own leaf execution, peer delegation, Tribunal composition, or human-expert interaction. Those are later phases.

## Stable invariants carried into R3

1. ResearchDOM is the historical/execution tree; KnowledgeGraph is epistemic state. Neither replaces the other.
2. Gap/Conflict are canonical knowledge entities. ResearchChallenge is the work object created to investigate them.
3. Historical challenge branches are preserved; reopen creates another iteration rather than erasing the previous resolution.
4. Knowledge changes are propagated through explicit/provenance-derived dependencies and reducers. Detection does not mutate authoritative state directly.
5. GraphEdge is a versioned information object. A relation can become stale without invalidating its endpoint entities.
6. Source identity bridges must be explicit until a shared canonical source identity exists.

## Future directions, ordered by complexity

### L1: operational hardening
- Dedicated relation-current-state/history SQLite projector and indexes (TD-022).
- Unified Writer/Researcher source identity and migration away from SourceIdentityBinding (TD-021).
- Better provenance diagnostics and impact explainability.
- Close historical Guard/LocalCorpus baseline debt before release-quality claims are made.

### L2: richer dependency semantics
- Weighted/conditional dependencies rather than only HARD/SOFT/CONTEXTUAL.
- Multiple support groups and alternative derivation paths.
- Edge-level quorum and method/scope-sensitive invalidation.
- Incremental impact cache for large graphs.

### L3: truth-maintenance behavior
- Explicit justification sets / nogoods.
- Assumption environments.
- TMS-like selective belief revision.
- ATMS-like parallel contexts only if actual research workloads justify the complexity.

### L4: learned routing over graph history
- Learn specialist/tool/rule selection from recorded outcomes.
- Keep learned scoring advisory to deterministic contracts/gates.
- Never permit learned routing to mutate epistemic state directly.

## Deliberately deferred

R2 must not grow into a generic workflow scheduler. Task execution belongs to R3 and existing Job/Attempt runtime. Tribunal reasoning belongs to R4+. HumanExpert interaction belongs to R7. This boundary is deliberate: otherwise every subsystem eventually discovers that it secretly wanted to be Kubernetes.
