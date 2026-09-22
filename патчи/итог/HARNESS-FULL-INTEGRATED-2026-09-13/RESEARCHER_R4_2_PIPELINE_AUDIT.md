# Researcher R4.2 Pipeline Audit

Date: 2026-09-13
Scope: R3.3/R3.5 → R4.1 → R4.2 executable evidence-view boundary.

## 1. Pipeline under audit

```text
canonical Claim/Source/Evidence/GraphEdge
→ RelationAssessment
→ UncertaintyProfile
→ ReviewWorkField
→ TribunalCompositionPlan
→ TribunalEvidenceBundle / per-role EvidenceSlice
→ [STOP R4.2]
```

The audit is written after unit, nearest-chain E2E, targeted integration and full Researcher execution.

## 2. Authority audit

### Upstream authority

- RelationAssessment determines relation eligibility/qualification, not R4.2.
- R3.5 determines unresolved AssessmentNeeds.
- R4.1 determines admitted roles, assignments and EvidenceViewPolicy.

### R4.2 authority

R4.2 may only compile visibility projections under the plan.

### Explicitly not owned

- Claim truth/status;
- GraphEdge lifecycle/revision;
- Gap/Conflict lifecycle;
- uncertainty resolution;
- source/evidence admission;
- retrieval/search;
- provider/tool execution;
- Tribunal answer/verdict;
- Advocate/dialogue;
- aggregation.

E2E verifies Claim status and GraphEdge revision remain unchanged.

**Result: PASS.**

## 3. Evidence selection audit

R4.2 selection uses typed canonical refs and active GraphEdge kinds. It does not classify support/counter/method relevance from arbitrary prose.

Legacy top-N trust fallback is not used. Missing blocking evidence is surfaced as BLOCKED.

**Result: PASS L1.**

Caveat: canonical graph completeness bounds what can be classified; unlinked evidence remains unclassified rather than guessed.

## 4. Assignment-scope audit

A post-green code audit found that using aggregate `RWF.evidence_refs` for FULL_RELEVANT/FRESH_CONTEXT could widen one role's context beyond its assigned AssessmentNeeds. The compiler now scopes evidence to assigned needs plus structurally related typed relations. A background EVD present only in the aggregate RWF pool no longer leaks into the role slice.

**Result: PASS after repair.**

## 5. Evidence asymmetry audit

The compiler physically generates different views for roles:

- support-only;
- counterevidence-only;
- method-constrained;
- full relevant;
- fresh/blind.

A role does not receive a parameter allowing it to override the plan view.

**Result: PASS.**

## 6. FRESH_CONTEXT leakage audit

Current blind projection removes/masks:

- SourceProjection;
- evidence source ID;
- evidence locator;
- previous review artifacts;
- typed SUPPORT/COUNTER polarity;
- SUPPORT/COUNTER selection-reason codes;
- GraphEdge relation kind/endpoints and Source identity/type in target projections.

The exact evidence text remains available because the role still needs material to assess.

**Result: PASS for structural metadata leakage under current L1 policy.**

Exact evidence text is not semantically anonymized; source names/DOIs embedded in the excerpt can still reveal provenance. TD-039 keeps this limitation explicit. Future staged reveal remains an R4.3/R4.4 concern.

## 7. Bounding / fail-closed audit

- deterministic `max_refs` bounding: PASS;
- truncation visible as `PARTIAL`: PASS;
- missing canonical refs on blocking assignments visible as `BLOCKED`: PASS;
- blocking target-only numeric package can remain executable `READY`: PASS;
- no unrelated trusted-source backfill: PASS;
- plan/RWF mismatch: rejected;
- cross-run canonical state: rejected.

**Result: PASS.**

## 8. R3→R4 identity/traceability audit

The E2E uncovered mixed ref semantics in `AssessmentNeed.target_refs`: projectable targets and R3 control refs can coexist. R4.2 now keeps control refs explicit without pretending they are missing EVD/SRC/CLM objects.

This repair is adequate locally, but the underlying problem is larger than `AssessmentNeedRef`.

Needed future invariant:

