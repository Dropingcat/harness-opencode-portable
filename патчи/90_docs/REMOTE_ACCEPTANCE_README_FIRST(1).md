# Harness R4.4 L3B Remote Production Acceptance — README FIRST

Date: 2026-09-13
Purpose: deploy the complete Harness checkpoint on the real OpenCode host and collect a reproducible production-semantic trace without changing scientific/control contracts during the run.

## Target OpenCode build supplied by user

Uploaded Windows desktop installer metadata:

- Product: OpenCode
- FileVersion/ProductVersion: **1.18.30**
- Container: Windows NSIS installer (PE32 installer stub)
- Installer SHA256: `dcf723272c930f5dfa73a8561818ae4ad1a346384a859111ffeb554e19ce6567`

The server should preferably use the **same OpenCode version 1.18.30** in its native architecture/package. The Windows installer itself is not required on a Linux server; the acceptance report records the actual server CLI version and binary SHA256.


## Frozen deterministic baseline for this package

Before remote semantic execution, this checkpoint was verified locally with:

- R4 targeted: **111/111 PASS**;
- full Researcher: **588 total / 584 PASS / 4 known TD-015 failures**;
- known failures: 2 Guard + 2 LocalCorpus only;
- runtime compiler: PASS, policy hash `8910fd61122b450212d5bc459cdb52acdc02aa3cf6d87a37c5eaa3778e3cdfef`;
- capability compiler: PASS, policy hash `60105d715f8df50917156216b085f85ee25a2b1deb62947e041bd8537a1a9076`;
- remote/trace targeted tests: **16/16 PASS**.

Any additional or different Researcher failure is a regression for this acceptance.

## Non-negotiable acceptance rule

Do **not** edit Harness code, policies, role handbook, DDC/DQC/ADC, provider registry, evidence material or tests while executing acceptance. A failure is an observation to return, not permission to make the test green.

If the OpenCode agent believes a fix is required, it records the proposed fix in `AGENT_NOTES.md` after the run. It does not apply the fix.

## Minimum prerequisites

- a clean checkout from the supplied package;
- Python 3.11+;
- git;
- the production OpenCode CLI available as `opencode` or passed by `--opencode-bin`;
- the exact production model/provider configured on that host;
- credentials remain only on that host;
- enough disk space for isolated OpenCode run directories and returned trace archive.

## Primary command

From repository root:

```bash
python scripts/remote_acceptance/run_remote_acceptance.py \
  --model '<EXACT_PRODUCTION_MODEL_ID>' \
  --opencode-bin opencode \
  --timeout 180 \
  --output remote_acceptance_runs/production_001 \
  --archive
```

The command creates the machine report and trace artifacts. Then run the explicit named tests from `REMOTE_OPENCODE_ACCEPTANCE_PROTOCOL.md` and fill `REMOTE_OPENCODE_ACCEPTANCE_REPORT_TEMPLATE.md`.

## Return package

Return:

1. `remote_acceptance_runs/production_001.tar.gz`;
2. completed `REMOTE_OPENCODE_ACCEPTANCE_REPORT.md`;
3. `AGENT_NOTES.md` only if the agent observed anomalies/proposed changes.

Do not return API keys, tokens, credential files or unredacted provider secrets.
