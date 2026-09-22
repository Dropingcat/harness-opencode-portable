# R4 Discussion / Decision / Pattern Log

Status: ACTIVE. This file is a session-migration artifact and MUST be updated with each meaningful R4 design change.

## Record format

Each record contains: ID, status, date, question, decision/pattern, rationale, rejected alternatives, consequences, revisit trigger.

Statuses: `ACCEPTED`, `REJECTED`, `OPEN`, `SUPERSEDED`, `EXPERIMENTAL_POLICY`.

---

## R4-D001 — R3/R4 authority boundary

**Status:** ACCEPTED
**Date:** 2026-09-13

**Question:** Should Tribunal determine what is uncertain?

**Decision:** No. `ReviewWorkField` is the R3→R4 boundary. R3 owns characterization of uncertainty and AssessmentNeeds; R4 owns composition of assessors and work contracts.

**Rationale:** prevents Tribunal from inventing its own problem statement and keeps uncertainty analysis separately testable.

**Rejected:** prompt-only Tribunal that first decides what to investigate.

**Revisit:** only if an R4 acceptance test proves RWF structurally insufficient; do not reopen R3.5 for convenience.

## R4-D002 — Composition before dialogue

**Status:** ACCEPTED

**Decision:** R4.1 stops at `TribunalCompositionPlan`. No live judges, attacks, votes or aggregate verdicts.

**Rejected:** port legacy `tribunal-judge.md` directly into the new runtime.

**Reason:** composition must be deterministic/testable before LLM dialogue exists.

## R4-D003 — Closed/versioned role taxonomy

**Status:** ACCEPTED

**Decision:** authoritative roles come from `config/tribunal_composition.yaml`. LLM may later propose missing expertise but cannot create an authoritative role at runtime.

**Rejected:** free-form role names generated from the prompt.

**Consequence:** unsupported role requests fail closed.

## R4-D004 — Permanent panel is policy, not architecture

**Status:** EXPERIMENTAL_POLICY

**Current policy:** Critic + Skeptic + Methodologist + Evidence Auditor.

**Reason:** retains independent meta-review coverage while removing legacy hardcoded five-role prompt.

**Rejected as architecture invariant:** fixed permanent panel compiled into Python.

**Revisit:** after R4.3/R4.4 empirical role utility and duplication data.

## R4-D005 — Advocate handling

**Status:** OPEN / DEFERRED

**Decision for R4.1:** Advocate is not permanent and is not yet instantiated.

**Reason:** without live dialectic, “defend the claim” is not a meaningful composition function and risks systematic confirmation bias.

**Candidate later rule:** activate Advocate conditionally after a typed attack/challenge exists, with bounded evidence and explicit defense contract.

## R4-D006 — Aggregator handling

**Status:** ACCEPTED FOR R4.1

**Decision:** no Aggregator role in composition L1.

**Reason:** there are no typed Tribunal findings to aggregate yet. Majority-vote truth from legacy is explicitly rejected.

**Revisit:** R4/L4 aggregation semantics.

## R4-D007 — AssessmentNeed identity seam

**Status:** ACCEPTED TEMPORARY BRIDGE

**Problem:** R3.5 `AssessmentNeed` has no EntityId although R4 assignments require stable need references.

**Decision:** use R4-local content-addressed `AssessmentNeedRef(ANR-hash, ordinal)` without mutating the completed R3.5 contract.

**Rejected:** silently use list index as identity; opportunistically redesign R3.5 during R4.1.

**Debt:** TD-035 canonical AssessmentNeed identity.

## R4-D008 — Evidence asymmetry belongs to code contract

**Status:** ACCEPTED

**Decision:** `EvidenceViewPolicy` is compiled by R4; role prompts may not widen it.

**Preserved legacy pattern:** asymmetric views reduce correlated failures.

**Rejected legacy mechanism:** `judge_brief.py`/prompt owns final slicing semantics.

## R4-D009 — Fresh-context provenance visibility

**Status:** EXPERIMENTAL_POLICY

**Current policy:** Skeptic `FRESH_CONTEXT`, `include_previous_conclusions=false`, `include_provenance=false`.

**Reason:** strongest independence from prior verdict/source-prestige anchoring at first pass.

**Risk:** hiding provenance may prevent source-quality critique.

**Revisit:** R4.2 should test two-stage fresh pass: blind first pass followed by provenance reveal.

## R4-D010 — Role synonym handling

**Status:** ACCEPTED

**Decision:** roles have `equivalence_group` and `selection_priority`; compiler keeps one canonical candidate per equivalence group.

**Rejected:** string-name dedup only.

## R4-D011 — Lineage routing semantics

**Status:** ACCEPTED L1

**Decision:** role activation uses structural ResearchDOM lineage card kinds and declared dimension/title tags. No unrestricted semantic inference over arbitrary prose.

**Reason:** reproducibility and inspectable routing.

**Future:** typed domain vocabularies / admitted role packs, not opaque learned routing first.

## R4-D012 — Capability/tool authority

**Status:** ACCEPTED

**Decision:** Tribunal role policy may only name capabilities/tools present in central registries. Policy load fails closed otherwise.

**Rejected:** separate Tribunal-only tool registry.

