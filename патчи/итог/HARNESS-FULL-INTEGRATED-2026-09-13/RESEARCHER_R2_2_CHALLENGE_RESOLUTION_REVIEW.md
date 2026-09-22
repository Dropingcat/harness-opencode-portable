# RESEARCHER R2.2 — Challenge Resolution Review

## Boundary

R2.2 closes the first lifecycle loop from a knowledge problem through an adaptive challenge branch and back into canonical knowledge state.

`Gap/Conflict -> ResearchChallenge -> CHALLENGE subtree -> ChallengeResolutionAssessment -> canonical knowledge/challenge/card projection`

## Implemented

- `ChallengeResolutionAssessment/1.0` (`RRS`) with rationale, evidence refs, claim refs, remaining requirements and optimistic `expected_challenge_revision`.
- Outcomes: `RESOLVED`, `STILL_OPEN`, `BLOCKED`, `REOPENED`.
- Conflict modes: `SUBSTANTIVE`, `SCOPE_MISMATCH`, `METHOD_MISMATCH`, `INSUFFICIENT_EVIDENCE`.
- Gap projection: resolve to `NO_OPEN_GAPS`; reopen to blocking/nonblocking state based on canonical Gap severity.
- Conflict projection: resolve to `NO_DIRECT_CONFLICT`; reopen/still-open/block to `CONFLICT_UNRESOLVED`.
- Scope mismatch can resolve an apparent conflict without asserting substantive agreement between claims.
- `INSUFFICIENT_EVIDENCE` cannot be used as a resolving conflict assessment.
- `ResearchChallenge` revision increments on lifecycle transition; stale assessments fail closed.
- CHALLENGE card transitions with the same resolution: `COMPLETED`, `ACTIVE`, or `BLOCKED`.
- ResearchTraceLink records assessment/evidence/source linkage.
- Resolution assessments persist in the existing SQLite/UoW substrate.
- R2.1 activation optionally advances the bound `ResearchChallenge` to `ACTIVE` with revision increment, closing the prior entity/card lifecycle mismatch.

## Regression

- Selected R1/R1.1/R2/R2.1/R2.2 suite: **37/37 PASS**.
- Full Researcher suite: **397 total; 393 PASS; 4 pre-existing FAIL/ERROR**.
- The four failures remain the same Guard/LocalCorpus baseline debt and are tracked as TD-015.
- Runtime policy compiler: PASS.
- Capability policy compiler: PASS.
- `compileall`: PASS.
- `git diff --check`: PASS.

## Technical debt explicitly retained

- TD-015: pre-existing Guard/LocalCorpus baseline failures.
- TD-016: duplicate root `resercher-core` copy versus canonical `scripts/researcher/researcher_core`.
- TD-017: `evidence.verify` provider-priority overlap with code-factory provider.

R2.2 does not claim these debts as fixed.

## Next boundary: R2.3

Resolution-driven subtree finalization and invalidation:

1. when a challenge resolves, descendant TASK/METHOD/QUESTION cards must be deterministically finalized or preserved as historical completed work;
2. if supporting source/evidence becomes stale, a previously resolved Gap/Conflict can be reopened through provenance without hand-editing state;
3. reopening must preserve prior resolution assessment and create a new assessment/research iteration rather than overwriting history;
4. challenge re-planning should append/extend the historical branch, not erase the prior completed subtree.
