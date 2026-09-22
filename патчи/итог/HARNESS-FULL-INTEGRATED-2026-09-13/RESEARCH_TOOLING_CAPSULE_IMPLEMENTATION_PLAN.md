# Research Tooling Capsule Implementation Plan

Date: 2026-09-08.

Status: implementation plan; no runtime capability is enabled by this document.

## 1. Goal

Turn the existing search, document, local-corpus, evidence, and agent-dispatch
stubs into a bounded research toolchain for `research-orchestrator`,
`source-fetcher`, `writing-orchestrator`, and `article-writer`.

The target path is:

```text
task
-> capability preflight
-> local corpus first
-> SearXNG or academic discovery
-> canonical source resolution
-> document/scientific-file inspection
-> exact evidence spans
-> fact-checker + deterministic verdict normalization
-> Writer DOM / research handoff
-> checkpointed completion
```

The governing invariant remains:

> Search results and extracted documents are observations, not verdicts. LLMs
> propose; deterministic contracts validate and persist.

## 2. Scope

In scope:

- local SearXNG as a discovery backend;
- direct academic APIs and canonical source resolution;
- PDF, Word, Excel, TIFF/SEM/EDS inspection;
- incremental local-corpus indexing and exact retrieval;
- evidence and verdict handoff contracts;
- capability preflight, checkpointing, retry, and code acceptance;
- tool/MCP capsule registration, routing, guard, and runtime health checks.

Out of scope:

- bypassing paywalls, anti-bot controls, or publisher access policy;
- treating search snippets, OCR text, or vision output as primary evidence;
- advertising optional capabilities before standalone and live smoke tests pass;
- adding a new agent where an existing agent plus a bounded tool is sufficient;
- placing heavyweight scientific dependencies in the core runtime environment.

## 3. Current Module Reconciliation

The proposed architecture is not greenfield. The table below reconciles it
with current HARNESS documentation and code.

| Component | Current source of truth | Fact as of 2026-09-08 | Gap to close |
|---|---|---|---|
| SearXNG discovery | `mcp/searxng_search_server.py`, `config/mcp_registry.json` | MCP wrapper exists and defaults to `127.0.0.1:8888` | No module-owned deployment, backend liveness test, cache, normalized provenance envelope, or verified live registration |
| Academic discovery | `mcp/academic_search_server.py` | arXiv and OpenAlex clients exist | No Crossref, Unpaywall, canonical DOI resolver, retry/backoff policy, or common result schema |
| Document extraction | `mcp/doc_extract_server.py`, `requirements-mcp-doc.txt` | PDF/DOC/DOCX/HTML/XLSX extractor exists but is disabled in lifecycle config | Dependencies are absent; output is flattened Markdown without page/cell/span provenance; no OCR or TIFF support |
| Local corpus | `scripts/researcher/researcher_core/local_corpus.py` | Read-only JSONL capsule exists and has tests | Linear scan only; no index builder, hashes, incremental refresh, FTS5, duplicate groups, or document extraction bridge |
| Evidence verification | `scripts/researcher/researcher_core/`, `scripts/researcher/verify_claims.py` | Deterministic numeric/guard/formula core and Writer DOM bridge exist | Search/extraction does not yet feed a strict evidence bundle; verdict provenance and controlled vocabulary are not enforced end to end |
| Writer traceability | `shared/writer-traceability-contract.md`, `scripts/writer/*` | DOM, draft loop, and citation trace exist | Traceability PASS is not evidence-validity PASS; `writer-core`/`writer-review` are not mandatory in the live handoff |
| Tool capsules | `TOOL_CAPSULE_ARCHITECTURE.md`, `config/tool_*` | Registry and resolver exist; capsule registry marks tool bindings active | Tracker and hierarchy bindings are stale/incomplete; richer contracts and anti-contracts remain open |
| MCP capsules | `MCP_CAPSULE_ARCHITECTURE.md`, `config/mcp_*` | Registry, policy, graph, and lifecycle definitions exist | Capsule registry still marks `mcp-perimeter` planned; health checks are disabled; live OpenCode wiring is unverified |
| Runtime lifecycle | `RUNTIME_RUNBOOK.md`, `scripts/start_mcp_servers.py` | stdio definitions can be validated | Runbook says `start`; script deliberately rejects `start` because lifecycle is host-managed |
| Capability checks | `scripts/validate_env.py`, `scripts/health_check.py` | Paths, plugin definition, guard, DB, and MCP syntax can be checked | No dependency/backend/end-to-end capability report for PDF/OCR/Office/TIFF/search |
| Dispatch/checkpoint | `shared/dispatch-retry.md`, code-factory state, audit graph | Retry guidance and code state machinery exist | Research retry assumes no file side effects; no research job manifest, artifact recovery, or task-id/contract validation |
| Code acceptance | `shared/code-factory-process.md`, code agents | Worker/reviewer/tester/auditor roles exist | Writing/research orchestrators can bypass the factory and call a coder without independent review and testing |