## R4-D013 — Inquiry depth and token budget

**Status:** EXPERIMENTAL_POLICY

**Current values:** depth=2, token budget=6000 per assigned role.

**Meaning in R4.1:** contract metadata only; no execution.

**Revisit:** before R4.3 live inquiry. Values must be calibrated, not fossilized from one fixture.

## R4-D014 — Decision/history tracking

**Status:** ACCEPTED

**Decision:** this log is a required session-handoff artifact. Accepted, rejected, superseded and open patterns must be recorded alongside implementation tracker, tech debt and implementation review.

**Reason:** future sessions need the reasoning lineage, not only the final code state.

## R4-D015 — E2E-first acceptance for architectural capsules

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** every new capsule/block should, where technically possible, be exercised through the nearest real end-to-end chain before branch review/audit is considered sufficient.

**Reason:** static review can verify contracts while still missing boundary-shape errors. The first R4.2 E2E immediately exposed that R3.5 `AssessmentNeed.target_refs` may contain control refs such as `RAS-*` because source refs are folded into the need target tuple.

**Rejected:** treating unit coverage + document audit as sufficient evidence that a new boundary composes correctly.

**Consequence:** branch close order is `implementation -> targeted/E2E execution -> defect repair -> full regression -> review/audit/docs`.

## R4-D016 — Legacy Tribunal levels are preserved as staged inquiry, not one monolith

**Status:** ACCEPTED DIRECTION / EXECUTION DEFERRED
**Date:** 2026-09-13

**Recovered legacy sequence:** internal skeptical discussion -> Advocate for important/vulnerable claims -> Tribunal escalation. Later design evolved further toward independent views followed by dialectical `Q1 -> A1 -> Q2(on A1) -> A2` rather than majority voting.

**Decision:** preserve these functions as separate future inquiry stages/contracts:

1. independent evidence-conditioned first pass;
2. adversarial FOR/AGAINST or challenge/defense stage when policy triggers it;
3. bounded question/answer/question-on-answer chain;
4. typed discovery extraction and reducer-controlled disposition/escalation.

R4.2 implements only the evidence-control prerequisite. It does not instantiate Advocate or run discussion.

**Rejected:** porting the legacy five-role prompt and aggregator directly as one Tribunal worker.

**Revisit:** R4.3/R4.4 inquiry contract design.

## R4-D017 — Cross-layer traceability must become a first-class substrate

**Status:** ACCEPTED REQUIREMENT / OPEN DESIGN
**Date:** 2026-09-13

**Problem:** the temporary `AssessmentNeedRef` bridge is one symptom of a wider identity/lineage problem. Objects, derived projections, decisions, evidence slices, attempts and later inquiry turns need a queryable chain explaining what produced what, under which version/policy/run/attempt and which object revision was consumed.

**Decision:** design a general traceability substrate rather than patch each R3->R4 seam with local hashes. Candidate concepts are a versioned `TraceabilityLink` / `LineageEnvelope` plus a query/index layer. It must record identity and derivation, not become a semantic or truth authority.

**Required scope:** entity version lineage; produced-from/consumed-by; transformation step; policy/config hash; Job/Attempt/ResearchCard provenance; cross-layer aliases/bridges; selective invalidation/replay queries.

**Rejected:** one mutable god-object that "owns" every entity; ad-hoc string IDs independently invented by each phase.

**Debt:** TD-038.

## R4-D018 — R4.2 evidence selection uses canonical typed refs, not legacy trust/keyword fallback

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** executable evidence slicing is derived from `AssessmentNeed` refs, RWF evidence pool and canonical active `GraphEdge` SUPPORTS/CONTRADICTS relations. No free-text method-source classifier and no automatic top-N trust fallback are authoritative.

**Preserved legacy idea:** asymmetric views and blind first pass.

**Rejected legacy mechanism:** if a role-specific slice is empty, silently give top-3 high-trust sources. Missing blocking evidence remains visible as `BLOCKED` instead.

## R4-D019 — FRESH_CONTEXT hides semantic polarity as well as provenance/current conclusions

**Status:** ACCEPTED L1 POLICY
**Date:** 2026-09-13

**Decision:** a fresh-context slice may receive the selected evidence texts, but SUPPORT/COUNTER labels are projected as `UNLABELED`; source title/locator/source ID and prior review artifacts remain hidden when policy forbids them.

**Reason:** hiding the preliminary verdict while labeling every excerpt "support" or "counter" would be independence theater.

**Revisit:** R4.3 two-stage blind -> provenance/polarity reveal experiments.

## R4-D020 — Domain role packs remain explicit debt during R4.2

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** do not implement dynamic/admitted domain role packs inside evidence slicing. Keep TD-036 open until the evidence and inquiry contracts are stable enough to define pack authority safely.


## R4-D021 — Evidence slices are assignment-scoped, not RWF-global

**Status:** ACCEPTED
**Date:** 2026-09-13

**Problem:** the first FULL_RELEVANT/FRESH_CONTEXT implementation could include aggregate `ReviewWorkField.evidence_refs`, including evidence that belonged only to another AssessmentNeed/branch.

