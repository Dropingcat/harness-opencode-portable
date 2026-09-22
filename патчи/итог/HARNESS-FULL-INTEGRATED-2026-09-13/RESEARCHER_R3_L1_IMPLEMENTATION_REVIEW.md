# Researcher R3-L1 implementation review

## Boundary

R3-L1 implements execution of authoritative ResearchDOM leaf cards and peer-delegation lifecycle without introducing another scheduler and without conflating task success with scientific truth.

## Implemented blocks

`researcher_core/task_execution.py` adds typed `TaskExecutionPlan/1.0`, `DelegationRequest/1.0` and `TaskExecutionResult/1.0`; deterministic plan compilation; local capsule execution; JobCtl peer delegation adapter; revision-checked ResearchCard start/finish transitions; and SQLite/UoW audit persistence.

The identifier registry now includes `TEP`, `DLG`, `TER` namespaces for these typed execution objects.

## Local execution

A Researcher-owned leaf with a registered capability compiles to `LOCAL`. The capability is resolved from the existing `InMemoryCapabilityRegistry`. Capsule output must pass `assert_capsule_observation_is_untrusted`. The observation can be persisted in TaskExecutionResult but is not converted to Claim/Evidence in this phase.

Missing local provider fails closed. The compiler does not silently reroute the task to a peer or generic LLM.

## Peer delegation

A leaf with explicit CODER/WRITER ownership compiles to `PEER_DELEGATION`. `DelegationRequest` carries the source card, plan, capability, explicit route hint when present, parent/child Job ids and required/optional/detached mode.

`JobCtlDelegationAdapter` reuses the existing `job_ctl.create/load/save/event/reconcile` schema. Required child failure remains a parent reconciliation failure; optional child failure does not block parent reconciliation. No duplicate scheduler state machine was introduced.

The first slice does not call a live Coder/Writer transport. That remains a later adapter boundary.

## ResearchDOM authority

Execution starts only from a leaf TASK/DELEGATION in PLANNED/READY state. Plan compilation captures source-card revision. Start and finish both fail on stale revision. A successful result moves ACTIVE→COMPLETED; failed execution moves ACTIVE→BLOCKED.

No execution function changes Claim/Evidence/Gap/Conflict state.

## Persistence

`TaskExecutionRepository` stores plans, delegation requests and results using the existing SQLite UnitOfWork. This gives local observations an audit record instead of leaving them as process-local return values.

## Tests

R3-L1: 10/10 PASS.

Selected R1/R1.1/R2/R2.1/R2.2/R2.3/R2.3.1/R2.3.3/R3-L1: 71/71 PASS.

Full Researcher suite: 431 total, 427 PASS, 4 existing TD-015 Guard/LocalCorpus failures. TD-020 SQLite ResourceWarnings remain visible. No R3 regression was added.

## Recovery incident

At R3 start the extracted working snapshot no longer contained `.git`. The repository was reconstructed from `harness_writer_v1_researcher_r1_1.bundle` and the ordered R2, R2.1, R2.2, R2.3, R2.3.1 and R2.3.3 mail patches. This worked cleanly and preserved the source history, but the restore path is not yet automated. It is recorded as TD-023.

## Limitations and next development

R3.1 should introduce the admission bridge: execution output → ProposedClaim/EvidenceSpan/Derivation proposals → existing deterministic validators/reducers → canonical entities → ResearchTraceLink back to the source ResearchCard.

Later R3 should bind live Coder/Writer dispatch, persistent outbox/idempotency across process restarts, retry/checkpoint/budget policy, and typed acceptance gates. Those are intentionally not smuggled into L1 under a reassuring filename.
