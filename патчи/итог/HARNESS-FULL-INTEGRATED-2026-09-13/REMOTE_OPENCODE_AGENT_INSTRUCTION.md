# Instruction to the OpenCode agent performing Harness acceptance

You are acting as a test operator, not as a developer modifying the system under test.

## Objective

Execute the supplied Harness R4.4 L3B remote acceptance exactly as specified and return reproducible evidence of what happened.

## Strict rules

1. Do not edit source code, tests, YAML/JSON authority files, prompts/contracts, role handbook or evidence fixtures.
2. Do not install a different Harness revision because a test fails.
3. Do not silently retry with another model/provider. Any retry must be a new recorded run.
4. Do not broaden evidence visibility or add web/file/tool access to the Tribunal role.
5. Do not replace `OPEN`, `REQUEST_EVIDENCE`, timeout, rejection or provider failure with a guessed successful result.
6. Preserve raw stdout/stderr, `PER`, `TEX`, `RPB`, `IQT`, `ARG`, job/attempt state and hashes.
7. Never include API keys/tokens in returned artifacts. Record only whether a credential variable/config is present, never its value.
8. If a command fails, record the exact command, exit code, stdout/stderr and continue only where the protocol says continuation is safe.
9. Do not "fix and rerun" inside the same acceptance. Put proposed fixes into `AGENT_NOTES.md` after collecting the original failure trace.

## Execution order

Follow `REMOTE_OPENCODE_ACCEPTANCE_PROTOCOL.md` from T00 through T12.

Run the automated production trace command exactly once first. Repeated semantic runs are performed only in the designated variability section and must use distinct output directories.

## Required return

- machine-generated acceptance archive;
- filled human/agent report template;
- optional notes with observations and proposed fixes, clearly separated from test evidence.
