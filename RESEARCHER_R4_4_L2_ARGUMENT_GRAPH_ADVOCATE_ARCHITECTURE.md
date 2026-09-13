# Researcher R4.4 L2a — Branching Argument Graph and Conditional Advocate

Date: 2026-09-13
Status: IMPLEMENTED STRUCTURAL L2a; live semantic provider execution remains TD-037.

## 1. Purpose

R4.4 L1 proved bounded dialectic observation over typed inquiry artifacts, but its history was effectively a linear chain. That is insufficient once two reviewers attack different premises, a defense answers only one attack, or one branch returns to Researcher while another remains locally discussable.

R4.4 L2a adds a canonical **argument topology** and a conditional Advocate path without giving Tribunal outputs truth authority.

The implemented boundary is:

```text
ArgumentArtifact[]
+ admitted dialectic relation proposals
        ↓
ArgumentRelation/1.0 (ARL)
        ↓
ArgumentGraphProjection/1.0 (AGP)
        ↓
selected material ATTACKS / UNDERCUTS edge
        ↓
AdvocateActivationDecision
        ↓
DialecticDisclosureContract/1.0 (DDC)
        ↓
AdvocateDefenseContract/1.0 (ADC)
        ↓
Advocate ArgumentArtifact
+ REPLIES_TO / optional DEFENDS edges
        ↓
existing DialecticObserver
        ↓
continue cross-exam | local research | control return | OPEN
```

This is a dialectic graph, not a second KnowledgeGraph and not a voting layer.

## 2. Phase alignment

The older architecture review named the whole post-composition layer **R5 Dialectical inquiry**. The newer incremental numbering decomposes that same phase into R4.3/R4.4 slices so each control boundary can be tested before live multi-agent dialogue.

The semantics are unchanged:

```text
R4 composition
→ independent review
→ adversarial dialectic
→ typed discoveries
→ adaptive Researcher feedback
```

L2a specifically covers argument branching and conditional defense. Generic cross-role disclosure and live question/answer execution remain follow-on work.

## 3. Argument graph model

### 3.1 Nodes

Canonical semantic nodes remain `ArgumentArtifact/1.0` (`ARG-*`). The graph does not copy or rewrite their meaning.

### 3.2 Relations

`ArgumentRelation/1.0` (`ARL-*`) is a first-class versioned relation with:

- relation kind;
- source ArgumentArtifact;
- target ArgumentArtifact;
- assigned `AssessmentNeedRef` coverage;
- materiality flag;
- lifecycle state;
- reason codes;
- provenance metadata through `EntityMeta`.

Current relation vocabulary:

```text
ATTACKS
    challenges the conclusion/claim-bearing position of the target argument

UNDERCUTS
    challenges the justification bridge, method, assumption or evidence-to-position link

REPLIES_TO
    is a historical response to a prior argument, without implying support or refutation by itself

DEFENDS
    supplies a bounded defense/qualification of an earlier still-defensible argument
```

`REPLIES_TO` and `DEFENDS` are intentionally separate. A response can reply to an attack without successfully defending the attacked argument.

### 3.3 Direction

Edges are historical/dialectical:

```text
newer/source argument → earlier target argument
```

Example:

```text
ARG-root XRD qualification
├─ ARG-skeptic --ATTACKS----> ARG-root
│   └─ ARG-advocate --REPLIES_TO--> ARG-skeptic
│                    └─DEFENDS----> ARG-root
│
└─ ARG-methodologist --UNDERCUTS--> ARG-root
```

The two attack branches remain independent unless a disclosure contract explicitly joins them.

### 3.4 Graph projection

`ArgumentGraphProjection/1.0` (`AGP-*`) contains:

- referenced Argument IDs;
- versioned relations;
- root arguments;
- current branch heads;
- graph revision;
- deterministic fingerprint.

It enforces:

- no missing relation endpoints;
- same-run lineage;
- no duplicate active semantic edge;
- attack/undercut source must be a `CHALLENGE` position;
- defense source must be `SUPPORT` or `QUALIFY`;
- relation need coverage must intersect both source and target assignments;
- no self-edges;
- no cycles.

