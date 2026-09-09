# Adaptive Control Environment — normative v0.3

## 1. Purpose
Writer Core MUST NOT become an expert system that encodes semantic decisions in a growing forest of if/else rules. Code defines the world, legal actions, invariants, observations and transaction boundaries. The LLM remains the semantic decision maker inside that environment.

> **Code constrains. LLM interprets. Validators observe consequences. State exposes the next affordances.**

## 2. Four classes of control
Every rule MUST be classified as one of:

1. `HARD_INVARIANT` — cannot be violated: unknown identifiers, illegal authority mutation, broken dimensionality, unresolved hard reference, forbidden source fabrication.
2. `CONSTRAINT` — default boundary that MAY be overridden only by an explicit typed decision: insufficient evidence for a strong formulation, frozen section, required review.
3. `SIGNAL` — observation returned to the model: sentence complexity, unusual nominalization, possible topic jump, parser disagreement.
4. `LEARNED_PREFERENCE` — adaptive prior learned from accepted/rejected episodes: preferred construction, typical paragraph density, author-specific lexical tendency.

A `SIGNAL` MUST NOT silently become a hard rule. A `LEARNED_PREFERENCE` MUST NEVER mutate epistemic truth.

## 3. Affordance routing
Router output is normally an `AffordanceSet`, not one predetermined semantic action.

```text
state + policy + diagnostics + strategy memory
        -> EnvironmentBuilder
        -> {constraints, signals, affordances, unavailable_actions}
        -> LLM proposal
        -> TransactionGate
        -> validators
        -> updated state
```

Only hard mechanical operations MAY be routed directly, e.g. rebuild a stale generated figure, reject an invalid ID, or resolve a deterministic cross-reference.

## 4. Adaptive decomposition
Writing Decomposition DAG is a revisioned hypothesis, not immutable scripture. LLM MAY propose graph patches such as splitting an ArgumentNeed, changing a DiscourseNeed, or requesting research. Code validates graph integrity, budget, authority and closure before commit.

## 5. Strategy memory
The system MAY learn routing priors from episodes:

`state_signature -> proposed_action -> validator_delta -> human_verdict -> cost`.

Prior success affects ranking of future affordances but never removes alternatives unless policy does so.

## 6. Anti-hardcoding test
For every new heuristic ask:
- Does it protect an invariant? Keep it in code.
- Does it merely predict a good semantic choice? Emit a signal or learned prior.
- Could a legitimate context require the opposite action? It MUST NOT be a hard decision rule.
- Can an LLM choose between bounded alternatives after receiving structured context? Prefer affordances.
