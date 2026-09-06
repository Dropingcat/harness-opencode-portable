# Artifact Provenance Architecture — Stage 3

## Goal

Prevent evidence from being accepted merely because an agent names a source. Every material input is represented as a content-addressed artifact and every evidence event carries explicit artifact references.

## Chain

```text
raw bytes
  -> ARTIFACT_REGISTERED(content_hash, origin, tool_id, source_ref)
  -> [if untrusted] ARTIFACT_GUARD_VERDICT
  -> optional ARTIFACT_SANITIZED(new content_hash, source_artifact_id)
  -> AGENT_EVIDENCE(output_artifact_id, artifact_refs[])
  -> GateSet
  -> State Reducer
```

The event log remains the authority. `projection.artifacts`, `projection.artifact_guards`, and `projection.evidence` are materialized views.

## Trust rules

`agent_output`, `local_file`, and `tool_internal` are internal origins and do not require a trust-boundary guard by default.

`web`, `external_tool`, `subagent`, and `user_supplied` are untrusted origins. They cannot be referenced by `AGENT_EVIDENCE` until the latest guard verdict is `PASS`.

A sanitized derivative is a distinct artifact. It never overwrites the raw artifact. Its record contains `source_artifact_id`, its own SHA-256, sanitizer identity, and notes. This preserves the raw/sanitized relationship for audit and replay.

## Evidence binding

Every `factory_ctl submit ... output.json` automatically registers `output.json` as an `agent_output` artifact. `AGENT_EVIDENCE.output_artifact_id` points to that exact hash. Paths are hints only. Identity is the content hash plus artifact id in the event log.

Additional context/source artifacts are supplied with repeated `--artifact <artifact_id>` options.

## Commands

```bash
python scripts/code-factory/factory_ctl.py artifact-register source.txt --origin web --tool-id webfetch --state state.json
python scripts/code-factory/factory_ctl.py artifact-guard <artifact_id> PASS --guard-id session_guard --state state.json
python scripts/code-factory/factory_ctl.py artifact-sanitize <raw_artifact_id> clean.txt --sanitizer-id deterministic-redactor --state state.json
python scripts/code-factory/factory_ctl.py submit reviewer reviewer.json --artifact <artifact_id> --state state.json
python scripts/code-factory/factory_ctl.py replay --state state.json
```

## Invariants

1. Evidence without a registered output artifact is invalid at the runtime API.
2. An artifact id is immutable within an event log.
3. Untrusted artifacts require a guard PASS before evidence may reference them.
4. Sanitization creates a derivative artifact; it never mutates or replaces the raw record.
5. Evidence referencing unknown or inadmissible artifacts is ignored by the reducer and recorded in `provenance_errors`.
6. Event hashes protect the provenance history itself from silent edits.
7. Gate transitions happen only from provenance-admissible evidence.
8. The provenance policy and its SHA-256 are snapshotted into `TASK_CREATED` for reproducibility.

## Deliberate limitation

Stage 3 records and enforces guard attestations but does not pretend that every possible file type can be safely scanned by one generic text heuristic. A guard implementation must emit its verdict through `artifact-guard`. The existing session guard remains suitable for OpenCode session/database trust-boundary analysis; specialized file/content guards can be added without changing the reducer contract.

## Next hardening step

A future guard adapter layer can map concrete guards to artifact media types and origins and automatically emit signed/structured `ARTIFACT_GUARD_VERDICT` events. That should be implemented as adapters, not by teaching the reducer to inspect content.
