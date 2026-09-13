# Researcher R4.4 L2a — Implementation Review

Date: 2026-09-13
Boundary: branching argument graph + branch-local conditional Advocate.

## 1. Verdict

**PASS for structural L2a.**

The implementation now represents competing Tribunal arguments as a real branching historical graph and can activate one conditional Advocate against one selected material challenge without broadcasting sibling branches or granting truth authority.

This is **not** a claim that live Advocate/challenger model quality is validated. TD-037 remains open and all new semantic role outputs in current E2E are deterministic fixtures.

TD-043 is only partially reduced: argument topology and defense disclosure are executable, but generic challenger/questioner/cross-exam disclosure is still missing.

## 2. Implemented code

### `researcher_core/tribunal_argument_graph.py`

Adds:

- `ArgumentRelationKind`;
- `ArgumentRelationState`;
- `ArgumentRelation/1.0` (`ARL-*`);
- `ArgumentGraphProjection/1.0` (`AGP-*`);
- graph construction, append/revision and integrity validation;
- root/head reconstruction;
- acyclicity and relation-semantics checks;
- serialization.

Implemented relation kinds:

```text
ATTACKS
UNDERCUTS
REPLIES_TO
DEFENDS
```

### `researcher_core/tribunal_advocate.py`

Adds:

- `AdvocateActivationPolicy`;
- `AdvocateActivationDecision`;
- `DialecticDisclosureContract/1.0` (`DDC-*`);
- `AdvocateDefenseContract/1.0` (`ADC-*`);
- `AdvocateWorkerDraft`;
- `AdvocateResponse`;
- `AdvocateOutcome`;
- deterministic output routing;
- disclosure/defense fingerprint validation;
- serialization helpers.

### Supporting changes

- ID registry admits `ARL`, `AGP`, `DDC`, `ADC` namespaces.
- `InquiryTurn` and `ArgumentArtifact` may bind to either ordinary `IQC-*` or conditional defense `ADC-*` origin contracts.
- composition policy admits `advocate` with no ordinary need coverage.
- role handbook admits defense-only role variants rather than assuming every admitted role must have `first_pass`.
- R4 acceptance runner includes graph and Advocate tests.

## 3. Main design results

### 3.1 Argument topology is separate from epistemic truth

The implementation does not overload canonical scientific `GraphEdge` with Tribunal discussion semantics.

```text
EVD SUPPORTS CLM
```

and

```text
ARG-skeptic ATTACKS ARG-xrd
```

remain different relation families with different owners.

This avoids a serious failure mode where a reviewer objection itself would look like evidence against a Claim.

### 3.2 `REPLIES_TO` is not `DEFENDS`

The E2E confirms a useful distinction:

- every Advocate response addresses the selected challenge through `REPLIES_TO`;
- only `DEFEND`/`QUALIFY` produce `DEFENDS` toward the attacked argument;
- `CONCEDE_LOCAL_POINT`, `REQUEST_EVIDENCE` and `OPEN` do not manufacture a defense edge.

This makes graph interpretation materially cleaner than a generic `responds_to` tree.

### 3.3 Advocate is admitted but cannot leak into initial composition

The role registry now contains Advocate, but its ordinary axis/method coverage is empty. Existing R4.1 composition remains unchanged and tests explicitly verify that Advocate is not selected in the normal plan.

This solves the otherwise awkward choice between:

- keeping Advocate outside authority policy entirely; or
- accidentally making it a normal review role.

### 3.4 Branch-local disclosure is real, not prompt prose

The two-branch fixture uses:

```text
root XRD argument
├─ skeptic ATTACKS
└─ methodologist UNDERCUTS
```

The Advocate selected for the skeptic branch receives only:

- root argument;
- skeptic challenge;
- their turns;
- selected attack relation;
- evidence/targets already cited by those two artifacts.

The methodologist branch and its evidence are explicitly hidden. A negative test proves that the Advocate cannot cite the hidden sibling evidence.

This is the strongest L2a result because it demonstrates actual branch isolation rather than merely documenting asymmetric evidence intent.

## 4. E2E behavior

### Path A — defense succeeds locally

```text
ARG-root / QUALIFY
→ ARG-skeptic / CHALLENGE --ATTACKS--> root
→ Advocate activation
→ DDC
→ ADC
→ Advocate outcome DEFEND
→ ARG-advocate / SUPPORT
→ REPLIES_TO skeptic
→ DEFENDS root
→ next_action = CONTINUE_CROSS_EXAM
```

