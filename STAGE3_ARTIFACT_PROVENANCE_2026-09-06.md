# Stage 3 — Artifact Provenance Refactor

Date: 2026-09-06

## Implemented

- Added `config/artifact_provenance_policy.json`.
- Added `scripts/code-factory/provenance.py` with SHA-256 content addressing and policy helpers.
- Factory state format bumped to v3: `event-sourced+provenance`.
- `TASK_CREATED` now snapshots provenance policy and `provenance_policy_hash`.
- Added event types `ARTIFACT_REGISTERED`, `ARTIFACT_GUARD_VERDICT`, and `ARTIFACT_SANITIZED`.
- `AGENT_EVIDENCE` now contains `output_artifact_id` and `artifact_refs`.
- Agent JSON output is auto-registered and hash-bound before evidence is appended.
- Untrusted referenced artifacts are rejected at submission unless guard verdict is PASS.
- Reducer independently re-checks artifact existence/admissibility during replay. Invalid evidence cannot advance a gate.
- Sanitized derivatives preserve source lineage and receive a new content hash.
- Added CLI commands: `artifact-register`, `artifact-guard`, `artifact-sanitize`.
- Existing Stage 1 runtime policy compiler and Stage 2 Attempt/GateSet behavior remain intact.

## Compatibility

CLI `init`, `submit`, `budget`, `auditor_block`, `finalize`, `status`, and `replay` remain available. `submit` now automatically records provenance for its output path.

State v2 is intentionally not silently migrated to v3 because historical Stage 2 events lack artifact identity. Fabricating provenance during migration would produce false evidence. Old runs remain readable only by the Stage 2 runtime; new runs should be initialized under Stage 3.

## Tests

15 regression/unit tests pass, including:

- all Stage 1 routing/compiler tests;
- Stage 2 gate/retry/replay tests;
- untrusted artifact rejection before guard;
- acceptance after guard PASS;
- sanitized derivative lineage and distinct hash;
- agent-output hash binding.

## Security interpretation

This stage establishes provenance integrity, not universal content safety. `artifact-guard` records a concrete guard's attestation. The guard itself must be appropriate to the artifact origin/media type. This separation is intentional: orchestration policy should validate evidence flow, while content-specific scanning belongs to dedicated guard adapters.
