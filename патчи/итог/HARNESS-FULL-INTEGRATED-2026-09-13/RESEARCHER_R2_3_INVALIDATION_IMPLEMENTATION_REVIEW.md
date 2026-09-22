# RESEARCHER R2.3 invalidation implementation review

Status: first deterministic slice complete.

## Result

R2.3 closes the negative-feedback loop for already resolved knowledge. A source/evidence/relation change is first converted into `DependencyImpactAssessment/1.0`; only a complete critical impact may reopen the existing historical `ResearchChallenge` branch.

Implemented contracts: `KnowledgeDependency/1.0`, `DependencyImpactAssessment/1.0`, `ChallengeIteration/1.0`.

## Behaviour verified

- redundant evidence becomes `REVALIDATION_REQUIRED` and does not reopen the branch;
- sole HARD evidence invalidation reaches the resolution assessment and reopens the same challenge/card;
- stale relation targets are reported independently from endpoint claims;
- CONTEXTUAL dependency with `scope_overlap=false` produces no cascade;
- stale historical resolution revision fails closed;
- prior + reopened challenge iterations persist in order;
- unrelated ResearchDOM branches remain byte/structure-equivalent.

## Authority

Change detection does not mutate knowledge. Impact calculation does not mutate knowledge. `reopen_from_impact()` is the first-slice reducer boundary and only accepts a complete `REOPEN_REQUIRED` impact bound to the current historical resolution.

## Limits

Dependency links are explicit, SourceCatalog is not yet a direct trigger, relation state is projected as stale IDs rather than a versioned edge lifecycle, and no Tribunal/Search rerun occurs automatically. These are documented as TD-018..TD-020 / R2.3.1+.

## Regression

- R2.3 tests: 7/7 PASS.
- selected R1/R1.1/R2/R2.1/R2.2/R2.3 suite: 44/44 PASS.
- full Researcher suite: 404 total, 400 PASS; same four pre-existing Guard/LocalCorpus failures under TD-015.
- full suite also exposes pre-existing/newly-recorded SQLite ResourceWarnings, TD-020.
