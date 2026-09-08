# Integration review and test record

Date: 2026-09-08
Basis: supplied `harness.zip`, `RESEARCH_TOOLING_CAPSULE_IMPLEMENTATION_PLAN.md`, `IMPLEMENTATION_TRACKER.md`, and current `.kanban.db` observations.

## Reconciliation with current HARNESS

The pack reuses rather than replaces:

- Stage-1 `routes_authority.json` + `runtime_snapshot.json` + `resolve_route.py`;
- existing MCP registry and SearXNG/OpenAlex/arXiv/document wrappers;
- existing code-factory Stage-3 provenance/reducer;
- researcher-core deterministic units/uncertainty/formula/evidence logic;
- Writer DOM, `draft_loop`, `verify_claims`, and `citation_trace`;
- current skills registry and route skills.

The added layer addresses gaps already identified in the module plan: capability preflight, bounded provider selection, stage-specific tool exposure, document/science convenience tools, incremental FTS, and checkpointed dispatch.

## Important corrections discovered during integration

1. `scientific-critical-thinking` is used by the current base route policy but is absent from `skills_registry.json`. The capability compiler therefore accepts skills already authorized in the compiled base snapshot instead of creating a competing registry entry. Registry normalization remains baseline debt.
2. Existence of `mcp/searxng_search_server.py` is not treated as SearXNG availability. Backend liveness is probed separately.
3. The existing document MCP is currently disabled in HARNESS lifecycle documentation; this overlay marks that existing provider disabled and supplies format-specific local inspectors when their actual Python modules exist.
4. Research discovery supports an `any-of` requirement: web discovery or academic metadata. This permits an explicit degraded/fallback path instead of implicit Google/webfetch loops.
5. Reviewer stages explicitly forbid `code.edit`; Writer drafting explicitly forbids `web.discovery`.
6. Session retry is modeled as Job/Attempt separation. A timed-out invocation with checkpoint/artifacts moves Job to `WAITING_RETRY`, not global failure.
7. Parent completion reconciliation rejects required child jobs that are not successfully `COMPLETED`.

## Tests executed on a copy of the supplied HARNESS

### New overlay regression suite

13 scenarios passed across the final test runs:

- compiler freshness;
- degraded/available capability classification;
- academic discovery any-of fallback;
- bounded capability escalation and forbidden escalation;
- Writer no-web tool surface;
- code-review no-edit tool surface;
- numerical/symbolic/formula/uncertainty/molar-mass checks;
- PDF/DOCX/XLSX/TIFF fixtures;
- scientific-image observational-only invariant;
- incremental FTS + unchanged skip + deletion reconciliation;
- normalized SearXNG offline fixture with discovery-only snippets;
- DOI normalization in offline source resolver;
- Job timeout/checkpoint/retry and parent/child completion rejection;
- plot/report artifact generation.

### Base policy/compiler compatibility

PASS:

```text
compile_runtime.py --check
compile_capability_runtime.py --check
python -m compileall -q scripts mcp guard/src audit_graph/src
```

Base policy hash observed during test:

```text
6676bcbc8732fac4f97e88f13b712758dff818db849bf588adb0a7e1a2ea880a
```

Capability overlay policy hash:

```text
dc68b2f89bf8cd4ecbca8d112701995cb78a83f6e17efddca8d4b1d79f851ba0
```

### Existing Writer tests after overlay

PASS:

- citation trace: 8/8
- draft loop: 13/13
- verify claims: 10/10

### Existing researcher-core suite

The supplied baseline and the overlay copy produce the same result:

```text
360 tests
356 pass
3 failures
1 error
```

Existing baseline defects reproduced on both copies:

- `test_guard.GuardBlockTests.test_p0_internal_weak_ru_is_low`
- `test_guard_integration.GuardIntegrationTests.test_local_evidence_with_discussion_is_allowed`
- `test_local_corpus.LocalCorpusCapsuleTests.test_search_local_hits`
- `test_local_corpus.LocalCorpusCapsuleTests.test_sources_local_ranked`

Therefore these are not overlay regressions. They should remain explicit researcher-core debt and are good candidates for the next integration round.

### Existing code-factory tests

Core commands and individual Stage-3 tests exercised during review pass; the monolithic discovery run can hang in this container after several subprocess-heavy tests, while isolated cases pass. This pack does not modify code-factory files. Server-side acceptance should still run the existing runtime-core suite in its native environment before live activation.

## Not claimed as complete

This pack intentionally does not claim live verification of:

- SearXNG backend on the user's server;
- Crossref/OpenAlex/Unpaywall network availability;
- OCRmyPDF/GROBID/Docling;
- Word/Excel COM;
- HyperSpy/RosettaSciIO/ExifTool/OpenCV;
- live OpenCode MCP registration after restart.

These should transition to `live_verified` only after target-server smoke evidence exists.
