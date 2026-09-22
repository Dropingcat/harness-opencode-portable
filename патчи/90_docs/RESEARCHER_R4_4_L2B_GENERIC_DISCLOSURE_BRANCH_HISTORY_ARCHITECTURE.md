# Researcher R4.4 L2b — Generic Disclosure, Question Targeting and Branch History

Status: IMPLEMENTED / pending final post-E2E freeze
Date: 2026-09-13
Owner: Researcher orchestrator

## 1. Block identity

Implementation files:

- `scripts/researcher/researcher_core/tribunal_disclosure.py`
- `scripts/researcher/researcher_core/tribunal_dialectic.py`
- `scripts/researcher/researcher_core/tribunal_advocate.py`
- `scripts/researcher/researcher_core/tribunal_inquiry.py`
- `scripts/researcher/researcher_core/r0/ids.py`
- `scripts/run_researcher_acceptance.py`

Primary contracts:

- `DialecticBranchRef` (`DBR-*` content-addressed branch key; not an R0 EntityId)
- `DialecticDisclosureContract/1.1` (`DDC-*`)
- `DialecticQuestionContract/1.0` (`DQC-*`)
- `DialecticBranchHistory/1.0` checkpoint
- `DialecticResearchResumeAnchor`

Relevant existing objects:

- `ArgumentArtifact/1.0` (`ARG-*`)
- `ArgumentRelation/1.0` (`ARL-*`)
- `ArgumentGraphProjection/1.0` (`AGP-*`)
- `InquiryTurn/1.0` (`IQT-*`)
- `EmergentIssue`
- `ResearchChallenge` (`RCH-*`)

Policy dependencies:

- `config/tribunal_composition.yaml`
- `config/tribunal_role_handbook.yaml`
- R4.4 `DialecticPolicy`

## 2. Purpose

L2a proved that a selected Advocate branch can be isolated. L2b generalizes that idea so all later dialectic phases use one code-owned disclosure model rather than role-specific prompt conventions.

The block solves three concrete problems:

1. cross-role disclosure must be explicit, branch-scoped and replayable;
2. Q1/Q2 must target typed artifacts/issues rather than free-form topic drift;
3. parallel argument branches must not share no-progress counters, issue lifecycle, Q/A counts or budget history.

It explicitly does **not** execute live LLM/provider workers. That remains R4.4 L3 / TD-037.

## 3. Inputs and outputs

### Input topology

```text
ArgumentGraphProjection
+ ArgumentArtifact registry
+ selected ARL/ARG branch
+ AssessmentNeed scope
+ role policy/handbook instruction
+ prior DialecticObservation (for Q2)
        ↓
branch ref + disclosure + question contract
```

### Outputs

```text
DialecticBranchRef
DialecticDisclosureContract
DialecticQuestionContract
InquiryTurn (question)
DialecticBranchHistory checkpoint
DialecticResearchResumeAnchor
```

No output directly mutates Claim, GraphEdge, Gap truth, RelationAssessment or ClaimAssessment.

## 4. Stable branch identity

`DialecticBranchRef` separates stable branch identity from moving graph state.

Stable branch key is derived from:

```text
AGP id
+ root ARG
+ anchor ARG
+ anchor ARL (when present)
+ optional seed issue signature
```

It deliberately excludes:

- AGP revision;
- graph fingerprint;
- current branch head.

Those are snapshot fields. Therefore one branch can evolve:

```text
challenge ARG
→ A1 ARG
→ A2 ARG
```

without changing its stable `DBR-*` key.

A sibling challenge against the same root receives a different key because it has a different anchor relation/argument.

## 5. Generic disclosure model

`DialecticDisclosureContract/1.1` is now shared by:

- `CHALLENGE`;
- `DIRECT_QUESTION`;
- `QUESTION_ON_ANSWER`;
- `DEFENSE`;
- reserved `CROSS_EXAM` purpose.

The former Advocate-specific DDC compiler is now a compatibility wrapper over the generic compiler.

A DDC records:

