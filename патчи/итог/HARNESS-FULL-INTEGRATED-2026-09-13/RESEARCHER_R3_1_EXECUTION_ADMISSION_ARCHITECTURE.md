# Researcher R3.1 — Execution Output Admission Architecture

Status: IMPLEMENTED (R3.1 L1)
Boundary: R3.1, after R3-L1 task execution

## Purpose

Turn successful execution outputs into *proposals for knowledge admission* without granting execution providers authority over the KnowledgeGraph.

Canonical flow:

`TaskExecutionResult -> ExecutionAdmissionProposal -> deterministic preflight/ClaimRegistry -> ExecutionAdmissionReceipt -> ResearchTraceLink -> canonical KG entities`

The invariant is strict: `TaskExecutionResult.status == SUCCEEDED` does not imply that any claim is true or any evidence is admissible.

## Inputs

- `TaskExecutionResult/1.0` from R3-L1.
- Completed source `ResearchCard` in `ResearchDOM`.
- Structured local observation or an explicit peer-artifact adapter output.
- Existing R0 `ProposalBatch` and `ClaimRegistry`.

## New contracts

### ExecutionAdmissionProposal/1.0 (`EAP-*`)
Records the exact execution result, source card and typed proposal batch offered for admission. It is not authoritative KG state.

### ExecutionAdmissionReceipt/1.0 (`EAR-*`)
Records the registry command and canonical entity IDs actually admitted. The receipt is provenance/audit, not an epistemic verdict.

## Authority boundaries

- Capsule/peer adapter: may emit typed proposals only.
- R3.1 compiler: may package proposals, never create canonical Claim IDs.
- R0 ClaimRegistry: sole authority for Claim/Quantity/Source/Evidence/Edge admission in this slice.
- ResearchTrace reducer: may add process provenance from TASK to admitted entities; it does not change claim epistemic state.

## First implementation scope

Supported structured payloads:
- `ClaimProposal`
- `QuantityProposal`
- `Source`
- `EvidenceSpan`

A payload may contain any non-empty combination of these typed tuples. Prebuilt graph edges and R1 `Derivation` admission are intentionally deferred until their dependency mapping can be explicit after canonical Claim IDs exist.

Peer artifact admission is supported only if a caller supplies an explicit typed `ProposalBatch`. No generic JSON/text inference occurs in this block.

## Validation / fail-closed behavior

Admission rejects when:
- execution failed/blocked;
- TASK card is not completed;
- result/card revision lineage is stale;
- observation payload contains unsupported or incorrectly typed proposal members;
- proposal batch is empty;
- registry dependency validation fails;
- peer artifact has no explicit typed adapter output.

No fallback LLM admission is permitted.

## Trace semantics

Every canonical entity admitted from the execution is linked back to the producing ResearchCard with `ResearchTraceRelation.PRODUCED`. Quantity (`QTY`) is added to the allowed trace target namespaces in R3.1.

## Current limitations

1. ClaimProposal `source_span_ref` is not yet resolved into an admitted SUPPORTS edge.
2. Quantity-to-claim semantic attachment is not inferred.
3. R1 `Derivation` is not admitted by the R0 registry in this slice.
4. Peer artifact parsing is adapter-driven only.
5. Admission receipt records registry acceptance, not scientific verification.
6. The first validator bundle is fixed in code (atomicity/numeric/source/evidence); policy-selected domain/method validator composition is deferred.
7. Legacy `LocalDocumentExtractionCapsule` output vocabulary/hash format is not compatible with current Source/Evidence admission validators; no silent normalization is performed (TD-026).

## Development ladder

L1 (R3.1): typed proposal admission + receipt + TASK trace.

L2: temp-ID resolution and post-admission edge compiler (`EVD SUPPORTS CLM`, `QTY QUANTIFIES CLM`) where explicitly declared.

L3: Derivation/Assumption proposal admission with dependency-closed partial commit.

L4: policy-selected validator bundles by claim/method/domain, with `NEEDS_REVIEW/QUARANTINED` branches.

L5: human/expert admission review and Tribunal-generated admission challenges.

L6: learned admission-routing metrics, while deterministic validators/reducers remain authority.

## Non-goals

- Deciding scientific truth at execution time.
- Allowing Writer/Coder to mutate Researcher KG directly.
- Generic artifact interpretation without a typed adapter.
- Automatic causal/support relation invention.
