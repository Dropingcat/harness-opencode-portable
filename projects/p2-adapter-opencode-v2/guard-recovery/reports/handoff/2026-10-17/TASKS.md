# Remaining tasks

See `../../NEXT_STAGE.md` for required independent gates and the host boundary.
This is a component candidate, not a completed factory run or working P2 route.

Reproduction from the isolated worktree:

```powershell
$env:OPENCODE_HARNESS_ROOT = (Get-Location).Path
$scratch = Join-Path $env:OPENCODE_HARNESS_ROOT 'projects/p2-adapter-opencode-v2/guard-recovery/runs/tmp'
New-Item -ItemType Directory -Force -Path $scratch | Out-Null
$env:TEMP = $scratch
$env:TMP = $scratch
python -m pytest -q tests/coder/test_guard_recovery.py tests/coder/test_native_classifier_recovery.py tests/coder/test_guard_artifact_stage1.py tests/coder/test_guard_core_stage1.py tests/coder/test_guard_discovery_contract_stage1.py
python scripts/tools/doc_guard.py scan --config guard/src/guard_config.json --artifact projects/p2-adapter-opencode-v2/guard-recovery/artifacts/synthetic-canary.txt --timeout 2 --json
```

The second command must exit 1 with `BLOCK / p2_not_configured`, no coverage
and no real model invocation. Do not reinterpret this negative check as PASS.
Temporary test files belong under the task's ignored `runs/`, not system temp.
