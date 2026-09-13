# Current architecture state — Writer v1 + Researcher R3.1

This snapshot records the active architecture through Researcher R2.3.3, including adaptive challenge lifecycle, selective invalidation, provenance-triggered reopen and versioned graph-relation lifecycle.

## Peer orchestrators

Writer, Researcher and Coder are peer orchestrators. Each owns its domain reducer and subordinate agents. Cross-domain work is delegated through typed contracts over the shared Job/Attempt/Child runtime rather than by direct mutation of another orchestrator's state.

## Writer

Writer v1 is frozen around typed references/evidence, per-claim evidence selection, tiered cross-language style authority, ProposedClaim handling, structured DraftArtifact, optimistic DOM patching, ChangeLedger, authority binding, semantic round-trip and selective repair.

Rendered claim markers are a checked projection; DOM paragraph claim bindings are authoritative after patch application.

## Researcher

Researcher is based on `scripts/researcher/researcher_core` and remains a full peer orchestrator.

Current planning side:

ResearchRequest -> PlanningDialectic -> ResearchMap -> ResearchCard proposals -> ResearchPatch -> ResearchDOM -> PlanningGate -> persistence/replay.

ResearchDOM is an immutable historical card tree. Cards retain multidimensional metadata such as direction, discipline, question type, method and capability so later tribunal composition can be derived from ancestry rather than reclassified from raw claim text.

`ResearchTraceLink` is the current bridge from planning cards to knowledge entities.

## Universal recursive object-processing principle

The harness treats meaningful units as typed information objects. Examples include objectives, tasks, directions, questions, claims, gaps, evidence spans, paragraphs and computational defects.

The recurring processing pattern is:

Object -> Profile -> Candidate specialists/tools/skills -> Code-owned routing -> Processing -> Artifacts -> Validation -> State transition/new objects.

Decomposition stops when further splitting no longer materially improves executability, verifiability or information gain. This is a practical workflow stopping criterion, not an assertion that Kolmogorov complexity is computable for arbitrary objects.

Specialists, tools and skills are themselves typed entities with individual capability profiles, limitations, cost/availability and historical utility. Routing decisions must be provenance-bearing and versioned so future ranking can learn from actual outcomes.

Three structures remain intentionally distinct:

1. ResearchDOM / task tree: decomposition, execution history and ownership.
2. KnowledgeGraph: semantic and epistemic relationships among claims, evidence, gaps, conflicts, assumptions and artifacts.
3. RoutingHistory: why a specific specialist/tool/skill bundle was chosen for a specific object.

## Current adaptive Researcher loop

Implemented through R2.2:

Gap/Conflict -> ResearchChallenge -> CHALLENGE card -> PlanningDialectic -> executable subtree -> ResolutionAssessment -> resolved/still-open/blocked/reopened lifecycle.

## Next boundary

R2.3 adds negative feedback and historical reopen:

Source/Evidence change -> DependencyImpactAssessment -> stale resolution/relation -> selective revalidation or REOPENED challenge -> new iteration in the same historical branch.

Tribunal/search/live peer delegation remain later layers; R2.3 prepares the dependency semantics they will consume.

## Documentation discipline

From 2026-09-12 each new architectural block must document purpose, authority, contracts, links, current limits, failure behavior, complexity ladder, tests, tech debt and legacy lineage. See `ARCHITECTURE_BLOCK_DOCUMENTATION_STANDARD.md`.

## Researcher R2.3 first-slice status

Negative knowledge feedback is now implemented at deterministic L0/L1: explicit typed dependencies are traversed with bounded impact propagation; redundant evidence causes revalidation without full reopen, sole HARD support can reopen the same historical challenge branch, contextual non-overlap is ignored, and relation-only invalidation can stale a relation without destroying endpoint claims.

New canonical artifacts: `KnowledgeDependency/1.0`, `DependencyImpactAssessment/1.0`, `ChallengeIteration/1.0`.

Current boundary deliberately stops before automatic dependency extraction and SourceCatalog-trigger wiring. Those are tracked as TD-018/TD-019 rather than hidden in the feature.


## R2.3.1 provenance-derived invalidation

Researcher now derives R2.3 dependency records from canonical provenance rather than requiring hand-authored KDP lists. Writer SourceCatalog semantic changes are normalized and, through explicit source identity binding, can drive selective impact/reopen of the same historical challenge branch. BYTE_ONLY changes remain non-semantic and do not reopen knowledge. Shared canonical Source identity remains an explicit next integration debt (TD-021).


