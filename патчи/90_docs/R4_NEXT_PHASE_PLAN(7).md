# R4 Next Phase Plan — after L3B grounded dialogue + live conditional Advocate structural slice

Date: 2026-09-13
Status: grounding-aware semantic output and conditional Advocate process execution implemented; true production semantic provider execution remains environment-blocked.

## Completed through current L3B structural slice

```text
R3.5 ReviewWorkField
-> R4.1 TribunalCompositionPlan
-> R4.2 EvidenceSlice
-> R4.3 RoleInstructionPack + independent InquiryContract
-> R4.4 L1 DialecticObserver / bounded control
-> R4.4 L2a ArgumentGraph + conditional Advocate
-> R4.4 L2b generic DDC + DQC + branch history/replay
-> R4.4 L3A RoleProviderBinding + TEX + Job/Attempt + PER
-> R4.4 L3B response grounding + live conditional Advocate process path
```

## L3B structural/process acceptance complete

Pre-production checkpoint: `8204ce6bcbca56c42d6e4fb5ec458c2e1d71e99e`.
Milestone: `RESEARCHER-R4.4-L3B-PREPROD-GROUNDED-DIALOGUE-001.zip` (SHA256 `1ba3840813ccec2709288470c10852b4e9837a6b025ac157b0f2a9c35cf7bcf1`).

- [x] `ArgumentArtifact` records typed response grounding.
- [x] Disclosed evidence/target, prior argument/turn, explicit assumption, visible derivation and MODEL_PRIOR are distinct.
- [x] MODEL_PRIOR cannot masquerade as evidence or carry fake source refs.
- [x] Specialist non-OPEN model-prior-only response creates blocking research debt.
- [x] Live answer schema upgraded to grounding-aware `tribunal-answer-draft/1.1` while structural legacy 1.0 remains parse-compatible.
- [x] Conditional Advocate uses shared `RoleProviderBinding` with `execution_kind=DEFENSE` and ADC authority.
- [x] Advocate TEX is branch-bounded and contains no hidden sibling material.
- [x] Advocate executes through existing Job/Attempt/PER process boundary.
- [x] Grounded live QUALIFY produces `REPLIES_TO + DEFENDS`.
- [x] MODEL_PRIOR-only `DEFEND` is converted to `REQUEST_EVIDENCE`; no `DEFENDS` edge is created.
- [x] Hidden sibling grounding/citation is rejected as runtime `REJECTED`.
- [x] Live Advocate response can be admitted into a new ArgumentGraph revision.
- [x] R4 targeted: 109/109 PASS.
- [x] Full Researcher: 586 total / 582 PASS / same four TD-015 baseline failures.
- [x] runtime/capability compiler + compileall + `git diff --check` PASS.

## Production semantic completion gate — still OPEN

The configured production provider `existing.opencode_tribunal_role` is currently:

```text
implemented = true
available = false
status = degraded
reason = missing:opencode
```

Therefore the current slice proves contracts, traceability, grounding and process execution but does not prove scientific quality of an actual OpenCode/LLM Tribunal worker.

When an authorized semantic provider is execution-ready, run without changing the contracts:

1. real Skeptic Q1 -> specialist A1 through DDC/DQC/RPB/TEX/PER;
2. verify provider honestly labels evidence vs MODEL_PRIOR grounding;
3. observer admits only genuinely new issue surfaces;
4. real Q2 only against an admitted new surface;
5. material attack activates live conditional Advocate;
6. real Advocate DEFEND/QUALIFY/CONCEDE/REQUEST_EVIDENCE/OPEN;
7. test hallucinated refs, hidden refs, false closure and rhetorical defense;
8. calibrate no-progress and issue equivalence from real traces (TD-042/044).

## Response ownership remains intentionally above DQC — TD-046

`answer_role_id` addresses one turn. It does not determine scientific ownership of a Claim facet.

Future target:

```text
ResponseAssignment
  root_claim_id
  review_case_id
  facet_id
  position/argument ownership
  addressed semantic role
  response_function
    EXPLAIN / DEFEND / QUALIFY / CONCEDE / REFER / REQUEST_EVIDENCE
  optional conditional Advocate
  reason codes / policy fingerprint
```

Response ownership and response grounding are orthogonal. A correctly assigned specialist can still give an ungrounded answer; an Advocate can be evidence-grounded or merely rhetorical.

## Multidisciplinary Claim review — TD-047

Keep one canonical Claim and one review case:

```text
CLM-X
└── ClaimReviewCase
    ├── crystallography facet -> independent DBR/Q-A/ARG history
    ├── kinetics/causality facet -> independent DBR/Q-A/ARG history
    └── measurement/statistics facet -> independent DBR/Q-A/ARG history
```

Future `ClaimReviewJoinProjection` reports:

- coverage;
- blocking/open state;
- dependencies;
- conflicts;
- synergy / prerequisite closure;
- need for an explicit integration-review branch.

It never votes or averages role confidence and never mutates Claim truth directly.

## Other open debt

- TD-036 domain role-pack admission;
- TD-038 universal cross-layer traceability/index;
- TD-039 semantic blind-provenance projection;
- TD-041 PortableRoleDOM;
- TD-042 live observer calibration;
- TD-044 semantic issue facet/equivalence + Writer proposal bridge;
- TD-046 response ownership / Defender-Advocate arbitration;
- TD-047 multidisciplinary Claim fork/join.

## Stop rule

Do not implement learned responder selection, automatic multidisciplinary join or permanent Defender before production semantic Q/A/Advocate traces exist. The current architecture is sufficient to collect those traces without confusing model memory with evidence.
