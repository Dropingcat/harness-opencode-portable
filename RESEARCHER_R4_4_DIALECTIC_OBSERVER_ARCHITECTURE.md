# Researcher R4.4 L1 — Dialectic Observation and Bounded Escalation

Date: 2026-09-13
Status: IMPLEMENTED L1 control substrate; live multi-role dialogue runtime remains later work.

## 1. Purpose

R4.3 proved that an admitted Tribunal role can execute independently under an exact EvidenceSlice and emit typed `InquiryTurn + ArgumentArtifact` through the existing Job/Attempt runtime.

R4.4 L1 adds the control substrate required before live adversarial dialogue is safe. The block answers:

- what process level the dialectic is currently at;
- what *new typed difficulty* appeared in the latest response;
- whether the response changed the evidence frontier or argumentative position;
- whether the exchange is making progress or merely restating the same issue;
- whether the next action is challenge, direct Q/A, question-on-answer, local research, panel recomposition, or stop;
- where hard depth/turn/token/no-progress boundaries terminate the exchange.

It deliberately does **not** infer scientific weakness by parsing prose inside control code and does **not** mutate Claim/GraphEdge truth state.

## 2. Authority boundary

```text
semantic role / bounded turn observer
        ↓ typed proposals
ArgumentArtifact + InquiryDiscovery
+ AdditionalEvidenceRequest
+ optional DialecticIssueProposal
        ↓
R4.4 deterministic observer
        ↓
DialecticObservation
        ↓
DialecticControlDecision
```

The semantic worker may propose a difficulty. Code owns:

- admissible typed issue kinds;
- novelty/repetition detection;
- process depth;
- turn/pair/token limits;
- no-progress cutoff;
- escalation routing;
- whether a follow-up is allowed.

`DialecticControlDecision` is a routing/control artifact only. It is not a verdict and cannot mutate knowledge state.

## 3. Process levels

`DialecticLevel` describes **process depth**, never confidence:

### L0 — INDEPENDENT
Role receives only its compiled first-pass slice and emits an independent `ArgumentArtifact`.

### L1 — CHALLENGE
A second admitted perspective attacks a specific justification/issue from the first pass. It must target disclosed typed artifacts, not invent a generic debate topic.

### L2 — DIRECT_QA
A concrete challenge is converted into a direct question and bounded answer. The answer is observed for new typed issues.

### L3 — QUESTION_ON_ANSWER
A follow-up question is permitted only when the answer exposed a new testable surface: new assumption, scope shift, evidence gap, method limitation, contradiction, causal ambiguity, etc.

### L4 — LOCAL_RESEARCH_ESCALATION
The dialectic has reached an evidence/capability boundary that conversation cannot legitimately close. A typed issue is projected, under explicit admission, into the existing `Gap -> ResearchChallenge -> PlanningDialectic` path.

### L5 — EXTERNAL_ESCALATION
Reserved for future human/external expert escalation or policy intervention. It is not implemented by R4.4 L1.

## 4. Emergent complexity is multidimensional

R4.4 rejects a scalar `dialogue_complexity=0.82` score. A response may be difficult for several independent reasons.

Current `EmergentIssueKind` vocabulary includes:

- `MISSING_EVIDENCE`
- `METHOD_LIMITATION`
- `POSSIBLE_COUNTEREXAMPLE`
- `SCOPE_ISSUE`
- `CAUSALITY_PROBLEM`
- `NUMERIC_DISCREPANCY`
- `ASSUMPTION_ISSUE`
- `SOURCE_PROVENANCE_ISSUE`
- `FRESHNESS_ISSUE`
- `CONTRADICTION`
- `ANSWER_EVASION`
- `ROLE_CAPABILITY_GAP`

The first nine map directly from existing R4.3 typed discoveries. Interaction-specific signals such as `ANSWER_EVASION`, `CONTRADICTION` and `ROLE_CAPABILITY_GAP` can enter only as a bounded `DialecticIssueProposal`; control code validates the proposal against the assigned AssessmentNeeds and admitted refs.

This preserves the main architecture rule:

```text
semantic model proposes meaning
code decides admissibility and routing
```

## 5. Novelty and no-progress

Iteration count alone is a poor stopping rule. R4.4 therefore tracks semantic progress from typed state changes.

