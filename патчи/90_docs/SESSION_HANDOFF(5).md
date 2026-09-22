# SESSION HANDOFF - R4.4 L3A -> R4.4 L3B

Date: 2026-09-13

## Canonical boundary

Current HEAD:

`2db82d15a1781f506e882f441a13deb17de2f146`

`researcher: close r4.4 l3a milestone boundary`

Feature commit:

`8b15c1384c5d73774e59be0a9258b1b11d7e1fb9`

`researcher: bind bounded tribunal dialogue providers`

The Git working tree must be clean before continuation.

## What R4.4 L3A completed

The bounded Tribunal execution path is now explicit and replayable:

```text
DQC/1.1
  questioner role
  addressed answer role
        -> RoleProviderBinding (RPB)
        -> TribunalExecutionEnvelope (TEX)
        -> logical runtime tool/provider
        -> child Job / Attempt
        -> ProviderExecutionReceipt (PER)
        -> IQT / ARG
        -> ArgumentGraph admission
        -> DialecticObserver / branch control
```

Role, provider and runtime tool are separate authorities. Provider selection uses shared capability/provider/runtime registries and checks capability, role kind, contract namespace, live probe/current health, runtime binding and executor cardinality. A stale binding cannot silently switch provider.

Process-boundary Q1/A1/Q2/A2 is E2E-tested through the existing Job/Attempt runtime. Runtime timeout/failure, deterministic output rejection and semantic OPEN remain distinct states.

## Important live-E2E defect that changed the contracts

A DQC originally identified only the questioner. Live execution showed that deriving the respondent from the target argument can make a Skeptic ask and answer its own question. DQC is therefore now `dialectic-question-contract/1.1` and carries explicit `answer_role_id`. Legacy DQC/1.0 is not replayed by guessing the respondent; it must be recompiled from branch context.

This fixes one dialogue turn. It does not solve global response ownership.

## Future architecture opened by the responder problem

### TD-046 - response ownership / Defender-Advocate arbitration

Do not add a permanent Defender persona yet. The likely abstraction is `ResponseAssignment`, separating:

- semantic role/competence;
- Claim-facet or position ownership;
- response function (`EXPLAIN / DEFEND / QUALIFY / CONCEDE / REFER / REQUEST_EVIDENCE`);
- optional conditional Advocate activation;
- selected responder plus reason codes/policy identity.

Provider binding must happen only after semantic responder ownership is determined.

### TD-047 - multidisciplinary Claim fork/join

One canonical Claim may require several discipline/method facets. Future review should preserve one root `CLM-*` and create review projections/branches such as crystallography, causality/kinetics and measurement/statistics. A future `ClaimReviewJoinProjection` must rejoin by coverage, dependencies, conflicts and blocking state, never by vote or averaged confidence.

See `RESEARCHER_R4_4_FUTURE_RESPONSE_OWNERSHIP_MULTIDISCIPLINARY_REVIEW.md`.

## Production provider state

A production provider is registered under shared authority:

`existing.opencode_tribunal_role`

with capability:

`tribunal.role.execute`

and logical tool:

`tribunal_role`.

In the current environment the launcher is implemented but the shared preflight reports the provider unavailable/degraded because the `opencode` executable is absent. Therefore L3A proves execution/binding/process contracts, not production scientific LLM review quality.

## Acceptance at closure

- R4 targeted: 104/104 PASS.
- Full Researcher: 581 total / 577 PASS / same four TD-015 failures only.
- runtime compiler PASS: `8910fd61122b450212d5bc459cdb52acdc02aa3cf6d87a37c5eaa3778e3cdfef`.
- capability compiler PASS: `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`.
- compileall PASS.
- git diff --check PASS.

Known baseline TD-015 remains 2 Guard + 2 LocalCorpus failures.

## Recovery/package

Milestone:

`packages/RESEARCHER-R4.4-L3A-PROVIDER-BINDING-DIALOGUE-001.zip`

SHA256:

`f1c3c831e3d6e34206d166fa77571512738acb8ab7ea2d4f10511d37bfeed221`

Complete Git bundle:

`recovery/HARNESS-R4.4-L3A-COMPLETE-2026-09-13.bundle`

SHA256:

`89e81fb3c8913e6f5ca06df97565e67494bf19d371d3e804eab603e594cfcb90`

## Next hard boundary - R4.4 L3B

Do not implement TD-046/047 yet unless production traces prove they block L3B.

First:

1. run shared preflight in an environment with one genuinely available semantic provider;
2. execute one production Q1/A1 branch through RPB/TEX/PER;
3. persist IQT/ARG and admit ARG to ArgumentGraph before observation;
4. continue Q2 only from an admitted new issue surface;
5. execute one conditional Advocate through the same provider-binding path;
6. compare live semantic failures/observer signals to deterministic subprocess fixtures;
7. keep provider failure/rejection distinct from epistemic OPEN.

After those traces exist, revisit TD-046 responder ownership and TD-047 multidisciplinary fork/join with observed cases rather than inventing policy from diagrams alone.