> Every cross-layer artifact should be traceable to consumed object revisions, transformation/attempt, policy/config version and produced artifacts without each phase inventing another private identity bridge.

TD-038 records this as a high-priority traceability substrate rather than silently extending R4.2 scope.

**Result: PASS WITH EXPLICIT HIGH-PRIORITY DEBT.**

## 9. Legacy Tribunal-level audit

Legacy sources show an evolution from:

```text
skeptic discussion
→ conditional advocate
→ tribunal
```

toward:

```text
independent first pass
→ adversarial challenge/defense
→ Q1/A1/Q2(on A1)/A2
→ typed unresolved discoveries
```

Earlier vote/Aggregator truth semantics are obsolete for the target architecture.

R4.2 correctly implements only the visibility prerequisite and does not prematurely instantiate Advocate or Q/A execution.

**Result: PASS / downstream behavior explicitly deferred.**

## 10. E2E audit

Nearest-chain E2E uses real components from relation assessment through evidence slicing.

The E2E was useful rather than ceremonial: its first run failed because `RAS-*` was misinterpreted as missing evidence. The implementation was repaired and the E2E then passed.

This establishes a development-policy change: new capsules should have the nearest real E2E before review/audit whenever possible.

**Result: PASS and actionable defect found/repaired.**

## 11. Provider/capability audit

R4.1 validates logical capability/tool names against central registries. R4.2 does not execute providers and therefore does not prove health/availability.

The remaining TD-037 must be resolved before R4.3 executes a role that depends on a tool/capability.

No Tribunal-specific provider registry was created.

**Result: NOT IN R4.2 AUTHORITY / OPEN TD-037.**

## 12. Domain role-pack audit

No new domain role-pack mechanism was introduced.

This is intentional per user direction and R4-D020. TD-036 remains open until evidence/inquiry contracts are stable enough to define pack admission without letting packs widen tool/evidence authority.

**Result: DEFERRED BY DESIGN.**

## 13. Composition-plan integrity audit

The R4.2 boundary now verifies the R4.1 composition fingerprint before consuming the plan. The fingerprint covers authority-bearing brief fields, not only role IDs/assignments. Tests prove that changing a Skeptic evidence-provenance policy or inquiry budget without recomputing the plan is rejected. This detects accidental/inconsistent alteration; it is not intended as adversarial cryptographic authentication. Brief-to-assignment consistency is also checked to prevent a role from acquiring another valid AssessmentNeed by editing its brief.

**Result: PASS after repair.**

## 14. Regression audit

Observed after implementation:

- R4.2 local + E2E: 17/17 PASS;
- R3.5 + R4.1 + R4.2 targeted: 40/40 PASS;
- full Researcher: 517 total / 513 PASS / four unchanged TD-015 failures;
- runtime compiler `--check`: PASS, unchanged hash;
- capability compiler `--check`: PASS, unchanged hash;
- compileall: PASS;
- git diff --check: PASS;
- executable demo: PASS.

No new regression class was observed.

## 15. Audit verdict

**R4.2 L1: ACCEPTABLE TO FREEZE after milestone/recovery packaging.**

The implementation closes the R4.1 contract gap between declared EvidenceViewPolicy and real role-specific canonical evidence projections. It also produced one useful boundary defect during E2E and records the broader identity/lineage problem instead of hiding it.

Next boundary: R4.3 typed inquiry contracts and independent first-pass execution over R4.2 slices, reusing existing Job/Attempt runtime and resolving live provider health before capability-dependent execution.


## 12. Post-freeze reproducibility check

After milestone/package creation, the current checkout was re-run through the targeted R3.5→R4.2 chain, full Researcher regression, both policy compilers, compileall, demo and diff check. Results reproduce the recorded branch state: 40/40 targeted PASS; 513/517 full PASS with only the four pre-existing TD-015 failures; compiler hashes unchanged.

A plain root-level pytest invocation is not yet self-bootstrapping because the Researcher import root must be supplied explicitly (`PYTHONPATH=scripts/researcher`). This is recorded as TD-040 and is operational debt rather than evidence-slicing authority debt.
