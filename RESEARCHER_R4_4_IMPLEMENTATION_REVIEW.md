# Researcher R4.4 L1 — Implementation Review

Date: 2026-09-13
Scope: deterministic dialectic observation, novelty/no-progress control, issue lifecycle, bounded escalation.

## 1. Review basis

This review was written **after** executable tests, including the new vertical dialectic E2E. It is not a speculative architecture review.

Observed validation:

- R4 targeted acceptance: **67/67 PASS**.
- Full Researcher: **544 total / 540 PASS / 4 known TD-015 failures**.
- The four failures are unchanged baseline Guard/LocalCorpus failures.
- Runtime compiler: PASS, unchanged hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`.
- Capability compiler: PASS, unchanged hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`.
- `compileall`: PASS.
- `git diff --check`: PASS before this review write.

## 2. What is now genuinely implemented

### 2.1 Explicit process-depth model

R4.4 no longer treats Tribunal dialogue as an unstructured chat loop. It defines:

```text
L0 independent
L1 challenge
L2 direct Q/A
L3 question-on-answer
L4 local research escalation
L5 external escalation (reserved)
```

This is process depth only. No epistemic confidence is derived from reaching a deeper level.

### 2.2 Typed emergent difficulty observation

The controller observes typed issue proposals rather than parsing prose itself. Existing scientific discoveries map into `EmergentIssue`; interaction-only issues may be proposed as `DialecticIssueProposal` and are checked against assigned need/ref authority.

This closes a key authority gap: semantic interpretation remains semantic, while continuation is deterministic.

### 2.3 Novelty / repetition / no-progress

The controller now distinguishes:

- new typed issue;
- repeated typed issue;
- changed evidence frontier;
- changed argument position;
- explicit closure of a previous issue.

A response that repeats the same issue without another state change increments `no_progress_streak`. Dialogue can terminate before nominal depth/token limits.

### 2.4 Local issue lifecycle

`DialecticIssueResolutionProposal` lets an admitted response mark a previously observed issue as `RESOLVED` or `STILL_OPEN`. Unknown issue signatures fail closed.

This is deliberately **not** Claim truth maintenance. It only answers whether a specific local objection/question surface remains active in the dialectic.

### 2.5 Full-chain budget awareness

The first implementation counted only response artifacts because the observer runs on `ArgumentArtifact`. Review caught this as incorrect process accounting. The controller now accepts explicit full-chain turn count so questions also consume the turn budget.

If a runtime omits the explicit count, the observation records `CHAIN_TURN_COUNT_APPROXIMATED` rather than silently pretending exactness.

### 2.6 Explicit challenge turn

`InquiryTurnKind.CHALLENGE` was added so the historical chain is not compressed from independent first pass directly into Q1.

Current bounded chain:

```text
FIRST_PASS_ASSESSMENT
-> CHALLENGE
-> QUESTION
-> ANSWER
-> QUESTION_ON_ANSWER
-> REBUTTAL
```

### 2.7 Conversation can hand work back to Researcher

A blocking evidence/method issue can produce `REQUEST_LOCAL_RESEARCH`. An explicit projection helper can turn that admitted issue into the existing Gap contract, after which the pre-existing ResearchChallenge path is reused.

The E2E demonstrates:

```text
first-pass XRD limitation
-> skeptic challenge
-> Q1/A1 exposes assumption
-> Q2(on A1)/A2 exposes discriminating-evidence gap
-> REQUEST_LOCAL_RESEARCH
-> Gap
-> ResearchChallenge
```

No second scheduler was introduced.

## 3. What the E2E found that static review would likely miss

### Finding A — response-only turn counting was wrong

The code originally counted only observed argument-bearing turns. This understated dialogue depth. The E2E made the discrepancy obvious because a six-turn chain looked like three turns to the observer.

**Action:** explicit full-chain count added.

### Finding B — a controller that only discovers issues cannot converge honestly

Without issue closure, the active problem set could only grow. `STOP_CONVERGED` would then mean “we stopped” rather than “the local objections were answered”.

**Action:** typed local issue-resolution proposals added.

### Finding C — resource limit must not swallow an already-observed actionable escalation

If the final permitted response surfaces a blocking missing-evidence request, it is more useful to route that explicit research need than to discard it behind `TURN_LIMIT_REACHED`.

**Action:** actionable blocking escalation is evaluated before dialogue resource-stop actions. The conversation still stops, but the next owner is Researcher rather than a dead terminal.

### Finding D — issue lifecycle needs historical reopen, not set deletion

