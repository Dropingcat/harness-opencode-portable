# 14. Capability & Operation Registry

## Principle

Architecture routes **typed operations**, not personas. Agents/models are replaceable executors registered by capability.

## Operation contract

Every operation declares:

```yaml
id:
reads: []
writes: []
authority_required:
preconditions: []
postconditions: []
idempotency:
deterministic_part: []
model_assisted_part: []
validators: []
blockers_on_failure: []
```

## Core operations

- CompileRequirements
- ImportEpistemicProjection
- BuildWritingContract
- DecomposeWritingObjective
- BindClaimSlot
- BindArtifactSlot
- InstantiateArgumentPattern
- InstantiateDiscoursePattern
- RealizeUnit
- BackExtractSemantics
- ValidateRoundTrip
- PlanSemanticRepair
- ComputeImpactClosure
- RebuildArtifact
- ValidateGlobalConsistency
- OpenReviewIssue / ResolveReviewIssue
- CreateDecision
- CreateBlocker / ResolveBlocker
- BuildReleaseCandidate
- ExportArtifact
- ParseBackExport
- RunVisualPreflight

## Capability registry

Executor registration must state supported operations, model/tool version, determinism, cost class, and authority (normally proposal-only). A model cannot receive write authority simply because it performs well on a benchmark.
