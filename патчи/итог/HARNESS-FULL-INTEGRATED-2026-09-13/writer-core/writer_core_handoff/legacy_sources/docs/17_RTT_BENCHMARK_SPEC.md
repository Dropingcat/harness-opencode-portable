# 17B. RTT Benchmark Specification

RTT is itself an imperfect component and must be benchmarked.

## Mutation families

Positive controls:
- exact realization;
- safe paraphrase;
- harmless sentence reordering preserving argument.

Negative controls:
- unauthorized claim;
- claim omission;
- scope expansion/narrowing;
- modality upgrade/downgrade;
- causality upgrade/loss;
- qualifier loss;
- negation flip;
- entity substitution;
- temporal shift;
- numeric/unit/precision drift;
- uncertainty loss;
- evidence misattribution;
- compression-induced overclaim.

## Metrics

Per error class:
- precision;
- recall;
- false blocking rate;
- repair success after N iterations;
- calibration/inconclusive rate where model-assisted.

## Gates

Hard-error recall thresholds are stricter than prose/style metrics. RTT cannot graduate to production based on aggregate F1 that hides weak rare classes.
