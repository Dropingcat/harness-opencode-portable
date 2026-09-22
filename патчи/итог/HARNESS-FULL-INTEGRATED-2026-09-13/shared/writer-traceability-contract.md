# Writer Traceability Contract v1

This contract governs scientific and engineering writing. Traceability, claim authority and uncertainty are primary structured data. Prose is a rendered realization of those structures.

## 1. Authority hierarchy

The canonical order is:

1. Claim registry in the DOM defines authorized claim identity and semantics.
2. `DraftRequest.authorized_claims` defines the claims available to one drafting job.
3. `DraftArtifact.paragraphs[].realizes_claims` declares what the writer actually realized.
4. After an accepted DOM patch, `paragraph.claims` is the canonical realization binding.
5. Rendered `[C-*]` markers are a checked projection of the DOM binding. They do not create or authorize claims.

A mismatch between DOM paragraph bindings and rendered markers blocks release.

Writer does not author or upgrade Researcher evidence verdicts. Researcher does not rewrite prose. State reducer owns operational claim-state transitions after source invalidation.

## 2. Claim verification dimensions

Do not overload a single verdict with three different meanings.

```yaml
verification:
  verification_state: VERIFIED | UNCHECKED | FAILED
  evidence_verdict: SUPPORTED | CONTRADICTED | UNSUPPORTED | AMBIGUOUS | OPEN
  epistemic_state: ESTABLISHED | QUALIFIED | AMBIGUOUS | DISPUTED | UNKNOWN
  confidence: 0.0
  numeric_comparison: null
```

The legacy `verification.verdict` field may remain during migration, but new logic must prefer the explicit fields above.

`UNCHECKED` means that the verification operation has not established a result. It blocks evidence release, but does not by itself require hedged prose. Hedging follows `epistemic_state`, authorized modality and explicit uncertainty records.

## 3. DOM core

```yaml
product:
  id: PROD-001
  kind: dissertation | monograph | textbook | paper | article | report

structure:
  chapters:
    - id: CH-01
      sections:
        - id: SEC-01
          paragraphs:
            - id: PAR-01
              claims: [C-001, C-002]
              evidence_refs: [EVD-001]
              style_instruction_id: SI-...
              text: "..."

claims:
  - id: C-001
    text: "..."
    modality: assertive
    causal_level: none
    state: ACTIVE
    evidence:
      - source_id: S-012
        evidence_span_id: EVD-001
    verification:
      verification_state: VERIFIED
      evidence_verdict: SUPPORTED
      epistemic_state: ESTABLISHED

sources:
  - id: S-012
    sha256: "..."
    kind: primary
```

EvidenceSpan stores exact locator/hash provenance. SourceCatalog stores source versions. Dependency graph connects `Source → EvidenceSpan → Claim → Paragraph`.

## 4. Drafting lifecycle

1. Select writing object and section role.
2. Prepare references.
3. Style selection is tiered:
   - same-language reference may provide bounded surface rhetoric plus structure;
   - cross-language reference is `STRUCTURE_ONLY` and may provide argument architecture, graph motifs and citation architecture only.
4. Select evidence per claim. Style genre/language filters do not apply to evidence.
5. Build WritingPolicy and StyleInstructionArtifact.
6. Build DraftRequest with authorized claims and `evidence_by_claim`.
7. Writer returns DraftArtifact-compatible paragraphs.
8. Any new proposition is returned as `ProposedClaim/1.0`; it is research debt, not an authorized fact.
9. Code builds and applies an optimistic DOM patch.
10. ChangeLedger records the exact changed claims/sources/paragraphs.
11. Researcher validates unresolved evidence debt.
12. Traceability + semantic round-trip + evidence gates determine release.

## 5. Proposed claims

Writer may discover useful synthesis while composing. It must not silently add it to the claim registry.

```yaml
schema: proposed_claim/1.0
proposed_claim_id: PC-...
text: "..."
claim_type: SYNTHESIS | INTERPRETATION | COMPARISON | CAUSAL_HYPOTHESIS | EXTERNAL_FACT
paragraph_id: DP-001
span: {start: 0, end: 40}
reason: UNAUTHORIZED_DRAFT_PROPOSITION
requires_registration: true
```

The orchestrator may route a ProposedClaim to Researcher, register it as a new claim after approval, weaken/rewrite it, or discard it.

## 6. Source change and selective repair

A changed source does not trigger blind chapter regeneration.

```text
SourceVersionChanged
→ normalized/span hash comparison
→ InvalidationPlan
→ StateReducer
→ affected claims only
→ affected paragraphs only
→ RepairRequest
→ RTT/release
```

Operational claim state is distinct from evidence verdict. Typical states include `PENDING_REVALIDATION` and `SUPPORTED_WITH_STALE_EVIDENCE`.

## 7. Release invariants

Release is fail-closed when any required gate fails:

- evidence verification;
- traceability, including DOM↔marker authority binding;
- semantic round-trip validation.

For current rendered scientific text, every realized claim must resolve through:

```text
DraftArtifact
→ DOM paragraph.claims
→ claim registry
→ EvidenceSpan/source version
```

Rendered `[C-*]` and `[S-*]` markers are checked against this structure.

## 8. Research boundary

Writer may create ValidationPlan / ResearchDispatchContract but may not execute web discovery or know backend/provider names. Researcher receives the research debt and enters at the narrowest appropriate stage: evidence validation, document analysis, source resolution, local corpus or discovery.
