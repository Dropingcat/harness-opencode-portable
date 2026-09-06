# Skill Capsule Architecture

Цель: сделать **тонкую капсулу skills**, к которой можно пришивать skill-модули постепенно, не переписывая router core.

## 1. Что такое capsule

Skill capsule = не папка со всеми skills подряд, а контрактный слой:

- inventory
- classification
- advertisement policy
- route bindings
- tool/MCP bindings
- guard relevance
- fallback behavior

Router работает не с россыпью `SKILL.md`, а с capsule registry.

## 2. Capsule boundary

Router знает только:

- `capsule_id`
- `runtime_class`
- `provided_skills`
- `supported_routes`
- `related_tools`
- `guard_profile`

Router **не должен** парсить 184 skills каждый раз при route resolution.

## 3. Capsule types

### core-orchestration
- routing/process/verification/review/export/context

### code
- code-factory, incremental implementation, code review, deepwork, clonedeps

### research
- literature review, citation management, conducting scientific research, hypothesis generation

### integration-config
- customize-opencode, context-engineering, profile/config migration

### writing
- export, article writing, scientific writing

### domain capsules
- chemistry/bio/physics/data/ML/etc. подключаются отдельно

## 4. Capsule contract

```json
{
  "capsule_id": "research-core",
  "runtime_class": "core",
  "provided_skills": ["literature-review", "citation-management"],
  "supported_routes": ["academic-research", "claim-validation"],
  "related_tools": ["arxiv_search", "openalex_search", "extract_document"],
  "guard_profile": "strict",
  "advertise_by_default": true,
  "fallback_capsule": "core-orchestration"
}
```

## 5. Capsule lifecycle

```text
discovered from source
-> normalized in registry
-> classified into capsule
-> bound to routes/tools/guard
-> optionally advertised in runtime
```

## 6. Design rule

Сначала стабилизируем capsule contracts.

Потом skills можно добавлять модульно:

- один skill
- группа skills
- целый доменный capsule

без переделки router core.

## 7. Source of truth

- `config/skills_registry.json`
- `config/skill_capsule_policy.json`
- `config/skill_to_route_map.json`
- `config/tool_runtime_bindings.json`
- `config/skills_graph.json`

Документация:

- `SKILLS_MODULES.md`
- `UNIFIED_MODULE_SCOPE.md`
- `ROUTER_HOOKS_AND_TEMPLATES.md`
- `SKILL_GRAPH_ARCHITECTURE.md`
