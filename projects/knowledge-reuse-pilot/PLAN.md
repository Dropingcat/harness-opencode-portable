# Evidence path and implementation slices

## Goal

A project-scoped MCP returns existing artifacts, their explicit provenance and
the next unresolved work, rather than repeating searches and analyses. Wiki and
graph outputs are derived navigation, never a second authority for truth.

## Accepted scope

Corpus: F:/1 plus E:/opencode_harness_portable projects, docs, shared and selected
memory/tracker configuration. Skip dependencies, secrets, generated pilot output
and reparse-point traversals; report unsupported/oversized inputs in coverage.
No corpus material is sent to an external model by indexing.

## Slices

1. Platform inventory and lifecycle: identify the existing search service, keep
   TEMP/TMP/cache/log paths in this project, test on-demand start and real search.
2. Read-only incremental artifact catalog: content hashes, local text extraction,
   scope isolation, explicit links, source versions and complete coverage accounting.
3. Lookup/trace and explicit artifact registration: reuse only declared scope with
   matching artifact/dependency hashes; distinguish candidates from approved work.
4. Durable bounded jobs: idempotency, single-flight execution, cancellation,
   checkpoints/status, no hidden downloader or LLM fallback.
5. Graph/wiki projections, thread/L1-L3 references, optional real Graphify adapter.
   Flowsint readiness and network diagnostics; no fake successful Flowsint execution.
6. MCP stdio smoke + full-corpus indexing + repeat-query/no-op-index evidence.

## Verification ownership and minimum evidence

| Claim | Owner | Decisive evidence |
|---|---|---|
| No writes to corpus/outside pilot | catalog/path boundary | temporary-tree before/after hashes; configured write-root checks |
| Repeat work is not redone | catalog + job store | no-op second scan; same job ID; same input/method fingerprint |
| Reuse is evidence-backed | reuse policy | accepted fixture reuses; changed source/withdrawn report does not |
| Sources/versions are traceable | explicit-link importer | report -> input revision; ambiguous links remain candidates |
| Errors aren't hidden as success | lifecycle/adapters | unreachable and failed-step cases return blocked/partial |
| Real integration works | stdio MCP client | initialize/list_tools/call_tool against the actual subprocess |
| Corpus coverage is honest | scan run manifest | supported/unsupported/failed/excluded totals and reasons |

Unit tests use unittest, matching existing Harness tests. Runtime evidence and
unit checks are separate. Repeat a check only after relevant code/inputs change.

## Current platform observations

- Configured/default search endpoint: http://127.0.0.1:8888, initially unreachable.
- Existing launcher: scripts/tools/start_searxng.py; backend: mcp/mini_searxng.py.
- Full Flowsint /health on 127.0.0.1:5001 was unreachable. No Docker executable
  was found in PATH or the standard installation location.
- Harness has substantial pre-existing modifications: do not stage, revert or
  overwrite them. Pilot changes are additive under this project directory only.
