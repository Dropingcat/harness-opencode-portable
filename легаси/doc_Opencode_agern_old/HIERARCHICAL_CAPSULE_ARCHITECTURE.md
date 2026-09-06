# Hierarchical Capsule Architecture

Цель: собрать все капсулы в **иерархическую вложенную систему**, где маршрутизация идёт по слоям, а не одним плоским списком.

## 1. Слои

```text
incoming task
-> router core
-> claim routing
-> capsule routing
-> execution cell
-> audit graph
-> memory projection
```

## 2. Типы капсул

- `core` — базовые orchestration/policy/guard/runtime слои
- `skill` — semantic/domain capability capsules
- `audit` — source-of-truth graph and snapshot layer
- `memory` — L1/L2/L3 projections over audit graph
- `tool` — normalized tool contracts and tool families
- `mcp` — external perimeter capsules

## 3. Иерархия

```text
system
├─ core-orchestration
│  ├─ router-core
│  ├─ claim-routing
│  ├─ guard-policy
│  └─ execution-modes
├─ skills
│  ├─ core-orchestration
│  ├─ code
│  ├─ research-core
│  ├─ integration-config
│  └─ writing
├─ audit
│  └─ audit-graph
├─ memory
│  └─ graph-driven-memory
├─ tools
│  └─ tool-runtime-bindings
└─ mcp
   └─ mcp-perimeter
```

## 4. Router on layers

Router не прыгает сразу к tool. Он делает последовательность:

1. route class
2. claim split
3. bucket
4. capsules for bucket/profile
5. tool/mcp bindings for chosen capsules
6. guard requirement
7. execution plan

## 5. Интеграционное правило

Каждая новая капсула должна добавлять:

- architecture doc
- registry entry
- policy/config entry
- graph/hierarchy binding
- deterministic script or contract
- tracker workstream

Иначе это не капсула, а очередной разрозненный слой.

## 6. Порядок разработки капсул

1. `skill capsule` — уже есть
2. `audit capsule` — уже есть
3. `memory capsule` — уже есть
4. `tool capsule` — следующий
5. `mcp capsule` — после tool capsule
6. `live integration capsule` — после стабилизации tool/mcp

## 7. Definition of integrated capsule

Капсула считается интегрированной, если:

- есть запись в `capsule_registry.json`
- есть связи в `capsule_route_hierarchy.json`
- router может использовать её без прямого знания внутренностей
- source-of-truth files задокументированы в README/MANIFEST