An iteration counts as progress when at least one occurs:

1. a new content-addressed issue signature appears;
2. a previously tracked dialectic issue is explicitly resolved;
3. the visible evidence/reference frontier changes;
4. the admitted argument position changes.

A normalized issue signature includes:

- issue kind;
- normalized statement;
- AssessmentNeed refs;
- target/evidence refs;
- blocking flag.

Repeated copies of the same issue therefore remain historically visible but do not masquerade as progress.

Issue lifecycle is explicit and local to the dialogue. A later answer may submit `DialecticIssueResolutionProposal(RESOLVED|STILL_OPEN)` for a prior active issue signature. Code rejects unknown signatures and rejects a response that simultaneously reasserts and resolves the same issue. Resolved signatures remain in historical state; if the same issue later reappears it is marked `ISSUE_REOPENED` rather than pretending to be a brand-new difficulty. Resolving a dialogue issue counts as progress and can produce `STOP_CONVERGED` when no tracked issues remain, but it does **not** change Claim/GraphEdge truth or imply that the underlying scientific claim is true.

`no_progress_streak` is deterministic. Policy may stop the chain before the nominal turn/depth budget is consumed. New-issue fanout is never silently truncated: all issues remain observable, and exceeding the policy fanout bound produces an explicit stop reason after higher-priority blocking escalation has been considered.

## 6. Why Q2 is different from Q1

The preferred legacy form is:

```text
Q1 -> A1 -> Q2(on A1) -> A2
```

R4.4 sharpens the meaning of `Q2(on A1)`:

Q2 is admissible only if A1 creates a new target surface, for example:

- A1 introduces an assumption not present in the original argument;
- A1 changes scope;
- A1 relies on an unshown source;
- A1 leaves a competing cause unresolved;
- A1 reveals that a discriminating measurement is missing;
- A1 contradicts another admitted artifact;
- A1 fails to address the exact discriminating question (`ANSWER_EVASION` proposal).

If A1 merely repeats the original justification with no new typed issue/ref/position, Q2 is not justified by “depth for depth's sake”; the controller may stop as no-progress.

## 7. Stop and escalation semantics

Current `DialecticAction` includes:

- `CONTINUE_CHALLENGE`
- `CONTINUE_QA`
- `CONTINUE_QUESTION_ON_ANSWER`
- `REQUEST_LOCAL_RESEARCH`
- `RECOMPOSE_PANEL`
- `STOP_CONVERGED`
- `STOP_NO_PROGRESS`
- `STOP_DEPTH_LIMIT`
- `STOP_TURN_LIMIT`
- `STOP_BUDGET_LIMIT`
- `STOP_OPEN`

Important distinctions:

### `STOP_NO_PROGRESS`
The interaction repeated already-known typed issues without changing evidence or position.

### `STOP_OPEN`
A valid semantic result remains unresolved but does not expose a new actionable route under the current contract.

### `REQUEST_LOCAL_RESEARCH`
A blocking evidence/method need is explicit. Dialogue must not fabricate the missing experiment/source. The issue is eligible for explicit Gap/ResearchChallenge admission.

### `RECOMPOSE_PANEL`
The current panel lacks an admitted capability required to proceed. This is distinct from missing evidence.

### depth/turn/token stops
Resource boundaries are not epistemic conclusions.

## 8. Historical chain validation

R4.4 L1 validates the bounded linear sequence:

```text
FIRST_PASS_ASSESSMENT
-> CHALLENGE
-> QUESTION
-> ANSWER
-> QUESTION_ON_ANSWER
-> REBUTTAL
```

Each turn must point to its immediate historical parent. The runtime should also supply the explicit full-chain turn count to the observer; otherwise the observer marks the count as approximated. This prevents Q1/Q2 turns from disappearing from process-budget accounting merely because only answers produce `ArgumentArtifact`. This avoids a prompt-only conversation history whose causal lineage cannot later be replayed.

Future R4.4.x may support branching attacks, but branches must retain explicit parent links rather than rewriting a chat transcript.

## 9. Feedback into existing Researcher control loop

R4.4 does not create a second research scheduler.

An actionable `EmergentIssue` can be explicitly projected to the existing Gap contract:

