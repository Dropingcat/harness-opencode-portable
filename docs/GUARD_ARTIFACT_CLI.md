# Artifact guard (stage 1)

From any directory, invoke the absolute path to `scripts/tools/doc_guard.py`:

```powershell
python C:\path\to\harness\scripts\tools\doc_guard.py preflight --config C:\private\guard_config.json --json
python C:\path\to\harness\scripts\tools\doc_guard.py scan --artifact C:\work\input.txt --config C:\private\guard_config.json --json
```

`preflight` checks root/interpreter/version/policy/code/config metadata only. Its
`READINESS` result has `ok: false`: it never certifies provider availability or
artifact admission. Exit 0 means metadata ready, not PASS.

`scan` freshly executes required P0 and P2 without a session database. Exit 0
requires `ok: true`, `PASS`, and complete P2 coverage. Missing imports, config,
providers, invalid outputs, alarms, timeouts and incomplete scans block. There is
no P0-only admission, provider command option, or trusted-receipt shortcut.

Root precedence is `--harness-root`, `OPENCODE_HARNESS_ROOT`, then the module-owned
root. An override must resolve to that same installation, with all identity
paths present; invalid overrides block, never fall back or execute another tree.
Config precedence is `--config`, `DOC_GUARD_CONFIG`, existing
`~/.config/opencode/guard_config.json`, then existing
`guard/src/guard_config.json`. Examples are never treated as real configuration.
Config content and keys are not printed or passed in subprocess argv.

Inputs are nonempty strict UTF-8, at most 65,536 bytes. Oversized input blocks
without truncation-based admission. Every actual character is scanned, including
JSON keys, nested lists, malformed JSON, and purported trusted flags. This is a
text scanner, not a JSON trust interpreter. P0 uses bundled normalization,
signatures and suspicion logic with untrusted provenance. P2 uses the bundled
`ClassifierChain(config, Budget)` and its result dictionary, not a new provider.
Contiguous Unicode-character chunks are at most 4,000 characters, with 256
characters overlap across fixed boundaries (no line splitting or omitted
middle). Coverage ranges identify the exact boundaries. This provides complete
character coverage, not an assertion of unlimited cross-chunk semantic context.

The existing configured budget is bounded to 0–5 rubles per scan (default 5).
Production P2 runs in an isolated child process with a 180-second overall limit;
timeouts terminate that process. Provider alarms fail closed even if a fallback
returns NO. This conservative policy can block otherwise valid local fallback.
No live provider is needed or contacted by preflight or fixture tests.

JSON reports include artifact SHA-256 and byte count, current policy/code hashes,
config hash, required/executed stages, coverage and reason. Artifact, config and
code/policy identity are checked again before PASS. The caller must retain and
consume those exact bytes; later edits require another scan. Editable report JSON
is evidence, not cryptographic authorization. There is no receipt-reading mode:
every CLI scan runs fresh. The API's `chain_factory` function argument is only
for offline testing and labels results `testing_only_not_host_certification`;
it is not reachable through CLI or environment. This tool does not activate
native host enforcement or certify a connected host.

Offline regression command:
`python -m unittest discover -s tests/coder -p test_guard_artifact_stage1.py -v`
