# 02. Writer Core 2 Architecture

## 1. System boundary

```text
USER / PROJECT REQUIREMENTS
        |
        v
Requirement Compiler
        |
        +--> Policy Resolution
        |
        v
Researcher Core -----------------------------+
        |                                     |
        | EpistemicProjection                  |
        v                                     |
Writing Contract                              |
        |                                     |
        v                                     |
Writing Decomposition DAG                     |
        |                                     |
   +----+-------------------+                 |
   |                        |                 |
   v                        v                 |
Discourse Planner       Artifact Planner      |
   |                        |                 |
   +-----------+------------+                 |
               v                              |
         Realization Plan                     |
               |                              |
               v                              |
          LLM Realizer                        |
               |                              |
               v                              |
          Document IR                         |
               |                              |
    +----------+-----------+                  |
    |          |           |                  |
    v          v           v                  |
Claim back-  Object      Citation              |
extract      check       check                |
    +----------+-----------+                  |
               v                              |
      Round-trip Semantic Validator <----------+
               |
          +----+----+
          |         |
         FAIL      PASS
          |         |
      RepairPlan   Commit
                    |
                    v
             Dependency Engine
                    |
                    v
                Review
                    |
                    v
                 Export
```

## 2. Core layers

### Domain layer
Pure typed entities, relations, invariants. No LLM SDK and no database calls.

### Application layer
Commands and operations (`BindClaim`, `PlanParagraph`, `RealizeUnit`, `ValidateRoundTrip`, `InvalidateDependents`). One application write boundary: `WriterRegistry`.

### Infrastructure layer
SQLite, event log, template loader, model adapters, Pandoc exporter, Researcher adapter.

### Interface layer
CLI first. UI later. Human reviewer view is a projection, not a second state store.

## 3. Document IR

`DocumentIR` is a bundle of stable IDs and projections, not one giant nested JSON.

```text
DocumentIR
  document_tree_ref
  discourse_graph_ref
  artifact_graph_ref
  provenance_graph_ref
  policy_snapshot_ref
  dependency_snapshot_ref
```

Epistemic graph remains owned by Researcher. Writer stores stable references + immutable projection version.

## 4. Main command flow

```text
CompileRequirements
ResolvePolicy
ImportEpistemicProjection
BuildWritingContract
DecomposeWritingObjective
InstantiatePatterns
BindClaimsAndArtifacts
CreateRealizationPlan
RealizeUnit
ValidateObjects
BackExtractClaims
CompareSemanticRoundTrip
CommitUnit | ProduceRepairPlan
InvalidateAffectedDependencies
Review
BuildArtifact
```

## 5. Authority map

| Entity | Authority |
|---|---|
| Research Claim/Evidence/Scope | Researcher Core |
| Writing Contract | Writer bridge, derived |
| Document Tree | Writer Core |
| Discourse Graph | Writer Core |
| Artifact/Symbol nodes | Writer Core or external computation adapter |
| Policies/Templates | Git-managed static registry |
| Runtime events/revisions | Writer Core registry |
| Release approval | policy + required human/expert gate |
