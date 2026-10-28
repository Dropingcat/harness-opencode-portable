# Module map

| Module | Owns |
|---|---|
| `pilot.py`, `run.ps1` | CLI and project-local process environment |
| `knowledge_pilot/runtime.py` | Fixed writable home, TEMP/TMP/cache paths, trusted config |
| `knowledge_pilot/catalog.py` | Read-only corpus traversal, file/blob cache, FTS, coverage |
| `knowledge_pilot/extract.py` | Bounded local PDF/DOCX/XLSX/text/ZIP-inventory extraction |
| `knowledge_pilot/linking.py` | Explicit file/URL refs and hash-matched download provenance |
| `knowledge_pilot/reuse.py` | Declared scope/status, input versions and reuse eligibility |
| `knowledge_pilot/jobs.py` | Durable single-flight jobs, cancellation and dead-owner detection |
| `knowledge_pilot/local_analysis.py` | Local descriptive CSV/TSV profiling, no model calls |
| `knowledge_pilot/network.py` | Existing mini-search startup, health and transport diagnostics |
| `knowledge_pilot/projection.py` | Same-catalog Graphify graph and deterministic wiki links |
| `knowledge_pilot/service.py` | Fixed pipelines, read-only canonical thread context adapter |
| `mcp_server.py` | Project-scoped bounded MCP interface |
| `graphify_server.py` | Actual pinned Graphify native MCP reader; no global installer |
| `verify_mcp.py` | Live protocol, unchanged-input and repeated-result evidence |
| `tests/` | Temporary-tree behavioral/regression tests |

## Authorities

Original corpus files and existing Harness registries remain authoritative.
The catalog, extracted text, graph and wiki are rebuildable projections. A link
extracted from a report is NOT evidence that the report's claim is correct.
Git recency, filenames and similarity never imply accepted status.

## Runtime data (not source files)

- `state/catalog.sqlite`: indexed identities/content, links, declared registrations.
- `state/jobs.sqlite`: requests, fingerprints, progress, persisted results.
- `state/thread_context.json`: read-only snapshot from canonical helper functions.
- `artifacts/results/`: explicitly registered draft outputs, content-addressed.
- `artifacts/`: test/platform/MCP/coverage evidence.
- `graphify-out/graph.json`, `wiki/`: derived navigation, no new narrative reports.
- `vendor/`: hash-pinned Graphify reader distribution, no global packages.
- `tmp/`, `cache/`, `logs/`: pilot-owned scratch, package cache and diagnostics.