Documentation conflicts to resolve during Slice 0:

1. `CAPABILITY_REGISTRY.md` says servers are copied, while some surrounding
   documents read as if the capabilities are live.
2. `config/mcp_lifecycle_config.json` marks SearXNG `auto_start`, but no backend
   health check proves that SearXNG itself exists.
3. `RUNTIME_RUNBOOK.md` instructs `start_mcp_servers.py start`; the command exits
   with code 2 and tells the MCP host to manage stdio servers.
4. `config/runtime_integration_policy.json` requests MCP auto-start and includes
   disabled `doc_extract`; its plugin path also uses the obsolete
   `doc_Opencode_agern` location instead of the canonical harness root.
5. `HIERARCHICAL_CAPSULE_ARCHITECTURE.md`, `IMPLEMENTATION_TRACKER.md`, and
   `config/capsule_registry.json` disagree about tool/MCP capsule status.
6. The `academic-research` route in `config/capsule_route_hierarchy.json` does
   not include `tool-runtime-bindings` or `mcp-perimeter`, although its policies
   require academic and document MCP tools.

## 4. Capsule Boundary

Do not build one large research MCP. Keep bounded capabilities behind shared
envelopes and route them through the existing tool and MCP capsule layers.

Planned capability IDs:

| Capability | Responsibility | Side effects |
|---|---|---|
| `capability.preflight` | Report what is actually executable in this environment | none |
| `search.discovery` | Discover candidate web documents via SearXNG | read-only network |
| `literature.search_academic` | Discover scholarly works through direct APIs | read-only network |
| `source.resolve` | Resolve DOI, canonical citation, OA locations, correction/retraction metadata | read-only network/cache |
| `document.inspect` | Extract provenance-preserving PDF/Office/HTML structure | read-only input, cache output |
| `scientific_image.inspect` | Inspect TIFF/SEM/EDS frames, tags, previews, and plot metadata | read-only input, cache output |
| `corpus.index` | Incrementally index extracted local artifacts | local bounded writes |
| `evidence.bundle` | Bind exact source excerpts and locators to claim IDs | local bounded writes |
| `job.checkpoint` | Persist stage, hashes, artifacts, and resume state | local bounded writes |
| `code.acceptance` | Run independent test/review acceptance on isolated fixtures | worktree/run-dir writes |

Every external or extracted payload remains untrusted and passes `doc_guard`
before it can influence orchestration. A guard PASS does not imply scientific
support.

## 5. Common Contracts

### 5.1 Discovery result

```json
{
  "schema": "search-discovery/1.0",
  "query_id": "SEARCH-001",
  "backend": "searxng",
  "query": "...",
  "retrieved_at": "...",
  "results": [
    {
      "title": "...",
      "url": "...",
      "engine": "...",
      "snippet": "...",
      "rank": 1,
      "discovery_only": true
    }
  ]
}
```

Search snippets must never populate `claims[].evidence`.

### 5.2 Inspected document record

```json
{
  "schema": "document-inspection/1.0",
  "source_path": "...",
  "sha256": "...",
  "media_type": "application/pdf",
  "extractor": "pymupdf",
  "locator": {"page": 12, "printed_page": "47", "span": [120, 284]},
  "text": "...",
  "confidence": 1.0,
  "warnings": []
}
```

Spreadsheet records additionally preserve sheet, cell/range, formula, cached
value, number format, merged state, and visibility. Image records preserve
frame, vendor tag, unit status, and extraction method.

### 5.3 Evidence bundle

```json
{
  "schema": "evidence-bundle/1.0",
  "claim_id": "C-406",
  "sources": [
    {
      "source_id": "S-034",
      "relation": "direct",
      "excerpt": "...",
      "locator": "p. 47, Fig. 6",
      "artifact_sha256": "..."
    }
  ],
  "proposed_verdict": "AMBIGUOUS",
  "caveats": [],
  "producer": "source-fetcher"
}
```

Only `SUPPORTED`, `CONTRADICTED`, `UNSUPPORTED`, `AMBIGUOUS`, and `OPEN` are
valid verdict values. Source fetchers propose evidence; fact-checker and the
deterministic post-processor decide the persisted verdict.

### 5.4 Job checkpoint

```json
{
  "schema": "research-job/1.0",
  "job_id": "JOB-001",
  "contract_hash": "...",
  "input_hashes": {},
  "status": "RUNNING",
  "stages": {},
  "artifacts": [],
  "updated_at": "..."
}
```

