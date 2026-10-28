# Lineage

- Canonical scripts/meta/trace_store.py and daemon_safety.py were byte-backed-up and hash-recorded before implementation; normalized source matched receiving worktree at capture.
- docs/ARCHITECTURE_REVIEW_AUDIT_ROUTER_SLEEP_2026-10-15.md and its isolated evidence identified reload loss and stale-instance overwrite.
- docs/CODERS/06,09,10,11,13,14 define material, role sequence, falsifiable findings, explicit artifacts, checks and audit mode.
- Historical migration assumptions about 1.18.30, CWD, push and broad synchronization are not executed. Current headless host is 2.0.29 and canonical E: remains read-only until release.

No private production traces, OAuth tokens or provider configuration are included. Source P0 checks are input hygiene, not a repaired semantic-guard certificate.