```text
role
purpose
branch snapshot
focus ARG / optional ARL / optional IQT / optional issue signature
visible ARGs
visible IQTs
visible ARLs
visible EVD/SRC-style refs already exposed by branch artifacts
visible target refs
explicitly hidden ARGs
AssessmentNeed scope
fingerprint
```

### Disclosure phase transition

Cross-examination may reveal prior-argument evidence that was intentionally absent during independent first pass. This is allowed only when the DDC explicitly discloses it.

Therefore:

```text
first-pass EvidenceSlice authority
!=
later cross-exam disclosure authority
```

but:

```text
cross-exam extra visibility
MUST come from a fingerprinted DDC
```

A role/prompt cannot widen its view by itself.

## 6. Purpose semantics

### CHALLENGE

The role receives the argument it is allowed to challenge plus explicitly authorized base refs. Sibling branches remain hidden.

### DIRECT_QUESTION

The role receives the selected branch lineage needed to formulate Q1. A question may target an argument justification or an already-admitted typed issue.

### QUESTION_ON_ANSWER

Q2 may only target a typed **new issue surface** admitted from A1. It cannot jump to an arbitrary sibling argument/topic because prompt text suggests it.

### DEFENSE

The conditional Advocate receives the attacked argument plus selected challenge and local branch evidence only. Existing L2a behavior is preserved through the generic compiler.

## 7. Typed question targeting

`DialecticQuestionContract/1.0` (`DQC-*`) binds one bounded question to:

- questioner role;
- DDC id/fingerprint;
- stable dialectic branch;
- target kind (`ARGUMENT_JUSTIFICATION` or `EMERGENT_ISSUE`);
- target ARG;
- optional target IQT;
- optional exact issue signature;
- parent IQT;
- AssessmentNeed scope;
- allowed evidence/target refs;
- expected closure surface;
- response token limit;
- follow-up limit;
- role-instruction fingerprint;
- policy version/hash.

`QUESTION_ON_ANSWER` fails closed unless its issue signature is present among the newly admitted issue signatures from the prior answer observation.

This establishes the intended rule:

```text
A1
→ admitted new surface S
→ Q2(target=S)
```

not:

```text
A1
→ prompt decides to talk about something else
```

## 8. Question/answer leakage guard

`validate_answer_against_question_contract()` validates both semantic artifacts:

- `InquiryTurn.cited_refs`;
- `ArgumentArtifact` citations/discoveries/evidence requests.

An answer cannot smuggle a hidden sibling `ARG/EVD/IQT/ARL` through the turn while keeping its `ArgumentArtifact` superficially clean.

## 9. Branch-scoped history

`DialecticHistory` remains the local counter/state payload, but it is now wrapped by `DialecticBranchHistory`.

Each branch independently carries:

```text
argument ids
turn ids
active issue signatures
resolved issue signatures
last position
visible-ref fingerprint
no-progress streak
Q/A pair count
token spent
```

plus the current branch/graph snapshot and a history fingerprint.

Two sibling branches can therefore be interleaved without sharing:

- no-progress state;
- issue lifecycle;
- Q/A count;
- token consumption.

## 10. Replay

L2b adds actual serialization/restore rather than merely in-memory integrity checks:

- `DialecticDisclosureContract -> dict -> restore -> validate`
- `DialecticQuestionContract -> dict -> restore -> validate`
- `DialecticBranchHistory -> dict -> restore -> fingerprint check`
- `DialecticBranchRef -> dict -> restore`

Graph revision may advance while the stable branch key remains unchanged.

A stale branch snapshot cannot be used against a newer AGP without explicit refresh.

## 11. Research escalation/resume

When dialectic control produces blocking research work:

```text
EmergentIssue
→ Gap
→ ResearchChallenge
```

the challenge dimensions include:

```text
DBR key
AGP id/revision/fingerprint
root/anchor/head ARG
anchor ARL
issue signature
```

`DialecticResearchResumeAnchor` additionally binds:

- `RCH-*`;
- `GAP-*`;
- branch key/snapshot;
- issue signature;
- branch-history fingerprint.

Returned research must validate against this anchor before the branch continues. Research work therefore resumes the unresolved branch rather than starting an unrelated dialogue.

## 12. Authority boundary

Authoritative control remains code-owned:

