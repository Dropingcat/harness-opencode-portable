# OpenCode Native Plugin — Current State

## Status

`P1 HOSTLESS IMPLEMENTATION REPORTED / LIVE DESKTOP CERTIFICATION PENDING`

## Preferred architecture

Для Desktop сценария preferred transport:

`OpenCode Desktop -> Native Plugin -> full-duplex bridge -> Harness Core`

CLI остаётся explicit legacy fallback. Reverse-engineering Desktop IPC не является production strategy.

## P1 contract surface

OpenCode-facing:
- `harness_status`;
- `harness_run`.

Bridge:
- NDJSON JSON-RPC over stdio;
- full duplex;
- protocol `harness-bridge-rpc/1.0`.

Stable Core-facing DTO:
- `HostContext/1.0`;
- `WorkspaceRef/1.0`;
- `SemanticExecutionRequest/1.0`;
- `SemanticExecutionResult/1.0`.

## P1 boundary

`harness_run` на P1 выполняет deterministic core routing/bundle path. Это не означает, что Writer/Researcher/Coder уже полностью выполняются семантически через OpenCode.

`semantic.execute` должен быть включён только после live host certification.

## Host anti-corruption rule

Только HostAdapter знает OpenCode SDK/plugin-specific shapes. Raw OpenCode objects не пересекают bridge и не становятся Core state.

Если OpenCode меняет:
- ToolContext fields;
- SDK method parameters;
- session API;
- structured output behavior;

меняется HostAdapter/compatibility record, а не Claim/TEX/Writer/Coder schemas.

## Exact-version compatibility risk

Есть зафиксированное расхождение между публичными примерами SDK и exact-version generated types/contract assumptions (например, nested `body/query` vs flattened parameters). До live P2 необходимо проверить **фактически установленные** OpenCode plugin/SDK types и runtime behavior.

Версия строки сама по себе не считается certification.

## Live P2 acceptance

Обязательные gates:
1. plugin реально загружен;
2. legacy plugin не загружен одновременно;
3. `harness_status` виден;
4. `harness_run` виден;
5. real ToolContext корректно нормализуется;
6. bridge handshake;
7. doctor/health;
8. cancellation;
9. no mandatory `OPENCODE_BIN`;
10. no correctness dependency on `OPENCODE_SESSION_DB`;
11. one read-only semantic smoke;
12. recursion isolation;
13. credentials не передаются Python Core.

## Provider migration

До сертификации:
- existing CLI provider остаётся legacy explicit;
- plugin provider не должен silently replace его.

После P2/P3:
- plugin semantic provider preferred;
- CLI fallback только через новый preflight/new RPB lineage;
- затем Tribunal E2E;
- затем Writer/Coder transport convergence.
