# Harness Portable Module - self-installing bootstrap
# Windows PowerShell. Idempotent: safe to re-run.
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }
function Write-OK($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [WARN] $msg" -ForegroundColor Yellow }

# --- 1. Locate Python 3.11+ ---
Write-Step "Locating Python"
$py = $null
if ($env:PYTHON_BIN -and (Test-Path $env:PYTHON_BIN)) { $py = $env:PYTHON_BIN }
if (-not $py) {
  $cands = @(
    "$ROOT\.venv\Scripts\python.exe",
    (Get-Command python -ErrorAction SilentlyContinue).Source,
    (Get-Command py -ErrorAction SilentlyContinue).Source
  ) | Where-Object { $_ }
  foreach ($c in $cands) {
    if ($c -and (Test-Path $c)) {
      & $c -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" 2>$null
      if ($LASTEXITCODE -eq 0) { $py = $c; break }
    }
  }
}
if (-not $py) { Write-Error "Python 3.11+ not found. Install Python 3.11+ and set PYTHON_BIN." }
Write-OK "Python: $py"
& $py -c "import sys; print('  version:', sys.version.split()[0])"

# --- 2. Create venv ---
Write-Step "Creating virtualenv"
$venvPy = "$ROOT\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  & $py -m venv "$ROOT\.venv"
  if ($LASTEXITCODE -ne 0) { Write-Error "venv creation failed" }
}
Write-OK "venv: $venvPy"
$python = $venvPy

# --- 3. Install requirements ---
Write-Step "Installing requirements"
foreach ($req in @("requirements-core.txt", "requirements-capability-bundle.txt", "requirements-mcp-doc.txt")) {
  if (Test-Path "$ROOT\$req") {
    Write-Host "  pip install -r $req"
    & $python -m pip install --quiet --upgrade pip
    & $python -m pip install --quiet -r "$ROOT\$req"
    if ($LASTEXITCODE -ne 0) { Write-Warn "pip install $req had non-zero exit (continuing)" }
  }
}
Write-OK "requirements installed"

# --- 4. Build native plugin ---
Write-Step "Building native plugin"
$pkg = "$ROOT\packages\opencode-harness-plugin"
$distEntry = "$pkg\dist\index.js"
$hasNpm = Get-Command npm -ErrorAction SilentlyContinue
if ($hasNpm) {
  if (-not (Test-Path "$pkg\node_modules")) {
    Push-Location $pkg
    & npm install --no-audit --no-fund 2>&1 | Out-Null
    Pop-Location
  }
  Push-Location $pkg
  & npm run build
  $buildCode = $LASTEXITCODE
  Pop-Location
  if ($buildCode -ne 0) { Write-Error "plugin build failed (tsc)" }
} else {
  Write-Warn "npm not found; cannot rebuild plugin. Using prebuilt dist if present."
  if (-not (Test-Path $distEntry)) { Write-Error "npm missing and no dist/index.js present" }
}
Write-OK "plugin dist: $(Test-Path $distEntry)"

# --- 5. Project plugin deps (.opencode/node_modules) ---
Write-Step "Project plugin deps"
if (Test-Path "$ROOT\.opencode\package.json") {
  if (-not (Test-Path "$ROOT\.opencode\node_modules")) {
    Push-Location "$ROOT\.opencode"
    & npm install --no-audit --no-fund 2>&1 | Out-Null
    Pop-Location
  }
  Write-OK "opencode project deps ready"
}

