# Tracker / Tech Debt Delta v2 — Core ↔ Plugin Boundary

## Proposed new decisions

### D-P01 — OpenCode anti-corruption layer
Only the plugin HostAdapter may depend on OpenCode-specific SDK/plugin types. Harness Core receives normalized DTOs.

### D-P02 — Generic semantic execution contract
Researcher, Writer and Coder use one SemanticExecutionRequest/Result family. No role-specific OpenCode transports.

### D-P03 — OpenCode DB decoupling
`OPENCODE_SESSION_DB` is optional diagnostics/forensics, not a runtime correctness dependency.

### D-P04 — Legacy CLI explicit fallback
Direct `opencode run` launchers remain one deprecation cycle only as an explicitly selected provider. No silent fallback.

### D-P05 — Host capability certification
OpenCode support is based on version + live probes + packaged E2E, never version string alone.

## Additional tech debt

### TD-060 — Historical host-integration shell
`runtime_integration_policy.json`, `health_check.py`, `setup_env.*`, `register_plugin.py` still encode the old plugin/CLI model.

Acceptance:
Replace with Native Plugin installer, host-integration/2.0 policy and doctor.

### TD-061 — OpenCode session DB coupling
Guard/health paths still assume `OPENCODE_SESSION_DB`.

Acceptance:
Normal production flow works with no DB path; DB scan remains optional diagnostic provider.

### TD-062 — Semantic transport duplication
Tribunal, Coder and older research launchers have separate direct OpenCode invocation paths.

Acceptance:
All semantic execution routes through generic plugin bridge; module authority remains separate.

### TD-063 — Workspace identity normalization
Current host integrations sometimes infer cwd or use environment paths.

Acceptance:
HostContext + WorkspaceRef cross boundary; Core validates workspace; no implicit process cwd.

### TD-064 — Host readiness overclaim
Some providers are marked available because launcher/config exists, not because live semantic execution is ready.

Acceptance:
Provider readiness has adapter/bridge/runtime/auth/health/semantic/certification dimensions.

### TD-065 — Agent/skill discovery dependency
Some old orchestration documents assume OpenCode agent/skill autodiscovery paths.

Acceptance:
Internal Core semantics do not depend on OpenCode discovering named agent files. Agent packs are optional UX/runtime profiles.

## Workstream refinement

### WS-55A CORE-HOST-BOUNDARY-FREEZE
Status: DESIGN COMPLETE

Outputs:
- boundary audit;
- machine-readable matrix;
- migration plan;
- tech-debt delta.

### WS-56A STABLE-HOST-DTO-CONTRACTS
Build HostContext/WorkspaceRef/SemanticExecutionRequest/SemanticExecutionResult before RPC.

### WS-56B BRIDGE-RPC
Full-duplex TS/Python protocol.

### WS-57A OPENCODE-1.18.30-ADAPTER
Single anti-corruption layer + live probes.

### WS-57B PLUGIN-DOCTOR
Replace old health check.

### WS-58A GENERIC-SEMANTIC-PROVIDER
Plugin-backed semantic provider for Tribunal first, Writer/Coder later.

### WS-59A HOST-CERTIFICATION
Clean-install/upgrade/rollback matrix per OpenCode version.