```text
semantic role proposes answer/discovery
→ DQC/DDC scope validation
→ DialecticObserver admits typed surface
→ DialecticPolicy chooses continue/stop/escalate
```

Neither DDC, DQC, role output, Advocate nor argument graph sets scientific truth.

## 13. Failure/fail-closed behavior

Reject:

- stale AGP snapshot;
- branch whose head cannot reach exactly one root;
- focus ARG outside branch;
- parent IQT outside disclosure;
- Q2 without newly admitted issue surface;
- answer citations outside DDC/DQC;
- discovery/request that widens AssessmentNeed scope;
- hidden target/evidence leakage;
- tampered DDC/DQC/history fingerprint;
- cross-branch resume dimensions;
- graph revision moving backwards.

## 14. E2E boundary

Representative fixture contains two concurrent attacks against one root argument.

Only branch A enters:

```text
ATTACK A
→ DDC(Q1)
→ DQC(Q1)
→ Q1
→ A1 + new ASSUMPTION_ISSUE
→ ARG(A1) REPLIES_TO attack A
→ AGP revision
→ branch checkpoint/restore
→ DDC(Q2)
→ DQC(Q2 target=exact new issue)
→ Q2
→ A2 + AdditionalEvidenceRequest
→ ARG(A2) REPLIES_TO A1
→ AGP revision
→ blocking EmergentIssue
→ GAP
→ ResearchChallenge
→ ResumeAnchor
```

During the whole run, attack B is hidden from branch-A DDCs and retains an independent empty history. It can then start on the latest AGP revision with Q/A count and issue state still independent.

## 15. Current limitations

1. Live semantic question/answer generation is still fixture-only; TD-037 remains.
2. Issue semantic identity remains text-sensitive; TD-044 remains.
3. Branch history is serialized as a checkpoint artifact but not yet stored in a dedicated repository/index.
4. Generic disclosure policy is deterministic code policy; it is not yet exposed as a separately versioned YAML policy file.
5. `CROSS_EXAM` is represented as a disclosure purpose, while current executable Q2 uses `QUESTION_ON_ANSWER` as the more precise contract.
6. Full universal provenance/traceability across these artifacts remains TD-038.

## 16. Complexity ladder

- L1: branch identity + generic disclosure + typed DQC + independent histories. **Implemented.**
- L2: live shared-provider execution of question/answer workers and persisted branch checkpoints. **Next.**
- L3: adaptive branch scheduling/recomposition and conditional multi-Advocate policy.
- L4: calibration of role/question effectiveness using historical resolution data.
- L5: learned routing only after enough replayable outcomes exist; authority remains deterministic.

## 17. Tests / acceptance

Added:

- `tests/researcher/test_tribunal_disclosure.py`
- `tests/researcher/test_r4_4_l2b_branch_questioning_e2e.py`

Acceptance includes:

- generic CHALLENGE disclosure;
- direct-question disclosure;
- Q2 new-surface gate;
- hidden sibling leakage failure;
- DDC/DQC round-trip + fingerprint validation;
- branch-history checkpoint/restore;
- two-branch independent counters/issues;
- exact ResearchChallenge branch resume anchor;
- existing Advocate tests unchanged through generic compiler compatibility.

## 18. Tech debt impact

- TD-043: acceptance satisfied by generic compiler + question/defense/challenge paths + replay tests. DONE at L2b freeze.
- TD-045: acceptance satisfied by stable branch identity, independent histories, checkpoint replay and exact research resume anchor. DONE at L2b freeze.
- TD-044: remains OPEN; Writer semantic decomposition reuse direction unchanged.
- TD-037: remains OPEN; live provider execution is next.
- TD-038: remains OPEN; universal traceability substrate still broader than L2b.

## 19. Legacy lineage

Preserved from legacy Tribunal:

- asymmetric role views;
- inherited branch context;
- dialectical Q/A/Q-on-answer;
- bounded local escalation;
- honest OPEN;
- arguments attacking justification rather than vote aggregation.

Not preserved:

- global transcript broadcast;
- one model impersonating the whole panel;
- majority vote as truth;
- prompt-owned evidence expansion;
- unbounded follow-up discussion.
