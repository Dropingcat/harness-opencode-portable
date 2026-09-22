# Skill Graph Architecture

Skill capsule становится по-настоящему удобной для router core, когда skills/capsules/routes/tools описаны не только списками, но и **knowledge graph**.

## 1. Зачем graph layer

Router должен быстро отвечать:

- какие capsules подходят для route;
- какие skills они дают;
- какие tools/MCP связаны с ними;
- какой guard/profile нужен;
- какие fallback связи есть;
- какие модули подключены, а какие reference-only.

Graph удобен, потому что это relations, а не только плоские таблицы.

## 2. Node types

- `route`
- `bucket`
- `capsule`
- `skill`
- `tool`
- `profile`

## 3. Edge types

- `ROUTES_TO` : route -> bucket
- `USES_CAPSULE` : route -> capsule
- `STARTS_WITH` : route -> start-step
- `FINISHES_WITH` : route -> finish-step
- `PROVIDES_SKILL` : capsule -> skill
- `USES_TOOL` : capsule -> tool
- `DEFAULT_PROFILE` : route/bucket/capsule -> profile
- `FALLBACK_TO` : capsule -> capsule
- `CLASSIFIED_AS` : skill -> runtime_class

## 4. Source of truth

Graph не редактируется вручную. Он строится детерминированно из:

- `config/skills_registry.json`
- `config/skill_capsule_policy.json`
- `config/skill_to_route_map.json`
- `config/profile_routes.json`
- `config/bucket_contracts.json`
- `config/strictness_profiles.json`

## 5. Router contract with graph

Router не обязан принимать решения по произвольному текстовому графу. Он использует graph artifact для:

- lookup connected capsules
- lookup connected skills
- lookup connected tools
- verify that chosen route has a valid capsule path

## 6. Minimal graph artifact

```json
{
  "version": 1,
  "nodes": [...],
  "edges": [...],
  "indexes": {
    "routes": {...},
    "capsules": {...},
    "skills": {...}
  }
}
```

## 7. Design rule

Graph layer должна помогать router-у, а не заменять policy engine.

- policy decides
- graph connects
- router resolves

## 8. Outcome

После этого skill capsule становится удобной прослойкой:

```text
skills corpus -> registry -> capsules -> skill graph -> router core -> route plan -> runtime
```