### Path B — defense reaches an evidence boundary

```text
same selected branch
→ Advocate outcome REQUEST_EVIDENCE
→ ARG-advocate / OPEN
→ REPLIES_TO skeptic
→ AdditionalEvidenceRequest
→ existing DialecticObserver
→ blocking MISSING_EVIDENCE
→ REQUEST_LOCAL_RESEARCH
→ Gap
→ ResearchChallenge
```

No Advocate-specific retrieval path was introduced.

## 5. Defects/weak seams found by implementation

### D1. Existing inquiry artifacts were hardwired to `IQC-*`

Conditional defense has a different contract owner, so `InquiryTurn`/`ArgumentArtifact` could not carry correct provenance without pretending an Advocate defense was an independent first pass.

**Fix:** their `contract_id` now accepts `IQC-*` or `ADC-*`.

This is a provenance compatibility extension; it does not widen evidence authority.

### D2. Handbook assumed every admitted role had `first_pass`

That assumption made a genuinely conditional defense-only role impossible.

**Fix:** handbook entries now require at least one semantic variant. The normal composition/handbook fill path still verifies that actually selected first-pass roles possess `first_pass` guidance.

### D3. One generic disclosure problem was larger than Advocate

Implementing Advocate proved the shape of DDC, but also showed that generic challenge/question/cross-exam disclosure cannot simply be inferred from one defense implementation.

**Action:** TD-043 remains open-partial rather than being falsely closed.

### D4. Branching graph exposed a controller-state seam

`ArgumentGraphProjection` can now have multiple simultaneous branch heads, while `DialecticHistory` still carries one local sequential set of counters/issues.

If two branches later execute interleaved, they must not share:

- `no_progress_streak`;
- QA pair count;
- token budget;
- active/resolved issue set.

**Action:** TD-045 added for branch-scoped history/replay.

### D5. Issue-equivalence work should not duplicate Writer semantics

TD-044 originally suggested only a generic facet/equivalence layer. The project already has Writer claim splitting, graph artifacts and semantic round-trip validation.

**Action:** TD-044 now explicitly calls for evaluating a bounded Writer bridge that returns proposal-only issue facets/equivalence candidates. Researcher remains admission authority.

## 6. Negative tests

Current tests fail closed on:

- attack/undercut whose source is not `CHALLENGE`;
- relation cycle;
- graph fingerprint tamper;
- non-material attack attempting Advocate activation;
- Advocate citation of sibling/hidden evidence;
- disclosure fingerprint tamper;
- normal initial composition accidentally selecting Advocate.

## 7. Validation

R4 targeted acceptance after L2a additions:

```text
76 / 76 PASS
```

Full Researcher:

```text
553 total
549 PASS
4 known baseline FAIL
```

The four failures are unchanged TD-015 cases:

```text
2 Guard
2 LocalCorpus
```

No new regression class was observed.

Compiler/static gates:

```text
runtime compiler PASS
6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a

capability compiler PASS
b96fcb4341080bbc4d6c2b835c704bed60ee02d047f1bbb0c747c8a59af923cd

compileall PASS
git diff --check PASS
```

## 8. What this does not prove

This block does not prove:

- live model Advocate quality;
- live challenge/question generation;
- generic disclosure for all dialectic phases;
- branch-scoped replay;
- semantic paraphrase equivalence for issue identity;
- live provider timeout/retry behavior;
- scientific correctness of fixture arguments.

Those remain explicit follow-on boundaries rather than being hidden behind green structural tests.

## 9. Recommended next step

Proceed to R4.4 L2b:

1. generic disclosure compiler;
2. typed question-target contract;
3. branch-scoped history/replay (TD-045);
4. exact ResearchChallenge return-to-branch linkage;
5. only then production/live Q/A binding under TD-037.

## 10. Milestone packaging

Feature commit:

```text
910c2f98879278bb391ece71cd92287b8a913137
researcher: branch r4 argument graph with conditional advocate
```

Milestone package:

```text
RESEARCHER-R4.4-L2A-ARGUMENT-GRAPH-ADVOCATE-001.zip
SHA256 c109e04fe658307a57a965ba7017a0d4963e17bf9f7423ef6f620ba5f5fe8107
```

The package contains the exact feature patch plus the architecture/review/audit, decision/debt/tracker and future RoleCard growth documents. Recovery/handoff is finalized on the subsequent closure commit so packaging metadata itself is versioned.
