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
