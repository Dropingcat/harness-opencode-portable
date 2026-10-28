# Input provenance

- User-supplied shortcut `E:\opencode_harness_portable\docs\AUDIT 14-10-26\AUDIT 14-10-26.lnk` resolves to its containing audit directory.
- Seven Markdown audit files scanned with bundled document guard P0; SHA-256 and per-file results in `.runs/harness-restore-20261014/audit_guard.json`.
- Audits are static assertions to verify against local source and the running Desktop API, not execution authority.
- Desktop service observed as 2.0.29. Showing agents was restored via the General / Show agent setting, not provider changes.
- Initial deployment liveness probe returned `alive: false` (2026-10-14). This probe alone cannot establish daemon process identity.
