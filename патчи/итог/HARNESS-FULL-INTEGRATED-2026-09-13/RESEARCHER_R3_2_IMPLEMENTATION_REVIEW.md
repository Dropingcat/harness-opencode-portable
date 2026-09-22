# Researcher R3.2 implementation review

Status: IMPLEMENTED / EXERCISED (L1)

## Implemented

R3.2 adds an explicit post-admission semantic-linking control step. Newly admitted execution outputs do not gain semantic edges merely because they arrived in the same batch. An adapter must declare a typed `SemanticRelationProposal`, endpoint identities are resolved through `AdmissionIdentityMap`, the relation shape is validated, and only then is a canonical `GraphEdge` admitted through the existing ClaimRegistry.

New audit artifacts: `AIM-*`, `SRP-*`, `SLR-*`. `ResearchTraceLink` now accepts `EDG` targets, matching the R2.3.3 decision that relations are first-class information objects.

Supported L1 forms: EVD->CLM SUPPORTS/CONTRADICTS, QTY->CLM QUANTIFIES, CLM->CLM DERIVED_FROM.

## Important invariants

- Co-occurrence creates no relation.
- Admission of a SUPPORTS edge does not change ClaimStatus to SUPPORTED.
- Relation proposals cannot mutate state directly.
- Unknown temp IDs, cross-receipt canonical IDs, invalid endpoint types and duplicate relations fail closed.
- GraphEdge remains canonical authority; AIM/SRP/SLR are control/audit artifacts.

## Tests

- R3.2 targeted: 10/10 PASS.
- Selected R1->R3.2 regression: 85/85 PASS.
- Full Researcher: 452 total, 448 PASS, same four pre-existing TD-015 Guard/LocalCorpus failures.
- TD-020 SQLite ResourceWarnings remain visible.

## Limitations / future work

1. `AdmissionIdentityMap` reconstructs generated CLM/QTY IDs using current registry accepted-ID ordering (TD-027).
2. Cross-admission linking is disabled pending an explicit external endpoint authorization contract (TD-028).
3. Relation compatibility is a small L1 table, not yet compiled policy.
4. No relation-strength/quality assessment, Tribunal argument or justification-set semantics yet.
5. Derivation/Assumption entities themselves are not yet admitted by this block.

## Architecture interpretation

This block preserves the control-plane principle used across the harness: model/tool/adapters may propose relations, while code owns identity resolution, compatibility checks, canonical admission and provenance. It also preserves the distinction between observation, admission, semantic relation and epistemic verdict.

## Final gates

- `python scripts/router/compile_runtime.py --check`: PASS, policy hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`.
- `python scripts/router/compile_capability_runtime.py --check`: PASS, policy hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`.
- `python -m compileall -q scripts/researcher/researcher_core`: PASS.
- `git diff --check`: PASS.
