# Architecture block documentation standard

Status: ACTIVE from 2026-09-12.

Purpose: every new Writer/Researcher/Coder architectural block is documented at implementation time, not reconstructed after the fact.

## Required block card

Each non-trivial block MUST have a co-located architecture section or review entry with the following fields.

1. **Block identity**
   - name/version
   - owner orchestrator
   - implementation files
   - public contracts
   - policy/config dependencies

2. **Purpose**
   - problem solved
   - why the block exists
   - what it explicitly does not solve

3. **Inputs / outputs**
   - accepted object types
   - produced entities/artifacts/events
   - state transitions owned by the block

4. **Authority boundary**
   - what is authoritative
   - what is only a proposal/projection/cache
   - which reducer is allowed to mutate state

5. **Links to surrounding architecture**
   - upstream/downstream blocks
   - ResearchDOM / KnowledgeGraph / RoutingHistory relations
   - provenance edges emitted/consumed

6. **Current implementation limits**
   - known unsupported cases
   - current heuristics
   - scaling limits
   - concurrency assumptions
   - environment dependencies

7. **Failure modes and fail-closed behavior**
   - stale revision
   - unavailable capability
   - insufficient evidence
   - conflicting state
   - malformed artifact
   - budget exhaustion

8. **Complexity ladder / future development**
   - L0: deterministic minimum
   - L1: typed heuristics / policy routing
   - L2: adaptive ranking from history
   - L3: iterative multi-agent/tribunal behavior
   - L4: learned routing/calibration after enough history exists
   Not every block needs every level. Missing levels must be marked N/A rather than invented.

9. **Tests / acceptance gates**
   - unit/integration tests
   - replay/idempotency tests
   - policy compiler gates
   - representative E2E fixture

10. **Tech debt links**
    - explicit TD identifiers
    - sunset/review triggers

11. **Legacy lineage**
    - source legacy documents/modules if the block restores or replaces an older concept
    - what was preserved semantically
    - what was intentionally not carried forward

## Architecture rule

Documentation is part of the implementation boundary. A block is not considered frozen/stable if its authority, limitations, failure behavior and complexity ladder are undocumented.

## Shared complexity principle

The harness uses recursive typed-object processing:

`Object -> Profile -> Routing -> Specialists/Tools/Skills -> Processing -> Validation -> State/New Objects`.

The documentation for each block must state which part of that cycle it owns.
