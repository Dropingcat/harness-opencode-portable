# Next Phase Plan

## Phase P2 — Live Native Desktop Plugin

Goal: prove the actual OpenCode host boundary.

Acceptance:
1. clean installation into supported OpenCode Desktop;
2. legacy plugin conflict detection;
3. `harness_status` visible and callable;
4. `harness_run` visible and callable;
5. ToolContext -> HostContext/WorkspaceRef exact normalization;
6. bridge hello/health;
7. plugin/core protocol negotiation;
8. cancel propagation;
9. doctor JSON report;
10. package/uninstall/reinstall/rollback.

No Tribunal semantic switch yet.

## Phase P3 — Read-only semantic smoke

Goal: activate reverse `semantic.execute` safely.

- one read-only generic worker;
- no Harness tools in worker;
- no mutating tools;
- explicit timeout/cancel;
- provider/model/session IDs recorded;
- credentials remain host-local;
- structured output optional and Core-revalidated;
- negative tests for auth failure, malformed output, recursion, host unavailable.

## Phase P4 — Tribunal plugin transport

Keep RPB/TEX/PER unchanged.

- plugin provider candidate;
- fresh preflight/binding;
- Q1/A1;
- grounding;
- graph admission;
- Q2 only on admitted novelty;
- conditional Advocate;
- 3 variability runs.

No silent fallback to CLI.

## Phase P5 — Writer/Coder convergence

Replace duplicated OpenCode semantic invocation with the same SemanticExecutionRequest/Result path.

Do not merge module authority.

## Phase P6 — Calibration and live evidence

Measure:
- false grounding;
- MODEL_PRIOR leakage;
- scope drift;
- false Q2 novelty;
- over-defend vs CONCEDE;
- provider/model variability;
- retry/cancel behavior.

## Phase P7 — Scientific architecture

Using live traces:
- ResponseAssignment;
- multidisciplinary ClaimReviewCase;
- HypothesisCase lifecycle;
- evidence independence;
- EvidenceDigest.

## Release rule

A host/plugin release is `stable` only after clean install, upgrade, rollback, host probes, semantic smoke and packaged E2E for certified OpenCode versions.
