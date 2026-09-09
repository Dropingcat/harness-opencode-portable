# 23. Blocker & Project Orchestration Engine

## Blocker as first-class entity

A blocker states what prevents progress/release, not merely that a validator complained.

Core classes:
- MISSING_EVIDENCE
- UNRESOLVED_CONFLICT
- STALE_CRITICAL_DEPENDENCY
- RTT_HARD_FAILURE
- QUANTITATIVE_INTEGRITY_FAILURE
- ARTIFACT_LINEAGE_FAILURE
- REVIEW_REQUIRED
- POLICY_CONFLICT
- SOURCE_RETRACTED_OR_CHANGED
- EXPORT_FAILURE
- VISUAL_QA_FAILURE
- SCHEMA_MIGRATION_REQUIRED

Severity:
`INFO`, `WORK_BLOCKING`, `SECTION_BLOCKING`, `RELEASE_BLOCKING`.

Blocker records target, origin, dependency impact, possible resolution operations and state.

## Orchestrator

The orchestrator is deterministic/state-driven:

```text
ProjectState
→ open blockers
→ dependency graph
→ critical path
→ ready queue
→ priority policy
→ next typed operation
```

Queues:
`ready`, `blocked`, `research`, `repair`, `rebuild`, `review`, `release`.

## Document debt

Track separate debt vectors:
`evidence`, `citation`, `terminology`, `artifact`, `review`, `formatting`, `stale`, `migration`.

## Progress

Never report only percentage text completed. Report:
- closed required slots;
- critical-path blockers;
- stale critical entities;
- unresolved review/research work;
- release gate state.