**Decision:** role evidence is scoped to that role's assigned AssessmentNeeds plus structurally related canonical GraphEdges/endpoints. Aggregate RWF evidence is not an automatic visibility grant.

**Rejected:** interpreting FULL_RELEVANT as “dump every evidence ref in the work field”.

**Reason:** Tribunal independence and branch-local review require need-level visibility boundaries; otherwise evidence slicing becomes a prettier giant-context prompt.

## R4-D022 — CompositionPlan is an integrity-checked authority artifact

**Status:** ACCEPTED
**Date:** 2026-09-13

**Problem:** the first R4.1 composition fingerprint represented role selection and assignments but did not directly cover materialized RoleBrief authority fields. R4.2 would therefore trust a transferred plan whose evidence view/capabilities/budget could theoretically be modified while retaining the old fingerprint.

**Decision:** composition fingerprint covers assignments plus RoleBrief evidence policy, capabilities, tools, expected output contract and inquiry budgets. R4.2 validates fingerprint and brief↔assignment consistency before slicing. The hash is an integrity checksum, not a signature; admitted-plan provenance remains a separate control-plane/traceability requirement.

**Rejected:** assuming all in-memory/dataclass plans are trusted forever and deferring integrity until persistence exists.

**Reason:** the plan is a control-plane authority object and will cross persistence/session/runtime boundaries; integrity needs to be part of the contract before live worker execution.


## R4-D023 — FRESH_CONTEXT blindness is enforced across all structural leak channels

**Status:** ACCEPTED L1 + EXPLICIT LIMIT
**Date:** 2026-09-13

**Finding:** hiding SourceProjection and setting `polarity=UNLABELED` was insufficient. Selection reason codes could still say SUPPORT/COUNTER, and a target GraphEdge could still expose `edge_kind=SUPPORTS/CONTRADICTS`.

**Decision:** FRESH_CONTEXT also neutralizes selection reasons and masks GraphEdge relation semantics/endpoints plus Source target provenance/type metadata.

**Limit:** exact evidence text is preserved and may itself contain author names, DOI/journal strings or other provenance. R4.2 does not silently rewrite scientific quotations to achieve anonymity. This residual semantic-leak problem is TD-039.

## R4-D024 — EvidenceSlice status describes compilation executability, not epistemic resolution

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** `READY/PARTIAL/BLOCKED` on an EvidenceSlice describes whether the bounded role package can be compiled, not whether the AssessmentNeed is epistemically solved. A blocking numeric need with a valid QTY target and no EVD may be READY so the future specialist can return `MissingEvidence` or a qualification. Missing canonical refs required by a blocking assignment still fail closed as BLOCKED.

**Rejected:** `blocking need + zero EvidenceSpan -> BLOCKED` as a universal rule. That conflates evidence packaging with the Tribunal's future assessment.

## R4-D025 — Independent role execution precedes Tribunal dialogue

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** R4.3 first proves one bounded independent role execution from a compiled R4.2 EvidenceSlice through the existing Job/Attempt runtime into typed `InquiryTurn/ArgumentArtifact` output. Advocate, cross-examination and Q/A chains remain downstream stages.

**Reason:** if one role cannot be executed with enforceable input/output boundaries, adding dialogue only multiplies an unproven boundary.

**Rejected:** starting R4.3 with a whole-panel conversational orchestrator.

## R4-D026 — ArgumentArtifact is the canonical R4.3 role output

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** admitted Tribunal roles emit `ArgumentArtifact/1.0` plus historical `InquiryTurn/1.0`, not an authoritative `TribunalFinding` or verdict mutation.

**Reason:** role output is semantic evidence/argument input for later reducers and inquiry stages; it is not claim truth.

## R4-D027 — Role Handbook carries semantics, never authority

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** `tribunal_role_handbook.yaml` may define mission, mandatory checks, forbidden reasoning moves, stop conditions, discovery focus and phase-specific semantic variants. It may not grant role admission, tools, capabilities, evidence visibility or authoritative state rights.

**Authority remains in:** versioned Tribunal composition policy + central capability/tool registries + EvidenceView compiler.

**Rejected:** using a role prompt/handbook as a hidden IAM/policy layer.

## R4-D028 — Handbook gaps create typed fill requests, not self-modifying policy

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** code detects missing handbook entries/variants for selected admitted roles and emits deterministic `RoleHandbookFillRequest` records derived from assigned AssessmentNeeds, methods, lineage and policy snapshot. A YAML-ready skeleton may be generated, but it is `PROPOSAL_ONLY` and deliberately contains no tool/capability/evidence authority.

**Reason:** the runtime may state what semantic guidance is missing without granting itself new expertise or authority.

**Domain role packs:** remain TD-036 and are not admitted by this mechanism.

## R4-D029 — Role variants are phase semantics, not new role identities

**Status:** ACCEPTED L1
**Date:** 2026-09-13

**Decision:** `first_pass`, `challenger`, `cross_exam` and future `defense` are semantic variants of an admitted role. They compile to different instruction fingerprints but do not create new role authority.

**Current execution constraint:** R4.3 L1 Job/Attempt runtime accepts only `first_pass`. A challenger/cross-exam instruction presented to an independent-first-pass contract fails closed. Later inquiry phases must introduce their own typed turn/phase contracts.

