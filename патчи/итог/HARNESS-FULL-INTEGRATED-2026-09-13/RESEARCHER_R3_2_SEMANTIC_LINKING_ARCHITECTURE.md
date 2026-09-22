# Researcher R3.2: explicit post-admission semantic linking

Status: IMPLEMENTED / EXERCISED (L1)
Boundary: after R3.1 execution-output admission, before evidence assessment / Tribunal.

## 1. Purpose

R3.2 turns explicitly declared semantic relations from an execution adapter into canonical `GraphEdge` entities. It does not infer relations from co-occurrence and does not change Claim truth state.

Control-plane invariant:

`TaskExecutionResult -> admission -> identity resolution -> explicit relation proposal -> relation validation -> GraphEdge admission`.

`Admission != support verdict`; `GraphEdge(SUPPORTS) != ClaimStatus.SUPPORTED`.

## 2. New artifacts

- `AdmissionIdentityMap/1.0` (`AIM-*`): maps `ClaimProposal/QuantityProposal.temp_id` to canonical `CLM/QTY` IDs admitted by R3.1; also records all canonical IDs from the admission receipt.
- `SemanticRelationProposal/1.0` (`SRP-*`): adapter-declared source endpoint, target endpoint, `EdgeKind`, rationale and provenance.
- `SemanticLinkReceipt/1.0` (`SLR-*`): audit result containing admitted `EDG-*` and generated trace IDs.

Canonical relation authority remains `GraphEdge` in `ClaimRegistry`.

## 3. Supported L1 relation shapes

- `EVD -> CLM : SUPPORTS`
- `EVD -> CLM : CONTRADICTS`
- `QTY -> CLM : QUANTIFIES`
- `CLM -> CLM : DERIVED_FROM`

Other `EdgeKind` values are rejected in this execution-linking boundary until a dedicated semantic contract is defined.

## 4. Identity resolution

Endpoints are typed:

- `TEMP`: must resolve through current `AdmissionIdentityMap`;
- `CANONICAL`: must be one of the canonical IDs in the same admission receipt.

Unknown, malformed or cross-receipt endpoints fail closed.

L1 reconstruction of `CLM/QTY` temp identity relies on the R0 registry's documented accepted-ID grouping/order. This is deterministic in the current registry but is an implementation coupling. A later registry-native temp->canonical map should remove this coupling.

## 5. Authority and state transitions

`SemanticRelationProposal` cannot mutate KnowledgeGraph. `admit_semantic_relations()`:

1. validates proposal lineage;
2. resolves endpoints;
3. checks the relation compatibility matrix;
4. rejects duplicates inside the batch and exact duplicates already present in canonical registry;
5. builds immutable `GraphEdge` candidates;
6. admits them atomically through existing `ClaimRegistry`;
7. emits `ResearchTraceLink(PRODUCED -> EDG)` and `SemanticLinkReceipt`.

Claim status is unchanged.

## 6. Fail-closed behavior

R3.2 rejects:

- implicit/co-occurrence linking;
- unknown temp refs;
- canonical refs outside the current admission receipt;
- unsupported edge kinds;
- invalid endpoint namespace combinations;
- duplicate relation proposals;
- canonical duplicate edges;
- proposal/admission lineage mismatch.

## 7. Persistence / observability

`ExecutionLinkingAuditRepository` stores audit projections of `AIM`, `SRP`, `SLR` in the existing SQLite state substrate. `EDG` authority and lifecycle remain in `ClaimRegistry` / graph state.

`ResearchTraceLink` now permits `EDG` targets, aligning provenance with R2.3.3 where relations became first-class information objects.

## 8. Current limitations

1. Cross-admission linking is intentionally disabled.
2. The compatibility matrix is small and hard-coded for L1.
3. No semantic relation validator beyond endpoint type/kind compatibility and duplicate checks.
4. `AIM` reconstruction depends on R0 registry accepted-ID ordering for generated CLM/QTY IDs.
5. No automatic edge proposal extraction from arbitrary prose/artifacts.
6. No relation confidence, justification set or Tribunal assessment in R3.2.
7. `SUPPORTS`/`CONTRADICTS` admission records a declared relation, not final epistemic strength.

## 9. Development ladder

### L2: cross-admission authorization
Typed `ExternalEndpointBinding` allowing a new task to relate newly admitted evidence to an existing canonical Claim, with scope/run/policy checks and explicit authorization.

### L3: registry-native identity mapping
Move proposal-temp -> canonical-ID mapping into the canonical admission result/event contract, eliminating ordering dependence.

### L4: relation policy compiler
Replace the local relation compatibility table with versioned policy: allowed source/target types, required provenance, validator set and reason codes.

### L5: relation assessment
Attach evidence quality, scope match, contradiction strength, methodology and Tribunal arguments to relation assessment without mutating endpoint truth directly.

### L6: justification sets / TMS integration
Multiple independent relation justifications, quorum, nogoods and selective stale/reopen integrated with R2 invalidation.

## 10. Tests required at this boundary

- explicit QTY->CLM relation admitted;
- explicit EVD->CLM support admitted;
- co-occurrence produces no edge;
- unknown temp ref fails closed;
- invalid namespace/kind fails closed;
- cross-receipt canonical endpoint fails closed;
- duplicate batch relation rejected atomically;
- duplicate canonical relation rejected;
- audit artifacts persist;
- R1->R3 regression remains stable.