## R2.3.3 relation-level truth maintenance

Canonical `GraphEdge` relations are now versioned information objects with ACTIVE/STALE/SUPERSEDED/INVALIDATED lifecycle. Dependency impact may stale an EDG relation without mutating endpoint claims. Relation transitions are optimistic-concurrency checked, replayable through `EDGE_STATE_CHANGED`, visible in service artifacts, and consumed by provenance dependency compilation. Legacy relation event records without state remain backward-compatible as ACTIVE. Dedicated durable relation-history indexing remains TD-022.


## R2 branch freeze and R3 execution boundary

R2.x is now treated as a stable planning/knowledge feedback base. Further R2 development remains possible without blocking execution: relation-history indexing, shared source identity, richer dependency semantics, TMS/ATMS-like justification environments and learned routing are documented in `RESEARCHER_R2_BRANCH_FUTURE_DIRECTIONS.md`.

R3-L1 adds leaf execution while preserving peer boundaries:

`TASK/DELEGATION -> TaskExecutionPlan -> LOCAL Capsule or DelegationRequest -> Job/Child runtime -> TaskExecutionResult -> ResearchCard COMPLETED/BLOCKED`.

Task completion is operational state only. It does not establish a Claim or admit Evidence. Local outputs are untrusted `CapsuleObservation`; peer outputs are artifact references. Typed plans/delegations/results are persisted through the existing SQLite UoW.

R3.1 is now implemented as a typed execution-output admission bridge:

`TaskExecutionResult -> ExecutionAdmissionProposal -> deterministic validator preflight -> existing ClaimRegistry -> ExecutionAdmissionReceipt -> ResearchTraceLink.PRODUCED`.

Successful execution remains operational state only until this admission path accepts typed proposal objects. Local observations can admit explicit ClaimProposal, QuantityProposal, Source and EvidenceSpan objects. Peer artifacts require an explicit typed adapter output; arbitrary artifact interpretation is not allowed. The next boundary is post-admission semantic linking and richer dependency-closed admission, not another registry.

## R3.2 explicit semantic linking

Post-admission execution outputs can now create canonical KnowledgeGraph relations only through explicit typed relation proposals:

`ExecutionAdmissionReceipt -> AdmissionIdentityMap -> SemanticRelationProposal -> deterministic relation gate -> ClaimRegistry(GraphEdge) -> SemanticLinkReceipt -> ResearchTraceLink(PRODUCED -> EDG)`.

No edge is inferred from co-occurrence. L1 enables EVD->CLM SUPPORTS/CONTRADICTS, QTY->CLM QUANTIFIES and CLM->CLM DERIVED_FROM. Claim truth state remains unchanged by edge admission. Cross-admission endpoints and richer relation policy remain future extensions (TD-027/TD-028).

## R3.3 canonical relation assessment

R3.3 separates declared semantic relations from reasoning-eligible relations:

`GraphEdge -> RelationAssessmentProposal -> deterministic relation assessment -> ACCEPTED/QUALIFIED/INCONCLUSIVE/REJECTED -> reasoning eligibility / optional lifecycle projection`.

`GraphEdge.edge_kind`, `GraphEdge.state` and `RelationAssessment.verdict/use_state` are intentionally separate axes. ACCEPTED/QUALIFIED relations may participate in strict reasoning; INCONCLUSIVE relations remain historically ACTIVE but are blocked from semantic use; REJECTED relations may transition to INVALIDATED through the existing R2.3.3 lifecycle reducer. Endpoint Claim/Evidence state is untouched and Claim remains OPEN until later claim-level evidence assessment/Tribunal.

Full pipeline audit confirms execution -> admission -> explicit linking -> relation assessment -> lifecycle projection -> strict dependency compilation -> service artifact. New integration debts TD-029..TD-032 cover mandatory runtime wiring, canonical lifecycle persistence, relation-level challenge feedback and specialized kind-specific validators.


## R3 base closure update — R3.4

R3 is now closed as an L1 base control loop before Tribunal work. The path is:

