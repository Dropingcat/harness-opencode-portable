# Researcher R4.4 L2b — Pipeline Audit

Date: 2026-09-13
Status: post-E2E structural audit

## Audited path

```text
ArgumentGraphProjection
→ selected attack branch
→ DialecticBranchRef
→ generic DDC
→ DQC(Q1)
→ Q1
→ A1 / ARG
→ branch ARG relation + AGP revision
→ DialecticObservation(new surface)
→ DDC(Q2)
→ DQC(Q2 exact surface)
→ Q2
→ A2 / ARG
→ branch ARG relation + AGP revision
→ blocking issue
→ Gap
→ ResearchChallenge
→ DialecticResearchResumeAnchor
```

Sibling branch is audited in parallel as the negative/control branch.

## 1. Branch selection

PASS.

A stable DBR key uses graph/root/anchor identity while graph revision/head remain mutable snapshot fields. Sibling attack relations produce distinct keys.

Fail closed:

- missing anchor ARG/ARL;
- inactive anchor relation;
- head outside anchor lineage;
- head resolving to ambiguous/no graph root;
- stale graph snapshot.

## 2. Disclosure

PASS.

Generic DDC explicitly lists visible and hidden prior artifacts. The compiler is shared with Advocate defense.

Audit invariant:

```text
hidden sibling ARG
→ absent from visible ARG/IQT/ARL refs
→ sibling evidence absent unless separately authorized by DDC policy/input
```

No prompt-level widening path exists.

## 3. Question targeting

PASS.

DQC has first-class `DQC-*` identity and records branch, target kind, target ARG/IQT/issue, parent turn, allowed refs, expected closure surface, budgets and policy/handbook fingerprints.

Q2 requires a typed newly admitted issue from A1.

Negative test rejects unrelated/old issue signature.

## 4. Answer admission

PASS.

Both `InquiryTurn.cited_refs` and `ArgumentArtifact` refs are checked. Discoveries and evidence requests cannot widen need/evidence/target scope.

Negative test verifies hidden sibling ref cannot be smuggled in the turn.

## 5. Graph continuation

PASS.

A1 and A2 become new `ARG-*` nodes connected by `REPLIES_TO`; AGP revisions are append-only and preserve sibling branches.

Stable DBR identity survives graph revision/head movement.

## 6. Branch-local progress

PASS.

Branch A accumulates two answer/rebuttal pairs while branch B remains zero. Starting branch B later on AGP revision 3 does not inherit branch-A counters/issues.

This closes the concrete shared-history defect tracked by TD-045.

## 7. Checkpoint/replay

PASS.

Branch history survives serialize/restore and fingerprint validation before Q/A continues. DDC and DQC also survive serialize/restore and integrity validation.

## 8. Research escalation/resume

PASS structurally.

A2 missing-evidence request becomes blocking `EmergentIssue -> Gap -> ResearchChallenge`. Branch dimensions and `DialecticResearchResumeAnchor` bind the work to exact DBR/AGP/issue/history.

Live returned evidence execution is deferred to L3.

## 9. Authority mutation audit

PASS.

No L2b path writes Claim truth or canonical GraphEdge assessment. Argument graph remains a process projection.

## 10. Backward compatibility

PASS.

L2a Advocate branch E2E remains green after generic DDC extraction.

## 11. Known non-blockers

- TD-037 live provider binding;
- TD-038 universal traceability;
- TD-039 semantic provenance anonymization;
- TD-041 PortableRoleDOM;
- TD-042 live semantic observer calibration;
- TD-044 issue semantic equivalence/Writer bridge;
- durable branch-history repository/index;
- separate admitted YAML for DDC policy if/when runtime configurability is needed.

## 12. Audit verdict

R4.4 L2b is structurally coherent and ready to freeze independently. The next meaningful test is live bounded worker execution against these contracts; further fixture-only dialogue semantics would have diminishing value.
