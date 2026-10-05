# Runtime environment bootstrap for OpenCode unified module (Windows PowerShell)
# Invoke this script through the preferred harness path (an ASCII junction is fine).
#
# SCOPE POLICY (B3-T1):
#   By default this script applies runtime variables to the CURRENT PROCESS ONLY and
#   prints a WARN for every variable that is not persisted. Nothing is written to the
#   User scope (registry) unless the flag OPENCODE_HARNESS_SETUP_USER=1 is set:
#       $env:OPENCODE_HARNESS_SETUP_USER = "1"
#   and the script is re-run. Use the flag ONLY when you intentionally want to
#   persist runtime variables machine/user-wide (deployment).

# Run: powershell -ExecutionPolicy Bypass -File scripts/setup_env.ps1
# or:  . .\scripts\setup_env.ps1

$setupUser = ($env:OPENCODE_HARNESS_SETUP_USER -eq "1")

# Set a harness runtime variable in the User scope (persisted registry) when the
# setup flag is set; otherwise apply it to the current process only and warn that
# it was not persisted.
function Set-HarnessEnvVar {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )
    if ($setupUser) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "User")
    } else {
        Set-Item -Path "Env:$Name" -Value $Value
        Write-Host "WARN: $Name not persisted (process scope only). Set OPENCODE_HARNESS_SETUP_USER=1 for User scope."
    }
}

# --- Harness root (portable-first) -------------------------------------
# If OPENCODE_HARNESS_ROOT is unset, resolve it from $PSScriptRoot (this is the
# portable root). A pre-set value (e.g. the canon root) is deliberately kept and
# never silently overwritten - a WARN is printed instead.
if ([string]::IsNullOrWhiteSpace($env:OPENCODE_HARNESS_ROOT)) {
    $HARNESS = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
} else {
    $HARNESS = $env:OPENCODE_HARNESS_ROOT
    $portableRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
    if ([System.IO.Path]::GetFullPath($HARNESS) -ne $portableRoot) {
        Write-Host "WARN: OPENCODE_HARNESS_ROOT is '$HARNESS'; run from portable or set manually."
    }
}

Set-HarnessEnvVar "OPENCODE_HARNESS_ROOT" $HARNESS
Set-HarnessEnvVar "OPENCODE_RUNS_DIR" (Join-Path $HARNESS ".runs")
Set-HarnessEnvVar "OPENCODE_CONFIG_DIR" (Join-Path $env:USERPROFILE ".config\opencode")
# OPENCODE_BIN is set after detection below (real binary, never a bare name).

# --- OPENCODE_BIN resolution -------------------------------------------
# Priority: env OPENCODE_BIN (validated) -> PATH `opencode` -> bunx cache globs.
$opencodeBin = $env:OPENCODE_BIN
if (-not [string]::IsNullOrWhiteSpace($opencodeBin) -and -not (Test-Path -LiteralPath $opencodeBin)) {
    Write-Host "WARN: OPENCODE_BIN '$opencodeBin' does not exist; re-detecting."
    $opencodeBin = $null
}
if ([string]::IsNullOrWhiteSpace($opencodeBin)) {
    $cmd = Get-Command opencode -ErrorAction SilentlyContinue
    if ($cmd) {
        $opencodeBin = $cmd.Source
    } else {
        $bunxHits = @(Get-ChildItem -Path "C:\Temp\bunx-*\node_modules\.bin\opencode.exe" -ErrorAction SilentlyContinue)
        if ($bunxHits.Count -eq 0) {
            # Fallback: bun install cache (the real bunx cache location).
            $bunxHits = @(Get-ChildItem -Path (Join-Path $env:USERPROFILE ".bun\install\cache\opencode-ai@*\bin\opencode.exe") -ErrorAction SilentlyContinue)
        }
        if ($bunxHits.Count -gt 0) {
            $opencodeBin = $bunxHits | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName
        }
    }
}
if ([string]::IsNullOrWhiteSpace($opencodeBin)) {
    Write-Host "WARN: opencode binary not found; set OPENCODE_BIN manually."
} else {
    Set-HarnessEnvVar "OPENCODE_BIN" $opencodeBin
}

