# 18. Quantitative & Uncertainty Engine

## Quantity model

A reported number has three distinct states:

```text
raw_value → computed_value → reported_value
```

Each carries unit, dimension, precision, rounding policy, source and derivation.

## Uncertainty

Uncertainty is first-class:
- standard uncertainty;
- expanded uncertainty;
- distribution;
- coverage factor;
- correlation/covariance;
- propagation method;
- confidence/coverage semantics where applicable.

## Formula model

Formula contains:
- symbolic expression;
- variables/constants;
- assumptions;
- validity range;
- dimensional constraints;
- implementation/script reference;
- derivation references.

Displayed formula, symbolic formula and numerical implementation are checked for consistency.

## Hard errors

- UNIT_DRIFT
- DIMENSION_MISMATCH
- NUMERIC_DRIFT
- PRECISION_INFLATION
- ROUNDING_POLICY_VIOLATION
- UNCERTAINTY_LOSS
- UNCERTAINTY_SCOPE_MISMATCH
- FORMULA_IMPLEMENTATION_MISMATCH
- VARIABLE_UNBOUND

Numbers, DOI, standard numbers and equations are bind/select entities; free generation is forbidden in high-rigor policy.
