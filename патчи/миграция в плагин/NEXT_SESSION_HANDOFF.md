# Next Session Handoff

## Read first

1. `PROJECT_STATE.md`
2. `OPENCODE_NATIVE_PLUGIN_CURRENT.md`
3. `HARNESS_OPENCODE_INTERFACE_CONTROL.md`
4. `TEST_AND_EVIDENCE_MATRIX.md`
5. `NEXT_PHASE_PLAN.md`
6. `TECH_DEBT_CURRENT.md`

## Do not regress these decisions

- legacy `plugins/tool-skill-contract-router.ts` is not production authority;
- Native Plugin is preferred Desktop transport;
- CLI is explicit fallback only;
- Core never depends on OpenCode private DB for correctness;
- OpenCode raw SDK types stop at HostAdapter;
- one generic SemanticExecutionRequest/Result serves Tribunal/Writer/Coder;
- RPB/TEX/PER remain unchanged when transport changes;
- provider fallback creates new lineage;
- semantic worker must be recursion-isolated;
- MODEL_PRIOR is not evidence;
- Defender remains a response function until live traces justify something else.

## First implementation task

Finish/verify Native Desktop P2 against the actually installed OpenCode version.

Before coding:
1. inspect installed `@opencode-ai/plugin` and SDK generated types;
2. compare exact call shapes to current HostAdapter;
3. add strict fake-host tests for those exact argument shapes;
4. install plugin cleanly;
5. capture live doctor/host snapshot.

Do not start Tribunal semantic migration until P2 passes.

## Expected artifacts from P2

- host_environment.json
- plugin_install_report.json
- host_capability_snapshot.json
- bridge_handshake.json
- doctor.json
- harness_status_result.json
- harness_run_result.json
- cancel_test.json
- plugin logs
- compatibility/opencode/<version>.json

## After P2

Proceed to read-only semantic smoke, then Tribunal plugin transport.
