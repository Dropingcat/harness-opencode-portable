# Runtime environment bootstrap for OpenCode unified module (Windows PowerShell)
# Invoke this script through the preferred harness path (an ASCII junction is fine).

# Run: powershell -ExecutionPolicy Bypass -File scripts/setup_env.ps1
# or:  . .\scripts\setup_env.ps1

if ([string]::IsNullOrWhiteSpace($env:OPENCODE_HARNESS_ROOT)) {
    $HARNESS = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
} else {
    $HARNESS = $env:OPENCODE_HARNESS_ROOT
}

[Environment]::SetEnvironmentVariable("OPENCODE_HARNESS_ROOT", $HARNESS, "User")
[Environment]::SetEnvironmentVariable("OPENCODE_RUNS_DIR", (Join-Path $HARNESS ".runs"), "User")
[Environment]::SetEnvironmentVariable("OPENCODE_CONFIG_DIR", (Join-Path $env:USERPROFILE ".config\opencode"), "User")
[Environment]::SetEnvironmentVariable("OPENCODE_BIN", "opencode", "User")
[Environment]::SetEnvironmentVariable("DOC_GUARD_ENTRYPOINT", (Join-Path $HARNESS "guard\src\session_guard.py"), "User")
[Environment]::SetEnvironmentVariable("DOC_GUARD_RUNNER", (Join-Path $HARNESS "guard\src\guard_runner.py"), "User")
[Environment]::SetEnvironmentVariable("DOC_GUARD_CONFIG", (Join-Path $env:USERPROFILE ".config\opencode\guard_config.json"), "User")
[Environment]::SetEnvironmentVariable("DOC_GUARD_PROVIDER", "cloud", "User")
[Environment]::SetEnvironmentVariable("HERMES_ROOT", $HARNESS, "User")

# Native Writer Core. Runtime artifacts stay outside the source tree.
[Environment]::SetEnvironmentVariable("WRITER_CORE_ROOT", (Join-Path $HARNESS "scripts\writer-core"), "User")
[Environment]::SetEnvironmentVariable("WRITER_RUNS_DIR", (Join-Path $HARNESS ".runs\writer-core"), "User")
[Environment]::SetEnvironmentVariable("WRITER_LINGUISTICS_REGISTRY_DIR", (Join-Path $HARNESS "scripts\writer-core\linguistic_assets"), "User")

# Изолированный Python-venv фабрики (только stdlib; см. requirements-core.txt)
$venvDir = Join-Path $HARNESS ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (Test-Path $venvPython) {
    [Environment]::SetEnvironmentVariable("PYTHON_VENV", $venvPython, "User")
    [Environment]::SetEnvironmentVariable("PYTHON", $venvPython, "User")
    [Environment]::SetEnvironmentVariable("PYTHON_BIN", $venvPython, "User")
} else {
    [Environment]::SetEnvironmentVariable("PYTHON", "python", "User")
    Write-Host "WARN: venv not found at $venvPython; falling back to PATH 'python'"
}

# Writer Core may require dependencies not installed in the harness venv. Keep an
# explicitly configured interpreter; otherwise use a local writer venv when one
# exists and fall back visibly to the general Python interpreter.
$configuredWriterPython = $env:WRITER_PYTHON
$localWriterPython = Join-Path $HARNESS "scripts\writer-core\.venv\Scripts\python.exe"
if (-not [string]::IsNullOrWhiteSpace($configuredWriterPython)) {
    $writerPython = $configuredWriterPython
    if ([System.IO.Path]::IsPathRooted($writerPython) -and -not (Test-Path $writerPython)) {
        Write-Host "WARN: configured WRITER_PYTHON not found at $writerPython; Writer Core preflight will be degraded"
    }
} elseif (Test-Path $localWriterPython) {
    $writerPython = $localWriterPython
} elseif (Test-Path $venvPython) {
    $writerPython = $venvPython
    Write-Host "WARN: no dedicated Writer Core venv found; using harness venv and relying on preflight dependency checks"
} else {
    $writerPython = "python"
    Write-Host "WARN: no Writer Core venv found; falling back to PATH 'python' and relying on preflight dependency checks"
}
$env:WRITER_PYTHON = $writerPython
[Environment]::SetEnvironmentVariable("WRITER_PYTHON", $writerPython, "User")

# Researcher Core (WS-19): детерминированное ядро верификации (numeric/guard/formula)
[Environment]::SetEnvironmentVariable("RESEARCH_CORE_ROOT", (Join-Path $HARNESS "scripts\researcher"), "User")
[Environment]::SetEnvironmentVariable("RESEARCH_VERIFY_CLAIMS", (Join-Path $HARNESS "scripts\researcher\verify_claims.py"), "User")

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
[Environment]::SetEnvironmentVariable("RESEARCH_VERIFICATION_ROOT", (Join-Path $HARNESS ".runs\verification"), "User")

Write-Host "Runtime env applied (User scope). Restart OpenCode to load."