Acyclicity is a history invariant, not a claim about logical acyclicity of scientific reasoning. Rebuttals may revisit the same topic, but they do so through new historical argument nodes rather than literal graph cycles.

## 4. Conditional Advocate

### 4.1 Admission vs composition

`advocate` is now present in the versioned composition policy and semantic handbook, but has empty ordinary need coverage.

Therefore:

```text
admitted role != initially composed role
```

R4.1 composition cannot select Advocate from axis/method routing. Advocate can appear only through the explicit R4.4 activation path.

### 4.2 Activation conditions

Current L2a activation requires:

1. role `advocate` exists in local admitted policy;
2. selected relation is ACTIVE `ATTACKS` or `UNDERCUTS`;
3. source Argument position is `CHALLENGE`;
4. target Argument position is `SUPPORT` or `QUALIFY`;
5. source/target/relation share at least one `AssessmentNeedRef`;
6. challenge is marked material under policy;
7. attacked argument has visible cited support;
8. defense-count limit for that challenge has not been reached.

A non-material objection does not instantiate Advocate merely because one exists in the handbook.

### 4.3 Defense role semantics

Handbook variant:

```text
advocate / defense
```

Mission: test what, if anything, remains defensible against one specific admitted challenge.

Allowed semantic outcomes:

```text
DEFEND
QUALIFY
CONCEDE_LOCAL_POINT
REQUEST_EVIDENCE
OPEN
```

This makes Advocate an adversarial robustness role, not a permanent SUPPORT generator.

## 5. Disclosure contract

`DialecticDisclosureContract/1.0` (`DDC-*`) is compiled for the selected branch.

For current Advocate L2a it reveals only:

- attacked ArgumentArtifact;
- selected challenge ArgumentArtifact;
- their source InquiryTurns;
- selected ATTACKS/UNDERCUTS relation;
- evidence refs already cited by those two arguments;
- target refs already cited by those two arguments;
- shared AssessmentNeed refs.

Every other argument in the graph is explicitly listed as hidden.

Thus if another Methodologist branch attacks the same root argument, Advocate does **not** receive that branch automatically.

This is the first executable disclosure contract, but TD-043 stays open until challenger/questioner/cross-exam also use one generic disclosure compiler.

## 6. Advocate defense contract

`AdvocateDefenseContract/1.0` (`ADC-*`) binds:

- activation decision;
- DDC id/fingerprint;
- selected challenge relation;
- challenge and defended ARG IDs;
- challenge and defended IQT IDs;
- AssessmentNeed refs;
- allowed evidence/target refs;
- local role capabilities/tools from admitted policy;
- allowed semantic outcomes;
- token budget;
- defense instruction ID/fingerprint;
- policy version/hash;
- deterministic contract fingerprint.

An imported handbook entry cannot add tools or evidence. Local policy remains authority.

`InquiryTurn`/`ArgumentArtifact` now accept an `ADC-*` contract origin in addition to the earlier `IQC-*` first-pass contract origin. This is a compatibility extension of artifact provenance, not a relaxation of evidence authority.

## 7. Advocate output routing

Advocate response is materialized as:

```text
AdvocateResponse
  outcome
  InquiryTurn(REBUTTAL)
  ArgumentArtifact
  ArgumentRelation[]
  next_action
  reason_codes
```

Deterministic routing:

```text
DEFEND / QUALIFY
    → CONTINUE_CROSS_EXAM
    → REPLIES_TO challenge
    → DEFENDS attacked argument

CONCEDE_LOCAL_POINT
    → RETURN_TO_DIALECTIC_CONTROL
    → REPLIES_TO challenge
    → no synthetic DEFENDS edge

REQUEST_EVIDENCE
    → REQUEST_LOCAL_RESEARCH
    → REPLIES_TO challenge
    → AdditionalEvidenceRequest becomes blocking MISSING_EVIDENCE in normal dialectic observer

OPEN
    → STOP_OPEN
```

The graph relation does not resolve the original Claim. It only records what this argument did to another argument.

