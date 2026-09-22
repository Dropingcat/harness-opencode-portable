# R4.4 L3B Remote OpenCode Acceptance Boundary

Date: 2026-09-13

## Feature boundary

- Feature commit: `c47baad814c946cfd3dcdd1259498f474f304b6f`
- Feature subject: `researcher: package remote opencode semantic acceptance`
- Milestone package: `RESEARCHER-R4.4-L3B-REMOTE-ACCEPTANCE-001.zip`
- Milestone SHA256: `2d76cd361c5aa034764a79cdaa31413b9ad5e051e29b9fc3506d1cb56bb79086`

## Frozen local acceptance baseline

- R4 targeted: 111/111 PASS.
- Remote/trace targeted suite: 16/16 PASS.
- Full Researcher: 588 total / 584 PASS / 4 known TD-015 failures only.
- Known TD-015 failures: 2 Guard + 2 LocalCorpus.
- Runtime compiler: PASS; policy hash `8910fd61122b450212d5bc459cdb52acdc02aa3cf6d87a37c5eaa3778e3cdfef`.
- Capability compiler: PASS; policy hash `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`.
- `compileall`: PASS.
- `git diff --check`: PASS.

## Production semantic status

The package is ready for remote production-semantic acceptance against a real OpenCode CLI/provider. The local environment does not currently provide a reachable production semantic provider. Process-level execution, provider binding, bounded envelopes, materialized question traceability, output contracts, grounding, live conditional Advocate structure, edge cases, and report tooling are implemented and locally tested.

A remote run MUST preserve the supplied contracts and return trace artifacts. A failed production run is evidence; the remote agent must not edit Harness to make the test pass.
