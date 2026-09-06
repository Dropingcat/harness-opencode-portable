# Graph-Driven Memory Capsule

## Scope
This capsule defines deterministic memory extraction and promotion from claim-graph audit snapshots. It uses three levels:

- L1: ephemeral run-local working memory
- L2: task memory derived from a single audit snapshot
- L3: promoted recurring lessons backed by repeated evidence

## Design Rules
- All triggers are derived from claim graph and audit snapshot fields.
- No hard prompts, freeform summarizers, or opaque heuristics.
- Collectors must be deterministic from snapshot input plus policy config.
- Missing or malformed fields are handled conservatively by skipping uncertain inferences.
- Every stored item carries source references into the audit snapshot.

## Levels
### L1
L1 is transient execution context. It is not persisted as durable memory. It may hold current task identifiers, active claim ids, unresolved audit flags, and paths to the current snapshot.

### L2
L2 is a per-task memory artifact produced from one snapshot. It records task identity, snapshot identity, claim refs, audit refs, issue aggregates by reason code, evidence refs, and candidate lessons only when directly supported by snapshot structure.

### L3
L3 is a registry of recurring lessons promoted from L2. Promotion requires recurring_count meeting configured threshold, evidence_refs present, reason_codes present, and stable key derivation from lesson content and reason codes.

## Expected Snapshot Shape
Collectors are designed for task-audit snapshots with fields such as: task/task_id, claims, audits/audit_entries, evidence, edges. Equivalent fields may be configured by policy aliases.

## Data Flow
1. Audit system writes a snapshot JSON.
2. collect_l2.py reads the snapshot and emits one L2 memory JSON.
3. promote_l2_to_l3.py reads an L2 file and the L3 registry.
4. Promotion updates the registry only for lessons meeting policy gates.

## Guarantees
- Deterministic output for the same inputs.
- Conservative behavior on missing fields.
- Explicit provenance for every stored lesson.

## Constraint
Memory is built only after audit_graph exists and only as a projection of it. Memory never becomes authoritative state.
