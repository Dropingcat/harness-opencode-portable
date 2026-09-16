#!/usr/bin/env bash
# Harness Portable Module - self-installing bootstrap (Linux/macOS)
# Idempotent: safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

step() { echo ""; echo "=== $1 ==="; }
ok() { echo "  [OK] $1"; }
warn() { echo "  [WARN] $1"; }

# --- 1. Locate Python 3.11+ ---
step "Locating Python"
PY="${PYTHON_BIN:-}"
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  for cand in "$ROOT/.venv/bin/python" "$(command -v python3 || true)" "$(command -v python || true)"; do
    if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c 'import sys; exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  done
fi
if [ -z "$PY" ]; then echo "Python 3.11+ not found"; exit 1; fi
ok "Python: $PY"
"$PY" -c 'import sys; print("  version:", sys.version.split()[0])'

# --- 2. venv ---
step "Creating virtualenv"
VENV_PY="$ROOT/.venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
  "$PY" -m venv "$ROOT/.venv"
fi
PYTHON="$VENV_PY"
ok "venv: $PYTHON"

# --- 3. requirements ---
step "Installing requirements"
for req in requirements-core.txt requirements-capability-bundle.txt requirements-mcp-doc.txt; do
  if [ -f "$ROOT/$req" ]; then
    "$PYTHON" -m pip install --quiet --upgrade pip || true
    "$PYTHON" -m pip install --quiet -r "$ROOT/$req" || warn "pip install $req exit=$?"
  fi
done
ok "requirements installed"

# --- 4. Build native plugin ---
step "Building native plugin"
PKG="$ROOT/packages/opencode-harness-plugin"
DIST_ENTRY="$PKG/dist/index.js"
if command -v npm >/dev/null 2>&1; then
  if [ ! -d "$PKG/node_modules" ]; then
    (cd "$PKG" && npm install --no-audit --no-fund >/dev/null 2>&1 || true)
  fi
  (cd "$PKG" && npm run build) || { echo "plugin build failed"; exit 1; }
else
  warn "npm not found; using prebuilt dist if present"
  [ -f "$DIST_ENTRY" ] || { echo "npm missing and no dist/index.js"; exit 1; }
fi
ok "plugin dist present: $([ -f "$DIST_ENTRY" ] && echo yes || echo no)"

# --- 5. Project plugin deps ---
step "Project plugin deps"
if [ -f "$ROOT/.opencode/package.json" ] && [ ! -d "$ROOT/.opencode/node_modules" ]; then
  (cd "$ROOT/.opencode" && npm install --no-audit --no-fund >/dev/null 2>&1 || true)
fi

# --- 6. Generate project OpenCode config (plugin + MCP) ---
step "Generating project OpenCode config (.opencode/opencode.json)"
URI="file://${DIST_ENTRY}"
CFG_PATH="$ROOT/.opencode/opencode.json"
python3 - "$URI" "$CFG_PATH" <<'PY'
import json, sys, os
uri, cfg_path = sys.argv[1], sys.argv[2]
cfg = {}
if os.path.exists(cfg_path):
    try: cfg = json.load(open(cfg_path, encoding="utf-8"))
    except Exception: cfg = {}
plugins = cfg.get("plugin", []) if isinstance(cfg, dict) else []
plugins = [p for p in plugins if "opencode-harness-plugin" not in str(p)]
if uri not in plugins: plugins.append(uri)
mcp = {
    "academic_search": {
        "command": "${PYTHON_BIN}",
        "args": ["${OPENCODE_HARNESS_ROOT}/mcp/academic_search_server.py"],
        "cwd": "${OPENCODE_HARNESS_ROOT}/mcp",
    },
    "coder_router": {
        "command": "${PYTHON_BIN}",
        "args": ["${OPENCODE_HARNESS_ROOT}/mcp/coder_router_server.py"],
        "cwd": "${OPENCODE_HARNESS_ROOT}/mcp",
    },
    "searxng_search": {
        "command": "${PYTHON_BIN}",
        "args": ["${OPENCODE_HARNESS_ROOT}/mcp/searxng_search_server.py"],
        "cwd": "${OPENCODE_HARNESS_ROOT}/mcp",
    },
}
cfg = {"$schema": "https://opencode.ai/config.json", "plugin": plugins, "mcp": mcp}
os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("  opencode.json written; plugin:", uri)
PY

