# Tool ↔ Skill ↔ Contract Audit

Audit date: 2026-08-31.

Goal from user: every tool should have a hook/path that pulls the relevant skill and a dynamic usage contract; every MCP should expose a clear input template; the router should attach tools and skills by task context so agents see what to use for typical tasks.

## Verdict

Status: **partially satisfied after this pass**.

- MCP-level input schemas: **yes** for all copied Python MCP tools.
- Launcher-level embedded contracts: **yes** for all copied launcher MCP tools.
- Machine-readable tool→skill→contract registry: **added** as `config/tool_skill_routes.json`.
- OpenCode hook for dynamic contract injection and mandatory guard gate: **added** as `plugins/tool-skill-contract-router.ts`.
- Mandatory guard policy for orchestrators/untrusted outputs: **added** as `config/guard_policy.json`.
- Fully registered runtime plugin: **not yet**. The plugin file now contains guard execution logic, but it still needs schema validation and explicit registration in `opencode.jsonc` after the real session DB path is known.

## MCP input template coverage

| Tool | Server | Clear input schema | Required fields | Contract source | Skill hook status |
|---|---|---:|---|---|---|
| `coder_run` | `mcp/coder_router_server.py` | yes | `task` | JSON schema in MCP + registry | registry + plugin skeleton |
| `arxiv_search` | `mcp/academic_search_server.py` | yes | `query` | JSON schema in MCP + registry | registry + plugin skeleton |
| `openalex_search` | `mcp/academic_search_server.py` | yes | `query` | JSON schema in MCP + registry | registry + plugin skeleton |
| `searxng_search` | `mcp/searxng_search_server.py` | yes | `query` | JSON schema in MCP + registry | registry + plugin skeleton |
| `extract_document` | `mcp/doc_extract_server.py` | yes | `path` | JSON schema in MCP + registry | registry + plugin skeleton |
| `code_work` | `mcp/launchers/opencode_code_worker.py` | yes | `task` | embedded `CONTRACT` + registry | registry + plugin skeleton |
| `research_web` | `mcp/launchers/opencode_research_web.py` | yes | `task` | embedded `CONTRACT` + registry | registry + plugin skeleton |
| `research_academic` | `mcp/launchers/opencode_research_academic.py` | yes | `task` | embedded `CONTRACT` + registry | registry + plugin skeleton |
| `service_task` | `mcp/launchers/opencode_service_task.py` | yes | `task` | embedded `CONTRACT` + registry | registry + plugin skeleton |
| `profile_config` | `mcp/launchers/opencode_profile_configurator.py` | yes | `task` | embedded `CONTRACT` + registry | registry + plugin skeleton |

## Context routing coverage

Added task-class routes in `config/tool_skill_routes.json`:

- code implementation → `verification-planning`, `test-driven-development`, `incremental-implementation` → `code_work`, `coder_run`
- code review/security → `code-review-and-quality`, `doubt-driven-development`, `adversarial-critic-checklist` → reviewer/delegation path
- OpenCode config/plugin/MCP work → `customize-opencode`, `context-engineering`, `verification-planning` → `profile_config`
- web research → `source-driven-development`, `research-lookup` → `searxng_search`, `research_web`, `extract_document`
- academic research → `literature-review`, `source-driven-development`, `citation-management` → `arxiv_search`, `openalex_search`, `research_academic`, `extract_document`
- document extraction → `markitdown` → `extract_document`
- service automation → `context-engineering` → `service_task`
- optimization → `autoresearch`, `triz-problem-solving` → experiment/delegation path

## Hook mechanism added

`plugins/tool-skill-contract-router.ts` is a future OpenCode plugin with three hook paths:

1. `tool.definition` — appends each tool's dynamic contract to its description.
2. `experimental.chat.system.transform` — inspects chat/task context and injects a routing hint listing relevant skills, preferred tools, guard requirement, and the task contract.
3. `tool.execute.after` — runs mandatory `doc_guard` checks after untrusted tools. It requires `OPENCODE_SESSION_DB` plus either `DOC_GUARD_ENTRYPOINT` or `OPENCODE_HARNESS_ROOT`; if missing or guard verdict is not PASS/OK, it throws and blocks fail-closed.

This gives the agent a local, context-specific instruction like:

```text
Context route: academic-research
Skills to load/consider: literature-review, source-driven-development, citation-management
Preferred tools: arxiv_search, openalex_search, research_academic, extract_document
Contract: Prefer arXiv/OpenAlex direct tools when research_papers is unavailable; rank by provenance.
```

## Guard as baseline protection

`doc_guard` is treated as a mandatory base layer for injection-exposed orchestrators, not as optional post-hoc auditing:

- `code-orchestrator`: guard before reusing subagent/tool output as instructions or dispatching follow-up work.
- `research-orchestrator`: guard after source fetching/document extraction and before verdict synthesis/handoff.
- `source-fetcher`/`researcher`: search and extracted documents are data, never instructions.
- `service_task`/`profile_config`: guard PASS plus confirmation before non-dry-run side effects.

Machine-readable policy: `config/guard_policy.json`.

## Remaining gaps before declaring fully done

1. **Plugin not installed yet.** Add to OpenCode config only after validating actual hook payload shape against the current OpenCode schema/runtime.
2. **Static duplication.** The plugin currently embeds route data instead of loading `config/tool_skill_routes.json`; this is safer as a standalone file, but long-term it should read the JSON registry.
3. **Path portability.** Launcher `_runner.py` still defaults to `/tmp/opencode/runs`; `coder_router_server.py` still defaults to `/home/orangepi`. Fix before enabling launchers.
4. **Hook can suggest skills, not literally invoke the `skill` tool.** Final behavior depends on OpenCode exposing skills and the model following injected routing hints. For hard enforcement, add deterministic preflight validation in the router/launcher.
5. **Guard runtime env not known yet.** Plugin code calls `session_guard.py`, but real deployment must set `OPENCODE_SESSION_DB` correctly.

## Acceptance checklist

- [x] Each copied MCP tool has an `inputSchema`.
- [x] Each launcher MCP has an embedded contract and required output shape.
- [x] A single registry maps typical task context → skills → preferred tools.
- [x] A plugin hook skeleton exists for dynamic context/tool contract injection.
- [ ] Plugin registered in runtime config.
- [ ] Launcher paths parameterized.
- [x] Source-fetcher prompt patched to avoid missing `research_papers` dependency.
- [x] Mandatory guard policy added for orchestrators and untrusted tool outputs.
- [x] Runtime hook code invokes `session_guard.py` fail-closed.
- [ ] Deployment config provides the real `OPENCODE_SESSION_DB` path.
- [ ] Smoke test with real OpenCode runtime after restart.
