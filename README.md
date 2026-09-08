# doc_Opencode_agern

Единый переносимый harness для OpenCode: роутер, MCP-серверы, skills, guard-слой, память, документация и правила интеграции.

Цель папки: собрать всё, что уже было найдено в старых профилях/серверах, в один bundle, который можно быстро перенести на новую машину и подключить к OpenCode без повторного археологического поиска.

## Статус

Создан стартовый bundle. На первом проходе перенесены только безопасные артефакты без секретов:

- registry документов и источников;
- архитектура Router → Delegate → OpenCode/MCP;
- capability/routing table;
- стартовый набор MCP-серверов из `Z:\server\.hermes\mcp`;
- doc_guard как обязательный safety gate, но без приватного `guard_config.json`.

Pass 1 уже содержит копии текущих агентов и skills из `C:\Users\Arhys\.config\opencode`, выбранные MCP из `Z:\server\.hermes\mcp`, guard source/docs из `doc_guard`, и ключевые reference-документы из `doc_hermes_pi`.

Важно: это пока **архивно-интеграционный bundle**, не готовый npm-плагин. Следующий этап — config templates, smoke tests и адаптация Linux-путей.

## Next documents

- `MANIFEST.md` — pass-1 inventory and exclusion policy.
- `PORTABILITY.md` — environment variables and hardcoded path migration notes.
- `SMOKE_TESTS.md` — lightweight checks before runtime connection.
 - `TOOL_SKILL_CONTRACT_AUDIT.md` — coverage check for MCP input schemas, skill hooks, and dynamic contracts.
- `ROUTER_HOOKS_AND_TEMPLATES.md` — router hooks, start/finish workflows, and valid payload templates for skills/tools/MCP.
- `ROUTER_CORE_ARCHITECTURE.md` — deterministic router core as source-of-truth entry layer.
- `config/tool_skill_routes.json` — machine-readable context → skills → tools → contract registry.
- `config/tool_skill_templates.json` — machine-readable input templates to prevent wrong payload shape.
- `config/profile_routes.json` — route-to-bucket/profile matching.
- `config/route_resolution_policy.json` — ambiguity and fallback policy.
- `config/execution_modes.json` — execution mode registry.
- `config/tool_runtime_bindings.json` — tool -> mcp/launcher/script entrypoints.
- `config/guard_policy.json` — mandatory fail-closed doc_guard policy for orchestrators/untrusted outputs.
- `config/strictness_profiles.json` — soft/standard/strict execution profiles.
- `config/bucket_contracts.json` — bucket execution-cell contracts.
 - `config/claim_state_machine.json` — unified claim/task lifecycle states.
 - `config/claim_kinds.json` — deterministic claim kind taxonomy.
 - `config/claim_bucket_rules.json` — kind-to-bucket and priority rules.
 - `config/skills_registry.json` — first-pass skills classification registry.
 - `config/skills_graph.json` — generated graph artifact for routes/capsules/skills/tools/runtime.
- `config/tech_debt.json` — machine-readable debt register.
- `config/reason_codes.json` — stable machine reason codes for transitions/policy/guard.
- `plugins/tool-skill-contract-router.ts` — OpenCode hook for injecting routing/contracts and running mandatory `doc_guard` after untrusted tools.
- `UNIFIED_ORCHESTRATION_PRINCIPLES.md` — общие принципы researcher-core и code-factory; разная строгость, но одна архитектура.
- `UNIFIED_MODULE_SCOPE.md` — полный scope модуля: память, policy, guard, env, MCP, skills, controllers.
- `MEMORY_POLICY.md` — advisory memory subsystem rules.
- `SKILLS_MODULES.md` — skill layer как first-class subsystem; источник `W:\server2\skills` (184 skills).
- `SKILL_CAPSULE_ARCHITECTURE.md` — thin capsule, к которой skills пришиваются модульно.
- `SKILL_GRAPH_ARCHITECTURE.md` — graph layer для capsules/routes/skills/tools/runtime bindings.
 - `CLAIM_ROUTING_ARCHITECTURE.md` — task to split claims to grouped execution plan layer.
 - `IMPLEMENTATION_TRACKER.md` — workstreams корректной реализации unified module.
