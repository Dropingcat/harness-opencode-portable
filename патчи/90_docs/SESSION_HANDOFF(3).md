# SESSION HANDOFF — Writer/Researcher/Coder Harness

Date: 2026-09-13

## 1. Canonical state

R4.4 L2a Branching Argument Graph + Conditional Advocate is complete as a structural/control-plane milestone.

Canonical HEAD:

`4853230d9515c4333b64dcf1063adf4934487b3c`
`researcher: close r4.4 l2a milestone boundary`

Feature commit:

`910c2f98879278bb391ece71cd92287b8a913137`
`researcher: branch r4 argument graph with conditional advocate`

Expected working tree: clean.

Milestone:
`packages/RESEARCHER-R4.4-L2A-ARGUMENT-GRAPH-ADVOCATE-001.zip`
SHA256 `c109e04fe658307a57a965ba7017a0d4963e17bf9f7423ef6f620ba5f5fe8107`

Recovery bundle:
`recovery/HARNESS-R4.4-L2A-COMPLETE-2026-09-13.bundle`
SHA256 `32a4fa0a5b2a9c052f935f93c947dc1fb5759cd725d2290dacb339d6bfcc39ca`

## 2. Proven executable chain

```text
RelationAssessment
-> ReviewWorkField
-> TribunalCompositionPlan
-> role EvidenceSlice
-> independent role InquiryContract
-> child Job/Attempt
-> InquiryTurn + ArgumentArtifact
-> DialecticObservation / ControlDecision
-> ArgumentGraphProjection
-> ATTACKS / UNDERCUTS branch
-> conditional Advocate activation
-> branch-local disclosure
-> AdvocateDefenseContract
-> Advocate response
-> REPLIES_TO + optional DEFENDS
-> observer/control
-> cross-exam | local research | control | OPEN
```

A REQUEST_EVIDENCE branch was exercised through:

```text
Advocate
-> AdditionalEvidenceRequest
-> blocking MISSING_EVIDENCE
-> Gap
-> existing ResearchChallenge
```

No second scheduler, truth registry, or Tribunal-owned KnowledgeGraph was introduced.

## 3. Argument graph authority

`ArgumentGraphProjection` is historical review topology only.

```text
ArgumentArtifact != Claim
ArgumentRelation != GraphEdge semantic truth relation
ArgumentGraphProjection != KnowledgeGraph
```

Current relations:
`ATTACKS / UNDERCUTS / REPLIES_TO / DEFENDS`.

Relations are versioned, endpoint/run/need scoped, cycle-checked and fingerprinted. Direction is newer argument -> prior target argument.

## 4. Conditional Advocate contract

Advocate is present in policy/handbook as an admitted conditional role, but ordinary R4.1 need composition cannot select it because it advertises no normal need coverage.

Activation requires a specific material ACTIVE attack/undercut against a SUPPORT/QUALIFY argument with visible admissible support and policy room for defense.

The defense path is:

```text
AdvocateActivationDecision
-> DialecticDisclosureContract
-> AdvocateDefenseContract
-> AdvocateWorkerDraft
-> validated InquiryTurn + ArgumentArtifact
-> explicit ArgumentRelation[]
-> AdvocateNextAction
```

Allowed outcomes:
`DEFEND / QUALIFY / CONCEDE_LOCAL_POINT / REQUEST_EVIDENCE / OPEN`.

A defense role is not permitted to widen evidence, search independently, or emit support merely because it is named Advocate.

## 5. Branch isolation E2E

The E2E creates one defended root with two sibling adversarial branches: skeptic ATTACKS and methodologist UNDERCUTS. Only the selected skeptic branch is disclosed to Advocate. The sibling argument and sibling evidence are hidden and citation attempts fail closed.

`DEFEND` produces both:

```text
Advocate ARG -> REPLIES_TO -> challenge ARG
Advocate ARG -> DEFENDS -> defended root ARG
```

