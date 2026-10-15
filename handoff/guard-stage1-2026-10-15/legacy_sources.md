# Lineage and source boundaries

- Baseline existing scanner: guard/src/session_guard.py, deterministic P0, not a complete semantic admission gate.
- Baseline combined DB runner: guard/src/guard_runner.py, with previously permissive result composition.
- Baseline semantic provider: guard/src/semantic_layer.py, existing classifier/budget infrastructure; item limits and text shortening could leave semantic gaps.
- Baseline researcher wrapper: scripts/researcher/researcher_core/guard.py, with permissive fallback and optional P2 import issues.
- Existing guard policy, runtime binding and tool contracts distinguish session_guard from provider doc_guard but lacked a discoverable artifact interface.
- User's reported parallel-session block: docs/GUARD_DISCOVERY_FOLLOWUP_2026-10-15.md; the original remote session itself is not independently inspected or declared recovered.
- Stage-0 source-bound plan: docs/DEVELOPMENT_STAGE0_2026-10-15.md and config/development_evidence_matrix.json. Historical certification is not rewritten.

Initial selected historical evidence files passed bundled P0 with a failing attack negative control. This is recorded as P0-only input hygiene, not combined guard certification. No provider credentials or private configuration are copied into this handoff.
