# Linguistic Round-Trip Validation

Linguistic RTT strengthens semantic RTT by comparing normalized actionable linguistic fields before and after realization.

## Canonical digest dimensions
- predicate identity;
- participant roles;
- entity/event references;
- scope and conditions;
- negation scope;
- quantifiers;
- modality/hedging;
- causal force;
- temporal/aspectual status;
- comparison magnitude/direction;
- quantity bindings;
- attribution/source voice;
- presuppositions;
- discourse relation.

## Required mismatch classes
`PREDICATE_SHIFT`, `PARTICIPANT_SHIFT`, `REFERENCE_SHIFT`, `SCOPE_EXPANSION`, `SCOPE_LOSS`, `NEGATION_FLIP`, `QUANTIFIER_SHIFT`, `MODALITY_UPGRADE`, `MODALITY_LOSS`, `CAUSALITY_UPGRADE`, `TEMPORAL_SHIFT`, `COMPARISON_DRIFT`, `QUANTITY_DRIFT`, `ATTRIBUTION_SHIFT`, `PRESUPPOSITION_INJECTION`, `DISCOURSE_RELATION_SHIFT`, `REFORMULATION_DRIFT`.

## Levels
- micro: clause/sentence;
- meso: paragraph/argument;
- macro: section/abstract/conclusion/compression.

## Repair
Every semantic repair MUST be followed by a new RTT. Repair loops are bounded. Unresolved high-impact mismatch becomes a Blocker.
