# R4.4 L3B — Production OpenCode Semantic Acceptance Protocol

Date: 2026-09-13
Target reference OpenCode version from supplied Windows installer: **1.18.30**.

The purpose is not to prove that an LLM is "correct" from one demonstration. The purpose is to obtain the first reproducible production traces and expose contract, grounding, routing, convergence and role-behaviour failures.

## T00 — Package / Git integrity

From repo root:

```bash
git rev-parse HEAD
git status --short
git fsck --no-progress
```

Acceptance:

- HEAD matches package `GIT_BOUNDARY.txt` / README;
- `git status --short` is empty before test execution;
- `git fsck` succeeds.

Do not continue semantic acceptance from a modified checkout.

## T01 — Environment and OpenCode identity

```bash
python scripts/remote_acceptance/collect_environment.py \
  --repo . \
  --opencode-bin opencode \
  --output remote_acceptance_runs/production_001/environment.json
```

Also record:

```bash
opencode --version
which opencode || where opencode
```

Expected target version is preferably `1.18.30`. If different, do not hide it; continue only as a clearly labelled compatibility run.

## T02 — R4 deterministic acceptance

```bash
python scripts/run_researcher_acceptance.py r4
```

Expected package baseline will be recorded in the deployment manifest. Any failure is blocking before semantic execution.

## T03 — Compiler/static gates

```bash
python scripts/run_researcher_acceptance.py gates
```

Must PASS. Record runtime/capability policy hashes.

## T04 — Full Researcher regression

```bash
python scripts/run_researcher_acceptance.py full
```

Frozen package baseline: 588 total / 584 PASS / four TD-015 failures, specifically 2 Guard + 2 LocalCorpus. Treat any additional/different failure as regression. Do not edit tests to obtain green.

## T05 — Named L3/L3B edge tests

Run with names visible:

```bash
PYTHONPATH=scripts/researcher python -m pytest -vv \
  tests/researcher/test_tribunal_provider_binding.py \
  tests/researcher/test_r4_4_l3_live_dialogue_e2e.py \
  tests/researcher/test_r4_4_l3_live_dialogue_failures.py \
  tests/researcher/test_r4_4_l3_second_role_family_e2e.py \
  tests/researcher/test_r4_4_l3b_response_grounding.py \
  tests/researcher/test_r4_4_l3b_live_advocate_grounding_e2e.py
```

This explicitly exercises:

- wrong role;
- explicit wrong provider;
- provider wrong role-kind;
- provider wrong contract namespace;
- zero healthy provider;
- multiple candidates with deterministic single selection;
- more executors requested than policy allows;
- stale provider after binding;
- timeout;
- invalid JSON;
- hidden sibling evidence;
- second role family;
- RPB/TEX/PER round-trip;
- answer TEX contains exact materialized Q1/Q2;
- machine-readable output contract embedded in TEX;
- MODEL_PRIOR grounding hardening;
- live conditional Advocate structural path.

## T06 — Production provider preflight

```bash
python scripts/router/capability_preflight.py \
  --no-network \
  --output remote_acceptance_runs/production_001/capability_preflight.json
```

Inspect provider `existing.opencode_tribunal_role`.

Required before semantic test:

```text
implemented = true
available = true
status = available
```

If unavailable, stop semantic execution and return the preflight result. This is `FAIL_RUNTIME`, not scientific `OPEN`.

## T07 — Automated real semantic trace

Use the exact production model id:

```bash
python scripts/remote_acceptance/run_remote_acceptance.py \
  --model '<EXACT_PRODUCTION_MODEL_ID>' \
  --opencode-bin opencode \
  --timeout 180 \
  --output remote_acceptance_runs/production_001 \
  --archive
```

The script executes:

1. bounded real Skeptic Q1;
2. real specialist A1;
3. deterministic graph admission;
4. dialectic observation;
5. Q2/A2 only if A1 created an admitted genuinely new issue surface;
6. conditional live Advocate on the material challenge;
7. separate prior-only case with no disclosed evidence.

The script preserves `RPB/TEX/PER/IQT/ARG` and OpenCode run directories.

## T08 — Verify actual-question traceability

In `semantic_bounded_chain/semantic_trace.json` verify:

- `a1.envelope.question_turn_id == q1.turn.id`;
- Q1 turn id is present in `a1.envelope.visible_turn_ids`;
- material under Q1 id contains the exact generated question text;
- A1 does not answer a reconstructed/implicit question.

Failure is a control-contract defect.

## T09 — Verify grounding semantics

For A1/A2/Advocate inspect every grounding item.

Required:

- any `DISCLOSED_EVIDENCE` ref is in visible evidence refs;
- any `PRIOR_ARGUMENT`/`PRIOR_TURN` ref is visible in that TEX;
- `MODEL_PRIOR` contains no fake source/evidence ref;
- a non-OPEN prior-only answer must create research debt;
- a prior-only Advocate DEFEND must not materialize `DEFENDS`.

Record questionable semantic classifications even if deterministic validation accepted them. This is calibration input for TD-042/044/046.

## T10 — Branch isolation

Verify `hidden_sibling_present_in_q1_tex = false` and `hidden_sibling_present_in_a1_tex = false`.

If provider invents/cites hidden refs anyway, Harness must reject them. Do not add the hidden material merely to make the response pass.

## T11 — Three-run variability test

Run the semantic test three times with **unchanged** Harness, OpenCode version, model and provider config:

```bash
for n in 1 2 3; do
  python scripts/remote_acceptance/run_remote_acceptance.py \
    --model '<EXACT_PRODUCTION_MODEL_ID>' \
    --opencode-bin opencode \
    --timeout 180 \
    --skip-baseline \
    --output "remote_acceptance_runs/variability_${n}" \
    --archive
done
```

Do not force deterministic seeds in the provider. We want to observe semantic variability while control fingerprints remain comparable.

Compare:

- question focus;
- A1 position/grounding;
- discovered issue types;
- whether Q2 is triggered;
- Advocate outcome;
- unsupported causal/scope upgrades;
- false evidence grounding;
- no-progress/rephrasing behaviour.

## T12 — Return package

Return:

- `production_001.tar.gz`;
- `variability_1.tar.gz`, `variability_2.tar.gz`, `variability_3.tar.gz`;
- completed report template;
- optional `AGENT_NOTES.md`.

Before returning, confirm no secret values are included. Trace files may contain scientific fixture text and model output, but never API keys/tokens.

## Stop conditions

Stop and return evidence immediately if:

- checkout is dirty before testing;
- R4/gates regress;
- provider preflight is unavailable;
- OpenCode CLI command differs incompatibly from the expected `run --pure --model --dir` shape;
- credentials leak into generated artifacts;
- runtime silently swaps provider after RPB compilation.

Semantic `OPEN`, `REQUEST_EVIDENCE`, rejected hallucinated refs and lack of Q2 due no new issue are **not** infrastructure failures. They are valid scientific/behavioural observations.
