# Stage 1 guard discovery

`config/tool_runtime_bindings.json` registers logical `doc_guard`, provider
`doc_guard`, at `scripts/tools/doc_guard.py`. This is source discovery metadata,
not an enabled native host tool or execution interceptor.

From any directory, invoke the absolute canonical script path:

```text
python "<ROOT>/scripts/tools/doc_guard.py" preflight --json
python "<ROOT>/scripts/tools/doc_guard.py" scan --artifact FILE --config CONFIG --json
```

Root selection: `--harness-root`, then `OPENCODE_HARNESS_ROOT`, then the scanner's
owned root. Invalid explicit selections fail closed, without fallback. Preflight
is readiness metadata, never PASS or proof of live provider availability.
Artifact scanning needs trusted provider configuration, not a session database.
Never put secrets in arguments or output. Do not run live providers without authorization.

Before gathered-context handoff the operator must obtain an actual zero-exit
successful complete P0+P2 scan and hash-bound receipt for each exact bounded UTF-8
artifact. Check artifact SHA256/byte count, config/policy/code identity,
required/executed stages and complete coverage. Rescan or validate against trusted
current inputs; editable receipt JSON alone is not cryptographic authorization.
Missing scanner/import/config/provider, timeout, malformed output, nonzero exit
even with PASS, changed artifacts, stale identities or partial scans block.
Readiness, file presence and P0-only results never substitute for combined admission.

Legacy interfaces remain distinct: `session_guard` / `guard/src/session_guard.py`
is session DB P0-only; `guard_runner` / `guard/src/guard_runner.py` composes the
legacy DB P0+P2 stages and must actually complete both. No script named
session_guard under scripts is required. Existing isolated trusted local-only
exceptions and profiles are unchanged; they do not certify combined protection.

Native host binding/enforcement remains outstanding. Prompt instructions and
policy metadata do not automatically enforce admission. No generated live agents,
runtime deployment, native plugin or controller was changed. Offline fixtures
are testing evidence only, not host certification. Full P2 network execution and
automatic downstream receipt consumption are outside this integration scope.

Focused check: `python -m unittest discover -s tests/coder -p test_guard_discovery_contract_stage1.py -v`.
