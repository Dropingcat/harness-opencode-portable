# Linguistic Expert and Escalation

## Goal
Use a stronger model only where lower tiers cannot safely resolve a linguistically meaningful ambiguity.

## Escalation triggers
- competing coreference targets with semantic impact;
- nested negation or quantifier scope;
- ambiguous attribution or source voice;
- causal-language interpretation affecting claim type;
- implicit warrant / enthymeme reconstruction;
- presupposition that would introduce a new factual commitment;
- cross-paragraph discourse ambiguity;
- macro compression/expansion of critical claims;
- disagreement between linguistic RTT analyzers;
- weak model requests `REQUEST_EXPERT`.

## Diagnostic capsule
Tier 2 receives only relevant material:
- target span and local clause window;
- resolved entities and candidate references;
- semantic contract;
- syntax/clause structure;
- relevant claims/evidence refs;
- ambiguity description;
- allowed verdict schema.

## Output
Strong model returns a structured resolution with selected interpretation, rejected alternatives, reason codes and residual uncertainty. Code applies graph changes.

## Independence
For defense positions, novelty claims or major causal conclusions policy MAY require two independent Tier-2 analyses. Agreement is not proof; disagreement escalates to human review.
