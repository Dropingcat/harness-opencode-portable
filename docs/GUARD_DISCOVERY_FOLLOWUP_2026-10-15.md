# Guard discovery: reported parallel-session dispatch block

Source: user-reported parallel orchestrator failure on 2026-10-15. The parallel session's exact root, checkout and tool catalog were not independently inspected. Its decision to stop without a guard PASS is correct.

## Verified locally, not proof of a working guard

Both the canonical Harness and this accepting worktree contain `guard/src/session_guard.py` and `guard/src/guard_runner.py`; their factory controller and coder runner definition are present. Neither contains `scripts/doc_guard.py` or `scripts/tools/doc_guard.py`.

`config/tool_runtime_bindings.json` registers logical ID `session_guard`, provider `doc_guard`, entrypoint `guard/src/session_guard.py`. Mandatory instructions often name `doc_guard`, so provider/name/path discovery is not interchangeable with finding a script under `scripts/`. The P0 scanner binding is also not proof that the combined P0/P2 runner executed.

`guard_runner.py --help` runs, but currently describes a session/database interface. Help output and file presence do not produce an artifact guard PASS. Known fail-open composition/import-fallback and coverage gaps from the independent injection audit remain unresolved.

## Required stage-1 acceptance, not implemented here

Track under the existing open `TD-RESTORE-01`, linked to `TD-004` and `TD-013`, without creating a duplicate debt or closing the reported block:

1. One documented, discoverable logical guard contract across manifest, agent/runner instructions, CLI and native integration. Explicitly identify P0 versus required combined protection; no guessed alias or silent downgrade.
2. Cold-start preflight from a clean checkout, an approved external worktree and two parallel sessions resolves the same permitted Harness root/interpreter/entrypoint without manual filesystem searching. Record resolved identity and versions.
3. Guard accepts the actual untrusted artifact under a supported contract; an OpenCode database is not a mandatory correctness dependency for artifact admission.
4. Missing entrypoint, dependencies, unsupported input, timeout, malformed verdict, nonzero exit or unavailable required stage yields a structured BLOCK/ERROR, never PASS. No runner dispatch or source rewrite occurs after that result.
5. Healthy guard execution yields a scanner-produced receipt bound to the exact artifact bytes, policy, required stages and coverage. Only that receipt permits dispatch.
6. Reproduce the reported scenario with runner files and factory present: a missing guard blocks with an actionable diagnostic; a correctly installed and executed guard permits the bounded runner path. File presence or `--help` alone must never satisfy this test.

This follow-up changes planning/acceptance metadata only. It does not fix or certify the guard, dispatch a blocked runner, weaken fail-closed rules, or enable stages 1–8.
