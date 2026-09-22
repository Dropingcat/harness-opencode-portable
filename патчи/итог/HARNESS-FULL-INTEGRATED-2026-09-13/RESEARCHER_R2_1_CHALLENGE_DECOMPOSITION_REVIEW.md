# RESEARCHER R2.1 — Challenge decomposition review

## Boundary

R2 created the feedback edge `Gap/Conflict -> ResearchChallenge -> CHALLENGE card`.
R2.1 makes that edge executable by sending a CHALLENGE card through the same
planning dialectic/compiler already used for the initial research objective.
No search provider, tribunal, or second planner was added.

## Runtime flow

```text
Gap / Conflict
  -> ResearchChallenge
  -> CHALLENGE card (PLANNED)
  -> PlanningInquiryTurn Q1/A1/Q2/A2
  -> ResearchCardProposal[]
  -> compile_decomposition_proposals()
  -> local QUESTION / METHOD_VIEW / TASK subtree
  -> local PlanningGate
  -> CHALLENGE status ACTIVE
```

The semantic planner proposes turns/cards. Code owns structure validation,
optimistic concurrency, subtree locality, executability and state transition.

## New code

- `scripts/researcher/researcher_core/challenge_planning.py`
  - `ChallengePlanningResult`
  - `expand_challenge_with_decomposition(...)`
  - rejects wrong request, wrong target kind/status, cross-branch parents and non-executable local plans.
- `research_planning_runtime.evaluate_planning_subtree_gate(...)`
  - evaluates only descendants of one selected card;
  - no DIRECTION is required inside a feedback subtree;
  - TASK/DELEGATION leaves still require capability/delegation target;
  - card/depth budgets and duplicate siblings remain enforced.

## Important design decisions

### One planner, not two

Challenge expansion reuses `DecompositionSession`, `PlanningInquiryTurn`,
`ResearchCardProposal` and `compile_decomposition_proposals`. There is no
special LLM decomposition stack for feedback problems.

### Local gate

A second unresolved challenge in another branch must not block the current
feedback branch. Therefore R2.1 adds a scoped gate rather than weakening the
global PlanningGate.

### Atomic activation

The new child cards and the challenge state transition are in one
`ResearchPatch`. The target challenge becomes `ACTIVE` only when its produced
subtree passes the local gate. Failed planning returns no authoritative DOM to
the caller.

### Tree/graph separation remains intact

`Gap` / `Conflict` stay canonical knowledge entities. `ResearchChallenge` is the
planning request. The new children remain ResearchDOM history nodes.

## Real BCC/XRD fixture

Source problem:

`residual_stress_not_excluded`

Planning dialectic:

1. Q1: what must be demonstrated to exclude residual stress as an alternative explanation?
2. A1: separate composition and stress contributions to the diffraction-line position.
3. Q2: what observations can test this?
4. A2: stress-sensitive XRD evidence plus independent composition/phase evidence.

Compiled subtree:

```text
CHALLENGE
  -> QUESTION: separate stress vs compositional shift?
      -> METHOD_VIEW: stress-sensitive XRD comparison
          -> TASK: corpus.search for XRD evidence
      -> TASK: evidence.verify independent matrix-composition evidence
```

Before decomposition:

`local PlanningGate = FAIL / NON_EXECUTABLE_LEAF`

After decomposition:

- local cards: 5 including CHALLENGE root;
- leaves: 2;
- executable leaves: 2;
- local gate: PASS;
- global gate in fixture: PASS;
- CHALLENGE card: ACTIVE.

Artifact:
`artifacts/researcher_r2_1/bcc_challenge_decomposition_demo.json`

## Tests

New R2.1 tests: 6/6 PASS.

Selected planning/knowledge suite: 30/30 PASS.

Full Researcher suite after R2.1: 389 tests total, 4 known baseline failures
(2 Guard, 2 LocalCorpus), identical in class to the previously recorded debt.
No new failure class was introduced.

Policy/runtime gates:

- capability runtime compiler: PASS, hash `b96fcb4341080bbc6d2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`;
- route runtime compiler: PASS, hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`;
- `compileall`: PASS;
- `git diff --check`: PASS.

## Remaining boundary

R2.1 only makes Gap/Conflict feedback locally executable. It does not yet
resolve the underlying knowledge entity when tasks complete.

R2.2 should add:

```text
Conflict/Gap
 -> Challenge subtree execution
 -> new Evidence / ClaimAssessment
 -> resolution projection
 -> ResearchChallenge RESOLVED | REOPENED
 -> CHALLENGE COMPLETED | ACTIVE/BLOCKED
```

Conflict-specific decomposition also needs richer required outputs than a Gap:
aligned scope, evidence polarity comparison and substantive-vs-scope-dependent
resolution.
