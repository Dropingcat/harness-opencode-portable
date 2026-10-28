# TraceStore durability (A1)

The legacy `entries`, `transitions`, `state_snapshots` JSON layout is unchanged.
Existing complete serialized records retain their IDs and timestamps, including
transition timestamps. Reading performs no migration or rewrite. A missing file
is an empty in-memory store until the first successful mutation.

Each append, transition (including its trace entry), or snapshot update locks
`<storage_path>.lock` using the existing FileLease kernel lock, reads and validates
the latest disk state, applies only that operation, then flushes/fsyncs a unique
sibling temporary file and atomically replaces the store. The shared lock file
is never unlinked. Acquisition has a five-second deadline; the small primitive
also accepts an explicit finite timeout. Failed writes do not publish cache changes.
Reads and queries retain instance-local views; construct a new store to refresh.
Direct mutation of public lists/dictionaries is not a persistence API; the private
stale full-cache `_save` path was removed. Snapshot keys retain last-writer-wins
behavior for the same version; distinct version keys are preserved.

Malformed UTF-8/JSON, non-finite numbers, unknown/missing top-level or record
fields, and unsupported collection/record shapes raise `StoreCorruption`
(a ValueError). Invalid writes raise validation/serialization errors. Lock expiry
raises TimeoutError; filesystem failures propagate. No error falls back to an
empty overwrite. Preserve damaged bytes and repair a copy explicitly; no automatic
repair or in-place schema migration is provided.

Tests use explicit synthetic temporary paths under `C:\Temp\opencode` and bounded
spawned children. Windows kernel-lock behavior is exercised; actual POSIX execution
is not certified. Atomic replacement does not certify directory-fsync/power-loss
survival or retry idempotency/exactly-once semantics. Replaying multi-step chains
with a target version still has the pre-existing filtering limitation in
`reconstruct_state`; A1 does not change or certify replay correctness.

Storage identity is pinned to an absolute resolved path at construction, including
resolved parent directories. File symlinks (including dangling links) and files
with multiple hardlinks are rejected visibly with ValueError before mutation,
not followed or split into independent histories. Checks run on loads and again
on writes, including the locked read, so an alias introduced after construction
is rejected too. Path.resolve alone does not unify hardlink/inode aliases.
Relative/absolute and directory-alias spellings use the resolved target sidecar;
missing ordinary files remain supported. File symlink/hardlink rejection is tested
with actual Windows fixtures; unsupported host link creation is reported as a
test skip, never as a successful alias test.

The supported namespace must remain stable during each operation: external
renames, link creation/removal racing validation, lock-file substitution, unusual
filesystem alias mechanisms and network-filesystem locking are not certified.
This bounded validation is not an adversarial filesystem security layer.

The authorized FileLease.acquire cleanup now explicitly closes an unpublished
handle on non-OSError (including BaseException) and re-raises; OSError still
closes and returns False. A real opened-handle injection regression verifies
RuntimeError propagation, closure, subsequent successful acquisition and kernel
exclusion. Other BaseException types are covered structurally, not individually
injected. The transaction wrapper closes published handles even if body execution
or explicit unlocking raises. This resolves the prior reported pre-publication
cleanup limitation for the exercised acquisition boundary.

Run: `python -m unittest discover -s tests/coder -p test_trace_store_durability.py -v`.
Also run the unchanged independent `test_trace_store_durability_independent.py`
and new `test_trace_store_rework1.py` via the same discovery command pattern.
Broad meta/daemon suites are excluded because they may use live defaults or execute
controllers; only the isolated existing FileLease unit test is selected separately.
