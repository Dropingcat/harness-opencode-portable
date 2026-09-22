# Researcher R4.4 L1 — Pipeline Audit

Date: 2026-09-13

## Audited path

```text
R3.5 ReviewWorkField
-> R4.1 TribunalCompositionPlan
-> R4.2 EvidenceSlice
-> R4.3 independent InquiryTurn + ArgumentArtifact
-> R4.4 DialecticObservation
-> DialecticControlDecision
-> optional explicit EmergentIssue -> Gap
-> existing ResearchChallenge
```

## Authority audit

| Step | Produces | May mutate Claim/Graph truth? | Owner |
|---|---|---:|---|
| R4.3 role worker | ArgumentArtifact | No | semantic work plane under contract |
| Issue proposal | typed possible complexity | No | semantic observer/role |
| R4.4 observer | observation + control action | No | deterministic control plane |
| issue resolution proposal | local issue closure proposal | No | semantic response, validated by code |
| Gap projection | Gap value object | Not by itself | explicit admission caller/reducer |
| ResearchChallenge | research request | No Claim truth mutation | existing reconciliation path |

No new truth writer or scheduler was introduced.

## Historical audit

Current bounded turn sequence is explicit:

```text
FIRST_PASS_ASSESSMENT
-> CHALLENGE
-> QUESTION
-> ANSWER
-> QUESTION_ON_ANSWER
-> REBUTTAL
```

Every child turn must point to its immediate historical parent. Duplicate/invalid transition chains fail closed.

## Novelty/progress audit

Progress may come from:

- new issue signature;
- prior issue resolution;
- resolved-issue reopen;
- evidence-frontier change;
- argument-position change.

Repeated issue with none of the above increments no-progress. Exact issue signature is deterministic and content-addressed.

Known limitation: semantic paraphrases are not equivalence-collapsed (TD-044).

## Boundary audit

Controller distinguishes:

- `STOP_NO_PROGRESS` — repetition;
- `STOP_OPEN` — valid unresolved state with no actionable continuation;
- `STOP_DEPTH_LIMIT` / `STOP_TURN_LIMIT` / `STOP_BUDGET_LIMIT` — resource boundaries;
- `REQUEST_LOCAL_RESEARCH` — missing evidence/method information needs Researcher;
- `RECOMPOSE_PANEL` — missing role capability;
- `STOP_CONVERGED` — local tracked dialectic issues resolved / bounded chain complete under current policy.

These states are not interchangeable.

## E2E audit result

The E2E uses an XRD ambiguity branch and demonstrates:

1. independent XRD role exposes method ambiguity;
2. skeptic creates a typed challenge;
3. Q1 asks for discriminating observation;
4. A1 introduces an untested assumption;
5. Q2 targets exactly that newly exposed surface;
6. A2 cannot close it and emits typed additional-evidence request;
7. controller routes to local research;
8. issue projects to existing Gap;
9. existing `challenge_from_gap()` creates ResearchChallenge;
10. no Claim/GraphEdge truth state is overwritten by the dialogue.

## Acceptance results

- R4 targeted: 67/67 PASS.
- Full Researcher: 544 total / 540 PASS / same four TD-015 failures.
- Runtime compiler: PASS, unchanged hash.
- Capability compiler: PASS, unchanged hash.
- compileall: PASS.

## Open seams

- TD-037 live provider binding;
- TD-038 universal traceability/replay;
- TD-042 live interaction-observer calibration;
- TD-043 disclosure + branching argument graph;
- TD-044 semantic issue identity/equivalence;
- durable observation/decision persistence and explicit Gap admission wiring.
