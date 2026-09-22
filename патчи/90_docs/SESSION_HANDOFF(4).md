# SESSION HANDOFF — Writer/Researcher/Coder Harness

Date: 2026-09-13

## 1. Canonical state

R4.4 L2b Generic Disclosure + Question Targeting + Branch History is complete as a structural/control-plane milestone.

Canonical HEAD:

`420de134774ce7bbd072390e31b59f793295dea6`
`researcher: close r4.4 l2b milestone boundary`

Feature commit:

`8fc635160d9f3f90583d5e8e44a3206f4e7366ad`
`researcher: generalize r4 dialectic disclosure`

Expected working tree: clean.

Milestone:
`packages/RESEARCHER-R4.4-L2B-DISCLOSURE-BRANCH-HISTORY-001.zip`
SHA256 `e83a12e7d666a5f2d3e2183164a620e50bac3c5b6939e1553c70f8458fcaaf61`

Recovery bundle:
`recovery/HARNESS-R4.4-L2B-COMPLETE-2026-09-13.bundle`
SHA256 `b798ec817c10bab7173fda9301768a5be256239439a55cf3b01b6bf895833970`

## 2. Proven executable structural chain

```text
RelationAssessment
-> ReviewWorkField
-> TribunalCompositionPlan
-> role EvidenceSlice
-> first-pass role execution
-> ArgumentArtifact
-> DialecticObservation / ControlDecision
-> ArgumentGraphProjection
-> branch ATTACKS / UNDERCUTS
-> DialecticBranchRef
-> generic DialecticDisclosureContract
-> DialecticQuestionContract
-> branch-local DialecticBranchHistory
-> Q1/A1
-> admitted new surface
-> Q2(on that surface)/A2
-> branch-local control decision
-> Gap / ResearchChallenge when research is needed
-> DialecticResearchResumeAnchor for exact branch/issue continuation
```

No second scheduler, truth registry or Tribunal-owned KnowledgeGraph exists.

## 3. Generic disclosure boundary

`DialecticDisclosureContract/1.1` is now shared control-plane infrastructure rather than an Advocate-only contract.

Supported purposes:

- CHALLENGE
- DIRECT_QUESTION
- QUESTION_ON_ANSWER
- DEFENSE
- CROSS_EXAM reserved for later executable cross-exam policy

Cross-exam may widen the original first-pass visibility only through an explicit DDC with recorded policy version/hash and fingerprint. A prompt or role cannot widen its own evidence view.

Sibling branches remain hidden unless explicitly admitted into the disclosure.

TD-043 is DONE at this boundary.

## 4. Question targeting

`DialecticQuestionContract/1.0` (`DQC-*`) is a first-class entity.

Q1 binds a role, branch, target argument, parent turn and bounded evidence/target refs.

Q2 is more restrictive: it may target only an issue signature admitted as a newly exposed surface from the prior answer. Rephrasing Q1 without a new admitted surface is not a legitimate Q2 progression.

Both InquiryTurn citations and ArgumentArtifact references are checked against the DDC/DQC envelope.

## 5. Branch-scoped history

`DialecticBranchHistory` isolates:

- no-progress streak;
- issue lifecycle;
- Q/A pair count;
- token/turn accounting;
- branch history fingerprint.

Stable branch identity excludes changing graph revision/head so the same branch can survive appended replies. Snapshot revision/fingerprint remain part of each branch view and are integrity checked.

History supports serialize/restore/replay. Two-branch E2E proves branch A can execute Q1/A1/Q2/A2 and escalate while branch B remains untouched and later starts with its own counters.

TD-045 is DONE at this boundary.

## 6. Research resume

Local research escalation now produces a typed `DialecticResearchResumeAnchor` linking:

- ResearchChallenge;
- Gap;
- stable branch;
- argument-graph snapshot;
- issue signature;
- branch-history fingerprint.

This is not yet the universal traceability substrate (TD-038), but it prevents returned research from being silently resumed into the wrong sibling branch.

## 7. TD-044 Writer bridge

Issue semantic identity remains text-sensitive. The future path remains proposal-only reuse of Writer claim/proposition splitting, local graph artifacts and semantic round-trip validation:

```text
EmergentIssue + bounded context
-> Writer claim/facet decomposition proposal
-> local proposition graph + equivalence candidates + RTT
-> Researcher scope/provenance validation
-> explicit issue-equivalence admission
```

Writer never owns issue signatures, no-progress state or resolution authority.

## 8. Validation

- R4 targeted: 82/82 PASS.
- Full Researcher: 559 total / 555 PASS / same four TD-015 failures.
- Runtime compiler PASS, hash unchanged.
- Capability compiler PASS, hash unchanged.
- compileall PASS.
- JSON/YAML parse PASS.
- git diff --check PASS.

## 9. Next phase

Start R4.4 L3 with live provider/capability binding, not more structural graph work.

First vertical E2E should be one real branch:

```text
real challenger/questioner
-> DDC
-> DQC Q1
-> child Job/Attempt + authorized provider
-> typed A1
-> deterministic observation
-> Q2 only if a new surface is admitted
-> typed A2
-> branch-local stop | ResearchChallenge
```

Then repeat with a second role family and only afterward enable live conditional Advocate/cross-examination.

Keep runtime failure distinct from epistemic OPEN, preserve sibling-branch isolation, and run post-E2E review only after observed execution.
