# Full Harness — Writer + Researcher + Coder

Release date: 2026-09-13

This checkout is the integrated Harness module containing the canonical Writer, Researcher and Coder/code-factory runtimes together with the shared router, Job/Attempt runtime, capsules, policies, agents, skills, MCP launchers, tests, architecture documentation, implementation tracker and technical-debt registry.

## Start here

Run the deterministic local acceptance gates from repository root:

```bash
python scripts/run_harness_acceptance.py all
```

If the host has a production OpenCode installation, then follow:

- `REMOTE_ACCEPTANCE_README_FIRST.md`
- `REMOTE_OPENCODE_AGENT_INSTRUCTION.md`
- `REMOTE_OPENCODE_ACCEPTANCE_PROTOCOL.md`

The production semantic OpenCode trace is intentionally a separate external acceptance gate. A missing/unavailable OpenCode provider does not invalidate deterministic Writer/Researcher/Coder packaging.

## Canonical module roots

- Writer: `scripts/writer/`
- Researcher: `scripts/researcher/`
- Coder/code-factory: `scripts/code-factory/`
- Shared jobs: `scripts/jobs/`
- Shared router: `scripts/router/`
- Shared capsules: `scripts/capsules/`
- Shared orchestration: `scripts/orchestration/`
- Agent contracts: `agents/`
- Skills: `skills/`
- MCP/launchers: `mcp/`
- Authority/config: `config/`

## Governance / continuity

Read these before changing architecture:

- `IMPLEMENTATION_TRACKER.md`
- `TECH_DEBT.md`
- `config/tech_debt.json`
- `R4_DECISION_LOG.md`
- `CURRENT_ARCHITECTURE_STATE_2026-09-12.md`
- `FULL_HARNESS_ACCEPTANCE_REPORT.md`

## Important runtime rule for Coder

`factory_ctl submit worker` never treats the process current directory as an implicit Git workspace. Git snapshotting requires explicit `--workdir` or `OPENCODE_FACTORY_WORKDIR`. This prevents the code-factory from accidentally staging/committing the Harness controller repository.

## Known external gate

`existing.opencode_tribunal_role` is registered in provider authority, but production semantic validation still requires an actually available OpenCode executable/model on the deployment host. Use the remote acceptance protocol rather than weakening provider-health checks.