**Rejected:** silently running a cross-exam prompt under an independent-first-pass contract.

## R4-D030 — Deterministic fixture workers prove structure, not scientific quality

**Status:** ACCEPTED TESTING RULE
**Date:** 2026-09-13

**Decision:** R4.3 E2E uses deterministic fixture role workers to prove contract binding, slice containment, Job/Attempt lifecycle, typed output admission and downstream compatibility. This is not treated as evidence that a production LLM/provider produces scientifically good reviews.

**Remaining:** live authorized provider/capability binding and health remain TD-037.

## R4-D031 — Runtime failure and epistemic OPEN are different states

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** invalid citation/out-of-slice output or worker/runtime failure terminates the child Job as `FAILED_NO_OUTPUT`; it must not be converted into semantic `OPEN`. Conversely, a valid role may deliberately emit `ArgumentPosition.OPEN` when the bounded evidence is insufficient.

**Reason:** provider/runtime failure and scientific uncertainty have different owners and retry/escalation semantics.

## R4-D032 — R4.3 arguments can enter later rounds only through controlled prior-review projection

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** `ArgumentArtifact` has a deterministic projection into the R4.2 `PriorReviewArtifact` visibility envelope. Later EvidenceViewPolicy decides whether another role is allowed to see it.

**Rejected:** automatically broadcasting first-pass conclusions to every subsequent role.

## R4-D033 — Multi-role first passes remain independent artifacts

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** selected roles execute as separate child Jobs/Attempts with role-specific EvidenceSlices and role-specific instruction fingerprints. One first-pass role does not automatically receive another role's ArgumentArtifact.

**Observed E2E:** `xrd_specialist` used `METHOD_ONLY`; `crystallographer` used `CLAIM_PLUS_SUPPORT`; both completed independently and produced distinct arguments while Claim/GraphEdge remained unchanged.

## R4-D034 — Researcher acceptance has one repository-owned entrypoint

**Status:** ACCEPTED / IMPLEMENTED
**Date:** 2026-09-13

**Decision:** `scripts/run_researcher_acceptance.py` bootstraps the Researcher import roots and provides `r4`, `full`, `gates`, `all` modes. Session-specific `PYTHONPATH` knowledge is no longer required for normal acceptance execution.

**Debt impact:** TD-040 closed by R4.3.

## R4-D035 — Portable role semantics may travel; runtime authority remains local

**Status:** ACCEPTED FUTURE DIRECTION
**Date:** 2026-09-13

**Decision:** future role exchange should use a typed `RoleReference + RoleCard + RoleParameterGraph + RoleVariantCard + PortableRoleDOM` representation rather than copying prompt text. Imported role objects may carry semantic/provenance/compatibility information, but tools, capabilities, evidence visibility and admission rights are always stripped/recomputed under the receiving module's local policy.

**Reason:** a reusable role must be inspectable, diffable and composable without becoming a portable privilege escalation package.

**Implementation status:** documentation only in `ROLE_CARD_PORTABLE_DOM_FUTURE.md`; tracked as TD-041. Domain role-pack admission remains TD-036.

## R4-D036 — Dialectic level means process depth, not confidence

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** use explicit process levels `L0 independent -> L1 challenge -> L2 direct Q/A -> L3 question-on-answer -> L4 local research escalation -> L5 external escalation`. Level never means that an argument is more true or more confident.

**Rejected:** a single ordinal/scalar Tribunal score that mixes dialogue depth with epistemic quality.

## R4-D037 — Emergent dialogue complexity is multidimensional and typed

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** observe separate issue kinds such as missing evidence, method limitation, counterexample, scope, causality, numeric discrepancy, assumption, provenance, freshness, contradiction, answer evasion and capability gap. Do not collapse them into one dialogue-complexity number.

**Reason:** different difficulties require different owners and continuations: research, method review, panel recomposition or stop.

## R4-D038 — Follow-up depth requires semantic novelty, not unused budget

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** `Q2(on A1)` is justified only when A1 exposes a new typed issue, changes the admitted evidence frontier or changes the argument position. Repetition without one of these increments `no_progress_streak` and may terminate before max depth/turn/token limits.

**Rejected:** always consuming the configured Q/A depth because budget remains.

## R4-D039 — Control code does not infer answer quality from prose

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** the deterministic dialectic controller observes admitted typed discoveries/requests. Interaction-only semantics such as `ANSWER_EVASION`, `CONTRADICTION` or `ROLE_CAPABILITY_GAP` enter through bounded `DialecticIssueProposal` objects whose need/ref scope is validated by code.

**Reason:** semantic interpretation belongs to a semantic worker; routing/admission belongs to code.

## R4-D040 — Dialogue must be able to stop and hand work back to Researcher

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** a blocking emergent evidence/method issue may route to `REQUEST_LOCAL_RESEARCH` and, only through an explicit projection/admission call, reuse the existing canonical `Gap -> ResearchChallenge -> PlanningDialectic` path.

**Rejected:** continuing Tribunal conversation as a substitute for missing evidence, and creating a Tribunal-specific research scheduler.

## R4-D041 — Pure dialectic control may precede live provider binding; live dialogue may not

