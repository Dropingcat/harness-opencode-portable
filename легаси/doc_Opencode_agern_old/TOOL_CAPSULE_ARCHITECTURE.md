# Tool Capsule Architecture

Tool capsule — это слой нормализации всех tools в семейства, контракты и runtime bindings, чтобы router не работал с плоским списком инструментов.

## 1. Что делает tool capsule

- группирует tools в families;
- задаёт contracts and anti-contracts;
- связывает tools с routes/capsules;
- связывает tools с MCP/launchers/scripts;
- задаёт guard relevance и side-effect policy.

## 2. Tool families

- `code-tools`
- `research-tools`
- `document-tools`
- `integration-tools`
- `guard-tools`
- `controller-tools`

## 3. Source of truth

- `config/tool_capsule_policy.json`
- `config/tool_families.json`
- `config/tool_runtime_bindings.json`
- `config/tool_graph.json`

## 4. Router interaction

Router route -> claim/bucket -> skill capsule -> tool family -> concrete tool binding.

То есть router не выбирает сначала `arxiv_search` или `code_work`, а сначала выбирает семейство, затем конкретный допустимый tool.

## 5. Invariants

- every tool belongs to at least one family;
- every family has allowed routes and guard semantics;
- side-effect tools cannot be chosen without explicit family policy;
- tool capsule stays deterministic and config-driven.
