# WRITER-V1-FREEZE-001 — implementation and authority review

## 1. Goal

Close the remaining Writer-side contract seams before moving primary development effort to Researcher. The target is not a feature-complete autonomous writing system. The target is a stable Writer boundary in which prose generation can be replaced, upgraded or routed to another model without changing claim authority, evidence authority, provenance or release semantics.

## 2. Decisions

### 2.1 Cross-language style references

The former language hard-filter was too strict. It prevented an English/German dissertation from contributing useful argument structure to a Russian dissertation.

New policy:

- same-language STYLE reference: `FULL` authority over bounded style properties plus structural patterns;
- cross-language STYLE reference: `STRUCTURE_ONLY`;
- EVIDENCE selection remains independent of style language/genre filters.

`STRUCTURE_ONLY` may contribute graph motifs, argument structure, paragraph architecture and citation architecture. It may not contribute lexical wording, syntax imitation, idioms, hedging density or other surface-language behavior.

This is deliberately asymmetric. Structural transfer across language is useful. Surface transfer is a common source of translated-looking prose.

### 2.2 Proposed claims

Writer composition naturally produces synthesis. Treating every such sentence as an error loses useful reasoning; treating it as an authorized fact is worse.

`ProposedClaim/1.0` is now the only normal channel for a Writer to introduce a proposition that is not in `DraftRequest.authorized_claims`.

A proposed claim carries:

- stable ID/hash;
- text;
- paragraph/span;
- type (`SYNTHESIS`, `INTERPRETATION`, `COMPARISON`, `CAUSAL_HYPOTHESIS`, `EXTERNAL_FACT`, ...);
- evidence references if available;
- reason;
- explicit `requires_registration`.

DraftArtifact becomes non-releaseable until proposed claims are registered/validated, weakened, or discarded.

### 2.3 Per-claim evidence selection

Section-level evidence bundles were too coarse. The Writer could receive good sources for a section while an individual claim had no direct evidence.

`claim_evidence_selection/1.0` now runs deterministic evidence selection for each authorized claim and preserves `claim_id -> selected evidence fragments` in `DraftRequest.evidence_by_claim`.

Evidence is still only a candidate until Researcher validates it. Selection does not upgrade evidence authority.

### 2.4 Verification versus epistemic uncertainty

The former single `verdict` mixed three dimensions.

New explicit fields:

- `verification_state`: `VERIFIED | UNCHECKED | FAILED`;
- `evidence_verdict`: `SUPPORTED | CONTRADICTED | UNSUPPORTED | AMBIGUOUS | OPEN`;
- `epistemic_state`: `ESTABLISHED | QUALIFIED | AMBIGUOUS | DISPUTED | UNKNOWN`.

The legacy `verdict` remains for compatibility but new gates prefer the explicit fields.

Important behavior change: `UNCHECKED` blocks evidence release but does not automatically trigger hedged prose. Masked-uncertainty checks are driven by epistemic state (plus explicit DOM uncertainty), not by absence of verification alone.

### 2.5 Claim-realization authority

The final authority chain is:

```
Claim registry
→ DraftRequest authorization
→ DraftArtifact realizes_claims
→ DOM paragraph.claims
→ rendered [C-*] markers (projection only)
```

After a DOM patch, `paragraph.claims` is authoritative for what the paragraph realizes. Rendered markers must match it, but cannot change it.

Release uses the DOM binding when available. Historical documents without paragraph-level bindings keep a marker compatibility path.

A DOM/marker mismatch is surfaced inside the traceability gate as `authority_binding = FAIL`.

This avoids adding a fourth top-level release gate and preserves the public `evidence / traceability / semantic_roundtrip` contract.

### 2.6 Source invalidation authority

Source updates do not directly rewrite claim truth.

State reducer owns operational transitions such as:

- `PENDING_REVALIDATION`;
- `SUPPORTED_WITH_STALE_EVIDENCE`.

Evidence verdict is preserved separately. A single-evidence supported claim can therefore become operationally pending while its last evidence verdict remains `SUPPORTED` and its new verification state becomes `UNCHECKED`.

## 3. Agent boundary cleanup

The previous `article-writer` prompt still knew `webfetch/search`, old `wc_cli.py`, and could independently decide to verify claims. This contradicted the runtime architecture.

Updated Writer agent contract:

- receives DraftRequest/StyleInstruction/authorized claims;
- no direct web search or source provider access;
- no backend/provider names;
- no direct DOM mutation;
- returns realization mappings and ProposedClaims;
- research debt goes back to the orchestrator/Researcher.

`writing-orchestrator`, `shared/article-writing-process.md`, `shared/writing-orchestration-process.md` and `shared/writer-traceability-contract.md` were aligned to the same authority model.

Researcher internals were intentionally not refactored here. Writer talks to the stable `ValidationPlan / ResearchDispatchContract` boundary.

## 4. Routing changes

Added logical tool/capability/provider:

```
reference.evidence.select
→ writer.reference.evidence_select
→ scripts/writer/references/evidence_select.py
```

The `writing-prose / claim-load` stage now requires deterministic per-claim evidence selection.

Capability snapshot was rebuilt from authority sources rather than edited by hand.

## 5. Compatibility

Compatibility is retained for:

- `reference_selection/1.0` alongside new `1.1` output;
- `draft_artifact/1.0` consumers via compatibility metadata;
- legacy `verification.verdict`;
- marker-only historical documents that lack DOM paragraph claim bindings.

New production paths prefer the new explicit contracts.

## 6. Test coverage added

New regression cases include:

- cross-language STYLE becomes `STRUCTURE_ONLY` rather than rejected;
- cross-language reference cannot control surface hedging;
- per-claim evidence mapping survives into DraftRequest;
- DraftArtifact emits typed ProposedClaim and blocks release;
- numeric supported claim becomes `VERIFIED + SUPPORTED + ESTABLISHED`;
- nonnumeric unverified claim becomes `UNCHECKED + OPEN + UNKNOWN`;
- `UNCHECKED` alone does not trigger masked-uncertainty prose requirements;
- DOM claim binding outranks rendered marker;
- marker/DOM mismatch fails traceability;
- invalidation separates claim operational state from evidence verdict.

## 7. Remaining Writer risks

### 7.1 ProposedClaim extraction is contract-driven

The runtime validates ProposedClaims supplied by the Writer agent. It does not yet perform a high-quality semantic extraction of every unmarked new proposition itself. Traceability/orphan-claim checks remain the secondary safety net.

This is acceptable for v1 because automatic semantic proposal extraction belongs closer to the future Researcher/semantic-validator work than to deterministic composition.

### 7.2 Evidence ranking is intentionally simple

Per-claim evidence selection is lexical/provenance-based. Semantic entailment and evidence-quality ranking remain Researcher responsibilities.

### 7.3 Live external agent invocation

`WriterAgentDispatchContract` is implemented and deterministic post-processing is tested. This environment does not expose the external OpenCode task runtime needed to perform a genuine live `article-writer` invocation, so that environment-dependent check remains open.

## 8. Freeze recommendation

The Writer public contracts are now stable enough to freeze as v1 for Researcher work, with one rule: additions should be backward-compatible unless a concrete E2E failure justifies a Writer contract change.

Primary development should now move to Researcher:

1. executable semantic textual entailment;
2. evidence quality / justification normalization;
3. canonical SourceCatalog identity resolution;
4. external provider activation behind logical tools;
5. deterministic Researcher runner that consumes `ResearchDispatchContract` and returns a bounded ResearchBundle/EvidenceBundle.

Do not reintroduce provider names or direct search into Writer while repairing Researcher.