**Status:** ACCEPTED BOUNDARY
**Date:** 2026-09-13

**Decision:** deterministic R4.4 observation/stop/escalation policy can be implemented/tested over typed fixture artifacts before TD-037 live provider binding is closed. Executing live challenger/questioner/answerer roles remains gated by the shared provider-health/binding boundary.

**Reason:** the control algorithm is independently testable, while pretending fixture workers prove production semantic dialogue would repeat the exact mistake R4-D030 forbids.

## R4-D042 — Dialectic issue closure is explicit and local, not Claim truth

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** a later response may submit a typed `DialecticIssueResolutionProposal` for an already-observed issue signature with disposition `RESOLVED` or `STILL_OPEN`. Unknown signatures fail closed. Resolving the last tracked dialectic issue may end the local exchange as `STOP_CONVERGED`, but does not mutate Claim/GraphEdge epistemic state.

**Reason:** a dialogue controller that can only accumulate problems cannot distinguish genuine closure from budget exhaustion.

## R4-D043 — Process budgets count the full turn chain, not only response artifacts

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** R4.4 observation accepts explicit full-chain turn count so `QUESTION` and `QUESTION_ON_ANSWER` consume process budget even though only semantic responses necessarily emit `ArgumentArtifact`. When runtime does not provide an explicit count, the observer records an approximation reason code.

**Reason:** counting only answers underreports actual dialogue depth and makes turn limits deceptively permissive.

## R4-D044 — Advocate is conditional defense, not a permanent pro-claim voter

**Status:** ACCEPTED DESIGN DIRECTION
**Date:** 2026-09-13

**Decision:** future Advocate/defense activates only against a specific admitted challenge when the attacked argument still has visible admissible support and policy requires an independent defense perspective. Advocate may defend, qualify, concede a local point, request evidence or remain OPEN; it may not invent evidence, widen authority, or treat inability to defend as a reason to manufacture SUPPORT.

**Reason:** the useful function is adversarial testing of the strongest defensible justification, not maintaining a permanent confirmation-bias seat.

**Implementation:** deferred to R4.4 L2/L3 after disclosure and live dialogue contracts are stable.

## R4-D045 — Resolved dialectic issues remain historical and may reopen

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** `DialecticHistory` keeps active and resolved issue signatures separately. If a resolved issue later reappears in an admitted response, the controller records `ISSUE_REOPENED`, reactivates it and removes it from the resolved set. A response may not reassert and resolve the same signature simultaneously.

**Reason:** deleting resolved issues would erase dialectic history and let old objections masquerade as novel discoveries when they recur.

## R4-D046 — Fanout limits constrain continuation, never issue visibility

**Status:** ACCEPTED / IMPLEMENTED L1
**Date:** 2026-09-13

**Decision:** all admitted new/reopened issues remain in `DialecticObservation`. `max_new_issues_per_turn` is a process-control bound, not an array truncation rule. Excess fanout produces an explicit stop condition after higher-priority blocking research/capability escalation is considered.

**Reason:** silent truncation could hide a material/blocking issue merely because it appeared seventh in a response.

## R4-D047 — Argument graph is a review-process projection, not a second KnowledgeGraph

**Status:** ACCEPTED / IMPLEMENTED L2a
**Date:** 2026-09-13

**Decision:** `ArgumentArtifact` remains the semantic node and `ArgumentRelation/1.0` records dialectic topology separately from canonical Claim/Evidence GraphEdges. `ATTACKS`, `UNDERCUTS`, `REPLIES_TO` and `DEFENDS` never directly change Claim truth.

**Reason:** attacks between reviewer arguments and scientific evidence relations have different semantics, lifecycle and authority owners.

## R4-D048 — Argument relations point from newer response/challenge to the earlier argument they address

**Status:** ACCEPTED / IMPLEMENTED L2a
**Date:** 2026-09-13

**Decision:** argument relations use historical orientation `source/newer -> target/earlier`; graph revisions must be acyclic and preserve prior nodes/relations.

**Reason:** this makes branch heads/root reconstruction deterministic while revisiting the same scientific topic remains possible through new historical nodes rather than literal cycles.

## R4-D049 — Advocate is admitted-but-not-composed

**Status:** ACCEPTED / IMPLEMENTED L2a
**Date:** 2026-09-13

**Decision:** Advocate exists in local role policy and handbook but has no ordinary axis/method coverage, so R4.1 cannot select it during initial composition. Only the explicit conditional activation path may instantiate it.

**Rejected:** permanent Advocate seat and hidden prompt-level Advocate spawning.

## R4-D050 — Advocate activation is branch-specific and materiality-gated

**Status:** ACCEPTED / IMPLEMENTED L2a
**Date:** 2026-09-13

**Decision:** activation requires one ACTIVE material `ATTACKS/UNDERCUTS` edge, a CHALLENGE source, a still-defensible SUPPORT/QUALIFY target, shared AssessmentNeed scope, visible support and an unexhausted defense count.

**Reason:** defense should test a concrete challenge, not create confirmation-bias work on every disagreement.

## R4-D051 — Advocate disclosure is explicit and does not broadcast sibling branches

**Status:** ACCEPTED / IMPLEMENTED L2a
**Date:** 2026-09-13

