# 21. Review, Decisions & Conflict Resolution

## ReviewIssue

First-class entity:
`target`, `issue_type`, `severity`, `evidence`, `reviewer`, `proposal`, `state`, `resolution`, `revalidation`.

Lifecycle:
`OPEN → ACCEPTED | REJECTED_WITH_REASON → FIXED → REVALIDATED → CLOSED`.

## Reviewer disagreement

Conflicting requirements create `ReviewConflict`, never last-write-wins. Resolution records alternatives, authority and rationale.

## Human Decision Registry

Decisions for terminology, disputed interpretations, structure, overrides, freezes and release exceptions are versioned ADR-like entities with affected dependencies.

## Branch/Merge

Merge occurs at unit/semantic/artifact levels. Conflict types:
- TEXT_CONFLICT
- SEMANTIC_CONFLICT
- CLAIM_BINDING_CONFLICT
- STRUCTURE_CONFLICT
- ARTIFACT_CONFLICT
- POLICY_CONFLICT

After merge: RTT + global consistency + dependency validation mandatory.

## Freeze controls

Separate `KnowledgeFreeze` and `TextFreeze`. Authority levels:
`MODEL_CAN_EDIT`, `MODEL_CAN_PROPOSE`, `HUMAN_APPROVAL_REQUIRED`, `LOCKED`.
