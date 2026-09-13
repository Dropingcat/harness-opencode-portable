# R4.4 L3A Implementation Review

Date: 2026-09-13
Scope: provider binding, bounded execution envelope, process Q1/A1/Q2/A2, runtime edge cases and local traceability.

## 1. Review basis

This review was written after E2E execution, not before it. The implementation was restored onto the canonical R4.4 L2b Git checkout, the unfinished L3 files were reapplied as a normal diff, and the full R4 targeted suite was rerun.

Observed acceptance at review time:

- R4 targeted: 104/104 PASS;
- full Researcher: 581 total / 577 PASS / 4 known TD-015 failures;
- runtime compiler: PASS after authoritative config regeneration;
- capability compiler: PASS after authoritative config regeneration;
- production Tribunal provider preflight in this container: implemented/degraded, `missing:opencode`.

## 2. Defects found by live/process E2E

### D1 — DQC had a questioner but no explicit answerer

The structural contract could identify who asks Q1/Q2 but not who must answer. Inferring answerer from the target ARG selected the challenge author in the first live vertical, making Skeptic ask and answer its own question.

Fix:

```text
DQC/1.1
  role_id        = questioner
  answer_role_id = addressed responder
```

Current bounded dialectic also rejects accidental self-response.

### D2 — immutable Python mapping did not cross Job JSON boundary

TEX initially carried deeply frozen mapping proxies. Job contract hashing/serialization expects JSON-compatible values.

Fix: canonical recursive JSON projection at the execution boundary.

### D3 — live answer was observed before ArgumentGraph admission

Provider returned valid A2, but the DialecticObserver correctly rejected it because the new ARG had not yet entered the current AGP revision.

Fix: explicit `admit_live_answer_to_argument_graph()` step creates historical `REPLIES_TO`, refreshes branch snapshot, then observer runs.

### D4 — provider implementation existence was confused with execution readiness

Existing preflight historically treats a file-backed agent as implemented/available when no live probe exists. That is too weak for live Tribunal execution.

Fix: Tribunal provider binding requires declared live probe plus current preflight availability. Production OpenCode provider therefore reports implemented but unavailable when executable is missing.

### D5 — provider role-kind/contract declarations were present but not binding authority

Capability match alone could choose a provider incapable of the required semantic role/contract.

Fix: binding filters `role_kinds` and `execution_contracts` before priority selection.

### D6 — runtime receipt was not independently durable

Without a durable runtime receipt, absence of ARG/IQT could not be distinguished later between timeout, transport failure and deterministic output rejection.

Fix: `PER-*` is persisted on success and failure paths.

## 3. Strong properties after hardening

- questioner/responder separation is explicit and replayable;
- role/provider/runtime identities remain distinct;
- provider discovery uses shared authority and preflight rather than a Tribunal registry;
- deterministic selection precedes execution;
- stale binding is detected before child-job creation;
- multiple healthy providers do not imply multiple executors;
- bounded TEX physically omits hidden sibling material;
- runtime failures never become scientific OPEN;
- invalid provider output can be REJECTED even when transport succeeded;
- semantic output cannot affect dialectic state before graph admission;
- RPB/TEX/PER are replayable fingerprinted artifacts;
- second role-family E2E proves role-kind routing outranks provider priority.

## 4. Current limitations / open questions

### 4.1 Production semantic worker unavailable here

`existing.opencode_tribunal_role` is registered under shared authority but current preflight reports `missing:opencode`. Therefore deterministic subprocess E2E proves process/runtime/control-plane behavior, not the quality of an actual LLM reviewer.

### 4.2 Who should answer remains a higher-level policy problem

`answer_role_id` prevents ambiguity in one DQC. It does not yet model Claim-facet ownership, original position ownership, Defender/Advocate arbitration or multidisciplinary review join. TD-046/TD-047 track that future layer.

### 4.3 Advocate not yet executed through live binding

Structural Advocate activation/defense exists from L2a. It should be bound through the same RPB/TEX/PER path only after production semantic Q/A is available.

### 4.4 Universal traceability remains open

The execution chain is locally reproducible but there is not yet one query/index joining R3/R4/Writer/Coder lineage. TD-038 remains high.

## 5. Verdict

**PASS for R4.4 L3A structural/runtime boundary.**

Provider binding, bounded execution envelopes, process-level Q/A and failure semantics are coherent enough to freeze. Do not label this production semantic Tribunal completion. The next live milestone requires an actually available semantic provider and conditional Advocate execution on top of the same contracts.

## 6. Milestone boundary

Feature commit:

`8b15c1384c5d73774e59be0a9258b1b11d7e1fb9`
`researcher: bind bounded tribunal dialogue providers`

Milestone package:

`RESEARCHER-R4.4-L3A-PROVIDER-BINDING-DIALOGUE-001.zip`

SHA256:

`f1c3c831e3d6e34206d166fa77571512738acb8ab7ea2d4f10511d37bfeed221`

The package is patch-oriented and starts from the completed R4.4 L2b boundary. Production semantic OpenCode execution is deliberately not claimed by this package.
