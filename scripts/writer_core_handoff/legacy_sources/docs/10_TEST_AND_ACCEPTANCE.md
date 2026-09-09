# 10. Test & Acceptance v0.2

## Test pyramid

1. Schema/model tests.
2. Deterministic validator unit tests.
3. Property tests for graph/revision/invalidation.
4. Golden semantic mutation fixtures.
5. Integration build scenarios.
6. Catastrophic scenario tests.
7. Export parse-back and visual QA.
8. Forensics calibration/OOD benchmarks (separate track).

## Required negative fixtures

Every semantic/quantitative/policy validator has at least one fixture that must fail for the intended reason code; generic FAIL is insufficient.

## Release DoD

- no release blockers;
- critical dependency graph fresh or explicitly waived by approved Decision;
- RTT thresholds met;
- quantitative/artifact/citation integrity pass;
- required review/expert gates pass;
- reproducible build manifest complete;
- DOCX/PDF export QA pass;
- catastrophic scenario suite pass.

## Mutation testing

Critical validators should be mutation-tested: deliberately remove qualifiers, alter digits/units, change causal verbs, swap citations and break references. A validator suite that only validates known-good fixtures is not evidence of robustness.
