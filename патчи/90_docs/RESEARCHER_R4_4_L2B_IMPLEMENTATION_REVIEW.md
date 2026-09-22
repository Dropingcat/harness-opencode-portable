# Researcher R4.4 L2b — Implementation Review

Date: 2026-09-13
Status: post-E2E review; ready for milestone freeze if final acceptance remains unchanged.

## 1. What was actually implemented

L2b is not a live multi-agent debate. It is the structural control layer required before live dialogue can be safe/replayable.

Implemented:

- generic `tribunal_disclosure.py`;
- stable branch identity (`DialecticBranchRef`);
- shared DDC compiler for challenge/direct-question/Q-on-answer/defense;
- disclosure policy version/hash embedded in DDC;
- first-class `DQC-*` question contracts;
- exact typed Q2 surface requirement;
- turn-level and argument-level leakage validation;
- branch-scoped history/checkpoint/replay;
- exact ResearchChallenge resume anchor;
- Advocate L2a compatibility through the generic compiler;
- two-branch E2E.

## 2. Strongest observed result

The representative graph contains one root argument and two simultaneous challenge branches. Only branch A is disclosed to the questioner.

Observed chain:

```text
branch A challenge
→ Q1 contract/turn
→ A1 introduces ASSUMPTION_ISSUE
→ graph rev2 / A1 REPLIES_TO challenge
→ Q2 contract targets exact admitted issue
→ A2 requests discriminating evidence
→ graph rev3
→ blocking missing-evidence issue
→ Gap / ResearchChallenge
→ exact branch resume anchor
```

Branch B remains hidden and its history is still empty during branch-A work. After branch A escalates, branch B is refreshed to AGP revision 3 and begins with independent counters/issues. This directly exercises the TD-045 acceptance condition.

## 3. Defects found by E2E and fixed

### D1. New question contract identity was not registered

Initial L2b test introduced `DQC-*`, but R0 `ALLOWED_PREFIXES` did not include `DQC`.

Result: question compilation failed at the canonical ID factory.

Fix: register `DQC` centrally. No raw-string bypass was introduced.

### D2. Turn-level citation leakage path

Initial answer validation checked `ArgumentArtifact` citations/discoveries but not `InquiryTurn.cited_refs`.

A worker could therefore theoretically emit a clean argument while smuggling a hidden sibling ref in the turn.

Fix: answer validation checks the combined DDC/DQC visible argument/turn/relation/evidence/target envelope.

### D3. Parent-turn branch jump

Question compilation originally required only an `IQT-*` parent id, not that the parent was in the DDC.

Fix: Q1/Q2 parent turn must be one of the explicitly disclosed turns.

### D4. "Replay" initially meant only in-memory fingerprint validation

L2a had fingerprints but no complete contract/checkpoint restoration path.

Fix: add DDC/DQC dict round-trip, branch-ref round-trip and branch-history checkpoint restore/fingerprint validation.

### D5. Disclosure policy itself lacked identity

The generic DDC behavior depends on `DialecticDisclosurePolicy`, but the first implementation did not record policy version/hash.

Fix: policy identity/hash now participates in DDC state and fingerprint.

## 4. Q2 boundary

The most important new invariant is:

```text
QUESTION_ON_ANSWER
requires target_issue_signature
∈ prior A1 observation.new_issues
```

Reopened/old/unrelated issue signatures do not silently qualify as new Q2 surfaces.

This does not prove the generated natural-language Q2 is scientifically excellent. It proves the control plane can say what the Q2 is *allowed to be about*.

## 5. Disclosure boundary

Independent review and cross-exam intentionally have different information phases.

First-pass asymmetry remains controlled by R4.2 EvidenceSlice.

Later DDC may reveal selected prior arguments/evidence. This is an explicit authority transition and is replayable/fingerprinted.

Therefore an apparent evidence-view widening in cross-exam is valid only when the DDC records it.

## 6. Branch-history result

`DialecticHistory` is no longer effectively global to an exchange. `DialecticBranchHistory` scopes:

- active/resolved issue signatures;
- no-progress;
- Q/A count;
- token spend;
- turn/argument lineage;
- visible-ref frontier.

The stable `DBR-*` key survives AGP revision/head changes. This is necessary for Q/A and research return.

TD-045 acceptance is satisfied at structural L2b.

## 7. Research return

`ResearchChallenge.dimensions` records branch identity/snapshot/issue. `DialecticResearchResumeAnchor` additionally binds RCH/GAP and branch-history fingerprint.

This is sufficient to reject a result routed back to the wrong sibling branch.

It does not yet perform live evidence ingestion after the returned research. That belongs to L3/adaptive feedback execution.

## 8. Advocate compatibility

Old L2a Advocate tests continue to pass without a separate DDC implementation. `compile_advocate_disclosure()` is now a wrapper over the generic compiler.

This is important evidence that generic disclosure did not quietly create divergent defense semantics.

TD-043 acceptance is therefore satisfied at L2b.

## 9. Remaining weaknesses

1. Live provider/LLM execution is still absent (TD-037).
2. Semantic interaction-only observer calibration remains fixture-only (TD-042).
3. Issue identity remains text-sensitive (TD-044), though Writer reuse path is documented.
4. Branch checkpoints have serialization but no dedicated durable repository/index yet.
5. Universal cross-layer traceability remains broader than the local DBR/resume anchor (TD-038).
6. DDC policy is versioned in code but not yet loaded from a separately admitted YAML policy file. This is non-blocking for L2b because policy identity/hash is recorded in the contract.
7. `CROSS_EXAM` exists as a generic disclosure purpose, while current executable second question uses the more precise `QUESTION_ON_ANSWER` purpose.
8. Question semantic quality is not inferred by deterministic code; control validates target scope, not rhetorical usefulness. Live calibration belongs downstream.

## 10. Authority review

No new direct knowledge-state writer was introduced.

```text
DDC/DQC
    = visibility/question authority
ARG/IQT
    = semantic historical artifacts
DialecticObservation
    = typed local observation
DialecticControlDecision
    = process control
Gap/ResearchChallenge projection
    = explicit existing feedback path
```

Claim/GraphEdge truth remains outside these artifacts.

## 11. Test result

Freeze acceptance results:

- R4 targeted: 82/82 PASS;
- full Researcher: 559 total / 555 PASS / same four TD-015 failures;
- runtime compiler: PASS, hash unchanged;
- capability compiler: PASS, hash unchanged;
- compileall: PASS;
- JSON/YAML parse: PASS;
- `git diff --check`: PASS.

## 12. Freeze result

L2b is frozen as a separate structural boundary.

Feature commit:
`8fc635160d9f3f90583d5e8e44a3206f4e7366ad`
`researcher: generalize r4 dialectic disclosure`

Milestone package:
`RESEARCHER-R4.4-L2B-DISCLOSURE-BRANCH-HISTORY-001.zip`
SHA256: `e83a12e7d666a5f2d3e2183164a620e50bac3c5b6939e1553c70f8458fcaaf61`

Next boundary is R4.4 L3 live bounded dialogue/provider binding, not additional structural feature creep.
