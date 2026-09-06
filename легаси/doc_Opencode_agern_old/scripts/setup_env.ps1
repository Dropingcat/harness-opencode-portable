# Runtime environment bootstrap for OpenCode unified module (Windows PowerShell)
# NOTE: harness has an ASCII junction at E:\opencode_harness -> real (cyrillic) path.
# Use the ASCII path in env to avoid console/subprocess codepage breakage.

# Run: powershell -ExecutionPolicy Bypass -File scripts/setup_env.ps1
# or:  . .\scripts\setup_env.ps1

$HARNESS = "E:\opencode_harness"

[Environment]::SetEnvironmentVariable("OPENCODE_HARNESS_ROOT", $HARNESS, "User")
[Environment]::SetEnvironmentVariable("OPENCODE_RUNS_DIR", (Join-Path $HARNESS ".runs"), "User")
[Environment]::SetEnvironmentVariable("OPENCODE_CONFIG_DIR", (Join-Path $env:USERPROFILE ".config\opencode"), "User")
[Environment]::SetEnvironmentVariable("OPENCODE_BIN", "opencode", "User")
[Environment]::SetEnvironmentVariable("DOC_GUARD_ENTRYPOINT", (Join-Path $HARNESS "guard\src\session_guard.py"), "User")
[Environment]::SetEnvironmentVariable("DOC_GUARD_RUNNER", (Join-Path $HARNESS "guard\src\guard_runner.py"), "User")
[Environment]::SetEnvironmentVariable("DOC_GUARD_CONFIG", (Join-Path $env:USERPROFILE ".config\opencode\guard_config.json"), "User")
[Environment]::SetEnvironmentVariable("DOC_GUARD_PROVIDER", "cloud", "User")
[Environment]::SetEnvironmentVariable("PYTHON", "python", "User")
[Environment]::SetEnvironmentVariable("HERMES_ROOT", $HARNESS, "User")

# P2 semantic guard key (хранится вне HARNESS, в переменной окружения, не в репо).
# Ты сказал, что есть отдельный ключ для guard. Задай его здесь ОДИН раз:
# $POLZA_GUARD_KEY = "your-separate-guard-key"
# [Environment]::SetEnvironmentVariable("POLZA_API_KEY", $POLZA_GUARD_KEY, "User")
# НЕ коммить фактический ключ; в HARNESS ключа нет и не будет.

# OPENCODE_SESSION_DB: real path to OpenCode session DB (SQLite, ~/.local/share/opencode/opencode.db)
[Environment]::SetEnvironmentVariable("OPENCODE_SESSION_DB", (Join-Path $env:USERPROFILE ".local\share\opencode\opencode.db"), "User")

$researchRoot = Join-Path $HARNESS "scripts\research"
[Environment]::SetEnvironmentVariable("RESEARCH_SCRIPTS_ROOT", $researchRoot, "User")
[Environment]::SetEnvironmentVariable("RESEARCH_RUNNER_SH", (Join-Path $researchRoot "run_research.sh"), "User")
[Environment]::SetEnvironmentVariable("RESEARCH_RULES_PATH", (Join-Path $researchRoot "rules_balanced.yaml"), "User")
[Environment]::SetEnvironmentVariable("RESEARCH_NUMERIC_COMPARATOR", (Join-Path $researchRoot "numeric_comparator.py"), "User")
[Environment]::SetEnvironmentVariable("RESEARCH_SYNTHESIZER", (Join-Path $researchRoot "synthesizer.py"), "User")
[Environment]::SetEnvironmentVariable("RESEARCH_JUDGE_BRIEF", (Join-Path $researchRoot "judge_brief.py"), "User")

Write-Host "Runtime env applied (User scope). Restart OpenCode to load."