```text
ResearchDOM TASK
→ execution/delegation
→ typed admission
→ explicit semantic linking
→ relation assessment
→ strict reasoning eligibility
→ ACCEPTED/QUALIFIED: usable relation
→ INCONCLUSIVE: Gap → ResearchChallenge → CHALLENGE → executable TASK
→ REJECTED: relation lifecycle → canonical EDG revision
```

The loop preserves the central authority rule: observations/proposals do not directly mutate epistemic truth. Deterministic reducers/admission boundaries own state transitions.

R3 future work no longer blocks R4: richer relation-kind validators (TD-032), cross-admission endpoint authorization (TD-028), registry-native identity mapping (TD-027), large-graph relation history/index (TD-022), live peer transport (TD-024), and automated repository recovery verification (TD-023).

## R3.5 uncertainty field boundary (2026-09-13)

R3 now ends with an explicit pre-Tribunal uncertainty/work projection:

```text
canonical Claim/Edge/Gap/Conflict/Quantity context
→ RelationAssessment + admitted issues + numeric uncertainty observations
→ UncertaintyComponent[]
→ UncertaintyProfile/1.0 (UPR)
→ ReviewWorkField/1.0 (RWF)
→ R4 TribunalCompositionPolicy
```

R3.5 intentionally does not use a scalar confidence score and does not choose specialist roles. It records uncertainty axis, operational level, blocking status, provenance/reason codes, appropriate assessment methods and completion criteria. R4 receives the RWF plus ResearchDOM dimensions and decides which permanent/dynamic specialists should assess each need.

Implemented L1 axes include numeric measurement, evidence sufficiency, source provenance, scope, method, conflict, derivation, assumption, causality, extrapolation and freshness vocabulary; automatic adapters are currently strongest for relation method/evidence/scope, Gap/Conflict and explicit numeric interval observations. See TD-033/TD-034 for remaining canonical adapters.

## Update 2026-09-13 — R4.1 composition started

R3.5 remains the stable pre-Tribunal boundary. R4.1 now has an implemented deterministic composition compiler and versioned role policy. The compiler maps `ReviewWorkField + ResearchDOM lineage + object profile + policy snapshot` to `TribunalCompositionPlan`; it does not run judges or mutate truth state.

Current R4.1 implementation introduces closed/policy-defined permanent and dynamic roles, AssessmentNeed assignments, evidence-view contracts, allowed capabilities/tools, deterministic synonym-role deduplication, central authority validation, policy hash and composition fingerprint. Full Researcher regression, demo and audit are complete; R4.1 is L1-complete with Git/package/recovery boundary created. The next implementation boundary is R4.2 executable evidence slicing.

Decision lineage for accepted/rejected/open patterns is now maintained in `R4_DECISION_LOG.md` as a required session-migration artifact.


## Update 2026-09-13 — R4.2 executable evidence slicing

R4.2 now compiles the R4.1 EvidenceViewPolicy into deterministic, bounded per-role `TribunalEvidenceSlice` objects from canonical Claim/Quantity/Source/EvidenceSpan/GraphEdge state. The compiler implements support/counter asymmetry, conservative method-only views, genuinely blind fresh-context projection, visible missing/truncated status and deterministic fingerprints. It performs no search, provider execution, dialogue or knowledge-state mutation.

The nearest-chain E2E (`RelationAssessment -> UncertaintyProfile -> ReviewWorkField -> TribunalCompositionPlan -> TribunalEvidenceBundle`) found a real R3.5→R4 seam: `AssessmentNeed.target_refs` can contain control refs such as `RAS-*`. R4.2 now separates projectable semantic/evidence refs from explicit nonprojected control refs instead of misreporting them as missing evidence. This strengthens the case for TD-038, a future non-authoritative cross-layer traceability/lineage substrate.

Legacy Tribunal levels were rechecked. The retained direction is independent first-pass review -> optional challenge/Advocate defense -> bounded Q1/A1/Q2/A2 cross-examination -> typed discoveries -> existing ResearchChallenge/reducer loop. R4.2 intentionally stops before any of those live dialogue stages. Domain role packs remain TD-036.

Validation: R4.2 local/E2E 17/17 PASS; R3.5+R4.1+R4.2 targeted 40/40 PASS; full Researcher 517 total / 513 PASS with only the same four TD-015 baseline failures; runtime/capability compiler hashes unchanged; compileall/diff checks/demo PASS. The next hard boundary is R4.3 typed inquiry contracts plus independent first-pass execution over R4.2 slices, using the existing Job/Attempt runtime.

