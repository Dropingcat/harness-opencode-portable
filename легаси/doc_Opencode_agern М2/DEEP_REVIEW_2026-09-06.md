# Deep review — doc_Opencode_agern

Date: 2026-09-06

## Executive assessment

The module has a strong architectural direction: deterministic routing, typed policies, explicit stop semantics, capability capsules, guard boundaries, audit/memory separation, and agent-role contracts. The main weakness is not the concept but **semantic duplication between code, graph, JSON policy and plugin runtime**. Several declared invariants were not actually enforced by code.

Current maturity estimate after this patch set:

- Architectural idea: **8.5/10**
- Deterministic runtime correctness: **6.5/10 -> 7.5/10 after fixes**
- Policy/source-of-truth discipline: **5.5/10**
- Testability/replay: **5/10 -> 6/10 after fixes**
- Security boundary truthfulness: **6/10**
- Production portability: **5.5/10 -> 6.5/10 after fixes**

## P0 findings fixed in this review

### P0-1 Router declared one policy and executed another
`route_resolution_policy.json` declared multi-match resolution, while `resolve_route.py` simply selected the first regex hit. Route order therefore silently became policy.

Fix: route priorities are now config-owned; explicit route/bucket hints are honored; profile strictness and match length participate in deterministic ranking; candidates and strategy are emitted for audit.

### P0-2 Claim classification was order-dependent
`detect_kind()` returned the first matching kind. A phrase such as “сделай аудит безопасности guard” could become a generic requirement instead of a security claim.

Fix: all matching kinds are collected and ranked by config-owned priority. `matched_kinds` is preserved in the claim artifact.

### P0-3 Strict profile could execute a standard mode
Bucket default execution mode overrode profile strictness. An optimization route could be `strict` while still running `worker_reviewer_tester`.

Fix: bucket mode is accepted only when it explicitly supports the selected profile; otherwise the profile-preferred mode wins.

### P0-4 Factory state machine could mark a task PASSED after reviewer approval before tests
`record_verdict(APPROVE)` directly set global state to PASSED. This contradicted the documented reviewer+tester gate.

Fix: reviewer approval leaves the task RUNNING. PASSED is reached after current reviewer approval plus tester PASS. Historical REQUEST_CHANGES no longer poison future successful iterations.

### P0-5 Graph builder was not deterministic and had an indentation/stale-variable bug
`build_skill_graph.py` generated start/finish steps inside the tool-binding loop using stale `rid/route_meta`. It also used Python `hash()`, which is process-salted and therefore unsuitable for replay-stable IDs.

Fix: steps are generated inside the route loop and use SHA-256 derived stable IDs. Node/edge ordering is deterministic. Graph schema version bumped to 2.

### P0-6 Core capsule violated least-capability routing
`core-orchestration` carried `coder_run`, `code_work`, and `profile_config`, so research/document routes inherited coding/config mutation tools.

Fix: core capsule now carries orchestration skills only. Tools come from route/domain capsules. Example: document extraction now resolves only `extract_document` instead of coding/config tools.

### P0-7 MCP lifecycle model contradicted actual transport
All bundled MCP servers are stdio servers, but lifecycle config and health code treated them like HTTP daemons with `/health` endpoints. The previous start script also deadlocked after two starts because its concurrency counter never decreased.

Fix: lifecycle config explicitly marks `transport=stdio`; impossible HTTP health checks were removed; lifecycle is declared host-managed; `start_mcp_servers.py validate` now validates command/cwd/python syntax instead of pretending to daemon-manage stdio MCP.

### P0-8 Guard timeout unit bug
`DOC_GUARD_TIMEOUT_MS=180000` was passed to `subprocess.run(timeout=...)` as seconds, yielding about 50 hours.

Fix: milliseconds are converted to seconds.

### P0-9 DOCX tables could crash extraction
The table extractor appended a generator object to the parts list; later string join could fail. `.xls` was also advertised despite `openpyxl` not supporting legacy XLS.

Fix: table rows are materialized as strings; unsupported `.xls` advertisement removed.

### P0-10 Launcher isolation claims were stronger than enforcement
The launcher described itself as bounded/sandboxed while `read_only_paths` was metadata only. `coder_router` defaulted to the user's home directory and accepted arbitrary workdirs.

Fix: wording now distinguishes run-directory isolation from an OS sandbox; metadata explicitly states `sandbox_enforced=false`; coder router defaults to the harness/cwd and enforces `CODER_ROUTER_ALLOWED_ROOTS`; timeout termination is Windows-aware.

## P1 findings not fully fixed

### P1-1 Plugin still duplicates route/tool policy
`plugins/tool-skill-contract-router.ts` embeds `contextRoutes`, `toolContracts`, and `untrustedTools` that overlap `config/tool_skill_routes.json`, `profile_routes.json`, and `guard_policy.json`.

Recommendation: make the TypeScript plugin a thin adapter. It should load a generated runtime snapshot, not own domain policy. Best pattern:

`config sources -> validate/compile -> runtime_snapshot.json -> Python router + TS plugin consume snapshot`

The compiled snapshot should carry `policy_hash`, schema version, route table, tool contracts, guard classification and capability bindings.

