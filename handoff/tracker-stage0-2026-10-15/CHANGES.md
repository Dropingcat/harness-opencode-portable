# Changes and acceptance

Phase A implementation is complete in the accepting worktree: historical tracker snapshot retained, current V2 readiness separated, inconsistent DEV-05 readiness corrected, counts recomputed, read-only validator and focused mutation tests added.

Phase A reached factory DONE after scoped review, testing and process audit. Six validator mutation gaps were fixed; the independent test now uses a tracked exact-original fixture rather than ignored run data. Final scoped tests: 19/19. Canonical tracker replacement was hash-checked and rollback-protected; canonical validator and the same 19 tests exit 0. No canonical commit was made.

Broader caveats remain explicit: the semantic test failure was reproduced at the baseline and depends on OPENCODE_SESSION_ID; the earlier full-suite daemon timing failure did not reproduce in isolated current/baseline tests and remains unresolved. No broad-green claim.

Phase B started only after Phase A acceptance and canonical validation. Its matrix is derived from the accepted tracker and existing TD IDs, with no second status authority or blanket closure of the backlog. The context-reader task also corrects reporting that previously searched only the absent legacy Markdown tracker.

Integration packaging: the exact-original tracker fixture is marked `-text` in `.gitattributes`, preventing Git core.autocrlf=true from rewriting the hash-pinned bytes on Windows checkouts. This does not alter tracker content or runtime behavior.

## Stage 0 accepted

- `config/development_evidence_matrix.json` is a hash-bound projection, not a second status registry. It covers all 13 DEV / seven WS and inventories all 241 canonical TD/E2E records, with 182 open. Seventeen selected blockers/E2E records are mapped; the remaining inventory is explicitly outside the verified scope.
- `docs/DEVELOPMENT_STAGE0_2026-10-15.md` defines dependencies, ownership and measurable future closure gates. Stages 1–8 have not been executed. The public document retains the broader worker run of 201 checks / 199 passed / two unsuccessful checks without claiming established baseline causation or a globally green suite.
- `scripts/tools/check_stage0_matrix.py` validates source hashes/statuses, coverage, dependencies and evidence; supports canonical data with separately staged output/evidence. The 230-record worktree TD registry was not copied over the 241-record canonical registry.
- `project_context.py` now reports the validated structured development tracker, its declared counts and separate current-host readiness. Legacy fallback applies only if the structured source is absent; invalid structured data is not hidden by fallback.
- Canonical integration was exact-hash checked and rollback-protected. Seven canonical validation commands exit 0, including 75 scoped tests across four suites. The normal canonical context reports structured tracker data with no tracker error. The canonical TD hash stayed unchanged.
- Both stage-0 result reviews APPROVE; independent tests PASS; metadata-only process audit APPROVE. Factory `HARNESS-STAGE0-20261015` finalized DONE after one actual documentation rework. No tribunal or provenance errors.
- Runtime activation, daemon settings, memory and TD statuses were not changed. Full autonomy remains blocked under `TD-RESTORE-01`.

## Reported parallel-session guard block

The user's subsequent report was recorded as `PARALLEL-GUARD-DISCOVERY-20261015` in the existing open TD-RESTORE-01 notes and acceptance, linked to TD-004/013. No new debt ID or status change was made. The parallel session's exact environment remains unverified; stopping without a real guard PASS was correct.

Main canonical and worktree paths contain `guard/src/session_guard.py` and `guard/src/guard_runner.py`, while the guessed `scripts/doc_guard.py` / `scripts/tools/doc_guard.py` paths do not exist. The runtime binding distinguishes ID `session_guard` from provider `doc_guard`. Presence/help output does not establish a combined guard PASS. Discovery, packaging, artifact-input support and clean parallel-session preflight are now explicit stage-1 acceptance requirements.

This metadata-only follow-up changed the canonical TD content hash, not any debt status. The source-bound matrix was regenerated using its accepted generator. Final canonical revalidation again passed all seven commands / 75 scoped tests; normal context reports the structured tracker. Original receipts remain historical, and a separate follow-up/final receipt records the new source baseline. No guard fix, runner dispatch, memory injection or runtime activation was performed.
