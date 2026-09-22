# Development Tracker — Current

Статус: planned/current priorities. Новые DEV-ID не заменяют historical WS/TD.

| ID | Result | Acceptance / dependency |
|---|---|---|
| DEV-01 | Reproducible current baseline | Exact tree/commit/package hashes + baseline commands/results |
| DEV-02 | Documentation aligned with baseline | Every “implemented” claim links to code/test evidence; inventory/links checked |
| DEV-03 | Native Desktop P2 | Real plugin load, tools, HostContext, handshake, health/cancel; no double registration; CLI/DB not mandatory |
| DEV-04 | Safe semantic smoke | Read-only worker, recursion isolation, timeout/cancel, output schema, negative cases |
| DEV-05 | Unified semantic transport | Tribunal first, then Writer/Coder use SemanticExecutionRequest/Result; no silent transport switch |
| DEV-06 | Reliable cross-module dispatch | Live peer dispatch, durable outbox, reconciliation, stable source identity |
| DEV-07 | Research contract hardening | TD-017/026–028/032–035 with migration/stale/replay/negative tests |
| DEV-08 | Tooling/memory/skills reconciliation | Distinguish implemented vs connected vs live-ready across capsules/tools/skills |
| DEV-09 | Semantic acceptance/calibration | Live traces: grounding, false closure, Q2 novelty, Advocate, variability |
| DEV-10 | Legacy retirement | Separate sunset criteria for legacy hook and CLI; rollback retained |
| DEV-11 | Response ownership | ResponseAssignment after live traces; Defender remains response function |
| DEV-12 | Multidisciplinary ClaimReviewCase | One Claim, independent facets, non-voting join, dependencies/conflicts/synergy |
| DEV-13 | Hypothesis verification lifecycle | HypothesisCase revisions, competing hypotheses, discriminating tests, evidence independence/digest |

## Immediate critical path

`DEV-03 -> DEV-04 -> DEV-05 -> DEV-09`

Scientific architecture DEV-11..13 can continue in virtual E2E/design, but production status cannot be claimed without the host/semantic gates.
