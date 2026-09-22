# RESEARCHER R2.3.3 — canonical relation lifecycle implementation review

Date: 2026-09-12

## Result

The knowledge graph now treats `GraphEdge` as a first-class versioned information object rather than an immutable tuple whose current validity is only implied by an external impact report.

## Implemented

- `GraphEdgeState`: `ACTIVE`, `STALE`, `SUPERSEDED`, `INVALIDATED`.
- optimistic relation transitions with revision checks;
- replayable `EDGE_STATE_CHANGED` events containing the complete updated edge record;
- deterministic projection of `DependencyImpactAssessment.stale_relation_ids` onto canonical relations;
- endpoint entities remain untouched during relation-only invalidation;
- backward-compatible replay for legacy GraphEdge records without lifecycle state;
- service artifact visibility for relation state/revision;
- provenance dependency compilation honors relation lifecycle.

## Architectural meaning

This closes an important epistemic defect. Statements such as `C1 SUPPORTS C2` or `E1 CONTRADICTS C3` contain information that can become stale independently from `C1`, `C2`, `E1` or `C3`. R2.3.3 therefore gives the relation its own identity, revision and state transition history.

The design remains below a full TMS. It records and maintains exact relation validity but does not yet model multiple assumption contexts/nogood sets.

## Compatibility

Existing positional GraphEdge construction remains valid because lifecycle state is appended after the existing `attributes` field with default `ACTIVE`.

Legacy event records lacking `state` deserialize to `ACTIVE`.

## Regression findings during implementation

Two temporary projection regressions were detected by the full/registry tests while adding the new field: relation state was accidentally injected into Claim serialization/deserialization. Both were corrected before the final boundary. This is recorded because it confirms why full event-projection regression remains mandatory for future entity-schema changes.

## Tests

Target relation/provenance/graph/registry/artifact tests pass after fixes.

Full Researcher suite after implementation: 421 tests total, 417 PASS, with only the same four pre-existing Guard/LocalCorpus failures tracked by TD-015. SQLite ResourceWarnings remain tracked by TD-020.

## Limitations / next development

1. No dedicated durable relation-state/history index: TD-022.
2. Tribunal does not yet automatically revalidate stale relation edges.
3. Supersession has a lifecycle state but no explicit replacement-edge link.
4. No calibrated confidence/justification-set model.
5. Large-graph local truth maintenance remains bounded deterministic propagation rather than TMS/ATMS.

The next architectural layer should not add more relation states. It should either close TD-022 or move into R3 task execution/delegation, using R2.x as the stable knowledge/planning substrate.