R4.2 feature commit is `061bffa5ff5c3e0c638c50bb1c3f4b07d31e3061` (`researcher: compile r4 tribunal evidence slices`). Milestone package `RESEARCHER-R4.2-EVIDENCE-SLICING-001.zip` has SHA256 `dab5a998af72c6b479b88ae0360eb760511327fc3d7b70536e6e9adf23610a88`. A final metadata boundary commit and complete recovery bundle close the phase.

## Update 2026-09-13 — R4.3 independent role execution + semantic handbook

R4.3 now closes the first executable Tribunal role vertical without introducing a panel/chat orchestrator. The implemented chain is:

```text
R3.5 ReviewWorkField
-> R4.1 TribunalCompositionPlan / RoleBrief
-> R4.2 role-specific EvidenceSlice
-> R4.3 InquiryContract
-> existing child Job / Attempt
-> bounded semantic role worker
-> InquiryTurn + ArgumentArtifact
```

`ArgumentArtifact` is non-authoritative. Worker citations, discoveries and additional-evidence requests are admitted only if they remain inside the bound EvidenceSlice/AssessmentNeed authority. Invalid output becomes runtime `FAILED_NO_OUTPUT`; a scientifically unresolved but valid assessment may emit semantic `OPEN`. Claim/GraphEdge/Gap/Conflict state is not mutated by role execution.

A separate versioned Role Handbook now supplies semantic duties for already-admitted roles: mission, mandatory checks, forbidden moves, stop conditions, discovery focus and phase variants. It cannot grant role admission, tools/capabilities or evidence visibility. Missing handbook guidance creates a deterministic code-owned `RoleHandbookFillRequest` and a proposal-only skeleton; automatic domain-role admission remains TD-036.

The first full vertical E2E uses `xrd_specialist` over the BCC/XRD chain from RelationAssessment through R4.2 slice and real Job/Attempt lifecycle. A second E2E executes `xrd_specialist` and `crystallographer` independently from the same composition plan and confirms distinct evidence-view/instruction fingerprints and distinct argument artifacts with no automatic cross-disclosure.

Legacy Tribunal stage semantics remain downstream: independent first pass -> conditional challenge/Advocate defense -> bounded `Q1/A1/Q2(on A1)/A2` -> typed discoveries -> existing ResearchChallenge/reducer path. R4.3 L1 runtime explicitly rejects challenger/cross-exam instruction variants under an independent-first-pass contract.

Repository acceptance is now self-bootstrapping through `scripts/run_researcher_acceptance.py`, closing TD-040. Live provider health/binding remains TD-037; universal cross-layer traceability remains TD-038; domain role packs remain TD-036.

## Update 2026-09-13 — R4.4 L1 dialectic observation and bounded escalation

R4.4 now has a deterministic control substrate over admitted Tribunal outputs. Dialogue depth is explicit and separate from epistemic confidence:

```text
L0 independent
-> L1 challenge
-> L2 direct Q/A
-> L3 question-on-answer
-> L4 local research/recomposition
-> L5 external escalation (reserved)
```

The controller does not parse scientific prose to decide correctness. It observes typed `InquiryDiscovery`, `AdditionalEvidenceRequest` and bounded `DialecticIssueProposal` objects, computes content-addressed novelty/repetition, evidence-frontier change, position change and no-progress streak, then emits a non-authoritative `DialecticControlDecision`.

A follow-up is therefore justified by a new testable surface rather than by unused turn/token budget. Blocking missing evidence can terminate conversation and explicitly reuse the existing `Gap -> ResearchChallenge -> PlanningDialectic` feedback path. The new E2E exercises `first-pass -> Q1/A1 -> new assumption -> Q2(on A1)/A2 -> local research -> ResearchChallenge` and validates historical parent-turn links.

Future role portability is documented separately in `ROLE_CARD_PORTABLE_DOM_FUTURE.md`: role semantics may eventually be represented as `RoleReference + RoleCard + RoleParameterGraph + variants/evaluation` inside a portable YAML DOM, but imported role semantics never carry runtime authority. This direction is TD-041; admitted domain role packs remain TD-036.

Live challenger/questioner/answerer execution remains gated by TD-037 shared provider binding and by a future compiled dialectic disclosure contract (TD-043). Fixture E2E proves control semantics only, not production semantic-review quality.

