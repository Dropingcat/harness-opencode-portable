# Stage-1 host boundary: source observation, not certification

Inspection target: packages/opencode-harness-plugin/src/v2/index.js at the stage-1 baseline 8297e4b. This observation does not query a running host or mutate its configuration.

The deterministic V2 adapter installs an execute.before hook that rejects a small forbidden-tool set. It registers harness_status and harness_run; semantic reverse requests remain disabled. This source is not an implementation of general artifact/output P0+P2 admission for arbitrary tools or parallel sessions.

Consequently a repaired Python guard and discoverable artifact CLI do not alone demonstrate that Desktop invokes that guard at every trust boundary. Prompt/binding changes explain a supported call path; they do not automatically register a native tool or establish host enforcement.

Release reports must distinguish:

- offline failure/coverage regression tests;
- CLI cold-start discoverability and actual artifact receipts;
- real configured classifier behavior (not established by fixtures);
- native host enforcement of dispatch admission (requires separate host evidence).

The original reported parallel session is not deemed repaired merely because this worktree's CLI starts. Full autonomy and memory injection remain blocked until their existing acceptance gates pass. Do not rewrite historical compatibility records or promote this source observation to LIVE_CERTIFIED.
