# SESSION HANDOFF - R4.4 L3B PREPROD -> production semantic L3B

Date: 2026-09-13

## Canonical boundary

Current HEAD:

`11ec08550e81874fbd991449663849fd8f604315`

`researcher: checkpoint r4.4 l3b preproduction boundary`

Feature checkpoint:

`8204ce6bcbca56c42d6e4fb5ec458c2e1d71e99e`

`researcher: ground live tribunal dialogue and advocate`

Working tree must be clean before continuation.

## What this checkpoint actually proves

The bounded dialogue runtime now preserves a traceable chain:

```text
Claim / ReviewWorkField
-> TribunalCompositionPlan / RoleInstruction
-> ArgumentGraph branch
-> DDC / DQC or ADC
-> RoleProviderBinding (RPB)
-> TribunalExecutionEnvelope (TEX)
-> logical tool + provider
-> child Job / Attempt
-> ProviderExecutionReceipt (PER)
-> IQT / ARG with typed response grounding
-> ArgumentGraph admission
-> DialecticObserver / control / ResearchChallenge
```

`who answered` and `what grounds the answer` are independent axes.

Grounding kinds include disclosed evidence/targets, prior argument/turn, derivation from visible material, explicit assumption and MODEL_PRIOR. MODEL_PRIOR is model training memory/prediction, not a source. A prior-only non-OPEN specialist response generates blocking research debt. A prior-only Advocate DEFEND is converted to REQUEST_EVIDENCE and cannot create DEFENDS.

Conditional Advocate uses the same RPB/TEX/PER authority and Job/Attempt runtime as other semantic roles. No separate Advocate runtime exists.

## Production boundary remains open

`existing.opencode_tribunal_role` is registered and implemented, but current shared preflight reports:

```text
available = false
status = degraded
detail = missing:opencode
```

Therefore process-boundary E2E is real, but semantic workers in the current acceptance run are deterministic subprocess fixtures. Do not describe this checkpoint as a completed production semantic Tribunal.

## Response ownership seam: TD-046

DQC/1.1 carries explicit `answer_role_id`; legacy DQC/1.0 is not replayed by guessing the respondent. This solves turn addressability only.

Future `ResponseAssignment` must separate:

- Claim-facet/position ownership;
- semantic role/competence;
- response function (`EXPLAIN / DEFEND / QUALIFY / CONCEDE / REFER / REQUEST_EVIDENCE`);
- optional conditional Advocate;
- reason codes/policy identity.

Do not introduce a permanent Defender persona unless live traces prove a distinct responsibility that cannot be represented as response function plus facet ownership.

## Multidisciplinary Claim seam: TD-047

Keep one canonical `CLM-*`. A future `ClaimReviewCase` owns independent discipline/method `ReviewFacet` subbranches with their own Q/A, ARG relations, evidence and provider lineage.

The join is not a vote and not an averaged confidence. `ClaimReviewJoinProjection` should expose:

- facet coverage;
- resolved/open/blocking state;
- cross-facet dependencies;
- conflicts;
- synergy/prerequisite closure;
- integration-review need;
- reducer readiness.

The Claim remains the common root so every branch can be traced back to the same scientific proposition.

## Current acceptance

- R4 targeted: 109/109 PASS.
- Full Researcher: 586 total / 582 PASS / exactly four known TD-015 failures (2 Guard, 2 LocalCorpus).
- runtime compiler PASS, hash `8910fd61122b450212d5bc459cdb52acdc02aa3cf6d87a37c5eaa3778e3cdfef`.
- capability compiler PASS, hash `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`.
- compileall PASS.
- git diff --check PASS.

## Next executable boundary

1. Run an actually available authorized semantic provider through unchanged DQC/ADC contracts.
2. Preserve RPB/TEX/PER and grounding exactly as in PREPROD.
3. Collect production traces for hallucinated refs, false grounding, false closure, Q2 novelty, refusal/evasion and Advocate rationalization.
4. Only after those traces revisit TD-046 Defender/Advocate arbitration.
5. TD-047 multidisciplinary fork/join may then be implemented as a separate non-voting review-projection layer without destructively splitting Claim identity.
