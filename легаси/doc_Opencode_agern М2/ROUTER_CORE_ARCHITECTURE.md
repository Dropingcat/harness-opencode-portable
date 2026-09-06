# Router Core Architecture

Router core — это входной deterministic слой unified orchestration module. Он принимает задачу, раскладывает её в route plan и подготавливает агенту всё необходимое до первого содержательного действия.

## 1. Router core делает

```text
task
-> detect task class
-> parse claim/task proposals
-> assign bucket/execution cell
-> select strictness profile
-> select execution mode
-> select capsules/skills/tools/MCP
-> select guard mode
-> emit route plan
```

## 2. Router core не делает

- не решает задачу вместо worker/runtime;
- не хранит authoritative state;
- не меняет graph вручную;
- не заменяет validators/guard;
- не рекламирует весь skill corpus без фильтра.

## 3. Inputs

Минимальный вход:

```json
{
  "task_text": "string",
  "hints": {
    "domain": "optional",
    "risk_class": "optional",
    "preferred_profile": "optional"
  }
}
```

## 4. Outputs

Route plan:

```json
{
  "route_id": "code-implementation",
  "bucket": "code",
  "profile": "standard",
  "execution_mode": "worker_reviewer_tester",
  "capsules": ["core-orchestration", "code"],
  "skills": ["verification-planning", "incremental-implementation", "code-factory"],
  "tools": ["code_work", "coder_run"],
  "guard_required": false,
  "start_with": ["read interfaces", "define scope in/out"],
  "finish_with": ["run tests", "record risks"],
  "reason_codes": ["BUCKET_ASSIGNED"]
}
```

## 5. Resolution order

1. `task_text` -> route by policy regex/keywords/hints
2. route -> bucket from `bucket_contracts.json`
3. route -> capsules from `skill_to_route_map.json`
4. bucket/profile -> execution mode from `execution_modes.json`
5. profile -> guard semantics from `strictness_profiles.json` + `guard_policy.json`
6. route/capsule -> skills/tools/start/finish

## 6. Core config sources

- `config/profile_routes.json`
- `config/route_resolution_policy.json`
- `config/execution_modes.json`
- `config/bucket_contracts.json`
- `config/strictness_profiles.json`
- `config/guard_policy.json`
- `config/skill_capsule_policy.json`
- `config/skill_to_route_map.json`
- `config/tool_runtime_bindings.json`
- `config/skills_graph.json`
- `config/reason_codes.json`

## 7. Stop rule

Если route ambiguity не разрешена policy/hints:

- `unknown` -> `BLOCKED` or `ESCALATED`
- не выдумывать route

## 8. Capsule-first principle

Router выбирает сначала **capsules**, а не весь corpus skills. Skills подаются через capsule binding.

Graph layer связывает capsules со skills/tools/runtime entrypoints, чтобы router отдавал не только названия, но и привязки к MCP/launchers/scripts.

## 9. Deterministic first

Первый router core должен работать без LLM:

- regex/policy/hints
- static config
- explicit reason codes

LLM route suggestion может появиться позже как advisory layer, но не как source of truth.

## 10. Hierarchical capsule binding

Current layer-level capsule resolver:

- `scripts/router/resolve_capsules.py`

It reads:

- `config/capsule_registry.json`
- `config/capsule_route_hierarchy.json`

and returns which capsules/layers are active for a given route before execution starts.