# --- 7. Recompile runtime policy ---
step "Recompiling runtime policy"
if [ -f "$ROOT/scripts/router/compile_runtime.py" ]; then
  "$PYTHON" "$ROOT/scripts/router/compile_runtime.py" || warn "compile_runtime exit=$?"
fi

# --- 8. .env ---
step "Writing .env"
SEARXNG_URL="${SEARXNG_URL:-http://127.0.0.1:8888}"
SEARXNG_OK="no"
if "$PYTHON" -c "import urllib.request,urllib.parse,json,sys; u='$SEARXNG_URL'; p=urllib.parse.urlencode({'q':'test','format':'json'}); \
  d=json.loads(urllib.request.urlopen(f'{u}/search?{p}',timeout=5).read().decode()); print('OK' if d.get('results') is not None else 'EMPTY')" 2>/dev/null | grep -qE '^(OK|EMPTY)$'; then
  SEARXNG_OK="yes"
  ok "SearXNG reachable at $SEARXNG_URL"
else
  warn "SearXNG NOT reachable at $SEARXNG_URL. searxng_search MCP will be DEGRADED until a local SearXNG runs (e.g. docker run -p 8888:8080 searxng/searxng)."
fi

# --- 8b. Optional MCP servers check (doc_extract deps) ---
step "MCP optional servers check"
DOC_OK="yes"
for dep in pypdfium2 docx markdownify openpyxl; do
  if ! "$PYTHON" -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('$dep') else 1)" 2>/dev/null; then
    DOC_OK="no"; warn "doc_extract dep missing: $dep"
  fi
done
[ "$DOC_OK" = "yes" ] && ok "doc_extract server deps present" || warn "doc_extract server DEGRADED; run: pip install -r requirements-mcp-doc.txt"

# --- 8c. MCP server import smoke ---
step "MCP servers import smoke"
MCP_OK="yes"
for srv in academic_search_server coder_router_server searxng_search_server doc_extract_server; do
  if "$PYTHON" -c "import sys; sys.path.insert(0, '$ROOT/mcp'); import $srv" 2>/dev/null; then ok "  $srv import OK"; else MCP_OK="no"; warn "  $srv import FAIL"; fi
done
for l in opencode_code_worker opencode_research_web opencode_research_academic opencode_profile_configurator opencode_service_task opencode_tribunal_role; do
  if "$PYTHON" -c "import sys; sys.path.insert(0, '$ROOT/mcp/launchers'); import $l" 2>/dev/null; then ok "  $l import OK"; else MCP_OK="no"; warn "  $l import FAIL"; fi
done
[ "$MCP_OK" = "yes" ] || warn "Some MCP modules failed to import; check requirements and re-run bootstrap."

cat > "$ROOT/.env" <<EOF
# Auto-generated by deploy/bootstrap.sh - edit freely, git-ignored
OPENCODE_HARNESS_ROOT=$ROOT
PYTHON_BIN=$PYTHON
WRITER_PYTHON=$PYTHON
OPENCODE_CONFIG_DIR=$ROOT/.opencode
EOF
if [ "$SEARXNG_OK" = "yes" ]; then
  echo "SEARXNG_URL=$SEARXNG_URL" >> "$ROOT/.env"
else
  echo "# SEARXNG_URL=$SEARXNG_URL (unreachable during bootstrap; set when SearXNG is up)" >> "$ROOT/.env"
fi
ok ".env written"
export OPENCODE_HARNESS_ROOT="$ROOT"
export PYTHON_BIN="$PYTHON"
export WRITER_PYTHON="$PYTHON"
export OPENCODE_CONFIG_DIR="$ROOT/.opencode"

# --- 9. Doctor + health ---
step "Doctor"
[ -f "$PKG/core/doctor.py" ] && "$PYTHON" "$PKG/core/doctor.py" || true
echo ""
step "Health check"
if [ -f "$ROOT/scripts/health_check.py" ]; then
  "$PYTHON" "$ROOT/scripts/health_check.py" || true
fi

# --- 10. Final ---
step "DONE"
cat <<EOF

Portable Harness module ready at: $ROOT

To connect to OpenCode Desktop:
  1. Open OpenCode Desktop
  2. Open the project folder:  $ROOT
  3. The native plugin loads automatically via .opencode/opencode.json
  4. In chat use tools: harness_status, harness_run

Log marker on success:
  harness plugin loaded protocol=harness-bridge-rpc/1.0 required_features_ok=true
EOF
