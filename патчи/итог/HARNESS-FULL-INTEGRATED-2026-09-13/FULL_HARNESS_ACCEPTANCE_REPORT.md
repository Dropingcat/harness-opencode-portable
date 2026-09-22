# Full Harness Acceptance Report

Date: 2026-09-13
Scope: integrated Writer + Researcher + Coder/code-factory + shared runtime/periphery

## 1. Release intent

This report verifies that the repository can be packaged as one coherent Harness module rather than as separate Writer/Researcher checkpoints. The acceptance boundary covers module tests, shared routing/config compiler gates, event/provenance behavior and deployment inventory. Production semantic OpenCode quality remains an external acceptance gate.

## 2. Canonical module acceptance

### Writer

Command:

```bash
python -m pytest -q tests/writer
```

Result:

- 31 tests PASS
- 15 subtests PASS

### Researcher

Command:

```bash
python scripts/run_researcher_acceptance.py full
```

Result:

- 588 / 588 PASS
- former TD-015 Guard/LocalCorpus baseline failures are closed

R4 focused regression:

```bash
python scripts/run_researcher_acceptance.py r4
```

Result:

- 111 / 111 PASS

### Coder / code-factory

Command:

```bash
python scripts/run_coder_acceptance.py all
```

Result:

- 5 / 5 Coder tests PASS
- code-factory compileall PASS
- gate-policy JSON PASS
- provenance-policy JSON PASS

Covered Coder behaviors:

1. worker -> reviewer -> tester -> auditor -> PASSED -> finalize;
2. replay/event-chain integrity;
3. untrusted artifact requires guard PASS;
4. repeated reviewer failures expose tribunal/convergence requirement;
5. worker submit cannot mutate an arbitrary process-CWD Git repository without explicit workspace authority; the regression is portable to code-only Harness distributions without `.git`.

### Shared cross-module integration

Command:

```bash
PYTHONPATH=.:scripts/researcher:scripts/code-factory python -m pytest -q tests/integration
```

Result:

- 2 / 2 PASS

Verified common runtime routing:

- writing request -> `writing-prose` / `writing`;
- scientific research request -> `academic-research` / `research`;
- implementation request -> `code-implementation` / `code`;
- all use the same compiled runtime policy hash.

## 3. Legacy/shared compatibility layer

The old root compatibility tests were run in bounded groups because a single monolithic invocation exceeds the execution-shell limit in this development environment.

Results:

- compatibility group A: 58 / 58 PASS;
- compatibility group B: 59 / 59 PASS;
- `tests/test_runtime_core.py`: 19 / 19 PASS when split into bounded groups;
- total observed compatibility cases: 136 / 136 PASS.

The split is an execution-environment limit, not a test failure.

## 4. Shared compiler/static gates

Command:

```bash
python scripts/run_harness_acceptance.py gates
```

Results:

- runtime compiler: PASS
  - policy hash `8910fd61122b450212d5bc459cdb52acdc02aa3cf6d87a37c5eaa3778e3cdfef`
- capability compiler: PASS
  - policy hash `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`
- Researcher compileall: PASS
- Coder compileall: PASS
- Writer compileall: PASS
- shared jobs/router/orchestration/capsules compileall: PASS
- factory gate policy JSON: PASS
- artifact provenance policy JSON: PASS
- `git diff --check`: PASS before freeze

## 5. Defects repaired during full-Harness acceptance

### TD-015 closed

The historical four Researcher failures were two defects:

- fallback Guard elevated weak Russian imperative markers to high severity even for internal provenance;
- `tests/fixtures/literature_index_sample.jsonl` was missing from the checkout.

The fallback now keeps `WEAK_RU` low for internal provenance while explicit strong injection signatures remain fail-closed. The fixture is restored. Full Researcher is 588/588 PASS.

### TD-051 closed

Legacy code-factory Git snapshotting used process CWD when no workspace was supplied. A compatibility test therefore demonstrated that worker submission could commit the Harness repository itself.

The runtime now requires explicit `--workdir` or `OPENCODE_FACTORY_WORKDIR`; absent/invalid workspace safely skips snapshotting. A regression test verifies an external disposable controller-repository HEAD is unchanged, so the same acceptance works in both Git-backed development checkouts and code-only release archives.


### TD-052 closed

The first code-only release rehearsal exposed a test-portability defect: the Coder no-implicit-CWD regression itself assumed the Harness distribution contained `.git`. The release archive intentionally omits Git metadata, so the test failed before exercising code-factory behavior.

The regression now creates a disposable controller Git repository and invokes the absolute `factory_ctl.py` path from that repository. This strengthens the invariant and removes any dependency on the release container having `.git`. `tests/coder` remains 5/5 PASS in the canonical checkout and is now eligible for code-only deployment acceptance.

## 6. Open technical debt that remains deliberately visible

The authoritative list is `config/tech_debt.json`; `TECH_DEBT.md` contains rationale. Important open items include:

- TD-016 duplicate Researcher-core layout authority;
- TD-017 provider-priority overlap around `evidence.verify`;
- TD-020 SQLite ResourceWarning cleanup;
- TD-021 Writer/Researcher source identity domains;
- TD-024 live peer Coder/Writer transport + durable outbox;
- TD-035 canonical AssessmentNeed identity;
- TD-036 modular domain Tribunal role packs;
- TD-037 production semantic provider execution/calibration remains partial;
- TD-038 universal cross-layer traceability substrate;
- TD-041 portable RoleCard/RoleReference/RoleParameterGraph interchange;
- TD-042 live dialectic calibration;
- TD-044 semantic identity of dialectic issues;
- TD-046 response ownership / Defender-Advocate arbitration;
- TD-047 multidisciplinary Claim fork/join;
- TD-048 HypothesisCase lifecycle;
- TD-049 evidence independence/dependency groups;
- TD-050 hypothesis-specific EvidenceDigest semantics.

These are not silently waived by this release.

## 7. External production semantic gate

The deterministic Harness package is deployable independently of OpenCode availability. Production semantic Tribunal acceptance still requires the deployment host to execute the existing immutable remote protocol:

`DQC/ADC -> RPB -> TEX -> OpenCode -> PER -> IQT/ARG -> grounding -> graph admission`.

The remote acceptance agent must not edit Harness during the acceptance run.

## 8. Release verdict

**PASS for deterministic integrated Harness packaging.**

Writer, Researcher and Coder are present in one repository, have explicit module acceptance, share one compiled routing/periphery layer, and preserve the project tracker/debt/decision history. Production semantic OpenCode behavior remains a separately visible external gate rather than being falsely claimed as locally verified.

## 9. Code-only distribution rehearsal

A release rehearsal extracted `HARNESS-FULL-WRITER-RESEARCHER-CODER-002.zip` into a directory with no `.git` metadata and reran the canonical module/gate acceptance. Results:

- Writer: 31 tests + 15 subtests PASS;
- Researcher: 588/588 PASS;
- Coder: 5/5 PASS;
- runtime/capability/compiler/static gates: PASS;
- `.git` absent by design.

This closes TD-052 and proves the code milestone is acceptance-capable as a deployment artifact rather than only as a development checkout.
