# Researcher R3.3 relation assessment implementation review

Date: 2026-09-13
Status: IMPLEMENTED / EXERCISED (L1)

## Implemented

- Added `RAP` and `RAS` ID namespaces.
- Added `RelationAssessmentProposal/1.0` and `RelationAssessment/1.0`.
- Added verdicts `ACCEPTED`, `QUALIFIED`, `INCONCLUSIVE`, `REJECTED` and use states `ELIGIBLE`, `QUALIFIED`, `BLOCKED`.
- SUPPORTS/CONTRADICTS assessment composes existing `EdgeValidator`/`ScopeValidator` with typed method/evidence signals.
- QUANTIFIES gets an L1 scope/method/evidence policy.
- DERIVED_FROM is explicitly `INCONCLUSIVE` until reproducibility/assumption validation exists.
- `VALIDATED -> EDG` ResearchTraceLink records assessment provenance.
- REJECTED assessment can project to R2.3.3 `ACTIVE -> INVALIDATED` without endpoint mutation.
- `build_knowledge_dependencies()` can run in strict assessed-relation mode. Unassessed/inconclusive/rejected semantic relations do not become EDG->target reasoning dependencies.
- Service artifact can now carry `relation_assessments` separately from `graph_edges`.
- SQLite/UoW audit projection persists assessment proposals and assessments.

## Full-pipeline behavior

Exercised fixture:

`execution -> admission -> semantic linking -> relation assessment -> relation lifecycle -> strict dependency compile -> artifact render`.

Three SUPPORTS relations were tested:

1. ACCEPTED: ACTIVE, reasoning eligible, EDG->CLM dependency present.
2. INCONCLUSIVE: ACTIVE, blocked from strict semantic use, dependency omitted.
3. REJECTED: projected to INVALIDATED, dependency omitted.

All endpoint Claims remain OPEN. This confirms that relation assessment has not leaked into Claim truth state.

Representative artifact: `artifacts/researcher_r3_3/r3_3_full_pipeline_demo.json`.

## What the integration audit exposed

1. Strict relation assessment is not yet mandatory at every runtime call site. The compatibility default remains permissive for R2-era callers. TD-029.
2. Relation lifecycle reducer/event exists, but the dry-run ClaimRegistry owns only admission and cannot apply a revised EDG revision through one canonical update command. TD-030, related to TD-022.
3. INCONCLUSIVE relation is safely blocked but does not yet produce a Gap/ResearchChallenge feedback branch. TD-031.
4. DERIVED_FROM/QUANTIFIES need richer typed validators and assessment-signal adapters. TD-032.
5. Minimal service artifact writer-context remains fixture-level and is not a scientific release verdict.

## Regression

- R3.3 targeted tests: 15/15 PASS.
- Selected R1->R3.3 regression including artifact visibility: 117/117 PASS.
- Full Researcher: 467 total, 463 PASS, same four TD-015 Guard/LocalCorpus failures; TD-020 SQLite ResourceWarnings remain.
- Runtime compiler PASS, hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`.
- Capability compiler PASS, hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`.
- compileall PASS; git diff --check PASS.
- No new baseline failure class observed.

## Next boundary

R3.4 should be a small integration phase before R4 Tribunal:

- make assessed-relation use mandatory in the R3 reasoning facade;
- compile `INCONCLUSIVE/BLOCKED` relation assessment into a typed relation Gap/ResearchChallenge and reuse the existing challenge-planning loop;
- close the canonical EDG lifecycle write path or explicitly route through the durable relation projector.

Do not add Tribunal personas until this feedback/control loop is deterministic end to end.
