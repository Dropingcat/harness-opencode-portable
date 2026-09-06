# Security Guard Integration

`doc_guard` is the required trust-boundary layer for the harness. It is not an optional audit add-on: it was designed specifically as baseline protection for the **code orchestrator** and **research orchestrator**, which are the two most injection-exposed roles because they consume web/search/document/subagent outputs and then dispatch more actions.

Policy file:

- `config/guard_policy.json`

Runtime rule:

- orchestrator + untrusted input + no guard = **BLOCK / fail closed**;
- external side effect + no guard PASS = **BLOCK**;
- unknown tool origin = **untrusted**.

## What it protects

It scans OpenCode SQLite sessions before resume/analyze and blocks hidden prompt-injection instructions from untrusted outputs:

- webfetch;
- browser fetch/search/extract;
- subagent/task output;
- `research_papers`;
- `gh_grep`;
- Composio;
- Context7;
- unknown tools, fail-closed.

## Layers

- P0: deterministic signatures, stdlib only.
- P2: semantic classifier, cloud/local fallback, majority vote.
- Budget gate before calls.
- Timeout/error → fail closed.

## Current audit result

Manual run against `tests\synth.db` succeeded: `verdict=FAIL`, 4 high findings.

The bundled test file currently has stale hardcoded `/tmp/factory-bubble/...` paths, so tests fail until path constants are made relative.

## Bundle rule

Copy code and example config only. Never copy real `guard_config.json` or API keys.

## Mandatory guard points

1. **Before resume/summary/compaction**: scan `opencode.db` before old context is reused.
2. **After untrusted tool batches**: scan after web/search/document/subagent output enters the session and before it is treated as evidence or instructions.
3. **Before orchestrator handoff**: code/research orchestrators must pass only sanitized contracts/artifacts to workers.
4. **Before side effects**: profile edits, service actions, sends, external writes and git actions need guard PASS plus confirmation if not dry-run.

## Implementation path

Short term:

- expose `DOC_GUARD_CONFIG` outside the bundle;
- expose `OPENCODE_SESSION_DB` or the actual OpenCode session DB path;
- call `guard/src/session_guard.py <db> --json` from the router/plugin before risky phases.

Plugin gate:

- `plugins/tool-skill-contract-router.ts` now includes a `tool.execute.after` hook for untrusted tools.
- It calls `session_guard.py <OPENCODE_SESSION_DB> --json` through Python.
- It blocks fail-closed if `OPENCODE_SESSION_DB`, `DOC_GUARD_ENTRYPOINT`/`OPENCODE_HARNESS_ROOT`, Python, or guard PASS is missing.

Long term:

- also wire guard at session resume/compaction hooks where OpenCode exposes the DB path;
- add deterministic router preflight so launchers refuse to run if the session guard cannot pass.
