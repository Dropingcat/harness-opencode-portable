# Runtime Policy Compiler

## Назначение

Этот слой устраняет множественные независимые источники истины для route/tool/skill orchestration. Runtime больше не должен собирать политику из нескольких JSON-файлов и графа. Он читает только `config/runtime_snapshot.json`, скомпилированный из явно объявленных authoritative inputs.

## Authoritative inputs

Манифест: `config/runtime_source_manifest.json`.

Основные редактируемые источники:

- `config/routes_authority.json` — route id, regex, bucket, default profile, priority, capsules, route skills, preferred tools, guard flag, lifecycle steps и agent hint.
- `config/tool_contracts_authority.json` — динамические контракты использования tools.
- `config/bucket_contracts.json` — bucket contracts.
- `config/skill_capsule_policy.json` — capsule definitions.
- `config/strictness_profiles.json` — profiles.
- `config/execution_modes.json` — execution modes.
- `config/tool_runtime_bindings.json` — runtime bindings tools.
- `config/skills_registry.json` — skill registry.
- `config/route_resolution_policy.json`, `guard_policy.json`, `tool_capsule_policy.json` — policy sources.

## Generated artifacts

Не редактировать вручную:

- `config/runtime_snapshot.json`
- `config/skills_graph.json`
- `config/profile_routes.json`
- `config/tool_skill_routes.json`
- `config/skill_to_route_map.json`

Каждый generated view содержит `generated=true` и `generated_from_policy_hash`. Snapshot содержит SHA-256 `policy_hash` по canonical JSON всех authoritative inputs и отдельные `source_hashes`.

## Compile / check

```bash
python scripts/router/compile_runtime.py
python scripts/router/compile_runtime.py --check
```

`--check` ничего не переписывает. Он валидирует cross-references, повторно строит ожидаемые артефакты в памяти и возвращает ненулевой exit code, если generated files устарели.

Компиляция fail-closed. Сейчас проверяются как минимум: route→bucket/profile/capsule/tool/skill, capsule→route/fallback/profile/tool, bucket→profile/mode/tool, execution-mode→profile и tool-contract→runtime binding.

## Runtime contract

`scripts/router/resolve_route.py` читает только `runtime_snapshot.json`. TypeScript plugin также загружает тот же snapshot при старте. Таким образом Python router и OpenCode plugin используют один и тот же policy hash.

Graph является производным индексом/визуализацией и больше не участвует в принятии route decisions.

## Изменение route

1. Редактировать `config/routes_authority.json`.
2. При необходимости редактировать связанные authoritative configs.
3. Запустить compiler.
4. Запустить `python scripts/router/compile_runtime.py --check` и тесты.
5. Deploy/sync только после успешного check.

Нельзя исправлять generated compatibility files напрямую: следующая компиляция намеренно перезапишет такие изменения.

## Граница этапа 1

Этот этап централизует policy compilation и устраняет route-policy drift. Он не заменяет следующий архитектурный этап `Attempt + GateSet + State Reducer` и пока не вводит artifact-level provenance model.