Resume uses `job_id + contract_hash`, not a bare subagent task ID. The allowed
terminal statuses are `COMPLETED`, `FAILED_NO_OUTPUT`,
`FAILED_WITH_CHECKPOINT`, and `TERMINATED_WITH_ARTIFACTS`.

## 6. Implementation Slices

Each slice must leave the module runnable and independently testable. Do not
advertise its tools to live agents until its acceptance gate passes.

### Slice 0: Reconcile sources of truth

Deliverables:

- align capsule statuses and route hierarchy;
- correct the stdio lifecycle runbook;
- replace obsolete absolute plugin paths with `${OPENCODE_HARNESS_ROOT}`;
- remove duplicated/stale tracker statements;
- add an explicit status vocabulary: `planned`, `implemented`,
  `standalone_verified`, `live_verified`, `disabled`.

Acceptance:

- `compile_runtime.py` and route/capsule resolvers agree;
- human docs do not claim live availability without a live smoke result;
- no `start` instruction remains for host-managed stdio servers.

### Slice 1: Capability preflight

Extend health checking with a machine-readable report for:

- SearXNG HTTP/JSON availability;
- MCP Python package;
- PyMuPDF/pypdfium2 and OCR backend;
- DOCX, legacy DOC, XLSX/XLS/XLSB support;
- TIFF metadata and optional scientific-image stack;
- academic API connectivity;
- guard and writable run/cache directories.

Acceptance:

- one JSON report distinguishes `available`, `degraded`, `missing`, and
  `disabled`;
- agents receive the report before route execution;
- missing optional dependencies do not break core startup.

### Slice 2: SearXNG discovery vertical

Use the existing `searxng_search_server.py`; do not replace it prematurely.

Deliverables:

- module-owned deployment instructions and pinned configuration;
- localhost-only default;
- backend liveness and JSON-format smoke test;
- normalized `search-discovery/1.0` output;
- bounded query/result limits, timeout, retry/backoff, and deduplication;
- SQLite response cache keyed by normalized query and backend configuration.

Valkey is optional. Add it only if concurrent workers require shared rate
limiting; SQLite is the smaller first implementation.

Acceptance:

- a known query returns bounded normalized results;
- an unavailable backend returns a typed failure, not an empty success;
- snippets are marked `discovery_only`;
- SearXNG failure falls back to direct academic APIs or a declared degraded
  state, never an implicit Google `webfetch` loop.

### Slice 3: Academic source resolution

Extend the existing academic MCP behind a common adapter:

- retain arXiv and OpenAlex;
- add Crossref DOI/metadata resolution;
- add Unpaywall OA-location lookup when configured;
- leave Semantic Scholar optional;
- preserve provider-specific raw IDs in provenance;
- use contact/config env where an API requests polite-pool identification.

Acceptance:

- title, URL, and DOI candidates converge to a canonical source record;
- malformed/unknown DOI remains unresolved rather than fabricated;
- duplicate results from SearXNG/OpenAlex/Crossref collapse by DOI or canonical
  URL while preserving discovery provenance.

### Slice 4: Provenance-preserving document inspection

Refactor `doc_extract_server.py` rather than adding another generic converter.

Backend tiers:

1. PDF text: PyMuPDF primary, pypdfium2 fallback.
2. Scanned PDF: OCRmyPDF/Tesseract optional fallback.
3. Scientific structure: GROBID optional adapter, not a hard dependency.
4. DOCX: python-docx plus direct OOXML relationships/media extraction.
5. DOC: Word COM on Windows, LibreOffice/antiword optional fallback.
6. XLSX/XLS/XLSB/ODS: python-calamine for broad reading, openpyxl for XLSX
   formulas/styles, Excel COM only when recalculation is explicitly required.
7. HTML: trafilatura primary, markdownify fallback.

Do not return one giant Markdown string. Persist JSONL records plus a compact
summary and artifact paths.

Acceptance:

- every excerpt has a stable locator;
- formulas and cached spreadsheet values are separate;
- missing media and damaged encodings produce warnings;
- OCR output carries method and confidence;
- file hash prevents redundant extraction.

### Slice 5: Scientific image and SEM/EDS inspection

Create a separate optional capsule; do not overload generic document extraction.

Backend tiers:

- `tifffile` and Pillow for frames/previews;
- ExifTool for standard and vendor tags;
- OpenCV/scikit-image for axes, scale bars, and line geometry;
- Tesseract for labels;
- HyperSpy/RosettaSciIO for supported microscopy/spectroscopy formats;
- image hashes for exact and perceptual duplicate groups.

Acceptance:

- all TIFF frames and undecoded private tags are preserved;
- unknown units remain unknown;
- digitized plots are marked `digitized_from_plot` with calibration and
  uncertainty;
