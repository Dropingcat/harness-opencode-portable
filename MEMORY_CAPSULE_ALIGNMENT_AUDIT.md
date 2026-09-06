# Memory Capsule Alignment Audit

## Reviewed against

- gents/code-orchestrator.md
- shared/code-factory-process.md
- udit_graph/README.md
- MEMORY_POLICY.md
- UNIFIED_ORCHESTRATION_PRINCIPLES.md
- E:\барахло\Documents\Default Project\03-r0-core-contracts.md
- E:\барахло\Documents\Default Project\05-claim-validation-pipeline.md
- E:\барахло\Documents\Default Project\06-runtime-orchestration.md
- E:\барахло\Documents\Default Project\12-policy-config-and-heuristics.md
- E:\барахло\Documents\Default Project\malina_research_service_fixture.yaml

## Verdict

Direction remains **graph-based and aligned** with the original factory/research principles.

## Confirmed alignments

1. **Code decides, memory advises.**
   - code-orchestrator uses memory as retrospective only.
   - MEMORY_CAPSULE_ARCHITECTURE.md and policies keep memory non-authoritative.

2. **Claim graph binding preserved.**
   - L2 collector derives from audit snapshot claims/audits only.
   - L3 promotion requires reason codes + evidence refs + recurrence threshold.

3. **Policy-driven, not hard prompt.**
   - L1/L2/L3 live in config/memory_*.json.
   - No prompt text is required to decide memory admission.

4. **Researcher-core parity direction.**
   - Snapshot-first, typed transitions, reason codes, conservative omission on missing data.

5. **Capsule parity with skills/router.**
   - memory now has architecture doc, policies, registry, deterministic scripts.

## Remaining gaps

1. Current collectors operate on JSON snapshots; malina_research_service_fixture.yaml is still an architectural source, not a directly replayed runtime fixture.
2. L1 is policy-defined but not yet wired into ContextBuilder / router plugin.
3. L2 currently reads claims + audit lists conservatively; richer graph fields (gaps, conflicts, writer_context) should be added in the next pass.
4. L3 registry exists but is not yet connected to live OpenCode memory add/search.

## Graph-development check

The development direction is still correct:

`	ext
audit_graph -> task_audit_template -> memory L2 projection -> L3 promoted lessons
`

This avoids regression into chat-memory or hardcoded heuristics.
