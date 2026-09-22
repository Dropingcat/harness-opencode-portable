# 06. Round-Trip Semantic Validation v0.2

RTT compares semantic input contract with semantics recovered from generated/edited/compressed text.

## Levels
- micro: sentence/paragraph;
- meso: section/argument chain;
- macro: abstract/conclusion/novelty/whole-document summaries.

## Reason codes

`EXACT`, `PARAPHRASE_SAFE`, `CLAIM_OMISSION`, `UNAUTHORIZED_CLAIM`, `SCOPE_EXPANSION`, `SCOPE_NARROWING`, `MODALITY_UPGRADE`, `MODALITY_DOWNGRADE`, `CAUSALITY_UPGRADE`, `CAUSALITY_LOSS`, `QUALIFIER_LOSS`, `NEGATION_FLIP`, `ENTITY_SUBSTITUTION`, `TEMPORAL_SHIFT`, `NUMERIC_DRIFT`, `UNIT_DRIFT`, `PRECISION_INFLATION`, `UNCERTAINTY_LOSS`, `EVIDENCE_MISATTRIBUTION`.

## Repair authority

Deterministic: formatting/crossref/exact bound value substitution.  
Bounded model repair: qualifier restoration, causality wording, sentence restructuring.  
Research/human escalation: new unsupported claim, contradiction, missing evidence, disputed interpretation.

Every repair reruns RTT. Repair loop has iteration budget; exhaustion creates Blocker.

RTT is benchmarked independently according to `docs/17_RTT_BENCHMARK_SPEC.md`.