## 8. Downstream reuse

The existing R4.4 L1 observer consumes the Advocate `ArgumentArtifact` exactly like another admitted response.

Therefore:

```text
Advocate REQUEST_EVIDENCE
→ AdditionalEvidenceRequest
→ EmergentIssue(MISSING_EVIDENCE, blocking)
→ DialecticControlDecision.REQUEST_LOCAL_RESEARCH
→ explicit Gap projection
→ existing ResearchChallenge
→ existing PlanningDialectic / ResearchDOM expansion
```

No Advocate-specific research scheduler exists.

## 9. E2E acceptance

Implemented E2E scenario:

```text
ARG-root: xrd_specialist / QUALIFY
├─ ARG-skeptic / CHALLENGE --ATTACKS--> root
└─ ARG-methodologist / CHALLENGE --UNDERCUTS--> root

select skeptic ATTACKS branch
→ Advocate activation
→ DDC reveals root + skeptic only
→ methodologist branch and its evidence remain hidden
→ ADC compiled from admitted Advocate policy + defense handbook
→ Advocate REQUEST_EVIDENCE
→ ARG-advocate / OPEN
→ REPLIES_TO skeptic
→ graph revision preserves separate methodologist head
→ DialecticObserver requests local research
→ Gap → ResearchChallenge
```

Second path:

```text
Advocate DEFEND
→ ARG-advocate / SUPPORT
→ REPLIES_TO skeptic
→ DEFENDS root
→ CONTINUE_CROSS_EXAM
```

Negative tests cover:

- non-material challenge does not activate Advocate;
- Advocate cannot cite hidden sibling-branch evidence;
- attack source must actually be `CHALLENGE`;
- argument relation cycles fail closed.

## 10. Authority boundaries

The following remain distinct:

```text
KnowledgeGraph relation
!= ArgumentRelation
!= DialecticIssue
!= Claim truth
```

And:

```text
ATTACKS edge exists
!= attack is scientifically correct

DEFENDS edge exists
!= defended Claim is true

Advocate outcome DEFEND
!= reducer verdict SUPPORT
```

Argument topology is evidence about the review process. It is not itself epistemic authority.

## 11. TD-044 and Writer reuse direction

Issue identity remains text-sensitive at L1. Instead of building a second semantic decomposition system inside Tribunal, a future bridge may reuse Writer machinery that already performs proposition/claim decomposition, graph construction and semantic round-trip validation.

Proposed future flow:

```text
EmergentIssue statement + bounded local context
→ Writer-style semantic decomposition capsule
→ atomic ClaimFacetProposal[]
→ small local proposition graph
→ candidate issue-equivalence relations
→ round-trip check against original issue
→ Researcher scope/ref validation
→ explicit equivalence admission
```

Writer output is proposal-only. It cannot directly merge issue signatures or reset no-progress counters.

This direction is recorded in TD-044, not implemented in R4.4 L2a.

## 12. Known limitations / remaining work

1. TD-037: no production provider-health/live challenger/Advocate binding yet.
2. TD-043: generic disclosure compiler for challenger/questioner/cross-exam remains open.
3. TD-044: semantic issue equivalence/facets remain text-sensitive; Writer bridge is future work.
4. Argument relation persistence has typed/versioned objects and graph projection but no dedicated large-history index yet; the generic relation-history concerns of TD-022 remain relevant at scale.
5. No aggregation/quorum truth is implemented or planned at this boundary.
6. Human expert insertion remains downstream.
7. Returned ResearchChallenge evidence has not yet resumed the exact same graph branch through a generic replay contract; this belongs to later adaptive-feedback hardening.

## 13. Next boundary

R4.4 L2b should generalize disclosure and question targeting:

```text
ArgumentGraph branch head / issue
+ role phase
+ policy
→ generic DialecticDisclosureContract
→ DialecticQuestionContract
→ bounded challenger/questioner/cross-exam execution
```

Only after that and TD-037 live provider binding should the project claim a production live `Q1 → A1 → Q2(on A1) → A2` loop.
