# CONTEXT PATTERNS FROM SESSION AND PROJECT MEMORY

Date: 2026-09-13
Purpose: preserve the design logic, recurring patterns, rejected alternatives, working conventions and continuation cues needed to resume R4 without reconstructing several long sessions from archaeology.

This file is contextual guidance. Runtime code, policy snapshots, typed contracts and tests remain authoritative where they disagree.

---

## 1. Project-level philosophy

The recurring invariant is:

> LLM produces proposals, arguments and observations; code decides authoritative state transitions.

This is not a claim that LLM reasoning is useless. The LLM is deliberately the flexible semantic executor. Code provides the control plane: typed contracts, allowed actions, routing, provenance, gates, budgets, state reduction, recovery and stop conditions.

A useful mental model is:

```text
Object
  → profile
  → routing/selection
  → specialists + tools + skills
  → processing
  → validation/admission
  → state update
  → new objects
  → loop
```

The same recursive structure applies at multiple scales: ResearchRequest, ResearchDirection, Claim, Gap, Conflict, relation, paragraph, code task, simulation request and later Tribunal inquiry.

The user explicitly generalized this into recursive object processing: each information object is treated as an individual entity, decomposed until further splitting no longer improves executability/checkability, then processed by individually profiled specialists/tools/skills. Routing may later become learned/ranked, but L1/L2 should stay deterministic and inspectable.

Do not reduce this idea to literal least-squares regression everywhere. The architectural idea is a selection/ranking function over object profile + context + history. Early implementations should favor deterministic scoring/rules before learned routing.

---

## 2. Three structural layers that must remain distinct

### 2.1 ResearchDOM

Answers: **what did we do / what work exists / what is the historical branch?**

It is an executable/historical tree. Nodes are not destructively forgotten. Cards can become COMPLETED, SUPERSEDED, BLOCKED, ABANDONED, MERGED, etc.

### 2.2 KnowledgeGraph

Answers: **what do we know / what semantic objects and relations exist?**

Contains Claim, Source, EvidenceSpan, Quantity, Gap, Conflict, Assumption, Derivation, Scope and versioned GraphEdge-like semantic relations.

### 2.3 Provenance / trace / selection history

Answers: **why did a piece of work happen, what produced a knowledge object, which route/policy/tool/specialist was selected, and why?**

ResearchTraceLink joins ResearchDOM and KnowledgeGraph. Routing/selection history should eventually preserve candidate processors, chosen processors, reason codes, policy version and outcome.

Do not collapse tree and graph into one structure. Tree is ancestry/process/history; graph is semantic relation. The distinction was repeatedly useful and should survive R4.

---

## 3. Writer, Researcher and Coder are peers

Top-level orchestrators are peers:

- Writer
- Researcher
- Coder

None is a universal parent of the others. Each owns domain-specific reducers and contracts. Cross-domain work is delegated through typed peer contracts and the shared Job/Attempt child runtime.

Writer v1 is stable/frozen. Researcher may delegate numeric experiments to Coder and writing/synthesis to Writer, but must not absorb their internals into a god-agent.

The shared runtime owns generic concerns such as job/attempt lifecycle, required/optional child jobs, artifacts, gates, provenance, checkpoint/recovery and budgets.

---

## 4. Research decomposition model

Research planning is not a flat topic list. The conceptual lattice is:

```text
Objective
× ResearchDirection
× DisciplinaryView
× QuestionType
× MethodView
```

but the executable ResearchDOM is a selected/pruned tree, not a Cartesian explosion.

Important dimensions:

- ResearchDirection: concrete problem/direction, e.g. lattice-parameter change, redistribution into phases, residual stress/microstrain, measurement correctness.
- DisciplinaryView: crystallography, physics of metals, physical metallurgy, materials science, etc.
- QuestionType: descriptive, mechanistic, causal, comparative, measurement, scope, contradiction.
- MethodView: XRD, TEM/SAED, EDS/WDS/EPMA, metallography, microhardness, numerical simulation, etc.

Lineage dimensions must be inherited down the branch. This became essential for Challenge branches and is directly relevant to R4 composition.

---

## 5. Planning dialectic

Planning itself is dialectical, not a single decomposition prompt.

Canonical shape:

```text
Q1: what must be known?
A1: candidate directions
Q2: what is missing/redundant and why are these sufficient?
A2: repaired coverage
Q3: what concrete questions live inside each direction?
A3
Q4: what disciplines/methods/capabilities make leaves executable?
A4
```

Code compiles typed proposals into ResearchCards and applies revision-checked patches.

