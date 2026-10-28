# Run and inspect the pilot

Run commands from `E:\opencode_harness_portable\projects\knowledge-reuse-pilot`.
`run.ps1` uses the existing Harness Python interpreter and redirects writable
runtime locations into this project. It does not alter global configuration.

## Start with existing work

```powershell
.\run.ps1 lookup 'nitrogen diffusion'
.\run.ps1 trace 'F:\1\_STRUCTURED\VERIFICATION_REPORT.md'
.\run.ps1 graph 'source'
```

Lookup returns one result per observed content hash (with bounded duplicate
locations), source fragments, current coverage and an action. Candidates are not
automatically accepted results. `REUSE` requires explicit matching coverage and
current input/output hashes. `REVALIDATE` exposes changed or missing dependencies.
`INDEX_INCOMPLETE` is not permission to claim that the corpus has no evidence.

## Incremental maintenance

```powershell
.\run.ps1 scan
.\run.ps1 refresh
.\run.ps1 export
```

- `scan`: inventory all approved roots; extract new content; reuse existing blob
  extraction. Unsupported, oversized, OCR-needed, truncated and failed inputs
  remain visible in coverage. ZIP files are inventoried, NOT recursively unpacked.
- `refresh`: re-sanitize cached text and rebuild explicit links without parsing
  PDFs/documents again. Use after an importer/redaction update.
- `export`: derive Graphify JSON and wiki links; identical output is not rewritten.

Never start a competing full scan while one is already running. The current
bootstrap scan is tracked in `PROGRESS.md`; wait for its completion notification.

## Local processing and request-triggered search startup

```powershell
.\run.ps1 run table_profile --path 'F:\1\data.csv' --question 'Describe this dataset' --max-rows 1000 --wait 30
.\run.ps1 run project_context --wait 30
.\run.ps1 run web_search --question 'nitrogen diffusion' --wait 95
.\run.ps1 run network_probe --url 'https://raw.githubusercontent.com/reconurge/flowsint/main/README.md' --wait 30 --retry
```

Identical inputs/method/parameters reuse the job/result. The worker records local
table outputs as drafts with source hashes. It does not certify scientific
interpretations, infer units, or promote them to L3.

The installed search backend is `mini_searxng.py`, NOT full SearXNG. It may return
partial/irrelevant results; engine availability is not relevance certification.
The next search request starts the existing backend if it is down. Downloader is
never invoked as an automatic fallback.

Flowsint's real service is currently missing. `network_probe` distinguishes this
from search readiness. A transport probe is NOT execution of `website_to_text`.
That upstream method has not been modified or pretended to run.

## Register an existing report deliberately

```powershell
.\run.ps1 register 'F:\1\path\report.md' --input 'F:\1\path\primary.pdf' --coverage 'Exact question covered by this report' --status draft
```

Accepted status additionally requires `--confirm-acceptance`. This records an
authorized declaration, not an independent fact-check. Do not approve reports
because they are recent or have `final` in their names. Input hashes and the
artifact hash are rechecked before reuse.

## MCP

Open this pilot directory as the OpenCode project. Its own
`.opencode/opencode.json` registers `knowledge_pilot`; parent/global config is not
edited. Direct stdio MCP behavior is checked by:

```powershell
.\run.ps1 smoke
.\run.ps1 test
```

Default tools: `knowledge_lookup`, `knowledge_trace`, `knowledge_read`,
`knowledge_graph`, `knowledge_start`, `knowledge_job`.

`knowledge_start` accepts only the listed pipelines; no arbitrary Python/shell.
Use the job's bounded `wait_seconds` rather than an agent-generated polling loop.
Registration through MCP is hidden/disabled unless the operator explicitly sets
`PILOT_ALLOW_REGISTER=1`; accepted declarations still require confirmation.

## Limits and privacy

- Indexing performs no model/API extraction and sends no corpus to an LLM.
  Requested MCP fragments ARE returned to the calling agent; its model may be remote.
- Secret filenames and obvious credential patterns are filtered; this is not a
  universal secret detector. Do not broaden the roots to credentials directories.
- Only already-exported sessions inside the approved corpus are indexed. The
  live OpenCode database and files on C: are not imported or modified.
- Historical hashes/links are preserved, but historical ORIGINAL bytes are not
  magically recovered. Use the source archive/Git for unavailable versions.
- Graphify is a genuine graph reader here, not a new semantic/AST rebuild of the
  corpus. Communities in this graph are explicit corpus scopes.
- No integration into the dirty primary Harness router or global agent prompts
  is claimed. The pilot's `AGENTS.md` supplies its own reuse-first contract.