### P1-2 Too many partially overlapping registries
The module currently has route definitions distributed across `profile_routes`, `tool_skill_routes`, `skill_to_route_map`, capsule policy and `skills_graph`.

Recommendation: establish three authoritative inputs only:

1. `routes.json`: match/classification + bucket/profile/capsules;
2. `capabilities.json`: capsules -> skills/tools/runtime bindings;
3. `policy.json`: strictness/guard/budgets/stop semantics.

Everything else, especially graphs and plugin tables, should be generated artifacts.

### P1-3 Factory gate is still implicit
The patched state machine is safer, but it still does not derive required gates from `execution_modes.json`/bucket `done_when`. It assumes reviewer + tester for the common path.

Recommendation: introduce `GateSet` into state:

- required gates by route/profile/mode;
- per-gate latest state;
- attempt/revision id;
- gate evidence refs;
- recompute global state from gates only.

Never let individual agent submissions directly assign global success.

### P1-4 Attempt identity is under-modeled
`iteration` currently represents rework count, but outputs are not strongly tied to an `attempt_id`/revision. Cross-attempt reviewer/tester evidence can be mixed.

Recommendation: immutable attempt records: `attempt_id`, parent attempt, input claim revisions, worker artifact hash, reviewer verdict, tester result, auditor verdict. Only evidence from the same attempt may satisfy gates.

### P1-5 Guard is session-wide rather than artifact/provenance scoped
The guard scans the session database. This is useful but coarse: safe and unsafe fragments share one context, and the runtime cannot precisely say which artifact was admitted.

Recommendation: add an `UntrustedArtifact` envelope with origin, tool, hash, extraction boundary, guard verdict, policy version and sanitized derivative. Guard admission should attach to artifact IDs, then handoff passes only admitted artifacts.

### P1-6 No single transactional event log
Factory state, audit graph, memory, run files and kanban can diverge because writes are separate.

Recommendation: event-sourced controller or at minimum append-only `events.jsonl`/SQLite journal. Derived views (factory state, audit graph, memory promotion candidates, kanban projection) should be rebuilt from events.

### P1-7 Tests cover only a small fraction of the runtime
Before this review the module had almost no tests for its own router/factory core. Tests under reference/domain skills do not validate orchestration invariants.

Recommendation: build a contract test matrix for each route/profile/bucket and property tests for invariants:

- same input + same config => byte-stable route/graph;
- strict profile never selects weaker mode;
- untrusted tool implies guard requirement;
- global DONE impossible without all required gates;
- no route receives tools outside capsule policy;
- policy references resolve to existing IDs.

## P2 structural debt

- `numeric_comparator.py` (~888 lines) and `semantic_layer.py` (~835 lines) are becoming monoliths. Split parsing, normalization, comparison/rules, decision and serialization layers.
- Broad `except Exception` blocks are acceptable only at process boundaries. Internals should raise typed errors with reason codes.
- Configs need JSON Schema (or Pydantic/dataclass validation) rather than “valid JSON” checks only.
- `reason_codes.json` should be mandatory for state transitions, not merely documentation.
- `health_check.py` still needs a real JSONC parser if OpenCode config uses block comments/trailing commas.
- External research adapters should preserve raw provenance payloads separately from normalized summaries.

## Architectural target recommended

```text
Task
 -> deterministic Claim Extractor
 -> Claim Registry (immutable ids/revisions)
 -> Route Compiler (authoritative config snapshot)
 -> Capability Lease (minimum tools/skills, expiry/scope)
 -> Attempt Controller
      -> worker proposal
      -> artifact/evidence envelopes
      -> guard/admission
      -> reviewer/tester/auditor gates
 -> State Reducer (code-owned)
 -> Integration Gate
 -> event log
      -> audit graph projection
      -> memory promotion projection
      -> kanban/report projection
```

The key change is **compiled policy + state reducer**. LLMs propose. Tools produce artifacts. Validators produce evidence. Only the reducer mutates authoritative task state.

## Tests added and run

`tests/test_runtime_core.py` currently covers:

1. security claim priority over generic requirement;
2. code-review priority in overlapping route text;
3. strict optimization selects strict execution mode;
4. task-plan conflict structure;
5. reviewer approval cannot skip tester gate;
6. old REQUEST_CHANGES does not permanently poison a later corrected attempt.

Result on review environment: 6/6 passed. Python compileall also passed for `scripts`, `mcp`, `guard/src`, and tests.

## Recommended implementation order

1. **P1-A Runtime snapshot compiler**: collapse duplicated route/tool/guard knowledge into generated `runtime_snapshot.json` + hash.
2. **P1-B GateSet/Attempt model**: replace direct state assignment with reducer over typed events.
3. **P1-C Artifact provenance envelope**: guard and evidence admission by artifact ID/hash.
4. **P1-D Architecture validator CI**: cross-reference IDs, route/capsule/tool leakage, execution-mode/profile compatibility, graph determinism.
5. **P1-E Expand regression/property tests**.
6. Only then deepen L2/L3 memory and tribunal heuristics. Otherwise memory will faithfully learn inconsistencies produced by the runtime, a very human outcome but not a useful one.