The same decomposition machinery must be reused for newly discovered Challenge branches. Do not invent a second special planner for Tribunal-created research work.

Stop conditions belong to code: max depth/children, duplicate threshold, information gain/no-progress, budget, executability of leaves.

---

## 6. Gap/Conflict → Challenge feedback loop

R2 established a reusable control loop:

```text
TASK / knowledge object
→ Gap or Conflict
→ ResearchChallenge
→ CHALLENGE card in ResearchDOM
→ local PlanningDialectic
→ QUESTION / METHOD / TASK subtree
→ execution
→ new evidence/claims
→ resolution assessment
```

Challenge branches are historical. Reopening adds a new iteration to the same branch rather than replacing the old one.

Resolution semantics distinguish at least RESOLVED, STILL_OPEN, BLOCKED, REOPENED. Conflict resolution also distinguishes substantive resolution from scope/method mismatch or insufficient evidence.

R3.4 later reused this exact feedback path for INCONCLUSIVE semantic relations. R4 should also reuse it for typed Tribunal discoveries instead of inventing another side channel.

---

## 7. Truth-maintenance and invalidation

R2.3 introduced selective invalidation rather than a naive full cascade.

Dependencies can be HARD, SOFT or CONTEXTUAL. Impact traversal is bounded. A changed Source/Evidence/Relation may require revalidation or may reopen a resolved challenge if critical support is lost.

Important principle: knowledge lives in edges as well as nodes.

A Claim may remain valid while the relation `EVD SUPPORTS CLM` becomes STALE/INVALIDATED. Endpoint validity and relation validity are different axes.

GraphEdge lifecycle is versioned:

```text
ACTIVE → STALE → ACTIVE
STALE → SUPERSEDED
ACTIVE|STALE → INVALIDATED
```

SourceCatalog semantic changes can trigger Researcher invalidation through explicit source-identity binding. Byte-only changes do not automatically trigger semantic impact.

This matters for R4: role outputs should not directly mutate these states. They should emit typed artifacts that later feed reducers/admission.

---

## 8. Execution → knowledge admission → linking → assessment

R3 built a strict sequence:

```text
TASK execution
→ TaskExecutionResult
→ ExecutionAdmissionProposal
→ deterministic preflight
→ canonical knowledge admission
→ explicit SemanticRelationProposal
→ canonical GraphEdge
→ RelationAssessment
→ strict reasoning eligibility
```

Do not collapse stages.

Critical invariant:

```text
task completed ≠ claim verified
relation exists ≠ relation accepted for reasoning
accepted relation ≠ claim proven
```

R3.2 forbids co-occurrence inference. Two objects admitted by the same task are not automatically linked. Semantic relation must be explicitly proposed and admitted.

R3.3 added a separate epistemic assessment axis for relations:

- ACCEPTED
- QUALIFIED
- INCONCLUSIVE
- REJECTED

with use states such as ELIGIBLE, QUALIFIED, BLOCKED.

This remains separate from `GraphEdge.kind` and GraphEdge lifecycle state.

R3.4 made assessed-relation reasoning mandatory in the new R3 reasoning facade and connected INCONCLUSIVE/BLOCKED relation assessments back to Gap/ResearchChallenge.

---

## 9. Multidimensional uncertainty field, R3.5

The user explicitly rejected reducing uncertainty to one scalar confidence.

R3.5 models orthogonal uncertainty axes and prepares a Tribunal work field.

Current axes include:

- NUMERIC_MEASUREMENT
- EVIDENCE_SUFFICIENCY
- SOURCE_PROVENANCE
- SCOPE
- METHOD
- CONFLICT
- DERIVATION
- ASSUMPTION
- CAUSALITY
- EXTRAPOLATION
- FRESHNESS

Operational levels:

- RESOLVED
- QUALIFIED
- MATERIAL
- BLOCKING
- UNCHARACTERIZED

Core contracts:

- UncertaintyComponent
- UncertaintyProfile/1.0 (`UPR-*`)
- AssessmentNeed
- ReviewWorkField/1.0 (`RWF-*`)

R3.5 answers:

- what is uncertain?
- why is it uncertain?
- how materially does it block reasoning?
- which assessment methods could reduce it?
- what completion criteria would close the need?

R3.5 does **not** select specialists. That is the clean R4 boundary.

Absent information must not be silently interpreted as RESOLVED. UNCHARACTERIZED is legitimate.

Numeric uncertainty remains a lower-level quantitative layer, not the universal representation of epistemic uncertainty.

---