# --- 6. Generate .opencode/opencode.json (plugin + MCP servers) ---
Write-Step "Generating project OpenCode config (.opencode/opencode.json)"
$uri = "file:///" + ($distEntry.Replace('\','/'))
$cfgPath = "$ROOT\.opencode\opencode.json"
$mcpServers = @{
  "academic_search" = @{
    command = '${PYTHON_BIN}'
    args    = @('${OPENCODE_HARNESS_ROOT}/mcp/academic_search_server.py')
    cwd     = '${OPENCODE_HARNESS_ROOT}/mcp'
  }
  "coder_router" = @{
    command = '${PYTHON_BIN}'
    args    = @('${OPENCODE_HARNESS_ROOT}/mcp/coder_router_server.py')
    cwd     = '${OPENCODE_HARNESS_ROOT}/mcp'
  }
  "searxng_search" = @{
    command = '${PYTHON_BIN}'
    args    = @('${OPENCODE_HARNESS_ROOT}/mcp/searxng_search_server.py')
    cwd     = '${OPENCODE_HARNESS_ROOT}/mcp'
  }
}
$cfg = @{
  '$schema' = "https://opencode.ai/config.json"
  "plugin"   = @($uri)
  "mcp"      = $mcpServers
}
if (Test-Path $cfgPath) {
  try { $existing = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $existing = $null }
  if ($existing) {
    $plugins = @($existing.plugin | Where-Object { $_ -notmatch "opencode-harness-plugin" })
    if ($plugins -notcontains $uri) { $plugins += $uri }
    $cfg = @{
      '$schema' = "https://opencode.ai/config.json"
      "plugin"   = @($plugins)
      "mcp"      = $mcpServers
    }
  }
}
$cfg | ConvertTo-Json -Depth 6 | Set-Content -Path $cfgPath -Encoding UTF8
# PowerShell 5.1 Set-Content -Encoding UTF8 emits a BOM; strip it for clean JSON.
$bytes = [System.IO.File]::ReadAllBytes($cfgPath)
if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
  [System.IO.File]::WriteAllBytes($cfgPath, $bytes[3..($bytes.Length-1)])
}
Write-OK "opencode.json written: plugin=$uri"

# --- 7. Recompile runtime policy snapshot ---
Write-Step "Recompiling runtime policy"
if (Test-Path "$ROOT\scripts\router\compile_runtime.py") {
  & $python "$ROOT\scripts\router\compile_runtime.py"
  if ($LASTEXITCODE -ne 0) { Write-Warn "compile_runtime returned $LASTEXITCODE" }
  else { Write-OK "runtime_snapshot.json regenerated" }
}

# --- 8. Write .env ---
Write-Step "Writing .env"
$envPath = "$ROOT\.env"
$envLines = @(
  "# Auto-generated by deploy/bootstrap.ps1 - edit freely, git-ignored",
  "OPENCODE_HARNESS_ROOT=$ROOT",
  "PYTHON_BIN=$python",
  "WRITER_PYTHON=$python",
  "OPENCODE_CONFIG_DIR=$ROOT\.opencode"
)
# --- 8a. SearXNG / optional MCP probe ---
$searxngUrl = $env:SEARXNG_URL
if (-not $searxngUrl) { $searxngUrl = "http://127.0.0.1:8888" }
$searxngOk = $false
$searxngNote = ""
if (Test-Path "$ROOT\.venv\Scripts\python.exe") {
  $probe = & $python -c @"
import urllib.request, urllib.parse, json, sys
url = r'$searxngUrl'
params = urllib.parse.urlencode({'q':'test','format':'json'})
try:
    with urllib.request.urlopen(f'{url}/search?{params}', timeout=5) as r:
        data = json.loads(r.read().decode('utf-8'))
    print('OK' if data.get('results') is not None else 'EMPTY')
except Exception as e:
    print('FAIL:' + str(e))
"@ 2>&1 | Select-Object -Last 1
  if ($probe -eq 'OK' -or $probe -eq 'EMPTY') { $searxngOk = $true; $searxngNote = $probe }
  else { $searxngNote = $probe }
}
if ($searxngOk) {
  Write-OK "SearXNG reachable at $searxngUrl ($searxngNote)"
  $envLines += "SEARXNG_URL=$searxngUrl"
} else {
  Write-Warn "SearXNG NOT reachable at $searxngUrl ($searxngNote). searxng_search MCP will be DEGRADED until a local SearXNG is running (e.g. docker run -p 8888:8080 searxng/searxng)."
  $envLines += "# SEARXNG_URL=$searxngUrl (unreachable during bootstrap; set when SearXNG is up)"
}

# --- 8b. MCP optional servers check (doc_extract deps) ---
Write-Step "MCP optional servers check"
$docExtractDeps = @("pypdfium2", "docx", "markdownify", "openpyxl")
$docOk = $true
foreach ($dep in $docExtractDeps) {
  $probe = & $python -c "import importlib.util; print('OK' if importlib.util.find_spec('$dep') else 'MISSING')" 2>&1 | Select-Object -Last 1
  if ($probe -ne 'OK') { $docOk = $false; Write-Warn "doc_extract dep missing: $dep" }
}
if ($docOk) { Write-OK "doc_extract server deps present (pypdfium2/docx/markdownify/openpyxl)" }
else { Write-Warn "doc_extract server will be DEGRADED; run: pip install -r requirements-mcp-doc.txt" }

# --- 8c. MCP server import smoke (all bundled servers must import) ---
Write-Step "MCP servers import smoke"
$mcpRoot = "$ROOT\mcp"
$servers = @("academic_search_server","coder_router_server","searxng_search_server","doc_extract_server")
$mcpAllOk = $true
foreach ($srv in $servers) {
  $probe = & $python -c "import sys; sys.path.insert(0, r'$mcpRoot'); import $srv; print('OK')" 2>&1 | Select-Object -Last 1
  if ($probe -eq 'OK') { Write-OK "  $srv import OK" } else { Write-Warn "  $srv import FAIL: $probe"; $mcpAllOk = $false }
}
$launchers = @("opencode_code_worker","opencode_research_web","opencode_research_academic","opencode_profile_configurator","opencode_service_task","opencode_tribunal_role")
foreach ($l in $launchers) {
  $probe = & $python -c "import sys; sys.path.insert(0, r'$ROOT\mcp\launchers'); import $l; print('OK')" 2>&1 | Select-Object -Last 1
  if ($probe -eq 'OK') { Write-OK "  $l import OK" } else { Write-Warn "  $l import FAIL: $probe"; $mcpAllOk = $false }
}
if (-not $mcpAllOk) { Write-Warn "Some MCP modules failed to import; check requirements and re-run bootstrap." }

Set-Content -Path $envPath -Value $envLines -Encoding UTF8
Write-OK ".env written"
# Export for the remainder of this session so doctor/health resolve vars.
$env:OPENCODE_HARNESS_ROOT = $ROOT
$env:PYTHON_BIN = $python
$env:WRITER_PYTHON = $python
$env:OPENCODE_CONFIG_DIR = "$ROOT\.opencode"

# --- 9. Doctor + health ---
Write-Step "Doctor"
$doctor = "$pkg\core\doctor.py"
if (Test-Path $doctor) {
  & $python $doctor
  Write-Host ""
}
Write-Step "Health check"
$health = "$ROOT\scripts\health_check.py"
if (Test-Path $health) {
  & $python $health
}

# --- 10. Final ---
Write-Step "DONE"
Write-Host @"

Portable Harness module ready at: $ROOT

To connect to OpenCode Desktop:
  1. Open OpenCode Desktop
  2. Open the project folder:  $ROOT
  3. The native plugin loads automatically via .opencode/opencode.json
  4. In chat use tools: harness_status, harness_run

Log marker on success:
  harness plugin loaded protocol=harness-bridge-rpc/1.0 required_features_ok=true
"@