**Decision:** current defense `DialecticDisclosureContract` contains only the attacked argument, selected challenge, their turns/relation, already-cited evidence/targets and shared needs. Other graph branches are explicitly hidden.

**Debt:** TD-043 remains open until challenger/questioner/cross-exam use one generic disclosure compiler.

## R4-D052 — Advocate outcome and graph relation are different dimensions

**Status:** ACCEPTED / IMPLEMENTED L2a
**Date:** 2026-09-13

**Decision:** Advocate may `DEFEND`, `QUALIFY`, `CONCEDE_LOCAL_POINT`, `REQUEST_EVIDENCE` or remain `OPEN`. Every response may `REPLIES_TO` the challenge; only defend/qualify responses create a `DEFENDS` edge to the attacked argument.

**Reason:** replying to an objection does not imply that the original position survived it.

## R4-D053 — Advocate evidence deficit reuses the existing Researcher feedback loop

**Status:** ACCEPTED / IMPLEMENTED L2a
**Date:** 2026-09-13

**Decision:** a typed Advocate `AdditionalEvidenceRequest` is observed by the existing R4.4 controller as blocking missing evidence and can be explicitly projected to the existing `Gap -> ResearchChallenge` path.

**Rejected:** Advocate-specific retrieval/search scheduler.

## R4-D054 — TD-044 may reuse Writer semantic decomposition, but Writer cannot admit issue equivalence

**Status:** ACCEPTED FUTURE DIRECTION
**Date:** 2026-09-13

**Decision:** future issue-facet/equivalence work should evaluate reuse of Writer claim splitting, graph artifacts and semantic round-trip validation. Writer may propose atomic facets/local proposition graphs/equivalence candidates from a bounded issue context; Researcher code validates scope/provenance and explicitly admits any equivalence.

**Rejected:** a second independent paraphrase classifier inside Tribunal, and direct Writer mutation of issue signatures/progress state.

## R4-D055 — Dialectic disclosure is one shared control-plane contract

**Status:** ACCEPTED / IMPLEMENTED L2b
**Date:** 2026-09-13

**Decision:** challenge, direct-question, question-on-answer and defense phases use one generic `DialecticDisclosureContract` compiler. The Advocate-specific API remains only as a compatibility wrapper.

**Reason:** role-specific disclosure implementations would drift and create different leakage semantics for identical prior artifacts.

## R4-D056 — Cross-exam may widen first-pass visibility only through explicit DDC transition

**Status:** ACCEPTED / IMPLEMENTED L2b
**Date:** 2026-09-13

**Decision:** independent first-pass EvidenceSlice remains unchanged. A later dialectic phase may expose selected prior arguments/evidence that were not visible during first pass only through a branch-scoped fingerprinted DDC.

**Rejected:** implicit broadcast of previous arguments/evidence and prompt-level requests for more context.

## R4-D057 — Stable branch identity excludes graph revision and moving head

**Status:** ACCEPTED / IMPLEMENTED L2b
**Date:** 2026-09-13

**Decision:** `DialecticBranchRef.branch_key` is derived from AGP id, root, anchor argument/relation and optional seed issue. AGP revision/fingerprint and head ARG are snapshot fields and may advance without changing branch identity.

**Reason:** Q/A replies and returned research must continue the same historical branch across graph revisions.

## R4-D058 — Q2 requires an admitted new surface from A1

**Status:** ACCEPTED / IMPLEMENTED L2b
**Date:** 2026-09-13

**Decision:** `DialecticQuestionContract(QUESTION_ON_ANSWER)` requires an exact issue signature present among the newly admitted issues of the prior answer observation. Arbitrary free-form follow-up is rejected.

**Reason:** depth must follow information gain, not unused turn budget.

## R4-D059 — Turn citations and argument citations share the same disclosure boundary

**Status:** ACCEPTED / IMPLEMENTED L2b
**Date:** 2026-09-13

**Decision:** validation covers `InquiryTurn.cited_refs` as well as `ArgumentArtifact` evidence/targets/discoveries/requests. A hidden sibling ref cannot be smuggled through the turn while the argument remains superficially clean.

## R4-D060 — Dialectic progress state is branch-scoped and replayable

**Status:** ACCEPTED / IMPLEMENTED L2b
**Date:** 2026-09-13

**Decision:** `DialecticBranchHistory` binds local `DialecticHistory` to one stable DBR branch. Sibling branches do not share no-progress, issue lifecycle, Q/A count or token usage. Checkpoints serialize/restore with a deterministic fingerprint.

**Debt impact:** closes TD-045 at the structural L2b boundary.

## R4-D061 — Research escalation carries an exact branch resume anchor

**Status:** ACCEPTED / IMPLEMENTED L2b
**Date:** 2026-09-13

**Decision:** Tribunal-originated ResearchChallenge work records the DBR/AGP/issue lineage and may be bound to `DialecticResearchResumeAnchor`, which additionally fingerprints the local branch history. Returned research must match this anchor before continuing the exchange.

**Rejected:** returning evidence to a generic Tribunal queue and reconstructing the target branch from topic similarity.

## R4-D062 — DQC is a first-class typed entity

