# Writer artifact boundary v1

Canonical flow:

`Researcher verification -> Writer projection -> Draft -> Traceability -> Semantic RTT -> ReleaseDecision`

Authority is deliberately split:

- Researcher owns evidence verdicts and numerical/formula verification.
- Writer owns realization, citation traceability, semantic round-trip checks, and release aggregation.
- The Writer adapter is read-only. It executes `scripts/researcher/verify_claims.py` without `--apply`, verifies that the DOM hash is unchanged, and rejects verdicts outside the controlled vocabulary.
- Release is conjunctive. `EVIDENCE`, `TRACEABILITY`, and `SEMANTIC_ROUNDTRIP` are independent gates. No later PASS can erase an earlier FAIL.

## Artifacts

### ResearchVerificationEnvelope

Schema: `writer.research_verification/1.0`.

Carries the source DOM hash, Researcher authority path, controlled verdicts, confidence and numeric/formula/guard details. It is a projection, not a new authority record.

### ReleaseDecision

Schema: `writer.release_decision/1.0`.

Contains three gate results, blocking gate names, immutable input hashes and explicit authority ownership. `release_allowed` is true only when all required gates pass.

## Evidence policy

`strict` is the default for scientific release and accepts only `SUPPORTED` Researcher verdicts. `qualified` may also accept `AMBIGUOUS`; this is an explicit caller choice and does not rewrite the underlying verdict.

## Citation markers and RTT

Citation markers are presentation metadata, not claim semantics. The release gate strips `[C-*]` and `[S-*]` markers only from the temporary RTT input so identifier digits cannot be misread as scientific numbers. The original draft and DOM are never modified.
