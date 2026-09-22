# Researcher R3: Task execution and peer delegation architecture

Status: **R3-L1 IMPLEMENTED**

## Purpose

Turn executable ResearchDOM leaf cards into auditable work without creating a second scheduler. R3 binds Researcher planning to the existing `scripts/jobs/job_ctl.py` Job/Attempt/Child runtime and to local capability providers.

Core flow:

`TASK/DELEGATION card → ExecutionPlan → LOCAL or PEER_DELEGATION → Observation/Artifact → ExecutionResult → ResearchTraceLink → downstream knowledge admission`

R3 executes work. It does **not** decide scientific truth. Capsule/peer outputs remain observations/artifacts until existing validators/reducers admit claims/evidence.

## Input contracts

### ResearchCard
Executable leaf must already pass PlanningGate and have at least one of:
- `dimensions.capability`
- `dimensions.delegation_target`

Typed R3 routing may also read:
- `dimensions.execution_owner`: `RESEARCHER | CODER | WRITER`
- `dimensions.route_id`: explicit deterministic route hint for a peer
- `dimensions.delegation_mode`: `required | optional | detached`

Natural-language regex routing is not authoritative for peer delegation.

### Parent Job
Delegation attaches to an existing Job through the existing child runtime. R3 does not invent a parallel scheduler or child-state format.

## New R3 domain blocks

### TaskExecutionPlan/1.0
Immutable compiled decision from a leaf card. Contains card id/revision, capability, execution mode, owner, route id, delegation mode and input payload.

Authority: deterministic compiler from ResearchCard + capability availability/policy.

### DelegationRequest/1.0
Domain-level peer request layered on top of `job_ctl` child records. It identifies target peer, capability/route, source card, parent job and required mode.

Authority: R3 compiler/reducer. It does not itself execute Coder/Writer.

### TaskExecutionResult/1.0
Records terminal outcome and produced artifact/observation references. Result is provenance, not epistemic admission.

### JobCtlDelegationAdapter
Infrastructure adapter only. Uses existing `job_ctl.create/load/save/event` state. Registers child in parent Job and creates/updates child Job state.

## Execution modes

### LOCAL
Used when `execution_owner=RESEARCHER` (or default Researcher ownership) and a registered capsule provides the requested capability.

Flow:
`TaskExecutionPlan → CapsuleRequest → CapsuleObservation → TaskExecutionResult`

Capsule output is explicitly untrusted and must pass the existing capsule authority guard before any admission.

### PEER_DELEGATION
Used for `CODER` or `WRITER`, or explicit `delegation_target`.

Flow:
`TaskExecutionPlan → DelegationRequest → parent child-add → child Job → peer result/artifact → child-finish → TaskExecutionResult`

Required child failure blocks parent reconciliation through existing `job_ctl.reconcile` behavior. Optional/detached modes keep their existing semantics.

## State transitions

R3 may transition the source leaf card through ResearchPatch:
- `READY/PLANNED → ACTIVE` when execution starts.
- `ACTIVE → COMPLETED` only after a successful terminal execution result and required artifact contract is satisfied.
- `ACTIVE → BLOCKED` when a required delegation fails or no executable provider/peer route exists.

R3 never marks a Claim supported solely because a task completed.

## Provenance and trace

At minimum R3 records:
- source ResearchCard id/revision;
- execution/delegation request id;
- capability and selected owner;
- parent/child Job ids;
- artifact/observation ids;
- terminal status and failure reason.

ResearchTraceLink is used to associate card with produced canonical knowledge entities once admission happens. Raw external artifact refs are kept in execution result/job provenance, not pretended to be canonical Claim/Evidence ids.

## Fail-closed rules

- Non-leaf or non TASK/DELEGATION card cannot execute.
- Missing capability/delegation target is rejected.
- Explicit peer owner without route/capability contract is rejected.
- LOCAL plan with no provider is rejected, not silently rerouted to an LLM.
- Stale card revision rejects start/finish transition.
- Duplicate delegation request id / duplicate child id is rejected.
- Required child failure cannot be reconciled as complete.
- Peer output never mutates ResearchDOM/KnowledgeGraph directly.

## Current limitations after R3-L1

- Existing `job_ctl` is JSON-file state runtime, not a service-level scheduler.
- `TaskExecutionRepository` durably stores typed plans/delegations/results through the existing SQLite UoW, but the peer child transport itself remains `job_ctl` file-state based.
- Peer invocation itself is not yet live Coder/Writer transport. R3-L1 proves lifecycle and typed child contracts; R3-L4 will bind real peer orchestrators.
- Artifact/observation admission to canonical Claim/Evidence remains R3.1. Task completion is deliberately not evidence admission.
- Retry/checkpoint/resume policies are still owned only by generic Job runtime and are not yet compiled from ResearchCard execution policy.
- Capability authority still contains known `evidence.verify` provider-priority debt (TD-017).

## Complexity ladder

### R3-L1
Typed TaskExecutionPlan + local capsule execution + JobCtl peer child lifecycle + card transitions + tests.

### R3-L2
Artifact admission bridge: peer/local observations → ProposedClaim/EvidenceSpan/Derivation proposals → canonical reducers + ResearchTraceLink.

### R3-L3
Retries/checkpoint/resume, timeout/budget policies, idempotency across process restarts, persistent delegation repository/outbox.

### R3-L4
Cross-peer orchestration chains Researcher↔Coder↔Writer with typed return contracts and acceptance gates.

### R3-L5
Outcome-history based routing/ranking of specialist/tool bundles, still bounded by deterministic capability/policy constraints.

## Definition of done for R3 first slice

- Existing Job/Child runtime is reused, not duplicated.
- Deterministic local/delegated plan compiler exists.
- Local capsule path returns untrusted observation and auditable result.
- Required peer child lifecycle can be created/completed/failed and reconciles exactly as `job_ctl` specifies.
- ResearchCard execution state transition is revision checked.
- No execution result directly changes epistemic truth.
- Targeted regression + full Researcher baseline run.
- Architecture/review/tracker/tech-debt documentation updated in the same commit.

## R3-L1 implementation record

Implemented in `researcher_core/task_execution.py`:

- `TaskExecutionPlan/1.0` with typed owner/mode/delegation policy.
- `DelegationRequest/1.0` over the existing Job/Child runtime.
- `TaskExecutionResult/1.0`; result remains provenance, not knowledge admission.
- deterministic leaf compiler with fail-closed local/provider and explicit peer routing rules.
- revision-checked `PLANNED/READY -> ACTIVE -> COMPLETED/BLOCKED` card transitions.
- real local `InMemoryCapabilityRegistry` capsule path with untrusted-observation guard.
- `JobCtlDelegationAdapter` creating and completing existing child Job records.
- required vs optional child behavior inherited from `job_ctl.reconcile`.
- `TaskExecutionRepository` using existing SQLite UnitOfWork for plan/delegation/result audit persistence.

Validation at this boundary: R3 tests 10/10 PASS; selected R1→R3 regression 71/71 PASS; full Researcher 431 total / 427 PASS / same 4 historical Guard/LocalCorpus failures.