Post-E2E hardening added historical issue resolution/reopen semantics, explicit full-chain turn counting, and non-truncating issue fanout control. Current R4 targeted acceptance is 67/67 PASS; full Researcher is 544 total / 540 PASS with only the unchanged four TD-015 baseline failures.

## Update 2026-09-13 — R4.4 L2a branching argument graph + conditional Advocate

Tribunal history is no longer limited to one linear turn chain. `ArgumentArtifact` nodes can now be connected by versioned `ArgumentRelation` objects (`ATTACKS`, `UNDERCUTS`, `REPLIES_TO`, `DEFENDS`) inside an acyclic fingerprinted `ArgumentGraphProjection`. This graph records review-process topology only; it is not a second KnowledgeGraph and cannot mutate Claim/GraphEdge truth.

Advocate is now an admitted but non-composed role. It appears only when a material active attack/undercut targets a still-defensible supported argument within shared AssessmentNeed scope. A branch-local `DialecticDisclosureContract` exposes only the attacked argument, selected challenge and refs already cited by those artifacts; sibling argument branches remain hidden. `AdvocateDefenseContract` binds that disclosure to the local role policy/handbook, allowed outcomes and budget.

Advocate outputs are historical arguments, not verdicts. `DEFEND/QUALIFY` create a reply to the challenge plus a defense relation to the attacked argument and route toward cross-examination. `CONCEDE_LOCAL_POINT` returns to dialectic control without manufacturing a defense edge. `REQUEST_EVIDENCE`/OPEN can stop defense; a typed evidence request reuses the existing R4.4 observer and canonical `Gap -> ResearchChallenge` feedback path.

TD-043 is only partially resolved: the graph and Advocate disclosure are executable, but challenger/questioner/cross-exam still need one generic disclosure compiler. TD-044 now explicitly records a future option to reuse Writer claim splitting/graph/semantic-round-trip machinery to propose issue facets and paraphrase equivalence, while Researcher retains admission authority.

## Update 2026-09-13 — R4.4 L2b generic disclosure, typed question targeting and branch history

R4.4 L2b generalizes the L2a Advocate-only disclosure path. `DialecticDisclosureContract/1.1` now lives in the shared `tribunal_disclosure.py` control-plane module and compiles branch-scoped visibility for challenge, direct-question, question-on-answer and defense phases. The Advocate API remains a compatibility wrapper over the same compiler.

`DialecticBranchRef` gives each selected argument branch a stable content-addressed key while keeping AGP revision/fingerprint/current head as moving snapshot state. `DialecticBranchHistory` binds no-progress, active/resolved issue signatures, Q/A count and token usage to that branch and supports deterministic checkpoint serialize/restore. Two sibling attacks no longer share dialectic counters or issue lifecycle.

`DialecticQuestionContract/1.0` (`DQC-*`) gives Q1/Q2 their own authority boundary. Q2 must target an exact newly admitted issue surface from A1. Parent turns, target arguments/issues, visible refs, closure surface, follow-up budget, handbook fingerprint and policy hash are all explicit. Answer admission checks both `InquiryTurn.cited_refs` and `ArgumentArtifact` references, closing a hidden-ref leakage path that argument-only validation would miss.

Cross-examination is allowed to reveal selected prior-argument evidence that was absent during independent first pass, but only through an explicit fingerprinted DDC; roles/prompts cannot widen their own view.

Local research escalation now carries exact branch dimensions and a `DialecticResearchResumeAnchor` linking RCH/GAP to the DBR/AGP/issue/history fingerprint. This closes the structural branch-resume seam without creating a second scheduler or truth authority.

TD-043 (generic disclosure) and TD-045 (branch-scoped history/replay) are closed at this structural boundary. TD-037 live provider binding, TD-042 live observer calibration and TD-044 semantic issue identity remain open. The next hard boundary is R4.4 L3 live bounded dialogue using the shared Job/Attempt/provider runtime.

## Update 2026-09-13 — R4.4 L3A provider binding and executable bounded dialogue

R4.4 now separates semantic role assignment from runtime provider selection. `DialecticQuestionContract/1.1` records both the questioner and the addressed answer role; live E2E found and eliminated the previous ambiguous responder seam. Current bounded dialectic rejects accidental self-response.

