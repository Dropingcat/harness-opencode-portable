# Researcher R3.1 Execution Output Admission — implementation review

Status: COMPLETE, first admission slice
Boundary commit: pending final gate at document generation time

## Implemented

R3.1 adds a typed bridge from operational task success to canonical knowledge admission without granting capsules or peer orchestrators write authority.

Flow:

`TaskExecutionResult -> ExecutionAdmissionProposal -> deterministic preflight -> R0 ClaimRegistry -> ExecutionAdmissionReceipt -> ResearchTraceLink.PRODUCED`

New contracts:
- `ExecutionAdmissionProposal/1.0` (`EAP-*`)
- `ExecutionAdmissionReceipt/1.0` (`EAR-*`)

Supported typed proposal members:
- `ClaimProposal`
- `QuantityProposal`
- `Source`
- `EvidenceSpan`

Peer artifacts are accepted only through an explicit adapter-supplied `ProposalBatch`.

## Authority

`TaskExecutionResult` and `CapsuleObservation` remain untrusted operational outputs. The admission bridge packages/validates proposals. The existing R0 ClaimRegistry is the sole canonical write boundary for this slice. ResearchTrace links record production provenance but do not establish epistemic support.

## Validation

Preflight currently composes:
- `AtomicityValidator`
- `NumericValidator`
- `SourceAdmissionValidator`
- `EvidenceAdmissionValidator`

Validator FAIL blocks admission before registry mutation. WARN does not establish support and does not by itself block structural admission. The registry then applies dependency and batch atomicity checks.

TASK lineage is optimistic-concurrency checked: the source card must be COMPLETED and still have the exact revision expected from the execution result.

## Tests

- R3.1 targeted: 11/11 PASS.
- Selected R1 -> R3.1 regression: 82/82 PASS.
- Full Researcher: 442 total, 438 PASS, same four pre-existing TD-015 Guard/LocalCorpus failures.
- No new full-suite regressions.

## Important limitations

1. Admission does not imply scientific verification.
2. No inferred `EVD SUPPORTS CLM`, `QTY QUANTIFIES CLM` or `DERIVED_FROM` edge is created.
3. `ClaimProposal.source_span_ref` is not resolved in this slice.
4. R1 `Derivation` and `Assumption` are not yet admitted through the R0 registry.
5. Peer artifacts require an explicit typed adapter.
6. Validator selection is fixed, not yet policy/domain/method routed.
7. Legacy local-document capsule hashes/source vocabulary conflict with current admission validator contracts (TD-026).

## Development direction

R3.2 should add explicit temp-ID to canonical-ID resolution and relation proposals only where the execution adapter declared the relation. The system must not infer support/causality merely because entities were admitted in the same task.

Later R3 stages can add dependency-closed partial commits, Derivation/Assumption admission, policy-selected validator bundles, NEEDS_REVIEW/QUARANTINED branches, human review and Tribunal challenges.
