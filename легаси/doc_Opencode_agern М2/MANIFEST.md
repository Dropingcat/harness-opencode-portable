# Manifest

Generated: 2026-08-31.

## Summary

- Python files observed after copy: 123
- Markdown files observed after copy: 446
- Skill directories observed: 183
- Agent markdown files observed: 15

This manifest is intentionally descriptive rather than a cryptographic lockfile. It records the pass-1 bundle state and excludes secrets/runtime state by policy.

## Top-level inventory

- `agents/` — current OpenCode agent markdown files copied from `C:\Users\Arhys\.config\opencode\agent`.
- `skills/opencode-current/` — current OpenCode skill directories copied from `C:\Users\Arhys\.config\opencode\skills`.
- `skills/server2-corpus/` — module-owned copy of `W:\server2\skills` (184 skill modules).
- `mcp/` — selected MCP servers copied from `Z:\server\.hermes\mcp`.
- `mcp/launchers/` — selected OpenCode launcher MCP wrappers.
- `guard/` — safe `doc_guard` subset: source, docs, and example config only.
- `references/` — architecture and integration notes from `doc_hermes_pi`.
- `sources/` — source map and audit provenance.
- `config/` — machine-readable tool/skill/context route registry.
- `plugins/` — OpenCode plugin files for runtime hook injection and guard gates.

## Runtime-critical files

- `README.md`
- `ARCHITECTURE.md`
- `CAPABILITY_REGISTRY.md`
- `INTEGRATION_PLAN.md`
- `SECURITY_GUARD.md`
- `shared/code-factory-process.md`
- `scripts/code-factory/factory_ctl.py`
- `scripts/code-factory/contract_validator.py`
- `scripts/code-factory/code_factory_runner.py`
- `mcp/coder_router_server.py`
- `mcp/academic_search_server.py`
- `mcp/doc_extract_server.py`
- `mcp/searxng_search_server.py`
- `guard/src/session_guard.py`
- `config/tool_skill_routes.json`
- `config/guard_policy.json`
- `config/strictness_profiles.json`
 - `config/claim_state_machine.json`
 - `config/claim_kinds.json`
 - `config/claim_bucket_rules.json`
 - `config/bucket_contracts.json`
- `config/skills_registry.json`
- `config/skill_capsule_policy.json`
- `config/skill_to_route_map.json`
- `config/profile_routes.json`
- `config/route_resolution_policy.json`
- `config/execution_modes.json`
- `config/tool_runtime_bindings.json`
- `config/skills_graph.json`
- `config/reason_codes.json`
 - `scripts/router/resolve_route.py`
 - `scripts/router/build_skill_graph.py`
 - `scripts/router/split_claims.py`
 - `scripts/router/build_task_plan.py`
 - `plugins/tool-skill-contract-router.ts` — dynamic tool/skill contract injection plus mandatory `doc_guard` gate after untrusted tools.
 - `CLAIM_ROUTING_ARCHITECTURE.md`
- `TOOL_SKILL_CONTRACT_AUDIT.md`
- `UNIFIED_ORCHESTRATION_PRINCIPLES.md`
- `UNIFIED_MODULE_SCOPE.md`
- `MEMORY_POLICY.md`
- `SKILLS_MODULES.md`
- `SKILL_CAPSULE_ARCHITECTURE.md`
- `SKILL_GRAPH_ARCHITECTURE.md`
- `IMPLEMENTATION_TRACKER.md`
- `PRECONTINUATION_WEAKNESS_AUDIT.md`
- `AGENT_ARCHITECTURE_PLAN_VS_FACT.md`
- `RUNTIME_RUNBOOK.md`
- `RUNTIME_HEALTH_AUDIT.md`
- `SKILL_ADDING_CHEATSHEET.md`
- `AGENT_SKILLS_RECONCILIATION.md`
- `scripts/setup_env.ps1`
- `scripts/setup_env.sh`
- `scripts/add_skill.py`
- `scripts/sync_to_live.py`
- `SCRIPT_SCATTER_MAP.md`
- `guard/docs/*` (11 файлов — полный doc-набор doc_guard)

## Exclusion policy

Do not add these to the bundle:

- `.env` files with real values
- real `guard_config.json`
- `opencode.db` or other runtime session databases
- API keys, tokens, cookies, auth headers
- cache folders such as `__pycache__`, `.pytest_cache`, `node_modules` unless explicitly vendoring a dependency snapshot

## Known issue from pass 1

One copied reference document contained an example-looking but token-shaped Composio header value. It was redacted in-place to `REDACTED-SET-VIA-ENV`.