`RoleProviderBinding/1.0` resolves an admitted role/contract through the shared provider authority, capability preflight and tool runtime bindings. Compatibility requires capability, role kind, contract namespace, live-probe policy, current provider availability and runtime binding. Multiple compatible providers are deterministic candidates, not implicit redundant executors.

`TribunalExecutionEnvelope/1.0` is the only bounded provider input and contains exactly the DDC/DQC-visible artifacts/refs. `ProviderExecutionReceipt/1.0` persists runtime completion/failure/timeout/rejection independently of semantic `IQT/ARG` admission. Live answer ARGs must enter a new ArgumentGraph revision before DialecticObserver can consume them.

Process E2E now executes Q1/A1/Q2/A2 through the existing child Job/Attempt runtime and tests stale provider, timeout, invalid JSON, hidden-ref rejection, wrong role/provider/kind/contract, zero providers, multiple providers and executor-cardinality overflow. A second DOMAIN-role E2E proves role-kind compatibility outranks raw provider priority.

The shared production provider `existing.opencode_tribunal_role` is registered but current preflight reports it degraded/unavailable because `opencode` is absent. Therefore this boundary proves provider/runtime contracts and process-level live execution, not production scientific LLM quality. The milestone is named R4.4 L3A rather than claiming full live Tribunal completion.

The responder issue uncovered by live E2E is broader than one DQC. Future TD-046 introduces response/facet ownership and Defender/Advocate arbitration; TD-047 introduces a multidisciplinary `ClaimReviewCase` fork/join model. Advocate remains conditional and is not the default owner of scientific content. Multidisciplinary joins must preserve branch coverage/dependencies/conflicts rather than vote.


## Update 2026-09-13 — R4.4 L3B grounded dialogue and live conditional Advocate

Live semantic output now records its grounding origin instead of treating role authority as evidence. `ArgumentArtifact` carries `ResponseGroundingItem[]` and a deterministic state separating disclosed evidence, visible context/derivation, explicit assumptions and `MODEL_PRIOR`. Model prior remains useful for hypothesis generation but cannot close a scientific branch: a non-OPEN prior-only response creates blocking evidence debt and a typed research request.

Conditional Advocate now executes through the same RPB/TEX/Job-Attempt/PER path as other roles. Evidence-grounded QUALIFY/DEFEND can create `REPLIES_TO + DEFENDS`; prior-only DEFEND is downgraded to REQUEST_EVIDENCE and creates no DEFENDS edge. Hidden sibling grounding fails closed.

Production semantic quality remains unvalidated because the configured OpenCode provider is still unavailable in this environment (`missing:opencode`). The current process-level E2E proves authority, traceability, grounding semantics and live Advocate routing, not scientific LLM quality.

The multidisciplinary direction is one canonical Claim with independent review subbranches inside one future ClaimReviewCase. Rejoin semantics retain coverage, dependencies, conflicts and synergy; they do not vote or average confidence.

## Future research-cycle checkpoint — 2026-09-13

The post-L3B architecture now distinguishes role identity, response grounding and evidence authority. A specialist/Advocate response is an ArgumentArtifact; it becomes scientifically useful only through explicit grounding and canonical evidence/derivation links.

A future `HypothesisCase` layer is documented but not implemented. It should preserve append-only hypothesis revisions, discriminating verification plans, competing hypotheses, evidence/counterevidence/limitations, multidisciplinary review subbranches and repeated ResearchChallenge iterations. Hypothesis state remains multidimensional and does not replace ClaimAssessment.

A single canonical Claim remains the root of multidisciplinary review. `ClaimReviewCase`/ReviewFacet branches are independent in Q/A/ARG state but are intended to rejoin by coverage, dependencies, conflict and synergy rather than vote. See `RESEARCHER_FUTURE_HYPOTHESIS_VERIFICATION_CYCLE.md` and `RESEARCHER_R4_4_FUTURE_RESPONSE_OWNERSHIP_MULTIDISCIPLINARY_REVIEW.md`.

Production semantic OpenCode execution remains an external gate. The sandbox is Linux x86_64 but currently has no external DNS; cloud-only semantic execution therefore requires the documented remote trace-pack workflow or a locally reachable/offline backend. See `OPENCODE_PRODUCTION_SEMANTIC_TRACE_HANDOFF.md`.