**Status:** ACCEPTED / IMPLEMENTED L2b
**Date:** 2026-09-13

**Decision:** bounded question authority uses `DialecticQuestionContract/1.0` with registered `DQC-*` identity rather than reusing first-pass `IQC-*` or Advocate `ADC-*` ids.

**Reason:** first-pass execution, defense, and one bounded question/answer transaction have different authority and replay semantics.

## R4-D063 — DQC distinguishes questioner from addressed answer role

**Status:** ACCEPTED / IMPLEMENTED L3A
**Date:** 2026-09-13

**Decision:** `DialecticQuestionContract` carries both `role_id` (questioner) and `answer_role_id` (addressed semantic responder). Provider binding must use the correct side of the contract. Target ARG ownership is not used as an implicit substitute for answer addressing.

**Reason:** live E2E demonstrated that inferring answerer from the challenged ARG can make a Skeptic ask and answer its own question.

## R4-D064 — Bounded Tribunal dialogue rejects accidental self-response

**Status:** ACCEPTED / IMPLEMENTED L3A
**Date:** 2026-09-13

**Decision:** current bounded DQC compilation requires `questioner != answer_role`. A future explicit self-review policy may introduce a different contract, but self-dialogue is not silently accepted as Tribunal cross-examination.

## R4-D065 — Semantic role, provider and runtime tool are distinct authorities

**Status:** ACCEPTED / IMPLEMENTED L3A
**Date:** 2026-09-13

**Decision:** an admitted Tribunal role defines semantic duty; `RoleProviderBinding` chooses an authorized healthy execution provider; runtime binding chooses the executable logical tool/endpoint. Provider priority cannot override role-kind/contract compatibility.

## R4-D066 — Advocate is not the default owner of a challenged Claim facet

**Status:** ACCEPTED AS ARCHITECTURAL DIRECTION; detailed policy OPEN (TD-046)
**Date:** 2026-09-13

**Decision:** keep Advocate conditional. Questions about scientific content normally address the responsible facet/domain/method specialist. Advocate is activated to test defense of an already challenged position, not to replace the specialist who owns the scientific content.

**Open:** whether a future `Defender` is a separate actor, a response mode, or a party assignment. Current preference is `ResponseAssignment` rather than a permanent Defender persona.

## R4-D067 — Multidisciplinary review forks by facet and rejoins by coverage/dependency, never vote

**Status:** ACCEPTED AS FUTURE ARCHITECTURE; implementation OPEN (TD-047)
**Date:** 2026-09-13

**Decision:** one canonical Claim may own multiple review facets/branches. Each branch preserves root Claim identity and independent history. Future join semantics retain blocking facets and cross-facet conflicts; they do not average role verdicts or let an Aggregator overwrite branch findings.

## R4-D068 — More healthy providers than needed does not authorize redundant execution

**Status:** ACCEPTED / IMPLEMENTED L3A
**Date:** 2026-09-13

**Decision:** when multiple compatible providers are healthy, binding selects exactly one by versioned deterministic ordering. Running multiple executors requires a separate explicit review/redundancy policy. `requested_executor_count > max_executors_per_contract` fails closed.

## R4-D069 — Provider failure, output rejection and epistemic OPEN are three different states

**Status:** ACCEPTED / IMPLEMENTED L3A
**Date:** 2026-09-13

**Decision:** timeout/transport failure is runtime `FAILED/TIMED_OUT`; a syntactically returned but authority-violating result is `REJECTED`; `ArgumentPosition.OPEN` is permitted only after successful typed admission. All runtime outcomes receive a durable `PER-*` receipt.

## R4-D070 — Live provider output must enter ArgumentGraph before dialectic observation

**Status:** ACCEPTED / IMPLEMENTED L3A
**Date:** 2026-09-13

**Decision:** a validated live answer becomes `IQT + ARG`, then is admitted as historical `REPLIES_TO` in a new AGP revision, then the branch is refreshed, and only then may `DialecticObserver` update branch-control state.

**Rejected:** observing provider output directly before argument-graph admission.

## R4-D071 — Provider bindings are immutable snapshots; fallback requires a new binding lineage

**Status:** ACCEPTED / IMPLEMENTED L3A
**Date:** 2026-09-13

**Decision:** RPB fingerprints provider authority, runtime binding and health snapshot. If provider health changes before execution, the old RPB becomes unusable. Runtime adapters may not silently switch providers inside the same binding/Attempt.

## R4-D072 — Production-provider absence blocks production semantic validation, not structural L3A freeze

**Status:** ACCEPTED
**Date:** 2026-09-13

**Decision:** deterministic subprocess E2E may prove process boundary, Job/Attempt lifecycle, bounded visibility, typed admission and failure semantics. It is not evidence of scientific-review quality from a production semantic model. Current `existing.opencode_tribunal_role` is implemented but unavailable because `opencode` is missing; production semantic E2E remains an explicit L3B gate.

## R4-D073 — Specialist response is an argument, not evidence by role authority

**Status:** ACCEPTED / IMPLEMENTED L3B structural slice
**Date:** 2026-09-13

**Decision:** live specialist and Advocate outputs carry typed grounding. `MODEL_PRIOR`/training-memory knowledge may generate hypotheses but cannot be treated as evidence or silently close a scientific branch. Non-OPEN model-prior-only answers create blocking evidence debt and a typed research request.

