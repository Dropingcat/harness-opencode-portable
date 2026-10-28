# Restoration status

## Running and independently verified

- Canonical project: `E:\opencode_harness_portable`.
- Desktop 2.0.29 reports `harness.native.v2.deterministic` active. Configured target is the directory `packages/opencode-harness-plugin/dist-v2/v2`, not its `index.js` file.
- Deterministic `harness_status` / `harness_run` adapter installed; actual canonical Core smoke passed. Native model-driven tool invocation was not performed.
- Three owned observe-only daemons: `code-orchestrator`, `research-orchestrator`, `writing-orchestrator`. Identity, advancing heartbeat and duplicate-start rejection independently verified. Logs and startup diagnostics are under canonical `.meta_state/`.
- Four MCP transports connected: `academic_search`, `coder_router`, `doc_extract`, `searxng_search`. Connection is not certification of every tool or model-backed call.
- Worktree and canonical project defaults select `openai/gpt-6.1-sol`; active OpenAI OAuth observed. Quota is not verified; no separately billed API calls made by this restoration.
- Final canonical `health_check.py` returned HEALTHY / exit 0, corroborated separately by the active-plugin API and connected-MCP inventory. The accepted legacy `plugin` configuration alias is retained because the existing doctor only reads that spelling; Desktop normalizes it to the native plugin list. This is not a substitute for runtime verification.

## Gates and limitations

Daemon scoped tests: 23/23; subscription routing: 4/4; V2 contract suite: 9 cases against source and built entrypoint, plus real Core smoke. Independent live observer checks: 8 PASS; independent live native checks: PASS. All three implementation reviews APPROVE; process audit approves only the bounded observer stage. Coverage unmeasured. Seven broader Windows health-fixture failures reproduced at baseline `dc83907` remain documented.

The requested **full autonomous restoration is BLOCKED**, not DONE. `TD-RESTORE-01` requires certified V2 semantic execution, content guard/permissions, real task-observation ingestion and an independent verifier of genuine merge/test evidence. No repair executor or auto-merge was enabled; no production simulated recovery cycle was run. Persistent daemon startup is not reboot-autostart certification.

Factory `HARNESS-RESTORE-20261014`: narrow required gates reached PASSED, then explicit auditor block recorded for the remaining full-autonomy scope. One actual rework, two attempts; no tribunal required; no provenance errors. State: `.runs/harness-restore-20261014/factory_state.json`.

Backups, detailed test reports, baseline failure reproduction, guarded audit/loader evidence and deployed hashes remain under `.runs/harness-restore-20261014/`. Unrelated dirty canonical work was neither reverted nor committed.