## 10. ReviewWorkField is the R3→R4 boundary

This is the key handoff object.

```text
ReviewWorkField
+ ResearchDOM lineage dimensions
+ canonical Claim/Relation/Evidence refs
+ policy snapshot
        ↓
R4 TribunalCompositionPlan
```

ReviewWorkField should tell Tribunal what work exists. Tribunal composition decides who should do it.

Do not let Tribunal composition rewrite AssessmentNeeds just to fit available roles. Missing coverage must fail closed or generate a typed missing-expertise requirement.

---

## 11. Tribunal legacy intent to preserve

The old Researcher/AI_ReWriter design is a conceptual source, not runtime authority.

Useful recovered ideas:

- hierarchical `topics_tree` / node-aware review context;
- context inheritance down the branch;
- `expert_registry` / versioned role pool;
- dynamic specialists derived from topic/discipline/method;
- permanent adversarial/meta perspectives;
- asymmetric evidence views;
- claim/node-specific prompts/briefs;
- local bounded escalation;
- honest OPEN when evidence is insufficient;
- later shift from voting to dialectical challenge;
- TMS/ATMS as a possible advanced direction for justification/nogood management.

Do not carry forward literally:

- shell/orangepi orchestration as authority;
- provider/backend names embedded in prompts;
- one LLM simulating the whole panel in one context;
- majority vote as truth;
- aggregator override of truth state;
- giant undifferentiated Tribunal input;
- free-form confidence threshold used as factual state.

---

## 12. Permanent vs dynamic Tribunal roles

The exact permanent core is intentionally not frozen yet.

Current candidate meta-panel:

- Critic
- Skeptic
- Methodologist
- Evidence Auditor

Historical alternatives included Physicist, Advocate and Aggregator. Important interpretation:

- permanent roles are versioned policy entries, not eternal personas;
- `Aggregator` must not become truth authority;
- `Advocate` may be permanent or conditional, still open;
- dynamic roles should be selected from AssessmentNeeds + ResearchDOM lineage + object profile.

Dynamic families discussed/examples:

- physicist of metals
- crystallographer
- XRD specialist
- TEM specialist
- statistician / numerical analyst
- measurement specialist
- causal critic

A role should be modeled as a typed review lens/capability contract, not merely a persona name.

Suggested role metadata:

- stable role ID and family;
- supported uncertainty axes;
- supported assessment methods;
- compatible disciplines/methods/question types;
- allowed logical capabilities/tools;
- evidence-view constraints;
- expected output artifact types;
- independence/cross-examination policy;
- later cost/reliability history;
- policy version/reason codes.

Legacy composition pattern worth preserving:

```text
RoleBrief = RoleTemplate + branch lineage + AssessmentNeed specifics
```

not a generic specialist prompt.

---

## 13. Deterministic composition policy

R4.1 should follow a typed/deterministic path:

```text
AssessmentNeed
+ ResearchDOM lineage
+ Claim/Relation profile
+ policy snapshot
        ↓
required review capabilities
        ↓
role candidates from versioned registry
        ↓
coverage + compatibility filtering
        ↓
minimal sufficient panel
        ↓
AssessmentAssignment[]
```

Rules:

- closed/versioned L1 role taxonomy;
- LLM may propose a missing expertise requirement but cannot create an authoritative role;
- every blocking AssessmentNeed must be covered or fail closed as `UNASSIGNED_NEED`;
- every selected role gets reason codes tied to needs/lineage;
- synonyms/duplicates are deduplicated unless independence policy explicitly asks for duplicate perspectives;
- prefer minimal sufficient coverage, not maximal panel size;
- learned routing belongs later, after enough outcome data exists.

This mirrors the larger recursive-object/routing philosophy of the harness.

---

## 14. Evidence slicing and independence

Evidence visibility is a compiled control-plane contract, not prompt prose.

Planned L1 view classes:

- FULL_RELEVANT
- CLAIM_PLUS_SUPPORT
- CLAIM_PLUS_COUNTEREVIDENCE
- FRESH_CONTEXT
- METHOD_ONLY

Asymmetric views are intentional. They prevent five roles from merely paraphrasing the same summary.

Preferred sequence:

1. independent/fresh first assessment;
2. later cross-examination where another role's typed argument may be disclosed under an inquiry contract.

`FRESH_CONTEXT` should hide preliminary verdicts and other roles' conclusions. Provenance may still be visible when a role's task requires source auditing. Exact fields are policy decisions.

A role must not widen its own evidence slice. Additional evidence requests are typed requests handled by the control plane.