- `PRECONTINUATION_WEAKNESS_AUDIT.md` — дополнительный аудит слабых мест и blockers перед продолжением разработки.
- `AGENT_ARCHITECTURE_PLAN_VS_FACT.md` — сверка планировавшейся архитектуры (15 агентов) против live факта.
- `RUNTIME_RUNBOOK.md` — последовательность запуска модуля и known gaps.
- `scripts/setup_env.ps1` / `scripts/setup_env.sh` — bootstrap runtime env.
- `RUNTIME_HEALTH_AUDIT.md` — фактическая проверка роутеров, MCP и скилов (не-researcher контуры).
- `RESEARCH_TOOLING_CAPSULE_IMPLEMENTATION_PLAN.md` — сверенный с текущими модулями план SearXNG, academic source resolution, PDF/Office/TIFF inspection, local corpus, evidence и checkpoint capsules.
- `SKILL_ADDING_CHEATSHEET.md` — официальный способ добавить skill (скрипт `scripts/add_skill.py`).
- `AGENT_SKILLS_RECONCILIATION.md` — сверка agent-скилов с корпусом (gap: ai-slop-avoidance → заменён `deslop-ai-lint-skill`).
- `SCRIPT_SCATTER_MAP.md` — карта разброса скриптов/модулей по машине и принцип единого source of truth.
- `sources/SERVER_SOURCE_LAYOUT.md` — **READ-ONLY архивные источники**; всё сконсолидировано в HARNESS (включая `guard/docs/`).

## Принцип сборки

Не ставим чужие плагины целиком, если они конфликтуют с текущей фабрикой. Заимствуем:

1. инструменты;
2. skills/playbooks;
3. routing rules;
4. контракты делегирования;
5. deterministic gates.

Главный invariant:

> LLM свидетельствует, код решает.

## Структура

```text
doc_Opencode_agern/
├── CLAIM_ROUTING_ARCHITECTURE.md
├── README.md
├── ARCHITECTURE.md
├── CAPABILITY_REGISTRY.md
├── INTEGRATION_PLAN.md
├── SECURITY_GUARD.md
├── sources/
│   └── SOURCE_MAP.md
├── mcp/
│   ├── README.md
│   ├── coder_router_server.py
│   ├── academic_search_server.py
│   ├── doc_extract_server.py
│   ├── searxng_search_server.py
│   └── launchers/
│       ├── README.md
│       ├── _runner.py
│       ├── opencode_code_worker.py
│       ├── opencode_research_web.py
│       ├── opencode_research_academic.py
│       ├── opencode_service_task.py
│       └── opencode_profile_configurator.py
├── shared/
│   └── code-factory-process.md
├── scripts/
│   └── code-factory/
│       ├── factory_ctl.py
│       ├── contract_validator.py
│       └── code_factory_runner.py
├── skills/
│   ├── README.md
│   ├── opencode-current/
│   └── server2-corpus/
├── guard/
│   └── README.md
├── CODER_DESIGN_PRINCIPLES.md
├── TRIZ_FOR_CODERS.md
├── TECH_DEBT.md
├── GLOBAL_TASK_CONTROLLER.md
├── audit_graph/
│   ├── README.md
│   ├── config/
│   │   ├── audit_graph_schema.json
│   │   └── task_audit_template.json
│   └── src/
│       └── audit_graph/
├── config/
│   ├── claim_kinds.json
│   ├── claim_bucket_rules.json
│   ├── tool_skill_routes.json
│   ├── guard_policy.json
│   ├── strictness_profiles.json
│   ├── claim_state_machine.json
│   ├── bucket_contracts.json
│   ├── skills_registry.json
│   ├── skill_capsule_policy.json
│   ├── skill_to_route_map.json
│   ├── profile_routes.json
│   ├── route_resolution_policy.json
│   ├── execution_modes.json
│   ├── tool_runtime_bindings.json
│   ├── skills_graph.json
│   ├── reason_codes.json
│   └── tech_debt.json
├── scripts/
│   ├── code-factory/
│   ├── router/
│   │   ├── resolve_route.py
│   │   ├── build_skill_graph.py
│   │   ├── split_claims.py
│   │   └── build_task_plan.py
│   └── memory/
│       ├── collect_l2.py
│       └── promote_l2_to_l3.py
└── plugins/
    └── tool-skill-contract-router.ts
```

## Что не переносить

- `.env` файлы;
- API keys;
- реальные пользовательские сессии целиком;
- приватные профили без редактирования;
- `node_modules` как есть, кроме manifest/идей;
- `oh-my-opencode-slim` runtime целиком без отдельной совместимости.
