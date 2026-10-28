# Knowledge reuse pilot

Project-local MCP pilot for finding and reusing primary documents, reports and
session artifacts without reconstructing the whole project on every request.

## Boundaries

- Read-only corpus: `F:/1`, Harness projects/docs/shared/config memory.
- All new files, logs, caches and temporary files stay under this directory.
- No changes to global OpenCode configuration or existing Harness source files.
- Existing `mini_searxng.py` is the installed search backend, not full SearXNG.
- Flowsint's `website_to_text` is not modified; its live availability is reported.
- The downloader remains a separate agent-operated channel, never an automatic fallback.
- Missing, stale and unindexed evidence is reported, not invented or promoted to L3.

See `PLAN.md` for the acceptance path. Installation/readiness is NOT implied by
this scaffold; evidence is written to `artifacts/` as increments are verified.

Module responsibilities: `MAP.md`. Commands, MCP tools and known boundaries:
`USAGE.md`. Current evidence and remaining tasks: `PROGRESS.md`.