These edges are distinct intentionally: addressing a challenge and defending a position are not the same semantic relation.

## 6. Downstream behavior

Advocate output never writes Claim truth.

- DEFEND / QUALIFY -> allow controlled cross-exam continuation.
- CONCEDE_LOCAL_POINT -> return to dialectic control; this does not automatically reject the Claim.
- REQUEST_EVIDENCE -> local Researcher escalation through existing Gap/ResearchChallenge machinery.
- OPEN -> terminal epistemic open for this defense branch.

Runtime/provider failure remains different from semantic OPEN.

## 7. TD-043 remains partial

Defense disclosure is canonical and branch-local. Generic disclosure for challenger, direct-question, question-on-answer and cross-exam is still missing.

Do not mark TD-043 DONE until one generic compiler/policy covers those phases with integrity/replay and no sibling leakage.

## 8. TD-044 / Writer semantic bridge

Issue signatures are still text-sensitive. The preferred future experiment is reuse of Writer semantic infrastructure rather than a second Tribunal paraphrase system.

Candidate bounded bridge:

```text
EmergentIssue + bounded local context
-> Writer-style claim/proposition splitting
-> atomic ClaimFacetProposal[]
-> small local graph
-> semantic round-trip
-> equivalence candidates
-> Researcher scope/provenance validation
-> explicit equivalence admission
```

Writer never directly changes issue identity, no-progress or authority. Original and reformulated statements remain in history. If Writer is unavailable, degrade to conservative text-sensitive identity.

## 9. TD-045 branch history seam

The argument graph is now genuinely branching, but `DialecticHistory` remains sequential. Before running two concurrent/interleaved Q/A branches, introduce a branch identity/envelope tied to AGP revision + root/focus relation/issue.

Branch histories need independent:
- turn count;
- Q/A pair count;
- no-progress streak;
- token/budget state;
- issue lifecycle;
- local research escalation/resume lineage.

Two branches must be able to stop/open/continue independently.

## 10. Phase reconciliation

Legacy/review phase tracker says:
- R4 Tribunal composition;
- R5 Dialectical inquiry;
- R6 Adaptive feedback.

Current R4.4 L1/L2a/L2b/L3 are a finer decomposition of the old R5/R6 intent. Do not reopen numbering debates; preserve semantic boundaries and executable acceptance gates.

## 11. Validation

Current frozen validation:

- R4 targeted: 76/76 PASS.
- Full Researcher: 553 total / 549 PASS / same four TD-015 baseline failures.
- 2 Guard + 2 LocalCorpus only.
- runtime compiler PASS, unchanged hash `6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a`.
- capability compiler PASS, unchanged hash `b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd`.
- compileall PASS.
- YAML/JSON parse PASS.
- git diff --check PASS.

## 12. Immediate next implementation boundary

R4.4 L2b only:

1. Generic `DialecticDisclosurePolicy/Compiler` for CHALLENGE, DIRECT_QUESTION, QUESTION_ON_ANSWER, DEFENSE.
2. Typed `DialecticQuestionContract` bound to target ARG/IQT/issue and disclosed artifacts.
3. Branch-scoped history/replay (TD-045).
4. Q2 may target only a newly admitted surface produced by A1.
5. Exact ResearchChallenge return/resume into the same unresolved argument branch.
6. Branching E2E with two attacks, only one entering Q/A and sibling remaining untouched.
7. Post-E2E review before live binding.

After structural L2b passes, move to live provider-bound dialogue (TD-037), not before.

## 13. Deferred/future

- TD-036 domain role packs.
- TD-037 live provider binding/health.
- TD-038 universal traceability.
- TD-039 semantic blind-view leakage.
- TD-041 portable RoleCard YAML DOM implementation.
- TD-042 live semantic observer calibration.
- TD-044 issue facet/equivalence implementation with Writer reuse experiment.
- learned role ranking.
- majority/quorum truth.
- human expert insertion until automated inquiry/disclosure is stable.
