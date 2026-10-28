# Damage basket candidate (A2)

Legacy `{threshold, entries, saved_at?}` stores are validated and read without
rewriting. Entry identity, timestamp and severity points are restored exactly;
unsupported shapes, duplicate IDs and inconsistent scores fail visibly with
`StoreCorruption`. The six-positional entry constructor and scoring policy remain
unchanged. Queries read the current atomic-file view, not the instance cache.

Every mutation uses accepted A1 `update_json`: lock, read, validate, modify,
validate, fsync temporary file, atomic replacement. Only committed data updates
the instance cache. A batch is atomic; identical ID/payload/time delivery is
idempotent, but an ID collision raises `BasketConflict`. Different IDs remain
distinct, including similar text: random-ID observer semantic dedup is deferred.

On mutation the additive schema is version 1, retaining `threshold`, `entries`
and `saved_at`, adding `schema_version: 1` and `acknowledged`. Each acknowledgement
record contains the full original `entry` and `snapshot_hash`. History has no
automatic retention or compaction. Replaying an acknowledged event cannot
resurrect it. Identical retries can refresh saved_at but cannot duplicate debt
or erase original acknowledgement evidence.

`snapshot()` returns independent JSON data from one view: snapshot_version,
storage_identity (A1-resolved path with platform case normalization), threshold,
entries, total_damage, hash. SHA-256 covers canonical sorted compact UTF-8 JSON
of all fields except hash, preserving entry order. `acknowledge(snapshot)` checks
shape, binding, hash, unique IDs and every captured record against active/history
content before removing anything. Later entries survive; repeat acknowledgement
is safe. `reset()` without capture raises before writing; explicit capture is an
alias to acknowledge. Hashes are NOT authentication or proof of repair.

The planner captures once for threshold and clustering, keeps that exact capture
in `SleepPlan.basket_snapshot` and serializes it. Only the daemon's existing
`execute_verified` success branch acknowledges it; executor/verifier and HP policy
are unchanged. Legacy run_audit_cycle returns structured blocked status and exit
2 before stateful construction: it is not wired to fake repair or acknowledgement.
Broader recovery and semantic authorization remain A3.

Before executor, controller/HP actions or a success receipt, `run_once` checks
the exact captured plan with nonmutating `validate_snapshot`. Missing, malformed,
foreign, hash-tampered or payload-conflicting captures return structured
`status: blocked`, `merged: false`, `acknowledged: false`; no replacement snapshot
is obtained and no executor, sleep_merge or acknowledge runs. Validation reuses
acknowledgement's shape/hash/binding and active/history payload checks, returns
an independent capture copy and leaves basket bytes untouched. New IDs do not
invalidate a capture and remain outstanding.

This is a point-in-time admission check, not atomic future execution authorization.
No basket lock is held across external execution. Final acknowledgement repeats
the checks inside A1's locked mutation. Its exception is surfaced in both return
and receipt as `status: acknowledgement_failed`, `acknowledged: false` (with
`merged: true` reporting already-executed verified merge, NOT clean cycle success).
External merge/HP effects are not rolled back. A crash between stores, receipt
write failure, concurrent changes after admission and recovery/reconciliation
remain A3 limitations; hash integrity is not repair authorization.

## Release gate — BLOCKED without verified old-writer quiescence

Old writers do not honor A1 locks/history and can destroy acknowledgement
evidence. Before any future release an operator must independently verify all
old writers are quiescent or compatible. This candidate does not migrate any
production store, run/stop/restart writers, deploy or change production state.
Without that evidence release is BLOCKED, not DONE. TD-184 remains open.

## Scoped verification

Run only explicit fixture suites:

```
python -m unittest discover -s tests/coder -p test_damage_basket_durability.py
python -m unittest discover -s tests/coder -p test_basket_snapshot_callers.py
python -m unittest discover -s tests/coder -p test_damage_basket_independent.py
python -m unittest discover -s tests/coder -p test_trace_store_durability*.py
```

All new stores/planner state use temporary paths under C:\Temp\opencode with
cleanup. Process writers use a spawn barrier, bounded joins and finally cleanup.
Caller methods are AST-extracted with injected fakes: no real MetaCore, daemon,
sleep or merge. Replace errors and lock timeouts are injected/controlled.
Windows fixture checks do not establish POSIX, power-loss, hostile-namespace or
exactly-once guarantees. A1's stable namespace and leaf-alias rejection apply.
