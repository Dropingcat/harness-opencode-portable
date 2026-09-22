# Researcher R4.4 L2a — Pipeline Audit

Date: 2026-09-13

## 1. Audited path

```text
ReviewWorkField
→ TribunalCompositionPlan
→ EvidenceSlice
→ independent ArgumentArtifact
→ typed ATTACKS / UNDERCUTS relations
→ ArgumentGraphProjection
→ selected material challenge
→ AdvocateActivationDecision
→ DialecticDisclosureContract
→ AdvocateDefenseContract
→ Advocate ArgumentArtifact
→ REPLIES_TO / DEFENDS
→ DialecticObserver
→ optional Gap / ResearchChallenge
```

## 2. Authority matrix

| Stage | May propose semantics | May widen evidence | May mutate Claim truth | May create historical review artifact |
|---|---:|---:|---:|---:|
| Argument role | yes | no | no | through admission/materialization |
| ArgumentGraph compiler | no | no | no | yes, ARL/AGP |
| Advocate activation | no | no | no | decision only |
| Disclosure compiler | no | no | no | yes, DDC |
| Advocate semantic role | yes | no | no | through ADC/materialization |
| DialecticObserver | no free-prose inference | no | no | control observation/decision |
| Gap/ResearchChallenge admission | no | n/a | does not set truth | yes, through existing reducers/contracts |

## 3. Branch isolation audit

Fixture topology:

```text
root
├─ skeptic ATTACKS root
└─ methodologist UNDERCUTS root
```

Selected defense branch:

```text
root + skeptic only
```

Observed disclosure:

- root visible: PASS;
- skeptic visible: PASS;
- selected attack relation visible: PASS;
- methodologist argument hidden: PASS;
- methodologist evidence hidden: PASS;
- hidden evidence citation rejected: PASS.

Therefore no automatic sibling-branch broadcast exists in the implemented Advocate path.

## 4. Argument graph invariants

- ARG endpoint namespace required: PASS.
- shared AssessmentNeed scope required: PASS.
- same run lineage required: PASS.
- self-edge rejected: PASS.
- duplicate active semantic edge rejected: implemented.
- attack/undercut source position must be CHALLENGE: PASS.
- defense source position SUPPORT/QUALIFY: implemented.
- cycle rejected: PASS.
- graph fingerprint tamper rejected: PASS.
- roots/branch heads deterministic from active topology: PASS.

## 5. Advocate invariants

- role must be locally admitted: PASS.
- role absent from ordinary initial composition: PASS.
- relation must be ACTIVE ATTACKS/UNDERCUTS: implemented.
- materiality gate: PASS.
- target must remain SUPPORT/QUALIFY: implemented.
- visible support required by current policy: implemented.
- shared need coverage required: implemented.
- defense-count bound: implemented.
- defense instruction must be handbook `defense`: implemented.
- handbook cannot grant tools/evidence authority: inherited R4.3 invariant.
- citations outside DDC rejected: PASS.
- contract/disclosure fingerprints validated: PASS.

## 6. Downstream audit

### `DEFEND`

Produces:

```text
ArgumentArtifact(position=SUPPORT)
REPLIES_TO challenge
DEFENDS attacked argument
CONTINUE_CROSS_EXAM
```

No Claim mutation: PASS.

### `REQUEST_EVIDENCE`

Produces:

```text
ArgumentArtifact(position=OPEN)
REPLIES_TO challenge
AdditionalEvidenceRequest
REQUEST_LOCAL_RESEARCH
```

Then existing observer projects a blocking missing-evidence issue, which can enter canonical `Gap -> ResearchChallenge` only through explicit caller/admission. PASS.

## 7. Legacy alignment

Preserved legacy concepts:

- adversarial branch;
- skeptic vs advocate perspectives;
- local bounded escalation;
- honest OPEN;
- challenge justification rather than vote count;
- asymmetric information.

Not restored:

- permanent Advocate;
- one LLM role-playing the panel;
- majority vote as truth;
- Aggregator truth override;
- giant shared Tribunal context.

## 8. Phase-tracker alignment

The older architecture called the broad layer R5 `Dialectical inquiry`. Current incremental numbering implements the same semantics as R4.4 sublevels after composition/evidence/first-pass were separated into independently testable blocks.

No contradiction exists between phase documents; the newer tracker is a refinement of the older phase granularity.

## 9. Residual risks

### TD-037
Live provider binding/health is still open. Fixture role output does not establish production quality.

### TD-043
DDC is executable only for current defense path. Generic challenger/questioner/cross-exam disclosure remains open.

### TD-044
Issue identity remains text-sensitive. Writer semantic decomposition/RTT reuse is a future proposal-only bridge.

### TD-045
Dialectic history is not branch-scoped yet. Multiple graph heads must eventually receive independent progress/issue/budget histories.

## 10. Audit conclusion

R4.4 L2a is a valid structural milestone. The project now has a real branching argument topology and a bounded conditional Advocate whose output has explicit downstream semantics. It should **not** advance directly to free-form multi-agent debate. Generic disclosure, branch history and question-target contracts are the next required control surfaces.
