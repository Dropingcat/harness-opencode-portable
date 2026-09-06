# Skills Modules

## Sources

В модуле минимум два источника skills:

1. `skills/opencode-current/`
2. `W:\server2\skills` — **184 skill modules**
3. module-owned copy: `skills/server2-corpus/` — **184 skill modules**

## Зачем нужны

Skills задают:

- semantic trigger
- procedural instructions
- tool/library recommendations
- scope / anti-scope
- fallback behavior

## Реализационное правило

Не все skills должны одинаково рекламироваться в runtime. Нужны классы:

1. `core runtime skills`
2. `optional domain skills`
3. `reference-only skills`

## Нужный registry

Поверх skill layer нужен будущий `config/skills_registry.json`:

- skill id
- source path
- category
- runtime class (`core|optional|reference`)
- related tools/MCP
- guard relevance
- smoke-test status

## Где всё теперь лежит

Чтобы не зависеть от разрозненных серверных путей во время дальнейшей разработки:

- current OpenCode corpus: `skills/opencode-current/`
- server corpus copy: `skills/server2-corpus/`
- source path map: `sources/SERVER_SOURCE_LAYOUT.md`
- capsule contracts: `SKILL_CAPSULE_ARCHITECTURE.md`, `config/skill_capsule_policy.json`, `config/skill_to_route_map.json`
- graph artifact: `SKILL_GRAPH_ARCHITECTURE.md`, `config/skills_graph.json`, `config/tool_runtime_bindings.json`

Router должен работать через capsule registry + graph artifact, а не через прямой обход raw corpus `skills/server2-corpus/`.
