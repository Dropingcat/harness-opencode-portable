# MCP Capsule Architecture

MCP capsule is a layer normalizing all MCP servers/launchers into registry, contracts and runtime bindings. MCP is the external perimeter for tools/services.

## 1. What MCP capsule does
- groups MCP servers into families;
- defines contracts/anti-contracts;
- links MCP with routes/capsules;
- defines guard relevance and side-effect policy;
- defines health check / lifecycle.

## 2. MCP families
- search-mcp
- document-mcp
- service-mcp
- code-mcp
- research-mcp

## 3. Source of truth
- config/mcp_registry.json
- config/mcp_capsule_policy.json
- config/mcp_graph.json

## 4. Router interaction
Router route -> claim/bucket -> skill capsule -> tool family -> tool bindings -> MCP family -> concrete MCP server.

## 5. Invariants
- every MCP server belongs to at least one family;
- every family has allowed routes and guard semantics;
- side-effect MCPs cannot be chosen without explicit family policy;
- MCP capsule stays deterministic and config-driven.