**Reason:** the scientifically relevant question is not only who answered, but what observable/source/derivation justifies the answer.

## R4-D074 — Grounding origin is explicit and branch-bounded

**Status:** ACCEPTED / IMPLEMENTED L3B structural slice
**Date:** 2026-09-13

**Decision:** grounding distinguishes disclosed evidence, disclosed target, prior argument/turn, visible derivation, explicit assumption and model prior. Grounding refs are checked against DDC/ADC visibility and cannot cite hidden sibling material.

## R4-D075 — Conditional Advocate uses the same provider-binding/runtime authority as other roles

**Status:** ACCEPTED / IMPLEMENTED L3B structural slice
**Date:** 2026-09-13

**Decision:** Advocate execution is `ADC -> RPB(DEFENSE) -> TEX -> Job/Attempt -> PER -> AdvocateResponse`; no separate Advocate runtime/provider registry exists.

## R4-D076 — Prior-only defense cannot create a DEFENDS edge

**Status:** ACCEPTED / IMPLEMENTED L3B structural slice
**Date:** 2026-09-13

**Decision:** a live Advocate `DEFEND` based only on model prior/ungrounded context is deterministically downgraded to `REQUEST_EVIDENCE`. It may REPLY_TO the challenge historically but may not create `DEFENDS` until evidence-grounded support exists.

## R4-D077 — Multidisciplinary review keeps one canonical Claim with independent review subbranches

**Status:** ACCEPTED AS FUTURE ARCHITECTURE / TD-047
**Date:** 2026-09-13

**Decision:** one `CLM-*` remains the root identity. `ClaimReviewCase` owns independent ReviewFacet Q/A/argument branches. Join semantics preserve conflicts, dependencies and synergy; they never merge by vote or mean confidence.

## R4-D078 — Hypothesis is a historical research object, not a scalar Claim status

**Status:** ACCEPTED AS FUTURE ARCHITECTURE / TD-048
**Date:** 2026-09-13

**Decision:** model an explanatory hypothesis through a stable `HypothesisCase` and append-only revisions/verification iterations. A hypothesis may link to canonical Claims but does not replace Claim/ClaimAssessment and does not mutate truth directly.

**Rejected:** adding `HYPOTHESIS_CONFIDENCE` or overloading `Claim.status` as the complete research state.

## R4-D079 — Material hypothesis changes create revisions rather than rewriting history

**Status:** ACCEPTED AS FUTURE ARCHITECTURE / TD-048
**Date:** 2026-09-13

**Decision:** qualification, material reformulation or mechanism change records parent revision, triggering refs and changed fields. Prior hypothesis formulations remain inspectable. `RETAIN`, `QUALIFY`, `REVISE`, `SPLIT`, `REJECT` and `OPEN` are distinct process outcomes.

## R4-D080 — Model prior may seed a hypothesis but never count as hypothesis evidence

**Status:** ACCEPTED / aligned with L3B grounding
**Date:** 2026-09-13

**Decision:** `MODEL_PRIOR` may generate a testable hypothesis, alternative explanation or research question. It cannot create evidential support, close a verification branch or masquerade as a source. Scientific advancement requires canonical evidence/derivation or an explicit unresolved assumption.

## R4-D081 — Source/evidence count is not independence count

**Status:** ACCEPTED AS FUTURE ARCHITECTURE / TD-049
**Date:** 2026-09-13

**Decision:** hypothesis assessment must eventually distinguish multiple evidence records from genuinely independent replications/support groups. Shared datasets, experiments, derivations or citation ancestry must be visible before support is aggregated.

**Rejected:** `N supporting papers = N independent confirmations`.

## R4-D082 — EvidenceDigest is a derived inspection artifact, never the source of evidential authority

**Status:** ACCEPTED AS FUTURE ARCHITECTURE / TD-050
**Date:** 2026-09-13

**Decision:** concise source summaries may state what an exact EvidenceSpan supports, limits, counters or fails to discriminate, but every digest remains linked to the canonical source locator and must survive semantic round-trip/scope checks. Researcher admission owns support semantics.

## R4-D083 — Production semantic provider traces must preserve executable/provider reproducibility metadata without secrets

**Status:** ACCEPTED / operational L3B gate
**Date:** 2026-09-13

**Decision:** production traces preserve OpenCode version/build/hash, model id, sanitized provider/config hash, RPB/TEX/DDC/DQC/ADC/role-policy fingerprints, raw provider output hash, PER and admitted/rejected semantic artifacts. API keys/tokens are never stored in trace packs.

## R4-D084 — Remote semantic trace execution is valid only if control contracts are unchanged and hash-verified

**Status:** ACCEPTED / operational L3B gate
**Date:** 2026-09-13

**Decision:** when the Harness sandbox cannot access the cloud provider, an exact hash-stable TEX trace pack may be executed on the production OpenCode host and returned for deterministic admission. Remote execution does not authorize the production host to alter DDC/DQC/ADC/RPB/TEX or hidden evidence membership.

**Reason:** this preserves provider realism and user-held credentials without sacrificing control-plane reproducibility.
