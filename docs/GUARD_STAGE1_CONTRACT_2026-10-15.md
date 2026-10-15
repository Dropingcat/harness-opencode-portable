# Stage 1: guard correctness and discoverability

Task: HARNESS-GUARD-STAGE1-20261015. Baseline 8297e4b. Scope: existing open TD-RESTORE-01, TD-004 and TD-013. No debt closure or memory/semantic-agent/autonomous-merge activation is authorized.

## Claim and verification budget

Only explicitly successful, complete required scans permit admission. Discovery, a file's presence, a P0-only result or a fixture classifier cannot certify live combined protection. A failed or unavailable required stage blocks dispatch.

Owners: composition worker owns legacy P0/P2 composition, semantic coverage and researcher fallback; artifact worker owns file-scanning CLI, discovery and hash-bound receipts; independent reviewer owns source correctness; independent tester owns negative controls and cold/parallel subprocess runs. Metadata-only auditor owns process acceptance. Two actual reworks maximum, separately paid provider budget zero; no real provider request without explicit authorization. Fixture classifiers are test evidence only, not host certification.

## Modules

1. `guard-core`: guard/src/guard_runner.py, guard/src/semantic_layer.py and scripts/researcher/researcher_core/guard.py plus narrow tests. Reject exceptions, invalid JSON/shapes/verdicts, nonzero exits even with PASS, timeouts, unavailable imports and incomplete P2 coverage. A P0 failure/error never reaches P2. Retain legitimate P0-only reports as explicitly P0-only; never use them as combined admission. Full semantic input coverage or a structured non-PASS is mandatory. No silent head/tail or item-limit bypass. Remove permissive fallback, not the optional P0-only interface.
2. `guard-artifact`: new guard/src/artifact_guard.py, canonical scripts/tools/doc_guard.py CLI, dedicated discovery/receipt module if necessary, narrow tests and docs. Reuse bundled signatures and semantic ClassifierChain/Budget rather than introducing a new provider. `preflight` is readiness metadata, never PASS. `scan --artifact FILE --config CONFIG --json` performs required P0+P2 on the exact bounded UTF-8 bytes, without a session DB. Invalid/unavailable input/stage blocks. Receipt identifies SHA256, byte count, policy/code identity, required/executed stages and complete coverage. No persisted shared mutable scanner state. A standalone receipt is evidence, not cryptographic authorization; consumption must rescan or validate against trusted current inputs and cannot trust editable receipt JSON alone.
3. `guard-integration`: after the two APIs stabilize, align binding/policy/agent discovery docs with one artifact entrypoint and retain explicit legacy DB/P0 interfaces. Integrate verification into bounded admission where safely scoped. No broad native V2 implementation or enabling new host capabilities. Distinguish documented path from host-connected enforcement. Register remaining host gaps rather than declaring them solved.

Acceptance tests: malformed/empty stage output; list/scalar JSON; unknown verdict; PASS with nonzero exit; timeout; missing executable/import/config/provider; partial semantic count/overlong text; nested/list input strings; empty/malformed input; suspicious text in previously omitted middle; artifact changed after scan; stale or forged receipt; clean artifact with deterministic fixture classification; two cold parallel processes in different directories and a copied clean fixture checkout; missing guard with existing runner/controller blocks before a sentinel dispatch. No secrets in argv/output. Controlled fake providers are explicitly marked fixtures.

## Resources and design choice

Contradiction: stronger admission control makes cold starts more fragile. IFR: every cold session identifies its scanner and blocks unexamined artifacts without manual filesystem search. Existing resources: bundled P0 signatures and P2 chain (substance), offline subprocess fixtures (field), manifest/policy and exact hashes (information), factory validators (function), bounded timeouts (time), separate worktree and temporary directories (space). Prefer an intermediary artifact CLI plus preflight and explicit failure cushioning (TRIZ 24/10/11) over guessed aliases or silent fallback.

## Release gates

Run narrow regressions and independent mutations before acceptance; preserve broader unrelated baseline failures. Canonical release uses exact original backups and conflict checks only after independent gates. Matrix regeneration follows any accepted source metadata change. Preserve previous historical certification files. Handoff retains blocked live-provider/native-enforcement scope. No implicit promotion of memory lessons while promotion integrity remains unaccepted.
