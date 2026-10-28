# Stage 0: source-bound development baseline

The matrix in `config/development_evidence_matrix.json` projects the reconciled
13 DEV and seven WS records without becoming another status authority. Phase A
is accepted; this stage does not execute stages 1–8 or close technical debt.
Source bytes, statuses, reported evidence, readiness dimensions and historical
completion scope are pinned and checked offline. Historical 1.18.30 DONE remains
history, not V2 acceptance. Old master-plan “spec ready” means specification only.

## Inventory and evidence boundaries

The source inventory is canonical `config/tech_debt.json`: **241 total, 182 open,
59 closed**. Every existing ID/status is projected; only the ten selected TDs
and seven existing E2E records are mapped to this plan. Remaining records are
explicitly **outside verified scope / unassessed**, not 182 audited debts.
Workspace TD inventory (230) intentionally differs and is not imported or synced.
Relevant TD acceptance and owners are copied, not replaced; UNASSIGNED remains
unassigned. Stage ownership is coordination, not an ownership transfer.

Durable native, observer, memory, injection, BOM and Desktop summaries under
`docs/evidence/tracker-reconciliation-2026-10-14/` are hash-bound inputs. Private
tracker worktree references remain explicitly unresolved historical references;
alias mappings point to bounded durable summaries, not equivalent original receipts.
Availability does not imply success. Empty historical evidence is still source
text only; absent current readiness is NOT_TESTED, never inferred from DONE.

Native deterministic plugin load was observed only in the canonical E-project;
the current worktree has no Harness plugin/MCP activation. The observed profile
path is metadata, not an executable dependency. Active OpenAI OAuth does not
prove quota availability or a live model-driven tool call. Deterministic Core
smoke and mocks are not semantic certification. Guard enforcement/fail-open gaps
and unwired automatic memory injection persist. Input P0 PASS and its negative
control are bounded scanning, not safety certification. Full autonomy remains
BLOCKED by existing TD-RESTORE-01.

## Future sequence (not execution acceptance)

| Stage | Prerequisites | Existing anchors | Measurable closure |
|---|---|---|---|
| 0 baseline | accepted reconciliation | DEV-02 | Exact inventory/hash/status validation and mutation controls |
| 1 guard contracts | 0 | DEV-08, TD-004/013/RESTORE-01 | Zero fail-open outcomes for denial, missing guard and guard errors |
| 2 memory | 0, parallel with 1 | DEV-08, TD-175 | Two namespaces plus shared; zero leakage; admission/provenance negatives |
| 3 read-only V2 semantics | 1 | DEV-03/04/05, WS-58A/59A, TD-053/054 | Real read-only trace and timeout/cancel/recursion/auth/quota negatives |
| 4 context | 1 + 2 + 3 | DEV-08, TD-175/176/177 | Automatic bounded injection across two switches; stale/foreign rejection |
| 5 supervision | 4 | DEV-06, TD-024/174 | Heartbeat/loop detection and bounded restart; replay without duplicate effects |
| 6 nested E2E | 5 | existing E2E IDs | Seven real-artifact gates plus independent negatives |
| 7 controlled autonomy | 6 | DEV-09, WS-59A, TD-RESTORE-01 | Independent real merge/rollback evidence; auth/quota pause; dirty edits preserved |
| 8 learning (last) | 7 + verified W8 canon | DEV-08 | Canon positive/absent/stale tests, provenance-bound admitted replay |

Existing E2E order is **E2E-06 → 02 → 01 → 04 → 03 → 07 → 05**;
the matrix uses the full existing IDs, not new debt identifiers. DEV-07 and
DEV-11/12/13 remain separately queued advanced work. Gates are prospective:
no matrix row reports their completion. Dependencies are acyclic. Historical
bidirectional tracker cross-references are not execution dependency edges.

## Reproduction and staging

Run from the workspace, reading canonical sources and writing only workspace output:

```powershell
python -B scripts/tools/check_stage0_matrix.py --source-root E:/opencode_harness_portable --evidence-root . --output-root . --generate
python -B scripts/tools/check_stage0_matrix.py --source-root E:/opencode_harness_portable --evidence-root . --output-root .
python -B -m unittest discover -s tests/coder -p test_stage0_matrix.py
```

The E-path above is an explicitly selected data root, not hardcoded executable
discovery. `--tracker` and `--td` accept explicit data files. `--evidence-root`
allows durable summaries staged separately. Source master plans resolve under
`--source-root`; matrix output resolves under `--output-root`. Default checking
uses the script checkout root, so after deployment it checks canonical directly.
Before deployment, default workspace checking should fail on intentional TD drift.
Generation never writes source registries, copies TD data or activates anything.

The checker compares the complete deterministic projection, rejects source drift
and unsupported additions, and checks dangling/cyclic stage references. Fixture
tests need no ignored `.runs` files. Byte hashes intentionally detect BOM/encoding
changes too. Independent review remains a parent acceptance gate; these local
checks establish a baseline only, not host or semantic certification.

## Parallel-session guard discovery follow-up

The user reported a cold-start dispatch block because the logical `doc_guard`
could not be found. Main-tree checks found the scanner/runner under `guard/src/`,
not under `scripts/`; the manifest distinguishes ID `session_guard` and provider
`doc_guard`. The parallel session's exact environment is unverified. This is an
additional stage-1 discovery/packaging/interface acceptance requirement under
existing `TD-RESTORE-01`, not permission to bypass the missing PASS. See
`docs/GUARD_DISCOVERY_FOLLOWUP_2026-10-15.md` for the cold-start, parallel-session,
artifact-input and fail-closed test contract. The matrix is regenerated when this
acceptance metadata changes; no source debt status or runtime setting is changed.

### Verification results and limits

The worker receipt (`.runs/tracker-stage0-20261014/worker_stage0-matrix.json`)
records eight focused stage-0 tests and the source-bound checker passing.
Its actual broader run, `python -B -m unittest discover -s tests/coder`, ran
**201 tests: 199 passed, one error and one failure**:

- `test_bridge_peer_direct_cov.BridgePeerDirectTests.test_serve_loop_in_process`
  errored with `KeyError: 's2'` during the threaded fake-stdio test; the `s2`
  response appeared outside the captured output.
- `test_semantic_transport.SemanticTransportTests.test_build_request_valid`
  expected `cli` but received the environment's `OPENCODE_SESSION_ID`.

This worker did not independently reproduce a pre-change baseline, so baseline
causation for either unsuccessful test is **not established by this run**.
No unrelated runtime fixes were made, and the broad coder suite is **not green**.
The targeted documentation rework does not rerun or supersede that broader result.
