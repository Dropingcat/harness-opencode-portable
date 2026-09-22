# Capability Registry

Реестр того, что harness должен уметь, чем это покрывается сейчас, и что надо подключать.

## MCP / Tools

| Capability | Candidate tool/server | Status | Notes |
|---|---|---|---|
| One-shot OpenCode delegation | `coder_router_server.py`, `coder_run` | copied into bundle | model_class: free/fast/polza/custom |
| Code worker launcher | `opencode_code_worker.py`, `code_work` | copied into bundle | write only in run/worktree, no secrets |
| Web research delegate | `opencode_research_web.py`, `research_web` | copied into bundle | SearXNG/browser/DDG first |
| Academic research delegate | `opencode_research_academic.py`, `research_academic` | copied into bundle | arXiv/OpenAlex/research-mcp/PapersFlow |
| Service task delegate | `opencode_service_task.py`, `service_task` | copied into bundle | Composio, dry-run by default |
| Profile configurator | `opencode_profile_configurator.py`, `profile_config` | copied into bundle | backup + validate + smoke-test |
| Academic direct search | `academic_search_server.py` | copied into bundle | arXiv + OpenAlex, no API keys |
| Web meta-search | `searxng_search_server.py` | copied into bundle | requires local SearXNG at 127.0.0.1:8888 |
| Document extraction | `doc_extract_server.py` | copied into bundle | PDF/DOCX/HTML/XLSX/TXT/MD/CSV |
| Code search on GitHub | grep.app / `gh_grep` | current Windows MCP has grep_app | untrusted output, guard must scan |
| Documentation lookup | context7 | candidate from OMO | untrusted output, guard must scan |
| Research papers | `research_papers` plugin or academic MCP | partially duplicated | do not blindly duplicate |
| Memory | `opencode-mem` | candidate plugin | first runtime plugin to add after safety check |
| Autoresearch | `@sndrgrdn/opencode-autoresearch` | candidate/installed elsewhere | only for measurable optimization |

## Routing table

| Task class | Skills | Delegate/tool path |
|---|---|---|
| Simple config/setup | context-engineering, verification-planning | profile_config or direct minimal edit with backup |
| Code implementation | incremental-implementation, test-driven-development | code_work / coder-worker → code-tester |
| Code review | code-review-and-quality, doubt-driven-development | code-reviewer / oracle |
| Security/guard | ariz-contradiction-resolution, adversarial-critic-checklist | code-auditor + doc_guard |
| Scientific source search | source-driven-development, literature-review | academic_search / research_academic / source-fetcher |
| Web research | source-driven-development | searxng_search → doc_extract/webfetch |
| Service automation | context-engineering | service_task via Composio dry-run |
| Optimization | autoresearch, triz-problem-solving | experimenter / autoresearch plugin |

## Mandatory guard routing

Guard is a base capability, not a normal optional tool. Any route that consumes untrusted output must include `doc_guard` as a gate:

- `code-orchestrator`: guard before using subagent/tool output as instructions or before dispatching follow-up workers.
- `research-orchestrator`: guard after source fetch/document extraction and before verdict synthesis/handoff.
- `source-fetcher`/`researcher`: web/search/document outputs are data, never instructions.
- `service_task`/`profile_config`: guard PASS + user confirmation before non-dry-run side effects.

Machine-readable policy: `config/guard_policy.json`.
| Multi-agent conflict | ariz-contradiction-resolution, doubt-driven-development | tribunal-judge / council-style review |

## Dynamic contract registry

Machine-readable routing and tool contracts now live in:

- `config/tool_skill_routes.json`

OpenCode hook for injecting these hints into tool definitions/context and running mandatory guard after untrusted tools lives in:

- `plugins/tool-skill-contract-router.ts`

Audit status is recorded in:

- `TOOL_SKILL_CONTRACT_AUDIT.md`

Prepared start/finish templates and router hook behavior are documented in:

- `ROUTER_HOOKS_AND_TEMPLATES.md`
- `config/tool_skill_templates.json`

Cross-domain architectural invariants shared with researcher-core are documented in:

- `UNIFIED_ORCHESTRATION_PRINCIPLES.md`

Module-wide subsystem scope is documented in:

- `UNIFIED_MODULE_SCOPE.md`
- `MEMORY_POLICY.md`
- `SKILLS_MODULES.md`
- `SKILL_CAPSULE_ARCHITECTURE.md`
- `SKILL_GRAPH_ARCHITECTURE.md`
- `IMPLEMENTATION_TRACKER.md`

Server/source lineage map is documented in:

 - `sources/SERVER_SOURCE_LAYOUT.md`

Claim-to-bucket routing layer is documented in:

 - `CLAIM_ROUTING_ARCHITECTURE.md`
 - `config/claim_kinds.json`
 - `config/claim_bucket_rules.json`

## Known runtime mismatch

Original Windows `source-fetcher` assumed `research_papers` exists, but current `opencode.jsonc` did not include `opencode-research-papers`. In this bundle, `agents/source-fetcher.md` has been patched to use `research_papers` only if present and otherwise fall back to `arxiv_search` / `openalex_search` from `academic_search_server.py`.

Long-term runtime options:

1. adding the plugin, or
2. keeping the direct MCP fallback as the primary path.