- SEM/EDS observations cannot be promoted to phase identification by this
  capsule.

### Slice 6: Incremental local corpus

Build on `LocalCorpusCapsule`:

- manifest with path, SHA-256, size, mtime, media type, and extractor version;
- extraction only for new/changed files;
- SQLite FTS5 for exact lexical retrieval;
- DuckDB/Parquet only where tabular analysis benefits;
- duplicate grouping by content hash;
- optional vector retrieval after lexical retrieval is correct.

Acceptance:

- a second unchanged run performs no extraction;
- number/formula/DOI queries return exact locators;
- a deleted or changed source is reflected deterministically;
- index records retain their originating artifact hash.

### Slice 7: Evidence and Writer bridge

Connect retrieval to the existing researcher and Writer DOM contracts:

- source-fetcher emits `evidence-bundle/1.0`;
- fact-checker emits the existing controlled verdict vocabulary;
- deterministic post-processing rejects unknown verdicts;
- Writer consumes persisted verdicts but cannot author them;
- report `TRACEABILITY_PASS` and `EVIDENCE_PASS` independently;
- make `writer-review` report mandatory for scientific handoff.

Acceptance:

- a traceable but unsupported claim cannot receive `EVIDENCE_PASS`;
- search snippets and unlocated OCR cannot count as direct evidence;
- `verify_claims --apply` runs on a snapshot first and preserves curated fields;
- all persisted verdicts have producer and provenance.

### Slice 8: Checkpointed dispatch and code acceptance

Deliverables:

- research job manifest under `${OPENCODE_RUNS_DIR}`;
- atomic stage updates and artifact registration;
- retry by job contract, with completed stages skipped;
- validation that task/session ID belongs to the same contract;
- route any HARNESS code change through code-orchestrator;
- independent code-tester and code-reviewer verdicts;
- acceptance runs on copied fixtures/worktrees, never the canonical DOM.

Acceptance:

- a terminated extraction resumes without repeating completed files;
- the parent receives artifact paths on partial termination;
- a mismatched task ID is rejected;
- coder self-report alone cannot approve a runtime change.

### Slice 9: Live activation

Activate one vertical at a time:

1. capability preflight;
2. SearXNG discovery;
3. academic resolution;
4. document inspection;
5. local corpus;
6. evidence bridge;
7. scientific-image capsule.

For each vertical:

- standalone unit and fixture tests;
- MCP protocol smoke test;
- guard postflight test;
- router/capsule resolution test;
- live OpenCode invocation after restart;
- failure and degraded-mode test;
- update status to `live_verified` only after evidence is recorded.

## 7. Dependency Layout

Keep optional dependencies isolated:

| Environment | Contents |
|---|---|
| core | router, policy, audit graph, stdlib researcher core |
| search | MCP, SearXNG adapter, academic HTTP clients |
| documents | PyMuPDF/pypdfium2, python-docx, calamine/openpyxl, trafilatura |
| OCR | OCRmyPDF, Tesseract bindings |
| scientific-image | tifffile, Pillow, ExifTool integration, OpenCV, HyperSpy/RosettaSciIO |

The capability preflight chooses a supported tier. Skills describe workflows;
they must not be treated as proof that binaries or Python packages are present.

## 8. Required Documentation Updates Per Slice

Every implemented slice must update only the relevant sources of truth:

- capability status: `CAPABILITY_REGISTRY.md`;
- tool contract/binding: `config/tool_families.json`,
  `config/tool_runtime_bindings.json`, `config/tool_skill_templates.json`;
- MCP contract/lifecycle: `config/mcp_registry.json`,
  `config/mcp_capsule_policy.json`, `config/mcp_lifecycle_config.json`;
- capsule registration/hierarchy: `config/capsule_registry.json`,
  `config/capsule_route_hierarchy.json`;
- runtime operation: `RUNTIME_RUNBOOK.md`;
- work status: `IMPLEMENTATION_TRACKER.md`;
- agent behavior only after tools are live: relevant `agents/*.md` and shared
  process contract.

Do not copy status statements into multiple documents when a registry can be
the source of truth. Human documents should link to the registry and state the
last verified date.

## 9. Completion Criteria

This plan is complete when:

- a researcher can discover, resolve, download, inspect, and cite a source
  without using a search snippet as evidence;
- PDF/Word/Excel/TIFF inputs produce bounded, locator-rich artifacts without
  one-off extraction scripts;
- an unchanged corpus is not rescanned;
- every scientific verdict has controlled vocabulary and provenance;
- Writer reports traceability and evidence validity separately;
- terminated research resumes from a validated checkpoint;
- HARNESS code changes require independent test and review;
- capability status in documentation matches live smoke-test evidence.
