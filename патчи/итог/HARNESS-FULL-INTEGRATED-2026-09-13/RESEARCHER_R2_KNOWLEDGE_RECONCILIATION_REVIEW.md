# RESEARCHER-R2-KNOWLEDGE-RECONCILIATION-001

## Scope

R2 connects the historical ResearchDOM planning tree with the existing canonical knowledge layer. It deliberately does not create alternative Claim/Gap/Conflict models.

The new loop is:

`ResearchCard -> Claim/Evidence -> Gap|Conflict -> ResearchChallenge -> CHALLENGE ResearchCard`

A CHALLENGE card is intentionally non-executable until the normal PlanningDialectic decomposes it into questions/methods/tasks.

## Reused canonical components

- `r1_entities.Gap`
- `r1_entities.Conflict`
- `ResearchDOM`, `ResearchPatch`, reducer
- `ResearchTraceLink`
- existing SQLite `SqliteUnitOfWork`

## New contract

`ResearchChallenge/1.0` records the need to investigate an admitted knowledge problem. It carries:

- request identity;
- source Gap/Conflict identity;
- target Claim identities;
- resolution requirements;
- inherited research dimensions;
- challenge state.

The source Gap/Conflict remains authoritative.

## Feedback materialization

`materialize_challenge_card()`:

1. validates request ownership and parent card;
2. folds dimensions along the full ResearchDOM lineage;
3. creates an immutable `CHALLENGE` card with `created_from=(GAP|CNF)`;
4. applies it through a revision-checked `ResearchPatch`;
5. writes trace relations:
   - parent card `CREATED_CHALLENGE -> RCH`;
   - challenge card `ADDRESSES -> GAP|CNF`.

The lineage fold is important for future tribunal composition. A Gap found under an XRD branch keeps `disciplines`, `methods`, `question_types` and lower-level task dimensions instead of becoming a context-free problem.

## Persistence and projection

`ResearchChallengeRepository` uses the existing SQLite/UoW substrate. `ResearchKnowledgeProjection` builds both directions:

- ResearchCard -> linked knowledge/research entities;
- knowledge/research entity -> ResearchCards that produced/discovered/address it.

No second storage system was added.

## BCC/XRD fixture

Fixture: a task under D1 (`crystallography + physics_of_metals`, method `xrd`) discovers the Gap `residual_stress_not_excluded` for a lattice-parameter claim.

R2 produces:

- one canonical Gap;
- one `ResearchChallenge(GAP_RESOLUTION)`;
- one historical CHALLENGE card under the originating task;
- inherited D1/XRD dimensions;
- two trace links;
- SQLite round-trip for the challenge.

After feedback, PlanningGate returns `NON_EXECUTABLE_LEAF`. This is intended. The challenge has re-entered planning and must be decomposed before execution.

Artifact: `artifacts/researcher_r2/bcc_gap_feedback_demo.json`.

## Test state

New R2 tests: 6/6 PASS.

Full Researcher suite after R2: 384 total, 380 PASS, 4 pre-existing failures/errors:

- two Guard expectations;
- two LocalCorpus fixture/environment cases.

These are the same baseline defects observed before R2.

Additional gates:

- `compileall`: PASS
- runtime policy compiler: PASS (`6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`)
- capability policy compiler: PASS (`b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`)
- `git diff --check`: PASS

## Deliberately deferred

R2 does not yet automatically decompose a CHALLENGE into executable children. That is the next slice because it should reuse `PlanningInquiryTurn/DecompositionSession`, not introduce a special Gap planner.

The intended next loop is:

`Gap|Conflict -> ResearchChallenge -> CHALLENGE card -> PlanningDialectic -> QUESTION/METHOD/TASK subtree -> execution`
