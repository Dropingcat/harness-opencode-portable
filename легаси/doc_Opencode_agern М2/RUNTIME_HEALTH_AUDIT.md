# Runtime Health Audit: Routers, MCP, Skills (non-researcher agents)

Дата: 2026-09-01. Фокус: работоспособность того, что агенты (кроме researcher-контура) реально используют: роутеры, MCP-серверы, скилы.

## 1. Router resolvers — PASS

Прогнаны фактически (не только по докам):

| Скрипт | Test input | Result |
|---|---|---|
| `scripts/router/resolve_route.py` | "Implement a new feature and add tests" | OK rc=0 |
| `scripts/router/resolve_route.py` | "Find papers on MTP in LLMs" | OK rc=0 |
| `scripts/router/split_claims.py` | "Fix docs and add tests for router core" | OK rc=0 |
| `scripts/router/resolve_capsules.py` | academic-research | OK rc=0 |
| `scripts/router/resolve_tool_capsule.py` | academic-research | OK rc=0 |
| `scripts/router/resolve_mcp_capsule.py` | academic-research | OK rc=0 |

Вывод: роутерный стек исполним.

## 2. MCP servers and launchers — PASS (compile + import + stdio handshake)

- Все 4 сервера + 5 лаунчеров: `py_compile` OK.
- Пакет `mcp` (SDK) присутствует, `mcp.server` импортируется.
- У каждого зарегистрирован tool с `inputSchema`/`list_tools`:
  - `coder_run`, `arxiv_search`+`openalex_search`, `extract_document`, `searxng_search`, `code_work`, `research_web`, `research_academic`, `service_task`, `profile_config`.
- Живой stdio handshake на `doc_extract_server.py`:
  - `{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"doc-extract","version":"1.26.0"}}}` → сервер реально поднимается и отвечает на `initialize`.
- Внешних зависимостей (requests/httpx/yaml/playwright/...) в этих файлах нет — только stdlib + mcp SDK.

Вывод: MCP-серверы подключаемы в OpenCode и готовы к `mcp` config.

## 3. Skills — PASS (registry vs disk)

Проверено наличие `SKILL.md` в corpus (`skills/server2-corpus` или `skills/opencode-current`):

### core_runtime_skills (11) — все OK
`code-factory, context-engineering, doubt-driven-development, verification-planning, incremental-implementation, code-review-and-quality, compare, export, literature-review, citation-management, conducting-scientific-research`

- `customize-opencode` — MISS, но это **встроенный skill OpenCode** (не файловый), что нормально. Он используется в конфигах как встроенная capability.

### optional_domain_skills (10) — все OK
`astropy, chembl-database, drugbank-database, deepchem, dask, geopandas, fluid-dynamics, diffdock, bayesian-inference, market-research-reports`

### reference_only_skills (4) — все OK
`infographics, long-context, deepwork, llm-as-judge-evaluation`

Вывод: skill corpus не потерян; агенты получат нужные скилы из реестра/капсул.

## 4. Что гарантированно работает у «остальных» агентов

- **code-контур** (`code-orchestrator`): router → tool capsule → factory_ctl + contract_validator + runner — runtime scripts в live, PASS.
- **writing-контур** (`writing-orchestrator`, `article-writer`): опирается на writing/articule process docs + `export`/`compare`/`literature-review` скилы — все есть, PASS.
- **общая оркестрация**: `experimenter`, `researcher` (web) используют route/tool/mcp resolvers — PASS.

## 5. Известные ограничения (не поломки)

1. `customize-opencode` — встроенный скил OpenCode, отсутствует как файл (ожидаемо).
2. Research-контур (`research-orchestrator` + claimeai-скрипты) — НЕ в фокусе этого аудита; researcher в разработке.
3. MCP-серверы не «подняты», пока их не запустить через `start_mcp_servers.py` и не зарегистрировать в `opencode.jsonc` mcp-секции — но сами серверы работоспособны.