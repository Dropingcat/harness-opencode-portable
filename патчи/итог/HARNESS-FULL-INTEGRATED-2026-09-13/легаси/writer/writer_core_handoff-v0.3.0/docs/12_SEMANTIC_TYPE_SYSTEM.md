# 12. Semantic Type System

## Purpose

Prevent invalid semantic substitutions before prose generation. The type system does not prove truth; it constrains what kind of claim may satisfy a slot or participate in an argument/pattern.

## Core types

```text
Observation<T>
Measurement<T>
QuantitativeClaim<T>
Comparison<A,B>
Association<A,B>
CausalClaim<A,B>
Mechanism<A,B,M>
Definition<T>
Classification<T>
MethodClaim<M>
Interpretation<T>
HistoricalAttribution<T>
Recommendation<T>
NormativeClaim<T>
```

Additional modifiers:

```text
Scoped<T, Scope>
Qualified<T, QualifierSet>
Uncertain<T, UncertaintyModel>
Derived<T, DerivationRef>
```

## Rules

- `Association<A,B>` cannot satisfy `CausalClaim<A,B>` slot without admitted derivation.
- `Measurement<T>` may support `QuantitativeClaim<T>` only when unit/dimension/scope match.
- `Interpretation<T>` must not be rendered as `Observation<T>`.
- `Recommendation<T>` requires explicit recommendation policy and evidence class.
- `Definition<T>` is not evidence for a causal mechanism.
- `HistoricalAttribution<T>` requires attribution/source provenance, not experimental evidence.

## Subtyping and coercion

Only explicit safe coercions are allowed, e.g. `Measurement<T> -> Observation<T>` under same scope. Any strength-increasing coercion is forbidden by default.

## Diagnostics

```text
TYPE_MISMATCH
UNSAFE_SEMANTIC_COERCION
MISSING_DERIVATION
SCOPE_TYPE_MISMATCH
UNIT_TYPE_MISMATCH
ARGUMENT_ROLE_MISMATCH
```

The semantic type checker runs before realization and again on back-extracted claims after realization.
