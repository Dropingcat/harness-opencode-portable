param(
    [string]$HarnessRoot = "C:\Temp\opencode\harness-deploy",
    [string]$Version = "1.18.30",
    [switch]$PersistUserEnv
)

$ErrorActionPreference = "Stop"

function Invoke-Capture {
    param([string]$Exe,[string[]]$Args)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    foreach ($a in $Args) { [void]$psi.ArgumentList.Add($a) }
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()
    $stdout = $p.StandardOutput.ReadToEnd()
    $stderr = $p.StandardError.ReadToEnd()
    $p.WaitForExit()
    [pscustomobject]@{
        exit_code = $p.ExitCode
        stdout = $stdout.Trim()
        stderr = $stderr.Trim()
    }
}

$HarnessRoot = [IO.Path]::GetFullPath($HarnessRoot)
if (-not (Test-Path $HarnessRoot)) { throw "Harness root not found: $HarnessRoot" }

$node = Get-Command node -ErrorAction Stop
$npm = Get-Command npm -ErrorAction Stop
$ToolRoot = Join-Path $HarnessRoot ".tools\opencode-cli-$Version"
New-Item -ItemType Directory -Force -Path $ToolRoot | Out-Null

Write-Host "Installing pinned OpenCode CLI $Version into $ToolRoot"
& $npm.Source install --prefix $ToolRoot --include=optional "opencode-ai@$Version"
if ($LASTEXITCODE -ne 0) { throw "npm install failed with exit code $LASTEXITCODE" }

$candidatePaths = @(
    (Join-Path $ToolRoot "node_modules\opencode-ai\bin\opencode.exe"),
    (Join-Path $ToolRoot "node_modules\opencode-windows-x64\bin\opencode.exe"),
    (Join-Path $ToolRoot "node_modules\opencode-windows-x64-baseline\bin\opencode.exe")
)

$extra = Get-ChildItem -Path (Join-Path $ToolRoot "node_modules") -Recurse -Filter "opencode.exe" -File -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty FullName
$candidatePaths += $extra
$candidatePaths = $candidatePaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

if (-not $candidatePaths) { throw "No opencode.exe found under $ToolRoot" }

$probes = @()
$selected = $null
foreach ($candidate in $candidatePaths) {
    try {
        $probe = Invoke-Capture -Exe $candidate -Args @("--version")
        $probes += [pscustomobject]@{
            path = $candidate; exit_code = $probe.exit_code
            stdout = $probe.stdout; stderr = $probe.stderr
        }
        if (-not $selected -and $probe.exit_code -eq 0 -and $probe.stdout -match [regex]::Escape($Version)) {
            $selected = $candidate
        }
    } catch {
        $probes += [pscustomobject]@{
            path = $candidate; exit_code = -1; stdout = ""; stderr = $_.Exception.Message
        }
    }
}

if (-not $selected) {
    throw "No native OpenCode executable reported expected version $Version."
}

$versionProbe = Invoke-Capture -Exe $selected -Args @("--version")
$helpProbe = Invoke-Capture -Exe $selected -Args @("--help")
$runHelpProbe = Invoke-Capture -Exe $selected -Args @("run","--help")
if ($versionProbe.exit_code -ne 0) { throw "opencode --version failed" }
if ($helpProbe.exit_code -ne 0) { throw "opencode --help failed" }
if ($runHelpProbe.exit_code -ne 0) { throw "opencode run --help failed" }

$env:OPENCODE_BIN = $selected
if ($PersistUserEnv) {
    [Environment]::SetEnvironmentVariable("OPENCODE_BIN", $selected, "User")
}

$sha = (Get-FileHash -Algorithm SHA256 -Path $selected).Hash.ToLowerInvariant()
$status = [ordered]@{
    schema = "harness-opencode-cli-install/1.0"
    harness_root = $HarnessRoot
    requested_version = $Version
    node = (& $node.Source --version).Trim()
    npm = (& $npm.Source --version).Trim()
    tool_root = $ToolRoot
    selected_executable = $selected
    executable_sha256 = $sha
    opencode_version = $versionProbe.stdout
    help_ok = ($helpProbe.exit_code -eq 0)
    run_help_ok = ($runHelpProbe.exit_code -eq 0)
    persisted_user_env = [bool]$PersistUserEnv
    candidates = $probes
}
$statusPath = Join-Path $HarnessRoot "opencode_cli_install_status.json"
$status | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $statusPath

Write-Host ""
Write-Host "OpenCode CLI is ready."
Write-Host "  OPENCODE_BIN = $selected"
Write-Host "  version      = $($versionProbe.stdout)"
Write-Host "  SHA256       = $sha"
Write-Host "  report       = $statusPath"
Write-Host ""
Write-Host "Next:"
Write-Host '  & $env:OPENCODE_BIN --version'
Write-Host '  & $env:OPENCODE_BIN models'
Write-Host "  rerun Harness remote acceptance T00-T06/T07"
