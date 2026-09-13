# Researcher R4.3 — Independent Role Execution Architecture

Date: 2026-09-13
Status: DONE (L1); executable structural role path and handbook layer validated, packaging pending.
Boundary: R4.2 evidence slices -> one independent Tribunal role -> typed inquiry/argument artifacts.

## 1. Purpose

R4.3 proves one real vertical role path before expanding Tribunal dialogue:

```text
R3.5 ReviewWorkField
-> R4.1 TribunalCompositionPlan / RoleBriefContract
-> R4.2 TribunalEvidenceSlice
-> R4.3 InquiryContract
-> existing Job/Attempt runtime
-> role worker
-> InquiryTurn + ArgumentArtifact
-> typed discovery/follow-up boundary for R4.4 / ResearchChallenge projection
```

The first acceptance target is `xrd_specialist`, because the existing BCC/XRD E2E already produces a real method-specific role and bounded evidence slice.

## 2. Authority boundary

R4.3 may:

- compile a role-specific inquiry contract from an admitted composition plan and evidence slice;
- execute a worker inside the existing Job/Attempt substrate;
- validate that the worker only cites refs visible in its slice;
- persist/emit typed `InquiryTurn` and `ArgumentArtifact` outputs;
- emit typed discovery/additional-evidence proposals for later control-plane handling.

R4.3 may not:

- widen an EvidenceSlice;
- search the corpus by itself;
- create/admit new authoritative roles;
- mutate Claim, GraphEdge, Gap, Conflict, RelationAssessment or ReviewWorkField state;
- treat role output as truth;
- run Advocate, majority vote or a full Q1/A1/Q2/A2 exchange yet.

## 3. Contracts

### InquiryContract/1.0

Binds exactly one selected role to one R4.2 slice and carries:

- run/request/work-field identity;
- role id and `INDEPENDENT_FIRST_PASS` phase;
- composition and slice fingerprints;
- assigned AssessmentNeed refs;
- allowed capabilities/tools copied from RoleBrief authority;
- expected output schema;
- depth/token budgets;
- optional semantic role-instruction revision from the handbook layer.

The contract is fingerprinted.  A transferred contract whose role, slice, capabilities or budget changed fails closed.

### InquiryTurn/1.0

A historical dialogue/assessment event.  R4.3 L1 emits `FIRST_PASS_ASSESSMENT`; later R4.4 may add QUESTION / ANSWER / QUESTION_ON_ANSWER / REBUTTAL while preserving parent-turn links.

### ArgumentArtifact/1.0

Non-authoritative semantic result from a role.  It records:

- position: SUPPORT / CHALLENGE / QUALIFY / OPEN;
- justification;
- exact cited evidence/target refs;
- assigned need refs;
- typed discoveries;
- typed requests for more evidence.

A role cannot cite evidence or targets outside its EvidenceSlice.  Invalid refs reject the output rather than silently widening context.

## 4. Worker/runtime separation

The semantic worker is a protocol, not a scheduler.  Production may later bind it to an authorized LLM/agent provider.  Tests use a deterministic fixture worker.

The runtime adapter reuses `scripts/jobs/job_ctl.py` state and its child/attempt semantics.  R4.3 does not create a second scheduler.

For one role execution:

1. add child Job to parent;
2. create child state with `first_pass` stage;
3. start one Attempt with external task id = InquiryContract id;
4. call worker with only InquiryContract + TribunalEvidenceSlice;
5. validate output against contract/slice;
6. write/register typed argument artifact;
7. finish Attempt/stage/child;
8. parent observes terminal child state.

## 5. Adjacent-layer E2E acceptance

Required E2E is not merely `worker(input)->output`.

Upstream:

```text
RelationAssessment
-> UncertaintyProfile
-> ReviewWorkField
-> TribunalCompositionPlan
-> TribunalEvidenceBundle
-> xrd_specialist EvidenceSlice
```

R4.3:

```text
EvidenceSlice
-> InquiryContract
-> Job/Attempt
-> worker
-> InquiryTurn + ArgumentArtifact
```

Downstream compatibility:

- discoveries are typed and can seed later challenge/inquiry routing;
- additional evidence requests are typed and do not directly search/widen the slice;
- output remains non-authoritative and contains no state-transition fields.

## 6. Role handbook boundary

Authority and semantic guidance are separated.

`tribunal_composition.yaml` owns:

- admitted role id;
- capability/tool authority;
- evidence view;
- assignment compatibility;
- budget/output contract.

A separate Role Handbook may own semantic guidance:

- mission;
- mandatory checks;
- forbidden reasoning shortcuts;
- expected discovery classes;
- phase-specific variants (first pass, challenger, defense, cross-examination).

The handbook must never grant tools, capabilities, evidence visibility or authoritative role admission.

If code detects missing semantic guidance/expertise it should emit a typed handbook/expertise request.  Runtime code may generate a deterministic draft skeleton, but admission remains a policy/documentation operation.  Domain role packs remain TD-036.

## 7. Legacy Tribunal reconciliation

Retained later-stage sequence:

```text
independent first pass
-> optional FOR/AGAINST or Advocate stage when a typed challenge exists
-> Q1 -> A1 -> Q2(on A1) -> A2
-> typed discoveries
-> existing ResearchChallenge/reducer path
```

Rejected legacy mechanisms remain rejected: one model impersonating the whole panel, majority vote as truth, aggregator override, prompt-owned evidence widening.

## 8. Fail-closed behavior

- BLOCKED EvidenceSlice cannot execute.
- plan/slice/role/need/fingerprint mismatch rejects contract construction.
- worker citation outside slice rejects output.
- worker output with authoritative-state keys rejects output.
- unknown discovery/position/turn enum rejects output.
- duplicate external InquiryContract attempt in same Job rejects start.
- child failure is runtime failure, not epistemic OPEN.
- semantic OPEN is an explicit Argument position, not a runtime failure.

## 9. Implementation order

1. typed Inquiry/Argument contracts + integrity validation;
2. one xrd_specialist deterministic fixture worker;
3. Job/Attempt adapter and role vertical E2E;
4. downstream discovery/follow-up compatibility checks;
5. regression/static/compiler gates;
6. only after green E2E: core-role semantic handbook and typed handbook-fill requests;
7. review/audit/docs after observed behavior.

## 10. Observed implementation result

R4.3 L1 now executes the planned XRD vertical through the real Job/Attempt substrate using a deterministic semantic fixture worker, validates fail-closed hidden-reference handling, and verifies downstream PriorReview projection. A second E2E executes `xrd_specialist` and `crystallographer` independently from one plan with different EvidenceViews/instruction fingerprints.

The semantic Role Handbook is implemented for the current admitted core roles, including common stop conditions and phase variants. Code-owned fill requests/skeletons cover missing semantic guidance without self-admitting roles or authority. Only `first_pass` is executable in R4.3 L1; challenger/cross-exam remain typed semantic preparation for the next inquiry layer.

Live provider health/binding remains TD-037, general lineage remains TD-038, and domain role packs remain TD-036.
