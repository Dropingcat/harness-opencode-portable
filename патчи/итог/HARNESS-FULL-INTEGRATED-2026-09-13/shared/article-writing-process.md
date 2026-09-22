# Article / Scientific Writing Process

This process governs prose composition after the Writer runtime has decided **what is being written**, prepared references, and created a DraftRequest. For scientific and engineering work, the DOM and Writer contracts are the source of truth. Prose is a rendered realization, not the authority layer.

## Authority order

For claim realization use this order:

1. `DraftRequest.authorized_claims`
2. `DraftArtifact.paragraphs[].realizes_claims`
3. canonical DOM `paragraph.claims`
4. rendered `[C-*]` markers as a checked projection only

Rendered markers must agree with the DOM, but they never create or authorize a claim by themselves.

Evidence authority belongs to Researcher verification. Writer may consume evidence and verdicts but may not upgrade them.

## Inputs

The normal scientific/engineering composition input is:

- WritingObjectDecision
- WritingPolicy
- StyleInstructionArtifact
- authorized claims
- per-claim evidence selection
- target section/paragraph identifiers
- DraftRequest

A style reference and an evidence source are different roles even when they point to the same file.

## Reference use

### Same-language style reference

May contribute bounded surface/rhetorical properties included in StyleInstruction, plus argument structure and graph motifs.

### Cross-language style reference

`STRUCTURE_ONLY`. May contribute:

- paragraph/argument architecture;
- graph motifs;
- citation architecture;
- ordering such as observation → comparison → interpretation → limitation.

It may not contribute lexical wording, syntax imitation, idioms or surface prose style.

### Evidence reference

Used claim-by-claim. Genre and language filters from style selection do not apply. Evidence still requires source identity, locator/provenance and Researcher validation.

## Draft workflow

1. Read the DraftRequest and WritingPolicy.
2. Compose only the requested scope.
3. Map every realized factual proposition to an authorized claim ID.
4. If drafting naturally produces a new synthesis, interpretation, comparison or causal hypothesis, emit `ProposedClaim/1.0` instead of silently treating it as authorized.
5. Return DraftArtifact-compatible structured output.
6. Code validates authorization, builds the DOM patch and applies optimistic-concurrency checks.
7. ChangeLedger records what changed.
8. Researcher handles unresolved/new evidence debt.
9. Traceability and semantic round-trip gates validate the rendered text.
10. Selective repair edits only affected paragraphs.

## Verification versus uncertainty

Do not conflate these dimensions:

- `verification_state`: whether the verification process has completed (`VERIFIED`, `UNCHECKED`, `FAILED`).
- `evidence_verdict`: support result (`SUPPORTED`, `CONTRADICTED`, `AMBIGUOUS`, etc.).
- `epistemic_state`: knowledge status (`ESTABLISHED`, `QUALIFIED`, `AMBIGUOUS`, `DISPUTED`, `UNKNOWN`).

`UNCHECKED` blocks evidence release but does not, by itself, require hedged prose. Hedging follows epistemic state and the authorized claim modality.

## Output standards

- Preserve numbers, units, qualifiers, entities, modality and causal strength.
- Keep disagreement and uncertainty visible.
- Do not pad beyond the authorized content.
- Do not let style references become evidence by accident.
- Do not let evidence sources become prose templates by accident.
- Return research debt explicitly rather than solving it through unsanctioned search.
