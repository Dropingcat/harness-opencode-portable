# Implementation Tracker — Current Canonical View

## Completed / accepted boundaries

### Integrated Harness
- Writer unification and canonical CLI/runtime: accepted by saved tests.
- Researcher through R4.4 L3B deterministic/provider-bound process architecture: accepted structurally.
- Coder event-sourced factory, provenance/replay, explicit workspace authority: accepted.
- Common Router/Job/Capability runtime: accepted.
- Code-only distribution portability: accepted.

### Native Plugin P0/P1
- architecture/legacy isolation: documented;
- Host/Core boundary contracts: reported implemented;
- full-duplex bridge `harness-bridge-rpc/1.0`: reported implemented hostless;
- `harness_status`/`harness_run`: reported P1 surface;
- reverse RPC path: reported hostless;
- live Desktop certification: NOT COMPLETE.

## In progress / next

### WS-55A Core-host boundary freeze
Status: DESIGN COMPLETE.

### WS-56A Stable Host DTO
Status: P1 REPORTED / exact code baseline reconciliation required.

### WS-56B Bridge RPC
Status: P1 REPORTED HOSTLESS.

### WS-57A OpenCode adapter
Status: PARTIAL / exact 1.18.30 SDK call-shape live verification required.

### WS-57B Plugin doctor/live health
Status: HOSTLESS ONLY.

### WS-58A Generic semantic provider
Status: NOT PRODUCTION ENABLED.

### WS-59A Host certification
Status: NOT STARTED LIVE.

## Deferred scientific work

- TD-046 ResponseAssignment;
- TD-047 ClaimReviewCase;
- TD-048 HypothesisCase;
- TD-049 Evidence independence;
- TD-050 EvidenceDigest.

## Hard rule

Do not opportunistically modify Writer/Researcher/Coder state contracts while fixing OpenCode host compatibility. OpenCode-specific repair belongs in HostAdapter/bridge/compatibility layer.
