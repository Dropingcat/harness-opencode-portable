# SDD ledger — plan: projects/knowledge-reuse-pilot/PLAN.md

## User-approved constraints

- Full corpus: F:/1 plus Harness projects/docs/shared/config memory, read-only.
- All new files, caches, logs, TEMP/TMP stay inside this project. No C: writes by
  pilot code. Do not touch pre-existing dirty Harness files or global config.
- Existing mini-searxng uses default localhost:8888; start it on request if down.
- Keep Flowsint website_to_text unchanged; diagnose, don't rewrite/bypass it.
- Downloader remains agent-operated, no automatic downloader fallback.
- Goal is attention/context continuity and reuse, not token benchmarking.

## Completed evidence

- Catalog and reuse policy: original 5 tests were RED (missing module), then GREEN.
- Bounded extraction, rejected-status, JSON credential redaction tests GREEN.
- Jobs single-flight/result reuse tests RED->GREEN. Additional blocked-status and
  dead-owner regressions were observed failing, then fixed and GREEN.
- Latest full unit command: `./run.ps1 test`, 15/15 passed.
- Graphify 0.9.95 reader vendored with SHA256-pinned official wheel. No global
  assistant installer, no model/API extraction; real graph query tested.
- Live stdio smoke: `./run.ps1 smoke` passed; actual pilot MCP has six tools;
  actual native Graphify MCP has ten. Repeated real F:/1/data.csv profiling used
  the SAME job ID, input hash unchanged; canonical thread context returned.
- Actual search recovery: only pilot-owned mini-search process was stopped;
  next `web_search` started existing backend and returned five arXiv results.
  No downloader or Flowsint invocation. Search relevance is NOT certified.
- Flowsint http://127.0.0.1:5001/health absent, honestly BLOCKED_MISSING_SERVICE.

## Running, do not poll

Full-corpus scan started with shell background ID sh_174b32995001pBdocav3dnxKfP.
Command: `./run.ps1 scan *> ./logs/corpus-scan.log`. Await automatic completion
notification. DB cache is incremental; do not start a competing full scan.
One safety resource check found scanner ~168 MB working set, no stop performed.

## Remaining

1. Finish explicit JSON/provenance link import and cached-text redaction migration
   (the running scan loaded the old redactor). Do NOT reparse PDFs for redaction.
2. Expose controlled registration and register generated local-analysis results
   as draft navigation artifacts, never silently certify historical reports.
3. On full scan completion: refresh cached links/redaction, export real-corpus
   graph/wiki, real query/trace demonstration, then incremental no-op scan proof.
4. Update README/MAP/evidence summary and project-scoped MCP usage instructions.
5. ONE final fresh-context whole-pilot code review; fix important findings with
   failing regressions then full suite. No per-task reviewer swarm.

## Review repair gate (2026-10-26)

One independent review completed. Its reproducers were run locally: 36 tests,
16 failures plus one cleanup error caused by the failed duplicate-job test.
The original background scan was stopped (pilot scanner PIDs only); committed
catalog data remains, but old extraction entries are untrusted until reindexed.

- [x] C1: sanitize structured tokens/URLs and all fragment boundaries; migrate cache.
- [x] I1/I2: monotonic decisions; transitive input/status checks and cycle bounds.
- [x] I3/I4: format/version-aware extraction; hash the exact immutable parse input.
- [x] I5/I6: computation identity excludes wording; replay preserves dispositions.
- [x] I7: complete projection fingerprint and cached output validation.
- [x] I8/I9: shared recoverable scan exclusion; atomic cancel state transition.
- [x] I10/I11: pre-write containment; globally bounded provenance trace.
- [x] M1/M2: reconcile dead active jobs; recover search-start locks after crashes.
- [x] Re-run all units + live MCP (2026-10-28: `./run.ps1 test` 41/41 OK,
  each review reproducer in tests/test_review_regressions.py GREEN;
  `./run.ps1 smoke` PASS: pilot MCP + native Graphify 10 tools, query/stats pass).
- [ ] Finish honest full-corpus coverage, graph/wiki, no-op evidence
  (`./run.ps1 verify-corpus`, restarted 2026-10-28; the 2026-10-26 run stopped
  mid-scan without a result). No production-readiness claim from a pilot test.

## Rulings

- Ruling: Flowsint remains a blocked optional integration, not a fake execution —
  no full service/Docker exists on this Windows machine — cost: no claim of a
  complete live Flowsint path until its actual service is provisioned.
- Ruling: Graphify is a real read/MCP engine over the artifact projection, not an
  LLM semantic rebuild of the corpus — avoids external data/model calls — cost:
  semantic inference/AST extraction is not demonstrated by this pilot.
- Ruling: existing additive project directory is the isolation boundary; no
  worktree, branch switch, auto-commit or parent-repo staging — preserves the
  user's substantial dirty work and specified write scope — cost: pilot is not
  yet merged/released and requires explicit integration approval.
- Ruling: call canonical project_context read functions in-process rather than
  spawning Python from the stdio worker — live smoke exposed a 20s stalled handoff,
  while direct canonical call succeeds — cost: if its public helper composition
  changes, this small adapter must be checked against it.

## Platform

Python 3.11.15, Windows 10, 4 CPUs, ~7.2 GiB RAM, ~13.8 GiB initially free on E:.
Harness .venv: mcp 1.30.0, requests 2.34.2, PyMuPDF 1.28.2, NetworkX 3.6.1.
No new global packages/config. Installed search is mini_searxng, not full SearXNG.