---

## 15. Tribunal is dialectical, not majority-vote truth

The newer target architecture prefers:

```text
Question → Answer → Question-on-answer → Answer
```

with typical depth 2–4, bounded by code.

Participants emit typed artifacts such as:

- Argument
- InquiryQuestion
- Challenge
- Qualification
- MissingEvidence
- PossibleCounterexample
- MethodLimitation
- ScopeIssue
- CausalityProblem
- NumericDiscrepancy

Reducers/admission decide what becomes authoritative state.

Disagreement should survive as typed conflict/challenge, not be averaged away by a vote.

`OPEN` is a legitimate outcome when evidence or capability is insufficient.

Later rounds may adapt panel composition when new AssessmentNeeds appear, but revisions must be historical/versioned.

---

## 16. Human expert model

A human expert is an actor in the same provenance chain, not an oracle.

Conceptual positions:

- SUPPORT
- CHALLENGE
- QUALIFY
- REJECT
- REQUEST_RESEARCH

Human assertions may be wrong and must remain independently checkable. Researcher may search/verify them and preserve conflicts.

The human is external to the automated panel, not automatically a permanent seat. Escalation policy decides when to involve one.

---

## 17. Authority and trust boundaries

Preserve these distinctions:

```text
observation
!= admission
!= semantic relation
!= relation assessment
!= uncertainty characterization
!= Tribunal argument
!= authoritative claim truth
```

Similarly:

```text
Guard PASS != factual correctness
Review role recommendation != state transition
CompositionPlan != Tribunal outcome
```

The control plane owns:

- policy;
- route admissibility;
- evidence slices;
- typed contracts;
- state/revision checks;
- budgets;
- stop decisions;
- reducer/admission transitions.

Work-plane agents produce semantic artifacts inside that envelope.

---

## 18. Retry, rework, replan and escalation are different

Do not flatten all continuation into “retry”.

- Retry: same semantic operation after transient/provider failure.
- Selective rework: new attempt only for bounded failed scope.
- Replan: decomposition/strategy itself is wrong.
- Escalation: decision owner changes because ambiguity/capability/permission remains.

R4/R5 should retain this vocabulary when Tribunal inquiry loops are added.

No-progress cut-off is preferred over blindly consuming full iteration budgets.

---

## 19. Stop semantics

Timeout, budget exhaustion and capability absence are not success.

Long-term desired terminal vocabulary includes SUCCESS/DONE, PARTIAL, BLOCKED, UNRESOLVABLE, ESCALATED and OPEN where epistemically appropriate.

Not all runtime reducers currently implement the full vocabulary. Do not document a state as executable until the reducer actually produces it.

Tribunal inquiry needs explicit depth/hop/token/time budgets and honest unresolved termination.

---

## 20. User's development style and expectations

Recurring working preferences that materially affect implementation:

- cold, implementable architecture, no marketing language;
- code should “lead the LLM by the hand” through typed contracts and mandatory checks;
- heuristics are acceptable for guardrails/routing/orchestration, not as hidden semantic authority;
- avoid brittle hardcode, but prefer explicit closed L1 taxonomies before learned/dynamic systems;
- use 3–4 rounds of critique/revision for important architecture;
- keep an adversarial/auditor view of each claim and transition;
- document architecture while coding, not afterward;
- every block should state limitations and complexity-development ladder;
- track tech debt formally, including known baseline failures;
- preserve milestone ZIPs/recovery bundles and clean Git boundaries;
- do not opportunistically fix unrelated debt in a phase unless it blocks acceptance;
- use round-trip semantic validation for professional/research writing: extract realized claims after drafting and compare to authorized claims for scope shift, modality shift, causality upgrade, numeric drift, unauthorized claims and omissions.

---

## 21. Known infrastructure/debt context to keep visible

Important open items at R3.5 boundary:

- TD-015: four known Guard/LocalCorpus baseline failures.
- TD-017: `evidence.verify` provider-priority conflict.
- TD-020: SQLite ResourceWarnings.
- TD-021: Writer SourceCatalog free-string IDs vs Researcher canonical `SRC-*` identity.
- TD-022: no dedicated relation history/state index for large graphs.
- TD-023: restore/recovery needs one automated verifier; `.git` loss happened twice during development.
- TD-024: live Coder/Writer transport/outbox not implemented.
- TD-026: LocalDocumentExtractionCapsule source/hash vocabulary mismatch.
- TD-027: AdmissionIdentityMap depends on accepted-ID ordering.
- TD-028: cross-admission semantic linking authorization absent.
- TD-032: richer DERIVED_FROM/QUANTIFIES validators incomplete.
- TD-033: automatic uncertainty adapters incomplete for provenance/freshness/causality/assumption/extrapolation; Gap taxonomy partly string-family based.
- TD-034: numeric uncertainty remains projection-only; canonical Quantity/Measurement uncertainty model missing.

