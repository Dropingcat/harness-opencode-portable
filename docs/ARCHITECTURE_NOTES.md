# Notes on Architecture (v1)

## Plugin registration: canonical path vs transitional helper (TD-D3, issue #16)

**Canonical production path**: bootstrap writes/validates project-scoped registration in
`.opencode/opencode.json` — a `file://` URI pointing at
`packages/opencode-harness-plugin/dist/index.js`. The OpenCode host loads the native plugin
(`@harness/opencode-plugin`) from that project config; nothing is written to global config.
The canonical doctor (`packages/opencode-harness-plugin/core/doctor.py`) verifies this
registration (project config scan + `_registered_plugins`).

**Transitional helper**: `scripts/register_plugin.py` is a TEMPORARY (status: TRANSITIONAL_DECLARATION) project-scoped helper for
development/bootstrap convenience (register/unregister the file:// entry). Per
`INTERFACE_CONTROL.md` §12 / `BOUNDARY_MATRIX.json` it is marked REPLACE by
installer/package registration in the target architecture; until that installer ships (post-P5),
this helper remains operational but must not acquire new responsibilities.

**Status declaration**: `config/opencode_plugin_config.json` documents the plugin mode
(native) and the transitional status. It is a **declaration, not a runtime source of truth**:
no executable module (.py/.ts/.sh/.js) may read it at runtime. This invariant is enforced by
the fail-closed gate `scripts/tools/check_plugin_registration_status.py` (I1–I5) with mutation
tests in `tests/test_plugin_registration_status.py`.

## Module porting reconciliation: docs vs actual v1 composition (TD-D1, issue #17)

The migration documentation (`CURRENT_ARCHITECTURE.md` §5 Module inventory,
`BOUNDARY_MATRIX.json`) lists subsystems that exist in the source deployment but were
**not** carried into the v1 portable repo. TD-D1 is closed via the explicitly allowed
branch of the task: *document the exclusion*, not silently ship an incomplete port.

**Canonical registry**: `docs/MODULE_PORTING_EXCLUSIONS.json` — one record per declared
module with status `PORTED` (present and wired), `PARTIAL` (some files present, others
declared absent), or `EXCLUDED_PENDING_PORT` (absent from v1; port tracked separately):

- `scripts/writer` — EXCLUDED_PENDING_PORT (only `scripts/writer-core` shipped);
- `scripts/writer-core` — PORTED (active Writer module of v1);
- `scripts/kanban`, `scripts/memory` (tracked as TD-I2), `scripts/capsules` —
  EXCLUDED_PENDING_PORT;
- `shared/` — PARTIAL: only `shared/harness-dispatch-map.md` ported;
  `research-orchestration-process.md` and siblings are declared-absent by design.

**Invariant**: the registry must never drift from the filesystem. Enforced by the
fail-closed gate `scripts/tools/check_module_porting.py` (I1–I6: schema/parse, required
fields, status↔tree consistency, completeness of mandatory records, debt-id format,
ledger marked ЗАКРЫТО) with mutation tests in `tests/test_module_porting.py`. Adding a
new module to migration docs without a registry record fails CI.
