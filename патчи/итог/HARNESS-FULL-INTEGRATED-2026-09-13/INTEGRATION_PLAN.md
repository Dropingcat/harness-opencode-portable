# Integration Plan

## Wave 0: documentation and safe bundle

- [x] Create `doc_Opencode_agern`.
- [x] Add architecture, registry and source map.
- [x] Copy safe MCP server source files.
- [x] Copy doc_guard source without private config.
- [x] Copy current OpenCode agents and skills into bundle.
- [x] Align code-factory principles with researcher-core architecture from `E:\барахло\Documents\Default Project`.
- [ ] Add install scripts and config templates.
- [ ] Add smoke tests for copied MCP servers on target machine.

## Wave 1: current Windows OpenCode alignment

1. Compare current config:
   - `C:\Users\Arhys\.config\opencode\opencode.jsonc`
   - `C:\Users\Arhys\.config\opencode\.opencode\.mcp.json`
2. Import the real factory runtime from `W:\server2` into live Windows OpenCode:
   - `shared/code-factory-process.md`
   - `scripts/code-factory/factory_ctl.py`
   - `scripts/code-factory/contract_validator.py`
   - `scripts/code-factory/code_factory_runner.py`
3. Add only non-conflicting MCP/tools first:
   - academic search;
   - doc extraction;
   - SearXNG only if backend exists;
   - coder router only after path/model adaptation for Windows.
4. Do not copy secrets. Use env vars.
5. Smoke-test every server/script standalone before connecting.

Also treat `W:\server2\skills` as a primary migration source for the skill layer. It currently contains 184 skill modules and should be classified into core runtime / optional domain / reference-only before advertisement in live OpenCode.

Module-owned copy now lives in `skills/server2-corpus/`; continue integration against that local copy, not against scattered server paths.

Skill routing should use the generated graph artifact `config/skills_graph.json` and deterministic builder `scripts/router/build_skill_graph.py`, not direct ad hoc scans over the raw corpus.

Critical mismatch: many copied launcher contracts and controller docs contain Linux paths such as `/home/orangepi/...`, and `factory_ctl.py` defaults to `/tmp/factory_state.json`. Before runtime use on Windows, add a path abstraction/config layer. Do not run these launchers/controllers unchanged on Windows.

## Wave 2: guard-first runtime safety

1. Port `doc_guard/src/session_guard.py` and `semantic_layer.py`.
2. Fix tests to use relative paths.
3. Add a wrapper/pre-resume checklist:
   - scan `opencode.db`;
   - fail closed on `FAIL`;
   - ask user whether to proceed if ambiguous.

## Wave 3: skill/router consolidation

1. Make one `router.md` or `AGENTS.md` fragment with routing table.
2. Keep current custom skills as source of truth when duplicated.
3. OMO skills are patterns, not automatic runtime owner.
4. OpenWorkers pattern becomes evidence-audit backend.

## Wave D: router hooks + prepared contracts/templates

1. Add router hooks so the agent sees the route **before** acting:
   - `experimental.chat.system.transform` → context route + start/finish steps;
   - `tool.definition` → dynamic contract per tool;
   - `tool.execute.before` → payload shape preflight;
   - `tool.execute.after` → guard + output-shape postflight.
2. For every skill/tool/MCP, define:
   - `use_when` / `do_not_use_when`;
   - `required_input` / `optional_input` / `forbidden_input`;
   - `start_with` / `finish_with`;
   - `guard_required`.
3. Add machine-readable templates so functions are not fed oversized or wrong-domain payloads.
4. Make router fail closed when payload does not fit the template.
5. Ensure the agent is "led by the hand": what to load first, what tool to call next, what output is expected, what closes the task.

Artifacts for this wave:

- `ROUTER_HOOKS_AND_TEMPLATES.md`
- `config/tool_skill_templates.json`
- `plugins/tool-skill-contract-router.ts`

## Wave 4: plugin packaging

Target package shape:

```text
opencode-harness/
├── package.json
├── src/server.ts
├── skills/
├── mcp/
├── guard/
├── config.schema.json
└── README.md
```

This step should happen only after the Python MCP bundle passes smoke tests.