Simply removing a resolved issue from the active set loses the fact that it had already been discussed. If it later reappears, the system would misclassify it as novel.

**Action:** `DialecticHistory` now retains resolved signatures separately. Reappearance moves a signature back into active state with `ISSUE_REOPENED`.

### Finding E — fanout limits must constrain continuation, not visibility

The first draft truncated `new_issues` to `max_new_issues_per_turn`. That could hide a blocking seventh issue from the controller.

**Action:** all admitted issues remain in the observation. Fanout excess becomes an explicit control condition; blocking research/capability escalation has priority over the fanout stop.

## 4. Important current weaknesses

### 4.1 Semantic issue identity is still text-sensitive

The L1 issue signature includes normalized statement text. Exact repetition is handled well, but a paraphrase can appear novel.

This is visible and tracked as TD-044. It should not be “fixed” with fuzzy similarity hidden inside control code. The likely mature form is typed issue facet/equivalence proposal + deterministic admission.

### 4.2 Live semantic observer quality is unproven

`ANSWER_EVASION`, `CONTRADICTION` and `ROLE_CAPABILITY_GAP` can be carried safely, but current tests use typed fixtures. We have not shown that a live model labels these consistently.

Tracked as TD-042.

### 4.3 Dialogue artifacts are not yet a canonical branching graph

R4.4 L1 validates a linear historical chain. There is no canonical `attacks / undercuts / replies_to / defends` relation layer and no compiled cross-role disclosure contract.

Tracked as TD-043.

### 4.4 Dialectic observation state is not independently durable

Inquiry/Argument artifacts are historical objects, but `DialecticObservation`, `DialecticControlDecision` and `DialecticHistory` are currently value objects/control outputs. A production live chain will need persistence/replay and TD-038 traceability integration.

This is intentionally not solved by inventing a second Tribunal database.

### 4.5 Gap projection is explicit but not yet wired to durable admission

`gap_from_emergent_issue()` proves contract compatibility. A production pipeline still needs the reducer/admission decision and durable persistence around that projection.

### 4.6 Live provider binding remains open

R4.4 control semantics are testable independently, but live challenger/questioner/answerer execution remains gated by TD-037.

## 5. Advocate / defense design after legacy reconciliation

Advocate should remain **conditional**.

Recommended trigger conditions for a future L2/L3 policy:

1. an admitted challenge attacks a specific prior `ArgumentArtifact`;
2. the attacked position still has visible, admissible support worth defending;
3. the challenge is material/blocking or creates a genuine competing interpretation;
4. policy requires an independent defense perspective for that issue family.

Advocate must not:

- invent new evidence;
- widen the attacked role's evidence authority;
- defend a claim merely because a claim exists;
- convert inability to defend into a fake rebuttal.

Permitted outcomes should include:

```text
DEFEND
QUALIFY
CONCEDE_LOCAL_POINT
REQUEST_EVIDENCE
OPEN
```

The Advocate's role is therefore to test the strongest defensible justification, not to maximize SUPPORT votes.

A future FOR/AGAINST pair should be represented as competing typed argument branches, not as two personas whose scores are averaged.

## 6. Process-boundary recommendation

The next live dialectic slice should compile three separate envelopes:

1. `DialecticDisclosureContract` — exactly which prior arguments/turns are visible;
2. `DialecticQuestionContract` — exact target issue/argument, role, expected closure surface and budget;
3. existing EvidenceSlice/RoleInstruction authority — unchanged unless policy explicitly recompiles it.

Then execute one real chain:

```text
challenge target
-> Q1 contract
-> A1
-> observation
-> Q2 contract only if new surface exists
-> A2
-> observation
-> stop / research / recompose
```

## 7. Verdict on R4.4 L1

**Accept as an L1 deterministic control substrate.**

It materially improves the architecture because it gives the future Tribunal a way to:

- know why another round is allowed;
- know when another round is pointless;
- distinguish a new scientific problem from a repeated objection;
- explicitly close a local objection;
- hand missing evidence back to Researcher;
- stop on resource boundaries without pretending those boundaries are truth.

Do **not** describe it as a complete Tribunal dialogue runtime yet.

## 8. Milestone artifact

Feature commit: `e79e2d59e166a8d39642603f66112d4dc01f0fd3` (`researcher: bound r4 dialectic observation`).

Milestone package: `RESEARCHER-R4.4-DIALECTIC-OBSERVATION-001.zip`.

SHA256: `330d79a9df87e8a13c66a3606e0d8a3d2b6cc4069e7d1efe9419cfa209258fd0`.
