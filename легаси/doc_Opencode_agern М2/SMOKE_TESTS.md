# Smoke Tests

Run these before connecting the bundle to OpenCode runtime.

## Inventory check

```powershell
$root = "E:\Documents\Документы\doc_Opencode_agern"
Get-ChildItem -LiteralPath $root -Recurse -File | Measure-Object
Get-ChildItem -LiteralPath "$root\agents" -File -Filter *.md | Measure-Object
Get-ChildItem -LiteralPath "$root\skills\opencode-current" -Directory | Measure-Object
```

Expected pass-1 inventory was approximately:

- 123 Python files
- 446 Markdown files
- 183 skill directories
- 15 agent markdown files

## Python syntax check

```powershell
$root = "E:\Documents\Документы\doc_Opencode_agern"
python -m py_compile `
  "$root\mcp\coder_router_server.py" `
  "$root\mcp\academic_search_server.py" `
  "$root\mcp\doc_extract_server.py" `
  "$root\mcp\searxng_search_server.py" `
  "$root\guard\src\session_guard.py" `
  "$root\guard\src\semantic_layer.py" `
  "$root\guard\src\adversarial_build.py"
```

## Guard quick check

Use only synthetic or sanitized databases:

```powershell
$root = "E:\Documents\Документы\doc_Opencode_agern"
python "$root\guard\src\session_guard.py" --help
```

If using original `doc_guard` tests, fix stale hardcoded `/tmp/factory-bubble/...` paths first.

## Secret-shape check

Use a real grep tool if available:

```powershell
rg -n "sk-[A-Za-z0-9_-]{16,}|pza_[A-Za-z0-9_-]{8,}|\bck_[A-Za-z0-9_-]{12,}|x-consumer-api-key|api_key\s*[:=]" "E:\Documents\Документы\doc_Opencode_agern"
```

Expected: only placeholder keys such as `sk-your-openai-key-here` should appear. Real token-shaped values must be redacted or moved to environment variables.

## Launcher warning

Do not smoke-test `mcp/launchers/*.py` by spawning subagents until their Linux hardcoded paths are parameterized. They may currently point to `/home/orangepi` or `/tmp`.
