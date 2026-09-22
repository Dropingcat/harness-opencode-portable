# Writing Orchestration Process v1

Use this process for structured scientific/engineering writing and substantial long-form drafting. The canonical public entrypoint is `scripts/writer/cli.py`. Provider/backend names are implementation details and must not be passed to Writer agents.

## Pipeline

```text
WritingObjectDecision
→ Reference preparation
→ tiered style selection
→ per-claim evidence selection
→ WritingPolicy
→ StyleInstructionArtifact
→ DraftRequest
→ specialized Writer agent
→ DraftArtifact
→ DOM Patch
→ ChangeLedger
→ Research debt dispatch
→ evidence / traceability / semantic RTT gates
→ selective repair
```

## Object and reference selection

Explicit user intent determines document kind/section whenever available. Reference analysis is lazy: index the library cheaply, then fully profile only a small shortlist relevant to the current section.

Style and evidence are separate roles:

- same-language STYLE may contribute bounded surface rhetoric and structure;
- cross-language STYLE is `STRUCTURE_ONLY`;
- EVIDENCE is selected per claim and may cross genre/language.

## Drafting

The Writer receives DraftRequest, authorized claims, evidence-by-claim and StyleInstruction. It may not search for sources itself. Every paragraph declares `realizes_claims`. Any new proposition is returned as ProposedClaim and becomes research debt.

The Writer does not mutate the DOM. Code validates DraftArtifact and applies a hash-guarded DOM Patch.

## Authority and traceability

Authority order for realized claims:

```text
claim registry
→ DraftRequest authorization
→ DraftArtifact realizes_claims
→ DOM paragraph.claims
→ rendered [C-*] marker (projection only)
```

A DOM/marker mismatch blocks traceability release.

Verification is split into:

- `verification_state`: VERIFIED / UNCHECKED / FAILED;
- `evidence_verdict`: SUPPORTED / CONTRADICTED / UNSUPPORTED / AMBIGUOUS / OPEN;
- `epistemic_state`: ESTABLISHED / QUALIFIED / AMBIGUOUS / DISPUTED / UNKNOWN.

An unchecked claim blocks evidence release but does not automatically require hedged prose.

## Research debt

The Writer/orchestrator creates a ValidationPlan and ResearchDispatchContract. Researcher starts at the narrowest appropriate stage. Writer does not receive web discovery capability.

## Source updates

Source version changes flow through SourceCatalog and InvalidationPlan. State reducer marks affected claims and creates selective RepairRequests for only dependent paragraphs. Do not regenerate an entire chapter because one source changed.

## Release

Release requires all mandatory gates:

1. evidence verification;
2. traceability including authority binding;
3. semantic round-trip validation.

A later PASS cannot erase an earlier FAIL.
