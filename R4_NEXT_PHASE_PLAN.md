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
- [x] R4 targeted: 111/111 PASS.
- [x] Full Researcher: 588 total / 584 PASS / same four TD-015 baseline failures.
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

## Discussion checkpoint — hypothesis verification cycle and production semantic trace

### Hypothesis research direction (future, not part of current L3B runtime gate)

The next scientific abstraction after grounded dialogue is an append-only hypothesis verification case, not a new confidence scalar:

```text
Problem/Gap
→ HypothesisRevision
→ VerificationPlan
→ ResearchChallenge / evidence / computation
→ grounded review branches
→ HypothesisAssessment
→ retain | qualify | revise | split | reject | open
→ next revision/iteration
```

Implementation should be preceded by the virtual E2E suite in `RESEARCHER_FUTURE_HYPOTHESIS_VERIFICATION_CYCLE.md`.

New future debt:

- TD-048 `HypothesisCase` / revision / verification lifecycle;
- TD-049 evidence independence/dependency lineage;
- TD-050 source-bounded EvidenceDigest and hypothesis evidence-link projection.

Do not fold this into L3B provider work. L3B should first collect real semantic traces useful for calibrating hypothesis/response semantics.

### Production semantic trace execution modes

The current sandbox cannot resolve external DNS. Therefore:

```text
Mode A: direct local
  portable Linux x86_64 OpenCode
  + locally reachable/offline semantic backend

Mode B: remote production trace pack
  Harness compiles exact DDC/DQC/ADC/RPB/TEX
  → user executes unchanged pack on production OpenCode host
  → returns non-secret trace artifacts
  → Harness validates PER/IQT/ARG and grounding
```

Mode B is preferred for cloud-only provider configurations because credentials never leave the production host.

Reference: `OPENCODE_PRODUCTION_SEMANTIC_TRACE_HANDOFF.md`.

### Immediate user-supplied OpenCode artifact

Preferred upload:

1. portable Linux x86_64 OpenCode executable/archive matching intended production version;
2. `opencode --version` or equivalent build metadata;
3. sanitized OpenCode provider/model config;
4. exact command known to work on the target host;
5. if target production is ARM64, optionally also the exact ARM64 production artifact/build metadata so both deployment and sandbox traces can be fingerprinted.

Do not include API keys or tokens.

## Immediate execution boundary — user-host production acceptance package

The next step is now an external execution loop, not additional speculative role architecture.

1. deploy the supplied complete Harness checkpoint on the real OpenCode host;
2. confirm clean Git/package identity and OpenCode CLI identity;
3. run deterministic R4/gates/full baseline and named L3/L3B edge suite;
4. require `existing.opencode_tribunal_role` to be execution-ready;
5. run the machine acceptance command in `REMOTE_ACCEPTANCE_README_FIRST.md`;
6. return `production_001` trace plus three unchanged-model/config variability runs;
7. review real traces before modifying response ownership, observer equivalence or Advocate semantics.

Two virtual-E2E defects were fixed before this handoff:

- ANSWER TEX previously did not guarantee exposure of the exact generated Q1/Q2; current TEX 1.1 carries `question_turn_id` and the question IQT material explicitly.
- provider output was previously specified only by schema identifier; current TEX embeds and fingerprints the machine-readable `output_contract`.

Remote acceptance is observation-only. The OpenCode agent must not repair code or broaden evidence while testing. Any proposed fix is a separate next iteration.
