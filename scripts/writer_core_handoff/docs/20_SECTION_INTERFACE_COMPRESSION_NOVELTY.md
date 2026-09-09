# 20. Section Interfaces, Compression, Novelty & Contributions

## Section interface contracts

A section declares `requires`, `provides`, `exports`, `local assumptions`, `critical artifacts` and completion criteria.

Example:

```text
Methods provides METHOD_1, UNCERTAINTY_MODEL
Results requires METHOD_1
Discussion requires RESULT_CLAIMS
Conclusion imports only CONCLUSION_ELIGIBLE claims
```

Missing provided dependency blocks dependent section compilation.

## Claim visibility

`LOCAL`, `SECTION`, `DOCUMENT`, `ABSTRACT_ELIGIBLE`, `CONCLUSION_ELIGIBLE`, `DEFENSE_ELIGIBLE`.

## Compression safety

Transformations chapter→conclusion→abstract→annotation require RTT with special focus on qualifier/scope/uncertainty preservation.

Errors:
- COMPRESSION_SCOPE_LOSS
- COMPRESSION_QUALIFIER_LOSS
- COMPRESSION_CAUSALITY_UPGRADE
- COMPRESSION_UNCERTAINTY_LOSS

## Expansion safety

New background/examples/generalizations are classified as `SUPPORTED_EXTENSION`, `INTERPRETIVE_EXTENSION`, `UNAUTHORIZED_EXTENSION`.

## Novelty graph

`NoveltyClaim` must link to original result claims, prior-art coverage snapshot, distinguishing relation and scope. "Впервые" without prior-art basis is release-blocking under dissertation policy.

## Contribution graph

Scientific, methodological, experimental and engineering contributions are explicit nodes linked to supporting claims/artifacts and defense positions.
