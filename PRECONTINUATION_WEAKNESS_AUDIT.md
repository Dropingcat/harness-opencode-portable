# Pre-Continuation Weakness Audit

Reviewed scope:

- `README.md`
- `MANIFEST.md`
- `INTEGRATION_PLAN.md`
- `CAPABILITY_REGISTRY.md`
- `COMPARISON_CODE_ORCHESTRATOR.md`
- `TECH_DEBT.md`
- `IMPLEMENTATION_TRACKER.md`
- `config/tool_skill_routes.json`
- `config/tool_skill_templates.json`
- `config/guard_policy.json`
- `W:\server2\shared\code-factory-process.md`
- `W:\server2\scripts\code-factory\factory_ctl.py`
- `W:\server2\scripts\code-factory\contract_validator.py`
- `W:\server2\scripts\code-factory\code_factory_runner.py`
- `E:\барахло\Documents\Default Project\03-r0-core-contracts.md`
- `E:\барахло\Documents\Default Project\05-claim-validation-pipeline.md`
- `E:\барахло\Documents\Default Project\06-runtime-orchestration.md`
- `E:\барахло\Documents\Default Project\12-policy-config-and-heuristics.md`

## Findings

### 1. resolved in bundle / still pending for live integration — Runtime core previously existed only as references
- **Target:** `INTEGRATION_PLAN.md`, `IMPLEMENTATION_TRACKER.md`, live `C:\Users\Arhys\.config\opencode\scripts\code-factory\`
- **Trigger:** user tries to run `code-orchestrator` from live OpenCode or tries to treat the bundle as a working module.
- **Evidence:** this was true before the current step. The bundle now owns `shared/code-factory-process.md`, `scripts/code-factory/factory_ctl.py`, `scripts/code-factory/contract_validator.py`, `scripts/code-factory/code_factory_runner.py`, and passed `py_compile`, `factory_ctl --help`, `init -> status`. Live Windows OpenCode still has empty `shared/` and `scripts/code-factory/`.
- **Impact:** bundle-level blocker is removed; live integration blocker remains.
- **Smallest complete fix:** next, switch live OpenCode to the module-owned runtime or copy/symlink it into live config paths with env-driven wiring.

### 2. major / partially mitigated — Policy layer now exists in config, but is not yet fully runtime-governed at researcher-core parity
- **Target:** `IMPLEMENTATION_TRACKER.md`, `UNIFIED_ORCHESTRATION_PRINCIPLES.md`, `config/`
- **Trigger:** development continues and thresholds/strictness/rework/noAgents decisions are implemented ad hoc in docs or plugin code.
- **Evidence:** base files now exist: `strictness_profiles.json`, `bucket_contracts.json`, `claim_state_machine.json`, `skills_registry.json`, `tech_debt.json`. However, `plugins/tool-skill-contract-router.ts` still embeds overlapping runtime constants, and guard degradation / reason-code calibration are not fully bound to these configs.
- **Impact:** big improvement over docs-only state, but source-of-truth drift is still possible until runtime loads these configs directly.
- **Smallest complete fix:** make plugin/runtime read the config files directly and complete guard/reason-code calibration.

### 3. major — Router knowledge is duplicated across docs, JSON, and plugin code
- **Target:** `config/tool_skill_routes.json`, `config/tool_skill_templates.json`, `plugins/tool-skill-contract-router.ts`, `ROUTER_HOOKS_AND_TEMPLATES.md`
- **Trigger:** one route/tool/skill contract changes in one place but not the others.
- **Evidence:** routes and tool contracts exist in JSON, while the plugin embeds overlapping route/tool logic in TypeScript; docs repeat the same semantics in prose.
- **Impact:** high risk of configuration drift; agent may see one contract while runtime enforces another.
- **Smallest complete fix:** make the plugin load machine-readable JSON registries, keep prose docs descriptive only, and add a validation script that checks registry ↔ plugin coverage.

### 4. major — Skills layer is inventoried but not yet normalized into runtime classes
- **Target:** `SKILLS_MODULES.md`, `IMPLEMENTATION_TRACKER.md`, `W:\server2\skills`
- **Trigger:** advertising or auto-loading server skills into runtime without classification.
- **Evidence:** `W:\server2\skills` contains 184 skills, but there is no `skills_registry.json` yet and no deterministic classification into `core|optional|reference`.
- **Impact:** OpenCode may get a noisy or unstable skill surface, increasing routing ambiguity, context bloat, and accidental tool misuse.
- **Smallest complete fix:** generate `config/skills_registry.json` first, then advertise only core runtime skills by default.

### 5. major — Memory policy exists only as narrative, not runtime-bound metadata
- **Target:** `MEMORY_POLICY.md`, `agents/*.md`, `IMPLEMENTATION_TRACKER.md`
- **Trigger:** future work starts writing memory lessons without a schema or enforcement path.
- **Evidence:** memory rules and lesson template are documented, but there is no registry/schema, no storage contract, and no link from memory writes to policy version or guard/audit evidence.
- **Impact:** memory can regress into hidden state or vague anecdotal guidance, violating the researcher-core pattern of typed authoritative state and explicit advisory layers.
- **Smallest complete fix:** add machine-readable memory lesson schema and tie memory writes to reason codes / evidence refs / policy hash.

### 6. major / partially mitigated — Guard is conceptually mandatory and now has profile matrix, but runtime dependency wiring is still incomplete
- **Target:** `SECURITY_GUARD.md`, `config/guard_policy.json`, `plugins/tool-skill-contract-router.ts`
- **Trigger:** runtime is connected on a machine where `DOC_GUARD_ENTRYPOINT`, `OPENCODE_SESSION_DB`, or P2 config are missing.
- **Evidence:** `strictness_profiles.json` now contains guard degradation rules and `guard_policy.json` now binds profiles to guard modes with stable reason codes. However, runtime still does not load/deploy these rules automatically in live OpenCode.
- **Impact:** policy ambiguity is reduced, but deployment ambiguity remains until plugin/runtime read these files directly.
- **Smallest complete fix:** wire plugin/runtime to read the config files and enforce them at execution time.

### 7. minor — Bundle inventory metadata is already stale after the recent expansion
- **Target:** `MANIFEST.md`
- **Trigger:** using manifest counts and runtime-critical list as current truth.
- **Evidence:** summary still reports the earlier pass-1 counts and does not reflect the newly added documents and future `shared/` / `scripts/` ownership.
- **Impact:** low runtime risk, but it weakens trust in the module as a controlled artifact and makes migration reviews noisier.
- **Smallest complete fix:** regenerate manifest counts and extend runtime-critical inventory after each documentation/runtime wave.

### 8. minor — README structure/index is becoming dense enough to need a documentation controller section, not just a flat list
- **Target:** `README.md`
- **Trigger:** new contributors try to understand where memory/policy/guard/skills/controllers live.
- **Evidence:** the Next documents block is now a growing flat list with mixed indentation and without grouping by subsystem.
- **Impact:** onboarding friction and increased risk of duplicate docs or missed source-of-truth files.
- **Smallest complete fix:** regroup README index by subsystem: runtime, policy, guard, skills, orchestration, migration, references.

## Summary

NO BLOCKING FINDINGS against the architectural direction itself.

The runtime-core blocker is closed at bundle level, and the machine-readable policy base now exists. The main remaining risk is **drift between config, plugin constants, and prose docs**, plus incomplete calibration of strictness/guard semantics.
