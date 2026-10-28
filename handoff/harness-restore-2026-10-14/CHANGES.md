# Changes

- Saved the worktree's pre-restoration OpenCode configuration as baseline `dc83907`.
- Initialized a separate factory state with reviewer, tester and auditor gates and two-rework limit.
- Backed up worktree/global/deployment configuration and existing deployment meta-state.
- Recorded the bounded restoration contract; dispatched independent audit mapping, V2 connection investigation and daemon-safety implementation.

Implementation, activation and verification results will be recorded when the respective gates complete. Existing MCP processes were not killed or duplicated.

## Accepted implementation and activation

- Daemon safety: removed fabricated default audit observations and fake merge recovery, added independent verification gate, owned lifecycle locks/identity, persistent startup/output logs. Review APPROVE; independent 23/23 scoped tests PASS.
- Subscription routing: worktree defaults use the discovered active OpenAI OAuth model. Review APPROVE; independent 4/4 tests PASS. Quota remains unverified.
- Separate deterministic Desktop V2 adapter: V1 preserved; semantic execution absent. Review APPROVE; independent source/built/negative-path suites and real local Core smoke PASS.
- Process auditor approved bounded observe-only restoration only; full autonomous repair remains BLOCKED by `TD-RESTORE-01`.
- Hash-conflict checks passed before deploying three meta files and the isolated V2 build to the canonical installation. No blanket synchronization or canonical commit was performed.
- Canonical project config was minimally updated to the subscription model and the separate V2 plugin target; four MCP definitions preserved.
- Three persistent observe-only Meta-Cycle daemons were started, one for each orchestrator. They have no certified repair executor or observations feed.
- User explicitly approved a global configuration reload. It completed and all four MCP servers reconnected, but the configured Harness plugin was still absent from runtime inventory. This is not represented as successful native activation; loader diagnosis is a remaining integration gate.

### Native loader resolution

The remaining loader cause was established from guarded installed Desktop 2.0.29 source: configured local **file** plugin targets are omitted before module loading. A configured directory target is required. Replacing only the Harness URI with `file:///E:/opencode_harness_portable/packages/opencode-harness-plugin/dist-v2/v2` resolved to the identical reviewed `index.js`; normal file watching loaded it without a second global reload.

The running API now reports `harness.native.v2.deterministic` **active**, source `E:\opencode_harness_portable\packages\opencode-harness-plugin\dist-v2\v2\index.js`. All four MCP servers remain connected. Direct deterministic smoke also passed against the actual canonical Core. Native activation is not certification of model-driven tool invocation, semantic execution, full content guard or autonomous repair.

The final config retains the supported legacy `plugin` alias instead of native `plugins` because the existing doctor recognizes only the former. Both normalize identically in Desktop. After this compatibility-only adjustment, canonical health check returned HEALTHY / exit 0 and runtime independently still reported the V2 plugin active and four MCPs connected.

## Rollback

Private originals and pre-deployment hashes are in `.runs/harness-restore-20261014/backups/`; deployed hashes are in `deployed-hashes.json` beside it. Restore only matching reviewed files and configuration, never the entire dirty canonical tree. Stop only daemon PIDs whose current process identity and stored token match this deployment; do not terminate arbitrary Python/MCP processes. Removing an unverified runtime file does not authorize changing HP or inventing merge history.
