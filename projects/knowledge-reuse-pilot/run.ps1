param([Parameter(ValueFromRemainingArguments=$true)][string[]]$PilotArguments)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:GRAPHIFY_NO_AUTO_REFRESH = '1'
foreach ($name in 'tmp','cache','logs','artifacts') {
  New-Item -ItemType Directory -Path (Join-Path $root $name) -Force | Out-Null
}
$env:TEMP = Join-Path $root 'tmp'
$env:TMP = $env:TEMP
$env:TMPDIR = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $root 'cache\pip'
$env:UV_CACHE_DIR = Join-Path $root 'cache\uv'
$env:XDG_CACHE_HOME = Join-Path $root 'cache'
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'E:\opencode_harness_portable\.venv\Scripts\python.exe' }
Push-Location $root
try {
  & $python -B (Join-Path $root 'pilot.py') @PilotArguments
  $code = $LASTEXITCODE
} finally { Pop-Location }
exit $code