Do not mix these into R4.1 unless an acceptance gate genuinely requires them.

---

## 22. Known validation baseline

At the R3.5 handoff:

- R3.5 new tests: 11/11 PASS.
- targeted uncertainty/R3 integration: 88/88 PASS.
- full Researcher: 488 total, 484 PASS, same four TD-015 failures.
- runtime policy compiler: PASS, hash unchanged.
- capability compiler: PASS, hash unchanged.
- compileall: PASS.
- git diff --check: PASS.

Canonical HEAD:

`fe57c88312755d01e91a1ff1357481f577b71945`

---

## 23. R4.1 acceptance invariants

Treat these as hard starting gates:

1. Same typed input + same policy snapshot ⇒ identical composition.
2. Composition cannot mutate Claim/GraphEdge/Gap/truth state.
3. Every blocking AssessmentNeed is covered or fails closed as `UNASSIGNED_NEED`.
4. Unsupported role invention is rejected.
5. Role selection has reason codes and policy version/hash.
6. Evidence view is compiled by code; prompt cannot widen it.
7. Fresh-context assignment does not leak disallowed evidence or previous conclusions.
8. Role taxonomy is closed/versioned at L1.
9. Minimal sufficient panel is preferred over maximal role count.
10. R4.1 stops at composition/brief contracts. No live Tribunal dialogue yet.

---

## 24. Open decisions that must not silently default

Still open at handoff:

- exact permanent meta-panel;
- Advocate permanent vs conditional;
- exact evidence-view defaults per role;
- fresh-context provenance visibility;
- inquiry depth/budget policy;
- later quorum/aggregation semantics without majority truth;
- adaptive recomposition between rounds;
- domain role-pack loading/admission;
- historical-effectiveness/learned role ranking later;
- human expert insertion/escalation policy;
- exact role taxonomy schema and compatibility scoring.

Use `harness/handoff/R4_OPEN_DECISIONS_REGISTER.md` as the working register.

---

## 25. Recommended next implementation sequence

R4.1 should remain small and deterministic:

```text
1. write architecture doc
2. define typed role/composition contracts
3. define versioned role registry/policy
4. define required-capability derivation from AssessmentNeed + lineage
5. implement deterministic candidate filtering/coverage
6. implement minimal sufficient panel selection
7. implement assignments + reason codes
8. implement evidence-view policy contracts (not live slicing if scope is too large)
9. fail closed for uncovered blocking need
10. tests + docs + pipeline audit
```

Only after R4.1 composition is stable should the project move toward role-specific evidence slicing, inquiry contracts, independent first-pass workers and later dialectical loops.

---

## 26. Concrete scientific example used repeatedly in design

A recurring demo branch was BCC lattice parameter / XRD interpretation:

- observed lattice/peak change;
- possible compositional effect;
- residual stress not excluded;
- Gap becomes a ResearchChallenge;
- lineage contains crystallography / physics of metals / XRD / measurement or causal question;
- R3.5 would characterize METHOD, EVIDENCE_SUFFICIENCY, possibly CAUSALITY/SCOPE uncertainty;
- R4 composition should therefore select suitable review capability such as XRD/crystallography/measurement expertise rather than a generic prose critic only.

This is an example for testing routing/composition, not a hardcoded domain rule.

---

## 27. What not to do in the next session

- Do not reopen R3.5 uncertainty modeling unless an R4 acceptance test exposes a genuine blocker.
- Do not let the LLM invent authoritative specialists.
- Do not make every role see the entire evidence corpus.
- Do not use majority vote to set truth.
- Do not create a new scheduler for Tribunal jobs.
- Do not let Tribunal mutate Claim/Gap/GraphEdge state directly.
- Do not collapse role, skill, tool and capability into one string label.
- Do not introduce learned routing before deterministic policy is testable and data exists.
- Do not silently fix unrelated legacy/Guard/SQLite debt under R4 commit boundaries.
- Do not lose history when panel composition changes between later rounds.

---

## 28. One-line continuation cue

**Start R4 by compiling a deterministic, versioned, minimal-sufficient TribunalCompositionPlan from ReviewWorkField + ResearchDOM lineage + object profile; stop before live dialogue.**