Set-HarnessEnvVar "DOC_GUARD_ENTRYPOINT" (Join-Path $HARNESS "guard\src\session_guard.py")
Set-HarnessEnvVar "DOC_GUARD_RUNNER" (Join-Path $HARNESS "guard\src\guard_runner.py")
Set-HarnessEnvVar "DOC_GUARD_CONFIG" (Join-Path $env:USERPROFILE ".config\opencode\guard_config.json")
Set-HarnessEnvVar "DOC_GUARD_PROVIDER" "cloud"
Set-HarnessEnvVar "HERMES_ROOT" $HARNESS

# Native Writer Core. Runtime artifacts stay outside the source tree.
Set-HarnessEnvVar "WRITER_CORE_ROOT" (Join-Path $HARNESS "scripts\writer-core")
Set-HarnessEnvVar "WRITER_RUNS_DIR" (Join-Path $HARNESS ".runs\writer-core")
Set-HarnessEnvVar "WRITER_LINGUISTICS_REGISTRY_DIR" (Join-Path $HARNESS "scripts\writer-core\linguistic_assets")

# Изолированный Python-venv фабрики (только stdlib; см. requirements-core.txt)
$venvDir = Join-Path $HARNESS ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
if (Test-Path $venvPython) {
    Set-HarnessEnvVar "PYTHON_VENV" $venvPython
    Set-HarnessEnvVar "PYTHON" $venvPython
    Set-HarnessEnvVar "PYTHON_BIN" $venvPython
} else {
    Set-HarnessEnvVar "PYTHON" "python"
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
Set-HarnessEnvVar "WRITER_PYTHON" $writerPython

# Researcher Core (WS-19): детерминированное ядро верификации (numeric/guard/formula)
Set-HarnessEnvVar "RESEARCH_CORE_ROOT" (Join-Path $HARNESS "scripts\researcher")
Set-HarnessEnvVar "RESEARCH_VERIFY_CLAIMS" (Join-Path $HARNESS "scripts\researcher\verify_claims.py")

# P2 semantic guard key (хранится вне HARNESS, в переменной окружения, не в репо).
# Ты сказал, что есть отдельный ключ для guard. Задай его здесь ОДИН раз:
# $POLZA_GUARD_KEY = "your-separate-guard-key"
# [Environment]::SetEnvironmentVariable("POLZA_API_KEY", $POLZA_GUARD_KEY, "User")
# НЕ коммить фактический ключ; в HARNESS ключа нет и не будет.

# OPENCODE_SESSION_DB: real path to OpenCode session DB (SQLite, ~/.local/share/opencode/opencode.db)
Set-HarnessEnvVar "OPENCODE_SESSION_DB" (Join-Path $env:USERPROFILE ".local\share\opencode\opencode.db")

$researchRoot = Join-Path $HARNESS "scripts\research"
Set-HarnessEnvVar "RESEARCH_SCRIPTS_ROOT" $researchRoot
Set-HarnessEnvVar "RESEARCH_RUNNER_SH" (Join-Path $researchRoot "run_research.sh")
Set-HarnessEnvVar "RESEARCH_RULES_PATH" (Join-Path $researchRoot "rules_balanced.yaml")
Set-HarnessEnvVar "RESEARCH_NUMERIC_COMPARATOR" (Join-Path $researchRoot "numeric_comparator.py")
Set-HarnessEnvVar "RESEARCH_SYNTHESIZER" (Join-Path $researchRoot "synthesizer.py")
Set-HarnessEnvVar "RESEARCH_JUDGE_BRIEF" (Join-Path $researchRoot "judge_brief.py")
Set-HarnessEnvVar "RESEARCH_VERIFICATION_ROOT" (Join-Path $HARNESS ".runs\verification")

if ($setupUser) {
    Write-Host "Runtime env applied (User scope). Restart OpenCode to load."
} else {
    Write-Host "Runtime env applied (process scope). Set OPENCODE_HARNESS_SETUP_USER=1 for User scope."
}