```text
EmergentIssue
-> explicit admission/projection
-> Gap
-> ResearchChallenge
-> CHALLENGE ResearchCard
-> existing PlanningDialectic
-> executable TASK / retrieval / measurement / Coder work
```

The observer itself does not perform this write. A caller/reducer must intentionally invoke the projection/admission boundary.

## 10. Implemented contracts

Module: `scripts/researcher/researcher_core/tribunal_dialectic.py`

Current contracts:

- `DialecticLevel`
- `EmergentIssueKind`
- `DialecticAction`
- `DialecticPolicy`
- `DialecticIssueProposal`
- `DialecticIssueResolutionProposal`
- `DialecticIssueDisposition`
- `EmergentIssue`
- `DialecticObservation`
- `DialecticControlDecision`
- `DialecticHistory`
- `DialecticStepResult`

Current operations:

- `observe_dialectic_step()`
- `decide_dialectic_control()`
- `validate_dialectic_turn_chain()`
- `gap_from_emergent_issue()`

## 11. L1 policy defaults

Defaults are deliberately conservative and versionable in future policy:

- max process level: L3 question-on-answer;
- max turns: 6;
- max Q/A pairs: 2;
- no-progress cutoff enabled;
- maximum new issue fanout per response;
- token budget;
- blocking missing evidence may route to local research;
- follow-up requires novelty by default.

These are process policy values, not universal scientific constants.

## 12. E2E validation

The new vertical E2E exercises:

```text
R4.3 first-pass ArgumentArtifact
-> L0 observation
-> challenge permission
-> typed CHALLENGE
-> Q1 / A1
-> new ASSUMPTION_ISSUE
-> Q2(on A1)
-> A2 / typed AdditionalEvidenceRequest
-> L4 REQUEST_LOCAL_RESEARCH
-> EmergentIssue
-> explicit Gap projection
-> existing ResearchChallenge
```

The test also validates the historical parent chain and confirms that the original argument positions remain artifacts rather than being overwritten by the later exchange.

## 13. Conditional Advocate / defense boundary

Legacy Advocate semantics are retained only as a future conditional phase. Advocate is not part of every chain. A future policy may activate defense when a specific admitted challenge attacks a still-defensible prior argument and an independent defense perspective is useful.

Allowed semantic outcomes should include `DEFEND`, `QUALIFY`, `CONCEDE_LOCAL_POINT`, `REQUEST_EVIDENCE`, and `OPEN`. The defense role may not widen evidence authority or introduce unseen support. FOR/AGAINST branches remain competing typed justifications, never votes that are averaged into truth.

## 14. Current limitations

1. No live challenger/questioner/answerer worker is executed yet; R4.4 L1 tests deterministic control semantics over typed fixture artifacts.
2. Interaction-specific issue proposals and issue-resolution proposals require future live semantic-observer calibration; control code intentionally does not parse prose to detect evasion/contradiction/closure.
3. Cross-role disclosure is not yet compiled into a dedicated `DialecticDisclosureContract`.
4. Branching multi-attack graphs are not yet implemented; L1 validates a bounded linear chain.
5. Local research projection is implemented as an explicit helper, but durable admission/repository wiring remains a later integration slice.
6. L5 human/external escalation remains future work.
7. Live provider binding from TD-037 remains open and applies equally to future dialogue workers.

## 15. Complexity ladder

- **L1 current:** typed process levels, issue observation, content-addressed novelty, no-progress/depth/turn/token boundaries, explicit Gap projection, linear Q/A chain validation.
- **L2:** compiled disclosure contracts, live challenger/question/answer workers, durable dialectic chain repository, explicit question-target contracts.
- **L3:** branching argument graph, conditional Advocate/defense, local panel recomposition and research-return continuation.
- **L4:** calibrated semantic turn observers, contradiction/answer-evasion detection benchmarks, TMS/ATMS justification/nogood integration.
- **L5:** historical effectiveness/calibration and human expert insertion while control authority remains deterministic.

## 16. Non-goals

R4.4 L1 does not:

- vote on truth;
- average confidence scores;
- let the Advocate permanently defend every claim;
- let questioner/answerer widen evidence authority;
- create a second scheduler;
- infer scientific correctness from message length or eloquence;
- continue a dialogue merely because unused token budget remains.
